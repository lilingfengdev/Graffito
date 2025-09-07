#!/usr/bin/env python3
"""
NoneBot entrypoint for OQQWall.
This boots the NoneBot driver, registers OneBot v11 adapter,
loads our core plugin, and runs the server.
"""
import os
import sys
from loguru import logger


def configure_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        "data/logs/oqqwall_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
    )


def setup_env_from_settings():
    # Lazy import to avoid heavy modules before logging configured
    from config import get_settings

    settings = get_settings()

    # Driver host/port
    os.environ.setdefault("DRIVER", "~fastapi")
    os.environ.setdefault("HOST", str(settings.server.host))
    os.environ.setdefault("PORT", str(settings.server.port))

    # OneBot access token (optional)
    try:
        qq_cfg = settings.receivers.get("qq") or {}
        if hasattr(qq_cfg, "dict"):
            qq_cfg = qq_cfg.dict()
        elif hasattr(qq_cfg, "__dict__"):
            qq_cfg = qq_cfg.__dict__
        access_token = qq_cfg.get("access_token")
        if access_token:
            os.environ.setdefault("ONEBOT_ACCESS_TOKEN", str(access_token))
            os.environ.setdefault("ONEBOT_V11_ACCESS_TOKEN", str(access_token))
    except Exception:
        pass


def main():
    configure_logging()
    setup_env_from_settings()

    import nonebot
    from nonebot import get_driver
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

    nonebot.init()
    driver = get_driver()
    driver.register_adapter(OneBotV11Adapter)

    # Load plugins
    nonebot.load_plugins(["plugins.oqqwall"])  # core plugin

    # Optional: expose health endpoint here if needed by deployments
    try:
        app = nonebot.get_asgi()
        from fastapi import FastAPI

        if isinstance(app, FastAPI):
            @app.get("/health")  # type: ignore
            async def _health():
                return {"status": "healthy", "app": "oqqwall"}
    except Exception:
        pass

    nonebot.run()


if __name__ == "__main__":
    main()

