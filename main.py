#!/usr/bin/env python3
"""
Graffito 主程序入口
"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional
import nest_asyncio
from loguru import logger

# 修补 asyncio
nest_asyncio.apply()
# 配置日志
logger.remove()  # 移除默认处理器
# 控制台日志处理器
console_handler_id = logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
# 文件日志处理器
file_handler_id = logger.add(
    "data/logs/graffito_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)

# 设置全局标志，用于其他模块检查是否需要重新配置日志
import os
os.environ["GRAFFITO_LOG_CONFIGURED"] = "true"

from config import get_settings
from core.database import get_db, close_db
from core.cache_client import get_cache, close_cache
from core.plugin import plugin_manager


class GraffitoApp:
    """主应用程序"""
    
    def __init__(self):
        self.settings = get_settings()
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 延迟导入服务，避免启动时加载所有模块
        self.audit_service = None
        self.submission_service = None
        self.notification_service = None
        # Web 服务
        self.web_server = None
        self.web_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """初始化应用"""
        logger.info("正在初始化 Graffito...")
        
        # 创建必要的目录
        Path("data").mkdir(exist_ok=True)
        Path("data/cache").mkdir(exist_ok=True)
        Path("data/cache/rendered").mkdir(exist_ok=True)
        Path("data/cache/numb").mkdir(exist_ok=True)
        Path("data/logs").mkdir(exist_ok=True)
        Path("data/cookies").mkdir(exist_ok=True)
        
        # 并行初始化数据库、缓存和注册插件
        db_task = asyncio.create_task(self._init_database())
        cache_task = asyncio.create_task(self._init_cache())
        plugin_task = asyncio.create_task(self.register_plugins())
        
        # 等待数据库、缓存和插件注册完成
        db_ok, cache_ok, _ = await asyncio.gather(db_task, cache_task, plugin_task)
        if not db_ok:
            logger.error("数据库健康检查失败")
            return False
        if not cache_ok:
            logger.warning("缓存初始化失败，将降级到数据库存储")
        
        
        # 并行初始化插件和服务
        await asyncio.gather(
            plugin_manager.initialize_all(),
            self._init_services()
        )
        
        # 设置消息处理器
        self.setup_message_handlers()
        # 注入服务到接收器
        self.inject_services_into_receivers()
        
        # 检查 Chisel 状态
        if self.settings.chisel.enable:
            logger.info("Chisel 举报审核系统已启用")
            logger.info(f"  - 自动删除 danger 级别: {self.settings.chisel.auto_delete}")
            logger.info(f"  - 自动通过 safe 级别: {self.settings.chisel.auto_pass}")
            logger.info(f"  - 抓取平台评论: {self.settings.chisel.fetch_comments}")
        else:
            logger.info("Chisel 举报审核系统未启用")
        
        logger.info("Graffito 初始化完成")
        return True
    
    async def _init_database(self):
        """初始化数据库"""
        db = await get_db()
        return await db.health_check()
    
    async def _init_cache(self):
        """初始化缓存"""
        try:
            cache = await get_cache()
            logger.info(f"缓存客户端初始化成功: backend={cache.backend}, serializer={cache.serializer}")
            return True
        except Exception as e:
            logger.error(f"缓存初始化失败: {e}")
            return False
    
    async def _init_services(self):
        """初始化服务（延迟导入）"""
        from services import AuditService, SubmissionService, NotificationService
        
        self.audit_service = AuditService()
        self.submission_service = SubmissionService()
        self.notification_service = NotificationService()
        
        # 并行初始化服务
        await asyncio.gather(
            self.audit_service.initialize(),
            self.submission_service.initialize()
        )
        
    async def register_plugins(self):
        """注册插件（延迟导入）"""
        # 延迟导入插件
        from receivers.qq import QQReceiver
        from publishers.loader import register_publishers_from_configs
        
        # 注册QQ接收器
        if self.settings.receivers.get('qq'):
            qq_config = self.settings.receivers['qq']
            if hasattr(qq_config, 'model_dump'):
                qq_config = qq_config.model_dump()
            elif hasattr(qq_config, 'dict'):
                qq_config = qq_config.dict()
            elif hasattr(qq_config, '__dict__'):
                qq_config = qq_config.__dict__
                
            qq_receiver = QQReceiver(qq_config)
            plugin_manager.register(qq_receiver)
            logger.info("已注册 QQ 接收器")
            
        # 动态注册所有启用的发送器（仅依赖配置启用的目标模块）
        registered = register_publishers_from_configs()
        if registered:
            logger.info(f"已动态注册发送器: {list(registered.keys())}")
            
    def setup_message_handlers(self):
        """设置消息处理器"""
        # 设置QQ接收器的消息处理器
        qq_receiver = plugin_manager.get_receiver('qq_receiver')
        if qq_receiver:
            qq_receiver.set_message_handler(self.handle_message)
            qq_receiver.set_friend_request_handler(self.handle_friend_request)

    def inject_services_into_receivers(self):
        """将服务实例注入接收器（用于指令处理等场景）"""
        qq_receiver = plugin_manager.get_receiver('qq_receiver')
        if qq_receiver and hasattr(qq_receiver, 'set_services'):
            try:
                qq_receiver.set_services(
                    audit_service=self.audit_service,
                    submission_service=self.submission_service,
                    notification_service=self.notification_service
                )
            except Exception as e:
                logger.warning(f"注入服务到接收器失败: {e}")
            
    async def handle_message(self, submission):
        """处理收到的消息（投稿）"""
        try:
            # 通过投稿服务处理（后台任务，避免阻塞接收器与停机流程）
            asyncio.create_task(self.submission_service.process_submission(submission.id))
        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)
            
    async def handle_friend_request(self, request):
        """处理好友请求"""
        logger.info(f"收到好友请求: {request}")
        # 自动同意已在接收器中处理
            
    async def start(self):
        """启动应用"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("正在启动 Graffito...")
        
        # 启动所有接收器
        for name, receiver in plugin_manager.receivers.items():
            if receiver.is_enabled:
                await receiver.start()
                logger.info(f"已启动接收器: {name}")

        # 启动 Web 后端（可选）
        if getattr(self.settings, 'web', None) and self.settings.web.enabled:
            try:
                # 延迟导入 uvicorn 和 web 模块
                import uvicorn
                from web.backend import app as web_app_module
                
                web_app = web_app_module.app
                # Inject shared services so web reuses initialized pipeline
                try:
                    if hasattr(web_app_module, 'set_services'):
                        web_app_module.set_services(self.audit_service)
                except Exception as e:
                    logger.warning(f"注入服务到 Web 失败: {e}")
                web_cfg = uvicorn.Config(
                    web_app,
                    host=self.settings.web.host,
                    port=self.settings.web.port,
                    loop="asyncio",
                    lifespan="on",
                    log_level="info"
                )
                self.web_server = uvicorn.Server(web_cfg)
                self.web_task = asyncio.create_task(self.web_server.serve())
                logger.info(f"Web 后端已启动: http://{self.settings.web.host}:{self.settings.web.port}")
            except Exception as e:
                logger.error(f"启动 Web 后端失败: {e}")
                
        logger.info("Graffito 已启动")
        
        # 等待关闭信号
        await self.shutdown_event.wait()
        
    async def stop(self):
        """停止应用"""
        if not self.is_running:
            return

        logger.info("正在停止 Graffito...")
        self.is_running = False

        # 停止 Web 后端
        if self.web_server is not None:
            try:
                self.web_server.should_exit = True
                if self.web_task:
                    await self.web_task
            except Exception as e:
                logger.warning(f"停止 Web 后端失败: {e}")

        # 停止所有接收器
        for name, receiver in plugin_manager.receivers.items():
            await receiver.stop()
            logger.info(f"已停止接收器: {name}")

        # 关闭所有插件
        await plugin_manager.shutdown_all()

        # 关闭服务
        await self.audit_service.shutdown()
        await self.submission_service.shutdown()

        # 关闭缓存
        await close_cache()
        
        # 关闭数据库
        await close_db()

        logger.info("Graffito 已停止")
        
    def handle_signal(self, sig):
        """处理系统信号"""
        logger.info(f"收到信号: {sig}")
        self.shutdown_event.set()
        
    async def run(self):
        """运行应用"""
        # 初始化
        if not await self.initialize():
            logger.error("初始化失败")
            return
            
        # 设置信号处理
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: self.handle_signal(s)
                )
        else:
            # Windows 不支持 loop.add_signal_handler，使用同步 signal.signal
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    signal.signal(sig, lambda s, f: self.handle_signal(s))
                except Exception as e:
                    logger.warning(f"设置 Windows 信号处理器失败: {e}")
            
        try:
            # 启动应用
            await self.start()
        except Exception as e:
            logger.error(f"运行时错误: {e}", exc_info=True)
        finally:
            # 停止应用
            await self.stop()


async def main():
    """主函数"""
    logger.info("""
╔═══════════════════════════════════════════╗
║               Graffito                    ║
║         校园墙自动运营系统                    ║
╚═══════════════════════════════════════════╝
    """)
    
    app = GraffitoApp()
    await app.run()


if __name__ == "__main__":
    # Windows系统信号兼容
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception as e:
            logger.warning(f"设置 Windows Proactor 事件循环策略失败: {e}")
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
