"""投稿操作统一服务
集中处理投稿的通用操作，减少重复代码
"""
from typing import Dict, Any, Optional, Callable
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Submission
from core.enums import SubmissionStatus


class SubmissionOperations:
    """投稿操作统一服务"""
    
    @staticmethod
    async def get_submission(
        submission_id: int,
        session: Optional[AsyncSession] = None
    ) -> Optional[Submission]:
        """获取投稿（带自动会话管理）
        
        Args:
            submission_id: 投稿ID
            session: 可选的已存在会话，如果为None则自动创建
            
        Returns:
            投稿对象或None
        """
        try:
            if session:
                result = await session.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
                return result.scalar_one_or_none()
            else:
                db = await get_db()
                async with db.get_session() as sess:
                    result = await sess.execute(
                        select(Submission).where(Submission.id == submission_id)
                    )
                    return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取投稿失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def update_submission_status(
        submission_id: int,
        status: Optional[str] = None,
        operator_id: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
        invalidate_cache: bool = True
    ) -> Dict[str, Any]:
        """统一的投稿状态更新
        
        Args:
            submission_id: 投稿ID
            status: 新状态（None表示不更新状态）
            operator_id: 操作员ID
            extra_fields: 额外要更新的字段
            invalidate_cache: 是否清除缓存
            
        Returns:
            操作结果
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 获取投稿
                submission = await SubmissionOperations.get_submission(
                    submission_id, session
                )
                
                if not submission:
                    return {
                        'success': False,
                        'message': '投稿不存在'
                    }
                
                # 更新状态
                if status is not None:
                    submission.status = status
                
                # 更新操作员
                if operator_id:
                    submission.processed_by = operator_id
                
                # 更新额外字段
                if extra_fields:
                    for key, value in extra_fields.items():
                        if hasattr(submission, key):
                            setattr(submission, key, value)
                
                await session.commit()
                
                # 清除缓存
                if invalidate_cache:
                    try:
                        from core.data_cache_service import DataCacheService
                        await DataCacheService.invalidate_submission(submission_id)
                    except Exception as e:
                        logger.warning(f"清除缓存失败: {e}")
                
                return {
                    'success': True,
                    'message': '更新成功',
                    'submission': submission
                }
                
        except Exception as e:
            logger.error(f"更新投稿失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'更新失败: {str(e)}'
            }
    
    @staticmethod
    async def execute_with_submission(
        submission_id: int,
        operation: Callable[[Submission, AsyncSession], Any],
        error_message: str = "操作失败"
    ) -> Dict[str, Any]:
        """执行需要投稿对象的操作（模板方法）
        
        Args:
            submission_id: 投稿ID
            operation: 操作函数，接收 (submission, session) 参数
            error_message: 错误消息
            
        Returns:
            操作结果
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 获取投稿
                submission = await SubmissionOperations.get_submission(
                    submission_id, session
                )
                
                if not submission:
                    return {
                        'success': False,
                        'message': '投稿不存在'
                    }
                
                # 执行操作
                result = await operation(submission, session)
                
                # 如果操作返回字典，直接返回；否则包装为成功结果
                if isinstance(result, dict):
                    return result
                else:
                    return {
                        'success': True,
                        'message': '操作成功',
                        'data': result
                    }
                    
        except Exception as e:
            logger.error(f"{error_message}: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'{error_message}: {str(e)}'
            }
    
    @staticmethod
    async def validate_status_transition(
        submission: Submission,
        target_status: str,
        allowed_from: Optional[list] = None
    ) -> Dict[str, Any]:
        """验证状态转换是否合法
        
        Args:
            submission: 投稿对象
            target_status: 目标状态
            allowed_from: 允许的源状态列表，None表示不限制
            
        Returns:
            验证结果
        """
        if allowed_from and submission.status not in allowed_from:
            return {
                'success': False,
                'message': f'当前状态 {submission.status} 不允许转换为 {target_status}'
            }
        
        return {
            'success': True,
            'message': '状态转换合法'
        }
    
    @staticmethod
    async def check_ownership(
        submission: Submission,
        user_id: str
    ) -> bool:
        """检查用户是否拥有该投稿
        
        Args:
            submission: 投稿对象
            user_id: 用户ID
            
        Returns:
            是否拥有
        """
        return str(submission.sender_id) == str(user_id)
    
    @staticmethod
    async def send_notification(
        submission: Submission,
        notification_type: str,
        reason: Optional[str] = None
    ) -> bool:
        """发送投稿相关通知（统一入口）
        
        Args:
            submission: 投稿对象
            notification_type: 通知类型 (approved | rejected | deleted)
            reason: 原因（拒绝/删除时使用）
            
        Returns:
            是否发送成功
        """
        try:
            from services.notification_service import NotificationService
            notification = NotificationService()
            
            if notification_type == 'approved':
                return await notification.send_submission_approved(submission.id)
            
            elif notification_type == 'rejected':
                return await notification.send_submission_rejected(
                    submission.id, reason
                )
            
            elif notification_type == 'deleted':
                # 发送删除通知
                message = f"您的投稿 {submission.publish_id or submission.id} 已被删除"
                if reason:
                    message += f"\n原因: {reason}"
                
                return await notification.send_to_user(
                    submission.sender_id,
                    message,
                    submission.group_name
                )
            
            else:
                logger.warning(f"未知的通知类型: {notification_type}")
                return False
                
        except Exception as e:
            logger.error(f"发送通知失败: {e}", exc_info=True)
            return False

