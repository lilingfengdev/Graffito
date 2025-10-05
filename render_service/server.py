"""独立的 HTML 渲染服务器
只负责 HTML to screenshot 的渲染功能
"""
import asyncio
import base64
import os
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
except ImportError:
    logger.error("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
    async_playwright = None


# 全局浏览器实例
browser: Optional[Browser] = None
context: Optional[BrowserContext] = None
playwright_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global browser, context, playwright_instance
    
    if not async_playwright:
        logger.error("Playwright 未安装，渲染服务无法启动")
        yield
        return
    
    try:
        # 启动浏览器
        logger.info("正在启动浏览器...")
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(
            viewport={'width': 384, 'height': 768},
            device_scale_factor=2
        )
        logger.info("浏览器启动成功")
    except Exception as e:
        logger.error(f"浏览器启动失败: {e}")
    
    yield
    
    # 关闭浏览器
    if browser:
        try:
            await browser.close()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
    
    if playwright_instance:
        try:
            await playwright_instance.stop()
        except Exception as e:
            logger.error(f"停止 Playwright 失败: {e}")


app = FastAPI(
    title="Graffito HTML Render Service",
    description="独立的 HTML 渲染服务，负责将 HTML 转换为截图",
    version="1.0.0",
    lifespan=lifespan
)

# Token 认证配置
RENDER_SERVICE_TOKEN = os.getenv("RENDER_SERVICE_TOKEN", "")
security = HTTPBearer(auto_error=False)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """验证 Token"""
    # 如果未设置 token，则不需要验证
    if not RENDER_SERVICE_TOKEN:
        return True
    
    # 如果设置了 token，则必须验证
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )
    
    if credentials.credentials != RENDER_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    return True


class RenderRequest(BaseModel):
    """渲染请求"""
    html: str = Field(..., description="要渲染的 HTML 内容")
    submission_id: str = Field(..., description="投稿 ID，用于标识")
    page_height: int = Field(768, description="每页高度（像素）")
    width: int = Field(384, description="页面宽度（像素）")
    max_height: int = Field(2304, description="最大页面高度（像素）")


class RenderResponse(BaseModel):
    """渲染响应"""
    success: bool
    images: List[str] = Field(default_factory=list, description="生成的图片路径或 Base64 数据")
    error: Optional[str] = None


@app.get("/")
async def root():
    """健康检查"""
    return {
        "service": "Graffito HTML Render Service",
        "status": "running",
        "browser_ready": browser is not None
    }


@app.post("/render", response_model=RenderResponse)
async def render_html(request: RenderRequest, _: bool = Depends(verify_token)):
    """
    将 HTML 渲染为图片
    
    Args:
        request: 渲染请求
        
    Returns:
        渲染结果，包含 Base64 编码的图片数据
    """
    if not browser or not context:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="浏览器未初始化"
        )
    
    try:
        # 创建页面
        page = await context.new_page()
        
        # 设置 HTML 内容
        await page.set_content(request.html)
        
        # 等待渲染完成
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(0.5)  # 额外等待确保渲染完成
        
        # 获取页面高度
        height = await page.evaluate('document.documentElement.scrollHeight')
        
        # 设置视口高度
        await page.set_viewport_size({
            'width': request.width,
            'height': min(height, request.max_height)
        })
        
        images = []
        
        # 如果页面很长，分页截图
        if height > request.page_height:
            # 计算需要的页数
            pages = (height + request.page_height - 1) // request.page_height
            
            for i in range(pages):
                # 滚动到指定位置
                await page.evaluate(f'window.scrollTo(0, {i * request.page_height})')
                await asyncio.sleep(0.1)
                
                # 截图
                screenshot = await page.screenshot(
                    clip={
                        'x': 0,
                        'y': i * request.page_height,
                        'width': request.width,
                        'height': min(request.page_height, height - i * request.page_height)
                    }
                )
                
                # 返回 Base64 编码
                base64_image = base64.b64encode(screenshot).decode('utf-8')
                images.append(f"data:image/png;base64,{base64_image}")
        else:
            # 单页截图
            screenshot = await page.screenshot(full_page=True)
            base64_image = base64.b64encode(screenshot).decode('utf-8')
            images.append(f"data:image/png;base64,{base64_image}")
        
        await page.close()
        
        logger.info(f"渲染完成: {request.submission_id}, 生成 {len(images)} 张图片")
        
        return RenderResponse(
            success=True,
            images=images
        )
        
    except Exception as e:
        logger.error(f"渲染失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"渲染失败: {str(e)}"
        )




if __name__ == "__main__":
    import uvicorn
    
    # 配置日志
    logger.add(
        "logs/render_service_{time}.log",
        rotation="00:00",
        retention="7 days",
        level="INFO"
    )
    
    # 提示 Token 配置
    if RENDER_SERVICE_TOKEN:
        logger.info("渲染服务已启用 Token 认证")
    else:
        logger.warning("渲染服务未设置 Token，建议设置环境变量 RENDER_SERVICE_TOKEN")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8084,
        log_level="info"
    )

