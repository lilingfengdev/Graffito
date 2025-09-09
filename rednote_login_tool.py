#!/usr/bin/env python3
"""Xiaohongshu (RedNote) interactive login tool using Playwright.

Features:
- Opens a browser window to creator.xiaohongshu.com for manual login
- Persists cookies to data/cookies/rednote_{account_id}.json (Playwright format)

Prerequisites:
  pip install playwright
  python -m playwright install chromium
"""
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

from utils import json_util as json


def prompt(msg: str) -> str:
    try:
        return input(msg)
    except EOFError:
        return ""


def ensure_cookie_dir() -> Path:
    base = Path("data/cookies")
    base.mkdir(parents=True, exist_ok=True)
    return base


async def login_and_save(account_id: str, headless: bool = False, user_agent: Optional[str] = None) -> bool:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception as e:
        print("Playwright 未安装，请先安装: pip install playwright && python -m playwright install chromium")
        return False

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, slow_mo=50 if not headless else 0)
        context = await browser.new_context(user_agent=user_agent or None)
        page = await context.new_page()
        # Go to creator home; if not logged in, user should log in manually
        await page.goto("https://creator.xiaohongshu.com/", wait_until="domcontentloaded")
        print("已打开浏览器。请在新窗口中完成登录，然后回到此处按回车继续...")
        _ = prompt("")

        # Simple check: look for text '创作中心' or avatar
        ok = False
        try:
            await page.wait_for_selector("text=创作中心", timeout=3000)
            ok = True
        except Exception:
            try:
                await page.wait_for_selector("[data-test-id='user-avatar'], img[alt*='avatar']", timeout=2000)
                ok = True
            except Exception:
                ok = False

        cookies = await context.cookies()
        cookie_path = ensure_cookie_dir() / f"rednote_{account_id}.json"
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(cookies))
        print(f"Cookies 已保存至: {cookie_path}")
        await browser.close()
        return ok


async def main():
    account_id = prompt("输入 account_id（用于保存文件名，如 qq号/自定义）: ").strip()
    if not account_id:
        print("account_id 不能为空")
        return
    headless_in = prompt("是否无头(headless)模式? y/N: ").strip().lower()
    headless = headless_in in ("y", "yes")
    ua = prompt("自定义 User-Agent（可留空）: ").strip() or None
    ok = await login_and_save(account_id, headless=headless, user_agent=ua)
    print("登录状态：", "已登录" if ok else "无法确认已登录，请稍后在发送器中重试")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")

