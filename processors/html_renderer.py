"""HTML渲染器"""
import orjson as json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from jinja2 import Template
import os
import mimetypes
import re
import base64
from io import BytesIO
from urllib.parse import quote
from linkify_it import LinkifyIt
from humanfriendly import format_size

import qrcode

from core.plugin import ProcessorPlugin
from config.settings import get_settings


class HTMLRenderer(ProcessorPlugin):
    """HTML渲染器，将消息渲染为HTML页面"""
    
    def __init__(self):
        super().__init__("html_renderer", {})
        self.settings = get_settings()
        self.template = self.load_template()
        # 初始化 LinkifyIt
        self._linkify = LinkifyIt()
        
    async def initialize(self):
        """初始化渲染器"""
        self.logger.info("HTML渲染器初始化完成")
        
    async def shutdown(self):
        """关闭渲染器"""
        pass
        
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染HTML"""
        html = await self.render_html(data)
        data['rendered_html'] = html
        # 暴露在渲染过程中收集到的链接，供后续流程（发布时附带）使用
        data['extracted_links'] = getattr(self, '_collected_links', [])
        return data
        
    def load_template(self) -> Template:
        """加载HTML模板"""
        template_str = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XWall 消息页</title>
    <style>
        :root {
            /* 与前端设计系统保持一致的颜色和样式变量 */
            --primary-color: #6366f1;
            --secondary-color: #71a1cc;
            --background-color: #f8fafc;
            --card-background: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            --border-color: #e2e8f0;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            
            /* 间距系统 - 与设计系统保持一致 */
            --spacing-1: 4px;
            --spacing-2: 8px;
            --spacing-3: 12px;
            --spacing-4: 16px;
            --spacing-5: 20px;
            --spacing-6: 24px;
            --spacing-8: 32px;
            --spacing-sm: 6px;
            --spacing-md: 8px;
            --spacing-lg: 10px;
            --spacing-xl: 12px;
            --spacing-xxl: 20px;
            
            /* 边框圆角 */
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            
            /* 阴影系统 */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            
            /* 字体系统 */
            --font-family: {{ font_family }};
            --font-size-xs: 12px;
            --font-size-sm: 14px;
            --font-size-md: 16px;
            --font-size-lg: 24px;
            
            /* 组件特定变量 */
            --container-width: 4in;
            --avatar-size: 50px;
            
            /* 过渡动画 */
            --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * { box-sizing: border-box; }

        @page {
            margin: 0 !important;
            size: 4in 8in;
        }

        body {
            font-family: var(--font-family);
            background-color: var(--background-color);
            margin: 0;
            padding: 5px;
            line-height: 1.5;
        }

        .container {
            width: var(--container-width);
            margin: 0 auto;
            padding: var(--spacing-xxl);
            border-radius: var(--radius-lg);
            background-color: var(--background-color);
            position: relative;
        }

        .header {
            display: flex;
            align-items: center;
            gap: var(--spacing-lg);
        }

        .header img {
            border-radius: 50%;
            width: var(--avatar-size);
            height: var(--avatar-size);
            box-shadow: var(--shadow-md);
            flex-shrink: 0;
        }

        .header-text {
            display: block;
            flex: 1;
        }

        .header h1 {
            font-size: var(--font-size-lg);
            margin: 0;
            font-weight: 600;
        }

        .header h2 {
            font-size: var(--font-size-sm);
            margin: 0;
            color: var(--text-secondary);
        }

        .content {
            margin-top: var(--spacing-xxl);
        }

        .bubble {
            display: block;
            background-color: var(--card-background);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: var(--spacing-2) var(--spacing-3);
            margin-bottom: var(--spacing-lg);
            word-break: break-word;
            max-width: fit-content;
            box-shadow: var(--shadow-sm);
            line-height: 1.5;
            transition: var(--transition);
        }
        
        .bubble:hover {
            box-shadow: var(--shadow-md);
        }

        .content img:not(.thumb):not(.qr-code):not(.brand-icon):not(.card-tag-icon):not(.cqface),
        .content video:not(.thumb):not(.qr-code):not(.brand-icon):not(.card-tag-icon) {
            display: block;
            border-radius: var(--radius-lg);
            margin-bottom: var(--spacing-lg);
            max-width: 50%;
            max-height: 300px;
            box-shadow: var(--shadow-md);
            background-color: transparent;
        }

        .cqface {
            vertical-align: middle;
            width: 28px !important;
            height: 28px !important;
            margin: 0 !important;
            display: inline !important;
            padding: 0 !important;
            transform: translateY(-0.1em);
        }

        .sticker {
            display: block !important;
            width: 120px !important;
            height: 120px !important;
            margin-bottom: var(--spacing-lg) !important;
        }

        .file-block {
            display: flex !important;
            flex-direction: row-reverse;
            align-items: flex-start;
            background-color: var(--card-background);
            border-radius: var(--radius-lg);
            padding: 7px;
            margin-bottom: var(--spacing-lg);
            gap: var(--spacing-sm);
            line-height: 1.4;
            word-break: break-all;
            width: fit-content;
            max-width: 100%;
            box-shadow: var(--shadow-sm);
        }

        .file-icon {
            width: 40px !important;
            height: 40px !important;
            flex: 0 0 40px;
            margin: 0 !important;
            padding: 0 !important;
            border-radius: 0px !important;
            object-fit: contain;
        }

        .file-info {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: space-between;
            min-height: 40px;
            flex: 1;
        }

        .file-name {
            font-size: var(--font-size-md);
            line-height: 1.3;
            color: var(--text-primary);
            text-decoration: none;
            word-break: break-word;
        }

        .file-meta {
            font-size: 11px;
            color: var(--text-muted);
            margin: 0px 0px 1px 1px;
            line-height: 1;
        }

        .card {
            display: block;
            background-color: var(--card-background);
            border-radius: var(--radius-lg);
            padding: var(--spacing-md);
            margin-bottom: var(--spacing-lg);
            text-decoration: none;
            color: var(--text-primary);
            width: fit-content;
            max-width: 276px;
            box-shadow: var(--shadow-sm);
        }

        /* 联系人卡片：横向布局 */
        .card-contact { display: flex; align-items: center; gap: 8px; }
        .card-media img { width: 48px !important; height: 48px !important; border-radius: 4px !important; object-fit: cover; display: block; margin: 0 !important; }
        .card-body { margin-top: 0; display: flex; flex-direction: column; }
        .card-vertical .card-preview img { width: 100% !important; height: auto !important; object-fit: cover; border-radius: 0 !important; display: block; margin: 0 !important; }
        .card-tag-row { display: flex; align-items: center; gap: 4px; margin-top: 6px; font-size: 11px; color: var(--text-muted); }
        .card-tag-icon { width: 14px !important; height: 14px !important; border-radius: 3px !important; object-fit: contain; margin: 0 !important; }
        .card-tag { display: block; font-size: 11px; color: var(--text-muted); }

        /* QQ 官方风格头部：thumb 左，标题中，二维码最右 */
        .card-header { display: flex; align-items: center; justify-content: flex-start; gap: 8px; margin-bottom: 6px; }
        .card-header-left { min-width: 0; display: flex; flex-direction: column; gap: 6px; flex: 1 1 auto; }
        .card-header-right { display: flex; align-items: flex-start; gap: 8px; }
        .card-header .thumb { width: 48px !important; height: 48px !important; border-radius: 4px !important; object-fit: cover; margin: 0 !important; }
        .qr-code { width: 48px !important; height: 48px !important; border-radius: 0 !important; margin: 0 !important; flex: 0 0 48px; }
        .brand-inline { display: inline-flex; align-items: center; gap: 6px; }
        .brand-inline .brand-icon { width: 12px !important; height: 12px !important; border-radius: 0 !important; object-fit: contain; margin: 0 !important; }
        .brand-inline .brand-text { font-size: 12px; color: var(--text-secondary); }
        .card-header .card-title { margin: 0; white-space: normal; overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; word-break: break-word; }
        .card.card-vertical { width: 100%; max-width: 276px; }
        .card.card-vertical .card-header { width: 100%; display: flex; align-items: center; gap: 8px; }
        .card.card-vertical .qr-code { margin-left: auto; flex: 0 0 48px; }

        /* Forward 嵌套缩进 */
        .forward .forward { margin-left: 6px; }

        .card-title {
            font-size: var(--font-size-md);
            font-weight: 600;
            margin: 0 0 2px 0;
        }

        .card-desc {
            font-size: var(--font-size-sm);
            color: var(--text-secondary);
            margin: 0;
        }

        .forward {
            border-left: 3px solid var(--secondary-color);
            padding-left: var(--spacing-lg);
            margin: 0 0 var(--spacing-lg) 0;
        }

        .forward-title {
            font-size: var(--font-size-sm);
            color: var(--text-secondary);
            margin: 0px 0 var(--spacing-sm) 0;
        }

        .forward-item {
            margin: var(--spacing-sm) 0;
        }

        .reply {
            border-left: 3px solid var(--border-color);
            background: #fafafa;
            border-radius: var(--radius-sm);
            padding: var(--spacing-sm) var(--spacing-md);
            margin-bottom: var(--spacing-sm);
        }

        .reply-meta {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-bottom: 2px;
        }

        .reply-body {
            white-space: pre-wrap;
            color: #333;
        }

        .poke-icon {
            width: 30px;
            height: 30px;
        }

        .image-block {
            display: block;
        }

        .link-bubble {
            background-color: #f7f9fc;
            border: 1px solid var(--border-color);
        }

        /* 水印样式 */
        .wm-overlay {
            position: absolute;
            inset: 0;
            pointer-events: none;
            z-index: 999;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        .wm-item {
            position: absolute;
            white-space: nowrap;
            user-select: none;
            font-family: var(--font-family);
            font-weight: 500;
            color: rgba(0, 0, 0, 1);
            text-shadow: 0 0 1px rgba(255, 255, 255, 0.25);
            transform: rotate(-24deg);
            line-height: 1;
            mix-blend-mode: multiply;
        }
        @media print { .wm-item { mix-blend-mode: normal; } }

        .footer {
            margin-top: var(--spacing-xxl);
            padding-top: var(--spacing-md);
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            color: var(--text-secondary);
            font-size: var(--font-size-sm);
        }

        .footer .brand {
            font-weight: 600;
        }

        .footer .timestamp {
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {% if show_avatar %}
            <img src="{{ avatar_url }}" alt="Profile Image">
            {% endif %}
            <div class="header-text">
                <h1>{{ nickname }}</h1>
                <h2>{{ user_id_display }}</h2>
            </div>
        </div>
        <div class="content">
            {{ content_html | safe }}
        </div>
        <div class="footer">
            <div class="brand">{{ wall_mark }}</div>
            <div class="timestamp">{{ render_time }}</div>
        </div>
    </div>
    <script>
        window.onload = function () {
            const container = document.querySelector('.container');
            const contentHeight = container.scrollHeight;
            const pageHeight4in = 364; // 4 inches = 96px * 4

            let pageSize = '';
            if (contentHeight <= pageHeight4in) {
                pageSize = '4in 4in';
            } else if (contentHeight >= 2304) {
                pageSize = '4in 24in';
            } else {
                const containerHeightInInches = (contentHeight / 96 + 0.1).toFixed(2);
                pageSize = '4in ' + containerHeightInInches + 'in';
            }

            const style = document.createElement('style');
            style.innerHTML = '@page { size: ' + pageSize + '; margin: 0 !important; }';
            document.head.appendChild(style);

            const watermarkText = "{{ watermark_text }}";
            if (watermarkText && watermarkText.trim() !== '') {
              addWatermark({
                text: watermarkText,
                opacity: 0.12,
                angle: 24,
                fontSize: 40,
                tile: 480,
                jitter: 10
              });
            }

            function addWatermark(opts) {
                const container = document.querySelector('.container');

                let overlay = container.querySelector('.wm-overlay');
                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.className = 'wm-overlay';
                    container.appendChild(overlay);
                } else {
                    overlay.innerHTML = '';
                }

                const W = container.clientWidth;
                const H = container.scrollHeight; // 高度按内容
                overlay.style.width = W + 'px';
                overlay.style.height = H + 'px';

                const text = String(opts.text);
                const opacity = (typeof opts.opacity === 'number') ? opts.opacity : 0.12;
                const angle = Number.isFinite(opts.angle) ? opts.angle : 24;
                const fontSize = Number.isFinite(opts.fontSize) ? opts.fontSize : 40;
                const tile = Number.isFinite(opts.tile) ? opts.tile : 480;
                const jitter = Number.isFinite(opts.jitter) ? opts.jitter : 10;

                // 先创建一个隐藏样本元素，量出旋转后的包围盒尺寸
                const probe = document.createElement('span');
                probe.className = 'wm-item';
                probe.textContent = text;
                probe.style.fontSize = fontSize + 'px';
                probe.style.opacity = opacity.toString();
                probe.style.transform = `rotate(-${angle}deg)`;
                probe.style.visibility = 'hidden';
                probe.style.left = '-9999px';
                probe.style.top = '-9999px';
                overlay.appendChild(probe);
                const rect = probe.getBoundingClientRect();
                const stampW = rect.width;
                const stampH = rect.height;
                overlay.removeChild(probe);

                // 计算网格：仅在容器内布点，保证任何抖动后也不会越界
                const padX = Math.ceil(stampW * 0.5);
                const padY = Math.ceil(stampH * 0.5);
                const cols = Math.max(1, Math.floor((W - 2*padX) / tile) + 1);
                const rows = Math.max(1, Math.floor((H - 2*padY) / tile) + 1);

                // —— 水平居中 ——
                const centerX = W / 2;
                const gridSpanX = (cols - 1) * tile;
                const firstCX = centerX - gridSpanX / 2;

                const centerVertical = false;
                const baseCY0 = centerVertical ? (H/2 - ((rows - 1) * tile) / 2) : (padY + stampH/2);

                for (let r = 0; r < rows; r++) {
                  for (let c = 0; c < cols; c++) {
                    const span = document.createElement('span');
                    span.className = 'wm-item';
                    span.textContent = text;
                    span.style.fontSize = fontSize + 'px';
                    span.style.opacity  = opacity.toString();
                    span.style.transform = `rotate(-${angle}deg)`;

                    // 交错排布（可选，让视觉更满）
                    const stagger = (r % 2) ? tile / 2 : 0;

                    // 以“中心点”定位
                    const cx = firstCX + c * tile + stagger;
                    const cy = baseCY0 + r * tile;

                    // 轻微抖动
                    const jx = jitter ? (Math.random()*2-1)*jitter : 0;
                    const jy = jitter ? (Math.random()*2-1)*jitter : 0;

                    // 转成左上角坐标并限界
                    let x = Math.round(cx + jx - stampW / 2);
                    let y = Math.round(cy + jy - stampH / 2);
                    x = Math.max(0, Math.min(W - stampW, x));
                    y = Math.max(0, Math.min(H - stampH, y));

                    span.style.left = x + 'px';
                    span.style.top  = y + 'px';
                    overlay.appendChild(span);
                  }
                }
            }
        };
    </script>
</body>
</html>'''
        return Template(template_str)
        
    async def render_html(self, data: Dict[str, Any]) -> str:
        """渲染HTML页面"""
        # 每次渲染前重置链接收集器
        self._collected_links: List[str] = []
        # 获取基本信息
        sender_id = data.get('sender_id', '10000')
        nickname = data.get('nickname', '匿名用户')
        # 兼容 needpriv=true 的匿名逻辑
        is_anonymous = data.get('is_anonymous', False) or str(data.get('needpriv', '')).lower() == 'true'
        watermark_text = data.get('watermark_text', '')
        
        # 如果匿名，修改显示信息
        if is_anonymous:
            sender_id = '10000'
            nickname = '匿名'
            user_id_display = ''
            show_avatar = True
        else:
            user_id_display = sender_id
            show_avatar = True
            
        # 生成头像URL：匿名时使用透明占位，且不渲染头像元素
        if is_anonymous:
            avatar_url = f"https://qlogo2.store.qq.com/qzone/100000/100000/100"
        else:
            avatar_url = f"https://qlogo2.store.qq.com/qzone/{sender_id}/{sender_id}/640"
        
        # 渲染消息内容
        content_html = self.render_messages(data.get('messages', []))
        
        # 渲染HTML
        html = self.template.render(
            avatar_url=avatar_url,
            nickname=nickname,
            user_id_display=user_id_display,
            content_html=content_html,
            watermark_text=watermark_text,
            show_avatar=show_avatar,
            render_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            wall_mark=data.get('wall_mark') or 'XWall',
            font_family=self.settings.rendering.font_family
        )
        
        return html
        
    def render_messages(self, messages: List[Dict[str, Any]]) -> str:
        """渲染消息列表为HTML"""
        html_parts = []
        
        for msg in messages:
            msg_type = msg.get('type')
            
            if msg_type == 'text':
                html_parts.append(self.render_text(msg))
            elif msg_type == 'image':
                html_parts.append(self.render_image(msg))
            elif msg_type == 'video':
                html_parts.append(self.render_video(msg))
            elif msg_type == 'file':
                html_parts.append(self.render_file(msg))
            elif msg_type == 'face':
                html_parts.append(self.render_face(msg))
            elif msg_type == 'poke':
                html_parts.append(self.render_poke(msg))
            elif msg_type == 'forward':
                html_parts.append(self.render_forward(msg))
            elif msg_type == 'reply':
                html_parts.append(self.render_reply(msg))
            elif msg_type == 'json':
                html_parts.append(self.render_card(msg))
            elif msg.get('message'):
                # 嵌套消息
                for sub_msg in msg.get('message', []):
                    html_parts.append(self.render_messages([sub_msg]))
                    
        return '\n'.join(html_parts)
        
    def render_text(self, msg: Dict[str, Any]) -> str:
        """渲染文本消息"""
        text = msg.get('data', {}).get('text', '')
        # 识别文本中的链接并转为可点击锚点
        linkified, links = self._linkify_and_collect(text)
        self._collect_links(links)
        return f'<div class="bubble">{linkified}</div>'
        
    def render_image(self, msg: Dict[str, Any]) -> str:
        """渲染图片消息"""
        data = msg.get('data', {})
        url = data.get('url', '')
        # 将本地路径/file:// 转为 data:URI 以便在无权限的浏览器上下文中可渲染
        src = self._resolve_image_src(url)
        # 不再收集或展示图片的“原始链接”等，避免将图片渲染成链接
        return f'<img src="{src}" alt="Image">'
        
    def render_video(self, msg: Dict[str, Any]) -> str:
        """渲染视频消息"""
        data = msg.get('data', {})
        url = data.get('url') or data.get('file') or ''
        return f'''<video controls autoplay muted>
            <source src="{url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>'''
        
    def render_file(self, msg: Dict[str, Any]) -> str:
        """渲染文件消息"""
        data = msg.get('data', {})
        file_name = data.get('file', '未命名文件')
        file_size = data.get('file_size', 0)
        
        # 根据文件扩展名选择图标
        ext = Path(file_name).suffix.lower()
        icon = self.get_file_icon(ext)
        
        # 格式化文件大小（humanfriendly）
        try:
            size_str = format_size(int(file_size), binary=False)
        except Exception:
            size_str = format_size(float(file_size), binary=False)
            
        href = self._file_href(file_name)
        return f'''<div class="file-block">
            <img class="file-icon" src="{icon}" alt="File Icon">
            <div class="file-info">
                <a class="file-name" href="{href}" download>{self._html(file_name)}</a>
                <div class="file-meta">{size_str}</div>
            </div>
        </div>'''
        
    def render_face(self, msg: Dict[str, Any]) -> str:
        """渲染QQ表情"""
        data = msg.get('data', {})
        face_id = str(data.get('id', '0'))
        face_text = ''
        try:
            raw = data.get('raw') or {}
            face_text = raw.get('faceText') or ''
            # 判断是否为“大表情/贴纸”：faceType >= 2 视为大表情
            face_type_val = raw.get('faceType')
            is_sticker = False
            try:
                if face_type_val is not None and int(face_type_val) >= 2:
                    is_sticker = True
            except Exception:
                is_sticker = False
        except Exception:
            pass
        src = self._get_face_src(face_id)
        alt = face_text or '表情'
        css_class = 'sticker' if locals().get('is_sticker') else 'cqface'
        return f'<img class="{css_class}" src="{src}" alt="{alt}">'
        
    def render_poke(self, msg: Dict[str, Any]) -> str:
        """渲染戳一戳"""
        return '<img class="poke-icon" src="/static/source/poke.png" alt="戳一戳">'
        
    def render_forward(self, msg: Dict[str, Any]) -> str:
        """渲染合并转发"""
        data = msg.get('data', {})
        raw = data.get('messages') or data.get('content') or []

        # 归一化为若干“片段列表”，每个片段列表表示一条转发消息内的消息段数组
        segment_lists: List[List[Dict[str, Any]]] = []
        if isinstance(raw, list):
            if raw and isinstance(raw[0], dict) and 'type' in raw[0]:
                # 形如：[ {type:..., data:{...}}, ... ] -> 单条消息
                segment_lists.append(raw)  # treat as one forwarded item
            else:
                # 形如：[ { message:[...] } | { content:[...] } | {type:...,data:{...}} , ... ]
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    if isinstance(item.get('message'), list) and item.get('message'):
                        segment_lists.append(item.get('message') or [])
                    elif isinstance(item.get('content'), list) and item.get('content'):
                        segment_lists.append(item.get('content') or [])
                    elif 'type' in item:
                        segment_lists.append([item])

        blocks: List[str] = []
        for segs in segment_lists:
            inner_html = self.render_messages(segs)
            blocks.append(f'<div class="forward-item">{inner_html}</div>')

        return f'''<div class="forward-title">合并转发聊天记录</div>
        <div class="forward">
            {''.join(blocks)}
        </div>'''
        
    def render_reply(self, msg: Dict[str, Any]) -> str:
        """渲染回复消息"""
        data = msg.get('data', {})
        reply_id = data.get('id', '')
        # 可用字段尝试提取元信息和预览
        author = data.get('name') or data.get('nickname') or (data.get('sender') or {}).get('nickname') or ''
        preview_text = data.get('text') or data.get('content') or ''
        # 链接化预览文本
        preview_html, _ = self._linkify_and_collect(str(preview_text))
        meta = f"回复消息{(' · ' + self._html(author)) if author else ''}"
        return f'''<div class="reply" data-mid="{self._html(reply_id)}">
            <div class="reply-meta">{meta}</div>
            <div class="reply-body">{preview_html or '引用的消息'}</div>
        </div>'''
        
    def render_card(self, msg: Dict[str, Any]) -> str:
        """渲染卡片消息（支持 contact/miniapp/news/generic），并在有跳转时渲染二维码"""
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
            return '<div class="card">卡片消息</div>'

        view = str(card_data.get('view') or '').lower()
        meta = card_data.get('meta') or {}

        url = self._extract_card_url(card_data)
        if url:
            self._collect_links([url])
            qr_src = self._qr_data_uri(url)
        else:
            qr_src = None

        # contact
        if view == 'contact' and isinstance(meta.get('contact'), dict):
            c = meta.get('contact') or {}
            avatar = c.get('avatar') or ''
            nickname = c.get('nickname') or '联系人'
            contact_text = c.get('contact') or ''
            tag = c.get('tag')
            tag_icon = c.get('tagIcon')
            href = url or '#'
            parts = []
            parts.append(f'<a class="card card-contact" href="{href}" target="_blank" rel="noopener noreferrer">')
            parts.append('<div class="card-media">')
            parts.append(f'<img src="{avatar}" alt="avatar">')
            parts.append('</div>')
            parts.append('<div class="card-body">')
            parts.append(f'<div class="card-title">{self._html(nickname)}</div>')
            if contact_text:
                parts.append(f'<div class="card-desc">{self._html(contact_text)}</div>')
            if tag or tag_icon:
                parts.append('<div class="card-tag-row">')
                if tag_icon:
                    parts.append(f'<img class="card-tag-icon" src="{tag_icon}" alt="">')
                if tag:
                    parts.append(f'<span class="card-tag">{self._html(tag)}</span>')
                parts.append('</div>')
            parts.append('</div>')
            if qr_src:
                parts.append(f'<img class="qr-code" src="{qr_src}" alt="QR">')
            parts.append('</a>')
            return ''.join(parts)

        # miniapp
        if view == 'miniapp' and isinstance(meta.get('miniapp'), dict):
            m = meta.get('miniapp') or {}
            href = (m.get('jumpUrl') or m.get('doc_url') or url or '#')
            parts = []
            parts.append(f'<a class="card card-vertical card-miniapp" href="{href}" target="_blank" rel="noopener noreferrer">')
            parts.append('<div class="card-header">')
            parts.append('<div class="card-header-left">')
            if m.get('source') or m.get('sourcelogo'):
                parts.append('<div class="brand-inline">')
                if m.get('sourcelogo'):
                    parts.append(f'<img class="brand-icon" src="{m.get("sourcelogo")}" alt="">')
                if m.get('source'):
                    parts.append(f'<span class="brand-text">{self._html(m.get("source"))}</span>')
                parts.append('</div>')
            title = m.get('title') or '小程序卡片'
            parts.append(f'<div class="card-title">{self._html(title)}</div>')
            parts.append('</div>')
            if qr_src:
                parts.append(f'<img class="qr-code" src="{qr_src}" alt="QR">')
            parts.append('</div>')
            if m.get('preview'):
                parts.append('<div class="card-preview">')
                parts.append(f'<img src="{m.get("preview")}" alt="preview">')
                parts.append('</div>')
            if m.get('tag') or m.get('tagIcon'):
                parts.append('<div class="card-tag-row">')
                if m.get('tagIcon'):
                    parts.append(f'<img class="card-tag-icon" src="{m.get("tagIcon")}" alt="">')
                if m.get('tag'):
                    parts.append(f'<span class="card-tag">{self._html(m.get("tag"))}</span>')
                parts.append('</div>')
            parts.append('</a>')
            return ''.join(parts)

        # news
        if view == 'news' and isinstance(meta.get('news'), dict):
            n = meta.get('news') or {}
            href = (n.get('jumpUrl') or url or '#')
            parts = []
            parts.append(f'<a class="card card-news" href="{href}" target="_blank" rel="noopener noreferrer">')
            parts.append('<div class="card-header">')
            if n.get('preview'):
                parts.append(f'<img class="thumb" src="{n.get("preview")}" alt="thumb">')
            parts.append('<div class="card-header-right">')
            title = n.get('title') or '分享'
            parts.append(f'<div class="card-title">{self._html(title)}</div>')
            parts.append('</div>')
            if qr_src:
                parts.append(f'<img class="qr-code" src="{qr_src}" alt="QR">')
            parts.append('</div>')
            # bottom
            parts.append('<div class="card-bottom">')
            parts.append('<div class="card-bottom-left">')
            if n.get('desc'):
                parts.append(f'<div class="card-desc">{self._html(n.get("desc"))}</div>')
            if n.get('tag') or n.get('tagIcon'):
                parts.append('<div class="card-tag-row">')
                if n.get('tagIcon'):
                    parts.append(f'<img class="card-tag-icon" src="{n.get("tagIcon")}" alt="">')
                if n.get('tag'):
                    parts.append(f'<span class="card-tag">{self._html(n.get("tag"))}</span>')
                parts.append('</div>')
            parts.append('</div>')
            parts.append('</div>')
            parts.append('</a>')
            return ''.join(parts)

        # generic
        g = self._first_entry_value(meta)
        title = g.get('title') or card_data.get('prompt') or (card_data.get('view') or '卡片')
        desc = g.get('desc') or ''
        preview = g.get('preview')
        parts = []
        parts.append('<div class="card card-vertical">')
        if preview:
            parts.append('<div class="card-preview">')
            parts.append(f'<img src="{preview}" alt="preview">')
            parts.append('</div>')
        parts.append('<div class="card-body">')
        parts.append(f'<div class="card-title">{self._html(title)}</div>')
        if desc:
            parts.append(f'<div class="card-desc">{self._html(desc)}</div>')
        if qr_src:
            parts.append('<div class="qr-wrap">')
            parts.append(f'<img class="qr-code" src="{qr_src}" alt="QR">')
            parts.append('</div>')
        parts.append('</div>')
        parts.append('</div>')
        return ''.join(parts)
            
    def get_file_icon(self, ext: str) -> str:
        """根据文件扩展名获取图标"""
        icon_map = {
            '.doc': 'doc.png',
            '.docx': 'doc.png',
            '.pdf': 'pdf.png',
            '.xls': 'xls.png',
            '.xlsx': 'xls.png',
            '.ppt': 'ppt.png',
            '.pptx': 'ppt.png',
            '.zip': 'zip.png',
            '.rar': 'rar.png',
            '.txt': 'txt.png',
            '.mp3': 'audio.png',
            '.mp4': 'video.png',
            '.jpg': 'image.png',
            '.png': 'image.png',
            '.gif': 'image.png',
        }
        
        icon = icon_map.get(ext, 'unknown.png')
        return f"/static/file/{icon}"

    # ===== 工具方法 =====
    def _html(self, text: Any) -> str:
        try:
            import html as _html
            return _html.escape(str(text))
        except Exception:
            return str(text)

    def _anchor(self, url: str) -> str:
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'

    def _linkify_and_collect(self, text: str) -> (str, List[str]):
        """将文本中的URL替换为可点击链接，并返回收集到的URL列表（linkify-it-py）"""
        if not text:
            return '', []
        # 先替换换行为 <br>
        text_html = text.replace('\n', '<br>')

        # 使用 LinkifyIt 解析链接
        collected: List[str] = []
        parts: List[str] = []
        last_idx = 0
        matches = self._linkify.match(text)
        for m in matches or []:
            start = m.index
            end = m.last_index
            url = m.url if hasattr(m, 'url') else text[start:end]
            # 添加前一段普通文本（替换其内部换行）
            if start > last_idx:
                chunk = text[last_idx:start]
                parts.append(chunk.replace('\n', '<br>'))
            # 追加链接锚点
            if url:
                collected.append(url)
                parts.append(self._anchor(url))
            else:
                # 万一无 url 字段，直接原样输出
                chunk = text[start:end]
                parts.append(chunk.replace('\n', '<br>'))
            last_idx = end
        # 追加剩余文本
        if last_idx < len(text):
            parts.append(text[last_idx:].replace('\n', '<br>'))

        return ''.join(parts) or text_html, collected

    def _collect_links(self, links: List[str]):
        if not links:
            return
        seen = set(self._collected_links)
        for u in links:
            if u and u not in seen:
                self._collected_links.append(u)
                seen.add(u)

    def _extract_urls_from_object(self, obj: Any) -> List[str]:
        """从任意嵌套对象中提取URL字符串"""
        result: List[str] = []
        try:
            if isinstance(obj, dict):
                for v in obj.values():
                    result.extend(self._extract_urls_from_object(v))
            elif isinstance(obj, list):
                for item in obj:
                    result.extend(self._extract_urls_from_object(item))
            elif isinstance(obj, str):
                _, links = self._linkify_and_collect(obj)
                result.extend(links)
        except Exception:
            pass
        # 去重并保持顺序
        seen: set = set()
        unique = [x for x in result if not (x in seen or seen.add(x))]
        return unique

    # 将路径/URI 解析为适用于 HTML 的 <img src> 值
    def _resolve_image_src(self, url: str) -> str:
        try:
            if not url:
                return ''
            if url.startswith('data:image'):
                return url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            # file:// -> 本地路径
            path = url
            if url.startswith('file://'):
                path = self._file_uri_to_path(url)
            # 直接本地路径：转为 data URI 内联，避免浏览器 file 权限限制
            if os.path.exists(path):
                return self._image_to_data_uri(path)
            return url
        except Exception:
            return url

    def _file_uri_to_path(self, uri: str) -> str:
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
        try:
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                # 兜底按 png
                mime = 'image/png'
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
            return f'data:{mime};base64,{b64}'
        except Exception:
            return path

    def _get_face_src(self, face_id: str) -> str:
        """根据 face_id 返回 data-URI 图片，优先从 data/qlottie，其次回退 legacy 资源目录。"""
        # 缓存
        if not hasattr(self, '_face_cache'):
            self._face_cache: Dict[str, str] = {}
        cached = self._face_cache.get(face_id)
        if cached:
            return cached

        # 候选目录与文件名模式
        candidate_dirs = [
            Path('static/qlottie'),
            Path('qlottie'),
        ]
        name_patterns = [
            f"{face_id}.png", f"{face_id}.webp", f"{face_id}.gif",
            f"face_{face_id}.png", f"sticker_{face_id}.png"
        ]

        for d in candidate_dirs:
            try:
                if not d.exists():
                    continue
                for name in name_patterns:
                    p = d / name
                    if p.exists():
                        mime = 'image/png'
                        if p.suffix.lower() == '.gif':
                            mime = 'image/gif'
                        elif p.suffix.lower() == '.webp':
                            mime = 'image/webp'
                        with open(p, 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode('ascii')
                        data_uri = f"data:{mime};base64,{b64}"
                        self._face_cache[face_id] = data_uri
                        return data_uri
            except Exception:
                continue

        # 找不到时返回一个透明占位（1x1 PNG）
        transparent_png = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAA' 
            'AAC0lEQVR42mP8/x8AAwMCAO2e4eYAAAAASUVORK5CYII='
        )
        data_uri = f"data:image/png;base64,{transparent_png}"
        self._face_cache[face_id] = data_uri
        return data_uri

    def _qr_data_uri(self, url: str) -> str:
        """为给定 URL 生成二维码并以 data URI 返回，带缓存。"""
        if not hasattr(self, '_qr_cache'):
            self._qr_cache: Dict[str, str] = {}
        cached = self._qr_cache.get(url)
        if cached:
            return cached
        try:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=3, border=0)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            data_uri = f"data:image/png;base64,{b64}"
            self._qr_cache[url] = data_uri
            return data_uri
        except Exception:
            return ''

    def _extract_card_url(self, card: Dict[str, Any]) -> Optional[str]:
        """仿照 gotohtml.sh 的 card_url 逻辑提取跳转 URL。"""
        try:
            view = str(card.get('view') or '').lower()
            meta = card.get('meta') or {}
            if view == 'contact' and isinstance(meta.get('contact'), dict):
                c = meta.get('contact') or {}
                jump = c.get('jumpUrl')
                if isinstance(jump, str) and jump:
                    return jump
                text = c.get('contact') or ''
                if isinstance(text, str):
                    m = re.search(r'(?:uin=|)(?P<uin>\d{5,})', text)
                    if m:
                        return f'https://mp.qzone.qq.com/u/{m.group("uin")}'
                return None
            if view == 'miniapp' and isinstance(meta.get('miniapp'), dict):
                m = meta.get('miniapp') or {}
                return m.get('jumpUrl') or m.get('doc_url')
            if view == 'news' and isinstance(meta.get('news'), dict):
                n = meta.get('news') or {}
                return n.get('jumpUrl')
            # generic: 从 meta 的首个条目里找 jumpUrl
            g = self._first_entry_value(meta)
            if g.get('jumpUrl'):
                return g.get('jumpUrl')
            # 兜底：在整个对象内找第一个 URL
            urls = self._extract_urls_from_object(card)
            return urls[0] if urls else None
        except Exception:
            return None

    def _first_entry_value(self, d: Any) -> Dict[str, Any]:
        if isinstance(d, dict) and d:
            try:
                # Python 3.7+ preserves insertion order
                first_key = next(iter(d.keys()))
                v = d.get(first_key)
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
        return {}

    def _file_href(self, path: str) -> str:
        """生成 file:// 超链接，兼容绝对路径（含 Windows 盘符）与相对路径。"""
        if not path:
            return '#'
        try:
            p = Path(path)
            if p.is_absolute():
                return p.as_uri()
        except Exception:
            pass
        # 相对路径：尽力转义
        safe = path.replace('\\', '/')
        return f'file://{quote(safe)}'
