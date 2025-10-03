"""枚举类型定义"""
from enum import Enum


class SubmissionStatus(str, Enum):
    """投稿状态"""
    PENDING = "pending"          # 待处理
    PROCESSING = "processing"    # 处理中
    WAITING = "waiting"          # 等待审核
    APPROVED = "approved"        # 已通过
    REJECTED = "rejected"        # 已拒绝
    DELETED = "deleted"          # 已删除
    PUBLISHED = "published"      # 已发布
    

class AuditAction(str, Enum):
    """审核动作"""
    APPROVE = "approve"              # 通过
    REJECT = "reject"                # 拒绝
    DELETE = "delete"                # 删除
    HOLD = "hold"                    # 暂缓
    TOGGLE_ANONYMOUS = "toggle_anon" # 切换匿名
    COMMENT = "comment"              # 评论
    BLACKLIST = "blacklist"          # 拉黑
    IMMEDIATE_SEND = "immediate"     # 立即发送
    REFRESH = "refresh"              # 刷新
    RERENDER = "rerender"           # 重新渲染
    

class MessageType(str, Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    VOICE = "voice"
    EMOJI = "emoji"
    FORWARD = "forward"
    MIXED = "mixed"
    

class PublishPlatform(str, Enum):
    """发布平台"""
    QZONE = "qzone"       # QQ空间
    QQ_GROUP = "qq_group" # QQ群
    BILIBILI = "bilibili" # B站
    WEIBO = "weibo"       # 微博
    REDNOTE = "rednote"   # 小红书


class ReportStatus(str, Enum):
    """举报状态"""
    PENDING = "pending"           # 待处理
    AI_PROCESSING = "ai_processing"  # AI 处理中
    MANUAL_REVIEW = "manual_review"  # 人工审核中
    RESOLVED = "resolved"         # 已处理
    REJECTED = "rejected"         # 已驳回


class ModerationLevel(str, Enum):
    """审核等级"""
    SAFE = "safe"           # 安全
    WARNING = "warning"     # 警告
    DANGER = "danger"       # 危险


class ModerationAction(str, Enum):
    """审核处理动作"""
    DELETE = "delete"       # 删除
    KEEP = "keep"           # 保留
    AUTO_DELETE = "auto_delete"  # 自动删除
    AUTO_PASS = "auto_pass"      # 自动通过