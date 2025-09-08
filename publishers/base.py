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
                'http_token': getattr(group.main_account, 'http_token', None),
                'group_name': group_name,
                'is_main': True
            }
            
            # 副账号
            for minor in group.minor_accounts:
                self.accounts[minor.qq_id] = {
                    'qq_id': minor.qq_id,
                    'http_port': minor.http_port,
                    'http_token': getattr(minor, 'http_token', None),
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
                
            # 读取平台配置
            cfg = self._get_platform_config()

            # 准备发布内容（可配置：是否发文本、图片来源）
            publish_text = cfg.get('publish_text', True)
            # 即便不发布正文文本，也要附加链接
            content = self.prepare_content(submission, include_text=publish_text, **kwargs)

            # 决定图片来源
            image_source = cfg.get('image_source', 'rendered')
            images: List[str] = []
            if image_source in ('rendered', 'both'):
                images.extend(submission.rendered_images or [])
            if image_source in ('chat', 'both'):
                # 从 processed_content 或 raw_content 中提取聊天图片URL
                chat_images = self._extract_chat_images(submission)
                images.extend(chat_images)
            # 去重并保序
            if images:
                seen = set()
                images = [x for x in images if not (x in seen or seen.add(x))]
            
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
            # 读取平台配置
            cfg = self._get_platform_config()
            publish_text = cfg.get('publish_text', True)
            image_source = cfg.get('image_source', 'rendered')
            for submission in submissions:
                content = self.prepare_content(submission, include_text=publish_text, **kwargs)
                images: List[str] = []
                if image_source in ('rendered', 'both'):
                    images.extend(submission.rendered_images or [])
                if image_source in ('chat', 'both'):
                    images.extend(self._extract_chat_images(submission))
                if images:
                    seen = set()
                    images = [x for x in images if not (x in seen or seen.add(x))]
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
            
    def prepare_content(self, submission: Submission, include_text: bool = True, **kwargs) -> str:
        """准备发布内容
        
        Args:
            submission: 投稿对象
            include_text: 是否包含正文（编号/@/评论/分段文本）。即便为 False，仍会附加链接。
        """
        content = ""
        
        # 配置控制是否包含编号
        cfg = self._get_platform_config()

        include_publish_id = cfg.get('include_publish_id', True)
        include_at_sender = cfg.get('include_at_sender', True)
        include_segments = cfg.get('include_segments', True)

        if include_text:
            if include_publish_id and submission.publish_id:
                content = f"#{submission.publish_id}"
            
            # 添加@
            if not submission.is_anonymous and include_at_sender and kwargs.get('at_sender', True):
                at_text = self.format_at(submission)
                if at_text:
                    content += f" {at_text}"
            
            # 添加评论
            if submission.comment:
                content += f" {submission.comment}"
            
            # 添加处理后的文本内容（聊天分段），受 include_segments 控制
            if include_segments and submission.processed_content:
                text_val = submission.processed_content.get('text', '')
                if isinstance(text_val, list):
                    text_joined = "\n".join([str(x) for x in text_val if x])
                else:
                    text_joined = str(text_val or '')
                if text_joined:
                    content += f"\n{text_joined}"
        
        # 附加链接列表（不受 include_text 影响），并进行美化展示
        if submission.processed_content:
            links = submission.processed_content.get('links') or []
            if links:
                # 去重并保序
                seen = set()
                links = [x for x in links if not (x in seen or seen.add(x))]
                # 美化成列表：单条直接行内，多条加编号
                if len(links) == 1:
                    links_block = f"链接：{links[0]}"
                else:
                    numbered = [f"{i+1}) {u}" for i, u in enumerate(links)]
                    links_block = "链接：\n" + "\n".join(numbered)
                content = (content + ("\n\n" if content else "")) + links_block
                
        return content.strip()

    def format_at(self, submission: Submission) -> str:
        """格式化平台特定的@文本。默认使用QQ空间样式。
        子类可覆盖以适配平台（如B站仅返回@昵称的纯文本）。
        """
        try:
            return f"@{{uin:{submission.sender_id},nick:,who:1}}"
        except Exception:
            return ""

    def _get_platform_config(self) -> Dict[str, Any]:
        """获取当前平台的配置为字典"""
        try:
            from config import get_settings
            settings = get_settings()
            cfg = settings.publishers.get(self.platform.value)
            if hasattr(cfg, 'model_dump'):
                return cfg.model_dump()
            if hasattr(cfg, 'dict'):
                return cfg.dict()
            if hasattr(cfg, '__dict__'):
                return cfg.__dict__
            return cfg or {}
        except Exception:
            return {}

    def _extract_chat_images(self, submission: Submission) -> List[str]:
        """从投稿的原始消息中提取聊天图片URL"""
        images: List[str] = []

        def collect_from_messages(msgs: Any):  # type: ignore[name-defined]
            if not msgs:
                return
            for msg in msgs:
                try:
                    if not isinstance(msg, dict):
                        continue
                    # 直接图片
                    if msg.get('type') == 'image':
                        data = msg.get('data') or {}
                        url = data.get('url')
                        # 过滤QQ表情图片：sub_type/subType == 1
                        sub_type = data.get('sub_type') if 'sub_type' in data else data.get('subType')
                        try:
                            is_face_image = str(sub_type) == '1'
                        except Exception:
                            is_face_image = False
                        if url and not is_face_image:
                            images.append(url)
                    # 嵌套消息数组
                    if msg.get('message') and isinstance(msg.get('message'), list):
                        collect_from_messages(msg.get('message'))
                    # 合并转发结构 data.messages 或 data.content
                    data = msg.get('data') or {}
                    if isinstance(data, dict):
                        nested_messages = data.get('messages') or data.get('content')
                        if isinstance(nested_messages, list):
                            # 每个元素可能为 {message: [...]} 结构
                            for item in nested_messages:
                                if isinstance(item, dict) and 'message' in item:
                                    collect_from_messages(item.get('message'))
                                else:
                                    # 也可能直接是消息数组
                                    collect_from_messages(nested_messages)
                except Exception:
                    continue

        try:
            collect_from_messages(submission.raw_content or [])
        except Exception:
            pass
        return images
        
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
