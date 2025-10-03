"""举报服务"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Report, Submission, PlatformComment
from core.enums import ReportStatus, ModerationLevel, ModerationAction, SubmissionStatus
from core.database import get_db

logger = logging.getLogger(__name__)


class ReportService:
    """举报服务"""
    
    @staticmethod
    async def create_report(
        publish_id: int,
        reporter_id: str,
        receiver_id: str,
        group_name: str,
        reason: Optional[str] = None
    ) -> Optional[Report]:
        """创建举报记录
        
        Args:
            publish_id: 投稿发布编号（用户可见的外部 ID）
            reporter_id: 举报者 QQ 号
            receiver_id: 接收账号
            group_name: 账号组名称
            reason: 举报理由
            
        Returns:
            Report: 举报记录
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 根据 publish_id 查找投稿（内部 ID）
                result = await session.execute(
                    select(Submission).where(Submission.publish_id == publish_id)
                )
                submission = result.scalar_one_or_none()
                
                if not submission:
                    logger.warning(f"投稿 {publish_id} 不存在")
                    return None
                
                submission_id = submission.id
                
                # 检查是否已经举报过
                existing_result = await session.execute(
                    select(Report).where(
                        Report.submission_id == submission_id,
                        Report.reporter_id == reporter_id,
                        Report.status.in_([ReportStatus.PENDING.value, ReportStatus.AI_PROCESSING.value, ReportStatus.MANUAL_REVIEW.value])
                    )
                )
                existing_report = existing_result.scalar_one_or_none()
                
                if existing_report:
                    logger.info(f"用户 {reporter_id} 已经举报过投稿 {publish_id}（内部ID: {submission_id}）")
                    return existing_report
                
                # 创建举报记录
                report = Report(
                    submission_id=submission_id,
                    reporter_id=reporter_id,
                    receiver_id=receiver_id,
                    group_name=group_name,
                    reason=reason,
                    status=ReportStatus.PENDING.value
                )
                
                session.add(report)
                await session.commit()
                await session.refresh(report)
                
                logger.info(f"创建举报记录: ID={report.id}, 投稿={publish_id}（内部ID: {submission_id}）, 举报者={reporter_id}")
                return report
                
        except Exception as e:
            logger.error(f"创建举报记录失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def get_report(report_id: int) -> Optional[Report]:
        """获取举报记录
        
        Args:
            report_id: 举报 ID
            
        Returns:
            Report: 举报记录
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                result = await session.execute(
                    select(Report).where(Report.id == report_id)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取举报记录失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def get_pending_reports() -> List[Report]:
        """获取待处理的举报
        
        Returns:
            List[Report]: 举报列表
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                result = await session.execute(
                    select(Report)
                    .where(Report.status == ReportStatus.PENDING.value)
                    .order_by(Report.created_at.asc())
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"获取待处理举报失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def update_ai_result(
        report_id: int,
        level: str,
        reason: str
    ) -> bool:
        """更新 AI 审核结果
        
        Args:
            report_id: 举报 ID
            level: AI 评级
            reason: AI 评级理由
            
        Returns:
            bool: 是否更新成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                await session.execute(
                    update(Report)
                    .where(Report.id == report_id)
                    .values(
                        ai_level=level,
                        ai_reason=reason,
                        ai_processed_at=datetime.now(),
                        status=ReportStatus.AI_PROCESSING.value
                    )
                )
                await session.commit()
                logger.info(f"更新举报 {report_id} 的 AI 审核结果: {level}")
                return True
        except Exception as e:
            logger.error(f"更新 AI 审核结果失败: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def process_report(
        report_id: int,
        action: str,
        reason: str,
        processed_by: str
    ) -> bool:
        """处理举报
        
        Args:
            report_id: 举报 ID
            action: 处理动作
            reason: 处理理由
            processed_by: 处理人
            
        Returns:
            bool: 是否处理成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                await session.execute(
                    update(Report)
                    .where(Report.id == report_id)
                    .values(
                        manual_action=action,
                        manual_reason=reason,
                        processed_by=processed_by,
                        processed_at=datetime.now(),
                        status=ReportStatus.RESOLVED.value
                    )
                )
                await session.commit()
                
                logger.info(f"处理举报 {report_id}: 动作={action}, 处理人={processed_by}")
                return True
        except Exception as e:
            logger.error(f"处理举报失败: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def set_manual_review(report_id: int) -> bool:
        """设置为人工审核状态
        
        Args:
            report_id: 举报 ID
            
        Returns:
            bool: 是否设置成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                await session.execute(
                    update(Report)
                    .where(Report.id == report_id)
                    .values(status=ReportStatus.MANUAL_REVIEW.value)
                )
                await session.commit()
                logger.info(f"举报 {report_id} 进入人工审核")
                return True
        except Exception as e:
            logger.error(f"设置人工审核失败: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_reports_for_review(
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Report], int]:
        """获取需要审核的举报列表
        
        Args:
            status: 状态筛选
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            tuple: (举报列表, 总数)
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                # 构建查询
                query = select(Report)
                count_query = select(Report)
                
                if status:
                    query = query.where(Report.status == status)
                    count_query = count_query.where(Report.status == status)
                
                # 获取总数
                count_result = await session.execute(count_query)
                total = len(list(count_result.scalars().all()))
                
                # 获取列表
                query = query.order_by(desc(Report.created_at)).limit(limit).offset(offset)
                result = await session.execute(query)
                reports = list(result.scalars().all())
                
                return reports, total
        except Exception as e:
            logger.error(f"获取审核列表失败: {e}", exc_info=True)
            return [], 0
    
    @staticmethod
    async def save_platform_comments(
        submission_id: int,
        platform: str,
        comments: List[Dict[str, Any]]
    ) -> bool:
        """保存平台评论
        
        Args:
            submission_id: 投稿 ID
            platform: 平台名称
            comments: 评论列表
            
        Returns:
            bool: 是否保存成功
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                for comment_data in comments:
                    # 检查是否已存在
                    if comment_data.get('comment_id'):
                        existing_result = await session.execute(
                            select(PlatformComment).where(
                                PlatformComment.submission_id == submission_id,
                                PlatformComment.platform == platform,
                                PlatformComment.comment_id == comment_data['comment_id']
                            )
                        )
                        if existing_result.scalar_one_or_none():
                            continue
                    
                    # 创建评论记录
                    comment = PlatformComment(
                        submission_id=submission_id,
                        platform=platform,
                        comment_id=comment_data.get('comment_id'),
                        author_id=comment_data.get('author_id'),
                        author_name=comment_data.get('author_name'),
                        content=comment_data.get('content'),
                        created_at=comment_data.get('created_at', datetime.now())
                    )
                    session.add(comment)
                
                await session.commit()
                logger.info(f"保存了 {len(comments)} 条评论到投稿 {submission_id}")
                return True
        except Exception as e:
            logger.error(f"保存平台评论失败: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_platform_comments(submission_id: int) -> List[PlatformComment]:
        """获取投稿的平台评论
        
        Args:
            submission_id: 投稿 ID
            
        Returns:
            List[PlatformComment]: 评论列表
        """
        try:
            db = await get_db()
            async with db.get_session() as session:
                result = await session.execute(
                    select(PlatformComment)
                    .where(PlatformComment.submission_id == submission_id)
                    .order_by(PlatformComment.created_at.asc())
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"获取平台评论失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def handle_report_action(
        report: Report,
        submission: Submission,
        action: str,
        reason: str,
        processed_by: str
    ) -> Dict[str, Any]:
        """统一处理举报动作（删除或保留）
        
        Args:
            report: 举报记录
            submission: 投稿记录
            action: 处理动作 (delete | keep)
            reason: 处理理由
            processed_by: 处理人
            
        Returns:
            处理结果字典
        """
        try:
            # 导入必要模块
            from services.notification_service import NotificationService
            
            notification = NotificationService()
            
            # 更新举报状态
            await ReportService.process_report(
                report_id=report.id,
                action=action,
                reason=reason,
                processed_by=processed_by
            )
            
            if action == 'delete':
                # 调用 SubmissionService 删除投稿
                from services.submission_service import SubmissionService
                submission_service = SubmissionService()
                delete_result = await submission_service.delete_submission(submission.id)
                
                if not delete_result.get('success'):
                    logger.warning(
                        f"删除投稿 {submission.publish_id or submission.id} 失败: "
                        f"{delete_result.get('message')}"
                    )
                    # 即使平台删除失败，也将状态置为 DELETED
                    db = await get_db()
                    async with db.get_session() as session:
                        await session.execute(
                            update(Submission)
                            .where(Submission.id == submission.id)
                            .values(status=SubmissionStatus.DELETED.value)
                        )
                        await session.commit()
                
                # 通知举报者和投稿者
                await notification.notify_report_processed(
                    reporter_id=report.reporter_id,
                    sender_id=submission.sender_id,
                    receiver_id=report.receiver_id,
                    publish_id=submission.publish_id or submission.id,
                    action='delete',
                    reason=reason
                )
                
                logger.info(
                    f"删除投稿 {submission.publish_id or submission.id}"
                    f"（内部ID: {submission.id}），处理人: {processed_by}"
                )
                
            else:  # keep
                # 通知举报者
                await notification.notify_report_processed(
                    reporter_id=report.reporter_id,
                    sender_id=None,  # 保留时不通知投稿者
                    receiver_id=report.receiver_id,
                    publish_id=submission.publish_id or submission.id,
                    action='keep',
                    reason=reason
                )
                
                logger.info(
                    f"保留投稿 {submission.publish_id or submission.id}"
                    f"（内部ID: {submission.id}），处理人: {processed_by}"
                )
            
            return {
                "success": True,
                "message": "处理成功",
                "action": action
            }
            
        except Exception as e:
            logger.error(f"处理举报动作失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"处理失败: {str(e)}"
            }

