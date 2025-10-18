"""SVG渲染器 - 实验性功能
将消息渲染为SVG矢量图形，而非HTML
"""
import json
import base64
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO
import mimetypes
import re

from linkify_it import LinkifyIt
from humanfriendly import format_size
import qrcode

from core.plugin import ProcessorPlugin
from config.settings import get_settings


class SVGRenderer(ProcessorPlugin):
    """SVG渲染器，将消息渲染为SVG矢量图形"""
    
    def __init__(self):
        super().__init__("svg_renderer", {})
        self.settings = get_settings()
        self._linkify = LinkifyIt()
        # SVG 配置
        self.width = 384  # 4 inches at 96 DPI
        self.padding = 20
        self.content_width = self.width - (self.padding * 2)
        self.line_height = 24
        self.font_size = 16
        self.font_family = self.settings.rendering.font_family
        
    async def initialize(self):
        """初始化渲染器"""
        self.logger.info("SVG渲染器初始化完成")
        
    async def shutdown(self):
        """关闭渲染器"""
        pass
        
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染SVG"""
        svg = await self.render_svg(data)
        data['rendered_svg'] = svg
        # 暴露收集到的链接
        data['extracted_links'] = getattr(self, '_collected_links', [])
        return data
        
    async def render_svg(self, data: Dict[str, Any]) -> str:
        """渲染SVG图形"""
        # 重置链接收集器
        self._collected_links: List[str] = []
        
        # 获取基本信息
        sender_id = data.get('sender_id', '10000')
        nickname = data.get('nickname', '匿名用户')
        is_anonymous = data.get('is_anonymous', False) or str(data.get('needpriv', '')).lower() == 'true'
        watermark_text = data.get('watermark_text', '')
        
        # 匿名处理
        if is_anonymous:
            sender_id = '10000'
            nickname = '匿名'
            user_id_display = ''
            avatar_url = f"https://qlogo2.store.qq.com/qzone/100000/100000/100"
        else:
            user_id_display = sender_id
            avatar_url = f"https://qlogo2.store.qq.com/qzone/{sender_id}/{sender_id}/640"
        
        # 开始构建SVG
        svg_parts = []
        current_y = self.padding
        
        # 添加头部（头像和昵称）
        if not is_anonymous:
            header_height = self._add_header(svg_parts, avatar_url, nickname, user_id_display, current_y)
            current_y += header_height + 20
        
        # 渲染消息内容
        messages_svg, messages_height = self._render_messages(data.get('messages', []), current_y)
        svg_parts.extend(messages_svg)
        current_y += messages_height
        
        # 添加页脚
        current_y += 20
        footer_height = self._add_footer(svg_parts, data.get('wall_mark', 'Graffito'), current_y)
        current_y += footer_height
        
        # 添加水印
        if watermark_text:
            watermark_svg = self._add_watermark(watermark_text, current_y)
            svg_parts.extend(watermark_svg)
        
        # 最终高度
        total_height = current_y + self.padding
        
        # 构建完整SVG
        svg = self._build_svg(svg_parts, total_height)
        return svg
    
    def _add_header(self, svg_parts: List[str], avatar_url: str, nickname: str, user_id: str, y: float) -> float:
        """添加头部，返回高度"""
        avatar_size = 50
        
        # 头像（使用圆形裁剪）
        svg_parts.append(f'''
            <defs>
                <clipPath id="avatar-clip">
                    <circle cx="{self.padding + avatar_size/2}" cy="{y + avatar_size/2}" r="{avatar_size/2}" />
                </clipPath>
            </defs>
            <image href="{avatar_url}" 
                   x="{self.padding}" y="{y}" 
                   width="{avatar_size}" height="{avatar_size}" 
                   clip-path="url(#avatar-clip)" />
        ''')
        
        # 昵称和用户ID
        text_x = self.padding + avatar_size + 12
        svg_parts.append(f'''
            <text x="{text_x}" y="{y + 20}" 
                  font-family="{self.font_family}" 
                  font-size="24" font-weight="600" 
                  fill="#0f172a">{self._escape_xml(nickname)}</text>
        ''')
        
        if user_id:
            svg_parts.append(f'''
                <text x="{text_x}" y="{y + 42}" 
                      font-family="{self.font_family}" 
                      font-size="14" 
                      fill="#64748b">{self._escape_xml(user_id)}</text>
            ''')
        
        return avatar_size
    
    def _add_footer(self, svg_parts: List[str], wall_mark: str, y: float) -> float:
        """添加页脚，返回高度"""
        # 分隔线
        svg_parts.append(f'''
            <line x1="{self.padding}" y1="{y}" 
                  x2="{self.width - self.padding}" y2="{y}" 
                  stroke="#e2e8f0" stroke-width="1" />
        ''')
        
        y += 15
        
        # 品牌和时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        svg_parts.append(f'''
            <text x="{self.padding}" y="{y}" 
                  font-family="{self.font_family}" 
                  font-size="14" font-weight="600" 
                  fill="#64748b">{self._escape_xml(wall_mark)}</text>
            <text x="{self.width - self.padding}" y="{y}" 
                  text-anchor="end"
                  font-family="{self.font_family}" 
                  font-size="14" 
                  fill="#94a3b8">{timestamp}</text>
        ''')
        
        return 20
    
    def _add_watermark(self, text: str, content_height: float) -> List[str]:
        """添加水印"""
        watermarks = []
        tile_spacing = 480
        opacity = 0.12
        angle = -24
        font_size = 40
        
        # 计算需要多少行和列
        rows = int((content_height + tile_spacing) / tile_spacing)
        cols = int((self.width + tile_spacing) / tile_spacing)
        
        for row in range(rows):
            for col in range(cols):
                x = col * tile_spacing + (tile_spacing / 2 if row % 2 else 0)
                y = row * tile_spacing
                
                watermarks.append(f'''
                    <text x="{x}" y="{y}" 
                          transform="rotate({angle} {x} {y})"
                          font-family="{self.font_family}" 
                          font-size="{font_size}" font-weight="500"
                          fill="rgba(0,0,0,{opacity})" 
                          text-anchor="middle">{self._escape_xml(text)}</text>
                ''')
        
        return watermarks
    
    def _render_messages(self, messages: List[Dict[str, Any]], start_y: float) -> tuple[List[str], float]:
        """渲染消息列表，返回 (SVG部分列表, 总高度)"""
        svg_parts = []
        current_y = start_y
        
        for msg in messages:
            msg_type = msg.get('type')
            msg_svg, msg_height = self._render_message(msg, current_y)
            svg_parts.extend(msg_svg)
            current_y += msg_height + 10  # 消息间距
        
        return svg_parts, current_y - start_y
    
    def _render_message(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染单条消息，返回 (SVG部分列表, 高度)"""
        msg_type = msg.get('type')
        
        if msg_type == 'text':
            return self._render_text(msg, y)
        elif msg_type == 'image':
            return self._render_image(msg, y)
        elif msg_type == 'file':
            return self._render_file(msg, y)
        elif msg_type == 'face':
            return self._render_face(msg, y)
        elif msg_type == 'poke':
            return self._render_poke(msg, y)
        elif msg_type == 'forward':
            return self._render_forward(msg, y)
        elif msg_type == 'reply':
            return self._render_reply(msg, y)
        elif msg_type == 'json':
            return self._render_card(msg, y)
        else:
            return [], 0
    
    def _render_text(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染文本消息"""
        text = msg.get('data', {}).get('text', '')
        linkified, links = self._linkify_and_collect(text)
        self._collect_links(links)
        
        # 计算文本需要的行数
        lines = self._wrap_text(text, self.content_width - 24)
        height = len(lines) * self.line_height + 16
        
        svg_parts = []
        
        # 气泡背景
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="12" fill="#ffffff" 
                  stroke="#e2e8f0" stroke-width="1" />
        ''')
        
        # 文本内容
        text_y = y + 20
        for line in lines:
            svg_parts.append(f'''
                <text x="{self.padding + 12}" y="{text_y}" 
                      font-family="{self.font_family}" 
                      font-size="{self.font_size}" 
                      fill="#0f172a">{self._escape_xml(line)}</text>
            ''')
            text_y += self.line_height
        
        return svg_parts, height
    
    def _render_image(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染图片消息"""
        data = msg.get('data', {})
        url = data.get('url', '')
        
        # 图片默认尺寸
        img_width = self.content_width * 0.5
        img_height = 200
        
        svg_parts = []
        
        # 尝试将本地图片转为 data URI
        src = self._resolve_image_src(url)
        
        svg_parts.append(f'''
            <image href="{src}" 
                   x="{self.padding}" y="{y}" 
                   width="{img_width}" height="{img_height}" 
                   preserveAspectRatio="xMidYMid slice" />
        ''')
        
        return svg_parts, img_height
    
    def _render_file(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染文件消息"""
        data = msg.get('data', {})
        file_name = data.get('file', '未命名文件')
        file_size = data.get('file_size', 0)
        
        # 格式化文件大小
        try:
            size_str = format_size(int(file_size), binary=False)
        except Exception:
            size_str = format_size(float(file_size), binary=False)
        
        svg_parts = []
        height = 60
        
        # 文件块背景
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="12" fill="#ffffff" 
                  stroke="#e2e8f0" stroke-width="1" />
        ''')
        
        # 文件图标（简化为矩形）
        icon_size = 40
        svg_parts.append(f'''
            <rect x="{self.padding + 10}" y="{y + 10}" 
                  width="{icon_size}" height="{icon_size}" 
                  rx="4" fill="#6366f1" />
            <text x="{self.padding + 30}" y="{y + 35}" 
                  font-family="{self.font_family}" 
                  font-size="12" font-weight="600"
                  fill="#ffffff" text-anchor="middle">FILE</text>
        ''')
        
        # 文件名和大小
        text_x = self.padding + icon_size + 20
        svg_parts.append(f'''
            <text x="{text_x}" y="{y + 25}" 
                  font-family="{self.font_family}" 
                  font-size="16" 
                  fill="#0f172a">{self._escape_xml(file_name[:30])}</text>
            <text x="{text_x}" y="{y + 45}" 
                  font-family="{self.font_family}" 
                  font-size="11" 
                  fill="#94a3b8">{size_str}</text>
        ''')
        
        return svg_parts, height
    
    def _render_face(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染表情"""
        # 简化处理：显示表情文本
        svg_parts = []
        svg_parts.append(f'''
            <text x="{self.padding}" y="{y + 20}" 
                  font-family="{self.font_family}" 
                  font-size="28" 
                  fill="#0f172a">[表情]</text>
        ''')
        return svg_parts, 30
    
    def _render_poke(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染戳一戳"""
        svg_parts = []
        svg_parts.append(f'''
            <text x="{self.padding}" y="{y + 20}" 
                  font-family="{self.font_family}" 
                  font-size="16" 
                  fill="#6366f1">[戳一戳]</text>
        ''')
        return svg_parts, 30
    
    def _render_forward(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染合并转发"""
        svg_parts = []
        height = 60
        
        # 转发标题
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="4" height="{height}" 
                  fill="#71a1cc" />
            <text x="{self.padding + 12}" y="{y + 20}" 
                  font-family="{self.font_family}" 
                  font-size="14" 
                  fill="#64748b">合并转发聊天记录</text>
        ''')
        
        return svg_parts, height
    
    def _render_reply(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染回复消息"""
        data = msg.get('data', {})
        preview_text = data.get('text') or data.get('content') or '引用的消息'
        
        svg_parts = []
        height = 50
        
        # 回复框
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="4" fill="#fafafa" 
                  stroke="#e2e8f0" stroke-width="1" />
            <rect x="{self.padding}" y="{y}" 
                  width="3" height="{height}" 
                  fill="#e2e8f0" />
        ''')
        
        # 回复文本
        svg_parts.append(f'''
            <text x="{self.padding + 12}" y="{y + 20}" 
                  font-family="{self.font_family}" 
                  font-size="12" 
                  fill="#64748b">回复消息</text>
            <text x="{self.padding + 12}" y="{y + 38}" 
                  font-family="{self.font_family}" 
                  font-size="14" 
                  fill="#333333">{self._escape_xml(str(preview_text)[:40])}</text>
        ''')
        
        return svg_parts, height
    
    def _render_card(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染卡片消息"""
        svg_parts = []
        height = 80
        
        # 卡片背景
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="12" fill="#ffffff" 
                  stroke="#e2e8f0" stroke-width="1" />
            <text x="{self.padding + 12}" y="{y + 30}" 
                  font-family="{self.font_family}" 
                  font-size="16" font-weight="600"
                  fill="#0f172a">卡片消息</text>
        ''')
        
        return svg_parts, height
    
    def _build_svg(self, parts: List[str], height: float) -> str:
        """构建完整的SVG文档"""
        svg_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{self.width}" height="{height}" 
     viewBox="0 0 {self.width} {height}">
    <!-- 背景 -->
    <rect width="{self.width}" height="{height}" fill="#f8fafc" />
    
    <!-- 内容 -->
'''
        
        svg_footer = '''
</svg>'''
        
        return svg_header + '\n'.join(parts) + svg_footer
    
    # ===== 工具方法 =====
    
    def _escape_xml(self, text: str) -> str:
        """XML转义"""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text
    
    def _wrap_text(self, text: str, max_width: float) -> List[str]:
        """文本换行"""
        # 简化实现：按字符数估算
        chars_per_line = int(max_width / (self.font_size * 0.6))
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) <= chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [text[:chars_per_line]]
    
    def _linkify_and_collect(self, text: str) -> tuple[str, List[str]]:
        """提取链接"""
        if not text:
            return '', []
        
        collected: List[str] = []
        matches = self._linkify.match(text)
        
        for m in matches or []:
            url = m.url if hasattr(m, 'url') else text[m.index:m.last_index]
            if url:
                collected.append(url)
        
        return text, collected
    
    def _collect_links(self, links: List[str]):
        """收集链接"""
        if not links:
            return
        seen = set(self._collected_links)
        for u in links:
            if u and u not in seen:
                self._collected_links.append(u)
                seen.add(u)
    
    def _resolve_image_src(self, url: str) -> str:
        """解析图片源"""
        try:
            if not url:
                return ''
            if url.startswith('data:image'):
                return url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            
            # 本地文件转为 data URI
            path = url
            if url.startswith('file://'):
                path = self._file_uri_to_path(url)
            
            if os.path.exists(path):
                return self._image_to_data_uri(path)
            
            return url
        except Exception:
            return url
    
    def _file_uri_to_path(self, uri: str) -> str:
        """file:// URI 转路径"""
        try:
            s = str(uri)
            if not s.startswith('file://'):
                return s
            body = s[7:]
            while body.startswith('/') and len(body) > 3 and body[2] == ':':
                body = body[1:]
            return body.replace('/', '\\') if os.name == 'nt' else body
        except Exception:
            return uri
    
    def _image_to_data_uri(self, path: str) -> str:
        """图片转 data URI"""
        try:
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = 'image/png'
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
            return f'data:{mime};base64,{b64}'
        except Exception:
            return path

