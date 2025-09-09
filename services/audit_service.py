"""审核服务"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from core.database import get_db
from core.models import Submission, AuditLog, BlackList, StoredPost
from core.enums import SubmissionStatus, AuditAction
from processors.pipeline import ProcessingPipeline

# module-level commonly used imports to avoid repeated runtime imports
from config import get_settings
from sqlalchemy import update, delete, func
from services.notification_service import NotificationService
from utils.common import get_platform_config


class AuditService:
    """审核服务，处理投稿审核相关操作"""
    
    def __init__(self):
        self.logger = logger.bind(module="audit")
        self.pipeline = ProcessingPipeline()
        self.commands = {
            '是': self.approve,
            '否': self.reject,
            '匿': self.toggle_anonymous,
            '等': self.hold,
            '删': self.delete,
            '拒': self.reject_with_message,
            '立即': self.approve_immediate,
            '刷新': self.refresh,
            '重渲染': self.rerender,
            '扩列审查': self.expand_review,
            '评论': self.add_comment,
            '回复': self.reply_to_sender,
            '展示': self.show_content,
            '拉黑': self.blacklist,
        }
        
    async def initialize(self):
        """初始化服务"""
        await self.pipeline.initialize()
        self.logger.info("审核服务初始化完成")
        
    async def shutdown(self):
        """关闭服务"""
        await self.pipeline.shutdown()
        
    async def handle_command(self, submission_id: int, command: str, 
                           operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """处理审核指令
        
        Args:
            submission_id: 投稿ID
            command: 指令
            operator_id: 操作员ID
            extra: 额外参数
            
        Returns:
            处理结果
        """
        # 查找指令处理器
        handler = self.commands.get(command)
        if not handler:
            # 检查是否是快捷回复
            return await self.quick_reply(submission_id, command, operator_id, extra)
            
        # 执行指令
        try:
            result = await handler(submission_id, operator_id, extra)
            
            # 记录审核日志
            await self.log_audit(submission_id, operator_id, command, extra)
            
            return result
            
        except Exception as e:
            self.logger.error(f"执行审核指令失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'指令执行失败: {str(e)}'
            }
            
    async def approve(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """通过投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # 获取投稿
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 更新状态
            submission.status = SubmissionStatus.APPROVED.value
            
            # 获取发布编号
            settings = get_settings()
            group = settings.account_groups.get(submission.group_name)
            
            if group:
                # 获取当前编号
                num_file = f"data/cache/numb/{submission.group_name}_numfinal.txt"
                try:
                    with open(num_file, 'r') as f:
                        current_num = int(f.read().strip())
                except:
                    current_num = 1
                    
                submission.publish_id = current_num
                
                # 更新编号
                with open(num_file, 'w') as f:
                    f.write(str(current_num + 1))
                    
                # 添加到暂存区
                stored = StoredPost(
                    submission_id=submission_id,
                    group_name=submission.group_name,
                    publish_id=current_num,
                    priority=0
                )
                session.add(stored)
                
            await session.commit()
            
            return {
                'success': True,
                'message': f'投稿已通过，编号 #{submission.publish_id}',
                'publish_id': submission.publish_id
            }
            
    async def approve_immediate(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """立即发送投稿"""
        # 先通过投稿
        result = await self.approve(submission_id, operator_id, extra)
        if not result['success']:
            return result
            
        # 触发立即发送
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if submission:
                # 这里应该触发发送器立即发送
                # TODO: 集成发送器
                pass
                
        return {
            'success': True,
            'message': '投稿已立即发送'
        }
        
    async def reject(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """拒绝投稿（跳过）"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            submission.status = SubmissionStatus.REJECTED.value
            submission.rejection_reason = "管理员跳过处理"
            await session.commit()
            
            return {
                'success': True,
                'message': '投稿已跳过'
            }
            
    async def reject_with_message(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """拒绝投稿并通知"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            submission.status = SubmissionStatus.REJECTED.value
            submission.rejection_reason = extra or "投稿未通过审核"
            await session.commit()
            
            # 发送通知给投稿者
            try:
                notifier = NotificationService()
                await notifier.send_submission_rejected(submission_id, reason=submission.rejection_reason)
            except Exception:
                pass
            
            return {
                'success': True,
                'message': '投稿已拒绝，已通知投稿者'
            }
            
    async def delete(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """删除投稿"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            submission.status = SubmissionStatus.DELETED.value
            await session.commit()
            
            # 删除缓存文件
            import shutil
            cache_dir = f"data/cache/rendered/{submission_id}"
            try:
                shutil.rmtree(cache_dir)
            except:
                pass
                
            return {
                'success': True,
                'message': '投稿已删除'
            }
            
    async def toggle_anonymous(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """切换匿名状态"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 切换匿名状态
            submission.is_anonymous = not submission.is_anonymous
            
            # 更新LLM结果
            if submission.llm_result:
                submission.llm_result['needpriv'] = 'true' if submission.is_anonymous else 'false'
                
            await session.commit()
            
            # 重新渲染
            await self.pipeline.reprocess_submission(submission_id, skip_llm=True)
            
            return {
                'success': True,
                'message': f'匿名状态已切换为: {"匿名" if submission.is_anonymous else "实名"}',
                'need_reaudit': True
            }
            
    async def hold(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """暂缓处理"""
        # 等待一段时间后重新处理
        await asyncio.sleep(180)  # 等待3分钟
        
        # 重新处理
        success = await self.pipeline.process_submission(submission_id)
        
        return {
            'success': success,
            'message': '已重新处理',
            'need_reaudit': True
        }
        
    async def refresh(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """刷新处理"""
        success = await self.pipeline.process_submission(submission_id)
        
        return {
            'success': success,
            'message': '已刷新处理',
            'need_reaudit': True
        }
        
    async def rerender(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """重新渲染"""
        success = await self.pipeline.reprocess_submission(submission_id, skip_llm=True)
        
        return {
            'success': success,
            'message': '已重新渲染',
            'need_reaudit': True
        }
        
    async def expand_review(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """扩展审查"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # TODO: 获取用户信息、QQ等级、空间状态等
            info = {
                'user_id': submission.sender_id,
                'nickname': submission.sender_nickname,
                'qq_level': '未知',
                'qzone_status': '未知'
            }
            
            return {
                'success': True,
                'message': '扩展审查完成',
                'data': info
            }
            
    async def add_comment(self, submission_id: int, operator_id: str, comment: Optional[str] = None) -> Dict[str, Any]:
        """添加评论"""
        if not comment:
            return {'success': False, 'message': '评论内容不能为空'}
            
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            submission.comment = comment
            await session.commit()
            
            # 通知审核群重新审核
            try:
                notifier = NotificationService()
                await notifier.send_audit_request(submission_id)
            except Exception:
                pass

            return {
                'success': True,
                'message': f'已添加评论: {comment}',
                'need_reaudit': True
            }
            
    async def reply_to_sender(self, submission_id: int, operator_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """回复投稿者"""
        if not message:
            return {'success': False, 'message': '回复内容不能为空'}
            
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            try:
                notifier = NotificationService()
                await notifier.send_to_user(submission.sender_id, message, submission.group_name)
            except Exception:
                pass
            
            return {
                'success': True,
                'message': f'已回复: {message}'
            }
            
    async def show_content(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """展示内容"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 返回渲染的图片
            return {
                'success': True,
                'message': '内容展示',
                'images': submission.rendered_images,
                'need_reaudit': True
            }
            
    async def blacklist(self, submission_id: int, operator_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """拉黑用户"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 添加到黑名单
            blacklist = BlackList(
                user_id=submission.sender_id,
                group_name=submission.group_name,
                reason=reason or "违规投稿",
                operator_id=operator_id
            )
            session.add(blacklist)
            
            # 删除投稿
            submission.status = SubmissionStatus.DELETED.value
            
            await session.commit()
            
            return {
                'success': True,
                'message': f'用户 {submission.sender_id} 已拉黑'
            }
            
    async def quick_reply(self, submission_id: int, command: str, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """快捷回复"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 获取快捷回复配置
            settings = get_settings()
            group = settings.account_groups.get(submission.group_name)
            
            if not group:
                return {'success': False, 'message': '找不到账号组配置'}
                
            reply_content = group.quick_replies.get(command)
            if not reply_content:
                return {'success': False, 'message': f'未知的指令: {command}'}
                
            # 发送快捷回复给投稿者
            try:
                notifier = NotificationService()
                await notifier.send_to_user(submission.sender_id, reply_content, submission.group_name)
            except Exception:
                pass
            
            return {
                'success': True,
                'message': f'已发送快捷回复: {reply_content}'
            }
            
    async def log_audit(self, submission_id: int, operator_id: str, action: str, comment: Optional[str] = None):
        """记录审核日志"""
        db = await get_db()
        async with db.get_session() as session:
            audit_log = AuditLog(
                submission_id=submission_id,
                operator_id=operator_id,
                action=action,
                comment=comment
            )
            session.add(audit_log)
            await session.commit()
