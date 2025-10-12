"""LLM处理器 - 重构版本"""
import json
import asyncio
import os
import time
import hashlib
import base64
import mimetypes
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from PIL import Image, ImageFile
from openai import AsyncOpenAI

from config import get_settings
from core.plugin import ProcessorPlugin

ImageFile.LOAD_TRUNCATED_IMAGES = True


class LLMProcessor(ProcessorPlugin):
    """LLM处理器 - 处理投稿内容的LLM分析"""

    def __init__(self):
        settings = get_settings()
        config = settings.llm.dict() if hasattr(settings.llm, 'dict') else settings.llm.__dict__
        super().__init__("llm_processor", config)

        # 初始化异步LLM客户端
        self.client = AsyncOpenAI(
            api_key=self.config.get('api_key'),
            base_url=self.config.get('base_url', 'https://api.openai.com/v1')
        )
        self.text_model = self.config.get('text_model', 'gpt-4o-mini')
        self.vision_model = self.config.get('vision_model', self.text_model)
        self.timeout = self.config.get('timeout', 30)

        # 图片审核配置
        self.skip_image_audit_over_mb = float(getattr(settings.audit, 'skip_image_audit_over_mb', 0.0))
        
        # 图片缓存目录
        cache_root = getattr(settings.system, 'cache_dir', './data/cache')
        self.image_cache_dir = Path(cache_root) / 'chat_images'
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)

        # 消息清理规则
        self._init_cleaning_rules()

    def _init_cleaning_rules(self):
        """初始化消息清理规则"""
        # LLM输入时需要隐藏的字段（输出时保留）
        self.hide_rules = {
            'image': ['data'],
            'video': ['data.file', 'data.file_id', 'data.file_size'],
            'audio': ['data.file', 'data.file_id', 'data.file_size'],
            'file': ['data.file_size'],
            'poke': ['data'],
        }
        # 永久移除的字段
        self.remove_rules = {
            'global': ['file', 'file_id', 'file_size'],
            'image': ['data.file_id', 'data.file_size', 'summary'],
        }

    async def initialize(self):
        """初始化处理器"""
        self.logger.info("LLM处理器初始化完成")

    async def shutdown(self):
        """关闭处理器"""
        pass

    # ==================== 主流程 ====================
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理投稿数据：图片处理 -> LLM分析 -> 生成结果"""
        messages = data.get('messages', [])
        if not messages:
            return data

        # 1. 处理图片（下载、压缩、安全检查）
        images_safe = await self._process_all_images(messages)

        # 2. 准备LLM输入（清理敏感字段）
        lm_messages, original_messages = self._prepare_messages_for_llm(messages)
        
        # 3. 调用LLM分析
        llm_result = await self._analyze_with_llm(lm_messages, data.get('notregular'))
        
        # 4. 构建最终结果
        final_messages = self._build_final_messages(llm_result, original_messages)
        
        # 5. 组装返回数据
        llm_result['messages'] = final_messages
        llm_result['safemsg'] = 'false' if not images_safe else llm_result.get('safemsg', 'true')
        llm_result['segments'] = self._extract_text_segments(final_messages)
        
        data['messages'] = final_messages
        data['llm_result'] = llm_result
        data['is_anonymous'] = llm_result.get('needpriv') == 'true'
        
        return data

    # ==================== 图片处理 ====================
    
    async def _process_all_images(self, messages: List[Dict[str, Any]]) -> bool:
        """处理所有图片：下载、压缩、安全检查"""
        all_safe = True
        
        for msg in self._iter_message_nodes(messages):
            if msg.get('type') != 'image':
                continue
                
            data = msg.get('data', {})
            url = data.get('url') or data.get('file', '')
            if not url:
                continue
            
            try:
                # 处理图片URL（下载远程图片或获取本地路径）
                image_path, original_size = await self._get_image_path(url, data)
                if not image_path:
                    continue
                
                # 压缩图片
                self._compress_image(image_path)
                
                # 安全检查（根据原始大小决定是否跳过）
                if self._should_audit_image(original_size):
                    is_safe, description = await self._check_image_safety(image_path)
                    if not is_safe:
                        all_safe = False
                    if description:
                        msg['describe'] = description
                        
            except Exception as e:
                self.logger.error(f"处理图片失败 {url}: {e}")
        
        return all_safe

    async def _get_image_path(self, url: str, data: dict) -> Tuple[str, int]:
        """获取图片本地路径，下载远程图片"""
        if url.startswith('http://') or url.startswith('https://'):
            # 远程图片：下载到缓存
            data.setdefault('origin_url', url)
            image_path, size = await self._download_image(url)
            if image_path:
                data['url'] = str(Path(image_path).absolute())
            return image_path, size
        else:
            # 本地图片
            path = url.replace('file://', '').lstrip('/')
            if os.name == 'nt' and len(path) > 2 and path[1] == ':':
                # Windows路径修正
                pass
            else:
                path = '/' + path if not path.startswith('/') else path
            
            size = os.path.getsize(path) if os.path.exists(path) else 0
            return path, size

    async def _download_image(self, url: str) -> Tuple[str, int]:
        """下载远程图片到缓存目录"""
        # 生成文件名（优先使用QQ fileid）
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        basename = query.get('fileid', [None])[0] or hashlib.sha1(url.encode()).hexdigest()
        
        ext = Path(parsed.path).suffix.lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
            ext = '.jpg'
        
        filename = f"{basename}{ext}"
        local_path = self.image_cache_dir / filename
        
        # 如果已缓存则复用
        if local_path.exists():
            return str(local_path), local_path.stat().st_size
        
        # 下载图片
        try:
            import httpx
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*',
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                
                # 根据Content-Type纠正扩展名
                ctype = resp.headers.get('Content-Type', '')
                if 'image/' in ctype:
                    new_ext = '.' + ctype.split('/')[-1].split(';')[0]
                    if new_ext in {'.jpeg', '.png', '.gif', '.webp'}:
                        local_path = self.image_cache_dir / f"{basename}{new_ext}"
                
                local_path.write_bytes(resp.content)
                return str(local_path), len(resp.content)
                
        except Exception as e:
            self.logger.warning(f"下载图片失败 {url}: {e}")
            return "", 0

    def _compress_image(self, path: str):
        """压缩图片到合理尺寸"""
        try:
            with Image.open(path) as im:
                im.thumbnail((2048, 2048))
                im.save(path)
        except Exception as e:
            self.logger.warning(f"压缩图片失败 {path}: {e}")

    def _should_audit_image(self, size_bytes: int) -> bool:
        """判断是否需要审核图片"""
        if self.skip_image_audit_over_mb <= 0:
            return True
        threshold = int(self.skip_image_audit_over_mb * 1024 * 1024)
        return size_bytes < threshold

    async def _check_image_safety(self, path: str) -> Tuple[bool, str]:
        """使用Vision模型检查图片安全性并生成描述"""
        if not os.path.exists(path):
            return True, ""

        # 准备图片数据
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = 'image/jpeg'
        
        with open(path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('ascii')
        
        data_url = f"data:{mime_type};base64,{b64_data}"
        
        prompt = (
            '请分析这张图片并回答：\n'
            '1. 安全性：是否含有暴力、色情、政治敏感或攻击性内容？回答 safe 或 unsafe\n'
            '2. 描述：详细描述图片内容（主要元素、场景、风格等）\n\n'
            '格式：\n安全性：[safe/unsafe]\n描述：[内容]'
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }],
                temperature=0.0,
                max_tokens=1000
            )
            
            text = response.choices[0].message.content or ""
            is_safe = 'unsafe' not in text.lower()
            
            # 提取描述
            description = ""
            if '描述：' in text:
                description = text.split('描述：', 1)[1].strip()
            else:
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines:
                    if 'safe' not in line.lower() and not line.startswith('安全性'):
                        description = line
                        break
            
            return is_safe, description
            
        except Exception as e:
            self.logger.error(f"图片安全检查失败: {e}")
            return True, ""

    def _iter_message_nodes(self, messages: List[Dict[str, Any]]):
        """迭代所有消息节点"""
        for item in messages:
            if not isinstance(item, dict):
                continue
            if 'message' in item and isinstance(item['message'], list):
                yield from self._iter_message_nodes(item['message'])
            elif 'type' in item:
                yield item

    # ==================== LLM分析 ====================
    
    def _prepare_messages_for_llm(self, messages: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
        """准备LLM输入：清理敏感字段"""
        original = json.loads(json.dumps(messages))
        cleaned = json.loads(json.dumps(messages))
        
        for msg in self._iter_message_nodes(cleaned):
            msg_type = msg.get('type')
            
            # 应用隐藏规则（仅对LLM输入）
            if msg_type in self.hide_rules:
                for field in self.hide_rules[msg_type]:
                    self._remove_field(msg, field)
            
            # 应用永久移除规则
            for field in self.remove_rules.get('global', []):
                self._remove_field(msg, field)
            
            if msg_type in self.remove_rules:
                for field in self.remove_rules[msg_type]:
                    self._remove_field(msg, field)
        
        return cleaned, original

    def _remove_field(self, obj: dict, field_path: str):
        """移除对象中的字段（支持点号路径）"""
        parts = field_path.split('.')
        current = obj
        
        for i, part in enumerate(parts[:-1]):
            if not isinstance(current, dict) or part not in current:
                return
            current = current[part]
        
        if isinstance(current, dict):
            current.pop(parts[-1], None)

    async def _analyze_with_llm(self, messages: List[Dict], notregular: Any) -> Dict[str, Any]:
        """调用LLM分析投稿"""
        input_data = {"notregular": notregular, "messages": messages}
        input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
        
        prompt = f"""当前时间 {time.time()}
