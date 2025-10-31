"""渲染后端抽象层
支持多种渲染后端：本地 Playwright、独立渲染服务、Cloudflare Browser Rendering
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from loguru import logger
import aiohttp


class RenderBackend(ABC):
    """渲染后端基类"""
    
    @abstractmethod
    async def initialize(self):
        """初始化后端"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """关闭后端"""
        pass
    
    @abstractmethod
    async def render_html_to_images(
        self,
        html: str,
        submission_id: str,
        output_dir: str = "data/cache/rendered"
    ) -> List[str]:
        """
        将 HTML 渲染为图片
        
        Args:
            html: HTML 内容
            submission_id: 投稿 ID
            output_dir: 输出目录
            
        Returns:
            图片路径列表
        """
        pass


class LocalPlaywrightBackend(RenderBackend):
    """本地 Playwright 渲染后端"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.playwright = None
        
    async def initialize(self):
        """初始化 Playwright"""
        try:
            from playwright.async_api import async_playwright
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 384, 'height': 768},
                device_scale_factor=2
            )
            logger.info("本地 Playwright 后端初始化完成")
        except ImportError:
            logger.error("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Playwright 初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭 Playwright"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def render_html_to_images(
        self,
        html: str,
        submission_id: str,
        output_dir: str = "data/cache/rendered"
    ) -> List[str]:
        """渲染 HTML 为图片"""
        import asyncio
        
        if not self.browser:
            raise RuntimeError("Playwright 未初始化")
        
        try:
            # 确保 submission_id 是字符串
            submission_id = str(submission_id)
            output_path = Path(output_dir) / submission_id
            output_path.mkdir(parents=True, exist_ok=True)
            
            page = await self.context.new_page()
            await page.set_content(html)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(0.5)
            
            height = await page.evaluate('document.documentElement.scrollHeight')
            await page.set_viewport_size({'width': 384, 'height': min(height, 2304)})
            
            images = []
            page_height = 768
            
            if height > page_height:
                pages = (height + page_height - 1) // page_height
                
                for i in range(pages):
                    await page.evaluate(f'window.scrollTo(0, {i * page_height})')
                    await asyncio.sleep(0.1)
                    
                    image_path = output_path / f"page_{i+1:02d}.png"
                    await page.screenshot(
                        path=str(image_path),
                        clip={
                            'x': 0,
                            'y': i * page_height,
                            'width': 384,
                            'height': min(page_height, height - i * page_height)
                        }
                    )
                    images.append(str(image_path).replace('\\', '/'))
            else:
                image_path = output_path / "page_01.png"
                await page.screenshot(path=str(image_path), full_page=True)
                images.append(str(image_path).replace('\\', '/'))
            
            await page.close()
            logger.info(f"本地渲染完成: {submission_id}, {len(images)} 张图片")
            return images
            
        except Exception as e:
            logger.error(f"本地渲染失败: {e}")
            raise


class RemoteRenderServiceBackend(RenderBackend):
    """独立渲染服务后端"""
    
    def __init__(self, service_url: str, token: Optional[str] = None):
        """
        初始化远程渲染服务后端
        
        Args:
            service_url: 渲染服务 URL (例如: http://localhost:8084)
            token: 可选的认证 Token
        """
        self.service_url = service_url.rstrip('/')
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """初始化 HTTP 会话"""
        # 设置请求头
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        self.session = aiohttp.ClientSession(headers=headers)
        
        # 健康检查
        try:
            async with self.session.get(f"{self.service_url}/") as response:
                if response.status == 200:
                    logger.info(f"远程渲染服务连接成功: {self.service_url}")
                elif response.status == 401:
                    logger.error("远程渲染服务认证失败，请检查 Token")
                    raise Exception("Authentication failed")
                else:
                    logger.warning(f"远程渲染服务响应异常: {response.status}")
        except Exception as e:
            logger.error(f"无法连接到远程渲染服务: {e}")
            raise
    
    async def shutdown(self):
        """关闭 HTTP 会话"""
        if self.session:
            await self.session.close()
    
    async def render_html_to_images(
        self,
        html: str,
        submission_id: str,
        output_dir: str = "data/cache/rendered"
    ) -> List[str]:
        """通过远程服务渲染 HTML"""
        import base64
        
        if not self.session:
            raise RuntimeError("HTTP 会话未初始化")
        
        try:
            # 确保 submission_id 是字符串
            submission_id = str(submission_id)
            payload = {
                "html": html,
                "submission_id": submission_id
            }
            
            async with self.session.post(
                f"{self.service_url}/render",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"渲染服务错误: {response.status} - {error_text}")
                
                result = await response.json()
                
                if not result.get("success"):
                    raise Exception(f"渲染失败: {result.get('error')}")
                
                # 接收 base64 图片数据
                base64_images = result.get("images", [])
                
                # 创建输出目录
                output_path = Path(output_dir) / submission_id
                output_path.mkdir(parents=True, exist_ok=True)
                
                # 保存图片到本地
                images = []
                for i, base64_data in enumerate(base64_images):
                    # 去除 data:image/png;base64, 前缀
                    if base64_data.startswith('data:image/png;base64,'):
                        base64_data = base64_data.replace('data:image/png;base64,', '')
                    
                    # 解码并保存
                    image_bytes = base64.b64decode(base64_data)
                    image_path = output_path / f"page_{i+1:02d}.png"
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    images.append(str(image_path).replace('\\', '/'))
                
                logger.info(f"远程渲染完成: {submission_id}, {len(images)} 张图片")
                return images
                
        except Exception as e:
            logger.error(f"远程渲染失败: {e}")
            raise


class CloudflareRenderBackend(RenderBackend):
    """Cloudflare Browser Rendering 后端 (使用官方 SDK)"""
    
    def __init__(self, account_id: str, api_token: str):
        """
        初始化 Cloudflare 渲染后端
        
        Args:
            account_id: Cloudflare 账号 ID
            api_token: Cloudflare API Token
        """
        self.account_id = account_id
        self.api_token = api_token
        self.client = None
    
    async def initialize(self):
        """初始化 Cloudflare 客户端"""
        try:
            from cloudflare import AsyncCloudflare
            self.client = AsyncCloudflare(api_token=self.api_token)
            logger.info("Cloudflare Browser Rendering 后端初始化完成")
        except ImportError:
            logger.error("Cloudflare SDK 未安装，请运行: pip install cloudflare")
            raise
    
    async def shutdown(self):
        """关闭客户端"""
        if self.client:
            self.client = None
    
    async def render_html_to_images(
        self,
        html: str,
        submission_id: str,
        output_dir: str = "data/cache/rendered"
    ) -> List[str]:
        """通过 Cloudflare 渲染 HTML（完整截图后分页）"""
        import base64
        from PIL import Image
        from io import BytesIO
        
        if not self.client:
            raise RuntimeError("Cloudflare 客户端未初始化")
        
        try:
            # 确保 submission_id 是字符串
            submission_id = str(submission_id)
            
            # 将 HTML 编码为 data URL
            html_base64 = base64.b64encode(html.encode('utf-8')).decode('ascii')
            data_url = f"data:text/html;base64,{html_base64}"
            
            # 使用 AsyncCloudflare 直接调用 API
            response = await self.client.browser_rendering.screenshot.with_raw_response.create(
                account_id=self.account_id,
                url=data_url,
                viewport={
                    "width": 384,
                    "height": 768, 
                    "device_scale_factor": 2
                },
                screenshot_options={
                    "full_page": True,
                    "type": "png"
                }
            )
            
            # 从原始响应读取二进制数据
            image_bytes = response.read()
            
            if not image_bytes:
                raise Exception("未获取到截图数据")
            
            # 打开图片
            img = Image.open(BytesIO(image_bytes))
            width, height = img.size
            
            # 保存路径
            output_path = Path(output_dir) / submission_id
            output_path.mkdir(parents=True, exist_ok=True)
            
            images = []
            page_height = 768 * 2  # device_scale_factor = 2
            
            # 如果图片很长，分页保存
            if height > page_height:
                # 计算需要的页数
                pages = (height + page_height - 1) // page_height
                
                for i in range(pages):
                    # 计算裁剪区域
                    top = i * page_height
                    bottom = min((i + 1) * page_height, height)
                    
                    # 裁剪图片
                    page_img = img.crop((0, top, width, bottom))
                    
                    # 保存
                    image_path = output_path / f"page_{i+1:02d}.png"
                    page_img.save(image_path, 'PNG')
                    images.append(str(image_path).replace('\\', '/'))
                    
                logger.info(f"Cloudflare 渲染完成: {submission_id}, 分割为 {len(images)} 张图片")
            else:
                # 单页保存
                image_path = output_path / "page_01.png"
                img.save(image_path, 'PNG')
                images.append(str(image_path).replace('\\', '/'))
                logger.info(f"Cloudflare 渲染完成: {submission_id}")
            
            return images
            
        except Exception as e:
            logger.error(f"Cloudflare 渲染失败: {e}")
            raise

