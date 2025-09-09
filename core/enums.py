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
