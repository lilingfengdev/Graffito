"""HTML渲染器"""
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from jinja2 import Template

from core.plugin import ProcessorPlugin


class HTMLRenderer(ProcessorPlugin):
    """HTML渲染器，将消息渲染为HTML页面"""
    
    def __init__(self):
        super().__init__("html_renderer", {})
        self.template = self.load_template()
        
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
        return data
        
    def load_template(self) -> Template:
        """加载HTML模板"""
        template_str = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OQQWall消息页</title>
    <style>
        :root {
            --primary-color: #007aff;
            --secondary-color: #71a1cc;
            --background-color: #f2f2f2;
            --card-background: #ffffff;
            --text-primary: #000000;
            --text-secondary: #666666;
            --text-muted: #888888;
            --border-color: #e0e0e0;
            --spacing-sm: 6px;
            --spacing-md: 8px;
            --spacing-lg: 10px;
            --spacing-xl: 12px;
            --spacing-xxl: 20px;
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --shadow-sm: 0 0 5px rgba(0, 0, 0, 0.1);
            --shadow-md: 0px 0px 6px rgba(0, 0, 0, 0.2);
            --font-family: "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
            --font-size-sm: 12px;
            --font-size-md: 14px;
            --font-size-lg: 24px;
            --container-width: 4in;
            --avatar-size: 50px;
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
            border-radius: var(--radius-lg);
            padding: 4px 8px;
            margin-bottom: var(--spacing-lg);
            word-break: break-word;
            max-width: fit-content;
            box-shadow: var(--shadow-sm);
            line-height: 1.5;
        }

        .content img:not(.cqface), .content video {
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
            width: 20px !important;
            height: 20px !important;
            margin: 0 !important;
            display: inline !important;
            padding: 0 !important;
            transform: translateY(-0.1em);
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{{ avatar_url }}" alt="Profile Image">
            <div class="header-text">
                <h1>{{ nickname }}</h1>
                <h2>{{ user_id_display }}</h2>
            </div>
        </div>
        <div class="content">
            {{ content_html | safe }}
        </div>
    </div>
    <script>
        window.onload = function () {
            const container = document.querySelector('.container');
            const contentHeight = container.scrollHeight;
            const pageHeight4in = 364;

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

            // 添加水印（如果配置了）
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
        };

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
            const H = container.scrollHeight;
            overlay.style.width = W + 'px';
            overlay.style.height = H + 'px';

            const text = String(opts.text);
            const opacity = opts.opacity || 0.12;
            const angle = opts.angle || 24;
            const fontSize = opts.fontSize || 40;
            const tile = opts.tile || 480;
            const jitter = opts.jitter || 10;

            // 创建水印元素
            const cols = Math.max(1, Math.floor(W / tile));
            const rows = Math.max(1, Math.floor(H / tile));

            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    const span = document.createElement('span');
                    span.className = 'wm-item';
                    span.textContent = text;
                    span.style.fontSize = fontSize + 'px';
                    span.style.opacity = opacity.toString();
                    
                    const x = c * tile + (Math.random() * 2 - 1) * jitter;
                    const y = r * tile + (Math.random() * 2 - 1) * jitter;
                    
                    span.style.left = x + 'px';
                    span.style.top = y + 'px';
                    overlay.appendChild(span);
                }
            }
        }
    </script>
</body>
</html>'''
        return Template(template_str)
        
    async def render_html(self, data: Dict[str, Any]) -> str:
        """渲染HTML页面"""
        # 获取基本信息
        sender_id = data.get('sender_id', '10000')
        nickname = data.get('nickname', '匿名用户')
        is_anonymous = data.get('is_anonymous', False)
        watermark_text = data.get('watermark_text', '')
        
        # 如果匿名，修改显示信息
        if is_anonymous:
            sender_id = '10000'
            nickname = '匿名'
            user_id_display = ''
        else:
            user_id_display = sender_id
            
        # 生成头像URL
        avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={sender_id}&spec=640&img_type=jpg"
        
        # 渲染消息内容
        content_html = self.render_messages(data.get('messages', []))
        
        # 渲染HTML
        html = self.template.render(
            avatar_url=avatar_url,
            nickname=nickname,
            user_id_display=user_id_display,
            content_html=content_html,
            watermark_text=watermark_text
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
        text = text.replace('\n', '<br>')
        return f'<div class="bubble">{text}</div>'
        
    def render_image(self, msg: Dict[str, Any]) -> str:
        """渲染图片消息"""
        url = msg.get('data', {}).get('url', '')
        return f'<img src="{url}" alt="Image">'
        
    def render_video(self, msg: Dict[str, Any]) -> str:
        """渲染视频消息"""
        url = msg.get('data', {}).get('url', '')
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
        
        # 格式化文件大小
        if file_size > 1048576:
            size_str = f"{file_size / 1048576:.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} B"
            
        return f'''<div class="file-block">
            <img class="file-icon" src="{icon}" alt="File Icon">
            <div class="file-info">
                <a class="file-name" href="#" download>{file_name}</a>
                <div class="file-meta">{size_str}</div>
            </div>
        </div>'''
        
    def render_face(self, msg: Dict[str, Any]) -> str:
        """渲染QQ表情"""
        face_id = msg.get('data', {}).get('id', '0')
        # 这里应该有一个表情ID到图片的映射
        return f'<img class="cqface" src="/static/face/{face_id}.png" alt="表情">'
        
    def render_poke(self, msg: Dict[str, Any]) -> str:
        """渲染戳一戳"""
        return '<img class="poke-icon" src="/static/poke.png" alt="戳一戳">'
        
    def render_forward(self, msg: Dict[str, Any]) -> str:
        """渲染合并转发"""
        data = msg.get('data', {})
        messages = data.get('messages', data.get('content', []))
        
        items_html = []
        for item in messages:
            item_msgs = item.get('message', [])
            item_html = self.render_messages(item_msgs)
            items_html.append(f'<div class="forward-item">{item_html}</div>')
            
        return f'''<div class="forward-title">合并转发聊天记录</div>
        <div class="forward">
            {''.join(items_html)}
        </div>'''
        
    def render_reply(self, msg: Dict[str, Any]) -> str:
        """渲染回复消息"""
        data = msg.get('data', {})
        reply_id = data.get('id', '')
        
        # 这里应该查找被回复的消息内容
        return f'''<div class="reply" data-mid="{reply_id}">
            <div class="reply-meta">回复消息</div>
            <div class="reply-body">引用的消息</div>
        </div>'''
        
    def render_card(self, msg: Dict[str, Any]) -> str:
        """渲染卡片消息"""
        data = msg.get('data', {}).get('data', '{}')
        
        try:
            # 解析JSON卡片数据
            card_data = json.loads(data)
            title = card_data.get('prompt', '卡片消息')
            desc = card_data.get('desc', '')
            
            return f'''<div class="card">
                <div class="card-title">{title}</div>
                <div class="card-desc">{desc}</div>
            </div>'''
        except:
            return '<div class="card">卡片消息</div>'
            
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
        return f"/static/icons/{icon}"
