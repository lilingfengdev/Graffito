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
        from config import get_settings
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
                from sqlalchemy import select, and_
                from core.models import BlackList
                
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
                    from sqlalchemy import delete, and_ as _and
                    _stmt = delete(MessageCache).where(
                        _and_(
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
            from config import get_settings
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
            from sqlalchemy import select, and_
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
            from .notification_service import NotificationService
            notifier = NotificationService()
            ok = await notifier.send_audit_request(submission_id)
            if not ok:
                self.logger.error(f"发送审核通知失败: submission_id={submission_id}")
        except Exception as e:
            self.logger.error(f"发送审核通知异常: {e}", exc_info=True)
            
    async def get_group_name(self, receiver_id: str) -> Optional[str]:
        """根据接收者ID获取账号组名称"""
        from config import get_settings
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
            from sqlalchemy import select, and_
            
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
            from sqlalchemy import select
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
                
                from sqlalchemy import select
                stmt = select(Submission).where(Submission.id.in_(submission_ids))
                result = await session.execute(stmt)
                submissions = result.scalars().all()
                
                # 构建发布内容
                publish_items = []
                for submission in submissions:
                    # 生成发布文本（即便平台禁用正文，也携带链接）
                    text = self.build_publish_text(submission, include_text=True)
                    images = submission.rendered_images or []
                    
                    publish_items.append({
                        'submission_id': submission.id,
                        'content': text,
                        'images': images
                    })
                    
                # 使用发送器发布
                if 'qzone' in self.publishers:
                    publisher = self.publishers['qzone']
                    
                    # 批量发布
                    results = await publisher.batch_publish(publish_items)
                    
                    # 记录发布结果
                    for i, result in enumerate(results):
                        if result.get('success'):
                            # 更新投稿状态
                            submission = submissions[i]
                            submission.status = SubmissionStatus.PUBLISHED.value
                            submission.published_at = datetime.now()
                            
                    # 清空暂存区
                    from sqlalchemy import delete
                    stmt = delete(StoredPost).where(StoredPost.group_name == group_name)
                    await session.execute(stmt)
                    
                    await session.commit()
                    
                    self.logger.info(f"发布 {len(publish_items)} 个投稿完成")
                    return True
                else:
                    self.logger.error("没有可用的发送器")
                    return False
                    
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
            # 需要可用的发送器
            if 'qzone' not in self.publishers:
                self.logger.error("没有可用的发送器")
                return False
            publisher = self.publishers['qzone']

            # 直接复用发送器的单发逻辑（含记录与状态更新）
            result = await publisher.publish_submission(submission_id)

            # 成功则移除对应暂存记录
            if result.get('success'):
                db = await get_db()
                async with db.get_session() as session:
                    from sqlalchemy import delete
                    from core.models import StoredPost
                    stmt = delete(StoredPost).where(StoredPost.submission_id == submission_id)
                    await session.execute(stmt)
                    await session.commit()
                return True
            else:
                self.logger.error(f"发布失败: {result}")
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
        from config import get_settings
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
                seen = set()
                links = [x for x in links if not (x in seen or seen.add(x))]
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
                seen = set()
                links = [x for x in links if not (x in seen or seen.add(x))]
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
                from sqlalchemy import select, func
                stmt = select(func.min(StoredPost.publish_id)).where(
                    StoredPost.group_name == group_name
                )
                result = await session.execute(stmt)
                min_num = result.scalar()
                
                if min_num:
                    # 删除暂存投稿
                    from sqlalchemy import delete
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
