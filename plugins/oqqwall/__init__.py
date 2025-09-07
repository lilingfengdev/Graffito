"""OQQWall NoneBot core plugin

This plugin wires up services and registers matchers that bridge the
existing business logic to NoneBot events. It effectively replaces the
custom app bootstrap in main.py when running under NoneBot.
"""
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

import nonebot
from loguru import logger
from nonebot import get_driver, on_message, on_request
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    PrivateMessageEvent,
    GroupMessageEvent,
    FriendRequestEvent,
)


# Lazily constructed singletons for services
_services: Dict[str, Any] = {}


async def _ensure_dirs():
    Path("data").mkdir(exist_ok=True)
    Path("data/cache").mkdir(exist_ok=True)
    Path("data/cache/rendered").mkdir(exist_ok=True)
    Path("data/cache/numb").mkdir(exist_ok=True)
    Path("data/logs").mkdir(exist_ok=True)
    Path("data/cookies").mkdir(exist_ok=True)


async def _init_core():
    from core.database import get_db

    db = await get_db()
    ok = await db.health_check()
    if not ok:
        logger.error("数据库健康检查失败")
        return False
    return True


async def _init_services():
    from services import AuditService, SubmissionService, NotificationService

    submission_service = SubmissionService()
    audit_service = AuditService()
    notification_service = NotificationService()

    await submission_service.initialize()
    await audit_service.initialize()

    _services["submission"] = submission_service
    _services["audit"] = audit_service
    _services["notify"] = notification_service


async def _shutdown_services():
    try:
        sub = _services.get("submission")
        if sub:
            await sub.shutdown()
    except Exception as e:
        logger.error(f"关闭投稿服务失败: {e}")
    try:
        aud = _services.get("audit")
        if aud:
            await aud.shutdown()
    except Exception as e:
        logger.error(f"关闭审核服务失败: {e}")
    try:
        from core.database import close_db

        await close_db()
    except Exception as e:
        logger.error(f"关闭数据库失败: {e}")


driver = get_driver()


@driver.on_startup
async def _on_startup():
    logger.info("初始化 OQQWall (NoneBot 模式)...")
    await _ensure_dirs()
    ok = await _init_core()
    if not ok:
        logger.error("初始化失败，部分功能不可用")
        return
    await _init_services()
    logger.info("OQQWall 初始化完成 (NoneBot)")


@driver.on_shutdown
async def _on_shutdown():
    logger.info("正在关闭 OQQWall 服务 (NoneBot)")
    await _shutdown_services()
    logger.info("OQQWall 已关闭 (NoneBot)")


# ============== Matchers ==============

msg_matcher = on_message(priority=50, block=False)


@msg_matcher.handle()
async def _(bot: Bot, event: MessageEvent):
    try:
        # For group messages, prefer command handling; for private, create submission
        if isinstance(event, GroupMessageEvent):
            await _handle_group_message(bot, event)
            return
        if isinstance(event, PrivateMessageEvent):
            await _handle_private_message(bot, event)
            return
    except Exception as e:
        logger.error(f"处理消息事件失败: {e}", exc_info=True)


req_matcher = on_request(priority=50, block=False)


@req_matcher.handle()
async def _(bot: Bot, event: FriendRequestEvent):
    try:
        # 自动同意好友请求（若配置开启）
        from config import get_settings

        settings = get_settings()
        qq_cfg = settings.receivers.get("qq") or {}
        if hasattr(qq_cfg, "dict"):
            qq_cfg = qq_cfg.dict()
        elif hasattr(qq_cfg, "__dict__"):
            qq_cfg = qq_cfg.__dict__

        if qq_cfg.get("auto_accept_friend", True):
            flag = getattr(event, "flag", None)
            if flag:
                try:
                    await bot.call_api("set_friend_add_request", flag=flag, approve=True)
                except Exception as e:
                    logger.error(f"同意好友请求失败: {e}")
    except Exception as e:
        logger.error(f"处理好友请求失败: {e}")


async def _handle_private_message(bot: Bot, event: PrivateMessageEvent):
    try:
        from services.submission_service import SubmissionService

        submission: SubmissionService = _services.get("submission")
        if not submission:
            return
        user_id = str(getattr(event, "user_id", ""))
        self_id = str(getattr(bot, "self_id", ""))

        # Build message data aligned with existing pipeline expectations
        segments: List[Dict[str, Any]] = []
        try:
            for seg in event.get_message():
                try:
                    seg_data = dict(getattr(seg, "data", {}))
                except Exception:
                    seg_data = {}
                segments.append({"type": getattr(seg, "type", None), "data": seg_data})
        except Exception:
            segments = []

        data: Dict[str, Any] = {
            "post_type": "message",
            "message_type": "private",
            "user_id": user_id,
            "self_id": self_id,
            "message_id": str(getattr(event, "message_id", "")),
            "raw_message": event.get_plaintext() if hasattr(event, "get_plaintext") else str(event.get_message()),
            "message": segments,
            "time": int(getattr(event, "time", 0)),
            "sender": {"nickname": getattr(getattr(event, "sender", None), "nickname", None)},
        }
        await submission.create_submission(user_id, self_id, data)
    except Exception as e:
        logger.error(f"处理私聊消息失败: {e}", exc_info=True)


