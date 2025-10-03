"""数据模型定义"""
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Column, Integer, String, DateTime, JSON, Boolean, 
    Text, ForeignKey, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from .enums import SubmissionStatus, AuditAction, ReportStatus, ModerationLevel, ModerationAction

Base = declarative_base()


class Submission(Base):
    """投稿模型"""
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 发送者信息
    sender_id = Column(String(20), nullable=False, index=True)
    sender_nickname = Column(String(100))
    receiver_id = Column(String(20), nullable=False, index=True)  # 接收账号
    group_name = Column(String(50), index=True)  # 账号组名称
    
    # 内容
    raw_content = Column(JSON)  # 原始消息内容
    processed_content = Column(JSON)  # 处理后的内容
    llm_result = Column(JSON)  # LLM处理结果
    rendered_images = Column(JSON)  # 渲染后的图片路径列表
    
    # 状态
    status = Column(String(20), default=SubmissionStatus.PENDING.value, index=True)
    is_anonymous = Column(Boolean, default=False)
    is_safe = Column(Boolean, default=True)
    is_complete = Column(Boolean, default=False)
    
    # 编号
    internal_id = Column(Integer)  # 内部编号
    publish_id = Column(Integer)  # 发布编号
    
    # 审核信息
    comment = Column(Text)  # 管理员评论
    rejection_reason = Column(Text)  # 拒绝原因
    processed_by = Column(String(50))  # 处理管理员用户名
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    processed_at = Column(DateTime)
    published_at = Column(DateTime)
    
    # 关联
    audit_logs = relationship("AuditLog", back_populates="submission", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_sender_receiver', 'sender_id', 'receiver_id'),
        Index('idx_status_created', 'status', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_nickname': self.sender_nickname,
            'receiver_id': self.receiver_id,
            'group_name': self.group_name,
            'status': self.status,
            'is_anonymous': self.is_anonymous,
            'is_safe': self.is_safe,
            'is_complete': self.is_complete,
            'internal_id': self.internal_id,
            'publish_id': self.publish_id,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
        }


class AuditLog(Base):
    """审核日志"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False, index=True)
    operator_id = Column(String(20), nullable=False)  # 操作员ID
    action = Column(String(20), nullable=False)  # 操作类型
    comment = Column(Text)  # 操作说明
    extra_data = Column(JSON)  # 额外数据
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    submission = relationship("Submission", back_populates="audit_logs")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'operator_id': self.operator_id,
            'action': self.action,
            'comment': self.comment,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BlackList(Base):
    """黑名单"""
    __tablename__ = 'blacklist'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), nullable=False)
    group_name = Column(String(50), nullable=False)  # 在哪个组被拉黑
    reason = Column(Text)  # 拉黑原因
    operator_id = Column(String(20))  # 操作员
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)  # 过期时间，NULL表示永久
    
    # 唯一约束
    __table_args__ = (
        Index('idx_user_group', 'user_id', 'group_name', unique=True),
    )
    
    def is_active(self) -> bool:
        """检查是否仍在黑名单中"""
        if self.expires_at is None:
            return True
        return datetime.now() < self.expires_at


class StoredPost(Base):
    """暂存的待发送投稿"""
    __tablename__ = 'stored_posts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    group_name = Column(String(50), nullable=False, index=True)
    publish_id = Column(Integer, nullable=False)  # 发布编号
    priority = Column(Integer, default=0)  # 优先级
    scheduled_time = Column(DateTime)  # 计划发送时间
    pending_platforms = Column(JSON)  # 待发布的平台列表（独立模式：每个平台独立清理）
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'group_name': self.group_name,
            'publish_id': self.publish_id,
            'priority': self.priority,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'pending_platforms': self.pending_platforms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MessageCache(Base):
    """消息缓存（用于处理多条消息的投稿）"""
    __tablename__ = 'message_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String(20), nullable=False, index=True)
    receiver_id = Column(String(20), nullable=False, index=True)
    message_id = Column(String(50))  # 消息ID
    message_content = Column(JSON)  # 消息内容
    message_time = Column(Float)  # 消息时间戳
    created_at = Column(DateTime, default=datetime.now)
    
    # 索引
    __table_args__ = (
        Index('idx_sender_receiver_cache', 'sender_id', 'receiver_id'),
        Index('idx_message_time', 'message_time'),
    )


class PublishRecord(Base):
    """发布记录"""
    __tablename__ = 'publish_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_ids = Column(JSON)  # 包含的投稿ID列表
    platform = Column(String(20), nullable=False)  # 发布平台
    account_id = Column(String(20), nullable=False)  # 发布账号
    group_name = Column(String(50))
    
    # 发布信息
    publish_content = Column(Text)  # 发布的文本内容
    publish_images = Column(JSON)  # 发布的图片列表
    publish_result = Column(JSON)  # 发布结果（如返回的ID等）
    
    # 状态
    is_success = Column(Boolean, default=False)
    error_message = Column(Text)
    
    # 时间
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'submission_ids': self.submission_ids,
            'platform': self.platform,
            'account_id': self.account_id,
            'group_name': self.group_name,
            'is_success': self.is_success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """管理后台用户"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)

    # 角色标识
    is_admin = Column(Boolean, default=False, index=True)
    is_superadmin = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'is_admin': self.is_admin,
            'is_superadmin': self.is_superadmin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class InviteToken(Base):
    """邀请注册链接令牌"""
    __tablename__ = 'invite_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    used_by_user_id = Column(Integer, ForeignKey('users.id'))
    expires_at = Column(DateTime)
    used_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    # 使用次数限制：若为空则兼容旧逻辑（单次使用，以 used_at 判定）
    max_uses = Column(Integer)
    uses_count = Column(Integer, default=0)

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        # 过期校验
        if self.expires_at is not None and not (datetime.now() < self.expires_at):
            return False
        # 兼容旧数据：未设置 max_uses 时，沿用 used_at 单次使用逻辑
        if self.max_uses is None:
            return self.used_at is None
        # 新逻辑：未达到最大使用次数
        current_uses = self.uses_count or 0
        return current_uses < (self.max_uses or 1)


class AdminProfile(Base):
    """管理员扩展信息

    用于为后台用户提供角色、权限、备注及最后登录时间等扩展字段，
    不改变核心 `users` 表结构，兼容既有流程。
    """
    __tablename__ = 'admin_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True, index=True)

    # 展示/权限信息
    nickname = Column(String(100))
    role = Column(String(20), default='admin', index=True)  # admin | senior_admin | super_admin
    permissions = Column(JSON)  # list[str]
    notes = Column(Text)

    # 审计信息
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Feedback(Base):
    """用户反馈"""
    __tablename__ = 'feedbacks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), nullable=False, index=True)  # 反馈者 QQ 号
    receiver_id = Column(String(20), nullable=False)  # 接收账号
    group_name = Column(String(50), index=True)  # 账号组名称
    content = Column(Text, nullable=False)  # 反馈内容
    status = Column(String(20), default='pending', index=True)  # pending | read | resolved
    admin_reply = Column(Text)  # 管理员回复
    replied_by = Column(String(50))  # 回复管理员
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    replied_at = Column(DateTime)  # 回复时间
    
    # 索引
    __table_args__ = (
        Index('idx_feedback_user', 'user_id', 'created_at'),
        Index('idx_feedback_status', 'status', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'receiver_id': self.receiver_id,
            'group_name': self.group_name,
            'content': self.content,
            'status': self.status,
            'admin_reply': self.admin_reply,
            'replied_by': self.replied_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
        }


class Report(Base):
    """举报记录"""
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False, index=True)
    reporter_id = Column(String(20), nullable=False, index=True)  # 举报者 QQ 号
    receiver_id = Column(String(20), nullable=False)  # 接收账号
    group_name = Column(String(50), index=True)  # 账号组名称
    reason = Column(Text)  # 举报理由
    status = Column(String(20), default=ReportStatus.PENDING.value, index=True)
    
    # AI 审核结果
    ai_level = Column(String(20))  # AI 评级: safe/warning/danger
    ai_reason = Column(Text)  # AI 评级理由
    ai_processed_at = Column(DateTime)
    
    # 人工审核结果
    manual_action = Column(String(20))  # 人工处理动作
    manual_reason = Column(Text)  # 人工处理理由
    processed_by = Column(String(50))  # 处理人（LLM 或管理员用户名）
    processed_at = Column(DateTime)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联
    submission = relationship("Submission", backref="reports")
    
    # 索引
    __table_args__ = (
        Index('idx_report_status', 'status', 'created_at'),
        Index('idx_report_submission', 'submission_id', 'status'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'reporter_id': self.reporter_id,
            'receiver_id': self.receiver_id,
            'group_name': self.group_name,
            'reason': self.reason,
            'status': self.status,
            'ai_level': self.ai_level,
            'ai_reason': self.ai_reason,
            'ai_processed_at': self.ai_processed_at.isoformat() if self.ai_processed_at else None,
            'manual_action': self.manual_action,
            'manual_reason': self.manual_reason,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PlatformComment(Base):
    """平台评论记录"""
    __tablename__ = 'platform_comments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False, index=True)
    platform = Column(String(20), nullable=False)  # 平台名称
    comment_id = Column(String(100))  # 平台评论 ID
    author_id = Column(String(100))  # 评论者 ID
    author_name = Column(String(100))  # 评论者昵称
    content = Column(Text)  # 评论内容
    created_at = Column(DateTime, default=datetime.now)
    fetched_at = Column(DateTime, default=datetime.now)  # 抓取时间
    
    # 关联
    submission = relationship("Submission", backref="platform_comments")
    
    # 索引
    __table_args__ = (
        Index('idx_platform_comment', 'submission_id', 'platform'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'platform': self.platform,
            'comment_id': self.comment_id,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
        }