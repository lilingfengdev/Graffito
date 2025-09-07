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
    url: str = "sqlite+aiosqlite:///./data/oqqwall.db"
    pool_size: int = 10
    
class RedisConfig(BaseModel):
    """Redis配置"""
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    
class LLMConfig(BaseModel):
    """LLM配置"""
    provider: str = "dashscope"
    api_key: Optional[str] = None
    text_model: str = "qwen-plus-latest"
    vision_model: str = "qwen-vl-max-latest"
    timeout: int = 30
    max_retry: int = 3
    
    @validator('api_key', pre=True)
    def get_api_key_from_env(cls, v):
        """从环境变量获取API密钥"""
        if v and v.startswith('${') and v.endswith('}'):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v
    
class ProcessingConfig(BaseModel):
    """处理配置"""
    wait_time: int = 120
    max_concurrent: int = 10
    
class QQReceiverConfig(BaseModel):
    """QQ接收器配置"""
    enabled: bool = True
    auto_accept_friend: bool = True
    friend_request_window: int = 300
    # NoneBot/OneBot v11 访问令牌（可选，用于反向WS/HTTP鉴权）
    access_token: Optional[str] = None
    
class QzonePublisherConfig(BaseModel):
    """QQ空间发送器配置"""
    enabled: bool = True
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

class AuditConfig(BaseModel):
    """审核配置"""
    auto_approve: bool = False
    ai_safety_check: bool = True
    sensitive_words: List[str] = Field(default_factory=list)
    
class AccountInfo(BaseModel):
    """账号信息"""
    qq_id: str
    http_port: int
    # Napcat HTTP 服务端 Token（可选，用于访问 Napcat 本地 HTTP 接口）
    http_token: Optional[str] = None
    
class AccountGroup(BaseModel):
    """账号组配置"""
    name: str
    manage_group_id: str
    main_account: AccountInfo
    minor_accounts: List[AccountInfo] = Field(default_factory=list)
    max_post_stack: int = 1
    max_images_per_post: int = 30
    send_schedule: List[str] = Field(default_factory=list)
    watermark_text: str = ""
    wall_mark: str = ""
    friend_add_message: str = "你好，欢迎投稿"
    quick_replies: Dict[str, str] = Field(default_factory=dict)
    # 是否允许匿名评论（私聊 #评论 指令的操作者在审核日志中匿名记录）
    allow_anonymous_comment: bool = True
    
class Settings(BaseSettings):
    """全局配置"""
    system: SystemConfig = SystemConfig()
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    llm: LLMConfig = LLMConfig()
    processing: ProcessingConfig = ProcessingConfig()
    receivers: Dict[str, Any] = Field(default_factory=dict)
    publishers: Dict[str, Any] = Field(default_factory=dict)
    audit: AuditConfig = AuditConfig()
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
            if 'qzone' in data['publishers']:
                data['publishers']['qzone'] = QzonePublisherConfig(**data['publishers']['qzone'])
            if 'bilibili' in data['publishers']:
                data['publishers']['bilibili'] = BilibiliPublisherConfig(**data['publishers']['bilibili'])
                
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
