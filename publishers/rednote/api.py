"""Xiaohongshu (RedNote) web automation API via Playwright.

This module implements a minimal API client using Playwright to:
 - load and persist cookies
 - verify login by checking creator page
 - upload images and publish a new note (图文)

The implementation intentionally avoids private HTTP APIs and instead uses
stable creator web UI flows, making it resilient to minor API changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncio
from loguru import logger

from utils import json_util as json


CREATOR_HOME_URL = "https://creator.xiaohongshu.com/"
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


@dataclass
class PlaywrightConfig:
    headless: bool = True
    slow_mo_ms: int = 0
    user_agent: Optional[str] = None


class RedNoteAPI:
    """Playwright-driven automation for Xiaohongshu creator publishing."""

    def __init__(self, cookies: List[Dict[str, Any]], config: Optional[PlaywrightConfig] = None):
        self.cookies = cookies
        self.cfg = config or PlaywrightConfig()
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self):
        if self._browser:
            return
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception as e:
            raise RuntimeError("Playwright not installed. Please install playwright and browsers.") from e

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.cfg.headless, slow_mo=self.cfg.slow_mo_ms)
        ua = self.cfg.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        self._context = await self._browser.new_context(user_agent=ua)
        if self.cookies:
            try:
                await self._context.add_cookies(self.cookies)
            except Exception as e:
                logger.warning(f"Failed to add cookies to context: {e}")
        self._page = await self._context.new_page()

    async def close(self):
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if getattr(self, "_pw", None):
                await self._pw.stop()  # type: ignore
        except Exception:
            pass

    async def export_cookies(self) -> List[Dict[str, Any]]:
        if not self._context:
            return self.cookies
        try:
            return await self._context.cookies()
        except Exception:
            return self.cookies

    async def check_login(self) -> bool:
        await self._ensure_browser()
        assert self._page is not None
        try:
            await self._page.goto(CREATOR_HOME_URL, wait_until="domcontentloaded")
            # Heuristic: creator home shows element with text like "创作中心" or avatar menu
            # Check for any known element to confirm we are logged in; otherwise creator will redirect to login.
            try:
                await self._page.wait_for_selector("text=创作中心", timeout=5000)
                return True
            except Exception:
                # Try avatar
                try:
                    await self._page.wait_for_selector("[data-test-id='user-avatar'], img[alt*='avatar']", timeout=3000)
                    return True
                except Exception:
                    return False
        except Exception as e:
            logger.error(f"RedNote check_login failed: {e}")
            return False

    async def publish_image_note(self, title: str, content: str, images: List[bytes]) -> Dict[str, Any]:
        """Publish an image note with given title, content and raw image bytes list."""
        await self._ensure_browser()
        assert self._page is not None
        try:
            await self._page.goto(PUBLISH_URL, wait_until="domcontentloaded")
            # Wait editor ready: look for upload button or dropzone
            # Common selector in creator publish flow (may change, so keep fallbacks)
            upload_input = None
            try:
                upload_input = await self._page.wait_for_selector("input[type='file']", timeout=10000)
            except Exception:
                pass
            if not upload_input:
                # Try clicking an upload area to reveal input
                try:
                    await self._page.click("text=上传", timeout=5000)
                    upload_input = await self._page.wait_for_selector("input[type='file']", timeout=5000)
                except Exception:
                    pass
            if not upload_input:
                return {"success": False, "message": "Upload input not found"}

            # Write image bytes to temp files for upload
            tmp_dir = Path("data/cache/rednote_uploads")
            tmp_dir.mkdir(parents=True, exist_ok=True)
            file_paths: List[str] = []
            for idx, img in enumerate(images[:9]):
                fp = tmp_dir / f"up_{asyncio.get_event_loop().time():.0f}_{idx}.jpg"
                fp.write_bytes(img)
                file_paths.append(str(fp))

            await upload_input.set_input_files(file_paths)

            # Title and content selectors (best-effort, may vary)
            # Try typical placeholders
            try:
                title_locator = await self._page.wait_for_selector("input[placeholder*='标题'], textarea[placeholder*='标题']", timeout=5000)
                await title_locator.fill(title[:30])
            except Exception:
                pass

            try:
                content_locator = await self._page.wait_for_selector("textarea, div[contenteditable='true']", timeout=5000)
                await content_locator.fill(content[:1000])
            except Exception:
                pass

            # Publish button
            # Try multiple candidates
            published = False
            for selector in [
                "button:has-text('发布')",
                "[data-test-id='publish-button']",
                "button[type='submit']",
            ]:
                try:
                    await self._page.click(selector, timeout=5000)
                    published = True
                    break
                except Exception:
                    continue

            if not published:
                return {"success": False, "message": "Publish button not found"}

            # Wait for navigation or success toast
            try:
                await self._page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            # Heuristic success: URL change back to creator home or presence of "发布成功"
            url = self._page.url
            if "publish" not in url:
                return {"success": True, "url": url}
            try:
                await self._page.wait_for_selector("text=发布成功", timeout=5000)
                return {"success": True}
            except Exception:
                return {"success": True, "message": "Published, but success could not be confirmed"}
        except Exception as e:
            logger.error(f"RedNote publish failed: {e}")
            return {"success": False, "message": str(e)}


def load_cookie_file(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
        # Support list format or Netscape export style transformed to list of dicts
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and data.get("cookies"):
            return data.get("cookies")  # {cookies: [...]} format
        # try Chrome cookie JSON array of {name,value,domain,path,expires}
        if isinstance(data, dict):
            # Convert dict of {name: value} to list of cookie dicts (domain-less)
            return [{"name": k, "value": v} for k, v in data.items()]
        return []
    except Exception as e:
        logger.error(f"Failed to load cookies: {e}")
        return []


def save_cookie_file(path: str, cookies: List[Dict[str, Any]]):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(json.dumps(cookies))

