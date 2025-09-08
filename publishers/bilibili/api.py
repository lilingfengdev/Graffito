"""Bilibili 动态 API 接口

优先使用 nemo2011 的 bilibili_api 库（Credential + 动态发布）。
若库不可用或失败，则回退到原先基于 HTTP 的实现。
"""
import json
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class BilibiliAPI:
    """Bilibili API 客户端（发布图文动态），带 bilibili_api 优先实现"""

    # 回退端点
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

        # bilibili_api 适配
        self._bili_dynamic = None
        self._bili_credential = None
        try:
            from bilibili_api import Credential  # type: ignore
            from bilibili_api import dynamic  # type: ignore
            # 构建 Credential（至少需要 sessdata 和 bili_jct，且优选 buvid3）
            sessdata = cookies.get('SESSDATA') or cookies.get('sessdata')
            bili_jct = cookies.get('bili_jct') or cookies.get('csrf')
            dedeuserid = cookies.get('DedeUserID') or cookies.get('dedeuserid')
            buvid3 = cookies.get('buvid3') or cookies.get('BUVID3')
            if sessdata and bili_jct:
                cred = Credential(sessdata=sessdata, bili_jct=bili_jct, dedeuserid=dedeuserid, buvid3=buvid3)
                self._bili_credential = cred
                self._bili_dynamic = dynamic
        except Exception:
            self._bili_dynamic = None
            self._bili_credential = None

    def _get_csrf(self) -> Optional[str]:
        csrf = self.cookies.get('bili_jct') or self.cookies.get('csrf')
        return csrf

    async def check_login(self) -> bool:
        # 轻量检查：存在关键 cookie 即视为登录
        return bool(self.cookies.get('SESSDATA') and self._get_csrf())

    async def upload_image(self, image_bytes: bytes, category: str = 'daily') -> Dict[str, Any]:
        """上传图片到B站，优先使用 bilibili_api；失败回退 HTTP。"""
        # bilibili_api 优先：dynamic.upload_image
        if self._bili_dynamic and self._bili_credential:
            try:
                # 返回对象中一般含有 img_src/width/height
                up_res = await self._bili_dynamic.upload_image(image_bytes, credential=self._bili_credential)
                if isinstance(up_res, dict) and (up_res.get('img_src') or up_res.get('image_url')):
                    return up_res
            except Exception as e:
                logger.warning(f"bilibili_api 上传图片失败，回退HTTP: {e}")

        # HTTP 回退
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
        """发布图文动态。pictures: [{img_src,width,height}...]。优先使用 bilibili_api。"""
        # bilibili_api 优先：dynamic.create_draw_dynamic
        if self._bili_dynamic and self._bili_credential:
            try:
                res = await self._bili_dynamic.create_draw_dynamic(
                    content=content or '',
                    pictures=pictures,
                    credential=self._bili_credential
                )
                # 期望 res 为 dict，成功时包含 dynamic_id 或 code == 0
                if isinstance(res, dict):
                    if res.get('dynamic_id') or res.get('code') == 0:
                        return {'success': True, 'dynamic_id': res.get('dynamic_id') or res.get('data', {}).get('dynamic_id')}
                # 未明确定义，但未错也视为成功
                return {'success': True, 'dynamic_id': res}
            except Exception as e:
                logger.warning(f"bilibili_api 发布动态失败，回退HTTP: {e}")

        # HTTP 回退
        csrf = self._get_csrf()
        if not csrf:
            raise RuntimeError('缺少 CSRF Token')
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

