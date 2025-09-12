#!/usr/bin/env python3
"""Xiaohongshu (RedNote) interactive login tool using Playwright.

Features:
- Opens a browser window to creator.xiaohongshu.com for manual login
- Directly import cookies from string/JSON and optionally validate
- Persists cookies to data/cookies/rednote_{account_id}.json (Playwright format)

Prerequisites:
  pip install playwright
  python -m playwright install chromium
"""
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

import orjson


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
        cookie_path.write_bytes(orjson.dumps(cookies))
        print(f"Cookies 已保存至: {cookie_path}")
        await browser.close()
        return ok


def _standardize_domain_path(cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not (name and value):
            continue
        cookie = dict(c)
        # Provide default domain/path if missing (Playwright requires either url or domain+path)
        if not cookie.get("domain") and not cookie.get("url"):
            cookie["domain"] = ".xiaohongshu.com"
        if not cookie.get("path") and not cookie.get("url"):
            cookie["path"] = "/"
        out.append(cookie)
    return out


def parse_cookie_input(raw: str) -> List[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return []
    # Try JSON first
    try:
        import json as _json
        obj = _json.loads(raw)
        if isinstance(obj, list):
            # Expect list of cookie dicts
            return _standardize_domain_path(obj)
        if isinstance(obj, dict):
            # Formats: {cookies: [...]}, or {name: value} map
            if isinstance(obj.get("cookies"), list):
                return _standardize_domain_path(obj["cookies"])  # type: ignore[index]
            # dict of name->value
            pairs = [{"name": k, "value": v} for k, v in obj.items()]
            return _standardize_domain_path(pairs)
    except Exception:
        pass

    # Fallback: cookie string like "key=val; key2=val2"
    pairs: List[Dict[str, Any]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        pairs.append({"name": k.strip(), "value": v.strip(), "domain": ".xiaohongshu.com", "path": "/"})
    return _standardize_domain_path(pairs)


async def import_cookie_and_save(account_id: str, validate: bool = True) -> bool:
    raw = prompt("粘贴 Cookie 或 JSON: ")
    cookies = parse_cookie_input(raw)
    if not cookies:
        print("未解析到有效 Cookie")
        return False

    # Optionally validate via Playwright and export normalized cookies
    if validate:
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception:
            print("未安装 Playwright，跳过验证。将直接保存。")
        else:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context()
                try:
                    await context.add_cookies(cookies)
                except Exception as e:
                    print(f"添加 Cookie 到浏览器失败: {e}. 将尝试直接保存。")
                page = await context.new_page()
                try:
                    await page.goto("https://creator.xiaohongshu.com/", wait_until="domcontentloaded")
                    # Heuristic check
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
                    await browser.close()
                    cookie_path = ensure_cookie_dir() / f"rednote_{account_id}.json"
                    cookie_path.write_bytes(orjson.dumps(cookies))
                    print(f"Cookies 已保存至: {cookie_path}")
                    return ok
                except Exception as e:
                    await browser.close()
                    print(f"验证失败: {e}. 将直接保存未验证的 Cookies。")

    # Save as-is (unverified)
    cookie_path = ensure_cookie_dir() / f"rednote_{account_id}.json"
    cookie_path.write_bytes(orjson.dumps(cookies))
    print(f"Cookies 已保存至: {cookie_path}")
    return True


async def main():
    account_id = prompt("输入 account_id（用于保存文件名，如 qq号/自定义）: ").strip()
    if not account_id:
        print("account_id 不能为空")
        return

    while True:
        print("\n选择操作：")
        print("1) 浏览器登录并保存")
        print("2) 导入 Cookie 并保存")
        print("3) 退出")
        choice = prompt("输入选项: ").strip()
        if choice == "1":
            headless_in = prompt("是否无头(headless)模式? y/N: ").strip().lower()
            headless = headless_in in ("y", "yes")
            ua = prompt("自定义 User-Agent（可留空）: ").strip() or None
            ok = await login_and_save(account_id, headless=headless, user_agent=ua)
            print("登录状态：", "已登录" if ok else "无法确认已登录，请稍后在发送器中重试")
        elif choice == "2":
            validate_in = prompt("保存前是否验证 Cookie? Y/n: ").strip().lower()
            validate = validate_in not in ("n", "no")
            ok = await import_cookie_and_save(account_id, validate=validate)
            print("验证状态：", "有效(或已保存)" if ok else "未验证或无效")
        elif choice == "3":
            break
        else:
            print("无效选项")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")

