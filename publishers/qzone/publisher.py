"""QQ空间发送器

职责：
- 读取并管理每个账号的 QZone cookies
- 基于 aioqzone 的 gtk 检查登录有效性
- 通过 NapCat 本地接口获取/刷新 cookies（仅当无效或缺失时）
- 发布说说与追加评论
"""
from utils import json_util as json
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from loguru import logger
from io import BytesIO
from PIL import Image

from publishers.base import BasePublisher
from core.enums import PublishPlatform
from .api import QzoneAPI


class QzonePublisher(BasePublisher):
    """QQ空间发送器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("qzone_publisher", PublishPlatform.QZONE, config)
        self.cookies: Dict[str, Dict[str, Any]] = {}  # 账号cookies
        self.api_clients: Dict[str, QzoneAPI] = {}  # API客户端
        
    async def initialize(self):
        """初始化发送器：加载或刷新 cookies，准备 API 客户端。"""
        await super().initialize()
        
        # 加载所有账号的cookies；若不可用则尝试通过 NapCat 登录刷新
        for account_id in self.accounts:
            loaded = await self.load_cookies(account_id)
            if not loaded:
                self.logger.info(f"未找到本地 cookies，尝试NapCat登录: {account_id}")
                await self.login_via_napcat(account_id)
            else:
                api = self.api_clients.get(account_id)
                if api and not await api.check_login():
                    self.logger.info(f"检测到 cookies 失效，尝试NapCat登录: {account_id}")
                    await self.login_via_napcat(account_id)
            
    async def load_cookies(self, account_id: str) -> bool:
        """加载账号cookies"""
        cookie_file = Path(f"data/cookies/qzone_{account_id}.json")
        
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    self.cookies[account_id] = cookies
                    self.api_clients[account_id] = QzoneAPI(cookies)
                    self.logger.info(f"加载cookies成功: {account_id}")
                    return True
            except Exception as e:
                self.logger.error(f"加载cookies失败 {account_id}: {e}")
                
        return False
        
    async def save_cookies(self, account_id: str, cookies: Dict[str, Any]):
        """保存 cookies 并更新 API 客户端。"""
        cookie_file = Path(f"data/cookies/qzone_{account_id}.json")
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
            
        self.cookies[account_id] = cookies
        self.api_clients[account_id] = QzoneAPI(cookies)
    
    async def login_via_napcat(self, account_id: str) -> bool:
        """通过 NapCat 本地 HTTP 接口拉取 qzone.qq.com 域 cookies 完成登录。
        要求：account_groups 为账号提供 http_port，可选 http_token。
        成功后写入 data/cookies/qzone_{account_id}.json 并校验 gtk。
        """
        try:
            account_info = self.accounts.get(account_id)
            if not account_info:
                self.logger.error(f"账号不存在: {account_id}")
                return False
            port = account_info['http_port']
            headers = {}
            http_token = account_info.get('http_token')
            if http_token:
                headers['Authorization'] = f'Bearer {http_token}'

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:
                # 参考脚本：从 NapCat 获取指定域 Cookie 字符串
                resp = await client.get(
                    f"http://127.0.0.1:{port}/get_cookies",
                    params={"domain": "qzone.qq.com"}
                )
                if resp.status_code != 200:
                    self.logger.error(f"NapCat get_cookies HTTP {resp.status_code}: {account_id}")
                    return False
                data = resp.json()
                if data.get('status') != 'ok':
                    self.logger.error(f"NapCat get_cookies 返回异常: {data}")
                    return False
                cookies_str = data['data'].get('cookies') or ''
                if not cookies_str:
                    self.logger.error("NapCat 未返回 cookies 字符串")
                    return False
                # 解析 cookies
                cookies: Dict[str, Any] = {}
                for item in cookies_str.split('; '):
                    if '=' in item:
                        k, v = item.split('=', 1)
                        cookies[k] = v
                # 补充必要字段：uin/p_uin
                qq_id = str(account_info.get('qq_id') or '')
                if qq_id and not cookies.get('uin'):
                    cookies['uin'] = f"o{qq_id}"
                if qq_id and not cookies.get('p_uin'):
                    cookies['p_uin'] = f"o{qq_id}"
                if not cookies.get('p_skey'):
                    self.logger.error("缺少 p_skey，登录失败")
                    return False
                await self.save_cookies(account_id, cookies)
                # 验证 gtk 可用
                api = self.api_clients.get(account_id)
                ok = await api.check_login() if api else False
                if not ok:
                    self.logger.error("登录后 gtk 检查失败")
                    return False
                self.logger.info(f"NapCat 登录成功: {account_id}")
                return True
        except Exception as e:
            self.logger.error(f"NapCat 登录异常 {account_id}: {e}")
            return False
        
    async def check_login_status(self, account_id: Optional[str] = None) -> bool:
        """检查登录状态：基于 gtk 检查；失效则优先尝试 NapCat 登录，否则尝试重载磁盘 cookies。"""
        if account_id:
            # 单账号检查
            api = self.api_clients.get(account_id)
            ok = await api.check_login() if api else False
            if ok:
                return True
            # 尝试 NapCat 登录
            if await self.login_via_napcat(account_id):
                api2 = self.api_clients.get(account_id)
                return await api2.check_login() if api2 else False
            # 回退：重载磁盘 cookies（如外部已更新）
            if await self.load_cookies(account_id):
                api3 = self.api_clients.get(account_id)
                return await api3.check_login() if api3 else False
            return False
            
        # 检查所有账号
        for acc_id, api in self.api_clients.items():
            ok = await api.check_login()
            if not ok:
                # 尝试 NapCat 登录
                if await self.login_via_napcat(acc_id):
                    api2 = self.api_clients.get(acc_id)
                    if await api2.check_login():
                        continue
                # 回退：重载磁盘 cookies
                if await self.load_cookies(acc_id):
                    api3 = self.api_clients.get(acc_id)
                    if await (api3.check_login() if api3 else asyncio.sleep(0)):
                        continue
                self.logger.warning(f"账号 {acc_id} 登录失效")
                return False
        return True
        
    # 移除 refresh_login：使用外部提供的 cookies 文件
            
    async def publish(self, content: str, images: List[str] = None, **kwargs) -> Dict[str, Any]:
        """发布到QQ空间"""
        account_id = kwargs.get('account_id')
        if not account_id:
            # 主账号优先，选择第一个已加载 cookies 的账号
            candidate_ids = sorted(
                self.accounts.keys(),
                key=lambda aid: (not self.accounts[aid].get('is_main', False))
            )
            for acc_id in candidate_ids:
                if acc_id in self.api_clients:
                    account_id = acc_id
                    break
                    
        if not account_id:
            return {'success': False, 'error': '没有可用的账号'}
            
        # 检查登录状态（不再尝试刷新）
        if not await self.check_login_status(account_id):
            return {'success': False, 'error': '登录失效或 cookies 无效'}
                
        # 获取API客户端
        api = self.api_clients.get(account_id)
        if not api:
            return {'success': False, 'error': 'API客户端未初始化'}
            
        try:
            # 处理图片
            image_data = []
            if images:
                for img_path in images:
                    img_bytes = await self._load_image(img_path)
                    if img_bytes:
                        image_data.append(img_bytes)
                        
            # 发布说说
            result = await api.publish_emotion(content, image_data)
            
            if result.get('tid'):
                return {
                    'success': True,
                    'tid': result['tid'],
                    'account_id': account_id
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message', '发布失败')
                }
                
        except Exception as e:
            self.logger.error(f"发布失败: {e}")
            return {'success': False, 'error': str(e)}
            
    async def batch_publish(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量发布"""
        results = []
        
        # 分配账号
        account_ids = list(self.accounts.keys())
        if not account_ids:
            return [{'success': False, 'error': '没有可用账号'}] * len(items)
            
        # 轮流使用账号发布
        for i, item in enumerate(items):
            account_id = account_ids[i % len(account_ids)]
            result = await self.publish(
                item['content'],
                item.get('images'),
                account_id=account_id
            )
            results.append(result)
            
            # 发布间隔
            if i < len(items) - 1:
                await asyncio.sleep(2)
                
        return results
        
    async def _load_image(self, image_path: str) -> Optional[bytes]:
        """加载图片"""
        try:
            if image_path.startswith('http'):
                # 网络图片
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_path)
                    return await self._convert_to_jpeg(response.content)
            elif image_path.startswith('file://'):
                # 本地文件
                file_path = image_path.replace('file://', '')
                with open(file_path, 'rb') as f:
                    return await self._convert_to_jpeg(f.read())
            elif image_path.startswith('data:image'):
                # Base64数据
                import re
                match = re.match(r'data:image/[^;]+;base64,(.*)', image_path)
                if match:
                    raw = base64.b64decode(match.group(1))
                    return await self._convert_to_jpeg(raw)
            else:
                # 尝试作为本地文件
                if Path(image_path).exists():
                    with open(image_path, 'rb') as f:
                        return await self._convert_to_jpeg(f.read())
                        
        except Exception as e:
            self.logger.error(f"加载图片失败 {image_path}: {e}")
            
        return None

    async def _convert_to_jpeg(self, content: bytes) -> bytes:
        """将任意图片内容转换为JPEG，避免QQ空间WebP等不支持格式"""
        try:
            img = Image.open(BytesIO(content))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            out = BytesIO()
            img.save(out, format='JPEG', quality=90)
            return out.getvalue()
        except Exception as e:
            # 转换失败则原样返回（可能已是JPEG且可用）
            self.logger.warning(f"图片格式转换失败，回退原图: {e}")
            return content

    async def add_comment_for_submission(self, submission_id: int, content: str) -> Dict[str, Any]:
        """为已发布的投稿添加QQ空间评论
        
        - 定位该投稿对应的发布记录，获取 tid 与使用的账号
        - 使用对应账号调用评论 API
        """
        try:
            # 读取投稿及其发布记录
            from core.database import get_db
            from sqlalchemy import select
            from core.models import Submission, PublishRecord
            from core.enums import SubmissionStatus

            db = await get_db()
            async with db.get_session() as session:
                r = await session.execute(select(Submission).where(Submission.id == submission_id))
                submission = r.scalar_one_or_none()
                if not submission:
                    return {"success": False, "message": "投稿不存在"}

                if submission.status != SubmissionStatus.PUBLISHED.value:
                    return {"success": False, "message": "该投稿尚未发布，无法同步评论"}

                # 查找最近的、成功的发布记录以获取 tid
                r2 = await session.execute(
                    select(PublishRecord).order_by(PublishRecord.created_at.desc())
                )
                records = r2.scalars().all()
                target_record = None
                for record in records:
                    try:
                        if not record.is_success:
                            continue
                        if not record.publish_result:
                            continue
                        sub_ids = record.submission_ids or []
                        if isinstance(sub_ids, list) and submission_id in sub_ids:
                            if record.publish_result.get("tid"):
                                target_record = record
                                break
                    except Exception:
                        continue

                if not target_record:
                    return {"success": False, "message": "未找到发布记录或缺少tid"}

                account_id = target_record.account_id
                tid = target_record.publish_result.get("tid")
                api = self.api_clients.get(account_id)
                if not api:
                    return {"success": False, "message": "对应账号未登录或API未初始化"}

                # hostuin 为发布账号的 uin
                host_uin = api.uin
                # 调用评论接口
                result = await api.add_comment(host_uin, str(tid), content)
                if result.get("success"):
                    return {"success": True, "message": "评论已同步到QQ空间"}
                return {"success": False, "message": result.get("message", "评论失败")}
        except Exception as e:
            self.logger.error(f"同步QQ空间评论失败: {e}")
            return {"success": False, "message": str(e)}
