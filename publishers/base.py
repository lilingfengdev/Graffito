"""发送器基类"""
from typing import Dict, Any, List, Optional
from abc import abstractmethod
from datetime import datetime
from loguru import logger

from core.plugin import PublisherPlugin
from core.database import get_db
from core.models import PublishRecord, StoredPost, Submission
from core.enums import PublishPlatform


class BasePublisher(PublisherPlugin):
    """发送器基类"""
    
    def __init__(self, name: str, platform: PublishPlatform, config: Dict[str, Any]):
        super().__init__(name, config)
        self.platform = platform
        self.accounts: Dict[str, Dict[str, Any]] = {}  # 账号信息
        
    async def initialize(self):
        """初始化发送器"""
        self.logger.info(f"初始化发送器: {self.name}")
        await self.load_accounts()
        
    async def shutdown(self):
        """关闭发送器"""
        self.logger.info(f"发送器已关闭: {self.name}")
        
    async def load_accounts(self):
        """加载账号配置"""
        from config import get_settings
        settings = get_settings()
        
        for group_name, group in settings.account_groups.items():
            # 主账号
            self.accounts[group.main_account.qq_id] = {
                'qq_id': group.main_account.qq_id,
                'http_port': group.main_account.http_port,
                'group_name': group_name,
                'is_main': True
            }
            
            # 副账号
            for minor in group.minor_accounts:
                self.accounts[minor.qq_id] = {
                    'qq_id': minor.qq_id,
                    'http_port': minor.http_port,
                    'group_name': group_name,
                    'is_main': False
                }
                
    async def publish_submission(self, submission_id: int, **kwargs) -> Dict[str, Any]:
        """发布单个投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取投稿信息
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'error': '投稿不存在'}
                
            # 准备发布内容
            content = self.prepare_content(submission, **kwargs)
            images = submission.rendered_images or []
            
            # 发布
            result = await self.publish(content, images, **kwargs)
            
            # 记录发布结果
            await self.record_publish(
                submission_ids=[submission_id],
                content=content,
                images=images,
                result=result,
                account_id=kwargs.get('account_id')
            )
            
            return result
            
    async def batch_publish_submissions(self, submission_ids: List[int], **kwargs) -> List[Dict[str, Any]]:
        """批量发布投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取所有投稿
            from sqlalchemy import select
            stmt = select(Submission).where(Submission.id.in_(submission_ids))
            result = await session.execute(stmt)
            submissions = result.scalars().all()
            
            if not submissions:
                return [{'success': False, 'error': '没有找到投稿'}]
                
            # 准备批量发布内容
            items = []
            for submission in submissions:
                content = self.prepare_content(submission, **kwargs)
                images = submission.rendered_images or []
                items.append({
                    'content': content,
                    'images': images,
                    'submission_id': submission.id
                })
                
            # 批量发布
            results = await self.batch_publish(items)
            
            # 记录发布结果
            for i, result in enumerate(results):
                if i < len(items):
                    await self.record_publish(
                        submission_ids=[items[i]['submission_id']],
                        content=items[i]['content'],
                        images=items[i]['images'],
                        result=result,
                        account_id=kwargs.get('account_id')
                    )
                    
            return results
            
    def prepare_content(self, submission: Submission, **kwargs) -> str:
        """准备发布内容"""
        # 基础内容
        content = ""
        
        # 添加编号
        if submission.publish_id:
            content = f"#{submission.publish_id}"
            
        # 添加@
        if not submission.is_anonymous and kwargs.get('at_sender', True):
            content += f" @{{uin:{submission.sender_id},nick:,who:1}}"
            
        # 添加评论
        if submission.comment:
            content += f" {submission.comment}"
            
        # 添加处理后的文本内容
        if submission.processed_content:
            text = submission.processed_content.get('text', '')
            if text:
                content += f"\n{text}"
                
        return content.strip()
        
    async def record_publish(self, submission_ids: List[int], content: str, 
                            images: List[str], result: Dict[str, Any],
                            account_id: Optional[str] = None):
        """记录发布结果"""
        db = await get_db()
        async with db.get_session() as session:
            record = PublishRecord(
                submission_ids=submission_ids,
                platform=self.platform.value,
                account_id=account_id or '',
                publish_content=content,
                publish_images=images,
                publish_result=result,
                is_success=result.get('success', False),
                error_message=result.get('error')
            )
            session.add(record)
            
            # 更新投稿状态
            if result.get('success'):
                from sqlalchemy import update
                from core.enums import SubmissionStatus
                stmt = update(Submission).where(
                    Submission.id.in_(submission_ids)
                ).values(
                    status=SubmissionStatus.PUBLISHED.value,
                    published_at=datetime.now()
                )
                await session.execute(stmt)
                
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
            
    async def clear_stored_posts(self, group_name: str):
        """清空暂存的投稿"""
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import delete
            stmt = delete(StoredPost).where(StoredPost.group_name == group_name)
            await session.execute(stmt)
            
    @abstractmethod
    async def publish(self, content: str, images: List[str] = None, **kwargs) -> Dict[str, Any]:
        """发布内容（子类实现）"""
        pass
        
    @abstractmethod
    async def batch_publish(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量发布（子类实现）"""
        pass
        
    @abstractmethod
    async def check_login_status(self) -> bool:
        """检查登录状态（子类实现）"""
        pass
        
    @abstractmethod
    async def refresh_login(self) -> bool:
        """刷新登录（子类实现）"""
        pass
