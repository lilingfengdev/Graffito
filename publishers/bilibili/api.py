"""Bilibili 动态 API 接口（纯 bilibili_api 实现）

职责：
- 使用 nemo2011 的 bilibili_api 完成图文动态所需的图片上传和发布
- 仅依赖 Credential，不保留任何 HTTP 回退逻辑
"""
from typing import Any, Dict, List, Optional

from loguru import logger

# Early import of third-party bilibili_api to avoid runtime imports
from bilibili_api import Credential  # type: ignore
from bilibili_api import dynamic  # type: ignore
from bilibili_api import comment as bili_comment  # type: ignore
try:
    # 16.x版本
    from bilibili_api.comment import CommentResourceType  # type: ignore
except Exception:  # pragma: no cover
    CommentResourceType = None  # type: ignore


class BilibiliAPI:
    """Bilibili API 客户端（仅使用 bilibili_api）"""

    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
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

    async def add_comment(self, dynamic_id: int, message: str) -> Dict[str, Any]:
        """为指定动态添加评论。"""
        try:
            oid = int(dynamic_id)
        except Exception:
            return {'success': False, 'message': '无效的动态ID'}

        try:
            if CommentResourceType is not None:
                await bili_comment.send_comment(
                    resource_type=CommentResourceType.DYNAMIC,
                    oid=oid,
                    message=message,
                    credential=self._bili_credential
                )
            else:
                # 回退：某些版本为枚举值常量 11 表示动态
                await bili_comment.send_comment(11, oid, message, credential=self._bili_credential)  # type: ignore[arg-type]
            return {'success': True, 'message': '已评论'}
        except Exception as e:
            logger.error(f"B站评论失败: {e}")
            return {'success': False, 'message': str(e)}

    async def delete_dynamic(self, dynamic_id: int) -> Dict[str, Any]:
        """删除一条动态。

        依赖 bilibili_api 的 dynamic.delete 动态删除接口；不同版本 API 可能差异，做必要的兼容。
        """
        try:
            oid = int(dynamic_id)
        except Exception:
            return {'success': False, 'message': '无效的动态ID'}

        try:
            # 新版 bilibili_api 提供 dynamic.delete_dynamic / delete
            delete_fn = getattr(self._bili_dynamic, 'delete_dynamic', None)
            if callable(delete_fn):
                await delete_fn(oid, credential=self._bili_credential)  # type: ignore[arg-type]
                return {'success': True, 'message': '已删除'}
            # 回退：某些版本为 delete
            delete_fn2 = getattr(self._bili_dynamic, 'delete', None)
            if callable(delete_fn2):
                await delete_fn2(oid, credential=self._bili_credential)  # type: ignore[arg-type]
                return {'success': True, 'message': '已删除'}
            return {'success': False, 'message': '当前 bilibili_api 版本不支持删除动态'}
        except Exception as e:
            logger.error(f"B站删除动态失败: {e}")
            return {'success': False, 'message': str(e)}

