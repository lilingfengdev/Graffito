"""投稿服务"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from core.database import get_db
from core.models import Submission, MessageCache, StoredPost, PublishRecord
from core.enums import SubmissionStatus, PublishPlatform
from processors.pipeline import ProcessingPipeline
from publishers.qzone import QzonePublisher
from publishers.bilibili import BilibiliPublisher

# Moved frequently used imports to module level to avoid runtime import overhead
from config import get_settings
from sqlalchemy import select, and_, delete, update, func
from services.notification_service import NotificationService
from utils.common import deduplicate_preserve_order, get_platform_config


class SubmissionService:
    """投稿服务，管理投稿的生命周期"""
    
    def __init__(self):
        self.logger = logger.bind(module="submission")
        self.pipeline = ProcessingPipeline()
        self.publishers = {}
        
    async def initialize(self):
        """初始化服务"""
        await self.pipeline.initialize()
        
        # 初始化发送器
        settings = get_settings()
        
        if settings.publishers.get('qzone'):
            qzone_config = settings.publishers['qzone']
            if hasattr(qzone_config, 'dict'):
                qzone_config = qzone_config.dict()
            elif hasattr(qzone_config, '__dict__'):
                qzone_config = qzone_config.__dict__
                
            if qzone_config.get('enabled'):
                qzone_publisher = QzonePublisher(qzone_config)
                await qzone_publisher.initialize()
                self.publishers['qzone'] = qzone_publisher

        # 初始化B站发送器
        if settings.publishers.get('bilibili'):
            bili_config = settings.publishers['bilibili']
            if hasattr(bili_config, 'dict'):
                bili_config = bili_config.dict()
            elif hasattr(bili_config, '__dict__'):
                bili_config = bili_config.__dict__
            if bili_config.get('enabled'):
                bili_publisher = BilibiliPublisher(bili_config)
                await bili_publisher.initialize()
                self.publishers['bilibili'] = bili_publisher
                
        self.logger.info("投稿服务初始化完成")
        
    async def shutdown(self):
        """关闭服务"""
        await self.pipeline.shutdown()
        
        for publisher in self.publishers.values():
            await publisher.shutdown()
            
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
                # 检查是否在黑名单
                # SQLAlchemy imports moved to module level
                # BlackList import kept as is to avoid potential circular import
                
                # 获取账号组
                group_name = await self.get_group_name(receiver_id)
                
                stmt = select(BlackList).where(
                    and_(
                        BlackList.user_id == sender_id,
                        BlackList.group_name == group_name
                    )
                )
                result = await session.execute(stmt)
                blacklist = result.scalar_one_or_none()
                
                if blacklist and blacklist.is_active():
                    self.logger.info(f"用户 {sender_id} 在黑名单中，拒绝投稿")
                    return None
                    
                # 创建投稿（创建前先清理该 sender/receiver 的历史消息缓存，避免累计过多）
                try:
                    _stmt = delete(MessageCache).where(
                        and_(
                            MessageCache.sender_id == sender_id,
                            MessageCache.receiver_id == receiver_id
                        )
                    )
                    await session.execute(_stmt)
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
                
                # 异步处理投稿
                asyncio.create_task(self.process_submission(submission.id))
                
                return submission.id
                
        except Exception as e:
            self.logger.error(f"创建投稿失败: {e}", exc_info=True)
            return None
            
    async def process_submission(self, submission_id: int):
        """处理投稿"""
        try:
            # 等待用户可能的补充消息
            settings = get_settings()
            wait_time = settings.processing.wait_time
            
            self.logger.info(f"等待 {wait_time} 秒接收补充消息")
            await asyncio.sleep(wait_time)
            
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
                
            # 获取该用户的所有消息缓存
            stmt = select(MessageCache).where(
                and_(
                    MessageCache.sender_id == submission.sender_id,
                    MessageCache.receiver_id == submission.receiver_id
                )
            ).order_by(MessageCache.message_time)
            
            result = await session.execute(stmt)
            caches = result.scalars().all()
            
            if caches:
                # 合并消息
                messages = []
                for cache in caches:
                    if cache.message_content:
                        messages.append(cache.message_content)
                        
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
                    self.logger.error("没有可用的发送器")
                    return False

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
            any_success = False
            last_error: Optional[str] = None
            for name, publisher in self.publishers.items():
                result = await publisher.publish_submission(submission_id)
                if result.get('success'):
                    any_success = True
                else:
                    last_error = result.get('error') or result.get('message')

            if any_success:
                db = await get_db()
                async with db.get_session() as session:
                    stmt = delete(StoredPost).where(StoredPost.submission_id == submission_id)
                    await session.execute(stmt)
                    await session.commit()
                return True
            else:
                self.logger.error(f"发布失败: {last_error}")
                return False
        except Exception as e:
            self.logger.error(f"发布单条投稿失败: {e}", exc_info=True)
            return False
            
    def build_publish_text(self, submission: Submission, include_text: bool = True) -> str:
        """构建发布文本
        
        Args:
            include_text: 是否包含编号/@/评论/分段文本。无论如何都会附加 links。
        """
        text = ""
        
        # 读取配置，决定是否包含聊天分段文本
        settings = get_settings()
        qzone_cfg = settings.publishers.get('qzone')
        if hasattr(qzone_cfg, 'dict'):
            qzone_cfg = qzone_cfg.dict()
        elif hasattr(qzone_cfg, '__dict__'):
            qzone_cfg = qzone_cfg.__dict__
        qzone_cfg = qzone_cfg or {}
        include_segments = qzone_cfg.get('include_segments', True)

        if include_text:
            # 添加编号
            if submission.publish_id:
                text = f"#{submission.publish_id}"
            
            # 添加@
            if not submission.is_anonymous:
                text += f" @{{uin:{submission.sender_id},nick:,who:1}}"
            
            # 添加评论
            if submission.comment:
                text += f" {submission.comment}"
            
            # 添加处理后的文本（聊天分段）
            if include_segments and submission.processed_content:
                segments = submission.processed_content.get('text', [])
                if segments:
                    text += "\n" + "\n".join(segments)
            # 附加链接（如有）——美化展示
            links = submission.processed_content.get('links') or []
            if links:
                links = deduplicate_preserve_order(links)
                if len(links) == 1:
                    links_block = f"链接：{links[0]}"
                else:
                    numbered = [f"{i+1}) {u}" for i, u in enumerate(links)]
                    links_block = "链接：\n" + "\n".join(numbered)
                text += ("\n\n" if text else "") + links_block
                
        # 链接不受 include_text 影响（兜底：若前面未附加过，再附加一次美化后的链接）
        if submission.processed_content:
            links = submission.processed_content.get('links') or []
            if links and ("链接：" not in text):
                links = deduplicate_preserve_order(links)
                if len(links) == 1:
                    links_block = f"链接：{links[0]}"
                else:
                    numbered = [f"{i+1}) {u}" for i, u in enumerate(links)]
                    links_block = "链接：\n" + "\n".join(numbered)
                text = (text + ("\n\n" if text else "")) + links_block
        return text.strip()
        
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
