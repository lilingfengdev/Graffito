"""服务层装饰器
用于减少重复代码，统一错误处理和日志记录
"""
import functools
from typing import Dict, Any, Optional, Callable
from loguru import logger
from sqlalchemy import select

from core.database import get_db
from core.models import Submission


def with_submission(error_message: str = "操作失败"):
    """装饰器：自动获取投稿对象并注入到方法中
    
    被装饰的方法签名应为:
    async def method(self, submission: Submission, session, submission_id, ...)
    
    装饰后可以这样调用:
    async def method(self, submission_id: int, ...)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, submission_id: int, *args, **kwargs) -> Dict[str, Any]:
            try:
                db = await get_db()
                async with db.get_session() as session:
                    # 获取投稿
                    stmt = select(Submission).where(Submission.id == submission_id)
                    result = await session.execute(stmt)
                    submission = result.scalar_one_or_none()
                    
                    if not submission:
                        return {
                            'success': False,
                            'message': '投稿不存在'
                        }
                    
                    # 调用原函数，注入 submission 和 session
                    return await func(
                        self,
                        submission=submission,
                        session=session,
                        submission_id=submission_id,
                        *args,
                        **kwargs
                    )
                    
            except Exception as e:
                logger.error(f"{error_message}: {e}", exc_info=True)
                return {
                    'success': False,
                    'message': f'{error_message}: {str(e)}'
                }
        
        return wrapper
    return decorator


def invalidate_cache_after(func: Callable) -> Callable:
    """装饰器：方法执行成功后自动清除缓存
    
    要求方法返回包含 'success' 和 'submission_id' 的字典
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Dict[str, Any]:
        result = await func(*args, **kwargs)
        
        # 如果成功，清除缓存
        if isinstance(result, dict) and result.get('success'):
            try:
                submission_id = None
                
                # 尝试从参数中获取 submission_id
                if len(args) > 1 and isinstance(args[1], int):
                    submission_id = args[1]
                elif 'submission_id' in kwargs:
                    submission_id = kwargs['submission_id']
                elif 'submission_id' in result:
                    submission_id = result['submission_id']
                
                if submission_id:
                    from core.data_cache_service import DataCacheService
                    await DataCacheService.invalidate_submission(submission_id)
                    logger.debug(f"已清除投稿 {submission_id} 的缓存")
                    
            except Exception as e:
                logger.warning(f"清除缓存失败: {e}")
        
        return result
    
    return wrapper


def log_audit_action(action: str):
    """装饰器：自动记录审核日志
    
    要求方法签名包含 submission_id 和 operator_id
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, submission_id: int, operator_id: str, *args, **kwargs) -> Dict[str, Any]:
            result = await func(self, submission_id, operator_id, *args, **kwargs)
            
            # 如果成功，记录日志
            if isinstance(result, dict) and result.get('success'):
                try:
                    # 获取额外信息
                    extra = kwargs.get('extra') or (args[0] if args else None)
                    
                    # 调用审核服务的日志方法
                    if hasattr(self, 'log_audit'):
                        await self.log_audit(
                            submission_id,
                            operator_id,
                            action,
                            extra
                        )
                except Exception as e:
                    logger.warning(f"记录审核日志失败: {e}")
            
            return result
        
        return wrapper
    return decorator


def send_notification_after(notification_type: str):
    """装饰器：操作成功后自动发送通知
    
    Args:
        notification_type: 通知类型 (approved | rejected | deleted)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Dict[str, Any]:
            result = await func(*args, **kwargs)
            
            # 如果成功，发送通知
            if isinstance(result, dict) and result.get('success'):
                try:
                    # 获取 submission
                    submission = result.get('submission')
                    
                    if submission:
                        from services.submission_operations import SubmissionOperations
                        
                        # 获取原因（如果有）
                        reason = kwargs.get('extra') or (
                            args[2] if len(args) > 2 else None
                        )
                        
                        await SubmissionOperations.send_notification(
                            submission,
                            notification_type,
                            reason
                        )
                        logger.debug(f"已发送 {notification_type} 通知")
                        
                except Exception as e:
                    logger.warning(f"发送通知失败: {e}")
            
            return result
        
        return wrapper
    return decorator


def require_status(allowed_statuses: list):
    """装饰器：验证投稿当前状态是否允许操作
    
    Args:
        allowed_statuses: 允许的状态列表
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, submission: Submission, *args, **kwargs) -> Dict[str, Any]:
            if submission.status not in allowed_statuses:
                return {
                    'success': False,
                    'message': f'当前状态 ({submission.status}) 不允许此操作'
                }
            
            return await func(self, submission=submission, *args, **kwargs)
        
        return wrapper
    return decorator

