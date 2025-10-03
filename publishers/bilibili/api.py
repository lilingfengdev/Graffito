"""Bilibili 动态 API 接口（基于 nemo2011/bilibili-api v17）

职责：
- 使用 bilibili_api 的 BuildDynamic/send_dynamic 流程完成图文动态发布
- 统一封装评论与删除动态行为
"""
from typing import Any, Dict, List, Optional

from io import BytesIO
from loguru import logger

# Early import of third-party bilibili_api to avoid runtime imports
from bilibili_api import Credential  # type: ignore
from bilibili_api import dynamic  # type: ignore
from bilibili_api import comment as bili_comment  # type: ignore
from bilibili_api.comment import CommentResourceType  # type: ignore
from bilibili_api.utils.picture import Picture  # type: ignore


class BilibiliAPI:
    """Bilibili API 客户端（bilibili_api v17）"""

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

    async def upload_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """上传图片至 B 站，返回标准化结构。

        注意：v17 推荐通过 BuildDynamic 传入 Picture 列表，send_dynamic 内部会执行上传。
        此函数提供给少量需要单独上传的场景。
        """
        try:
            # 尝试用 Pillow 推断格式
            from PIL import Image  # type: ignore
            with Image.open(BytesIO(image_bytes)) as img:
                fmt = (img.format or 'JPEG').lower().replace('jpeg', 'jpg')
        except Exception:
            fmt = 'jpg'

        pic = Picture.from_content(image_bytes, fmt)
        res = await self._bili_dynamic.upload_image(pic, credential=self._bili_credential)
        # 返回统一字段
        if isinstance(res, dict):
            return {
                'image_url': res.get('image_url') or res.get('img_src') or res.get('url'),
                'image_width': res.get('image_width') or res.get('width'),
                'image_height': res.get('image_height') or res.get('height'),
            }
        return {'image_url': res}

    async def create_draw_dynamic(self, content: str, images_bytes: List[bytes]) -> Dict[str, Any]:
        """发布图文动态（使用 BuildDynamic + send_dynamic）。

        Args:
            content: 文本内容
            images_bytes: 图片字节列表
        Returns:
            {'success': True, 'dynamic_id': int} 或 {'success': False, 'message': str}
        """
        try:
            pics: List[Picture] = []
            for b in images_bytes or []:
                try:
                    from PIL import Image  # type: ignore
                    with Image.open(BytesIO(b)) as img:
                        fmt = (img.format or 'JPEG').lower().replace('jpeg', 'jpg')
                except Exception:
                    fmt = 'jpg'
                pics.append(Picture.from_content(b, fmt))

            # 让 send_dynamic 自行完成图片上传
            builder = dynamic.BuildDynamic.create_by_args(text=content or '', pics=pics)
            res = await dynamic.send_dynamic(builder, credential=self._bili_credential)
            # 兼容多种返回结构
            if isinstance(res, dict):
                dyn_id = (
                    res.get('dyn_id')
                    or res.get('dynamic_id')
                    or (res.get('data', {}) if isinstance(res.get('data'), dict) else {}).get('dynamic_id')
                )
                if dyn_id:
                    return {'success': True, 'dynamic_id': int(dyn_id)}
                # 某些情况下返回 {code:0,...}
                code = res.get('code')
                if code == 0:
                    # 无法直接取到 ID，但也视为成功
                    return {'success': True}
                return {'success': False, 'message': res.get('message') or res.get('msg') or '发布失败'}
            # 其他返回，视作成功但无 ID
            return {'success': True}
        except Exception as e:
            logger.error(f"B站发布失败: {e}")
            return {'success': False, 'message': str(e)}

    async def add_comment(self, dynamic_id: int, message: str) -> Dict[str, Any]:
        """为指定动态添加评论。

        在 v17 中，评论动态通常需要将 dynamic_id 映射为评论所需的 rid。
        """
        try:
            dyn = dynamic.Dynamic(int(dynamic_id), credential=self._bili_credential)
            rid = await dyn.get_rid()
            await bili_comment.send_comment(
                text=message,
                oid=int(rid),
                type_=CommentResourceType.DYNAMIC,
                credential=self._bili_credential,
            )
            return {'success': True, 'message': '已评论'}
        except Exception as e:
            logger.error(f"B站评论失败: {e}")
            return {'success': False, 'message': str(e)}

    async def delete_dynamic(self, dynamic_id: int) -> Dict[str, Any]:
        """删除一条动态（使用 Dynamic.delete）。"""
        try:
            dyn = dynamic.Dynamic(int(dynamic_id), credential=self._bili_credential)
            res = await dyn.delete()
            if isinstance(res, dict):
                code = res.get('code')
                if code is None or code == 0:
                    return {'success': True, 'message': '已删除'}
                return {'success': False, 'message': res.get('message') or res.get('msg') or '删除失败'}
            return {'success': True, 'message': '已删除'}
        except Exception as e:
            logger.error(f"B站删除动态失败: {e}")
            return {'success': False, 'message': str(e)}

    async def get_comments(self, dynamic_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取动态的评论列表。
        
        Args:
            dynamic_id: 动态ID
            page: 页码（从1开始）
            page_size: 每页数量
        Returns:
            {'success': True, 'comments': [...], 'total': int} 或 {'success': False, 'message': str}
        """
        try:
            dyn = dynamic.Dynamic(int(dynamic_id), credential=self._bili_credential)
            rid = await dyn.get_rid()
            
            # 使用 comment 模块获取评论列表
            comments_data = await bili_comment.get_comments(
                oid=int(rid),
                type_=CommentResourceType.DYNAMIC,
                page_index=page,
                credential=self._bili_credential
            )
            
            # 格式化评论数据
            comments_list = []
            if isinstance(comments_data, dict):
                replies = comments_data.get('replies') or []
                for reply in replies:
                    if not isinstance(reply, dict):
                        continue
                    member = reply.get('member') or {}
                    content_data = reply.get('content') or {}
                    
                    # B站头像字段可能是 'avatar' 或 'face'
                    user_avatar = member.get('avatar') or member.get('face') or ''
                    
                    comments_list.append({
                        'id': reply.get('rpid'),
                        'user_id': member.get('mid'),
                        'user_name': member.get('uname'),
                        'user_avatar': user_avatar,
                        'content': content_data.get('message', ''),
                        'like_count': reply.get('like', 0),
                        'reply_count': reply.get('rcount', 0),
                        'created_at': reply.get('ctime'),
                    })
                
                total = comments_data.get('page', {}).get('count', 0) if isinstance(comments_data.get('page'), dict) else len(comments_list)
                
                return {
                    'success': True,
                    'comments': comments_list,
                    'total': total,
                    'page': page,
                    'page_size': page_size
                }
            
            return {'success': True, 'comments': [], 'total': 0}
        except Exception as e:
            logger.error(f"B站获取评论失败: {e}")
            return {'success': False, 'message': str(e)}

