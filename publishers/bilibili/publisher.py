"""Bilibili 发送器

职责：
- 加载/管理每个账号的 B 站 cookies（SESSDATA/bili_jct 等）
- 基于 bilibili_api 的 Credential 检查可用性
- 发布图文动态
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from publishers.base import BasePublisher
from core.enums import PublishPlatform
from .api import BilibiliAPI
import orjson


class BilibiliPublisher(BasePublisher):
    """B站图文动态发送器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("bilibili_publisher", PublishPlatform.BILIBILI, config)
        self.cookies_map: Dict[str, Dict[str, Any]] = {}
        self.api_clients: Dict[str, BilibiliAPI] = {}

    async def initialize(self):
        await super().initialize()
        # 加载 cookies
        await self._load_all_cookies_from_config()

    async def shutdown(self):
        for api in self.api_clients.values():
            try:
                await api.close()
            except Exception:
                pass
        await super().shutdown()

    async def _load_all_cookies_from_config(self):
        """根据配置加载所有账号 cookies。优先 config.publishers.bilibili.accounts 指定的 cookie_file。"""
        cfg = self._get_platform_config()
        accounts_cfg: Dict[str, Dict[str, Any]] = cfg.get('accounts') or {}
        for account_id in (accounts_cfg.keys() or []):
            cookie_file = accounts_cfg[account_id].get('cookie_file') or f"data/cookies/bilibili_{account_id}.json"
            await self.load_cookies(account_id, cookie_file)

        # 若无 accounts 显式配置，则尝试从 QQ 账号列表镜像加载同名文件
        if not accounts_cfg:
            for acc_id in self.accounts:
                await self.load_cookies(acc_id, f"data/cookies/bilibili_{acc_id}.json")

    async def load_cookies(self, account_id: str, cookie_file_path: str) -> bool:
        p = Path(cookie_file_path)
        if not p.exists():
            self.logger.warning(f"B站 cookie 文件不存在: {cookie_file_path}")
            return False
        try:
            if p.stat().st_size == 0:
                self.logger.error(f"B站 cookie 文件为空: {cookie_file_path}")
                return False
            cookies = orjson.loads(p.read_bytes())
            # 支持两种格式：{'SESSDATA': '...', 'bili_jct': '...'} 或 [{name, value}...]
            if isinstance(cookies, dict):
                normalized = cookies
            elif isinstance(cookies, list):
                normalized = {c.get('name'): c.get('value') for c in cookies if isinstance(c, dict)}
            else:
                normalized = {}
            if not normalized.get('SESSDATA') or not (normalized.get('bili_jct') or normalized.get('csrf')):
                self.logger.error(f"B站 cookie 缺少 SESSDATA/bili_jct: {cookie_file_path}")
                return False
            self.cookies_map[account_id] = normalized
            self.api_clients[account_id] = BilibiliAPI(normalized)
            self.logger.info(f"加载B站 cookies成功: {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"加载B站 cookies失败 {account_id}: {e}")
            return False

    async def check_login_status(self, account_id: Optional[str] = None) -> bool:
        if account_id:
            api = self.api_clients.get(account_id)
            return await api.check_login() if api else False
        # 检查所有账号
        ok_any = False
        for acc_id, api in self.api_clients.items():
            ok = await api.check_login()
            ok_any = ok_any or ok
            if not ok:
                self.logger.warning(f"B站账号未登录: {acc_id}")
        return ok_any

    # 移除 refresh_login：仅依赖外部 cookies 文件

    def format_at(self, submission) -> str:
        # B站不支持通过 QQ 号直接@，默认返回空
        return ""

    async def _load_image_bytes(self, image_path: str) -> Optional[bytes]:
        try:
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
            # 优先使用主账号（与 QQ 配置对应的第一个账号）
            candidate_ids = sorted(self.api_clients.keys()) or sorted(self.accounts.keys())
            account_id = candidate_ids[0] if candidate_ids else None
        if not account_id:
            return {'success': False, 'error': '没有可用的B站账号'}

        api = self.api_clients.get(account_id)
        if not api:
            return {'success': False, 'error': 'B站API客户端未初始化'}
        if not await api.check_login():
            return {'success': False, 'error': 'B站账号未登录或Cookie无效'}

        try:
            images_bytes: List[bytes] = []
            if images:
                cfg = self._get_platform_config()
                for img in images[: cfg.get('max_images_per_post', 9)]:
                    img_bytes = await self._load_image_bytes(img)
                    if img_bytes:
                        images_bytes.append(img_bytes)

            result = await api.create_draw_dynamic(content or '', images_bytes)
            if result.get('success'):
                return {'success': True, 'dynamic_id': result.get('dynamic_id'), 'account_id': account_id}
            return {'success': False, 'error': result.get('message', '发布失败'), 'code': result.get('code')}
        except Exception as e:
            self.logger.error(f"B站发布失败: {e}")
            return {'success': False, 'error': str(e)}

    async def batch_publish(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        account_ids = list(self.api_clients.keys())
        if not account_ids:
            return [{'success': False, 'error': '没有可用的B站账号'}] * len(items)
        for i, item in enumerate(items):
            aid = account_ids[i % len(account_ids)]
            res = await self.publish(item.get('content', ''), item.get('images') or [], account_id=aid)
            results.append(res)
        return results

    async def add_comment_for_submission(self, submission_id: int, content: str) -> Dict[str, Any]:
        """为已发布到B站的投稿追加评论。

        通过 PublishRecord 查找该投稿在B站发布时的 dynamic_id，然后选择任一有可用登录态的账号发表评论。
        """
        try:
            from core.database import get_db
            from sqlalchemy import select
            from core.models import PublishRecord
            from core.enums import PublishPlatform

            db = await get_db()
            async with db.get_session() as session:
                r = await session.execute(select(PublishRecord).order_by(PublishRecord.created_at.desc()))
                records = r.scalars().all()
                dynamic_id: Optional[int] = None
                account_id: Optional[str] = None
                for rec in records:
                    try:
                        if not rec.is_success or rec.platform != PublishPlatform.BILIBILI.value:
                            continue
                        if submission_id in (rec.submission_ids or []):
                            pr = rec.publish_result or {}
                            did = pr.get('dynamic_id') or pr.get('dyn_id')
                            if did:
                                dynamic_id = int(did)
                                account_id = rec.account_id or None
                                break
                    except Exception:
                        continue

                if dynamic_id is None:
                    return {"success": False, "message": "未找到B站发布记录或缺少dynamic_id"}

                # 选择账号
                api = None
                if account_id and account_id in self.api_clients:
                    api = self.api_clients.get(account_id)
                else:
                    # 任取一个可用账号
                    for aid, client in self.api_clients.items():
                        if await client.check_login():
                            api = client
                            break
                if not api:
                    return {"success": False, "message": "B站API未初始化或无可用账号"}

                res = await api.add_comment(dynamic_id, content)
                return res
        except Exception as e:
            self.logger.error(f"B站追加评论失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_submission(self, submission_id: int) -> Dict[str, Any]:
        """删除已发布到B站的投稿（动态）。
        
        通过 PublishRecord 查找 dynamic_id 与账号，再调用 BilibiliAPI.delete_dynamic。
        """
        try:
            from core.database import get_db
            from sqlalchemy import select
            from core.models import PublishRecord
            from core.enums import PublishPlatform

            db = await get_db()
            async with db.get_session() as session:
                r = await session.execute(select(PublishRecord).order_by(PublishRecord.created_at.desc()))
                records = r.scalars().all()
                dynamic_id: Optional[int] = None
                account_id: Optional[str] = None
                for rec in records:
                    try:
                        if not rec.is_success or rec.platform != PublishPlatform.BILIBILI.value:
                            continue
                        if submission_id in (rec.submission_ids or []):
                            pr = rec.publish_result or {}
                            did = pr.get('dynamic_id') or pr.get('dyn_id')
                            if did:
                                dynamic_id = int(did)
                                account_id = rec.account_id or None
                                break
                    except Exception:
                        continue

                if dynamic_id is None:
                    return {"success": False, "message": "未找到B站发布记录或缺少dynamic_id"}

                api = None
                if account_id and account_id in self.api_clients:
                    api = self.api_clients.get(account_id)
                else:
                    for aid, client in self.api_clients.items():
                        if await client.check_login():
                            api = client
                            break
                if not api:
                    return {"success": False, "message": "B站API未初始化或无可用账号"}

                res = await api.delete_dynamic(dynamic_id)
                return res
        except Exception as e:
            self.logger.error(f"B站删除动态失败: {e}")
            return {"success": False, "message": str(e)}

    async def delete_by_publish_record(self, record) -> Dict[str, Any]:
        try:
            pr = record.publish_result or {}
            did = pr.get('dynamic_id') or pr.get('dyn_id')
            if not did:
                return {"success": False, "message": "missing dynamic_id"}
            dynamic_id = int(did)
            api = None
            if record.account_id and record.account_id in self.api_clients:
                api = self.api_clients.get(record.account_id)
            else:
                for aid, client in self.api_clients.items():
                    if await client.check_login():
                        api = client
                        break
            if not api:
                return {"success": False, "message": "api not ready"}
            res = await api.delete_dynamic(dynamic_id)
            return res
        except Exception as e:
            return {"success": False, "message": str(e)}

