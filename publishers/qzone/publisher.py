"""QQ空间发送器实现"""
import json
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from loguru import logger

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
        """初始化发送器"""
        await super().initialize()
        
        # 加载所有账号的cookies
        for account_id in self.accounts:
            await self.load_cookies(account_id)
            
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
        """保存cookies"""
        cookie_file = Path(f"data/cookies/qzone_{account_id}.json")
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
            
        self.cookies[account_id] = cookies
        self.api_clients[account_id] = QzoneAPI(cookies)
        
    async def check_login_status(self, account_id: Optional[str] = None) -> bool:
        """检查登录状态"""
        if account_id:
            if account_id in self.api_clients:
                return await self.api_clients[account_id].check_login()
            return False
            
        # 检查所有账号
        for acc_id, api in self.api_clients.items():
            if not await api.check_login():
                self.logger.warning(f"账号 {acc_id} 登录失效")
                return False
        return True
        
    async def refresh_login(self, account_id: str) -> bool:
        """刷新登录（通过NapCat获取新cookies）"""
        try:
            account_info = self.accounts.get(account_id)
            if not account_info:
                self.logger.error(f"账号不存在: {account_id}")
                return False
                
            # 通过NapCat API获取cookies
            port = account_info['http_port']
            async with httpx.AsyncClient() as client:
                # 获取QQ空间cookies
                response = await client.get(
                    f"http://127.0.0.1:{port}/get_cookies",
                    params={"domain": "qzone.qq.com"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'ok':
                        cookies_str = data['data']['cookies']
                        
                        # 解析cookies字符串
                        cookies = {}
                        for item in cookies_str.split('; '):
                            if '=' in item:
                                key, value = item.split('=', 1)
                                cookies[key] = value
                                
                        # 保存cookies
                        await self.save_cookies(account_id, cookies)
                        self.logger.info(f"刷新登录成功: {account_id}")
                        return True
                        
            self.logger.error(f"刷新登录失败: {account_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"刷新登录异常 {account_id}: {e}")
            return False
            
    async def publish(self, content: str, images: List[str] = None, **kwargs) -> Dict[str, Any]:
        """发布到QQ空间"""
        account_id = kwargs.get('account_id')
        if not account_id:
            # 选择第一个可用账号
            for acc_id in self.accounts:
                if await self.check_login_status(acc_id):
                    account_id = acc_id
                    break
                    
        if not account_id:
            return {'success': False, 'error': '没有可用的账号'}
            
        # 检查登录状态
        if not await self.check_login_status(account_id):
            # 尝试刷新登录
            if not await self.refresh_login(account_id):
                return {'success': False, 'error': '登录失效且刷新失败'}
                
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
                    return response.content
            elif image_path.startswith('file://'):
                # 本地文件
                file_path = image_path.replace('file://', '')
                with open(file_path, 'rb') as f:
                    return f.read()
            elif image_path.startswith('data:image'):
                # Base64数据
                import re
                match = re.match(r'data:image/[^;]+;base64,(.*)', image_path)
                if match:
                    return base64.b64decode(match.group(1))
            else:
                # 尝试作为本地文件
                if Path(image_path).exists():
                    with open(image_path, 'rb') as f:
                        return f.read()
                        
        except Exception as e:
            self.logger.error(f"加载图片失败 {image_path}: {e}")
            
        return None
