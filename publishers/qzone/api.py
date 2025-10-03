"""QQ空间API接口封装

支持两种驱动：
- aioqzone（默认）：基于 aioqzone.h5 API 直连
- ooqzone：封装 publishers.qzone.ooqzone 中的实现

通过平台配置 `publishers.qzone.driver` 选择，默认为 aioqzone。
"""
from typing import Any, Dict, List, Optional, Sequence, Union
from tenacity import RetryError
import re

from loguru import logger

from qqqr.utils.net import ClientAdapter
from aioqzone.exception import QzoneError
from aioqzone.api.h5.model import QzoneH5API
from aioqzone.api.login import ConstLoginMan
from aioqzone.model.api.request import PhotoData
from utils.common import get_platform_config

# QzEmoji 用于转换 QQ 空间表情符号
try:
    import qzemoji as qe
    qe.enable_auto_update = False
    QZEMOJI_AVAILABLE = True
except ImportError:
    logger.warning("qzemoji 未安装，QQ空间评论中的表情符号将不会被转换")
    QZEMOJI_AVAILABLE = False


async def _process_qzone_emoji(content: str) -> str:
    """处理 QQ 空间评论中的表情符号，转换为可读文本或 emoji
    
    Args:
        content: 原始评论内容，可能包含 [em]e113[/em] 格式的表情符号
    
    Returns:
        处理后的内容，表情符号已被转换为文本或 emoji
    
    Examples:
        "[em]e113[/em][em]e150[/em] nn" -> "😊😃 nn"
        "[em]e100[/em]" -> "微笑"
    """
    if not QZEMOJI_AVAILABLE or not content:
        return content
    
    # 匹配 [em]e数字[/em] 格式的表情符号
    emoji_pattern = r'\[em\]e(\d+)\[/em\]'
    
    async def replace_emoji(match):
        """异步替换单个表情符号"""
        emoji_id = int(match.group(1))
        try:
            # 查询表情符号对应的文本或 emoji
            emoji_text = await qe.query(emoji_id)
            if emoji_text:
                return emoji_text
            # 如果未找到，保留原始格式
            return match.group(0)
        except Exception as e:
            logger.debug(f"转换表情符号 {emoji_id} 失败: {e}")
            return match.group(0)
    
    # 找到所有匹配项
    matches = list(re.finditer(emoji_pattern, content))
    if not matches:
        return content
    
    # 异步处理所有表情符号
    result = content
    # 从后向前替换，避免索引变化影响
    for match in reversed(matches):
        replacement = await replace_emoji(match)
        result = result[:match.start()] + replacement + result[match.end():]
    
    return result


