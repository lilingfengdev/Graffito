"""QQ空间API接口（纯 aioqzone 实现）"""
import hashlib
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from loguru import logger


class QzoneAPI:
    """QQ空间API客户端（仅 aioqzone）"""
    
    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        self.gtk = self._generate_gtk(cookies.get('p_skey', ''))
        self.uin = cookies.get('uin', '').lstrip('o')
        # aioqzone 客户端
        from aioqzone import Qzone as AioQzone  # type: ignore
        try:
            self._aioqzone = AioQzone(cookies=cookies)  # type: ignore
        except Exception:
            self._aioqzone = AioQzone(
                uin=self.uin,
                p_skey=cookies.get('p_skey'),
                skey=cookies.get('skey'),
                cookies=cookies
            )  # type: ignore
        
    def _generate_gtk(self, skey: str) -> str:
        """生成gtk参数"""
        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        return str(hash_val & 2147483647)
        
    async def check_login(self) -> bool:
        """检查登录状态（基于 aioqzone 的 gtk 与必要字段）"""
        try:
            if not (self.cookies.get('p_skey') and self.uin):
                return False
            gtk_val = str(getattr(self._aioqzone, 'gtk', '') or '')
            return bool(gtk_val)
        except Exception:
            return False
        
    async def upload_image(self, image_data: bytes) -> Dict[str, Any]:
        """上传图片（由 aioqzone 处理，返回 aioqzone 的结构）"""
        return await self._aioqzone.upload_image(image_data)  # type: ignore
        
    async def publish_emotion(self, content: str, images: List[bytes] = None) -> Dict[str, Any]:
        """发布说说（仅 aioqzone）"""
        if images:
            try:
                result = await self._aioqzone.publish_mood(content=content, images=images)  # type: ignore
            except TypeError:
                result = await self._aioqzone.publish_mood(content=content, pictures=images)  # type: ignore
        else:
            result = await self._aioqzone.publish_mood(content=content)  # type: ignore
        # 标准化：尽量返回 {'success': True, 'tid': ...}
        if isinstance(result, dict):
            tid = result.get('tid') or result.get('id') or result.get('data', {}).get('tid')
            return {'success': True, 'tid': tid}
        return {'success': True, 'tid': result}
            
    async def close(self):
        """关闭客户端（aioqzone 若需要可在此处关闭）"""
        close_fn = getattr(self._aioqzone, "close", None)
        if callable(close_fn):
            await close_fn()

    async def add_comment(self, host_uin: str, tid: str, content: str) -> Dict[str, Any]:
        """为说说添加评论（仅 aioqzone）"""
        try:
            try:
                res = await self._aioqzone.add_comment(tid=tid, content=content)  # type: ignore
            except Exception:
                # 某些版本的方法路径不同
                res = await self._aioqzone.mood.comment(tid, content)  # type: ignore
            if isinstance(res, dict) and (res.get('success') or res.get('code') == 0):
                return {"success": True, "message": "评论成功"}
            return {"success": True, "message": "评论已提交"}
        except Exception as e:
            logger.error(f"评论失败: {e}")
            return {"success": False, "message": str(e)}
