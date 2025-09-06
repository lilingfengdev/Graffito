"""LLM处理器"""
import json
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
import httpx
import dashscope
from dashscope import Generation, MultiModalConversation

from config import get_settings
from core.plugin import ProcessorPlugin


class LLMProcessor(ProcessorPlugin):
    """LLM处理器，用于处理投稿内容"""
    
    def __init__(self):
        settings = get_settings()
        config = settings.llm.dict() if hasattr(settings.llm, 'dict') else settings.llm.__dict__
        super().__init__("llm_processor", config)
        
        # 设置API密钥
        dashscope.api_key = self.config.get('api_key')
        self.text_model = self.config.get('text_model', 'qwen-plus-latest')
        self.vision_model = self.config.get('vision_model', 'qwen-vl-max-latest')
        self.timeout = self.config.get('timeout', 30)
        self.max_retry = self.config.get('max_retry', 3)
        
    async def initialize(self):
        """初始化处理器"""
        self.logger.info("LLM处理器初始化完成")
        
    async def shutdown(self):
        """关闭处理器"""
        pass
        
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据"""
        # 这是入口方法，根据数据类型选择不同的处理方式
        messages = data.get('messages', [])
        
        if not messages:
            return data
            
        # 检查是否有图片
        has_images = any(
            msg.get('type') == 'image' or 
            (msg.get('message') and any(m.get('type') == 'image' for m in msg.get('message', [])))
            for msg in messages
        )
        
        if has_images:
            # 使用视觉模型
            result = await self.process_with_vision(messages)
        else:
            # 使用文本模型
            result = await self.process_text_only(messages)
            
        data['llm_result'] = result
        return data
        
    async def process_text_only(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理纯文本投稿"""
        # 提取文本内容
        text_content = self.extract_text(messages)
        
        if not text_content:
            return {
                'needpriv': 'false',
                'safemsg': 'true',
                'isover': 'true',
                'notregular': 'false',
                'messages': messages
            }
            
        # 构建提示词
        prompt = self.build_text_prompt(text_content)
        
        # 调用LLM
        for attempt in range(self.max_retry):
            try:
                response = await self.call_text_llm(prompt)
                result = self.parse_llm_response(response)
                result['messages'] = messages
                return result
            except Exception as e:
                self.logger.error(f"LLM调用失败 (尝试 {attempt+1}/{self.max_retry}): {e}")
                if attempt == self.max_retry - 1:
                    # 返回默认结果
                    return {
                        'needpriv': 'false',
                        'safemsg': 'true',
                        'isover': 'true',
                        'notregular': 'false',
                        'messages': messages
                    }
                await asyncio.sleep(1)
                
    async def process_with_vision(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理包含图片的投稿"""
        # 提取文本和图片
        text_content = self.extract_text(messages)
        images = self.extract_images(messages)
        
        # 构建多模态提示
        prompt = self.build_vision_prompt(text_content, images)
        
        # 调用视觉LLM
        for attempt in range(self.max_retry):
            try:
                response = await self.call_vision_llm(prompt, images)
                result = self.parse_llm_response(response)
                result['messages'] = messages
                return result
            except Exception as e:
                self.logger.error(f"视觉LLM调用失败 (尝试 {attempt+1}/{self.max_retry}): {e}")
                if attempt == self.max_retry - 1:
                    return {
                        'needpriv': 'false',
                        'safemsg': 'true',
                        'isover': 'true',
                        'notregular': 'false',
                        'messages': messages
                    }
                await asyncio.sleep(1)
                
    def extract_text(self, messages: List[Dict[str, Any]]) -> str:
        """提取消息中的文本"""
        texts = []
        
        for msg in messages:
            if msg.get('type') == 'text':
                texts.append(msg.get('data', {}).get('text', ''))
            elif msg.get('message'):
                for m in msg.get('message', []):
                    if m.get('type') == 'text':
                        texts.append(m.get('data', {}).get('text', ''))
                        
        return '\n'.join(texts)
        
    def extract_images(self, messages: List[Dict[str, Any]]) -> List[str]:
        """提取消息中的图片URL"""
        images = []
        
        for msg in messages:
            if msg.get('type') == 'image':
                url = msg.get('data', {}).get('url')
                if url:
                    images.append(url)
            elif msg.get('message'):
                for m in msg.get('message', []):
                    if m.get('type') == 'image':
                        url = m.get('data', {}).get('url')
                        if url:
                            images.append(url)
                            
        return images
        
    def build_text_prompt(self, text: str) -> str:
        """构建文本处理提示词"""
        return f"""你是一个校园墙投稿处理助手。请分析以下投稿内容，并返回JSON格式的结果。

投稿内容：
{text}

请分析并返回以下信息（JSON格式）：
1. needpriv: 是否需要匿名（"true"或"false"）。如果内容包含"匿名"、"匿"、"不要暴露"等词汇，或涉及隐私敏感话题，返回"true"
2. safemsg: 内容是否安全（"true"或"false"）。如果包含不当言论、人身攻击、违法信息等，返回"false"
3. isover: 投稿是否完整（"true"或"false"）。如果看起来话没说完或明显未结束，返回"false"
4. segments: 内容分段（数组）。将长内容合理分段，每段不超过200字

示例返回格式：
{{
    "needpriv": "false",
    "safemsg": "true", 
    "isover": "true",
    "segments": ["第一段内容", "第二段内容"]
}}

请直接返回JSON，不要有其他说明。"""

    def build_vision_prompt(self, text: str, images: List[str]) -> str:
        """构建视觉处理提示词"""
        image_count = len(images)
        return f"""你是一个校园墙投稿处理助手。请分析以下包含{image_count}张图片的投稿内容。

文字内容：
{text if text else "（无文字描述）"}

请分析文字和图片内容，返回JSON格式的结果：
1. needpriv: 是否需要匿名（"true"或"false"）
2. safemsg: 内容和图片是否安全（"true"或"false"）
3. isover: 投稿是否完整（"true"或"false"）
4. image_desc: 图片内容描述（简要说明图片展示了什么）
5. segments: 内容分段（如有文字）

请确保图片内容符合校园墙发布规范，不包含不当内容。
直接返回JSON格式结果。"""

    async def call_text_llm(self, prompt: str) -> str:
        """调用文本LLM"""
        try:
            response = Generation.call(
                model=self.text_model,
                prompt=prompt,
                temperature=0.7,
                top_p=0.8,
                max_tokens=1000
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                raise Exception(f"LLM调用失败: {response.message}")
                
        except Exception as e:
            self.logger.error(f"文本LLM调用异常: {e}")
            raise
            
    async def call_vision_llm(self, prompt: str, images: List[str]) -> str:
        """调用视觉LLM"""
        try:
            # 构建消息内容
            content = [{"text": prompt}]
            
            # 添加图片
            for img_url in images[:9]:  # 最多9张图片
                if img_url.startswith('http'):
                    content.append({"image": img_url})
                elif img_url.startswith('file://'):
                    # 本地文件需要特殊处理
                    file_path = img_url.replace('file://', '')
                    content.append({"image": f"file://{file_path}"})
                    
            messages = [{
                'role': 'user',
                'content': content
            }]
            
            response = MultiModalConversation.call(
                model=self.vision_model,
                messages=messages,
                temperature=0.7,
                top_p=0.8,
                max_tokens=1000
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                # content 可能是 list[{'text': '...'}, {'image': '...'}]
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        try:
                            if isinstance(item, dict) and 'text' in item:
                                texts.append(str(item.get('text') or ''))
                        except Exception:
                            continue
                    if texts:
                        return "\n".join(texts)
                    # 若没有 text 段，回退为 JSON 文本
                    import json as _json
                    try:
                        return _json.dumps(content, ensure_ascii=False)
                    except Exception:
                        return str(content)
                # 若已是字符串
                if isinstance(content, str):
                    return content
                # 其他类型回退
                return str(content)
            else:
                raise Exception(f"视觉LLM调用失败: {response.message}")
                
        except Exception as e:
            self.logger.error(f"视觉LLM调用异常: {e}")
            raise
            
    def parse_llm_response(self, response: Any) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 统一将响应转换为字符串
            if not isinstance(response, str):
                try:
                    import json as _json
                    response = _json.dumps(response, ensure_ascii=False)
                except Exception:
                    response = str(response)
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
                
            # 确保必要字段存在
            result.setdefault('needpriv', 'false')
            result.setdefault('safemsg', 'true')
            result.setdefault('isover', 'true')
            result.setdefault('notregular', 'false')
            
            # 将布尔值转换为字符串
            for key in ['needpriv', 'safemsg', 'isover', 'notregular']:
                if isinstance(result.get(key), bool):
                    result[key] = 'true' if result[key] else 'false'
                    
            return result
            
        except Exception as e:
            self.logger.error(f"解析LLM响应失败: {e}, 原始响应: {response}")
            return {
                'needpriv': 'false',
                'safemsg': 'true',
                'isover': 'true',
                'notregular': 'false'
            }
