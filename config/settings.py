"""配置管理"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class SystemConfig(BaseModel):
    """系统配置"""

    debug: bool = False

    log_level: str = "INFO"

    data_dir: str = "./data"

    cache_dir: str = "./data/cache"


class ServerConfig(BaseModel):
    """服务器配置"""

    host: str = "0.0.0.0"

    port: int = 8082

    workers: int = 4


class DatabaseConfig(BaseModel):
    """数据库配置"""

    type: str = "sqlite"

    url: str = "sqlite+aiosqlite:///./data/graffito.db"

    pool_size: int = 10


class CacheConfig(BaseModel):
    """统一缓存配置 (基于 aiocache)
    
    支持三种后端:
    - memory: 本地内存缓存 (SimpleMemoryCache)
    - redis: Redis 缓存 (RedisCache)
    - memcached: Memcached 缓存 (MemcachedCache)
    """
    
    # 缓存后端类型: memory | redis | memcached
    backend: str = "memory"
    
    # 序列化器: null | string | json | pickle | msgpack
    serializer: str = "json"
    
    # 命名空间（键前缀）
    namespace: str = "graffito"
    
    # 默认 TTL（秒）
    ttl: int = 300
    
    # 操作超时（秒）
    timeout: int = 5
    
    # === Redis 后端配置 (backend=redis 时生效) ===
    redis_endpoint: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_pool_size: int = 50
    
    # === Memcached 后端配置 (backend=memcached 时生效) ===
    memcached_endpoint: str = "127.0.0.1"
    memcached_port: int = 11211
    memcached_pool_size: int = 2
    
    # === 业务配置 ===
    # 消息缓存过期时间（秒）
    message_cache_ttl: int = 7200
    
    # 分布式锁超时（秒）
    lock_timeout: int = 30


class QueueMySQLConfig(BaseModel):
    host: str = "localhost"

    port: int = 3306

    user: str = "root"

    password: str = ""

    database: str = "graffito_queue"

    table: str = "graffito_tasks"


class QueueConfig(BaseModel):
    """任务队列配置

    backend: AsyncSQLiteQueue | AsyncQueue | MySQLQueue

    path: 本地队列目录（用于 Async* 后端）

    mysql: MySQL 连接参数（用于 MySQLQueue）

    """

    backend: str = "AsyncSQLiteQueue"

    path: str = "data/queues"

    mysql: QueueMySQLConfig = QueueMySQLConfig()


class RateLimitConfig(BaseModel):
    """Web API 限流配置"""

    enabled: bool = False
    default: Optional[str] = "120/minute"
    login: Optional[str] = "10/minute"
    register_invite: Optional[str] = "5/hour"
    create_invite: Optional[str] = "20/hour"
    init_superadmin: Optional[str] = "2/hour"
    storage_uri: Optional[str] = None
    trust_forwarded_for: bool = True


class WebConfig(BaseModel):
    """Web 后端配置"""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8083
    # 简化 CORS：可仅设置前端域名（含协议与端口），例如 "http://localhost:5173"
    frontend_origin: Optional[str] = None
    jwt_secret_key: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 12 * 60
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit: RateLimitConfig = RateLimitConfig()


class LLMConfig(BaseModel):
    """LLM配置"""

    api_key: Optional[str] = None

    # OpenAI 兼容接口地址（如使用代理/自建服务可修改）
    base_url: Optional[str] = "https://api.openai.com/v1"

    text_model: str = "gpt-4o-mini"

    vision_model: str = "gpt-4o-mini"

    timeout: int = 30

    max_retry: int = 3

    @validator('api_key', pre=True)
    def get_api_key_from_env(cls, v):
        """从环境变量获取API密钥"""

        if v and v.startswith('${') and v.endswith('}'):
            env_var = v[2:-1]

            return os.getenv(env_var)

        return v

    @validator('base_url', pre=True)
    def get_base_url_from_env(cls, v):
        """支持从环境变量读取 base_url（例如 ${OPENAI_BASE_URL}）"""

        if isinstance(v, str) and v.startswith('${') and v.endswith('}'):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class ProcessingConfig(BaseModel):
    """处理配置"""

    wait_time: int = 120

    max_concurrent: int = 10


class RenderingConfig(BaseModel):
    """渲染配置"""
    
    # 自定义字体族，支持多个字体回退
    font_family: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif"
    
    # 渲染后端类型: local (本地 Playwright) | remote (独立渲染服务) | cloudflare (Cloudflare Browser Rendering)
    backend: str = "local"
    
    # 渲染后端配置
    backend_config: Dict[str, Any] = Field(default_factory=dict)
    
    # 静态资源基础 URL (可以是本地路径或远程 URL)
    # 例如: "file:///path/to/static" 或 "https://raw.githubusercontent.com/user/repo/branch"
    static_base_url: str = "file://./static"


 


class QQReceiverConfig(BaseModel):
    """QQ接收器配置"""

    enabled: bool = True

    auto_accept_friend: bool = True

    friend_request_window: int = 300

    friend_accept_delay_min: int = 180

    friend_accept_delay_max: int = 240

    # NoneBot/OneBot v11 访问令牌（可选，用于反向WS/HTTP鉴权）

    access_token: Optional[str] = None

    @validator("friend_accept_delay_min", "friend_accept_delay_max")
    def _validate_friend_accept_delay_non_negative(cls, value):

        if value < 0:
            raise ValueError("friend_accept_delay_* 必须大于等于 0")

        return value

    @validator("friend_accept_delay_max")
    def _validate_friend_accept_delay_range(cls, value, values):

        min_value = values.get("friend_accept_delay_min")

        if min_value is not None and value < min_value:
            raise ValueError("friend_accept_delay_max 不能小于 friend_accept_delay_min")

        return value


class QzonePublisherConfig(BaseModel):
    """QQ空间发送器配置"""

    enabled: bool = True

    # 驱动选择：aioqzone（默认，基于 aioqzone H5）| ooqzone（兼容旧实现）

    driver: str = "aioqzone"

    max_attempts: int = 3

    batch_size: int = 30

    max_images_per_post: int = 9

    send_schedule: List[str] = Field(default_factory=list)

    # 新增控制项

    publish_text: bool = True  # 是否发布文本（否则仅发图）

    include_publish_id: bool = True  # 是否在文本中包含发布编号

    include_at_sender: bool = True  # 是否@投稿人

    image_source: str = "rendered"  # rendered|chat|both

    include_segments: bool = True  # 是否在文本中包含聊天分段内容


class BilibiliPublisherConfig(BaseModel):
    """B站发送器配置"""

    enabled: bool = False

    max_attempts: int = 3

    batch_size: int = 30

    max_images_per_post: int = 9

    send_schedule: List[str] = Field(default_factory=list)

    # 发布控制（与通用字段对齐，便于基类使用）

    publish_text: bool = True

    include_publish_id: bool = True

    include_at_sender: bool = False  # B站@需要 at_uids，默认关闭

    image_source: str = "rendered"  # rendered|chat|both

    include_segments: bool = False

    # 账号 cookies 配置：{"account_id": {"cookie_file": "..."}}

    accounts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RedNotePublisherConfig(BaseModel):
    """小红书发送器配置"""

    enabled: bool = False

    max_attempts: int = 3

    batch_size: int = 20

    max_images_per_post: int = 9

    send_schedule: List[str] = Field(default_factory=list)

    # 发布控制

    publish_text: bool = True

    include_publish_id: bool = False

    include_at_sender: bool = False

    image_source: str = "rendered"  # rendered|chat|both

    include_segments: bool = False

    # 账号 cookies 配置：{"account_id": {"cookie_file": "..."}}

    accounts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Playwright 配置

    headless: bool = True

    slow_mo_ms: int = 0

    user_agent: Optional[str] = None


class AuditConfig(BaseModel):
    """审核配置"""

    auto_approve: bool = False

    ai_safety_check: bool = True

    sensitive_words: List[str] = Field(default_factory=list)

    # 当图片原始大小超过该阈值（单位：MB）时，跳过 AI 安全检测与描述生成；0 或负值表示不跳过
    skip_image_audit_over_mb: float = 0.0


class ChiselConfig(BaseModel):
    """Chisel 举报审核配置"""

    enable: bool = True

    auto_delete: bool = True

    auto_pass: bool = True

    fetch_comments: bool = True

    comment_fetch_limit: int = 50


class AccountInfo(BaseModel):
    """账号信息"""

    qq_id: str

    http_port: int

    # Napcat HTTP 服务端地址（可选，默认 127.0.0.1，支持配置远程 NapCat 服务器）

    http_host: str = "127.0.0.1"

    # Napcat HTTP 服务端 Token（可选，用于访问 Napcat 本地 HTTP 接口）

    http_token: Optional[str] = None


class AccountGroup(BaseModel):
    """账号组配置"""

    name: str

    manage_group_id: str

    main_account: AccountInfo

    minor_accounts: List[AccountInfo] = Field(default_factory=list)

    max_post_stack: int = 1

    watermark_text: str = ""

    wall_mark: str = ""

    # 好友添加成功后的欢迎消息（支持多行文本，使用 | 符号表示多行）
    friend_add_message: str = "你好，欢迎投稿"

    # 快捷回复配置（关键词 -> 回复内容）
    quick_replies: Dict[str, str] = Field(default_factory=dict)

    # 是否启用 #评论 指令（投稿者可私聊追加评论到已发布平台）
    # 如果为 True，评论时不暴露投稿者身份到外部平台（内部审核日志可见）
    allow_anonymous_comment: bool = True


class Settings(BaseSettings):
    """全局配置"""

    system: SystemConfig = SystemConfig()

    server: ServerConfig = ServerConfig()

    database: DatabaseConfig = DatabaseConfig()

    cache: CacheConfig = CacheConfig()

    queue: QueueConfig = QueueConfig()
    web: WebConfig = WebConfig()

    llm: LLMConfig = LLMConfig()

    processing: ProcessingConfig = ProcessingConfig()

    rendering: RenderingConfig = RenderingConfig()

    receivers: Dict[str, Any] = Field(default_factory=dict)

    publishers: Dict[str, Any] = Field(default_factory=dict)

    audit: AuditConfig = AuditConfig()

    chisel: ChiselConfig = ChiselConfig()

    account_groups: Dict[str, AccountGroup] = Field(default_factory=dict)

    class Config:

        env_file = ".env"

        env_file_encoding = "utf-8"

    @classmethod
    def from_yaml(cls, yaml_file: str = "config/config.yaml") -> "Settings":

        """从YAML文件加载配置"""

        yaml_path = Path(yaml_file)

        if not yaml_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {yaml_file}")

        with open(yaml_path, 'r', encoding='utf-8') as f:

            data = yaml.safe_load(f)

        # 处理环境变量替换

        data = cls._replace_env_vars(data)

        # 特殊处理接收器和发送器配置

        if 'receivers' in data:

            if 'qq' in data['receivers']:
                data['receivers']['qq'] = QQReceiverConfig(**data['receivers']['qq'])

        if 'publishers' in data:

            # Accept raw dict first; schema validation will happen inside each publisher if needed

            try:

                if 'qzone' in data['publishers']:
                    data['publishers']['qzone'] = QzonePublisherConfig(**data['publishers']['qzone'])

                if 'bilibili' in data['publishers']:
                    data['publishers']['bilibili'] = BilibiliPublisherConfig(**data['publishers']['bilibili'])

                if 'rednote' in data['publishers']:
                    data['publishers']['rednote'] = RedNotePublisherConfig(**data['publishers']['rednote'])

            except Exception:

                # If per-publisher schema fails, keep raw dicts; dynamic overrides may supply valid fields

                pass

        # 处理账号组配置

        if 'account_groups' in data:

            account_groups = {}

            for key, value in data['account_groups'].items():

                if 'main_account' in value:
                    value['main_account'] = AccountInfo(**value['main_account'])

                if 'minor_accounts' in value:
                    value['minor_accounts'] = [AccountInfo(**acc) for acc in value['minor_accounts']]

                account_groups[key] = AccountGroup(**value)

            data['account_groups'] = account_groups

        return cls(**data)

    @staticmethod
    def _replace_env_vars(data: Any) -> Any:

        """递归替换环境变量"""

        if isinstance(data, dict):

            return {k: Settings._replace_env_vars(v) for k, v in data.items()}

        elif isinstance(data, list):

            return [Settings._replace_env_vars(item) for item in data]

        elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):

            env_var = data[2:-1]

            return os.getenv(env_var, data)

        return data

    def save_yaml(self, yaml_file: str = "config/config.yaml"):

        """保存配置到YAML文件"""

        data = self.dict()

        yaml_path = Path(yaml_file)

        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置（单例）"""

    try:

        return Settings.from_yaml()

    except FileNotFoundError:

        # 如果配置文件不存在，创建默认配置

        settings = Settings()

        settings.save_yaml()

        return settings