以下内容是一组按时间顺序排列的校园墙投稿聊天记录：

{input_json}

请根据以下标准，提取出这些消息中属于**最后一组投稿**的信息：

### 分组标准
- 通常以关键词"在吗"、"投稿"、"墙"等开始，但这些关键词可能出现在中途或根本不出现。
- 属于同一组投稿的消息，时间间隔一般较近（通常小于 600 秒），但也存在例外。
- 投稿内容可能包含文本、图片（image）、视频（video）、文件（file）、戳一戳（poke）、合并转发的聊天记录（forward）等多种类型。
- 大多数情况下该记录只包含一组投稿，这种情况下认为所有消息都在组中，偶尔可能有多组，需要你自己判断。
- 信息只可能包含多个完整的投稿，不可能出现半个投稿+一个投稿的情况，如果真的出现了，说明你判断错误，前面那个"半个投稿"，是后面投稿的一部分。

### 你需要给出的判断

- `needpriv`（是否需要匿名）  
  - 如果信息中明确表达"匿名"意图或使用谐音字（如："匿"、"腻"、"拟"、"逆"、"🐎"、"🐴"、"马" 等），则为 `true`。  
  - 当信息仅包含单个含义模糊的字或 emoji 时，也应考虑匿名的可能性。  
  - 否则为 `false`。
  - 如果用户明确说了不匿(也可能是不腻，不码，不马之类的谐音内容)，那么一定为`false`

