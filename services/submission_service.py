"""投稿服务"""
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
import time
from loguru import logger

from core.database import get_db
from core.models import Submission, MessageCache, StoredPost, PublishRecord, BlackList
from core.enums import SubmissionStatus, PublishPlatform
from processors.pipeline import get_shared_pipeline, ProcessingPipeline
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Moved frequently used imports to module level to avoid runtime import overhead
from config import get_settings
from sqlalchemy import select, and_, delete, update, func
from services.notification_service import NotificationService
from utils.common import deduplicate_preserve_order, get_platform_config
from core.task_queue import build_queue_backend, TaskQueueBackend


class SubmissionService:
    """投稿服务，管理投稿的生命周期"""
    
    def __init__(self):
        self.logger = logger.bind(module="submission")
        # 共享全局管道，避免重复初始化
        self.pipeline = get_shared_pipeline()
        self.publishers = {}
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._queue_backend: TaskQueueBackend = build_queue_backend()
        self._pub_workers: Dict[str, asyncio.Task] = {}
        # 防重复处理：同一 submission_id 在单进程内只允许一个处理协程
        self._inflight: Set[int] = set()
        self._inflight_lock: asyncio.Lock = asyncio.Lock()
        # 跟踪投稿处理任务，用于优雅停机时取消
        self._proc_tasks: Dict[int, asyncio.Task] = {}
        self._stopping: bool = False
        
    async def initialize(self):
        """初始化服务"""
        await self.pipeline.initialize()
        
        # 动态获取已注册的发送器（实例及其生命周期由 PluginManager 统一管理）
        from core.plugin import plugin_manager
        self.publishers = dict(plugin_manager.publishers)
        
        # 调试日志：显示获取到的发布器
        if self.publishers:
            self.logger.info(f"已获取发布器: {list(self.publishers.keys())}")
        else:
            self.logger.warning("未获取到任何发布器！plugin_manager.publishers 为空")

        self.logger.info("投稿服务初始化完成")
        # 初始化定时计划
        try:
            self._setup_send_schedules()
        except Exception as e:
            self.logger.error(f"设置定时计划失败: {e}")
        # 恢复待处理投稿（处理 120 秒等待期间发生重启的情况）
        try:
            await self._resume_pending_submissions()
        except Exception as e:
            self.logger.error(f"恢复待处理投稿失败: {e}")
        
    async def shutdown(self):
        """关闭服务"""
        # 标记停机，通知处理循环尽快退出
        self._stopping = True
        await self.pipeline.shutdown()
        # 停止调度器与工作协程
        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=False)
                self.scheduler = None
        except Exception:
            pass
        try:
            for name, task in list(self._pub_workers.items()):
                if task and not task.done():
                    task.cancel()
            self._pub_workers.clear()
        except Exception:
            pass
        # 取消所有仍在运行的投稿处理任务
        try:
            tasks = [t for t in self._proc_tasks.values() if t and not t.done()]
            for t in tasks:
                try:
                    t.cancel()
                except Exception:
                    pass
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    pass
            self._proc_tasks.clear()
        except Exception:
            pass
            
    async def create_submission(self, sender_id: str, receiver_id: str, 
                              message: Dict[str, Any]) -> Optional[int]:
        """创建新投稿
        
        Args:
            sender_id: 发送者ID
            receiver_id: 接收者ID
            message: 消息内容
            
        Returns:
            投稿ID，失败返回None
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 检查是否在黑名单（使用缓存）
                from core.data_cache_service import DataCacheService
                
                # 获取账号组
                group_name = await self.get_group_name(receiver_id)
                
                is_blacklisted = await DataCacheService.check_blacklist(
                    user_id=sender_id,
                    group_name=group_name,
                    session=session,
                    use_cache=True
                )
                
                if is_blacklisted:
                    self.logger.info(f"用户 {sender_id} 在黑名单中，拒绝投稿")
                    return None
                    
                # 创建投稿（创建前先清理该 sender/receiver 的历史消息缓存，避免累计过多）
                try:
                    from core.message_cache_service import MessageCacheService
                    await MessageCacheService.clear_messages(sender_id, receiver_id, session)
                except Exception as _e:
                    self.logger.warning(f"预清理历史消息缓存失败: {sender_id}/{receiver_id}: {_e}")

                # 创建投稿
                submission = Submission(
                    sender_id=sender_id,
                    sender_nickname=message.get('sender', {}).get('nickname'),
                    receiver_id=receiver_id,
                    group_name=group_name,
                    raw_content=[message],
                    status=SubmissionStatus.PENDING.value
                )
                session.add(submission)
                await session.commit()
                
                self.logger.info(f"创建投稿: {submission.id}")
                
                # 发送确认消息给用户
                try:
                    notifier = NotificationService()
                    confirm_message = (
                        f"🎉 收到你的投稿！\n"
                        f"⏰ 投稿编号: #{submission.id}\n\n"
                        f"我们的 AI 正在审核中，请耐心等待..."
                    )
                    asyncio.create_task(
                        notifier.send_to_user(sender_id, confirm_message, group_name)
                    )
                except Exception as e:
                    self.logger.error(f"发送投稿确认消息失败: {e}")
                
                # 异步处理投稿
                asyncio.create_task(self.process_submission(submission.id))
                
                return submission.id
                
        except Exception as e:
            self.logger.error(f"创建投稿失败: {e}", exc_info=True)
            return None
            
    async def process_submission(self, submission_id: int):
        """处理投稿（带重启恢复的动态等待）。

        - 根据投稿 `created_at` 计算剩余等待时间，支持在 120 秒等待期间重启后继续等待剩余时间。
        - 使用进程内去重，避免同一投稿被并发处理。
        """
        # 进程内防重复
        async with self._inflight_lock:
            if submission_id in self._inflight:
                try:
                    self.logger.info(f"投稿 {submission_id} 已在处理，跳过重复触发")
                except Exception:
                    pass
                return
            self._inflight.add(submission_id)
            # 记录当前任务以便停机时取消
            try:
                cur = asyncio.current_task()
                if cur is not None:
                    self._proc_tasks[submission_id] = cur
            except Exception:
                pass

        try:
            settings = get_settings()
            wait_time = max(0, int(settings.processing.wait_time))

            # 读取投稿创建时间与当前状态，用于计算剩余等待
            db = await get_db()
            async with db.get_session() as session:
                stmt = select(Submission).where(Submission.id == submission_id)
                result = await session.execute(stmt)
                submission = result.scalar_one_or_none()
                # 获取该会话缓存中最早一条消息的时间戳（优先用消息时间作为等待基准，更贴合“消息窗口”概念）
                earliest_ts: Optional[float] = None
                try:
                    ts_stmt = (
                        select(func.min(MessageCache.message_time))
                        .where(
                            and_(
                                MessageCache.sender_id == submission.sender_id,  # type: ignore[arg-type]
                                MessageCache.receiver_id == submission.receiver_id,  # type: ignore[arg-type]
                            )
                        )
                    )
                    ts_result = await session.execute(ts_stmt)
                    earliest_ts = ts_result.scalar_one_or_none()
                except Exception:
                    earliest_ts = None

            if not submission:
                return

            # 仅在待处理投稿上执行等待逻辑；其他状态直接进入后续流程
            if submission.status == SubmissionStatus.PENDING.value:
                # 滑动窗口：自“最后一条消息”起静默 wait_time 秒才进入处理
                # 先确定创建时间作为兜底基准
                created_ts: Optional[float] = None
                try:
                    created_ts = submission.created_at.timestamp() if submission.created_at else None
                except Exception:
                    created_ts = None

                # 获取当前最新消息时间戳；若无缓存，则以创建时间兜底
                async def _get_last_ts() -> float:
                    db2 = await get_db()
                    async with db2.get_session() as s2:
                        try:
                            last_stmt = (
                                select(func.max(MessageCache.message_time))
                                .where(
                                    and_(
                                        MessageCache.sender_id == submission.sender_id,  # type: ignore[arg-type]
                                        MessageCache.receiver_id == submission.receiver_id,  # type: ignore[arg-type]
                                    )
                                )
                            )
                            last_res = await s2.execute(last_stmt)
                            last_ts = last_res.scalar_one_or_none()
                        except Exception:
                            last_ts = None
                    if isinstance(last_ts, (int, float)) and last_ts > 0:
                        return float(last_ts)
                    if isinstance(earliest_ts, (int, float)) and earliest_ts > 0:
                        return float(earliest_ts)
                    return float(created_ts or time.time())

                # 循环等待直到与最后一条消息间隔 >= wait_time
                # 节流日志：首次与每 30s 打印一次，或剩余 <= 5s
                first_logged = False
                last_info_log_ts: float = 0.0
                while True:
                    # 停机则中断
                    if self._stopping:
                        raise asyncio.CancelledError()
                    # 若投稿已不再处于 PENDING（例如被删除/改状态），立即退出
                    try:
                        db_chk = await get_db()
                        async with db_chk.get_session() as s_chk:
                            st_stmt = select(Submission.status).where(Submission.id == submission_id)
                            st_res = await s_chk.execute(st_stmt)
                            cur_status = st_res.scalar_one_or_none()
                    except Exception:
                        cur_status = None
                    if cur_status != SubmissionStatus.PENDING.value:
                        return
                    last_ts = await _get_last_ts()
                    gap = max(0.0, time.time() - last_ts)
                    if gap >= float(wait_time):
                        break
                    remaining = max(0.0, float(wait_time) - gap)
                    sleep_s = min(remaining, 5.0)
                    now_ts = time.time()
                    # 仅在首次、距离上次 >=30s、或剩余<=5s 时输出 INFO 日志
                    if (not first_logged) or (now_ts - last_info_log_ts >= 30.0) or (remaining <= 5.0):
                        try:
                            self.logger.info(f"等待 {int(sleep_s)} 秒（距最后一条消息 {int(gap)}s < {wait_time}s）")
                        except Exception:
                            pass
                        first_logged = True
                        last_info_log_ts = now_ts
                    try:
                        await asyncio.sleep(max(0.5, sleep_s))
                    except asyncio.CancelledError:
                        # 停机或外部取消
                        raise
            
            # 合并消息
            await self.merge_messages(submission_id)
            
            # 执行处理管道
            success = await self.pipeline.process_submission(submission_id)
            
            if success:
                # 发送审核通知
                await self.send_audit_notification(submission_id)
            else:
                self.logger.error(f"处理投稿失败: {submission_id}")
                
        except Exception as e:
            self.logger.error(f"处理投稿异常: {e}", exc_info=True)
        finally:
            # 释放 in-flight 标记
            async with self._inflight_lock:
                self._inflight.discard(submission_id)
                try:
                    self._proc_tasks.pop(submission_id, None)
                except Exception:
                    pass

    async def _resume_pending_submissions(self):
        """在服务启动时恢复待处理投稿，确保等待中的投稿不会因重启而永久卡住。

        策略：
        - 扫描状态为 PENDING 的投稿；依据 `created_at` 由 `process_submission` 自行计算剩余等待并继续处理。
        - 避免一次性创建过多任务：可按创建时间排序逐一拉起（这里简单并发创建，由 in-flight 去重保障）。
        """
        db = await get_db()
        async with db.get_session() as session:
            stmt = (
                select(Submission)
                .where(Submission.status == SubmissionStatus.PENDING.value)
                .order_by(Submission.created_at)
            )
            result = await session.execute(stmt)
            pendings: List[Submission] = result.scalars().all()

        if not pendings:
            return

        settings = get_settings()
        wait_time = max(0, int(settings.processing.wait_time))
        now = datetime.now()
        for sub in pendings:
            try:
                if not sub.created_at:
                    remain = wait_time
                else:
                    elapsed = (now - sub.created_at).total_seconds()
                    remain = max(0, int(wait_time - max(0.0, elapsed)))
                try:
                    self.logger.info(
                        f"恢复待处理投稿 {sub.id}（sender={sub.sender_id}）：剩余等待 {remain} 秒"
                    )
                except Exception:
                    pass
                # 交由 process_submission 动态等待与处理（含 in-flight 去重）
                asyncio.create_task(self.process_submission(int(sub.id)))
            except Exception as e:
                self.logger.error(f"恢复投稿 {getattr(sub, 'id', None)} 失败: {e}")
            
    async def merge_messages(self, submission_id: int):
        """合并用户的多条消息"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取投稿
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return
                
            # 获取该用户的所有消息缓存（使用 MessageCacheService）
            from core.message_cache_service import MessageCacheService
            cached_messages = await MessageCacheService.get_messages(
                sender_id=submission.sender_id,
                receiver_id=submission.receiver_id,
                db=session
            )
            
            if cached_messages:
                # 合并消息
                messages = []
                for msg_data in cached_messages:
                    if msg_data.get('message_content'):
                        messages.append(msg_data['message_content'])
                        
                submission.raw_content = messages
                await session.commit()
                
    async def send_audit_notification(self, submission_id: int):
        """发送审核通知到管理群"""
        try:
            # 复用通知服务的统一逻辑（含图片发送）
            notifier = NotificationService()
            ok = await notifier.send_audit_request(submission_id)
            if not ok:
                self.logger.error(f"发送审核通知失败: submission_id={submission_id}")
        except Exception as e:
            self.logger.error(f"发送审核通知异常: {e}", exc_info=True)
            
    async def get_group_name(self, receiver_id: str) -> Optional[str]:
        """根据接收者ID获取账号组名称"""
        settings = get_settings()
        
        for group_name, group in settings.account_groups.items():
            if group.main_account.qq_id == receiver_id:
                return group_name
            for minor in group.minor_accounts:
                if minor.qq_id == receiver_id:
                    return group_name
                    
        return None

    async def delete_submission(self, submission_id: int) -> Dict[str, Any]:
        """删除投稿：同步删除外部平台内容并将投稿状态置为 DELETED。
        
        - 查找该投稿在各平台的发布记录；对支持的平台（qzone、bilibili）尝试删除
        - 至少一个平台删除成功即视为成功；若均失败，返回最后错误
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                stmt = select(Submission).where(Submission.id == submission_id)
                r = await session.execute(stmt)
                submission = r.scalar_one_or_none()
                if not submission:
                    return {"success": False, "message": "投稿不存在"}

            # 若尚未发布，则直接置为删除并返回成功
            if submission.status != SubmissionStatus.PUBLISHED.value:
                async with (await get_db()).get_session() as session2:
                    upd = update(Submission).where(Submission.id == submission_id).values(status=SubmissionStatus.DELETED.value)
                    await session2.execute(upd)
                    await session2.commit()
                return {"success": True, "message": "已删除"}

            # 已发布：按发布记录逐平台分发，调用 publishser.delete_by_publish_record
            any_success = False
            try:
                async with (await get_db()).get_session() as session2:
                    pr_stmt = select(PublishRecord).where(PublishRecord.submission_ids.isnot(None)).order_by(PublishRecord.created_at.desc())
                    r2 = await session2.execute(pr_stmt)
                    records = r2.scalars().all()
            except Exception:
                records = []

            # 动态获取发布器（如果 self.publishers 为空）
            publishers = self.publishers
            if not publishers:
                from core.plugin import plugin_manager
                publishers = dict(plugin_manager.publishers)
                if not publishers:
                    self.logger.warning("未获取到任何发布器，跳过平台删除")
                    # 即使没有发布器，也标记为删除
                    async with (await get_db()).get_session() as session2:
                        upd = update(Submission).where(Submission.id == submission_id).values(status=SubmissionStatus.DELETED.value)
                        await session2.execute(upd)
                        await session2.commit()
                    return {"success": True, "message": "已删除（无平台内容）"}

            # 根据平台键映射到具体 publisher 实例
            platform_to_publisher: Dict[str, Any] = {}
            for name, pub in publishers.items():
                try:
                    key = getattr(pub.platform, 'value', None)
                    if key:
                        platform_to_publisher[key] = pub
                except Exception:
                    continue

            for rec in records:
                try:
                    subs = rec.submission_ids or []
                    if submission_id not in subs:
                        continue
                    publisher = platform_to_publisher.get(rec.platform)
                    if not publisher:
                        continue
                    if hasattr(publisher, 'delete_by_publish_record'):
                        res = await publisher.delete_by_publish_record(rec)
                        if res and res.get('success'):
                            any_success = True
                except Exception:
                    continue

            # 仅当外部平台至少一个删除成功时，才更新状态为 DELETED
            if any_success:
                async with (await get_db()).get_session() as session2:
                    upd = update(Submission).where(Submission.id == submission_id).values(status=SubmissionStatus.DELETED.value)
                    await session2.execute(upd)
                    await session2.commit()
                return {"success": True, "message": "已删除"}
            else:
                return {"success": False, "message": "未能删除，请稍后再试"}
        except Exception as e:
            self.logger.error(f"删除投稿失败: {e}")
            return {"success": False, "message": "未能删除，请稍后再试"}
        
    async def get_pending_submissions(self, group_name: Optional[str] = None) -> List[Submission]:
        """获取待处理的投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # select, func are imported at module level
            
            conditions = [
                Submission.status.in_([
                    SubmissionStatus.PENDING.value,
                    SubmissionStatus.PROCESSING.value,
                    SubmissionStatus.WAITING.value
                ])
            ]
            
            if group_name:
                conditions.append(Submission.group_name == group_name)
                
            stmt = select(Submission).where(and_(*conditions)).order_by(Submission.created_at)
            result = await session.execute(stmt)
            return result.scalars().all()
            
    async def get_stored_posts(self, group_name: str) -> List[StoredPost]:
        """获取暂存的投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # select imported at module level
            stmt = select(StoredPost).where(
                StoredPost.group_name == group_name
            ).order_by(StoredPost.priority.desc(), StoredPost.created_at)
            
            result = await session.execute(stmt)
            return result.scalars().all()
            
    async def publish_stored_posts(self, group_name: str) -> bool:
        """发布暂存的投稿"""
        try:
            # 获取暂存投稿
            stored_posts = await self.get_stored_posts(group_name)
            
            if not stored_posts:
                self.logger.info(f"组 {group_name} 没有暂存的投稿")
                return True
                
            # 获取投稿详情
            db = await get_db()
            async with db.get_session() as session:
                submission_ids = [post.submission_id for post in stored_posts]
                
                stmt = select(Submission).where(Submission.id.in_(submission_ids))
                result = await session.execute(stmt)
                submissions = result.scalars().all()
                
            # 使用发送器发布到所有已启用平台（各自根据平台配置生成文案/图片源）
            if not self.publishers:
                # 尝试重新获取发布器
                from core.plugin import plugin_manager
                self.publishers = dict(plugin_manager.publishers)
                
                if not self.publishers:
                    self.logger.error(f"没有可用的发送器 (plugin_manager.publishers: {list(plugin_manager.publishers.keys())})")
                    return False
                else:
                    self.logger.info(f"重新获取发布器成功: {list(self.publishers.keys())}")

            platform_results: Dict[str, List[Dict[str, Any]]] = {}
            for name, publisher in self.publishers.items():
                try:
                    res = await publisher.batch_publish_submissions([s.id for s in submissions])
                    platform_results[name] = res
                except Exception as e:
                    self.logger.error(f"平台 {name} 发布失败: {e}")
                    platform_results[name] = [{'success': False, 'error': str(e)}] * len(submissions)

            # 若任一平台成功则标记投稿为已发布
            for i, sub in enumerate(submissions):
                ok_any = False
                for name, results in platform_results.items():
                    if i < len(results) and results[i].get('success'):
                        ok_any = True
                if ok_any:
                    sub.status = SubmissionStatus.PUBLISHED.value
                    sub.published_at = datetime.now()

            # 清空暂存区
            stmt = delete(StoredPost).where(StoredPost.group_name == group_name)
            await session.execute(stmt)
            await session.commit()

            self.logger.info(f"发布 {len(submissions)} 个投稿完成（平台：{list(self.publishers.keys())}）")
            return True
                    
        except Exception as e:
            self.logger.error(f"发布暂存投稿失败: {e}", exc_info=True)
            return False
            
    async def publish_single_submission(self, submission_id: int) -> bool:
        """发布单条投稿，并在成功后从暂存区移除该条
        
        Args:
            submission_id: 投稿ID
        
        Returns:
            是否发布成功
        """
        try:
            # 所有平台尝试发布，任一成功即视为成功
            if not self.publishers:
                # 尝试重新获取发布器
                from core.plugin import plugin_manager
                self.publishers = dict(plugin_manager.publishers)
                
                if not self.publishers:
                    self.logger.error("发布失败: 未找到可用发送器（请检查 config/publishers/*.yml 的 enabled）")
                    return False
                else:
                    self.logger.info(f"重新获取发布器成功: {list(self.publishers.keys())}")
            any_success = False
            error_details: List[str] = []
            for name, publisher in self.publishers.items():
                result = await publisher.publish_submission(submission_id)
                if result.get('success'):
                    any_success = True
                else:
                    detail = result.get('error') or result.get('message') or str(result)
                    error_details.append(f"{name}: {detail}")

            if any_success:
                db = await get_db()
                async with db.get_session() as session:
                    stmt = delete(StoredPost).where(StoredPost.submission_id == submission_id)
                    await session.execute(stmt)
                    await session.commit()
                return True
            else:
                msg = "; ".join(error_details) if error_details else '未知错误'
                self.logger.error(f"发布失败: {msg}")
                return False
        except Exception as e:
            self.logger.error(f"发布单条投稿失败: {e}", exc_info=True)
            return False

    async def publish_single_submission_for_platforms(self, submission_id: int, platform_keys: List[str]) -> bool:
        """为指定平台发布单条投稿（独立模式）
        
        Args:
            submission_id: 投稿ID
            platform_keys: 要发布的平台键列表
        
        Returns:
            是否发布成功
        """
        try:
            if not platform_keys:
                return True
            
            any_success = False
            error_details: List[str] = []
            
            for name, publisher in self.publishers.items():
                platform_key = getattr(publisher.platform, 'value', '')
                if platform_key not in platform_keys:
                    continue
                
                result = await publisher.publish_submission(submission_id)
                if result.get('success'):
                    any_success = True
                else:
                    detail = result.get('error') or result.get('message') or str(result)
                    error_details.append(f"{name}: {detail}")
            
            if any_success:
                # 独立模式：从暂存的 pending_platforms 中移除已成功的平台
                db = await get_db()
                async with db.get_session() as session:
                    stmt = select(StoredPost).where(StoredPost.submission_id == submission_id)
                    result = await session.execute(stmt)
                    stored = result.scalar_one_or_none()
                    
                    if stored:
                        pending = stored.pending_platforms or []
                        if isinstance(pending, list):
                            # 移除已发布的平台
                            for key in platform_keys:
                                if key in pending:
                                    pending.remove(key)
                            stored.pending_platforms = pending
                            
                            # 若所有平台都已发布，删除暂存记录
                            if not pending:
                                await session.delete(stored)
                        
                        await session.commit()
                return True
            else:
                msg = "; ".join(error_details) if error_details else '未知错误'
                self.logger.error(f"发布平台 {platform_keys} 失败: {msg}")
                return False
        except Exception as e:
            self.logger.error(f"发布单条投稿到指定平台失败: {e}", exc_info=True)
            return False
            
    def _setup_send_schedules(self):
        """根据各平台 send_schedule 设置定时任务，任务入队到各自发布器队列。"""
        if not self.scheduler:
            # 显式设置为本地时区，避免默认 UTC 造成触发时间偏移
            try:
                from tzlocal import get_localzone  # 延迟导入，避免环境缺失导致启动失败
                tz = get_localzone()
            except Exception:
                tz = None
            self.scheduler = AsyncIOScheduler(timezone=tz) if tz else AsyncIOScheduler()
            self.scheduler.start()
            try:
                self.logger.info(f"启动定时调度器，timezone={getattr(self.scheduler, 'timezone', None)}")
            except Exception:
                pass
        # 为每个 publisher 建立队列与 worker，并注册 cron 任务
        from utils.common import get_platform_config
        for pub_name, publisher in self.publishers.items():
            cfg = get_platform_config(publisher.platform.value) or {}
            times: List[str] = cfg.get('send_schedule') or []
            if not times:
                continue
            # 准备队列与 worker
            self._ensure_publisher_worker(pub_name)
            # 去重
            seen = set()
            for t in times:
                t = (t or '').strip()
                if not t or t in seen:
                    continue
                seen.add(t)
                # 解析 HH:MM 或 HH:MM:SS
                parts = t.split(':')
                try:
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    second = int(parts[2]) if len(parts) > 2 else 0
                except Exception:
                    self.logger.warning(f"无效的 send_schedule 时间格式: {t}")
                    continue
                # 与调度器使用相同时区
                _tz = getattr(self.scheduler, 'timezone', None)
                if _tz:
                    trigger = CronTrigger(hour=hour, minute=minute, second=second, timezone=_tz)
                else:
                    trigger = CronTrigger(hour=hour, minute=minute, second=second)
                # 允许小范围延迟（例如程序刚恢复）仍然触发；合并积压任务
                self.scheduler.add_job(
                    self._enqueue_scheduled_group_jobs,
                    trigger,
                    args=[pub_name],
                    id=f"sched_{pub_name}_{t}",
                    replace_existing=True,
                    misfire_grace_time=300,
                    coalesce=True,
                )
                try:
                    self.logger.info(f"注册定时任务[{pub_name}] {t} -> h={hour},m={minute},s={second}")
                except Exception:
                    pass

    def _ensure_publisher_worker(self, pub_name: str):
        if pub_name not in self._pub_workers or self._pub_workers[pub_name].done():
            self._pub_workers[pub_name] = asyncio.create_task(self._publisher_worker(pub_name))

    async def _enqueue_scheduled_group_jobs(self, pub_name: str):
        """按组入队执行 flush（避免一次处理过大批量）。"""
        try:
            settings = get_settings()
            try:
                now_str = datetime.now(getattr(self.scheduler, 'timezone', None)).strftime('%Y-%m-%d %H:%M:%S %Z') if self.scheduler else ''
                self.logger.info(f"定时触发[{pub_name}] at {now_str}; groups={list(settings.account_groups.keys())}")
            except Exception:
                pass
            await self._queue_backend.ensure_queue(pub_name)
            # 逐组入队
            for group_name in list(settings.account_groups.keys()):
                try:
                    await self._queue_backend.enqueue(pub_name, {'type': 'flush_group', 'group_name': group_name})
                except Exception as e:
                    self.logger.error(f"入队失败 {pub_name}/{group_name}: {e}")
        except Exception as e:
            self.logger.error(f"定时入队失败 {pub_name}: {e}")

    async def _publisher_worker(self, pub_name: str):
        """每个发布器一个串行 worker，消费队列任务。"""
        while True:
            try:
                popped = await self._queue_backend.pop(pub_name, timeout=5)
                if popped is None:
                    await asyncio.sleep(0.2)
                    continue
                _token, job = popped
                if not isinstance(job, dict):
                    continue
                jtype = job.get('type')
                if jtype == 'flush_group':
                    g = job.get('group_name')
                    try:
                        ok = await self.publish_stored_posts_for_publisher(g, pub_name)
                        self.logger.info(f"[{pub_name}] 组 {g} 定时发送完成: {ok}")
                    except Exception as e:
                        self.logger.error(f"[{pub_name}] 组 {g} 定时发送失败: {e}")
                # 轻微等待，避免打满平台接口
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"发布器 worker 异常 {pub_name}: {e}")

    async def publish_stored_posts_for_publisher(self, group_name: str, publisher_name: str) -> bool:
        """仅通过指定发布器发送该组的暂存投稿（独立模式）。

        独立模式：只发布该平台待发布的投稿，发布成功后从 pending_platforms 中移除该平台。
        当 pending_platforms 为空时，删除暂存记录。
        """
        try:
            stored_posts = await self.get_stored_posts(group_name)
            if not stored_posts:
                try:
                    self.logger.info(f"[{publisher_name}] 组 {group_name} 暂无待发送投稿")
                except Exception:
                    pass
                return True

            publisher = self.publishers.get(publisher_name)
            if not publisher:
                self.logger.error(f"找不到发布器: {publisher_name}")
                return False

            platform_key = getattr(publisher.platform, 'value', '')
            
            # 独立模式：只处理该平台待发布的投稿
            to_publish_posts = []
            for sp in stored_posts:
                pending = sp.pending_platforms or []
                if isinstance(pending, list) and platform_key in pending:
                    to_publish_posts.append(sp)
            
            if not to_publish_posts:
                try:
                    self.logger.info(f"[{publisher_name}] 组 {group_name} 无需该平台发布的投稿")
                except Exception:
                    pass
                return True

            submission_ids = [p.submission_id for p in to_publish_posts]
            db = await get_db()
            async with db.get_session() as session:
                # 加载投稿
                stmt = select(Submission).where(Submission.id.in_(submission_ids))
                result = await session.execute(stmt)
                submissions = result.scalars().all()
            
            if not submissions:
                try:
                    self.logger.info(f"[{publisher_name}] 组 {group_name} 暂无有效投稿记录")
                except Exception:
                    pass
                return True

            # 只由该发布器发布
            try:
                results = await publisher.batch_publish_submissions([s.id for s in submissions])
                # 统计本轮发布结果
                try:
                    total = len(results)
                    success_count = sum(1 for r in results if r and r.get('success')) if isinstance(results, list) else 0
                    fail_count = total - success_count
                    self.logger.info(f"[{publisher_name}] 组 {group_name} 本轮发布：成功 {success_count} / 失败 {fail_count} / 总计 {total}")
                except Exception:
                    pass
            except Exception as e:
                self.logger.error(f"平台 {publisher_name} 批量发布失败: {e}")
                return False

            # 独立模式：从 pending_platforms 中移除该平台，清理已完成的暂存记录
            try:
                async with (await get_db()).get_session() as session2:
                    # 重新加载暂存记录（避免脏读）
                    stmt = select(StoredPost).where(StoredPost.id.in_([sp.id for sp in to_publish_posts]))
                    r = await session2.execute(stmt)
                    current_stored = r.scalars().all()
                    
                    # 构建本次发布的成功投稿ID集合
                    success_submission_ids = set()
                    for i, res in enumerate(results):
                        if res and res.get('success') and i < len(submissions):
                            success_submission_ids.add(submissions[i].id)
                    
                    to_delete_ids: List[int] = []
                    for sp in current_stored:
                        if sp.submission_id in success_submission_ids:
                            pending = sp.pending_platforms or []
                            if isinstance(pending, list) and platform_key in pending:
                                pending.remove(platform_key)
                                sp.pending_platforms = pending
                                
                                # 若所有平台都已发布，标记删除
                                if not pending:
                                    to_delete_ids.append(sp.id)
                    
                    # 删除已完成的暂存记录
                    if to_delete_ids:
                        del_stmt = delete(StoredPost).where(StoredPost.id.in_(to_delete_ids))
                        await session2.execute(del_stmt)
                    
                    await session2.commit()
                    
                    try:
                        self.logger.info(f"[{publisher_name}] 清理已完成的暂存记录: {len(to_delete_ids)} 条")
                    except Exception:
                        pass
            except Exception as e:
                self.logger.error(f"清理暂存记录失败: {e}")
            
            # 返回是否至少有一条成功
            try:
                success_any = any(r and r.get('success') for r in (results or []))  # type: ignore[name-defined]
                return success_any
            except Exception:
                return True
        except Exception as e:
            self.logger.error(f"按平台发布暂存失败: {e}", exc_info=True)
            return False
        
    async def clear_stored_posts(self, group_name: str) -> bool:
        """清空暂存区"""
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 获取最小编号用于回滚
                stmt = select(func.min(StoredPost.publish_id)).where(
                    StoredPost.group_name == group_name
                )
                result = await session.execute(stmt)
                min_num = result.scalar()
                
                if min_num:
                    # 删除暂存投稿
                    stmt = delete(StoredPost).where(StoredPost.group_name == group_name)
                    await session.execute(stmt)
                    
                    # 回滚编号
                    num_file = f"data/cache/numb/{group_name}_numfinal.txt"
                    with open(num_file, 'w') as f:
                        f.write(str(min_num))
                        
                    await session.commit()
                    
                    self.logger.info(f"清空暂存区，回滚编号到 {min_num}")
                    return True
                else:
                    self.logger.info("暂存区已经是空的")
                    return True
                    
        except Exception as e:
            self.logger.error(f"清空暂存区失败: {e}", exc_info=True)
            return False
