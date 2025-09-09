"""RedNote (Xiaohongshu) Publisher

This publisher uses a Playwright-based API client to post image notes.
It loads cookies from configured files and publishes with a simple title/content.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from publishers.base import BasePublisher
from core.enums import PublishPlatform
from .api import RedNoteAPI, PlaywrightConfig, load_cookie_file


class RedNotePublisher(BasePublisher):
    def __init__(self, config: Dict[str, Any]):
        super().__init__("rednote_publisher", PublishPlatform.REDNOTE, config)
        self.cookies_map: Dict[str, List[Dict[str, Any]]] = {}
        self.api_clients: Dict[str, RedNoteAPI] = {}

    async def initialize(self):
        await super().initialize()
        await self._load_all_cookies_from_config()

    async def shutdown(self):
        for api in self.api_clients.values():
            try:
                await api.close()
            except Exception:
                pass
        await super().shutdown()

    async def _load_all_cookies_from_config(self):
        cfg = self._get_platform_config()
        accounts_cfg: Dict[str, Dict[str, Any]] = cfg.get('accounts') or {}
        headless = bool(cfg.get('headless', True))
        slow_mo_ms = int(cfg.get('slow_mo_ms', 0))
        user_agent = cfg.get('user_agent') or None
        pw_cfg = PlaywrightConfig(headless=headless, slow_mo_ms=slow_mo_ms, user_agent=user_agent)
        # Prefer explicit accounts mapping
        if accounts_cfg:
            for account_id, a in accounts_cfg.items():
                cookie_file = a.get('cookie_file') or f"data/cookies/rednote_{account_id}.json"
                await self.load_cookies(account_id, cookie_file, pw_cfg)
        else:
            # Fallback to mirror QQ accounts
            for acc_id in self.accounts:
                await self.load_cookies(acc_id, f"data/cookies/rednote_{acc_id}.json", pw_cfg)

    async def load_cookies(self, account_id: str, cookie_file_path: str, pw_cfg: Optional[PlaywrightConfig] = None) -> bool:
        p = Path(cookie_file_path)
        if not p.exists():
            self.logger.warning(f"RedNote cookie 文件不存在: {cookie_file_path}")
            return False
        try:
            cookies = load_cookie_file(str(p))
            if not isinstance(cookies, list) or not cookies:
                self.logger.error(f"RedNote cookie 文件格式不正确或为空: {cookie_file_path}")
                return False
            self.cookies_map[account_id] = cookies
            api = RedNoteAPI(cookies, config=pw_cfg)
            self.api_clients[account_id] = api
            self.logger.info(f"加载RedNote cookies成功: {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"加载RedNote cookies失败 {account_id}: {e}")
            return False

    async def check_login_status(self, account_id: Optional[str] = None) -> bool:
        if account_id:
            api = self.api_clients.get(account_id)
            return await api.check_login() if api else False
        ok_any = False
        for acc_id, api in self.api_clients.items():
            ok = await api.check_login()
            ok_any = ok_any or ok
            if not ok:
                self.logger.warning(f"RedNote账号未登录: {acc_id}")
        return ok_any

    def format_at(self, submission) -> str:
        # 红书不支持通过 QQ 号直接@
        return ""

    async def _load_image_bytes(self, image_path: str) -> Optional[bytes]:
        try:
            import httpx
            if image_path.startswith('http'):
                async with httpx.AsyncClient() as client:
                    r = await client.get(image_path)
                    if r.status_code == 200:
                        return r.content
            elif image_path.startswith('file://'):
                local = image_path.replace('file://', '')
                with open(local, 'rb') as f:
                    return f.read()
            else:
                p = Path(image_path)
                if p.exists():
                    return p.read_bytes()
        except Exception as e:
            self.logger.error(f"读取图片失败 {image_path}: {e}")
        return None

    async def publish(self, content: str, images: List[str] = None, **kwargs) -> Dict[str, Any]:
        account_id = kwargs.get('account_id')
        if not account_id:
            candidate_ids = sorted(self.api_clients.keys()) or sorted(self.accounts.keys())
            account_id = candidate_ids[0] if candidate_ids else None
        if not account_id:
            return {'success': False, 'error': '没有可用的小红书账号'}

        api = self.api_clients.get(account_id)
        if not api:
            return {'success': False, 'error': 'RedNote API客户端未初始化'}
        if not await api.check_login():
            return {'success': False, 'error': '小红书账号未登录或Cookie无效'}

        try:
            # Determine title from content (first line) and body from rest
            text = content or ""
            title = text.splitlines()[0][:30] if text else "校园墙"
            body = text if text else ""

            images_bytes: List[bytes] = []
            if images:
                cfg = self._get_platform_config()
                for img in images[: cfg.get('max_images_per_post', 9)]:
                    b = await self._load_image_bytes(img)
                    if b:
                        images_bytes.append(b)

            if not images_bytes:
                return {'success': False, 'error': '发布需要至少一张图片'}

            result = await api.publish_image_note(title, body, images_bytes)
            if result.get('success'):
                return {'success': True, 'url': result.get('url'), 'account_id': account_id}
            return {'success': False, 'error': result.get('message', '发布失败')}
        except Exception as e:
            self.logger.error(f"小红书发布失败: {e}")
            return {'success': False, 'error': str(e)}

    async def batch_publish(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        account_ids = list(self.api_clients.keys())
        if not account_ids:
            return [{'success': False, 'error': '没有可用的小红书账号'}] * len(items)
        for i, item in enumerate(items):
            aid = account_ids[i % len(account_ids)]
            res = await self.publish(item.get('content', ''), item.get('images') or [], account_id=aid)
            results.append(res)
        return results

