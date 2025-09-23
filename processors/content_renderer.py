"""内容渲染器，将HTML转换为图片"""
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

try:
    from playwright.async_api import async_playwright
except ImportError:
    logger.warning("Playwright未安装，图片渲染功能将不可用")
    async_playwright = None

from core.plugin import ProcessorPlugin


class ContentRenderer(ProcessorPlugin):
    """内容渲染器，将HTML转换为PDF和图片"""
    
    def __init__(self):
        super().__init__("content_renderer", {})
        self.browser = None
        self.context = None
        
    async def initialize(self):
        """初始化渲染器"""
        if async_playwright:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                self.context = await self.browser.new_context(
                    viewport={'width': 384, 'height': 768},  # 4英寸宽度
                    device_scale_factor=2  # 高清渲染
                )
                self.logger.info("内容渲染器初始化完成")
            except Exception as e:
                self.logger.error(f"浏览器初始化失败: {e}")
                self.browser = None
        else:
            self.logger.warning("Playwright未安装，渲染功能不可用")
            
    async def shutdown(self):
        """关闭渲染器"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
            
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
        if not self.browser:
            self.logger.error("浏览器未初始化")
            return []
            
        try:
            # 创建输出目录
            output_dir = Path(f"data/cache/rendered/{submission_id}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建页面
            page = await self.context.new_page()
            
            # 设置HTML内容
            await page.set_content(html)
            
            # 等待渲染完成
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(0.5)  # 额外等待确保渲染完成
            
            # 获取页面高度
            height = await page.evaluate('document.documentElement.scrollHeight')
            
            # 设置视口高度
            await page.set_viewport_size({'width': 384, 'height': min(height, 2304)})
            
            images = []
            
            # 如果页面很长，分页截图
            if height > 768:
                # 计算需要的页数
                page_height = 768
                pages = (height + page_height - 1) // page_height
                
                for i in range(pages):
                    # 滚动到指定位置
                    await page.evaluate(f'window.scrollTo(0, {i * page_height})')
                    await asyncio.sleep(0.1)
                    
                    # 截图
                    image_path = output_dir / f"page_{i+1:02d}.png"
                    await page.screenshot(
                        path=str(image_path),
                        clip={
                            'x': 0,
                            'y': i * page_height,
                            'width': 384,
                            'height': min(page_height, height - i * page_height)
                        }
                    )
                    # 统一 URL 使用正斜杠，便于前端与静态服务
                    images.append(str(image_path).replace('\\', '/'))
            else:
                # 单页截图
                image_path = output_dir / "page_01.png"
                await page.screenshot(path=str(image_path), full_page=True)
                images.append(str(image_path).replace('\\', '/'))
                
            await page.close()
            
            self.logger.info(f"渲染完成，生成 {len(images)} 张图片")
            return images
            
        except Exception as e:
            self.logger.error(f"渲染失败: {e}")
            return []
            
    async def render_to_pdf(self, html: str, output_path: str) -> bool:
        """将HTML渲染为PDF"""
        if not self.browser:
            self.logger.error("浏览器未初始化")
            return False
            
        try:
            page = await self.context.new_page()
            await page.set_content(html)
            await page.wait_for_load_state('networkidle')
            
            # 生成PDF
            await page.pdf(
                path=output_path,
                format='A6',  # 接近4英寸宽度
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
        """将HTML转换为Base64编码的图片"""
        if not self.browser:
            return None
            
        try:
            page = await self.context.new_page()
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
