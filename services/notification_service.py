"""通知服务"""
import asyncio
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from config import get_settings
from core.plugin import plugin_manager


class NotificationService:
    """通知服务，负责发送各种通知消息"""
    
    def __init__(self):
        self.logger = logger.bind(module="notification")
        self.settings = get_settings()
        
    async def send_to_admin_group(self, group_name: str, message: str, 
                                 images: Optional[List[str]] = None) -> bool:
        """发送消息到管理群
        
        Args:
            group_name: 账号组名称
            message: 消息内容
            images: 图片列表
            
        Returns:
            是否发送成功
        """
        try:
            # 获取管理群ID
            group_config = self.settings.account_groups.get(group_name)
            if not group_config:
                self.logger.error(f"找不到账号组配置: {group_name}")
                return False
                
            manage_group_id = group_config.manage_group_id
            if not manage_group_id:
                self.logger.error(f"账号组 {group_name} 没有配置管理群")
                return False
                
            # 获取QQ接收器
            qq_receiver = plugin_manager.get_receiver('qq_receiver')
            if not qq_receiver:
                self.logger.error("QQ接收器未初始化")
                return False
                
            # 先发文本
            success = await qq_receiver.send_group_message(manage_group_id, message)
            if not success:
                self.logger.error(f"发送管理群文本失败: {manage_group_id}")
                # 继续尝试发送图片
            else:
                self.logger.info(f"发送管理群文本成功: {manage_group_id}")

            # 再逐张发图片，遇到错误重试一次
            if images:
                from pathlib import Path
                for img in images:
                    # 规范化为可用的 file/url
                    try:
                        if isinstance(img, str) and (img.startswith('http://') or img.startswith('https://')):
                            cq = f"[CQ:image,file={img}]"
                        else:
                            p = Path(str(img))
                            if not str(img).startswith('file://'):
                                if not p.is_absolute():
                                    p = (Path.cwd() / p).resolve()
                                img_uri = p.as_uri()
                            else:
                                img_uri = str(img)
                            cq = f"[CQ:image,file={img_uri}]"
                    except Exception:
                        cq = f"[CQ:image,file={img}]"

                    sent_ok = False
                    for attempt in range(2):
                        try:
                            img_ok = await qq_receiver.send_group_message(manage_group_id, cq)
                            if img_ok:
                                sent_ok = True
                                break
                            await asyncio.sleep(0.8)
                        except Exception:
                            await asyncio.sleep(1.0)
                    if not sent_ok:
                        self.logger.error(f"发送管理群图片失败: {manage_group_id}, img={img}")
                        # 不中断其余图片

            return success or True
            
        except Exception as e:
            self.logger.error(f"发送管理群消息异常: {e}", exc_info=True)
            return False
            
    async def send_to_user(self, user_id: str, message: str, 
                          group_name: Optional[str] = None) -> bool:
        """发送私聊消息给用户
        
        Args:
            user_id: 用户QQ号
            message: 消息内容
            group_name: 账号组名称（用于确定使用哪个账号发送）
            
        Returns:
            是否发送成功
        """
        try:
            # 获取QQ接收器
            qq_receiver = plugin_manager.get_receiver('qq_receiver')
            if not qq_receiver:
                self.logger.error("QQ接收器未初始化")
                return False
                
            # 发送私聊消息
            success = await qq_receiver.send_private_message(user_id, message)
            
            if success:
                self.logger.info(f"发送私聊消息成功: {user_id}")
            else:
                self.logger.error(f"发送私聊消息失败: {user_id}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"发送私聊消息异常: {e}", exc_info=True)
            return False
            
    async def send_submission_approved(self, submission_id: int) -> bool:
        """发送投稿通过通知"""
        from core.database import get_db
        from core.models import Submission
        
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return False
            
            # 构建通知消息
            message = f"✅ 你的投稿已通过审核！\n"
            
            # 使用 publish_id 或 id 作为编号
            display_id = submission.publish_id if submission.publish_id else submission.id
            message += f"📝 投稿编号: #{display_id}\n"
            
            # 获取下次发布时间
            try:
                from utils.common import get_platform_config
                next_schedule_time = None
                
                # 查找最早的定时发布时间
                if submission.group_name:
                    group_config = self.settings.account_groups.get(submission.group_name)
                    if group_config:
                        # 遍历所有平台，找到最早的发布时间
                        for platform_name in ['qzone', 'bilibili', 'rednote']:
                            platform_cfg = get_platform_config(platform_name)
                            if platform_cfg and platform_cfg.get('enabled'):
                                schedules = platform_cfg.get('send_schedule', [])
                                if schedules:
                                    from datetime import datetime
                                    now = datetime.now()
                                    for time_str in schedules:
                                        try:
                                            hour, minute = map(int, time_str.split(':'))
                                            schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                                            # 如果时间已过，则为明天
                                            if schedule_time <= now:
                                                from datetime import timedelta
                                                schedule_time += timedelta(days=1)
                                            # 记录最早的时间
                                            if next_schedule_time is None or schedule_time < next_schedule_time:
                                                next_schedule_time = schedule_time
                                        except Exception:
                                            continue
                
                if next_schedule_time:
                    time_str = next_schedule_time.strftime('%H:%M')
                    message += f"⏰ 预计在 {time_str} 发布到各平台"
                else:
                    message += "⏰ 将尽快发布到各平台"
                    
            except Exception as e:
                self.logger.error(f"获取发布时间失败: {e}")
                message += "⏰ 将尽快发布到各平台"
                
            return await self.send_to_user(
                submission.sender_id, 
                message,
                submission.group_name
            )
            
    async def send_submission_rejected(self, submission_id: int, reason: Optional[str] = None) -> bool:
        """发送投稿拒绝通知"""
        from core.database import get_db
        from core.models import Submission
        
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return False
            
            # 构建拒绝通知消息
            # 使用 publish_id 或 id 作为编号
            display_id = submission.publish_id if submission.publish_id else submission.id
            
            message = f"❌ 很抱歉，你的投稿未通过审核\n"
            message += f"📝 投稿编号: #{display_id}"
            
            if reason:
                message += f"\n💬 原因: {reason}"
                
            return await self.send_to_user(
                submission.sender_id,
                message,
                submission.group_name
            )
            
    async def send_audit_request(self, submission_id: int) -> bool:
        """发送审核请求到管理群"""
        from core.database import get_db
        from core.models import Submission
        
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return False
                
            # 构建审核消息
            message = f"📝 新投稿待审核\n"
            message += f"内部编号：{submission.id}\n"
            
            if submission.is_complete:
                message += "✅ AI判断已写完\n"
            else:
                message += "⚠️ AI判断未写完\n"
                
            if submission.is_safe:
                message += "✅ AI审核判定安全\n"
            else:
                message += "❌ AI审核判定不安全\n"
                
            if submission.is_anonymous:
                message += "🔒 需要匿名\n"
            else:
                message += f"👤 投稿者：{submission.sender_id}\n"
                
            message += "\n请发送审核指令："
            message += "\n@机器人 {} 是 - 通过"
            message += "\n@机器人 {} 否 - 跳过"
            message += "\n@机器人 {} 拒 - 拒绝"
            message += "\n@机器人 {} 匿 - 切换匿名"
            message += "\n更多指令请发送：@机器人 帮助"
            
            message = message.format(*([submission.id] * 4))
            
            # 发送到管理群
            return await self.send_to_admin_group(
                submission.group_name,
                message,
                submission.rendered_images
            )
            
    async def send_quick_reply(self, submission_id: int, reply_key: str) -> bool:
        """发送快捷回复"""
        from core.database import get_db
        from core.models import Submission
        
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return False
                
            # 获取快捷回复内容
            group_config = self.settings.account_groups.get(submission.group_name)
            if not group_config:
                return False
                
            reply_content = group_config.quick_replies.get(reply_key)
            if not reply_content:
                self.logger.error(f"找不到快捷回复: {reply_key}")
                return False
                
            # 发送给投稿者
            return await self.send_to_user(
                submission.sender_id,
                reply_content,
                submission.group_name
            )
            
    async def broadcast_to_admins(self, message: str) -> int:
        """广播消息到所有管理群
        
        Args:
            message: 消息内容
            
        Returns:
            成功发送的群数量
        """
        success_count = 0
        
        for group_name in self.settings.account_groups:
            if await self.send_to_admin_group(group_name, message):
                success_count += 1
                
        self.logger.info(f"广播消息到 {success_count} 个管理群")
        return success_count

    async def broadcast_to_users(self, message: str, group_name: Optional[str] = None) -> Dict[str, int]:
        """向所有用户（去重）私聊推送公告。

        当提供 group_name 时，仅推送给该账号组下与机器人有过交互的用户；
        否则推送给全局所有用户。

        Returns:
            {"total": 总人数, "success": 成功数, "failed": 失败数}
        """
        from core.database import get_db
        from core.models import Submission, MessageCache
        from sqlalchemy import select, distinct

        # 汇总目标用户ID（字符串）
        user_ids: Set[str] = set()

        try:
            db = await get_db()
            async with db.get_session() as session:
                # 约束 receiver_id 列表（当限定组时）
                receiver_ids: Optional[Set[str]] = None
                if group_name:
                    grp = self.settings.account_groups.get(group_name)
                    if grp:
                        receiver_ids = {str(grp.main_account.qq_id)} | {str(acc.qq_id) for acc in (grp.minor_accounts or [])}

                # 从 Submission 取 distinct(sender_id)
                if group_name:
                    sub_stmt = select(distinct(Submission.sender_id)).where(Submission.group_name == group_name)
                else:
                    sub_stmt = select(distinct(Submission.sender_id))
                sub_rows = await session.execute(sub_stmt)
                for (sid,) in sub_rows.all():
                    if sid:
                        user_ids.add(str(sid))

                # 从 MessageCache 取 distinct(sender_id)
                if receiver_ids:
                    mc_stmt = select(distinct(MessageCache.sender_id)).where(MessageCache.receiver_id.in_(list(receiver_ids)))
                else:
                    mc_stmt = select(distinct(MessageCache.sender_id))
                mc_rows = await session.execute(mc_stmt)
                for (sid,) in mc_rows.all():
                    if sid:
                        user_ids.add(str(sid))
        except Exception as e:
            self.logger.error(f"收集公告推送用户失败: {e}")
            return {"total": 0, "success": 0, "failed": 0}

        if not user_ids:
            self.logger.info("没有可推送的目标用户")
            return {"total": 0, "success": 0, "failed": 0}

        # 控制并发，避免对 OneBot/Napcat 造成压力
        semaphore = asyncio.Semaphore(10)
        success_count = 0

        async def _send(uid: str) -> bool:
            async with semaphore:
                try:
                    ok = await self.send_to_user(uid, message, group_name)
                    return bool(ok)
                except Exception:
                    return False

        tasks = [asyncio.create_task(_send(uid)) for uid in user_ids]
        for t in asyncio.as_completed(tasks):
            if await t:
                success_count += 1

        total = len(user_ids)
        failed = total - success_count
        self.logger.info(f"公告推送完成：总计 {total}，成功 {success_count}，失败 {failed}")
        return {"total": total, "success": success_count, "failed": failed}

    async def broadcast_to_friends(self, message: str, group_name: Optional[str] = None) -> Dict[str, int]:
        """向所有好友私聊推送公告（基于 OneBot 好友列表）。

        当提供 group_name 时，仅使用该账号组的主/副账号的好友列表；
        否则汇总所有已连接账号的好友列表去重发送。

        Returns:
            {"total": 总人数, "success": 成功数, "failed": 失败数}
        """
        qq_receiver = plugin_manager.get_receiver('qq_receiver')
        if not qq_receiver:
            self.logger.error("QQ接收器未初始化")
            return {"total": 0, "success": 0, "failed": 0}

        # 计算需要查询好友的 self_id 列表
        self_ids: Optional[List[str]] = None
        if group_name:
            grp = self.settings.account_groups.get(group_name)
            if grp:
                self_ids = [str(grp.main_account.qq_id)] + [str(acc.qq_id) for acc in (grp.minor_accounts or [])]

        # 拉取好友列表
        friend_entries: List[Dict[str, str]] = []
        try:
            if self_ids is None:
                friend_entries = await qq_receiver.list_friends(None)
            else:
                collected: List[Dict[str, str]] = []
                for sid in self_ids:
                    items = await qq_receiver.list_friends(sid)
                    collected.extend(items)
                friend_entries = collected
        except Exception as e:
            self.logger.error(f"获取好友列表失败: {e}")
            return {"total": 0, "success": 0, "failed": 0}

        # 去重 user_id
        user_ids: Set[str] = set()
        for it in friend_entries:
            uid = (it or {}).get("user_id")
            if uid:
                user_ids.add(str(uid))

        if not user_ids:
            self.logger.info("好友列表为空，无需推送")
            return {"total": 0, "success": 0, "failed": 0}

        # 并发发送
        semaphore = asyncio.Semaphore(10)
        success_count = 0

        async def _send(uid: str) -> bool:
            async with semaphore:
                try:
                    # 优先选择 group_name 指定账号发送；否则使用默认 send_to_user
                    if group_name:
                        # 使用 group_name 限定：由 qq_receiver 自动选择合适 bot
                        ok = await self.send_to_user(uid, message, group_name)
                    else:
                        ok = await self.send_to_user(uid, message)
                    return bool(ok)
                except Exception:
                    return False

        tasks = [asyncio.create_task(_send(uid)) for uid in user_ids]
        for t in asyncio.as_completed(tasks):
            if await t:
                success_count += 1

        total = len(user_ids)
        failed = total - success_count
        self.logger.info(f"好友公告推送完成：总计 {total}，成功 {success_count}，失败 {failed}")
        return {"total": total, "success": success_count, "failed": failed}
    
    async def notify_report_processed(
        self,
        reporter_id: str,
        receiver_id: str,
        publish_id: int,
        action: str,
        reason: str,
        sender_id: Optional[str] = None
    ) -> bool:
        """发送举报处理通知
        
        Args:
            reporter_id: 举报者 QQ 号
            receiver_id: 接收账号（用于指定发送 Bot）
            publish_id: 投稿发布编号
            action: 处理动作 (delete | keep)
            reason: 处理理由
            sender_id: 投稿者 QQ 号（仅删除时需要）
            
        Returns:
            是否发送成功
        """
        try:
            # 获取 QQ 接收器
            qq_receiver = plugin_manager.get_receiver('qq_receiver')
            if not qq_receiver:
                self.logger.error("QQ接收器未初始化")
                return False
            
            # 发送通知给举报者
            if action == 'delete':
                reporter_msg = (
                    f"【系统回复】\n\n"
                    f"您的举报已经处理,投稿 {publish_id} 已经被删除，"
                    f"如果你不满意此次处理, 可以使用 #反馈 指令"
                )
            else:  # keep
                reporter_msg = (
                    f"【系统回复】\n\n"
                    f"您的举报已经处理,投稿 {publish_id} 被判断为安全，"
                    f"如果您不满意此次处理, 可以使用 #反馈 指令"
                )
            
            try:
                await qq_receiver.send_private_message_by_self(
                    receiver_id,
                    reporter_id,
                    reporter_msg
                )
                self.logger.info(f"已通知举报者 {reporter_id}: {action}")
            except Exception as e:
                self.logger.error(f"通知举报者失败: {e}", exc_info=True)
            
            # 如果是删除动作，同时通知投稿者
            if action == 'delete' and sender_id:
                sender_msg = (
                    f"【系统消息】\n\n"
                    f"您的投稿 {publish_id} 由于举报已经被删除，"
                    f"如果你不满意此次处理, 可以使用 #反馈 指令\n\n"
                    f"原因: {reason}"
                )
                
                try:
                    await qq_receiver.send_private_message_by_self(
                        receiver_id,
                        sender_id,
                        sender_msg
                    )
                    self.logger.info(f"已通知投稿者 {sender_id}: 投稿被删除")
                except Exception as e:
                    self.logger.error(f"通知投稿者失败: {e}", exc_info=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送举报处理通知异常: {e}", exc_info=True)
            return False