#!/usr/bin/env python3
"""
OQQWall-Python 主程序入口
"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# 配置日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "data/logs/oqqwall_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG"
)

from config import get_settings
from core.database import get_db, close_db
from core.plugin import plugin_manager

# 导入插件
from receivers.qq import QQReceiver
from publishers.qzone import QzonePublisher
from publishers.bilibili import BilibiliPublisher
from publishers.rednote import RedNotePublisher

# 导入服务
from services import AuditService, SubmissionService, NotificationService


class OQQWallApp:
    """主应用程序"""
    
    def __init__(self):
        self.settings = get_settings()
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 服务实例
        self.audit_service = AuditService()
        self.submission_service = SubmissionService()
        self.notification_service = NotificationService()
        
    async def initialize(self):
        """初始化应用"""
        logger.info("正在初始化 OQQWall...")
        
        # 创建必要的目录
        Path("data").mkdir(exist_ok=True)
        Path("data/cache").mkdir(exist_ok=True)
        Path("data/cache/rendered").mkdir(exist_ok=True)
        Path("data/cache/numb").mkdir(exist_ok=True)
        Path("data/logs").mkdir(exist_ok=True)
        Path("data/cookies").mkdir(exist_ok=True)
        
        # 初始化数据库
        db = await get_db()
        if not await db.health_check():
            logger.error("数据库健康检查失败")
            return False
            
        # 注册插件
        await self.register_plugins()
        
        # 初始化所有插件
        await plugin_manager.initialize_all()
        
        # 初始化服务
        await self.audit_service.initialize()
        await self.submission_service.initialize()
        
        # 设置消息处理器
        self.setup_message_handlers()
        # 注入服务到接收器
        self.inject_services_into_receivers()
        
        logger.info("OQQWall 初始化完成")
        return True
        
    async def register_plugins(self):
        """注册插件"""
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
            
        # 注册QQ空间发送器
        if self.settings.publishers.get('qzone'):
            qzone_config = self.settings.publishers['qzone']
            if hasattr(qzone_config, 'model_dump'):
                qzone_config = qzone_config.model_dump()
            elif hasattr(qzone_config, 'dict'):
                qzone_config = qzone_config.dict()
            elif hasattr(qzone_config, '__dict__'):
                qzone_config = qzone_config.__dict__
                
            qzone_publisher = QzonePublisher(qzone_config)
            plugin_manager.register(qzone_publisher)
            logger.info("已注册 QQ空间 发送器")

        # 注册B站发送器
        if self.settings.publishers.get('bilibili'):
            bili_config = self.settings.publishers['bilibili']
            if hasattr(bili_config, 'model_dump'):
                bili_config = bili_config.model_dump()
            elif hasattr(bili_config, 'dict'):
                bili_config = bili_config.dict()
            elif hasattr(bili_config, '__dict__'):
                bili_config = bili_config.__dict__

            if bili_config.get('enabled'):
                bili_publisher = BilibiliPublisher(bili_config)
                plugin_manager.register(bili_publisher)
                logger.info("已注册 Bilibili 发送器")

        # 注册小红书发送器
        if self.settings.publishers.get('rednote'):
            rn_config = self.settings.publishers['rednote']
            if hasattr(rn_config, 'model_dump'):
                rn_config = rn_config.model_dump()
            elif hasattr(rn_config, 'dict'):
                rn_config = rn_config.dict()
            elif hasattr(rn_config, '__dict__'):
                rn_config = rn_config.__dict__

            if rn_config.get('enabled'):
                rednote_publisher = RedNotePublisher(rn_config)
                plugin_manager.register(rednote_publisher)
                logger.info("已注册 小红书 发送器")
            
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
            # 通过投稿服务处理
            await self.submission_service.process_submission(submission.id)
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
        logger.info("正在启动 OQQWall...")
        
        # 启动所有接收器
        for name, receiver in plugin_manager.receivers.items():
            if receiver.is_enabled:
                await receiver.start()
                logger.info(f"已启动接收器: {name}")
                
        logger.info("OQQWall 已启动")
        
        # 等待关闭信号
        await self.shutdown_event.wait()
        
    async def stop(self):
        """停止应用"""
        if not self.is_running:
            return

        logger.info("正在停止 OQQWall...")
        self.is_running = False

        # 停止所有接收器
        for name, receiver in plugin_manager.receivers.items():
            await receiver.stop()
            logger.info(f"已停止接收器: {name}")

        # 关闭所有插件
        await plugin_manager.shutdown_all()

        # 关闭服务
        await self.audit_service.shutdown()
        await self.submission_service.shutdown()

        # 关闭数据库
        await close_db()

        logger.info("OQQWall 已停止")
        
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
║          OQQWall-Python 重构版            ║
║         校园墙自动运营系统 v2.0           ║
╚═══════════════════════════════════════════╝
    """)
    
    app = OQQWallApp()
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
