"""Bilibili 动态 API 接口"""
import json
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class BilibiliAPI:
    """Bilibili API 客户端（发布图文动态）"""

    # 端点（参考 SocialSisterYi 文档/社区实践）
    UPLOAD_IMAGE_URL = "https://api.bilibili.com/x/dynamic/feed/draw/upload_bfs"
    CREATE_DYNAMIC_URL = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/create"

    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        self.client = httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://t.bilibili.com/'
            },
            cookies=cookies,
            timeout=30
        )

    def _get_csrf(self) -> Optional[str]:
        # 优先取 bili_jct
        csrf = self.cookies.get('bili_jct') or self.cookies.get('csrf')
        return csrf

    async def check_login(self) -> bool:
        # 轻量检查：存在关键 cookie 即视为登录
        return bool(self.cookies.get('SESSDATA') and self._get_csrf())

    async def upload_image(self, image_bytes: bytes, category: str = 'daily') -> Dict[str, Any]:
        """上传图片到B站，返回 {image_url, width, height} 等"""
        csrf = self._get_csrf()
        if not csrf:
            raise RuntimeError('缺少 CSRF Token')

        files = {'file_up': ('image.jpg', image_bytes, 'image/jpeg')}
        data = {'category': category, 'csrf': csrf}

        resp = await self.client.post(self.UPLOAD_IMAGE_URL, data=data, files=files)
        if resp.status_code != 200:
            raise RuntimeError(f'图片上传失败 HTTP {resp.status_code}')
        try:
            j = resp.json()
        except Exception:
            raise RuntimeError('图片上传返回解析失败')
        if j.get('code') != 0:
            raise RuntimeError(f"图片上传失败: {j}")
        return j.get('data') or {}

    async def create_draw_dynamic(self, content: str, pictures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """发布图文动态。pictures: [{img_src,width,height}...]"""
        csrf = self._get_csrf()
        if not csrf:
            raise RuntimeError('缺少 CSRF Token')

        # 构造 payload（图文 type 通常为 2；content 传文本；pictures 为 JSON 字符串）
        payload = {
            'dynamic_id': 0,
            'type': 2,
            'rid': 0,
            'content': content or '',
            'pictures': json.dumps(pictures, ensure_ascii=False),
            'csrf_token': csrf,
            'csrf': csrf
        }

        resp = await self.client.post(self.CREATE_DYNAMIC_URL, data=payload)
        if resp.status_code != 200:
            return {'success': False, 'message': f'HTTP {resp.status_code}'}
        try:
            j = resp.json()
        except Exception:
            return {'success': False, 'message': '返回解析失败'}
        if j.get('code') == 0:
            return {'success': True, 'dynamic_id': j.get('data', {}).get('dynamic_id', 0)}
        return {'success': False, 'message': j.get('message', '发布失败'), 'code': j.get('code')}

    async def close(self):
        await self.client.aclose()

