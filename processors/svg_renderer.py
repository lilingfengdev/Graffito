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

# 导入 AVIF 支持
try:
    import pillow_avif
except ImportError:
    pass

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
        
        # 最终高度
        total_height = current_y + self.padding
        
        # 添加水印（使用总高度）
        if watermark_text:
            watermark_svg = self._add_watermark(watermark_text, total_height)
            svg_parts.extend(watermark_svg)
        
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
        # 调整水印间距，适配画布宽度
        tile_spacing_x = 250  # 横向间距
        tile_spacing_y = 200  # 纵向间距
        opacity = 0.08  # 降低透明度，避免遮挡内容
        angle = -30
        font_size = 32
        
        # 计算需要多少行和列（至少1行1列）
        total_height = content_height + self.padding * 2
        rows = max(1, int((total_height + tile_spacing_y) / tile_spacing_y))
        cols = max(1, int((self.width + tile_spacing_x) / tile_spacing_x))
        
        for row in range(rows):
            for col in range(cols):
                # 错开布局，奇数行偏移半个间距
                x = col * tile_spacing_x + (tile_spacing_x / 2 if row % 2 else tile_spacing_x / 4)
                y = row * tile_spacing_y + tile_spacing_y / 2
                
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
        elif msg_type == 'video':
            return self._render_video(msg, y)
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
        # 上下内边距各8px，行高20px
        padding_top = 8
        padding_bottom = 8
        line_spacing = 20
        height = padding_top + len(lines) * line_spacing + padding_bottom
        
        svg_parts = []
        
        # 气泡背景
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="12" fill="#ffffff" 
                  stroke="#e2e8f0" stroke-width="1" />
        ''')
        
        # 文本内容 - 使用单独的 text 元素确保换行
        text_y = y + padding_top + 16  # 基线位置
        for i, line in enumerate(lines):
            svg_parts.append(f'''<text x="{self.padding + 12}" y="{text_y}" font-family="{self.font_family}" font-size="{self.font_size}" fill="#0f172a">{self._escape_xml(line)}</text>''')
            text_y += line_spacing
        
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
    
    def _render_video(self, msg: Dict[str, Any], y: float) -> tuple[List[str], float]:
        """渲染视频消息（显示占位符）"""
        svg_parts = []
        width = self.content_width * 0.6
        height = 150
        
        # 视频占位框
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{width}" height="{height}" 
                  rx="12" fill="#f1f5f9" 
                  stroke="#cbd5e1" stroke-width="2" />
        ''')
        
        # 播放图标（简化为三角形）
        center_x = self.padding + width / 2
        center_y = y + height / 2
        play_size = 40
        
        svg_parts.append(f'''
            <circle cx="{center_x}" cy="{center_y}" r="{play_size}" 
                    fill="rgba(0,0,0,0.5)" />
            <polygon points="{center_x - 12},{center_y - 15} {center_x - 12},{center_y + 15} {center_x + 15},{center_y}" 
                     fill="white" />
        ''')
        
        # 视频文本
        svg_parts.append(f'''
            <text x="{center_x}" y="{y + height - 15}" 
                  text-anchor="middle"
                  font-family="{self.font_family}" 
                  font-size="14" 
                  fill="#64748b">[视频]</text>
        ''')
        
        return svg_parts, height
    
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
        """渲染QQ表情"""
        data = msg.get('data', {})
        face_id = str(data.get('id', '0'))
        
        # 判断是否为大表情/贴纸
        is_sticker = False
        try:
            raw = data.get('raw') or {}
            face_type_val = raw.get('faceType')
            if face_type_val is not None and int(face_type_val) >= 2:
                is_sticker = True
        except Exception:
            pass
        
        # 尝试加载表情图片
        src = self._get_face_src(face_id)
        
        svg_parts = []
        if src:
            # 使用图片
            img_size = 120 if is_sticker else 28
            height = img_size + 10
            
            svg_parts.append(f'''
            <image href="{src}" 
                   x="{self.padding}" y="{y}" 
                   width="{img_size}" height="{img_size}" 
                   preserveAspectRatio="xMidYMid meet" />
        ''')
            return svg_parts, height
        else:
            # 回退到文本显示
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
        raw = msg.get('data', {}).get('data', '{}')
        card_data: Optional[Dict[str, Any]] = None
        try:
            if isinstance(raw, dict):
                card_data = raw
            else:
                s = str(raw)
                # 兼容 HTML 实体/转义
                s = s.replace('&#44;', ',').replace('\\/', '/')
                try:
                    import html as _html
                    s = _html.unescape(s)
                except Exception:
                    pass
                card_data = json.loads(s)
        except Exception:
            card_data = None

        if not isinstance(card_data, dict):
            svg_parts = []
            height = 60
            svg_parts.append(f'''
                <rect x="{self.padding}" y="{y}" 
                      width="{self.content_width}" height="{height}" 
                      rx="12" fill="#ffffff" 
                      stroke="#e2e8f0" stroke-width="1" />
                <text x="{self.padding + 12}" y="{y + 35}" 
                      font-family="{self.font_family}" 
                      font-size="16" font-weight="600"
                      fill="#0f172a">卡片消息</text>
            ''')
            return svg_parts, height

        view = str(card_data.get('view') or '').lower()
        meta = card_data.get('meta') or {}
        
        # 提取标题和描述
        title = ''
        desc = ''
        
        if view == 'contact' and isinstance(meta.get('contact'), dict):
            c = meta.get('contact') or {}
            title = c.get('nickname') or '联系人'
            desc = c.get('contact') or ''
        elif view == 'miniapp' and isinstance(meta.get('miniapp'), dict):
            m = meta.get('miniapp') or {}
            title = m.get('title') or '小程序卡片'
            desc = m.get('source') or ''
        elif view == 'news' and isinstance(meta.get('news'), dict):
            n = meta.get('news') or {}
            title = n.get('title') or '分享'
            desc = n.get('desc') or ''
        else:
            # 通用卡片
            g = self._first_entry_value(meta)
            title = g.get('title') or card_data.get('prompt') or (card_data.get('view') or '卡片')
            desc = g.get('desc') or ''

        # 渲染卡片
        svg_parts = []
        height = 80 if desc else 60
        
        # 卡片背景
        svg_parts.append(f'''
            <rect x="{self.padding}" y="{y}" 
                  width="{self.content_width}" height="{height}" 
                  rx="12" fill="#ffffff" 
                  stroke="#e2e8f0" stroke-width="1" />
        ''')
        
        # 标题
        title_lines = self._wrap_text(title, self.content_width - 24)
        text_y = y + 25
        for line in title_lines[:2]:  # 最多显示2行标题
            svg_parts.append(f'''<text x="{self.padding + 12}" y="{text_y}" font-family="{self.font_family}" font-size="16" font-weight="600" fill="#0f172a">{self._escape_xml(line)}</text>''')
            text_y += 20
        
        # 描述
        if desc:
            desc_lines = self._wrap_text(desc, self.content_width - 24)
            svg_parts.append(f'''<text x="{self.padding + 12}" y="{text_y + 5}" font-family="{self.font_family}" font-size="14" fill="#64748b">{self._escape_xml(desc_lines[0][:30])}</text>''')
        
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
        """文本换行 - 支持中英文混排和自动换行"""
        if not text:
            return ['']
        
        # 估算每行最大字符数（中文字符算1个，英文字符算0.5个）
        # max_width 是像素宽度，font_size 是字体大小
        # 中文字符宽度约等于 font_size，英文字符约为 font_size * 0.6
        max_chars_estimate = int(max_width / self.font_size) * 1.5
        
        all_lines = []
        
        # 首先按原有的换行符分割
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph:
                # 空行保留
                all_lines.append('')
                continue
                
            # 对每个段落进行宽度检查和自动换行
            current_line = ""
            current_width = 0
            
            for char in paragraph:
                # 估算字符宽度
                if ord(char) > 127:  # 非ASCII字符（包括中文）
                    char_width = 1.0
                elif char == ' ':
                    char_width = 0.3
                else:  # ASCII字符
                    char_width = 0.5
                
                # 检查是否需要换行
                if current_width + char_width > max_chars_estimate and current_line:
                    all_lines.append(current_line)
                    current_line = char
                    current_width = char_width
                else:
                    current_line += char
                    current_width += char_width
            
            # 添加段落的最后一行
            if current_line:
                all_lines.append(current_line)
        
        return all_lines if all_lines else ['']
    
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
    
    def _get_face_src(self, face_id: str) -> str:
        """根据 face_id 返回表情图片 data-URI"""
        # 缓存
        if not hasattr(self, '_face_cache'):
            self._face_cache: Dict[str, str] = {}
        cached = self._face_cache.get(face_id)
        if cached:
            return cached

        # 候选目录与文件名模式（优先 AVIF/WebP，避免 GIF 过大）
        candidate_dirs = [
            Path('static/qlottie'),
            Path('qlottie'),
        ]
        name_patterns = [
            f"{face_id}.avif",
            f"{face_id}.webp",
            f"{face_id}.png",
            f"face_{face_id}.avif",
            f"face_{face_id}.webp",
            f"face_{face_id}.png",
            f"sticker_{face_id}.avif",
            f"sticker_{face_id}.png",
            # GIF 放在最后（因为文件太大）
            f"{face_id}.gif",
        ]

        for d in candidate_dirs:
            try:
                if not d.exists():
                    continue
                for name in name_patterns:
                    p = d / name
                    if p.exists():
                        ext = p.suffix.lower()
                        
                        # AVIF/GIF 需要转换为 PNG（cairosvg 不支持 AVIF）
                        if ext in ('.avif', '.gif'):
                            try:
                                from PIL import Image
                                from io import BytesIO
                                
                                # 转换为 PNG
                                with Image.open(p) as img:
                                    # 如果是 GIF 动画，只取第一帧
                                    if hasattr(img, 'n_frames') and img.n_frames > 1:
                                        img.seek(0)
                                    
                                    # 转换为 RGBA
                                    if img.mode not in ('RGB', 'RGBA'):
                                        img = img.convert('RGBA')
                                    
                                    # 保存为 PNG
                                    buf = BytesIO()
                                    img.save(buf, format='PNG', optimize=True)
                                    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                                    data_uri = f"data:image/png;base64,{b64}"
                                    self._face_cache[face_id] = data_uri
                                    return data_uri
                            except Exception:
                                # 转换失败，继续查找其他格式
                                continue
                        else:
                            # PNG/WebP 直接使用
                            mime = 'image/png'
                            if ext == '.webp':
                                mime = 'image/webp'
                            
                            with open(p, 'rb') as f:
                                b64 = base64.b64encode(f.read()).decode('ascii')
                            data_uri = f"data:{mime};base64,{b64}"
                            self._face_cache[face_id] = data_uri
                            return data_uri
            except Exception:
                continue

        # 找不到时返回空字符串
        return ''
    
    def _first_entry_value(self, d: Any) -> Dict[str, Any]:
        """获取字典的第一个值（用于通用卡片解析）"""
        if isinstance(d, dict) and d:
            try:
                first_key = next(iter(d.keys()))
                v = d.get(first_key)
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
        return {}

