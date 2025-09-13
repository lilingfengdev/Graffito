"""QQ空间API接口（基于 aioqzone + qqqr 的 H5 实现）

职责：
- 使用 aioqzone.h5 API 完成图片上传、预上传和发表说说
- 基于 aioqzone.login 的 gtk 计算做轻量登录有效性检查
"""
from typing import Any, Dict, List, Optional, Sequence, Union
from tenacity import RetryError

from loguru import logger

from qqqr.utils.net import ClientAdapter
from aioqzone.exception import QzoneError
from aioqzone.api.h5.model import QzoneH5API
from aioqzone.api.login import ConstLoginMan
from aioqzone.model.api.request import PhotoData


class QzoneAPI:
    """QQ空间API客户端（aioqzone H5 直连）"""

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

    async def close(self):
        """关闭底层客户端（若有需要）。"""
        close_fn = getattr(self._client, "close", None)
        if callable(close_fn):
            await close_fn()