- `safemsg`（投稿是否安全）  
  - 投稿若包含攻击性言论、辱骂内容、敏感政治信息，应判定为 `false`。  
  - 否则为 `true`。

- `isover`（投稿是否完整）  
  - 若投稿者明确表示"发完了"、"没了"、"完毕"等；或投稿语义完整且最后一条消息距离当前时间较远，则为 `true`。  
  - 若存在"没发完"之类的未结束迹象，或最后消息距当前时间较近且不明确，则为 `false`。

- `notregular`（投稿是否异常）  
  - 若投稿者明确表示"不合常规"或你主观判断此内容异常，则为 `true`。  
  - 否则为 `false`。

- `summary`（投稿内容总结）  
  - 生成一段简洁的投稿内容总结（100-200字），包括：
    1. 投稿的核心主题或话题
    2. 主要内容和关键信息
    3. 情感倾向（正面/负面/中性）
    4. 是否包含图片、视频等多媒体内容
  - 总结应客观、准确，便于后续审核和管理使用

### 输出格式

**严格按照下面的 JSON 格式输出**，仅填写最后一组投稿的 `message_id`，不要输出任何额外的文字或说明：

{{
"needpriv": "true" 或 "false",
"safemsg": "true" 或 "false",
"isover": "true" 或 "false",
"notregular": "true" 或 "false",
"summary": "投稿内容的简洁总结（100-200字）",
"messages": [
    "message_id1",
    "message_id2",
    ...
]
}}"""

        try:
            result = await self._call_llm_json(prompt)
            if not result:
                return self._get_default_result()
            
            # 标准化布尔值
            for key in ['needpriv', 'safemsg', 'isover', 'notregular']:
                val = result.get(key)
                if isinstance(val, bool):
                    result[key] = 'true' if val else 'false'
                elif isinstance(val, str):
                    result[key] = 'true' if val.strip().lower() == 'true' else 'false'
                else:
                    result[key] = 'false' if key in ('needpriv', 'notregular') else 'true'
            
            return result
            
        except Exception as e:
            self.logger.error(f"LLM分析失败: {e}")
            return self._get_default_result()

    def _get_default_result(self) -> Dict[str, Any]:
        """获取默认分析结果"""
        return {
            'needpriv': 'false',
            'safemsg': 'true',
            'isover': 'true',
            'notregular': 'false',
            'summary': '',
            'messages': []
        }

    async def _call_llm_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """调用LLM并返回JSON"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {'role': 'system', 'content': '你是校园墙投稿管理员，只返回规范JSON'},
                    {'role': 'user', 'content': prompt}
                ],
                stream=True,
                timeout=1000,
            )
            
            # 收集流式响应
            text = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    text += chunk.choices[0].delta.content
            
            return json.loads(text.strip())
            
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            return None

    # ==================== 结果构建 ====================
    
    def _build_final_messages(self, llm_result: Dict, original_messages: List[Dict]) -> List[Dict]:
        """根据LLM结果构建最终消息列表"""
        # 构建message_id查找表
        lookup = {str(msg.get('message_id')): msg for msg in original_messages if msg.get('message_id')}
        
        # 提取选中的消息
        selected_ids = llm_result.get('messages', [])
        final_messages = []
        
        for msg_id in selected_ids:
            if str(msg_id) in lookup:
                final_messages.append(self._clean_for_output(lookup[str(msg_id)]))
        
        # 如果没有选中任何消息，返回全部
        if not final_messages:
            final_messages = [self._clean_for_output(msg) for msg in original_messages]
        
        return final_messages

    def _clean_for_output(self, message: Dict) -> Dict:
        """清理输出消息（仅移除永久删除的字段）"""
        cleaned = json.loads(json.dumps(message))
        
        for msg in self._iter_message_nodes([cleaned]):
            for field in self.remove_rules.get('global', []):
                self._remove_field(msg, field)
            
            msg_type = msg.get('type')
            if msg_type in self.remove_rules:
                for field in self.remove_rules[msg_type]:
                    # 不移除仅用于隐藏的字段
                    if msg_type not in self.hide_rules or field not in self.hide_rules[msg_type]:
                        self._remove_field(msg, field)
        
        return cleaned

    def _extract_text_segments(self, messages: List[Dict], limit: int = 200) -> List[str]:
        """提取文本段落"""
        texts = []
        
        for msg in self._iter_message_nodes(messages):
            msg_type = msg.get('type')
            
            if msg_type == 'text':
                text = msg.get('data', {}).get('text', '').strip()
                if text:
                    texts.append(text)
            elif msg_type == 'image':
                desc = msg.get('describe', '').strip()
                if desc:
                    texts.append(desc)
        
        # 合并文本并切分
        merged = '\n'.join(texts).strip()
        if not merged:
            return []
        
        segments = []
        for i in range(0, len(merged), limit):
            segments.append(merged[i:i+limit])
        
        return segments
