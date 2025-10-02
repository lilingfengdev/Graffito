"""内容渲染器，将HTML转换为图片
支持多种渲染后端：本地 Playwright、独立渲染服务、Cloudflare Browser Rendering
"""
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from core.plugin import ProcessorPlugin
from .render_backends import (
    RenderBackend,
    LocalPlaywrightBackend,
    RemoteRenderServiceBackend,
    CloudflareRenderBackend
)


class ContentRenderer(ProcessorPlugin):
    """内容渲染器，将HTML转换为图片
    
    支持的渲染后端：
    - local: 本地 Playwright（默认）
    - remote: 独立渲染服务
    - cloudflare: Cloudflare Browser Rendering
    """
    
    def __init__(self, backend_type: str = "local", backend_config: Optional[Dict[str, Any]] = None):
        """
        初始化内容渲染器
        
        Args:
            backend_type: 渲染后端类型 (local/remote/cloudflare)
            backend_config: 后端配置
        """
        super().__init__("content_renderer", {})
        self.backend_type = backend_type
        self.backend_config = backend_config or {}
        self.backend: Optional[RenderBackend] = None
        
    async def initialize(self):
        """初始化渲染器"""
        try:
            # 根据配置创建渲染后端
            if self.backend_type == "local":
                self.backend = LocalPlaywrightBackend()
                
            elif self.backend_type == "remote":
                service_url = self.backend_config.get("service_url", "http://localhost:8084")
                token = self.backend_config.get("token")
                self.backend = RemoteRenderServiceBackend(service_url, token)
                
            elif self.backend_type == "cloudflare":
                account_id = self.backend_config.get("account_id")
                api_token = self.backend_config.get("api_token")
                
                if not account_id or not api_token:
                    raise ValueError("Cloudflare 后端需要 account_id 和 api_token")
                
                self.backend = CloudflareRenderBackend(account_id, api_token)
                
            else:
                raise ValueError(f"不支持的渲染后端: {self.backend_type}")
            
            # 初始化后端
            await self.backend.initialize()
            self.logger.info(f"内容渲染器初始化完成 (后端: {self.backend_type})")
            
        except Exception as e:
            self.logger.error(f"渲染器初始化失败: {e}")
            raise
            
    async def shutdown(self):
        """关闭渲染器"""
        if self.backend:
            await self.backend.shutdown()
            
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理渲染"""
        html = data.get('rendered_html')
        if not html:
            self.logger.warning("没有HTML内容可渲染")
            return data
            
        # 渲染为图片
        images = await self.render_to_images(html, data.get('submission_id', 'unknown'))
        data['rendered_images'] = images
        
        return data
        
    async def render_to_images(self, html: str, submission_id: str) -> List[str]:
        """将HTML渲染为图片"""
        if not self.backend:
            self.logger.error("渲染后端未初始化")
            return []
            
        try:
            images = await self.backend.render_html_to_images(
                html=html,
                submission_id=submission_id,
                output_dir="data/cache/rendered"
            )
            
            self.logger.info(f"渲染完成，生成 {len(images)} 张图片")
            return images
            
        except Exception as e:
            self.logger.error(f"渲染失败: {e}")
            return []
            
    async def render_to_pdf(self, html: str, output_path: str) -> bool:
        """将HTML渲染为PDF (仅本地后端支持)"""
        if not isinstance(self.backend, LocalPlaywrightBackend):
            self.logger.warning("当前渲染后端不支持 PDF 生成")
            return False
            
        try:
            import asyncio
            
            page = await self.backend.context.new_page()
            await page.set_content(html)
            await page.wait_for_load_state('networkidle')
            
            # 生成PDF
            await page.pdf(
                path=output_path,
                format='A6',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
            )
            
            await page.close()
            self.logger.info(f"PDF生成成功: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"PDF生成失败: {e}")
            return False
            
    async def html_to_base64_image(self, html: str) -> Optional[str]:
        """将HTML转换为Base64编码的图片 (仅本地后端支持)"""
        if not isinstance(self.backend, LocalPlaywrightBackend):
            self.logger.warning("当前渲染后端不支持 Base64 转换")
            return None
            
        try:
            page = await self.backend.context.new_page()
            await page.set_content(html)
            await page.wait_for_load_state('networkidle')
            
            # 截图
            screenshot = await page.screenshot(full_page=True)
            await page.close()
            
            # 转换为Base64
            base64_image = base64.b64encode(screenshot).decode('utf-8')
            return f"data:image/png;base64,{base64_image}"
            
        except Exception as e:
            self.logger.error(f"转换为Base64失败: {e}")
            return None
