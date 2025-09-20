"""LLM处理器"""
import orjson
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import os
import time
import ssl
import hashlib
from pathlib import Path
import base64
import mimetypes
from openai import OpenAI
import urllib3
from urllib.parse import urlparse, parse_qs

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

        # OpenAI 客户端与模型
        self.api_key = self.config.get('api_key')
        self.base_url = self.config.get('base_url') or 'https://api.openai.com/v1'
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.text_model = self.config.get('text_model', 'gpt-4o-mini')
        self.vision_model = self.config.get('vision_model', self.text_model)
        self.timeout = self.config.get('timeout', 30)
        self.max_retry = self.config.get('max_retry', 3)

        # 审核跳过阈值（单位：MB，<=0 表示不跳过）
        try:
            self.skip_image_audit_over_mb: float = float(getattr(settings.audit, 'skip_image_audit_over_mb', 0.0))
        except Exception:
            self.skip_image_audit_over_mb = 0.0

        # 图片缓存目录（用于将远程图片保存为本地 file://）
        cache_root = getattr(settings.system, 'cache_dir', './data/cache') or './data/cache'
        self.chat_image_cache_dir = os.path.join(cache_root, 'chat_images')
        try:
            Path(self.chat_image_cache_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

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

**严格按照下面的 JSON 格式输出**，仅填写最后一组投稿的 `message_id`，不要输出任何额外的文字或说明：

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
            original_size_bytes: int = 0
            if url.startswith('file://'):
                # 兼容 file:///D:/... 与 file://D:/... 两种写法，统一解析为本地路径
                image_path = self._file_uri_to_path(url)
                try:
                    original_size_bytes = os.path.getsize(image_path)
                except Exception:
                    original_size_bytes = 0
            elif url.startswith('http://') or url.startswith('https://'):
                # 远程图片：下载到本地缓存，并将 url 改写为 file://
                try:
                    # 保留原始链接供后续渲染时作为说明链接
                    if 'origin_url' not in data:
                        data['origin_url'] = url
                    image_path, original_size_bytes = await self._download_remote_image(url)
                    if not image_path:
                        # 下载失败，跳过该图片的后续处理
                        continue
                    abs_path = os.path.abspath(image_path)
                    # 后续渲染/发布统一使用本地绝对路径（不带 file://）
                    data['url'] = abs_path
                except Exception as e:
                    self.logger.warning(f"远程图片下载失败: {url}, {e}")
                    continue
            else:
                # 非本地/非HTTP链接跳过
                continue
            try:
                with Image.open(image_path) as im:
                    im.thumbnail((2048, 2048))
                    im.save(image_path)
            except Exception as e:
                self.logger.warning(f"压缩失败: {image_path}, {e}")
            # 根据原始大小判断是否跳过 AI 检测
            skip_audit = False
            if self.skip_image_audit_over_mb and self.skip_image_audit_over_mb > 0:
                threshold_bytes = int(self.skip_image_audit_over_mb * 1024 * 1024)
                if original_size_bytes and original_size_bytes > threshold_bytes:
                    skip_audit = True
                    self.logger.info(
                        f"跳过图片安全检测（原始大小 {original_size_bytes} bytes > {threshold_bytes} bytes）: {image_path}"
                    )
            if not skip_audit:
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
        abs_path = os.path.abspath(path)
        import mimetypes, base64
        mime, _ = mimetypes.guess_type(abs_path)
        if not mime:
            mime = 'image/jpeg'
        try:
            with open(abs_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
            data_url = f"data:{mime};base64,{b64}"
        except Exception:
            return True, ""

        prompt = (
            '请分析这张图片并回答以下两个问题：\n\n'
            '1. 安全性检查：这张图片是否含有暴力、血腥、色情、政治敏感，人生攻击或其他敏感内容(发到国内平台，被举报后会导致处罚的都算)？如果安全请回答"safe"，否则回答"unsafe"。\n\n'
            '2. 图片描述：请详细描述这张图片的内容，包括图片中的主要元素、场景、颜色、风格等。描述要准确、详细，但不要过于冗长。\n\n'
            '请按以下格式回答：\n安全性：[safe/unsafe]\n描述：[详细描述内容]'
        )

        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[{"role": "user", "content": content}],
                temperature=0.0,
                max_tokens=1000,
            )
            txt = str(response.choices[0].message.content or "")
            lower = txt.lower()
            is_safe = 'unsafe' not in lower
            description = ""
            idx = txt.find('描述：')
            if idx != -1:
                description = txt[idx + 3:].strip()
            else:
                for line in txt.splitlines():
                    l = line.strip()
                    if not l:
                        continue
                    lw = l.lower()
                    if 'safe' in lw or 'unsafe' in lw or l.startswith('安全性'):
                        continue
                    description = l
                    break
            return is_safe, description
        except Exception:
            return True, ""

    # ===== 路径与 file:// 互转 =====
    def _to_file_uri(self, path: str) -> str:
        """将本地绝对路径转换为标准 file URI（跨平台）。"""
        try:
            if not path:
                return ''
            p = Path(path)
            if not p.is_absolute():
                p = Path(os.path.abspath(str(p)))
            return p.as_uri()
        except Exception:
            # 回退：尽量构造
            path = os.path.abspath(path)
            if os.name == 'nt':
                # Windows: file:///D:/...
                drive = ''
                if len(path) >= 2 and path[1] == ':' and path[0].isalpha():
                    drive = path[:2]
                rest = path[2:] if drive else path
                rest = rest.replace('\\', '/')
                if drive:
                    return f'file:///{drive[0].upper()}{rest}'
                return f'file:///{rest}'
            return f'file://{path}'

    def _file_uri_to_path(self, uri: str) -> str:
        """将 file:// URI 转换为本地路径，兼容 Windows 与 Unix。"""
        try:
            if not uri:
                return ''
            s = str(uri)
            if not s.startswith('file://'):
                return s
            # 去掉前缀，考虑 file:///D:/... 与 file://D:/...
            body = s[7:]
            # 去除多余的斜杠
            while body.startswith('/') and len(body) > 3 and body[2] == ':':
                # 形如 /D:/path -> D:/path
                body = body[1:]
            return body.replace('/', '\\') if os.name == 'nt' else body
        except Exception:
            return uri
        except Exception:
            return True, ""

    async def _download_remote_image(self, url: str) -> Tuple[str, int]:
        """下载远程图片到缓存目录并返回 (本地路径, 原始大小字节)。失败返回 ("", 0)。"""
        # 生成稳定文件名：优先使用 QQ fileid；否则使用 URL 哈希
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        basename = None
        if 'fileid' in query and query['fileid']:
            basename = query['fileid'][0]
        if not basename:
            basename = hashlib.sha1(url.encode('utf-8')).hexdigest()

        # 预判扩展名
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
            ext = '.jpg'
        filename = f"{basename}{ext}"
        local_path = os.path.join(self.chat_image_cache_dir, filename)

        # 如已存在则复用
        try:
            if os.path.exists(local_path):
                size = os.path.getsize(local_path)
                return local_path, size
        except Exception:
            pass

        try:
            import httpx
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://multimedia.nt.qq.com.cn/' if 'multimedia.nt.qq.com.cn' in parsed.netloc else parsed.scheme + '://' + parsed.netloc,
            }
            timeout = self.timeout if isinstance(self.timeout, (int, float)) else 30
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                # 根据 Content-Type 纠正扩展名
                ctype = resp.headers.get('Content-Type', '')
                if 'image/' in ctype:
                    if 'jpeg' in ctype and not filename.lower().endswith('.jpg') and not filename.lower().endswith(
                            '.jpeg'):
                        filename = f"{basename}.jpg"
                    elif 'png' in ctype and not filename.lower().endswith('.png'):
                        filename = f"{basename}.png"
                    elif 'gif' in ctype and not filename.lower().endswith('.gif'):
                        filename = f"{basename}.gif"
                    elif 'webp' in ctype and not filename.lower().endswith('.webp'):
                        filename = f"{basename}.webp"
                    local_path = os.path.join(self.chat_image_cache_dir, filename)

                Path(self.chat_image_cache_dir).mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                size = os.path.getsize(local_path)
                return local_path, size
        except Exception as e:
            self.logger.warning(f"下载远程图片失败: {url}, {e}")
            return "", 0

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
        origin_messages = orjson.loads(orjson.dumps(data_root.get("messages", [])))
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
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.text_model,
                messages=messages,
                response_format={'type': 'json_object'},
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as exc:
            self.logger.error(f"调用文本模型失败: {exc}")
            return None

        try:
            raw_text = (response.choices[0].message.content or '').strip()
            return orjson.loads(raw_text)
        except Exception:
            return None