async def _handle_group_message(bot: Bot, event: GroupMessageEvent):
    try:
        # Only handle when bot is mentioned, then parse and dispatch to AuditService
        try:
            to_me = event.to_me
        except Exception:
            to_me = False
        if not to_me:
            return

        from services.audit_service import AuditService
        from services.submission_service import SubmissionService
        from services.notification_service import NotificationService

        audit: AuditService = _services.get("audit")
        submission: SubmissionService = _services.get("submission")
        notification: NotificationService = _services.get("notify")
        if not audit:
            return

        group_id = str(getattr(event, "group_id", ""))
        self_id = str(getattr(bot, "self_id", ""))

        # Reply-based ID extraction (best-effort)
        reply_sub_id: Optional[int] = None
        try:
            for seg in event.get_message():
                if getattr(seg, "type", None) == "reply":
                    rid = getattr(seg, "data", {}).get("id") or getattr(seg, "data", {}).get("message_id")
                    if rid is not None:
                        reply_sub_id = int(rid)
                        break
        except Exception:
            pass

        after_text = event.get_plaintext().strip()
        if reply_sub_id is not None and after_text:
            full_text = f"{reply_sub_id} {after_text}"
        else:
            full_text = after_text
        if not full_text:
            return

        # Resolve group_name using self_id or group_id
        group_name = None
        try:
            from config import get_settings

            settings = get_settings()
            for gname, group in settings.account_groups.items():
                if str(group.manage_group_id) == str(group_id):
                    group_name = gname
                    break
                if str(group.main_account.qq_id) == str(self_id):
                    group_name = gname
                    break
                for minor in group.minor_accounts:
                    if str(minor.qq_id) == str(self_id):
                        group_name = gname
                        break
        except Exception:
            pass
        if not group_name:
            return

        # Determine command type and call AuditService or global handlers on SubmissionService
        tokens = full_text.split()
        if not tokens:
            return
        if tokens[0].isdigit():
            submission_id = int(tokens[0])
            cmd = tokens[1] if len(tokens) > 1 else ""
            extra = " ".join(tokens[2:]) if len(tokens) > 2 else None
            result = await audit.handle_command(submission_id, cmd, str(event.user_id), extra)
            # Feedback to group
            msg = result.get("message") if isinstance(result, dict) else str(result)
            await _send_group_text(group_id, msg or "已处理")
            # Post-approve hooks
            if cmd == "是":
                try:
                    if submission:
                        await submission.publish_single_submission(submission_id)
                except Exception as e:
                    logger.error(f"审核通过后发布失败: {e}")
                try:
                    if notification:
                        await notification.send_submission_approved(submission_id)
                except Exception as e:
                    logger.error(f"审核通过后通知投稿者失败: {e}")
            if cmd == "立即":
                try:
                    if submission:
                        await submission.publish_single_submission(submission_id)
                except Exception as e:
                    logger.error(f"立即发送失败: {e}")
            return

        # Global commands: handle certain commands here to avoid legacy plugin_manager deps
        if tokens[0] in {"自动重新登录", "手动重新登录"}:
            if not submission:
                return
            try:
                publisher = submission.publishers.get("qzone") if hasattr(submission, "publishers") else None
                if not publisher:
                    await _send_group_text(group_id, "QQ空间发送器未就绪")
                    return
                # Find all accounts belonging to this group
                accounts = [
                    acc_id for acc_id, info in getattr(publisher, "accounts", {}).items()
                    if info.get("group_name") == group_name
                ]
                if not accounts:
                    await _send_group_text(group_id, "未找到本组账号")
                    return
                ok_list: List[str] = []
                fail_list: List[str] = []
                for acc in accounts:
                    try:
                        ok = await publisher.refresh_login(acc)
                        (ok_list if ok else fail_list).append(acc)
                    except Exception:
                        fail_list.append(acc)
                msg = "自动登录QQ空间尝试完毕\n" if tokens[0] == "自动重新登录" else "手动登录刷新尝试完毕\n"
                if ok_list:
                    msg += f"成功: {', '.join(ok_list)}\n"
                if fail_list:
                    msg += f"失败: {', '.join(fail_list)}"
                await _send_group_text(group_id, msg.strip())
            except Exception as e:
                await _send_group_text(group_id, f"刷新登录失败: {e}")
            return

        if tokens[0] in {"自检"}:
            try:
                from core.database import get_db

                db_ok = False
                try:
                    db = await get_db()
                    db_ok = await db.health_check()
                except Exception:
                    db_ok = False
                login_ok = False
                try:
                    if submission and hasattr(submission, "publishers"):
                        publisher = submission.publishers.get("qzone")
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
                await _send_group_text(group_id, msg)
            except Exception as e:
                await _send_group_text(group_id, f"自检失败: {e}")
            return

        # Global commands: delegate to legacy helper to reuse formatting/DB ops
        if tokens[0] in {"待处理", "删除待处理", "删除暂存区", "发送暂存区", "重渲染", "调出", "信息", "取消拉黑", "列出拉黑", "快捷回复"}:
            # Reuse existing handlers by importing and calling functions similar to receiver implementation
            from receivers.qq.nonebot_receiver import QQReceiver  # use helper methods for formatting

            fake_receiver = QQReceiver({})
            fake_receiver.audit_service = _services.get("audit")
            fake_receiver.submission_service = _services.get("submission")
            fake_receiver.notification_service = _services.get("notify")
            # Call internal method to keep behavior parity
            handled = await fake_receiver._handle_global_command(group_id, group_name, full_text)  # type: ignore
            if handled:
                return


async def _send_group_text(group_id: str, message: str) -> bool:
    try:
        # Pick any available bot
        bots = nonebot.get_bots()
        if not bots:
            return False
        bot = next(iter(bots.values()))
        try:
            gid = int(group_id)
        except Exception:
            gid = group_id
        await bot.call_api("send_group_msg", group_id=gid, message=message)
        return True
    except Exception:
        return False

