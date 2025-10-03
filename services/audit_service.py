"""审核服务"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from core.database import get_db
from core.models import Submission, AuditLog, BlackList, StoredPost
from core.enums import SubmissionStatus, AuditAction
from processors.pipeline import get_shared_pipeline, ProcessingPipeline

# module-level commonly used imports to avoid repeated runtime imports
from config import get_settings
from sqlalchemy import update, delete, func, select
from services.notification_service import NotificationService
from services.submission_operations import SubmissionOperations
from services.decorators import with_submission, invalidate_cache_after, log_audit_action
from utils.common import get_platform_config


class AuditService:
    """审核服务，处理投稿审核相关操作"""
    
    def __init__(self):
        self.logger = logger.bind(module="audit")
        # 共享全局管道，避免重复初始化
        self.pipeline = get_shared_pipeline()
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
            
            # 已通过或已发布不可重复通过
            if submission.status in (SubmissionStatus.APPROVED.value, SubmissionStatus.PUBLISHED.value):
                return {
                    'success': False,
                    'message': '该投稿已处于通过/发布状态，不能重复通过'
                }
                
            # 更新状态和处理人
            submission.status = SubmissionStatus.APPROVED.value
            submission.processed_by = operator_id
            
            # 清除缓存
            from core.data_cache_service import DataCacheService
            await DataCacheService.invalidate_submission(submission_id)
            
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
                    
                # 添加到暂存区（独立模式：记录所有配置了定时的平台）
                from core.plugin import plugin_manager
                from utils.common import get_platform_config
                
                scheduled_platforms = []
                try:
                    for pub in plugin_manager.publishers.values():
                        try:
                            platform_key = getattr(pub.platform, "value", "")
                            cfg = get_platform_config(platform_key)
                            times = (cfg or {}).get("send_schedule") or []
                            if times:
                                scheduled_platforms.append(platform_key)
                        except Exception:
                            continue
                except Exception:
                    pass
                
                stored = StoredPost(
                    submission_id=submission_id,
                    group_name=submission.group_name,
                    publish_id=current_num,
                    priority=0,
                    pending_platforms=scheduled_platforms  # 独立模式：记录待发布的平台
                )
                session.add(stored)
                
            await session.commit()
            
            # 如果没有配置定时发送（scheduled_platforms 为空），则立即发送
            if not scheduled_platforms:
                try:
                    from services.submission_service import SubmissionService
                    submission_service = SubmissionService()
                    await submission_service.initialize()
                    
                    # 立即发送该投稿
                    success = await submission_service.publish_single_submission(submission_id)
                    
                    await submission_service.shutdown()
                    
                    if success:
                        self.logger.info(f"投稿 {submission_id} 已立即发送")
                        return {
                            'success': True,
                            'message': f'投稿已通过并立即发送，编号 #{submission.publish_id}',
                            'publish_id': submission.publish_id
                        }
                    else:
                        self.logger.warning(f"投稿 {submission_id} 通过但发送失败")
                        return {
                            'success': True,
                            'message': f'投稿已通过（编号 #{submission.publish_id}），但发送失败，请稍后重试',
                            'publish_id': submission.publish_id
                        }
                except Exception as e:
                    self.logger.error(f"立即发送投稿失败: {e}", exc_info=True)
            
            return {
                'success': True,
                'message': f'投稿已通过，编号 #{submission.publish_id}',
                'publish_id': submission.publish_id
            }
            
    async def approve_immediate(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """立即发送投稿"""
        db = await get_db()
        async with db.get_session() as session:
            # 检查投稿状态
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
            
            # 如果还未通过，先通过
            if submission.status not in (SubmissionStatus.APPROVED.value, SubmissionStatus.PUBLISHED.value):
                approve_result = await self.approve(submission_id, operator_id, extra)
                if not approve_result['success']:
                    return approve_result
        
        # 立即发送（无论是否有 send_schedule 配置）
        try:
            from services.submission_service import SubmissionService
            submission_service = SubmissionService()
            await submission_service.initialize()
            
            # 立即发送该投稿
            success = await submission_service.publish_single_submission(submission_id)
            
            await submission_service.shutdown()
            
            if success:
                self.logger.info(f"投稿 {submission_id} 已立即发送")
                return {
                    'success': True,
                    'message': '投稿已立即发送'
                }
            else:
                self.logger.warning(f"投稿 {submission_id} 发送失败")
                return {
                    'success': False,
                    'message': '发送失败，请检查发布器配置或稍后重试'
                }
        except Exception as e:
            self.logger.error(f"立即发送投稿失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'发送失败: {str(e)}'
            }
        
    @invalidate_cache_after
    async def reject(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """拒绝投稿（跳过）"""
        result = await SubmissionOperations.update_submission_status(
            submission_id,
            SubmissionStatus.REJECTED.value,
            operator_id,
            extra_fields={'rejection_reason': "管理员跳过处理"},
            invalidate_cache=False  # 装饰器会处理
        )
        
        if result['success']:
            result['message'] = '投稿已跳过'
        
        return result
            
    @invalidate_cache_after
    async def reject_with_message(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """拒绝投稿并通知"""
        reason = extra or "投稿未通过审核"
        
        result = await SubmissionOperations.update_submission_status(
            submission_id,
            SubmissionStatus.REJECTED.value,
            operator_id,
            extra_fields={'rejection_reason': reason},
            invalidate_cache=False  # 装饰器处理
        )
        
        if not result['success']:
            return result
        
        # 发送通知给投稿者
        try:
            submission = result.get('submission')
            if submission:
                await SubmissionOperations.send_notification(
                    submission, 'rejected', reason
                )
        except Exception:
            pass
        
        return {
            'success': True,
            'message': '投稿已拒绝，已通知投稿者'
        }
            
    async def delete(self, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """删除投稿（包括已发布到平台的内容）"""
        # 调用 SubmissionService 的完整删除逻辑，包括删除平台内容
        from services.submission_service import SubmissionService
        
        submission_service = SubmissionService()
        await submission_service.initialize()
        
        try:
            result = await submission_service.delete_submission(submission_id)
            
            # 删除本地缓存文件
            if result.get('success'):
                import shutil
                cache_dir = f"data/cache/rendered/{submission_id}"
                try:
                    shutil.rmtree(cache_dir)
                except:
                    pass
            
            return result
        finally:
            await submission_service.shutdown()
            
    @invalidate_cache_after
    @with_submission("切换匿名状态失败")
    async def toggle_anonymous(self, submission: Submission, session, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """切换匿名状态"""
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
            'submission_id': submission_id,
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
        """扩展审查 - 通过 NapCat API 获取用户详细信息"""
        db = await get_db()
        async with db.get_session() as session:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                return {'success': False, 'message': '投稿不存在'}
                
            # 通过 NapCat API 获取用户信息
            user_info = await self._get_user_info_from_napcat(
                user_id=submission.sender_id,
                receiver_id=submission.receiver_id
            )
            
            # 性别和状态映射
            sex_map = {"male": "男", "female": "女", "unknown": "未知"}
            status_map = {10: "离线", 20: "在线", 30: "离开", 40: "隐身", 50: "忙碌", 60: "Q我吧", 70: "请勿打扰"}
            
            sex_value = user_info.get('sex', 'unknown')
            status_code = user_info.get('status')
            
            info = {
                'user_id': submission.sender_id,
                'nickname': user_info.get('nickname') or submission.sender_nickname,
                'qq_level': str(user_info.get('qqLevel', '未知')),
                'age': str(user_info.get('age', '未知')),
                'sex': sex_map.get(sex_value, sex_value),
                'login_days': str(user_info.get('login_days', '未知')),
                'status': status_map.get(status_code, f"未知({status_code})") if status_code is not None else "未知",
                'card': user_info.get('card', ''),
                'area': user_info.get('area', ''),
                'title': user_info.get('title', ''),
            }
            
            return {
                'success': True,
                'message': '扩展审查完成',
                'data': info
            }
    
    async def _get_user_info_from_napcat(self, user_id: str, receiver_id: str) -> Dict[str, Any]:
        """通过 NapCat API 获取用户详细信息
        
        参考文档: https://napcat.apifox.cn/226656970e0.md
        """
        try:
            # 获取配置
            settings = get_settings()
            
            # 找到对应的账号配置
            account_config = None
            for group in settings.account_groups.values():
                if group.main_account.qq_id == receiver_id:
                    account_config = group.main_account
                    break
                for minor in group.minor_accounts:
                    if minor.qq_id == receiver_id:
                        account_config = minor
                        break
                if account_config:
                    break
            
            if not account_config:
                self.logger.warning(f"未找到账号配置: receiver_id={receiver_id}")
                return {}
            
            # 准备 NapCat HTTP 请求
            import httpx
            
            host = account_config.http_host
            port = account_config.http_port
            http_token = account_config.http_token
            
            headers = {}
            if http_token:
                headers['Authorization'] = f'Bearer {http_token}'
            
            async with httpx.AsyncClient(headers=headers, timeout=10) as client:
                # 调用 get_stranger_info API (根据 NapCat 文档应使用 POST 请求)
                url = f"http://{host}:{port}/get_stranger_info"
                payload = {"user_id": int(user_id)}
                
                try:
                    resp = await client.post(url, json=payload)
                    
                    if resp.status_code != 200:
                        self.logger.error(f"NapCat API 请求失败: HTTP {resp.status_code}")
                        return {}
                    
                    data = resp.json()
                    
                    if data.get('status') == 'ok' and data.get('data'):
                        return data['data']
                    else:
                        self.logger.warning(f"NapCat API 返回异常: {data}")
                        return {}
                        
                except httpx.HTTPError as e:
                    self.logger.error(f"NapCat API 请求异常: {e}")
                    return {}
                    
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}", exc_info=True)
            return {}
            
    @invalidate_cache_after
    @with_submission("添加评论失败")
    async def add_comment(self, submission: Submission, session, submission_id: int, operator_id: str, comment: Optional[str] = None) -> Dict[str, Any]:
        """添加评论"""
        if not comment:
            return {'success': False, 'message': '评论内容不能为空'}
        
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
            
    @with_submission("回复投稿者失败")
    async def reply_to_sender(self, submission: Submission, session, submission_id: int, operator_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """回复投稿者"""
        if not message:
            return {'success': False, 'message': '回复内容不能为空'}
        
        try:
            notifier = NotificationService()
            await notifier.send_to_user(submission.sender_id, message, submission.group_name)
        except Exception:
            pass
        
        return {
            'success': True,
            'message': f'已回复: {message}'
        }
            
    @with_submission("展示内容失败")
    async def show_content(self, submission: Submission, session, submission_id: int, operator_id: str, extra: Optional[str] = None) -> Dict[str, Any]:
        """展示内容"""
        # 返回渲染的图片
        return {
            'success': True,
            'message': '内容展示',
            'images': submission.rendered_images,
            'need_reaudit': True
        }
    
    @invalidate_cache_after
    @with_submission("拉黑用户失败")
    async def blacklist(self, submission: Submission, session, submission_id: int, operator_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """拉黑用户"""
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
        submission.processed_by = operator_id
        
        # 清除黑名单缓存（因为新加入黑名单）
        from core.data_cache_service import DataCacheService
        await DataCacheService.invalidate_blacklist(str(submission.sender_id), submission.group_name)
        
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
