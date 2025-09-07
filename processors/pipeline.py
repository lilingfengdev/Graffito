"""处理管道"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from core.database import get_db
from core.models import Submission, MessageCache
from core.enums import SubmissionStatus
from .llm_processor import LLMProcessor
from .html_renderer import HTMLRenderer
from .content_renderer import ContentRenderer


class ProcessingPipeline:
    """消息处理管道"""
    
    def __init__(self):
        self.llm_processor = LLMProcessor()
        self.html_renderer = HTMLRenderer()
        self.content_renderer = ContentRenderer()
        self.logger = logger.bind(module="pipeline")
        
    async def initialize(self):
        """初始化管道"""
        await self.llm_processor.initialize()
        await self.html_renderer.initialize()
        await self.content_renderer.initialize()
        self.logger.info("处理管道初始化完成")
        
    async def shutdown(self):
        """关闭管道"""
        await self.llm_processor.shutdown()
        await self.html_renderer.shutdown()
        await self.content_renderer.shutdown()
        
    async def process_submission(self, submission_id: int) -> bool:
        """处理投稿
        
        Args:
            submission_id: 投稿ID
            
        Returns:
            处理是否成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 获取投稿
                from sqlalchemy import select
                stmt = select(Submission).where(Submission.id == submission_id)
                result = await session.execute(stmt)
                submission = result.scalar_one_or_none()
                
                if not submission:
                    self.logger.error(f"投稿不存在: {submission_id}")
                    return False
                    
                # 更新状态为处理中
                submission.status = SubmissionStatus.PROCESSING.value
                await session.commit()
                
                # 获取消息缓存
                messages = await self.get_messages_for_submission(submission)
                
                # 准备处理数据
                data = {
                    'submission_id': submission_id,
                    'sender_id': submission.sender_id,
                    'nickname': submission.sender_nickname,
                    'messages': messages,
                    'is_anonymous': submission.is_anonymous,
                    'watermark_text': await self.get_watermark_text(submission.group_name)
                }
                
                # 执行处理管道
                # 1. LLM处理
                data = await self.llm_processor.process(data)
                
                # 保存LLM结果
                llm_result = data.get('llm_result', {})
                submission.llm_result = llm_result
                submission.is_anonymous = llm_result.get('needpriv') == 'true'
                submission.is_safe = llm_result.get('safemsg') == 'true'
                submission.is_complete = llm_result.get('isover') == 'true'
                
                # 2. HTML渲染（会收集链接到 data['extracted_links']）
                data = await self.html_renderer.process(data)
                
                # 3. 图片渲染
                data = await self.content_renderer.process(data)
                
                # 保存渲染结果
                submission.rendered_images = data.get('rendered_images', [])
                submission.processed_content = {
                    'text': llm_result.get('segments', []),
                    'html': data.get('rendered_html', ''),
                    'links': data.get('extracted_links', [])
                }
                submission.processed_at = datetime.now()
                submission.status = SubmissionStatus.WAITING.value
                
                await session.commit()
                
                # 清理该投稿对应的历史消息缓存，避免后续投稿重复合并旧消息
                try:
                    from sqlalchemy import delete, and_
                    stmt = delete(MessageCache).where(
                        and_(
                            MessageCache.sender_id == submission.sender_id,
                            MessageCache.receiver_id == submission.receiver_id
                        )
                    )
                    await session.execute(stmt)
                    await session.commit()
                    self.logger.info(f"已清理消息缓存: sender={submission.sender_id}, receiver={submission.receiver_id}")
                except Exception as e:
                    self.logger.error(f"清理消息缓存失败: {e}")
                
                self.logger.info(f"投稿处理完成: {submission_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"处理投稿失败 {submission_id}: {e}", exc_info=True)
            
            # 更新状态为失败
            try:
                async with db.get_session() as session:
                    stmt = select(Submission).where(Submission.id == submission_id)
                    result = await session.execute(stmt)
                    submission = result.scalar_one_or_none()
                    if submission:
                        submission.status = SubmissionStatus.PENDING.value
                        await session.commit()
            except:
                pass
                
            return False
            
    async def get_messages_for_submission(self, submission: Submission) -> List[Dict[str, Any]]:
        """获取投稿的所有消息"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取消息缓存
            from sqlalchemy import select, and_
            stmt = select(MessageCache).where(
                and_(
                    MessageCache.sender_id == submission.sender_id,
                    MessageCache.receiver_id == submission.receiver_id
                )
            ).order_by(MessageCache.message_time)
            
            result = await session.execute(stmt)
            caches = result.scalars().all()
            
            messages = []
            for cache in caches:
                if cache.message_content:
                    messages.append(cache.message_content)
                    
            # 如果没有缓存，使用原始内容
            if not messages and submission.raw_content:
                messages = submission.raw_content
                
            return messages
            
    async def get_watermark_text(self, group_name: Optional[str]) -> str:
        """获取水印文本"""
        if not group_name:
            return ""
            
        from config import get_settings
        settings = get_settings()
        
        group = settings.account_groups.get(group_name)
        if group:
            return group.watermark_text
            
        return ""
        
    async def reprocess_submission(self, submission_id: int, skip_llm: bool = False) -> bool:
        """重新处理投稿
        
        Args:
            submission_id: 投稿ID
            skip_llm: 是否跳过LLM处理
            
        Returns:
            处理是否成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 获取投稿
                from sqlalchemy import select
                stmt = select(Submission).where(Submission.id == submission_id)
                result = await session.execute(stmt)
                submission = result.scalar_one_or_none()
                
                if not submission:
                    self.logger.error(f"投稿不存在: {submission_id}")
                    return False
                    
                # 获取消息
                messages = await self.get_messages_for_submission(submission)
                
                # 准备数据
                data = {
                    'submission_id': submission_id,
                    'sender_id': submission.sender_id,
                    'nickname': submission.sender_nickname,
                    'messages': messages,
                    'is_anonymous': submission.is_anonymous,
                    'watermark_text': await self.get_watermark_text(submission.group_name)
                }
                
                # 如果不跳过LLM，执行LLM处理
                if not skip_llm:
                    data = await self.llm_processor.process(data)
                    llm_result = data.get('llm_result', {})
                    submission.llm_result = llm_result
                    submission.is_anonymous = llm_result.get('needpriv') == 'true'
                    submission.is_safe = llm_result.get('safemsg') == 'true'
                    submission.is_complete = llm_result.get('isover') == 'true'
                else:
                    # 使用现有的LLM结果
                    data['llm_result'] = submission.llm_result or {}
                    
                # HTML渲染
                data = await self.html_renderer.process(data)
                
                # 图片渲染
                data = await self.content_renderer.process(data)
                
                # 保存结果（恢复 extracted_links）
                submission.rendered_images = data.get('rendered_images', [])
                submission.processed_content = {
                    'text': data.get('llm_result', {}).get('segments', []),
                    'html': data.get('rendered_html', ''),
                    'links': data.get('extracted_links', [])
                }
                submission.processed_at = datetime.now()
                
                await session.commit()
                
                self.logger.info(f"重新处理投稿完成: {submission_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"重新处理投稿失败 {submission_id}: {e}", exc_info=True)
            return False
