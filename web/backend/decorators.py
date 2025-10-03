"""FastAPI 辅助函数
减少审核端点的重复代码
"""
from typing import Optional, Callable, Dict, Any, Awaitable
from fastapi import HTTPException


async def execute_audit_action(
    submission_id: int,
    operator_id: str,
    action_func: Callable[..., Awaitable[Dict[str, Any]]],
    extra: Optional[str] = None,
    send_sse: bool = False,
    sse_event_type: Optional[str] = None,
    notify_submission_update: Optional[Callable] = None
) -> Dict[str, Any]:
    """统一执行审核操作
    
    Args:
        submission_id: 投稿ID
        operator_id: 操作员ID
        action_func: 审核服务方法
        extra: 额外参数
        send_sse: 是否发送 SSE 通知
        sse_event_type: SSE 事件类型
        notify_submission_update: SSE 通知函数
        
    Returns:
        操作结果
    """
    # 调用业务逻辑
    if extra is not None:
        result = await action_func(submission_id, operator_id, extra)
    else:
        result = await action_func(submission_id, operator_id)
    
    # 检查结果
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    # 发送 SSE 通知
    if send_sse and sse_event_type and notify_submission_update:
        try:
            await notify_submission_update(
                submission_id,
                sse_event_type,
                {"operator": operator_id}
            )
        except Exception:
            pass  # SSE 失败不影响主流程
    
    return result

