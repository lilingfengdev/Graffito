"""通知服务"""
import asyncio
from typing import Dict, Any, List, Optional
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
                
            message = f"您的投稿已通过审核！"
            if submission.publish_id:
                message += f"\n编号：#{submission.publish_id}"
                
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
                
            message = "您的投稿未通过审核。"
            if reason:
                message += f"\n原因：{reason}"
                
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
