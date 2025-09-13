"""LLM处理器"""
import orjson
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import os
import time
import ssl
import dashscope
from dashscope import Generation, MultiModalConversation
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

try:
    from PIL import Image, ImageFile, UnidentifiedImageError, ImageOps

    ImageFile.LOAD_TRUNCATED_IMAGES = True
except Exception:
    Image = None
    UnidentifiedImageError = Exception
    ImageOps = None

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

        self.per_type_rules = {
            "image": {
                "remove_in_data": ["file_id", "file_size"],
                "remove_msg": ["summary"],
                "remove_event": [],
                "hide_from_LM_only": ["data"]
            },
            "video": {
                "remove_in_data": ["file_id", "file_size"],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": ["data.file", "data.file_id", "data.file_size"]
            },
            "audio": {
                "remove_in_data": ["file_id", "file_size"],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": ["data.file", "data.file_id", "data.file_size"]
            },
            "json": {
                "remove_in_data": [],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": []
            },
            "text": {
                "remove_in_data": [],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": []
            },
            "file": {
                "remove_in_data": ["file_id"],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": ["data.file_size"]
            },
            "poke": {
                "remove_in_data": [],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": ["data"]
            },
            "forward": {
                "remove_in_data": ["id"],
                "remove_msg": [],
                "remove_event": [],
                "hide_from_LM_only": []
            },
        }
        self.default_rules = {
            "remove_in_data": ["file", "file_id", "file_size"],
            "remove_msg": [],
            "remove_event": [],
            "hide_from_LM_only": []
        }
        self.global_event_rules = {
            "remove_event": ["file", "file_id", "file_size"],
            "hide_from_LM_only": []
        }

    async def initialize(self):
        """初始化处理器"""
        self.logger.info("LLM处理器初始化完成")

    async def shutdown(self):
        """关闭处理器"""
        pass

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据（对齐 sendtoLM.py 的流程：图片处理 -> 裁剪 -> 文本LLM分组 -> 生成最终消息集）"""
        messages_root = data.get('messages', [])
        if not isinstance(messages_root, List) or not messages_root:
            return data

        # 1) 处理图片（压缩/安全/描述）
        pictures_safe = True
        try:
            pictures_safe = await self._process_images_in_messages(messages_root)
        except Exception as e:
            self.logger.error(f"图片处理失败: {e}")

        # 2) 生成 LM 输入（按规则隐藏/裁剪）
        lm_messages, origin_messages = self._make_lm_sanitized_and_original({"messages": messages_root})
        lm_input = {"notregular": data.get("notregular"), "messages": lm_messages}
        input_content = orjson.dumps(lm_input, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS).decode("utf-8")
        timenow = time.time()

        prompt = f"""当前时间 {timenow}
以下内容是一组按时间顺序排列的校园墙投稿聊天记录：

{input_content}

请根据以下标准，提取出这些消息中属于**最后一组投稿**的信息：

### 分组标准
- 通常以关键词"在吗"、"投稿"、"墙"等开始，但这些关键词可能出现在中途或根本不出现。
- 属于同一组投稿的消息，时间间隔一般较近（通常小于 600 秒），但也存在例外。
- 投稿内容可能包含文本、图片（image）、视频（video）、文件（file）、戳一戳（poke）、合并转发的聊天记录（forward）等多种类型。
- 大多数情况下该记录只包含一组投稿，这种情况下认为所有消息都在组中，偶尔可能有多组，需要你自己判断。
- 信息只可能包含多个完整的投稿，户可能出现半个投稿+一个投稿的情况，如果真的出现了，说明你判断错误，前面那个"半个投稿"，是后面投稿的一部分。

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

### 输出格式

严格按照下面的 JSON 格式输出，仅填写最后一组投稿的 `message_id`，不要输出任何额外的文字或说明：

