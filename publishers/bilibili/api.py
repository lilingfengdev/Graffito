"""Bilibili 动态 API 接口（纯 bilibili_api 实现）

职责：
- 使用 nemo2011 的 bilibili_api 完成图文动态所需的图片上传和发布
- 仅依赖 Credential，不保留任何 HTTP 回退逻辑
"""
import json
from typing import Any, Dict, List, Optional

from loguru import logger


class BilibiliAPI:
    """Bilibili API 客户端（仅使用 bilibili_api）"""

    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        from bilibili_api import Credential  # type: ignore
        from bilibili_api import dynamic  # type: ignore
        sessdata = cookies.get('SESSDATA') or cookies.get('sessdata')
        bili_jct = cookies.get('bili_jct') or cookies.get('csrf')
        dedeuserid = cookies.get('DedeUserID') or cookies.get('dedeuserid')
        buvid3 = cookies.get('buvid3') or cookies.get('BUVID3')
        if not (sessdata and bili_jct):
            raise RuntimeError('缺少B站必要 cookies: SESSDATA/bili_jct')
        self._bili_dynamic = dynamic
        self._bili_credential = Credential(sessdata=sessdata, bili_jct=bili_jct, dedeuserid=dedeuserid, buvid3=buvid3)

    def _get_csrf(self) -> Optional[str]:
        csrf = self.cookies.get('bili_jct') or self.cookies.get('csrf')
        return csrf

    async def check_login(self) -> bool:
        # 轻量检查：存在关键 cookie 即视为登录
        return bool(self.cookies.get('SESSDATA') and self._get_csrf())

    async def upload_image(self, image_bytes: bytes, category: str = 'daily') -> Dict[str, Any]:
        """上传图片到B站（bilibili_api）。"""
        # dynamic.upload_image
        up_res = await self._bili_dynamic.upload_image(image_bytes, credential=self._bili_credential)
        return up_res if isinstance(up_res, dict) else {'img_src': up_res}

    async def create_draw_dynamic(self, content: str, pictures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """发布图文动态。pictures: [{img_src,width,height}...]（bilibili_api）。"""
        res = await self._bili_dynamic.create_draw_dynamic(
            content=content or '',
            pictures=pictures,
            credential=self._bili_credential
        )
        if isinstance(res, dict):
            return {'success': True, 'dynamic_id': res.get('dynamic_id') or res.get('data', {}).get('dynamic_id')}
        return {'success': True, 'dynamic_id': res}

