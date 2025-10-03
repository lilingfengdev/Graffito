"""接收器基类"""
import asyncio
from typing import Dict, Any, Optional, Callable
from abc import abstractmethod
from loguru import logger

from core.plugin import ReceiverPlugin
from core.database import get_db
from core.models import Submission, MessageCache
from core.enums import SubmissionStatus


class BaseReceiver(ReceiverPlugin):
    """接收器基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.message_handler: Optional[Callable] = None
        self.friend_request_handler: Optional[Callable] = None
        self.message_queue = asyncio.Queue()
        self.is_running = False
        
    async def initialize(self):
        """初始化接收器"""
        self.logger.info(f"初始化接收器: {self.name}")
        
    async def shutdown(self):
        """关闭接收器"""
        await self.stop()
        self.logger.info(f"接收器已关闭: {self.name}")
        
    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self.message_handler = handler
        
    def set_friend_request_handler(self, handler: Callable):
        """设置好友请求处理器"""
        self.friend_request_handler = handler
        
    async def process_message(self, message: Dict[str, Any]):
        """处理消息的通用逻辑"""
        try:
            # 过滤不需要处理的消息
            if not self.should_process_message(message):
                return
                
            # 保存到消息缓存
            await self.cache_message(message)
            
            # 检查是否需要创建新投稿
            if await self.should_create_submission(message):
                await self.create_submission(message)
                
        except Exception as e:
            self.logger.error(f"处理消息失败: {e}", exc_info=True)
            
    def should_process_message(self, message: Dict[str, Any]) -> bool:
        """判断是否需要处理消息"""
        # 过滤自动回复
        if message.get('message_type') == 'private':
            raw_message = message.get('raw_message', '')
            if any(keyword in raw_message for keyword in ['自动回复', '请求添加你为好友', '我们已成功添加为好友']):
                return False
        return True
        
    async def cache_message(self, message: Dict[str, Any]):
        """缓存消息（使用 MessageCacheService）"""
        from core.message_cache_service import MessageCacheService
        
        db = await get_db()
        async with db.get_session() as session:
            await MessageCacheService.add_message(
                sender_id=str(message.get('user_id')),
                receiver_id=str(message.get('self_id')),
                message_id=str(message.get('message_id')),
                message_content=message,
                message_time=float(message.get('time', 0)),
                db=session
            )
            
    async def remove_cached_message(self, sender_id: str, receiver_id: str, message_id: str) -> bool:
        """根据 sender/receiver/message_id 删除一条已缓存的消息。
        返回是否删除成功（存在即删）。
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                from sqlalchemy import select, delete, and_  # type: ignore

                norm_sender = str(sender_id)
                norm_receiver = str(receiver_id)
                norm_mid = str(message_id)

                # 先精确匹配查询，确保确实存在
                sel = select(MessageCache.id).where(
                    and_(
                        MessageCache.sender_id == norm_sender,
                        MessageCache.receiver_id == norm_receiver,
                        MessageCache.message_id == norm_mid,
                    )
                )
                r = await session.execute(sel)
                ids = [row[0] for row in r.fetchall()]

                # 找到则按主键删除
                if ids:
                    del_stmt = delete(MessageCache).where(MessageCache.id.in_(ids))
                    await session.execute(del_stmt)
                    await session.commit()
                    return True

                # 兜底：某些实现可能 message_id 不一致或被裁剪，尝试在最新记录里通过 JSON 内容比对
                # 仅在指定的会话对内查找最近的若干条
                sel_recent = (
                    select(MessageCache)
                    .where(
                        and_(
                            MessageCache.sender_id == norm_sender,
                            MessageCache.receiver_id == norm_receiver,
                        )
                    )
                    .order_by(MessageCache.created_at.desc())
                    .limit(20)
                )
                r2 = await session.execute(sel_recent)
                rows = r2.scalars().all()
                hit_ids: list[int] = []
                for row in rows:
                    try:
                        content = row.message_content or {}
                        mc_mid = str(content.get("message_id", ""))
                        if mc_mid and mc_mid == norm_mid:
                            hit_ids.append(row.id)
                            break
                    except Exception:
                        continue
                if hit_ids:
                    del_stmt = delete(MessageCache).where(MessageCache.id.in_(hit_ids))
                    await session.execute(del_stmt)
                    await session.commit()
                    return True

                return False
        except Exception as e:
            self.logger.error(f"删除缓存消息失败: {e}")
            return False

    async def should_create_submission(self, message: Dict[str, Any]) -> bool:
        """判断是否需要创建新投稿"""
        # 检查是否是新的投稿者或距离上次投稿超过等待时间
        sender_id = str(message.get('user_id'))
        receiver_id = str(message.get('self_id'))
        
        db = await get_db()
        async with db.get_session() as session:
            # 查询最近的未完成投稿
            from sqlalchemy import select, and_, or_
            stmt = select(Submission).where(
                and_(
                    Submission.sender_id == sender_id,
                    Submission.receiver_id == receiver_id,
                    or_(
                        Submission.status == SubmissionStatus.PENDING.value,
                        Submission.status == SubmissionStatus.PROCESSING.value
                    )
                )
            ).order_by(Submission.created_at.desc()).limit(1)
            
            result = await session.execute(stmt)
            latest = result.scalar_one_or_none()
            
            if latest is None:
                return True  # 没有未完成的投稿
                
            # 检查时间间隔
            import time
            current_time = time.time()
            last_message_time = float(message.get('time', 0))
            
            # 如果距离上次消息超过等待时间，创建新投稿
            wait_time = self.config.get('wait_time', 120)
            if current_time - last_message_time > wait_time:
                return True
                
        return False
        
    async def create_submission(self, message: Dict[str, Any]):
        """创建新投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取账号组信息
            from config import get_settings
            settings = get_settings()
            
            receiver_id = str(message.get('self_id'))
            group_name = None
            
            # 查找所属账号组
            for gname, group in settings.account_groups.items():
                if group.main_account.qq_id == receiver_id:
                    group_name = gname
                    break
                for minor in group.minor_accounts:
                    if minor.qq_id == receiver_id:
                        group_name = gname
                        break
                        
            submission = Submission(
                sender_id=str(message.get('user_id')),
                sender_nickname=message.get('sender', {}).get('nickname'),
                receiver_id=receiver_id,
                group_name=group_name,
                raw_content=[message],  # 初始消息
                status=SubmissionStatus.PENDING.value
            )
            session.add(submission)
            await session.commit()
            
            self.logger.info(f"创建新投稿: ID={submission.id}, 发送者={submission.sender_id}")
            
            # 触发处理流程
            if self.message_handler:
                await self.message_handler(submission)
                
    @abstractmethod
    async def start(self):
        """启动接收器"""
        pass
        
    @abstractmethod
    async def stop(self):
        """停止接收器"""
        pass
