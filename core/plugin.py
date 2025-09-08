"""插件基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from loguru import logger

from config import Settings


class Plugin(ABC):
    """插件基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.logger = logger.bind(plugin=name)
        
    @abstractmethod
    async def initialize(self):
        """初始化插件"""
        pass
        
    @abstractmethod
    async def shutdown(self):
        """关闭插件"""
        pass
        
    @property
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self.enabled
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)


class ReceiverPlugin(Plugin):
    """接收器插件基类"""
    
    @abstractmethod
    async def start(self):
        """启动接收器"""
        pass
        
    @abstractmethod
    async def stop(self):
        """停止接收器"""
        pass
        
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]):
        """处理接收到的消息"""
        pass
        
    @abstractmethod
    async def handle_friend_request(self, request: Dict[str, Any]):
        """处理好友请求"""
        pass
        
    @abstractmethod
    async def send_private_message(self, user_id: str, message: str) -> bool:
        """发送私聊消息"""
        pass
        
    @abstractmethod
    async def send_group_message(self, group_id: str, message: str) -> bool:
        """发送群消息"""
        pass


class PublisherPlugin(Plugin):
    """发送器插件基类"""
    
    @abstractmethod
    async def publish(self, content: str, images: List[str] = None, **kwargs) -> Dict[str, Any]:
        """发布内容
        
        Args:
            content: 文本内容
            images: 图片路径列表
            **kwargs: 其他参数
            
        Returns:
            发布结果，包含成功状态和返回信息
        """
        pass
        
    @abstractmethod
    async def batch_publish(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量发布
        
        Args:
            items: 发布项列表，每项包含content和images
            
        Returns:
            发布结果列表
        """
        pass
        
    @abstractmethod
    async def check_login_status(self) -> bool:
        """检查登录状态"""
        pass


class ProcessorPlugin(Plugin):
    """处理器插件基类"""
    
    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据
        
        Args:
            data: 输入数据
            
        Returns:
            处理后的数据
        """
        pass


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.receivers: Dict[str, ReceiverPlugin] = {}
        self.publishers: Dict[str, PublisherPlugin] = {}
        self.processors: Dict[str, ProcessorPlugin] = {}
        
    def register(self, plugin: Plugin):
        """注册插件"""
        self.plugins[plugin.name] = plugin
        
        if isinstance(plugin, ReceiverPlugin):
            self.receivers[plugin.name] = plugin
        elif isinstance(plugin, PublisherPlugin):
            self.publishers[plugin.name] = plugin
        elif isinstance(plugin, ProcessorPlugin):
            self.processors[plugin.name] = plugin
            
        logger.info(f"插件已注册: {plugin.name}")
        
    def unregister(self, name: str):
        """注销插件"""
        if name in self.plugins:
            plugin = self.plugins.pop(name)
            
            if name in self.receivers:
                del self.receivers[name]
            elif name in self.publishers:
                del self.publishers[name]
            elif name in self.processors:
                del self.processors[name]
                
            logger.info(f"插件已注销: {name}")
            
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """获取插件"""
        return self.plugins.get(name)
        
    def get_receiver(self, name: str) -> Optional[ReceiverPlugin]:
        """获取接收器"""
        return self.receivers.get(name)
        
    def get_publisher(self, name: str) -> Optional[PublisherPlugin]:
        """获取发送器"""
        return self.publishers.get(name)
        
    def get_processor(self, name: str) -> Optional[ProcessorPlugin]:
        """获取处理器"""
        return self.processors.get(name)
        
    async def initialize_all(self):
        """初始化所有插件"""
        for plugin in self.plugins.values():
            if plugin.is_enabled:
                try:
                    await plugin.initialize()
                    logger.info(f"插件初始化成功: {plugin.name}")
                except Exception as e:
                    logger.error(f"插件初始化失败 {plugin.name}: {e}")
                    
    async def shutdown_all(self):
        """关闭所有插件"""
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
                logger.info(f"插件已关闭: {plugin.name}")
            except Exception as e:
                logger.error(f"插件关闭失败 {plugin.name}: {e}")
                
    def list_plugins(self) -> Dict[str, List[str]]:
        """列出所有插件"""
        return {
            'all': list(self.plugins.keys()),
            'receivers': list(self.receivers.keys()),
            'publishers': list(self.publishers.keys()),
            'processors': list(self.processors.keys()),
        }


# 全局插件管理器
plugin_manager = PluginManager()
