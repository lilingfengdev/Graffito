"""基于 NoneBot2 的 QQ 接收器实现"""
import asyncio
import time
from typing import Dict, Any, Optional

from loguru import logger
from uvicorn import Server, Config

import nonebot
from nonebot import on_message, on_request
from nonebot.adapters.onebot.v11 import (
    Adapter as OneBotV11Adapter,
    Bot,
    MessageEvent,
    PrivateMessageEvent,
    GroupMessageEvent,
    FriendRequestEvent,
)

from receivers.base import BaseReceiver
from core.database import get_db
from core.models import MessageCache, BlackList
from sqlalchemy import select, and_  # type: ignore


class QQReceiver(BaseReceiver):
    """QQ 接收器（NoneBot2 + OneBot v11）"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("qq_receiver", config)
        self.app = None
        self.server: Optional[Server] = None
        self.friend_request_cache: Dict[str, float] = {}
        self.suppression_cache: Dict[str, list] = {}

    async def initialize(self):
        await super().initialize()

        # 初始化 NoneBot（注入 OneBot 鉴权配置）
        access_token = self.config.get("access_token")
        if access_token:
            try:
                import os
                # 常见环境变量名，尽量兼容
                os.environ.setdefault("ONEBOT_ACCESS_TOKEN", str(access_token))
                os.environ.setdefault("ONEBOT_V11_ACCESS_TOKEN", str(access_token))
            except Exception:
                pass

        # 确保使用 FastAPI 驱动
        try:
            import os
            os.environ.setdefault("DRIVER", "~fastapi")
        except Exception:
            pass

        nonebot.init()
        driver = nonebot.get_driver()
        # 通过运行时配置再次注入（适配不同版本）
        try:
            if access_token:
                setattr(driver.config, "onebot_access_token", access_token)
        except Exception:
            pass
        driver.register_adapter(OneBotV11Adapter)

        # 注册事件处理
        self._setup_handlers()

        # 获取 ASGI 应用
        self.app = nonebot.get_asgi()
        # 尝试添加健康检查路由
        try:
            from fastapi import FastAPI

            if isinstance(self.app, FastAPI):
                @self.app.get("/health")  # type: ignore
                async def _health():
                    return {"status": "healthy", "receiver": "qq"}
        except Exception:
            pass
        self.logger.info("NoneBot2 初始化完成，已注册 OneBot v11 适配器")

    def _setup_handlers(self):
        """注册 NoneBot 事件处理器"""

        msg_matcher = on_message(priority=50, block=False)

        @msg_matcher.handle()
        async def _(bot: Bot, event: MessageEvent):
            try:
                if isinstance(event, PrivateMessageEvent):
                    message_type = "private"
                elif isinstance(event, GroupMessageEvent):
                    message_type = "group"
                else:
                    return

                user_id = str(getattr(event, "user_id", ""))
                self_id = str(getattr(bot, "self_id", ""))

                # 检查黑名单
                if await self._is_blacklisted(user_id, self_id):
                    self.logger.info(f"用户 {user_id} 在黑名单中，忽略消息")
                    return

                # 抑制重复消息
                raw_plain = event.get_plaintext() if hasattr(event, "get_plaintext") else str(event.get_message())
                if self._should_suppress_message(user_id, raw_plain):
                    self.logger.debug(f"消息被抑制: {user_id}")
                    return

                data: Dict[str, Any] = {
                    "post_type": "message",
                    "message_type": message_type,
                    "user_id": user_id,
                    "self_id": self_id,
                    "message_id": str(getattr(event, "message_id", "")),
                    "raw_message": raw_plain,
                    "time": int(getattr(event, "time", int(time.time()))),
                    "sender": {
                        "nickname": getattr(getattr(event, "sender", None), "nickname", None),
                    },
                }

                if isinstance(event, GroupMessageEvent):
                    data["group_id"] = str(getattr(event, "group_id", ""))

                await self.process_message(data)
            except Exception as e:
                self.logger.error(f"处理消息事件失败: {e}", exc_info=True)

        req_matcher = on_request(priority=50, block=False)

        @req_matcher.handle()
        async def _(bot: Bot, event: FriendRequestEvent):
            try:
                if not isinstance(event, FriendRequestEvent):
                    return

                user_id = str(getattr(event, "user_id", ""))
                flag = getattr(event, "flag", None)
                comment = getattr(event, "comment", "")
                self_id = str(getattr(bot, "self_id", ""))

                # 去重窗口
                if not self._should_process_friend_request(user_id):
                    self.logger.info(f"忽略重复的好友请求: {user_id}")
                    return

                # 添加抑制项，避免同样文本立即触发投稿
                self._add_suppression(user_id, comment)

                # 自动同意
                if self.config.get("auto_accept_friend", True) and flag:
                    try:
                        await bot.call_api("set_friend_add_request", flag=flag, approve=True)
                        self.logger.info(f"已同意好友请求: {flag}")
                    except Exception as e:
                        self.logger.error(f"同意好友请求失败: {e}")

                if self.friend_request_handler:
                    await self.friend_request_handler(
                        {
                            "post_type": "request",
                            "request_type": "friend",
                            "user_id": user_id,
                            "self_id": self_id,
                            "flag": flag,
                            "comment": comment,
                            "time": int(time.time()),
                        }
                    )
            except Exception as e:
                self.logger.error(f"处理好友请求失败: {e}", exc_info=True)

    def _should_process_friend_request(self, user_id: str) -> bool:
        now = time.time()
        window = self.config.get("friend_request_window", 300)
        expire = self.friend_request_cache.get(user_id)
        if expire and expire > now:
            return False
        self.friend_request_cache[user_id] = now + window
        return True

    def _add_suppression(self, user_id: str, text: str, duration: int = 120):
        expire_time = time.time() + duration
        norm_text = self._normalize_text(text)
        self.suppression_cache.setdefault(user_id, []).append({"text": norm_text, "expire": expire_time})

    def _should_suppress_message(self, user_id: str, raw_message: str) -> bool:
        rules = self.suppression_cache.get(user_id)
        if not rules:
            return False
        norm_text = self._normalize_text(raw_message)
        now = time.time()
        self.suppression_cache[user_id] = [r for r in rules if r["expire"] > now]
        for rule in self.suppression_cache[user_id]:
            if rule["text"] == norm_text:
                return True
        return False

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        import re
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
        return text.lower()

    async def _is_blacklisted(self, user_id: str, receiver_id: str) -> bool:
        db = await get_db()
        async with db.get_session() as session:
            # 解析账号组
            from config import get_settings

            settings = get_settings()
            group_name = None
            for gname, group in settings.account_groups.items():
                if group.main_account.qq_id == receiver_id:
                    group_name = gname
                    break
                for minor in group.minor_accounts:
                    if minor.qq_id == receiver_id:
                        group_name = gname
                        break

            if not group_name:
                return False

            stmt = select(BlackList).where(
                and_(BlackList.user_id == user_id, BlackList.group_name == group_name)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return bool(row and row.is_active())

    async def start(self):
        if self.is_running:
            return
        self.is_running = True

        if not self.app:
            # 容错：若未初始化则初始化
            await self.initialize()

        # 端口与host采用全局 server 配置
        from config import get_settings
        app_settings = get_settings()
        server_host = app_settings.server.host
        server_port = app_settings.server.port

        config = Config(
            app=self.app,  # type: ignore
            host=server_host,
            port=server_port,
            log_level="info" if not self.config.get("debug") else "debug",
        )
        self.server = Server(config)
        asyncio.create_task(self.server.serve())
        self.logger.info(f"QQ NoneBot 接收器已启动: {config.host}:{config.port}")

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.server:
            self.server.should_exit = True
            await asyncio.sleep(1)
        self.logger.info("QQ NoneBot 接收器已停止")

    async def handle_message(self, message: Dict[str, Any]):
        # 由 NoneBot 事件处理直接调用 process_message
        pass

    async def handle_friend_request(self, request: Dict[str, Any]):
        # 由 NoneBot 事件处理直接回调
        pass

    def _get_preferred_bot(self, receiver_id: Optional[str] = None) -> Optional[Bot]:
        try:
            bots = nonebot.get_bots()
            if not bots:
                return None
            # 优先选择与 receiver_id 匹配的 Bot
            if receiver_id:
                for bot in bots.values():
                    if str(getattr(bot, "self_id", "")) == str(receiver_id):
                        return bot
            # 回退到任意可用 Bot
            return next(iter(bots.values()))
        except Exception:
            return None

    async def send_private_message(self, user_id: str, message: str, port: Optional[int] = None) -> bool:  # type: ignore[override]
        try:
            bot = self._get_preferred_bot()
            if not bot:
                self.logger.error("没有可用的 OneBot Bot 实例")
                return False
            try:
                uid = int(user_id)
            except Exception:
                uid = user_id  # 适配少数实现允许字符串
            await bot.call_api("send_private_msg", user_id=uid, message=message)
            return True
        except Exception as e:
            self.logger.error(f"发送私聊消息失败: {e}")
            return False

    async def send_group_message(self, group_id: str, message: str, port: Optional[int] = None) -> bool:  # type: ignore[override]
        try:
            bot = self._get_preferred_bot()
            if not bot:
                self.logger.error("没有可用的 OneBot Bot 实例")
                return False
            try:
                gid = int(group_id)
            except Exception:
                gid = group_id
            await bot.call_api("send_group_msg", group_id=gid, message=message)
            return True
        except Exception as e:
            self.logger.error(f"发送群消息失败: {e}")
            return False