```json
{{
"needpriv": "true" 或 "false",
"safemsg": "true" 或 "false",
"isover": "true" 或 "false",
"notregular": "true" 或 "false",
"messages": [
    "message_id1",
    "message_id2",
    ...
]
}}
```
"""

        # 3) 调用文本 LLM（一次性 JSON 返回）
        final_obj = await self._call_llm_json(prompt)
        if not isinstance(final_obj, dict):
            # 失败时回退默认
            final_obj = {
                'needpriv': 'false',
                'safemsg': 'true' if pictures_safe else 'false',
                'isover': 'true',
                'notregular': 'false',
                'messages': []
            }

        origin_lookup: Dict[str, Dict[str, Any]] = {}
        for it in origin_messages:
            mid = it.get('message_id')
            if mid is not None:
                origin_lookup[str(mid)] = it

        final_list: List[Dict[str, Any]] = []
        for mid in final_obj.get('messages', []) or []:
            key = str(mid)
            if key in origin_lookup:
                final_list.append(self._finalize_item_for_output(origin_lookup[key]))

        if not final_list:
            # 如果没有选中，默认全部
            final_list = [self._finalize_item_for_output(it) for it in origin_messages]

        # 规范化布尔字段
        for k in ['needpriv', 'safemsg', 'isover', 'notregular']:
            v = final_obj.get(k)
            if isinstance(v, bool):
                final_obj[k] = 'true' if v else 'false'
            elif isinstance(v, str):
                final_obj[k] = 'true' if v.strip().lower() == 'true' else 'false'
            else:
                final_obj[k] = 'false' if k in ('needpriv', 'notregular') else 'true'

        if not pictures_safe:
            final_obj['safemsg'] = 'false'

        final_obj['messages'] = final_list

        # 覆盖 data.messages 以用于后续渲染
        data['messages'] = final_list
        # 生成文本段落供后续使用（如渲染/发布说明），上限每段200字
        try:
            segments = self._extract_text_segments_from_messages(final_list, limit=200)
            if segments:
                final_obj['segments'] = segments
        except Exception:
            pass
        data['llm_result'] = final_obj
        data['is_anonymous'] = final_obj.get('needpriv') == 'true'
        return data


    # ==================== 图片处理 ====================
    async def _process_images_in_messages(self, messages_root: List[Dict[str, Any]]) -> bool:
        """压缩本地图片、进行安全检查并为图片生成描述，返回全局安全性。"""
        if Image is None:
            return True
        overall_safe = True
        for msg in self._iter_all_message_nodes(messages_root):
            if not isinstance(msg, dict) or msg.get('type') != 'image':
                continue
            data = msg.get('data') or {}
            url = data.get('url') or data.get('file') or ''
            if not isinstance(url, str):
                continue
            if url.startswith('file://'):
                image_path = url[7:]
            else:
                # 非本地文件不处理压缩与安全
                continue
            try:
                with Image.open(image_path) as im:
                    im.thumbnail((2048, 2048))
                    im.save(image_path)
            except Exception as e:
                self.logger.warning(f"压缩失败: {image_path}, {e}")
            try:
                is_safe, description = self._process_image_safety_and_description(image_path)
                if not is_safe:
                    overall_safe = False
                if description:
                    msg['describe'] = description.strip()
            except Exception as e:
                self.logger.warning(f"安全/描述失败: {image_path}, {e}")
        return overall_safe


    # _compress_image 已移除：直接在 _process_images_in_messages 中使用 Pillow 进行缩放与保存

    def _process_image_safety_and_description(self, path: str) -> Tuple[bool, str]:
        if not path or not os.path.exists(path):
            return True, ""
        messages = [{
            'role': 'user',
            'content': [
                {'image': 'file://' + os.path.abspath(path)},
                {'text': (
                    '请分析这张图片并回答以下两个问题：\n\n'
                    '1. 安全性检查：这张图片是否含有暴力、血腥、色情、政治敏感，人生攻击或其他敏感内容(发到国内平台，被举报后会导致处罚的都算)？如果安全请回答"safe"，否则回答"unsafe"。\n\n'
                    '2. 图片描述：请详细描述这张图片的内容，包括图片中的主要元素、场景、颜色、风格等。描述要准确、详细，但不要过于冗长。\n\n'
                    '请按以下格式回答：\n安全性：[safe/unsafe]\n描述：[详细描述内容]'
                )}
            ]
        }]
        try:
            response = MultiModalConversation.call(
                model=self.vision_model,
                messages=messages,
                api_key=self.config.get('api_key'),
                timeout=self.timeout
            )
            if getattr(response, 'status_code', None) == 200:
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    content = " ".join(map(str, content))
                txt = str(content or "")
                is_safe = 'unsafe' not in txt.lower()
                description = ""
                idx = txt.find('描述：')
                if idx != -1:
                    description = txt[idx + 3:].strip()
                else:
                    # 退化提取第一行非 safe/unsafe 的文本
                    for line in txt.splitlines():
                        l = line.strip()
                        if not l:
                            continue
                        lower = l.lower()
                        if 'safe' in lower or 'unsafe' in lower or l.startswith('安全性'):
                            continue
                        description = l
                        break
                return is_safe, description
            if getattr(response, 'status_code', None) == 400:
                return False, ""
            return True, ""
        except Exception:
            return True, ""

    def _iter_all_message_nodes(self, messages_root: List[Dict[str, Any]]):
        for item in messages_root:
            if not isinstance(item, dict):
                continue
            if 'message' in item and isinstance(item['message'], list):
                for msg in item['message']:
                    if isinstance(msg, dict):
                        yield msg
            else:
                if 'type' in item:
                    yield item

    def _extract_text_segments_from_messages(self, items: List[Dict[str, Any]], limit: int = 200) -> List[str]:
        """从最终消息中提取可读文本段：
        - 聚合文本消息内容
        - 对图片带有 describe 的，作为一个段落
        - 每段不超过 limit 字
        """

        def _walk_and_collect_text(msgs: List[Dict[str, Any]]) -> List[str]:
            out: List[str] = []
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                mtype = m.get('type')
                if mtype == 'text':
                    txt = (m.get('data') or {}).get('text')
                    if isinstance(txt, str) and txt.strip():
                        out.append(txt.strip())
                elif mtype == 'image':
                    desc = m.get('describe')
                    if isinstance(desc, str) and desc.strip():
                        out.append(desc.strip())
                elif 'message' in m and isinstance(m['message'], list):
                    out.extend(_walk_and_collect_text(m['message']))
            return out

        collected: List[str] = []
        # items 为事件列表（每个事件可能包含 message 数组）
        for it in items:
            if not isinstance(it, dict):
                continue
            if 'message' in it and isinstance(it['message'], list):
                collected.extend(_walk_and_collect_text(it['message']))
            else:
                # 兼容直接消息
                collected.extend(_walk_and_collect_text([it]))

        # 合并并按长度切段
        merged = '\n'.join(collected)
        merged = merged.strip()
        if not merged:
            return []
        # 简单按 limit 切分
        segments: List[str] = []
        start = 0
        while start < len(merged):
            end = min(len(merged), start + max(1, int(limit)))
            segments.append(merged[start:end])
            start = end
        return segments

    # ==================== LM 输入裁剪/恢复 ====================
    def _pop_path(self, obj: Dict[str, Any], dotted: str):
        if not dotted:
            return
        parts = dotted.split('.')
        cur = obj
        for i, k in enumerate(parts):
            if not isinstance(cur, dict) or k not in cur:
                return
            if i == len(parts) - 1:
                cur.pop(k, None)
            else:
                cur = cur.get(k)

    def _remove_many(self, obj: Dict[str, Any], paths: List[str]):
        for p in paths:
            self._pop_path(obj, p)

    def _clean_forward_content(self, content_list: Any) -> Any:
        if not isinstance(content_list, list):
            return content_list
        cleaned_content: List[Any] = []
        for item in content_list:
            if not isinstance(item, dict):
                cleaned_content.append(item)
                continue
            cleaned_item: Dict[str, Any] = {}
            if "message" in item and isinstance(item["message"], list):
                cleaned_item["message"] = []
                for msg in item["message"]:
                    if isinstance(msg, dict):
                        cleaned_msg = msg.copy()
                        if msg.get("type") == "forward" and "data" in msg:
                            cleaned_msg["data"] = msg["data"].copy()
                            if "content" in msg["data"]:
                                cleaned_msg["data"]["content"] = self._clean_forward_content(msg["data"]["content"])
                            elif "messages" in msg["data"]:
                                cleaned_msg["data"]["messages"] = self._clean_forward_content(msg["data"]["messages"])
                        cleaned_item["message"].append(cleaned_msg)
                    else:
                        cleaned_item["message"].append(msg)
            if cleaned_item:
                cleaned_content.append(cleaned_item)
        return cleaned_content

    def _make_lm_sanitized_and_original(self, data_root: Dict[str, Any]) -> Tuple[
        List[Dict[str, Any]], List[Dict[str, Any]]]:
        origin_messages = orjson.loads(orjson.dumps(data_root.get("messages", []) ))
        lm_messages = orjson.loads(orjson.dumps(origin_messages))
        for item in lm_messages:
            self._remove_many(item, self.global_event_rules.get('remove_event', []))
            self._remove_many(item, self.global_event_rules.get('hide_from_LM_only', []))
            if "message" in item and isinstance(item["message"], list):
                for msg in item["message"]:
                    mtype = msg.get("type")
                    rules = self.per_type_rules.get(mtype, self.default_rules)
                    if mtype == "forward" and "data" in msg:
                        if "content" in msg["data"]:
                            msg["data"]["content"] = self._clean_forward_content(msg["data"]["content"])
                        elif "messages" in msg["data"]:
                            msg["data"]["messages"] = self._clean_forward_content(msg["data"]["messages"])
                    self._remove_many(msg, rules.get('remove_msg', []))
                    self._remove_many(msg, rules.get('hide_from_LM_only', []))
                    if isinstance(msg.get("data"), dict):
                        self._remove_many(msg, [f"data.{k}" for k in rules.get('remove_in_data', [])])
        return lm_messages, origin_messages

    def _finalize_item_for_output(self, item_origin: Dict[str, Any]) -> Dict[str, Any]:
        out_item = orjson.loads(orjson.dumps(item_origin))
        for key in self.global_event_rules.get('remove_event', []):
            if key not in self.global_event_rules.get('hide_from_LM_only', []):
                self._pop_path(out_item, key)
        if "message" in out_item and isinstance(out_item["message"], list):
            for msg in out_item["message"]:
                mtype = msg.get("type")
                rules = self.per_type_rules.get(mtype, self.default_rules)
                hide_set = set(rules.get('hide_from_LM_only', []))
                for p in rules.get('remove_msg', []):
                    if p not in hide_set:
                        self._pop_path(msg, p)
                if isinstance(msg.get('data'), dict):
                    for k in rules.get('remove_in_data', []):
                        dotted = f"data.{k}"
                        if dotted not in hide_set:
                            self._pop_path(msg, dotted)
        return out_item

    # ==================== 文本模型：一次性 JSON 调用 ====================
    async def _call_llm_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not prompt:
            return None
        messages = [
            {'role': 'system', 'content': '你是一个校园墙投稿管理员，只能返回规范 JSON 对象'},
            {'role': 'user', 'content': prompt}
        ]
        try:
            response = Generation.call(
                model=self.text_model,
                messages=messages,
                # 尝试强制 JSON 对象返回；如果 SDK 不支持，则由提示词保证
                response_format={'type': 'json_object'},  # 兼容新版 SDK
                result_format='message',
                stream=False,
                max_tokens=2048,
                temperature=0.3,
                repetition_penalty=1.0,
                timeout=self.timeout
            )
        except Exception as exc:
            self.logger.error(f"调用文本模型失败: {exc}")
            return None

        try:
            if getattr(response, 'status_code', None) != 200:
                return None
            # 优先使用 output_text
            raw_text = getattr(response, 'output_text', None)
            if not raw_text:
                # 兼容 message 结构
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    parts: List[str] = []
                    for c in content:
                        # 兼容 {"text": "..."} 或 直接字符串
                        if isinstance(c, dict) and 'text' in c:
                            parts.append(str(c['text']))
                        else:
                            parts.append(str(c))
                    raw_text = ''.join(parts)
                else:
                    raw_text = str(content)
            # 直接尝试解析 JSON
            raw_text = raw_text.strip()
            return orjson.loads(raw_text)
        except Exception:
            return None