class AioQzoneAPI:
    """基于 aioqzone H5 的 Qzone API 客户端"""

    def __init__(self, cookies: Dict[str, str]):
        self.cookies: Dict[str, str] = cookies
        uin_str = cookies.get("uin") or cookies.get("p_uin") or ""
        uin_str = uin_str.lstrip("oO")
        try:
            self.uin: int = int(uin_str) if uin_str else 0
        except Exception:
            self.uin = 0

        self._client = ClientAdapter()
        self._login = ConstLoginMan(uin=self.uin, cookie=self.cookies)
        self._api = QzoneH5API(client=self._client, loginman=self._login)

    async def check_login(self) -> bool:
        """检查登录状态：
        - 必须存在 `p_skey` 且能计算出 gtk
        - 通过调用需要登录态的接口进行校验（`mfeeds_get_count`）
        """
        try:
            if not (self.cookies.get("p_skey") and self.uin):
                return False
            if self._login.gtk == 0:
                return False
            # 通过需要登录态的接口校验；遇到登录失效相关错误视为未登录
            try:
                await self._api.mfeeds_get_count()
            except (RetryError, QzoneError):
                return False
            except Exception:
                # 网络或解析问题时回退轻触发 index 刷新 qzonetoken，但不强制失败
                try:
                    await self._api.index()
                except Exception:
                    pass
            return True
        except Exception:
            return False

    async def publish_emotion(self, content: str, images: Optional[List[bytes]] = None) -> Dict[str, Any]:
        """发布说说，支持可选图片（bytes 列表）。

        仅当返回包含有效 tid/fid 时才视为成功。
        """
        try:
            photos: Sequence[PhotoData] = []
            if images:
                # 1) 上传图片，获得 UploadPicResponse 列表
                upload_results = []
                for img in images:
                    try:
                        r = await self._api.upload_pic(img)
                        upload_results.append(r)
                    except QzoneError as e:
                        # 对登录失效类错误直接抛出，由上层处理重登
                        if int(getattr(e, "code", 0)) in (-100, -3000, -10000):
                            raise
                        logger.error(f"上传图片失败，跳过一张: {e}")
                    except RetryError:
                        # 自动重试已失败（通常因登录问题），交由上层处理
                        raise
                    except Exception as e:
                        logger.error(f"上传图片失败，跳过一张: {e}")

                # 2) 预上传，获得 PicInfo 列表
                if upload_results:
                    pre = await self._api.preupload_photos(upload_results)
                    photos = [PhotoData.from_PicInfo(p) for p in pre.photos]

            # 3) 发表说说
            resp = await self._api.publish_mood(content=content, photos=list(photos) if photos else None)
            tid = getattr(resp, "fid", None) or getattr(resp, "tid", None)
            if tid:
                try:
                    logger.info(f"Qzone 发布成功: tid={tid} uin={self.uin}")
                except Exception:
                    pass
                return {"success": True, "tid": str(tid)}
            # 无 tid 视为失败
            try:
                snippet = str(resp)[:200]
            except Exception:
                snippet = "<unknown>"
            logger.error(f"Qzone 发布失败：未返回tid，响应片段: {snippet}")
            return {"success": False, "message": "未返回tid，发布失败"}
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return {"success": False, "message": str(e)}

    async def add_comment(self, host_uin: Union[str, int], tid: str, content: str) -> Dict[str, Any]:
        """为说说添加评论（H5 接口）。"""
        try:
            ownuin = int(host_uin) if not isinstance(host_uin, int) else host_uin
            res = await self._api.add_comment(ownuin=ownuin, fid=tid, appid=311, content=content, private=False)
            return {"success": True, "message": "评论成功"}
        except Exception as e:
            logger.error(f"评论失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_mood(self, tid: str) -> Dict[str, Any]:
        """删除一条说说（H5 接口）。"""
        try:
            res = await self._api.delete_ugc(fid=tid, appid=311)
            return {"success": True, "message": "已删除"}
        except Exception as e:
            logger.error(f"删除说说失败: {e}")
            return {"success": False, "message": str(e)}

    async def get_comments(self, tid: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取说说的评论列表。
        
        Args:
            tid: 说说ID (fid)
            page: 页码（从1开始）
            page_size: 每页数量（注意：实际返回数量由QZone接口决定）
        Returns:
            {'success': True, 'comments': [...], 'total': int} 或 {'success': False, 'message': str}
        """
        try:
            # 使用 shuoshuo 方法获取说说详情，其中包含评论数据
            # 参数顺序：fid, uin, appid（位置参数）
            detail = await self._api.shuoshuo(tid, self.uin, 311)
            
            comments_list = []
            if hasattr(detail, 'comment') and detail.comment:
                comment_data = detail.comment
                total = getattr(comment_data, 'num', 0)
                
                # 获取评论列表
                comment_items = getattr(comment_data, 'comments', []) or []
                for item in comment_items:
                    if not item:
                        continue
                    user_info = getattr(item, 'user', None)
                    user_uin = getattr(user_info, 'uin', '') if user_info else ''
                    
                    # 构造QQ空间头像URL
                    # 格式: https://qlogo2.store.qq.com/qzone/{QQ号}/{QQ号}/100
                    user_avatar = ''
                    if user_uin:
                        # 移除可能的前缀（如 'o' 或 'O'）
                        clean_uin = str(user_uin).lstrip('oO')
                        if clean_uin:
                            user_avatar = f"https://qlogo2.store.qq.com/qzone/{clean_uin}/{clean_uin}/100"
                    
                    # 提取评论中的图片
                    # commentpic 字段是一个列表，包含评论的图片数据
                    # 结构: [{'photourl': {'0': {'url': '...', 'width': ..., 'height': ...}, '1': {...}, ...}, ...}]
                    comment_images = []
                    commentpic = getattr(item, 'commentpic', None) or []
                    if commentpic and isinstance(commentpic, list):
                        for pic_item in commentpic:
                            pic_url_found = False
                            if isinstance(pic_item, dict):
                                # 优先从 photourl 字典中提取图片URL
                                photourl = pic_item.get('photourl', {})
                                if isinstance(photourl, dict):
                                    # 尝试获取最高质量的图片，优先级：'0'(原图) > '1' > '11' > '14'
                                    for size_key in ['0', '1', '11', '14']:
                                        size_data = photourl.get(size_key)
                                        if isinstance(size_data, dict):
                                            pic_url = size_data.get('url', '')
                                            if pic_url:
                                                comment_images.append(pic_url)
                                                pic_url_found = True
                                                break  # 只取一个尺寸，避免重复
                                
                                # 备选：从 busi_param 中提取（如果当前图片的 photourl 不可用）
                                if not pic_url_found:
                                    busi_param = pic_item.get('busi_param', {})
                                    if isinstance(busi_param, dict):
                                        # 尝试 '-1' 或 '144' 键
                                        pic_url = busi_param.get('-1') or busi_param.get('144') or ''
                                        if pic_url:
                                            comment_images.append(pic_url)
                            elif isinstance(pic_item, str):
                                # 如果直接是字符串URL
                                comment_images.append(pic_item)
                    

                    
                    comments_list.append({
                        'id': getattr(item, 'commentid', ''),
                        'user_id': user_uin,
                        'user_name': getattr(user_info, 'name', '') if user_info else '',
                        'user_avatar': user_avatar,
                        'content': getattr(item, 'content', ''),
                        'like_count': getattr(item, 'likeNum', 0),
                        'reply_count': 0,  # QZone评论可能没有回复数
                        'created_at': getattr(item, 'date', 0),
                        'images': comment_images,  # 评论中的图片列表
                    })
                
                return {
                    'success': True,
                    'comments': comments_list,
                    'total': total,
                    'page': page,
                    'page_size': page_size
                }
            
            return {'success': True, 'comments': [], 'total': 0}
        except Exception as e:
            logger.error(f"获取QZone评论失败: {e}")
            return {'success': False, 'message': str(e)}

    async def close(self):
        """关闭底层客户端（若有需要）。"""
        close_fn = getattr(self._client, "close", None)
        if callable(close_fn):
            await close_fn()


class OoqzoneAPIAdapter:
    """封装 publishers.qzone.ooqzone 的 API，以适配与 AioQzoneAPI 相同接口。

    注意：ooqzone 实现内部使用同步 requests，这里保持接口的 async 以便上层统一。
    """

    def __init__(self, cookies: Dict[str, str]):
        from publishers.qzone.ooqzone import QzoneAPI as _RawAPI  # 延迟导入避免不必要依赖
        self._raw = _RawAPI(cookies)
        uin_str = cookies.get("uin") or cookies.get("p_uin") or ""
        uin_str = uin_str.lstrip("oO")
        try:
            self.uin: int = int(uin_str) if uin_str else 0
        except Exception:
            self.uin = 0

    async def check_login(self) -> bool:
        try:
            return await self._raw.token_valid()
        except Exception:
            return False

    async def publish_emotion(self, content: str, images: Optional[List[bytes]] = None) -> Dict[str, Any]:
        images = images or []
        try:
            tid = await self._raw.publish_emotion(content, images)
            return {"success": True, "tid": str(tid)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def add_comment(self, host_uin: Union[str, int], tid: str, content: str) -> Dict[str, Any]:
        # 旧实现无评论接口，返回不支持
        return {"success": False, "message": "not supported"}

    async def delete_mood(self, tid: str) -> Dict[str, Any]:
        # 旧实现无删除接口，返回不支持
        return {"success": False, "message": "not supported"}

    async def get_comments(self, tid: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取说说的评论列表（旧驱动不支持）。"""
        return {"success": False, "message": "not supported"}

    async def close(self):
        return None


def create_qzone_api(cookies: Dict[str, str]):
    """根据配置返回相应驱动的 Qzone API 客户端实例。"""
    cfg = get_platform_config("qzone") or {}
    driver = (cfg.get("driver") or "aioqzone").strip().lower()
    if driver == "ooqzone":
        return OoqzoneAPIAdapter(cookies)
    return AioQzoneAPI(cookies)
