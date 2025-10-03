"""基于 NoneBot2 的 QQ 接收器实现"""

import asyncio
import contextlib

import random

import time

from typing import Dict, Any, Optional, List, Tuple, Awaitable

import re

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
        # 保存 Uvicorn 服务任务以便优雅关闭
        self.server_task: Optional[asyncio.Task] = None

        self.friend_request_cache: Dict[str, float] = {}

        self.suppression_cache: Dict[str, list] = {}

        # 未通过好友前的待过滤映射：key = f"{self_id}:{user_id}", value = expire_ts

        self.pending_friend_map: Dict[str, float] = {}

        # 注入的服务

        self.audit_service = None

        self.submission_service = None

        self.notification_service = None

        # 撤回事件处理：是否开启

        self.enable_recall_delete: bool = True

    def set_services(self, audit_service, submission_service, notification_service):

        """注入服务实例供指令处理使用"""

        self.audit_service = audit_service

        self.submission_service = submission_service

        self.notification_service = notification_service

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

        # 快速初始化 NoneBot（避免重复配置）
        nonebot.init()
        
        # NoneBot2 初始化后重新配置日志输出（避免被 NoneBot2 覆盖）
        # 使用缓存的日志配置，避免重复添加
        import os
        if os.getenv("XWALL_LOG_CONFIGURED") == "true":
            from loguru import logger as loguru_logger
            import sys
            
            # NoneBot2 会移除所有处理器，需要重新添加
            loguru_logger.remove()
            
            # 只添加必要的处理器（避免重复添加）
            loguru_logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level="INFO"
            )
            loguru_logger.add(
                "data/logs/xwall_{time:YYYY-MM-DD}.log",
                rotation="00:00",
                retention="30 days",
                level="DEBUG",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
            )

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

                # 未通过好友前，过滤其私聊消息

                if isinstance(event, PrivateMessageEvent):

                    if self._is_pending_friend(self_id, user_id):
                        self.logger.info(f"用户 {user_id} 尚未通过好友，忽略消息")

                        return

                # 检查黑名单

                if await self._is_blacklisted(user_id, self_id):
                    self.logger.info(f"用户 {user_id} 在黑名单中，忽略消息")

                    return

                # 抑制重复消息

                raw_plain = event.get_plaintext() if hasattr(event, "get_plaintext") else str(event.get_message())

                if self._should_suppress_message(user_id, raw_plain):
                    self.logger.debug(f"消息被抑制: {user_id}")

                    return

                # 群内优先尝试解析指令；私聊才进行投稿处理

                if isinstance(event, GroupMessageEvent):

                    handled = await self._try_handle_group_command(bot, event)

                    if handled:
                        return

                    # 非指令的群消息不创建投稿

                    return

                # 私聊 -> 进入投稿缓存/建稿流程

                # 在进入建稿流程前，优先解析私聊指令（如：#评论 <投稿ID> <内容>）

                if isinstance(event, PrivateMessageEvent):

                    handled_cmd = await self._try_handle_private_command(user_id, self_id, raw_plain)

                    if handled_cmd:
                        return

                # 提取消息段（用于渲染）

                segments: List[Dict[str, Any]] = []

                try:

                    for seg in event.get_message():

                        seg_type = getattr(seg, "type", None)

                        try:

                            seg_data = dict(getattr(seg, "data", {}))



                        except Exception:

                            seg_data = {}

                        # 展开 OneBot v11 合并转发：forward 段 -> 调 get_forward_msg

                        if seg_type == "forward":

                            expanded = await self._expand_forward_segment(bot, seg_data)

                            if expanded is not None:
                                segments.append({"type": "forward", "data": expanded})

                                continue

                        segments.append({

                            "type": seg_type,

                            "data": seg_data,

                        })



                except Exception:

                    segments = []

                data: Dict[str, Any] = {

                    "post_type": "message",

                    "message_type": message_type,

                    "user_id": user_id,

                    "self_id": self_id,

                    "message_id": str(getattr(event, "message_id", "")),

                    "raw_message": raw_plain,

                    "message": segments,

                    "time": int(getattr(event, "time", int(time.time()))),

                    "sender": {

                        "nickname": getattr(getattr(event, "sender", None), "nickname", None),

                    },

                }

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

                # 标记该用户为待通过好友，期间屏蔽其私聊消息

                try:

                    delay_min = max(0, int(self.config.get("friend_accept_delay_min", 180)))

                    delay_max = max(delay_min, int(self.config.get("friend_accept_delay_max", 240)))

                    delay_seconds = random.uniform(delay_min, delay_max) if delay_max > 0 else 0.0



                except Exception:

                    delay_seconds = 0.0

                # 额外保留 300 秒兜底，避免 notice 丢失导致短时未解除

                self._mark_pending_friend(self_id, user_id, duration=(delay_seconds or 0.0) + 300.0)

                # 自动同意

                if self.config.get("auto_accept_friend", True) and flag:

                    delay_min = max(0, int(self.config.get("friend_accept_delay_min", 180)))

                    delay_max = max(delay_min, int(self.config.get("friend_accept_delay_max", 240)))

                    delay_seconds = random.uniform(delay_min, delay_max) if delay_max > 0 else 0.0

                    if delay_seconds > 0:
                        self.logger.info(f"将于 {delay_seconds:.1f} 秒后同意好友请求: flag={flag}, user_id={user_id}")

                    self._create_background_task(

                        self._accept_friend_request_with_delay(bot, flag, delay_seconds, user_id),

                        f"延迟同意好友请求 flag={flag}"

                    )

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

        # 通知事件（好友撤回、好友添加等）

        try:

            from nonebot.adapters.onebot.v11 import NoticeEvent

            notice_matcher = nonebot.on_notice(priority=50, block=False)  # type: ignore

            @notice_matcher.handle()  # type: ignore
            async def _(bot: Bot, event: NoticeEvent):

                try:

                    notice_type = getattr(event, "notice_type", None)

                    user_id = str(getattr(event, "user_id", ""))

                    self_id = str(getattr(bot, "self_id", ""))

                    # 处理好友撤回

                    if notice_type == "friend_recall":

                        if not self.enable_recall_delete:
                            return

                        message_id = str(getattr(event, "message_id", ""))

                        if not (user_id and self_id and message_id):
                            return

                        ok = await self.remove_cached_message(user_id, self_id, message_id)

                        if ok:
                            self.logger.info(
                                f"已根据撤回事件删除缓存消息: uid={user_id}, sid={self_id}, mid={message_id}")



                    # 处理好友添加成功

                    elif notice_type == "friend_add":

                        if not user_id or not self_id:
                            return

                        # 解除 pending 屏蔽

                        try:

                            self._unmark_pending_friend(self_id, user_id)



                        except Exception:

                            pass

                        # 获取配置的欢迎消息

                        try:

                            from config import get_settings

                            settings = get_settings()

                            group_name = self._resolve_group_name_by_self_id(self_id)

                            if group_name and group_name in settings.account_groups:

                                group_config = settings.account_groups[group_name]

                                welcome_msg = getattr(group_config, 'friend_add_message', '')

                                if welcome_msg and welcome_msg.strip():
                                    await self.send_private_message(user_id, welcome_msg)

                                    self.logger.info(
                                        f"已发送好友添加欢迎消息: uid={user_id}, sid={self_id}, group={group_name}")



                        except Exception as e:

                            self.logger.error(f"发送好友欢迎消息失败: {e}")



                except Exception as e:

                    self.logger.error(f"处理通知事件失败: {e}")



        except Exception:

            pass

    async def _accept_friend_request_with_delay(self, bot: Bot, flag: str, delay: float, user_id: Optional[str] = None):

        try:

            wait_seconds = max(0.0, float(delay))

            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            await bot.call_api("set_friend_add_request", flag=flag, approve=True)

            self.logger.info(f"已同意好友请求: flag={flag}, user_id={user_id}")



        except Exception as e:

            self.logger.error(f"延迟同意好友请求失败: flag={flag}, user_id={user_id}, 错误={e}", exc_info=True)

    def _create_background_task(self, coro: Awaitable[Any], description: str = "") -> asyncio.Task:

        task = asyncio.create_task(coro)

        if description:

            def _log_task_result(t: asyncio.Task):

                try:

                    t.result()



                except Exception as exc:

                    self.logger.error(f"{description}出现异常: {exc}", exc_info=True)

            task.add_done_callback(_log_task_result)

        return task

    async def _expand_forward_segment(self, bot: Bot, seg_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:

        """展开合并转发段：调用 get_forward_msg，转换成 data.messages 结构。



        目标结构：



        {



          "messages": [



            { "message": [ {"type": ..., "data": {...}}, ... ] },



            ...



          ]



        }



        """

        try:

            forward_id = (

                    seg_data.get("id")

                    or seg_data.get("forward_id")

                    or seg_data.get("res_id")

                    or seg_data.get("resource_id")

                    or seg_data.get("resId")

            )

            if not forward_id:
                return None

            # OneBot v11: get_forward_msg

            resp = await bot.call_api("get_forward_msg", id=forward_id)

            # 兼容不同实现的返回层级

            ob_msgs = (

                    resp.get("messages")

                    or (resp.get("data") or {}).get("messages")

                    or []

            )

            items: List[Dict[str, Any]] = []

            for ob in ob_msgs:

                # 有的返回用 content（可能是 list 或 str），有的直接用 message（list）

                inner: List[Dict[str, Any]] = []

                content = ob.get("content")

                if isinstance(content, list):

                    for c in content:

                        if isinstance(c, dict) and "type" in c:

                            ctype = c.get("type")

                            cdata = c.get("data") if isinstance(c.get("data"), dict) else {}

                            inner.append({"type": ctype, "data": dict(cdata)})



                        else:

                            inner.append({"type": "text", "data": {"text": str(c)}})



                elif isinstance(content, str):

                    inner.append({"type": "text", "data": {"text": content}})



                else:

                    msg_list = ob.get("message") or []

                    if isinstance(msg_list, list):

                        for c in msg_list:

                            if isinstance(c, dict) and "type" in c:

                                ctype = c.get("type")

                                cdata = c.get("data") if isinstance(c.get("data"), dict) else {}

                                inner.append({"type": ctype, "data": dict(cdata)})



                            else:

                                inner.append({"type": "text", "data": {"text": str(c)}})

                if inner:
                    items.append({"message": inner})

            return {"messages": items}



        except Exception:

            return None

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
        # 保存任务句柄，便于 stop 阶段等待退出
        self.server_task = asyncio.create_task(self.server.serve())

        self.logger.info(f"QQ NoneBot 接收器已启动: {config.host}:{config.port}")

    async def stop(self):

        if not self.is_running:
            return

        self.is_running = False

        if self.server:
            self.server.should_exit = True
            # 优雅等待服务任务退出；超时则强制取消
            try:
                if self.server_task:
                    await asyncio.wait_for(self.server_task, timeout=5)
            except asyncio.TimeoutError:
                try:
                    if self.server_task and not self.server_task.done():
                        self.server_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await self.server_task
                except Exception:
                    pass
            except asyncio.CancelledError:
                pass
            except Exception:
                # 兜底等待一小段时间
                await asyncio.sleep(0.5)

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

    async def send_private_message(self, user_id: str, message: str,
                                   port: Optional[int] = None) -> bool:  # type: ignore[override]

        try:

            bot = self._get_preferred_bot()

            if not bot:
                self.logger.error("没有可用的 OneBot Bot 实例")

                return False

            try:

                uid = int(user_id)



            except Exception:

                uid = user_id  # 适配少数实现允许字符串

            # 重试发送，缓解偶发超时

            for attempt in range(3):

                try:

                    await bot.call_api("send_private_msg", user_id=uid, message=message)

                    return True



                except Exception as e:

                    if attempt == 2:
                        raise

                    await asyncio.sleep(0.8 + attempt * 0.8)



        except Exception as e:

            self.logger.error(f"发送私聊消息失败: {e}")

            return False

    async def send_group_message(self, group_id: str, message: str,
                                 port: Optional[int] = None) -> bool:  # type: ignore[override]

        try:

            bot = self._get_preferred_bot()

            if not bot:
                self.logger.error("没有可用的 OneBot Bot 实例")

                return False

            try:

                gid = int(group_id)



            except Exception:

                gid = group_id

            # 重试发送，缓解 Napcat/OneBot 偶发 retcode 1200 超时

            for attempt in range(3):

                try:

                    await bot.call_api("send_group_msg", group_id=gid, message=message)

                    return True



                except Exception as e:

                    if attempt == 2:
                        raise

                    await asyncio.sleep(1.0 + attempt * 1.0)



        except Exception as e:

            self.logger.error(f"发送群消息失败: {e}")

            return False

    async def send_private_message_by_self(self, self_id: str, user_id: str, message: str) -> bool:

        """指定使用某个 Bot(self_id) 发送私聊消息。"""

        try:

            bot = None

            try:

                bots = nonebot.get_bots()

                for b in bots.values():

                    if str(getattr(b, "self_id", "")) == str(self_id):
                        bot = b

                        break



            except Exception:

                bot = None

            if not bot:
                self.logger.error(f"未找到指定 self_id 的 Bot：{self_id}")

                return False

            try:

                uid = int(user_id)



            except Exception:

                uid = user_id

            for attempt in range(3):

                try:

                    await bot.call_api("send_private_msg", user_id=uid, message=message)

                    return True



                except Exception as e:

                    if attempt == 2:
                        raise

                    await asyncio.sleep(0.8 + attempt * 0.8)



        except Exception as e:

            self.logger.error(f"发送私聊消息失败(self_id={self_id}): {e}")

            return False

    async def list_friends(self, receiver_id: Optional[str] = None) -> List[Dict[str, str]]:

        """列出好友列表。



        当 receiver_id 为 None 时，返回所有已连接 Bot 的好友，包含对应 self_id；



        返回形如：[{"self_id": "123", "user_id": "456", "nickname": "...", "remark": "..."}, ...]



        """

        friends: List[Dict[str, str]] = []

        try:

            bots = []

            try:

                all_bots = nonebot.get_bots()

                for b in all_bots.values():

                    if (receiver_id is None) or (str(getattr(b, "self_id", "")) == str(receiver_id)):
                        bots.append(b)



            except Exception:

                bots = []

            for bot in bots:

                try:

                    resp = await bot.call_api("get_friend_list")

                    for item in (resp or []):

                        try:

                            uid = str(item.get("user_id"))

                            if not uid:
                                continue

                            friends.append({

                                "self_id": str(getattr(bot, "self_id", "")),

                                "user_id": uid,

                                "nickname": str(item.get("nickname", "")),

                                "remark": str(item.get("remark", "")),

                            })



                        except Exception:

                            continue



                except Exception:

                    continue



        except Exception:

            return friends

        return friends

    # ===== 指令解析与执行 =====

    async def _try_handle_group_command(self, bot: Bot, event: GroupMessageEvent) -> bool:

        try:

            self_id = str(getattr(bot, "self_id", ""))

            group_id = str(getattr(event, "group_id", ""))

            # 是否 @了本机器人

            if not self._is_at_self(event, self_id):
                return False

            # 取得 @ 后的纯文本

            after_text = event.get_plaintext().strip()

            # 帮助命令：任何成员、任意群均可触发

            if after_text in ("帮助", "help", "指令"):
                await self.send_group_message(group_id, self._build_help_text())

                return True

            # 其余命令：仅管理员/群主允许在管理群执行

            if not self._is_admin_sender(event):
                return False

            group_name = self._resolve_group_name_by_group_id(group_id) or self._resolve_group_name_by_self_id(self_id)

            if not group_name:
                return False

            # 如果是回复消息，尝试从被回复的消息里解析内部编号

            reply_sub_id = await self._try_extract_submission_id_from_reply(bot, event)

            if reply_sub_id is not None and after_text:

                full_text = f"{reply_sub_id} {after_text}"



            else:

                full_text = after_text

            if not full_text:
                return False

            # 判断是审核指令还是全局指令

            tokens = full_text.split()

            if not tokens:
                return False

            # 以数字开头 -> 审核指令

            if tokens[0].isdigit():
                submission_id = int(tokens[0])

                cmd = tokens[1] if len(tokens) > 1 else ""

                extra = " ".join(tokens[2:]) if len(tokens) > 2 else None

                return await self._handle_audit_command(group_id, submission_id, cmd, str(event.user_id), extra)

            # 非数字开头 -> 全局指令

            return await self._handle_global_command(group_id, group_name, full_text)



        except Exception as e:

            self.logger.error(f"解析群指令失败: {e}", exc_info=True)

            return False

    def _is_admin_sender(self, event: GroupMessageEvent) -> bool:

        try:

            role = getattr(getattr(event, "sender", None), "role", None)

            return role in ("admin", "owner")



        except Exception:

            return False

    def _is_at_self(self, event: GroupMessageEvent, self_id: str) -> bool:

        try:

            return event.to_me



        except Exception:

            return False

    async def _try_extract_submission_id_from_reply(self, bot: Bot, event: GroupMessageEvent) -> Optional[int]:

        try:

            reply_id = None

            for seg in event.get_message():

                if seg.type == "reply":

                    rid = seg.data.get("id") or seg.data.get("message_id")

                    if rid is not None:
                        reply_id = int(rid)

                        break

            if reply_id is None:
                return None

            # 获取被回复消息

            try:

                resp = await bot.call_api("get_msg", message_id=reply_id)

                # 解析纯文本

                plain = ""

                try:

                    parts = []

                    for seg in resp.get("message", []):

                        if seg.get("type") == "text":
                            parts.append(seg.get("data", {}).get("text", ""))

                    plain = "".join(parts)



                except Exception:

                    plain = str(resp)

                import re

                m = re.search(r"内部编号(\d+)", plain)

                if m:
                    return int(m.group(1))



            except Exception:

                return None



        except Exception:

            return None

        return None

    def _resolve_group_name_by_group_id(self, group_id: str) -> Optional[str]:

        try:

            from config import get_settings

            settings = get_settings()

            for gname, group in settings.account_groups.items():

                if str(group.manage_group_id) == str(group_id):
                    return gname



        except Exception:

            pass

        return None

    def _resolve_group_name_by_self_id(self, self_id: str) -> Optional[str]:

        try:

            from config import get_settings

            settings = get_settings()

            for gname, group in settings.account_groups.items():

                if str(group.main_account.qq_id) == str(self_id):
                    return gname

                for minor in group.minor_accounts:

                    if str(minor.qq_id) == str(self_id):
                        return gname



        except Exception:

            pass

        return None

    async def _handle_audit_command(self, group_id: str, submission_id: int, cmd: str, operator_id: str,
                                    extra: Optional[str]) -> bool:

        try:

            if not self.audit_service:
                await self.send_group_message(group_id, "审核服务未就绪")

                return True

            # 将未知指令作为快捷回复键交给审核服务 quick_reply 兜底

            result = await self.audit_service.handle_command(submission_id, cmd, operator_id, extra)

            # 审核通过：仅通知投稿者；发送留待定时任务处理

            pub_ok = None

            notif_ok = None

            if cmd == "是" and (isinstance(result, dict) and result.get("success")):

                try:

                    if self.notification_service:
                        notif_ok = await self.notification_service.send_submission_approved(submission_id)



                except Exception as e:

                    self.logger.error(f"审核通过后通知投稿者失败: {e}")

                    notif_ok = False

            # 特殊命令：立即 -> 同步触发发送暂存区并单发当前投稿

            if cmd == "立即" and (isinstance(result, dict) and result.get("success")):

                try:

                    # 仅单发当前，避免与暂存区重复发送

                    if self.submission_service:
                        await self.submission_service.publish_single_submission(submission_id)



                except Exception as e:

                    self.logger.error(f"立即发送失败: {e}")

            # "是" 的独立模式：每个平台独立判断是否定时发送

            scheduled_platforms = []
            instant_platforms = []
            pub_ok = None

            if cmd == "是" and (isinstance(result, dict) and result.get("success")):

                try:

                    # 区分各平台是否配置了 send_schedule

                    from core.plugin import plugin_manager

                    from utils.common import get_platform_config

                    pubs = list(plugin_manager.publishers.values())

                    for pub in pubs:

                        try:

                            platform_key = getattr(pub.platform, "value", "")
                            cfg = get_platform_config(platform_key)

                            times = (cfg or {}).get("send_schedule") or []

                            if times:
                                scheduled_platforms.append(platform_key)

                            else:
                                instant_platforms.append(platform_key)



                        except Exception:

                            continue



                except Exception as e:

                    self.logger.error(f"区分平台定时配置失败: {e}")

                # 无定时的平台立即发送

                if instant_platforms:

                    try:

                        if self.submission_service:
                            pub_ok = await self.submission_service.publish_single_submission_for_platforms(
                                submission_id, instant_platforms
                            )



                    except Exception as e:

                        self.logger.error(f"立即发送平台 {instant_platforms} 失败: {e}")

                        pub_ok = False

            # 结果反馈

            msg = result.get("message") if isinstance(result, dict) else str(result)

            if cmd == "是":

                parts = []

                # 仅通知投稿者

                if notif_ok is not None:
                    parts.append("已私聊通知投稿者" if notif_ok else "通知投稿者失败")

                # 根据平台分布决定提示（独立模式）

                if instant_platforms and scheduled_platforms:
                    # 混合模式
                    if pub_ok is True:
                        tail = f"已立即发送到 {', '.join(instant_platforms)}；{', '.join(scheduled_platforms)} 已加入暂存区等待定时"
                    elif pub_ok is False:
                        tail = f"立即发送 {', '.join(instant_platforms)} 失败；{', '.join(scheduled_platforms)} 已加入暂存区"
                    else:
                        tail = f"{', '.join(scheduled_platforms)} 已加入暂存区等待定时"
                elif instant_platforms:
                    # 仅即时发送
                    if pub_ok is True:
                        tail = "已立即发送"
                    elif pub_ok is False:
                        tail = "自动发送失败。可用\"发送暂存区\"或\"立即\"重试"
                    else:
                        tail = "处理完成"
                elif scheduled_platforms:
                    # 仅定时发送
                    tail = "已加入暂存区，等待定时发送"
                else:
                    tail = "处理完成"

                extra_line = "；".join(parts + [tail]) if parts else tail

                msg = (msg or "") + ("\n" + extra_line if extra_line else "")

            if isinstance(result, dict) and result.get("need_reaudit"):
                msg = (msg or "") + "\n请继续发送审核指令"

            await self.send_group_message(group_id, msg or "已处理")

            return True



        except Exception as e:

            self.logger.error(f"执行审核指令异常: {e}", exc_info=True)

            await self.send_group_message(group_id, f"指令执行失败: {e}")

            return True

    async def _handle_global_command(self, group_id: str, group_name: str, text: str) -> bool:

        try:

            # 规范化：按空白切分

            parts = text.split()

            if not parts:
                return False

            cmd = parts[0]

            arg1 = parts[1] if len(parts) > 1 else None

            arg_rest = " ".join(parts[1:]) if len(parts) > 1 else None

            # 帮助

            if cmd in ("帮助", "help", "指令"):
                await self.send_group_message(group_id, self._build_help_text())

                return True

            # 设定编号 N

            if cmd == "设定编号" and arg1 and arg1.isdigit():

                try:

                    from pathlib import Path

                    num_dir = Path("data/cache/numb")

                    num_dir.mkdir(parents=True, exist_ok=True)

                    with open(num_dir / f"{group_name}_numfinal.txt", "w", encoding="utf-8") as f:

                        f.write(str(int(arg1)))

                    await self.send_group_message(group_id, f"外部编号已设定为{arg1}")



                except Exception as e:

                    await self.send_group_message(group_id, f"设定编号失败: {e}")

                return True

            # 取消登录刷新相关命令

            if cmd in ("自动重新登录", "手动重新登录"):
                await self.send_group_message(group_id, "已移除登录刷新逻辑，请更新 cookies 后重试")

                return True

            # 重渲染 <id> -> 仅重渲染

            if cmd == "重渲染" and arg1 and arg1.isdigit():

                if not self.audit_service:
                    await self.send_group_message(group_id, "审核服务未就绪")

                    return True

                res = await self.audit_service.rerender(int(arg1), operator_id=group_id)

                await self.send_group_message(group_id, res.get("message", "已处理"))

                return True

            # 调出 <id> -> 仅重渲染（等价命令）

            if cmd == "调出" and arg1 and arg1.isdigit():

                if not self.audit_service:
                    await self.send_group_message(group_id, "审核服务未就绪")

                    return True

                res = await self.audit_service.rerender(int(arg1), operator_id=group_id)

                await self.send_group_message(group_id, res.get("message", "已处理"))

                return True

            # 信息 <id>

            if cmd == "信息" and arg1 and arg1.isdigit():

                from core.database import get_db

                from sqlalchemy import select

                from core.models import Submission

                db = await get_db()

                async with db.get_session() as session:

                    r = await session.execute(select(Submission).where(Submission.id == int(arg1)))

                    sub = r.scalar_one_or_none()

                    if not sub:
                        await self.send_group_message(group_id, "投稿不存在")

                        return True

                    await self.send_group_message(group_id, self._format_submission_info(sub))

                return True

            # 待处理

            if cmd == "待处理":

                if not self.submission_service:
                    await self.send_group_message(group_id, "投稿服务未就绪")

                    return True

                pendings = await self.submission_service.get_pending_submissions(group_name)

                if not pendings:

                    await self.send_group_message(group_id, "本组没有待处理项目")



                else:

                    ids = "\n".join(str(s.id) for s in pendings)

                    await self.send_group_message(group_id, f"本组待处理项目:\n{ids}")

                return True

            # 删除待处理 -> 全部标为已删除

            if cmd == "删除待处理":

                try:

                    from core.database import get_db

                    from sqlalchemy import select, update

                    from core.models import Submission

                    from core.enums import SubmissionStatus

                    db = await get_db()

                    async with db.get_session() as session:

                        r = await session.execute(select(Submission).where(

                            (Submission.group_name == group_name) & (Submission.status.in_([

                                SubmissionStatus.PENDING.value,

                                SubmissionStatus.PROCESSING.value,

                                SubmissionStatus.WAITING.value

                            ]))

                        ))

                        subs = r.scalars().all()

                        if subs:
                            await session.execute(
                                update(Submission).where(Submission.id.in_([s.id for s in subs])).values(
                                    status=SubmissionStatus.DELETED.value))

                            await session.commit()

                    # 同时清理本账号组的历史消息缓存（MessageCache，使用 MessageCacheService）
                    try:
                        from config import get_settings
                        from core.message_cache_service import MessageCacheService

                        settings = get_settings()
                        group_cfg = (settings.account_groups or {}).get(group_name)

                        receiver_ids = []
                        if group_cfg:
                            try:
                                if getattr(group_cfg, "main_account", None) and getattr(group_cfg.main_account, "qq_id", None):
                                    receiver_ids.append(str(group_cfg.main_account.qq_id))
                            except Exception:
                                pass
                            try:
                                for minor in getattr(group_cfg, "minor_accounts", []) or []:
                                    try:
                                        if getattr(minor, "qq_id", None):
                                            receiver_ids.append(str(minor.qq_id))
                                    except Exception:
                                        continue
                            except Exception:
                                pass

                        if receiver_ids:
                            db = await get_db()
                            async with db.get_session() as session2:
                                # 清理每个 receiver 的缓存（包括 Redis/Memory 和数据库）
                                for receiver_id in receiver_ids:
                                    await MessageCacheService.clear_all_by_receiver(receiver_id, session2)
                    except Exception:
                        # 清理缓存失败不影响主流程
                        pass

                    await self.send_group_message(group_id, "已清空待处理列表，并删除历史消息")



                except Exception as e:

                    await self.send_group_message(group_id, f"清空失败: {e}")

                return True

            # 删除暂存区

            if cmd == "删除暂存区":

                if not self.submission_service:
                    await self.send_group_message(group_id, "投稿服务未就绪")

                    return True

                ok = await self.submission_service.clear_stored_posts(group_name)

                await self.send_group_message(group_id, "已清空暂存区" if ok else "清空暂存区失败")

                return True

            # 发送暂存区 [平台]

            if cmd == "发送暂存区":

                if not self.submission_service:
                    await self.send_group_message(group_id, "投稿服务未就绪")

                    return True

                # 可选平台参数：qzone/bilibili/rednote ...

                target_platform = (arg1 or "").strip().lower() if arg1 else None

                # 若带平台，则仅该平台按发布器路径发送；否则对所有已注册发布器发送

                try:

                    from core.plugin import plugin_manager

                    publishers = list(plugin_manager.publishers.values())



                except Exception:

                    publishers = []

                if target_platform:

                    # 按平台键匹配发布器（优先用 platform.value == 平台键）

                    target_pub_names = []

                    for name, pub in plugin_manager.publishers.items():  # type: ignore[attr-defined]

                        try:

                            if str(getattr(pub, 'platform', None).value) == target_platform:
                                target_pub_names.append(name)



                        except Exception:

                            continue

                    if not target_pub_names:
                        await self.send_group_message(group_id, f"未找到平台：{target_platform}")

                        return True

                    all_ok = True

                    for pub_name in target_pub_names:

                        try:

                            ok = await self.submission_service.publish_stored_posts_for_publisher(group_name, pub_name)

                            all_ok = all_ok and bool(ok)



                        except Exception:

                            all_ok = False

                    await self.send_group_message(group_id, (
                        f"[{target_platform}] 投稿已发送" if all_ok else f"[{target_platform}] 发送失败"))

                    return True



                else:

                    # 无平台参数：对所有已注册发布器逐一发送

                    if not publishers:
                        await self.send_group_message(group_id, "没有可用的发送器")

                        return True

                    results = []

                    all_ok = True

                    for pub in publishers:

                        try:

                            ok = await self.submission_service.publish_stored_posts_for_publisher(group_name, pub.name)

                            results.append((pub.name, bool(ok)))

                            all_ok = all_ok and bool(ok)



                        except Exception:

                            results.append((pub.name, False))

                            all_ok = False

                    # 总结消息

                    parts = []

                    for name, ok in results:
                        parts.append(f"{name}:{'OK' if ok else 'FAIL'}")

                    msg = "；".join(parts) if parts else ("无可用发送器" if not publishers else "未知")

                    await self.send_group_message(group_id,
                                                  ("投稿已发送\n" + msg) if all_ok else ("发送完成（部分失败）\n" + msg))

                    return True

            # 公告 / #公告 [全部] <内容>

            if cmd in ("公告", "#公告"):

                # 判定是否全局

                synonyms_all = {"全部", "全体", "所有", "ALL", "all"}

                is_global = bool(arg1 and arg1 in synonyms_all)

                if is_global:

                    content = " ".join(parts[2:]) if len(parts) > 2 else ""



                else:

                    content = (arg_rest or "")

                content = content.strip()

                if not content:
                    await self.send_group_message(group_id, "错误：请输入公告内容。例如：公告 <内容> 或 公告 全部 <内容>")

                    return True

                try:

                    # 复用已注入的通知服务；未注入则就地创建

                    notifier = self.notification_service

                    if not notifier:
                        from services.notification_service import NotificationService  # 局部导入避免循环

                        notifier = NotificationService()

                    # 调整为向所有好友发布

                    res = await notifier.broadcast_to_friends(content, None if is_global else group_name)

                    await self.send_group_message(

                        group_id,

                        f"公告已推送：总计 {res.get('total', 0)}，成功 {res.get('success', 0)}，失败 {res.get('failed', 0)}"

                    )



                except Exception as e:

                    await self.send_group_message(group_id, f"公告发送失败：{e}")

                return True

            # 自检

            if cmd == "自检":

                try:

                    from core.database import get_db

                    db = await get_db()

                    db_ok = await db.health_check()



                except Exception:

                    db_ok = False

                # 登录状态

                login_ok = False

                try:

                    from core.plugin import plugin_manager

                    publisher = plugin_manager.get_publisher("qzone_publisher")

                    if publisher:
                        login_ok = await publisher.check_login_status()



                except Exception:

                    login_ok = False

                msg = (

                    "== 系统自检报告 ==\n"



                    f"数据库: {'正常' if db_ok else '异常'}\n"



                    f"QQ空间登录: {'正常' if login_ok else '异常'}\n"



                    "==== 自检完成 ===="

                )

                await self.send_group_message(group_id, msg)

                return True

            # 删除 <编号或投稿ID> （管理员群任意投稿）

            if cmd == "删除" and arg1 and arg1.isdigit():

                if not self.submission_service:
                    await self.send_group_message(group_id, "投稿服务未就绪")

                    return True

                # 允许使用外部发布编号 publish_id 或内部投稿ID

                sid = await self._resolve_submission_id_by_any(arg1)

                if sid is None:
                    await self.send_group_message(group_id, "未找到该编号对应的投稿")

                    return True

                try:

                    res = await self.submission_service.delete_submission(sid)

                    await self.send_group_message(group_id, res.get("message", "操作完成"))



                except Exception:

                    await self.send_group_message(group_id, "未能删除，请稍后再试")

                return True

            # 取消拉黑 <qq>

            if cmd == "取消拉黑" and arg1:

                try:

                    from core.database import get_db

                    from sqlalchemy import delete

                    from core.models import BlackList

                    db = await get_db()

                    async with db.get_session() as session:

                        await session.execute(delete(BlackList).where(
                            (BlackList.user_id == str(arg1)) & (BlackList.group_name == group_name)))

                        await session.commit()

                    await self.send_group_message(group_id, f"已取消拉黑 senderid: {arg1}")



                except Exception as e:

                    await self.send_group_message(group_id, f"取消拉黑失败: {e}")

                return True

            # 列出拉黑

            if cmd == "列出拉黑":

                try:

                    from core.database import get_db

                    from sqlalchemy import select

                    from core.models import BlackList

                    db = await get_db()

                    async with db.get_session() as session:

                        r = await session.execute(select(BlackList).where(BlackList.group_name == group_name))

                        rows = r.scalars().all()

                    if not rows:

                        await self.send_group_message(group_id, "当前账户组没有被拉黑的账号")



                    else:

                        lines = ["被拉黑账号列表："]

                        for row in rows:
                            lines.append(f"账号: {row.user_id}，理由: {row.reason or '无'}")

                        await self.send_group_message(group_id, "\n".join(lines))



                except Exception as e:

                    await self.send_group_message(group_id, f"查询失败: {e}")

                return True

            # 快捷回复 管理

            if cmd == "快捷回复":

                subcmd = parts[1] if len(parts) > 1 else None

                if subcmd == "添加" and len(parts) >= 3:

                    kv = " ".join(parts[2:])

                    if "=" in kv:
                        k, v = kv.split("=", 1)

                        ok, msg = self._quick_reply_update(group_name, k.strip(), v.strip(), op="add")

                        await self.send_group_message(group_id, msg)

                        return True

                    await self.send_group_message(group_id, "错误：格式不正确，请使用 '指令名=内容'")

                    return True

                if subcmd == "删除" and len(parts) >= 3:
                    k = " ".join(parts[2:]).strip()

                    ok, msg = self._quick_reply_update(group_name, k, None, op="del")

                    await self.send_group_message(group_id, msg)

                    return True

                # 查看列表

                ok, msg = self._quick_reply_list(group_name)

                await self.send_group_message(group_id, msg)

                return True

            # 未识别

            return False



        except Exception as e:

            self.logger.error(f"处理全局指令失败: {e}", exc_info=True)

            return False

    async def _try_handle_private_command(self, user_id: str, self_id: str, raw_text: str) -> bool:

        """解析并处理私聊指令。目前支持：



        - #评论 <投稿ID> <内容>  -> 投稿者本人为其投稿追加评论（外部平台不暴露身份）



        - #删除 <投稿ID>         -> 投稿者本人删除自己的投稿（未发布或已发布平台删除）



        识别到并处理返回 True；未识别返回 False。



        """

        try:

            text = (raw_text or "").strip()

            # 反馈指令：#反馈 <内容>

            m_fb = re.match(r"^#?\s*反馈\s+(.+)$", text)

            if m_fb:

                feedback_text = m_fb.group(1).strip()

                if not feedback_text:
                    await self.send_private_message(user_id, "错误：反馈内容不能为空")

                    return True

                try:

                    from pathlib import Path

                    from config import get_settings

                    settings = get_settings()

                    base_dir = Path(settings.system.data_dir or "./data")

                    fb_dir = base_dir / "feedback"

                    fb_dir.mkdir(parents=True, exist_ok=True)

                    # 按日期分别记录

                    day_str = time.strftime("%Y-%m-%d", time.localtime())

                    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                    group_name = self._resolve_group_name_by_self_id(self_id) or "unknown"

                    line = f"[{ts_str}] uid={user_id} sid={self_id} group={group_name} feedback={feedback_text}\n"

                    with open(fb_dir / f"{day_str}.log", "a", encoding="utf-8") as f:

                        f.write(line)

                    self.logger.info(f"已记录用户反馈: uid={user_id}, group={group_name}")

                    await self.send_private_message(user_id, "感谢反馈，我们已记录")



                except Exception as e:

                    self.logger.error(f"保存反馈失败: {e}", exc_info=True)

                    await self.send_private_message(user_id, "反馈保存失败，请稍后重试")

                return True

            # 私聊删除：#删除 <编号或投稿ID>

            m_del = re.match(r"^#?删除\s+(\d+)$", text)

            if m_del:

                raw_id = m_del.group(1)

                sid = await self._resolve_submission_id_by_any(raw_id)

                if sid is None:
                    await self.send_private_message(user_id, "错误：未找到该编号对应的投稿")

                    return True

                # 校验归属：仅允许删除自己的投稿

                from core.database import get_db

                from sqlalchemy import select

                from core.models import Submission

                db = await get_db()

                async with db.get_session() as session:

                    r = await session.execute(select(Submission).where(Submission.id == sid))

                    sub = r.scalar_one_or_none()

                    if not sub:
                        await self.send_private_message(user_id, "错误：投稿不存在")

                        return True

                    if str(sub.sender_id) != str(user_id):
                        await self.send_private_message(user_id, "错误：只能删除自己的投稿")

                        return True

                if not self.submission_service:
                    await self.send_private_message(user_id, "服务暂不可用，请稍后再试")

                    return True

                try:

                    res = await self.submission_service.delete_submission(sid)

                    await self.send_private_message(user_id, res.get("message", "操作完成"))



                except Exception:

                    await self.send_private_message(user_id, "未能删除，请稍后再试")

                return True

            # 允许前缀可选的 # -> 评论（编号或投稿ID）

            m = re.match(r"^#?评论\s+(\d+)\s+(.+)$", text)

            if not m:
                return False

            raw_id = m.group(1)

            submission_id = await self._resolve_submission_id_by_any(raw_id)

            if submission_id is None:
                await self.send_private_message(user_id, "错误：未找到该编号对应的投稿")

                return True

            comment_text = m.group(2).strip()

            if not comment_text:
                await self.send_private_message(user_id, "错误：评论内容不能为空")

                return True

            # 查询投稿并进行状态校验

            from core.database import get_db

            from sqlalchemy import select

            from core.models import Submission

            from core.enums import SubmissionStatus

            db = await get_db()

            async with db.get_session() as session:

                r = await session.execute(select(Submission).where(Submission.id == submission_id))

                submission = r.scalar_one_or_none()

                if not submission:
                    await self.send_private_message(user_id, "错误：投稿不存在")

                    return True

                # 仅允许对已发布的投稿同步评论

                if submission.status != SubmissionStatus.PUBLISHED.value:
                    await self.send_private_message(user_id, "当前投稿尚未发布，无法同步评论到外部平台")

                    return True

                group_name_for_comment = submission.group_name

            # 检查是否启用 #评论 指令（按投稿所属组配置）

            try:

                from config import get_settings

                settings = get_settings()

                if group_name_for_comment and group_name_for_comment in settings.account_groups:

                    grp = settings.account_groups.get(group_name_for_comment)

                    enable_comment_cmd = bool(getattr(grp, 'allow_anonymous_comment', True))

                    if not enable_comment_cmd:
                        await self.send_private_message(user_id, "本组未启用 #评论 功能")

                        return True



            except Exception:

                # 若配置读取异常，则默认允许

                pass

            # 记录审核日志（始终记录操作者真实ID）

            try:

                if self.audit_service:
                    await self.audit_service.log_audit(submission_id, user_id, "评论", comment_text)



            except Exception:

                pass

            # 同步到所有已注册的支持评论的发送器（不暴露操作者身份）

            try:

                from core.plugin import plugin_manager

                publishers = list(plugin_manager.publishers.values())

                if not publishers:
                    await self.send_private_message(user_id, "发送器未就绪，稍后再试")

                    return True

                results = []

                success_any = False

                for pub in publishers:

                    try:

                        if hasattr(pub, "add_comment_for_submission"):
                            r = await getattr(pub, "add_comment_for_submission")(submission_id, comment_text)

                            results.append((pub.name, bool(r.get("success")), r))

                            success_any = success_any or bool(r.get("success"))



                    except Exception as _e:

                        results.append((pub.name, False, {"message": str(_e)}))

                if success_any:

                    await self.send_private_message(user_id, "评论成功")



                else:

                    msg = "；".join([f"{n}:{r.get('message', '失败')}" for n, ok, r in results]) or "未知错误"

                    await self.send_private_message(user_id, f"评论失败：{msg}")

                return True



            except Exception as e:

                self.logger.error(f"评论同步失败: {e}")

                await self.send_private_message(user_id, "评论失败：系统异常")

                return True

            # 不应到达此处

            return False



        except Exception as e:

            self.logger.error(f"处理私聊评论指令失败: {e}", exc_info=True)

            try:

                await self.send_private_message(user_id, f"处理失败：{e}")



            except Exception:

                pass

            return True

    def _quick_reply_update(self, group_name: str, key: str, value: Optional[str], op: str) -> Tuple[bool, str]:

        try:

            from config import get_settings

            settings = get_settings()

            group = settings.account_groups.get(group_name)

            if not group:
                return False, "找不到账号组配置"

            # 冲突检查

            if op == "add":

                audit_cmds = {"是", "否", "匿", "等", "删", "拒", "立即", "刷新", "重渲染", "扩列审查", "评论", "回复",
                              "展示", "拉黑"}

                if key in audit_cmds:
                    return False, f"错误：快捷回复指令 '{key}' 与审核指令冲突"

                group.quick_replies[key] = value or ""



            elif op == "del":

                if key not in group.quick_replies:
                    return False, f"错误：快捷回复指令 '{key}' 不存在"

                del group.quick_replies[key]



            else:

                return False, "无效操作"

            # 持久化

            settings.save_yaml()

            return True, (f"已添加快捷回复指令：{key}" if op == "add" else f"已删除快捷回复指令：{key}")



        except Exception as e:

            return False, f"快捷回复更新失败: {e}"

    def _quick_reply_list(self, group_name: str) -> Tuple[bool, str]:

        try:

            from config import get_settings

            settings = get_settings()

            group = settings.account_groups.get(group_name)

            qrs = (group.quick_replies if group else {}) or {}

            if not qrs:
                return True, "当前账户组未配置快捷回复"

            lines = ["== 快捷回复列表 =="]

            for k, v in qrs.items():

                vv = (v or "")

                if len(vv) > 120:
                    vv = vv[:120] + "…"

                lines.append(f"- {k}：{vv}")

            return True, "\n".join(lines)



        except Exception as e:

            return False, f"获取快捷回复失败: {e}"

    def _build_help_text(self) -> str:

        return (

            "== 指令帮助 ==\n"



            "语法：@本账号 指令\n\n"



            "[全局]\n"



            "- 调出 <编号>\n"



            "- 信息 <编号>\n"



            "- 待处理\n"



            "- 删除 <编号或投稿ID>\n"



            "- 删除待处理\n"



            "- 删除暂存区\n"



            "- 发送暂存区 [平台]\n"



            "- 公告 [全部] <内容>\n"



            "- 设定编号 <数字>\n"



            "- 快捷回复 [添加 指令=内容|删除 指令]\n"



            "- 取消拉黑 <QQ>\n"



            "- 列出拉黑\n"



            "- 自检\n\n"



            "[审核]（在管理群，仅管理员）\n"



            "语法：@本账号 <内部编号> 指令 或 回复审核消息 指令\n"



            "可用：是/否/匿/等/删/拒/立即/刷新/重渲染/扩列审查/评论 <内容>/回复 <内容>/展示/拉黑 [理由]\n"



            "说明：'是' 加入暂存区；如已配置定时将自动发送；"



            "未配置定时可用“发送暂存区”或“立即”手动发送\n\n"



            "[私聊]\n"



            "#删除 <编号或投稿ID>（仅能删除自己的投稿）\n"



            "#评论 <编号或投稿ID> <内容>\n"



            "提示：可配置快捷回复，详见“快捷回复”"

        )

    def _format_submission_info(self, sub) -> str:

        """将投稿信息格式化为更易读的文本。"""

        try:

            import json

            def yn(flag: bool) -> str:

                return "是" if flag else "否"

            llm = getattr(sub, "llm_result", None) or {}

            if llm:

                llm_text = json.dumps(llm, ensure_ascii=False, separators=(",", ":"))

                if len(llm_text) > 600:
                    llm_text = llm_text[:600] + "…"



            else:

                llm_text = "无"

            created = sub.created_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(sub, "created_at", None) else "-"

            updated = sub.updated_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(sub, "updated_at", None) else "-"

            published = sub.published_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(sub, "published_at", None) else "-"

            nickname = getattr(sub, "sender_nickname", None)

            sender_line = f"发送者：{sub.sender_id}" + (f"（{nickname}）" if nickname else "")

            lines = [

                "== 投稿信息 ==",

                f"投稿ID：{sub.id}",

                f"内部编号：{getattr(sub, 'internal_id', None) or '-'}    发布编号：{getattr(sub, 'publish_id', None) or '-'}",

                f"状态：{sub.status}    匿名：{yn(getattr(sub, 'is_anonymous', False))}    安全：{yn(getattr(sub, 'is_safe', True))}    完整：{yn(getattr(sub, 'is_complete', False))}",

                f"所属组：{getattr(sub, 'group_name', None) or '-'}",

                sender_line,

                f"接收者：{getattr(sub, 'receiver_id', None) or '-'}",

                f"创建时间：{created}    更新时间：{updated}    发布时间：{published}",

                f"LLM结果：{llm_text}",

            ]

            return "\n".join(lines)



        except Exception:

            return (

                f"投稿ID：{getattr(sub, 'id', '-')}\n"



                f"接收者：{getattr(sub, 'receiver_id', '-')}\n"



                f"发送者：{getattr(sub, 'sender_id', '-')}\n"



                f"所属组：{getattr(sub, 'group_name', '-')}\n"



                f"状态：{'未知' if not getattr(sub, 'status', None) else sub.status}"

            )

    async def _resolve_submission_id_by_any(self, raw_id: str) -> Optional[int]:

        """根据用户提供的编号解析到内部 Submission.id。



        支持两种输入：



        - 投稿ID（submissions.id）



        - 发布编号（submissions.publish_id）



        优先按投稿ID匹配，其次按发布编号匹配最近创建的一条。



        """

        try:

            num = int(str(raw_id).strip())



        except Exception:

            return None

        from core.database import get_db

        from sqlalchemy import select

        from core.models import Submission

        db = await get_db()

        async with db.get_session() as session:

            # 先按内部ID匹配

            r = await session.execute(select(Submission).where(Submission.id == num))

            sub = r.scalar_one_or_none()

            if sub:
                return int(sub.id)

            # 再按发布编号匹配，若多条则取最新创建

            try:

                r2 = await session.execute(
                    select(Submission).where(Submission.publish_id == num).order_by(Submission.created_at.desc()))

                subs = r2.scalars().all()

                if subs:
                    return int(subs[0].id)



            except Exception:

                pass

        return None

    # ===== 待通过好友过滤 =====

    def _pending_key(self, self_id: str, user_id: str) -> str:

        return f"{self_id}:{user_id}"

    def _mark_pending_friend(self, self_id: str, user_id: str, duration: float = 600.0) -> None:

        try:

            ttl = max(1.0, float(duration or 0.0))



        except Exception:

            ttl = 600.0

        expire_ts = time.time() + ttl

        self.pending_friend_map[self._pending_key(self_id, user_id)] = expire_ts

    def _is_pending_friend(self, self_id: str, user_id: str) -> bool:

        key = self._pending_key(self_id, user_id)

        expire = self.pending_friend_map.get(key)

        if not expire:
            return False

        now = time.time()

        if expire <= now:

            try:

                self.pending_friend_map.pop(key, None)



            except Exception:

                pass

            return False

        return True

    def _unmark_pending_friend(self, self_id: str, user_id: str) -> None:

        try:

            self.pending_friend_map.pop(self._pending_key(self_id, user_id), None)



        except Exception:

            pass
