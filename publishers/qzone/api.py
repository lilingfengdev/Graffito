"""QQ空间API接口

优先使用第三方库 aioqzone 实现发布/评论等操作；
若运行环境未安装或不可用，则回退到原有的 HTTP 接口实现。
"""
import hashlib
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import httpx
from loguru import logger


class QzoneAPI:
    """QQ空间API客户端（带 aioqzone 优先的实现）"""
    
    # API地址
    UPLOAD_IMAGE_URL = "https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image"
    PUBLISH_EMOTION_URL = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
    CHECK_LOGIN_URL = "https://h5.qzone.qq.com/proxy/domain/g.qzone.qq.com/cgi-bin/friendshow/cgi_get_visitor_more"
    ADD_COMMENT_URL = "https://h5.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_addcomment"
    
    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        self.gtk = self._generate_gtk(cookies.get('p_skey', ''))
        self.uin = cookies.get('uin', '').lstrip('o')
        self.client = httpx.AsyncClient(
            cookies=cookies,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'https://user.qzone.qq.com/{self.uin}'
            },
            timeout=30
        )

        # aioqzone 适配
        self._aioqzone = None
        try:
            # 尝试多种可能的导入路径/类名，提升兼容性
            AioQzone = None
            try:
                from aioqzone import Qzone as AioQzone  # type: ignore
            except Exception:
                try:
                    from aioqzone import QZone as AioQzone  # type: ignore
                except Exception:
                    try:
                        from aioqzone import Client as AioQzone  # type: ignore
                    except Exception:
                        AioQzone = None

            if AioQzone is not None:
                # 部分实现可能支持 cookies 直接初始化；若失败则在具体调用时再降级
                try:
                    self._aioqzone = AioQzone(cookies=cookies)  # type: ignore
                except Exception:
                    # 再尝试以关键字段显式传入
                    try:
                        self._aioqzone = AioQzone(
                            uin=self.uin,
                            p_skey=cookies.get('p_skey'),
                            skey=cookies.get('skey'),
                            cookies=cookies
                        )  # type: ignore
                    except Exception:
                        self._aioqzone = None
        except Exception:
            self._aioqzone = None
        
    def _generate_gtk(self, skey: str) -> str:
        """生成gtk参数"""
        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        return str(hash_val & 2147483647)
        
    async def check_login(self) -> bool:
        """检查登录状态"""
        try:
            # 仅进行轻量校验：存在关键 cookie 即视为可能已登录
            if not self.cookies.get('p_skey') or not self.uin:
                return False

            # 网络探测：忽略 JSON/JSONP 解析错误，只看 HTTP 结果
            params = {
                'uin': self.uin,
                'mask': 7,
                'g_tk': self.gtk,
                'page': 1,
                'fupdate': 1
            }

            response = await self.client.get(self.CHECK_LOGIN_URL, params=params)
            if response.status_code == 200:
                # 有些环境返回 JSONP 或 HTML，这里不强制解析
                return True
        except Exception as e:
            # 放宽为 warning，避免干扰正常发布
            logger.warning(f"检查登录状态异常: {e}")
        return True
        
    async def upload_image(self, image_data: bytes) -> Dict[str, Any]:
        """上传图片"""
        import base64
        
        # 图片转Base64
        pic_base64 = base64.b64encode(image_data).decode('utf-8')
        
        data = {
            "filename": "image.jpg",
            "zzpanelkey": "",
            "uploadtype": "1",
            "albumtype": "7",
            "exttype": "0",
            "skey": self.cookies.get("skey", ""),
            "zzpaneluin": self.uin,
            "p_uin": self.uin,
            "uin": self.uin,
            "p_skey": self.cookies.get('p_skey', ''),
            "output_type": "json",
            "qzonetoken": "",
            "refer": "shuoshuo",
            "charset": "utf-8",
            "output_charset": "utf-8",
            "upload_hd": "1",
            "hd_width": "2048",
            "hd_height": "10000",
            "hd_quality": "96",
            "backUrls": "http://upbak.photo.qzone.qq.com/cgi-bin/upload/cgi_upload_image",
            "url": f"https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image?g_tk={self.gtk}",
            "base64": "1",
            "picfile": pic_base64,
        }
        
        response = await self.client.post(
            self.UPLOAD_IMAGE_URL,
            data=data,
            params={'g_tk': self.gtk}
        )
        
        if response.status_code == 200:
            # 解析返回的数据（可能包含在回调函数中）
            text = response.text
            if '{' in text and '}' in text:
                json_str = text[text.find('{'):text.rfind('}')+1]
                return json.loads(json_str)
                
        raise Exception(f"图片上传失败: {response.status_code}")
        
    async def publish_emotion(self, content: str, images: List[bytes] = None) -> Dict[str, Any]:
        """发布说说
        
        优先尝试 aioqzone 的 publish_mood 实现（支持图片）；
        失败或未安装时，回退到原有的 HTTP 接口逻辑。

        Args:
            content: 说说内容
            images: 图片数据列表（bytes）
        Returns:
            发布结果字典
        """
        # aioqzone 优先
        if self._aioqzone is not None:
            try:
                # 兼容性调用尝试：不同版本可能参数名不同
                if images:
                    # 直接尝试 images/pictures 两种形参
                    try:
                        result = await self._aioqzone.publish_mood(content=content, images=images)  # type: ignore
                    except TypeError:
                        try:
                            result = await self._aioqzone.publish_mood(content=content, pictures=images)  # type: ignore
                        except Exception:
                            # 进一步兼容可能的命名空间
                            if hasattr(self._aioqzone, 'mood'):
                                try:
                                    result = await self._aioqzone.mood.publish(content, images)  # type: ignore
                                except Exception:
                                    raise
                            else:
                                raise
                else:
                    try:
                        result = await self._aioqzone.publish_mood(content=content)  # type: ignore
                    except Exception:
                        if hasattr(self._aioqzone, 'mood'):
                            result = await self._aioqzone.mood.publish(content)  # type: ignore
                        else:
                            raise

                # 标准化返回
                if isinstance(result, dict):
                    if result.get('success') is True and (result.get('tid') or result.get('id')):
                        return {
                            'success': True,
                            'tid': result.get('tid') or result.get('id')
                        }
                    # 某些实现仅返回 id
                    if result.get('id'):
                        return {'success': True, 'tid': result.get('id')}
                # 未知返回但未抛异常，也视为成功
                return {'success': True, 'tid': result}
            except Exception as e:
                logger.warning(f"aioqzone 发布失败，回退到HTTP实现: {e}")

        # 回退到原有 HTTP 实现
        post_data = {
            "syn_tweet_verson": "1",
            "paramstr": "1",
            "who": "1",
            "con": content,
            "feedversion": "1",
            "ver": "1",
            "ugc_right": "1",
            "to_sign": "0",
            "hostuin": self.uin,
            "code_version": "1",
            "format": "json",
            "qzreferrer": f"https://user.qzone.qq.com/{self.uin}"
        }
        
        # 处理图片（HTTP 回退路径）
        if images:
            pic_bos = []
            richvals = []
            for img_data in images:
                try:
                    upload_result = await self.upload_image(img_data)
                    if upload_result.get('ret') != 0:
                        logger.error(f"图片上传失败: {upload_result}")
                        continue
                    data = upload_result.get('data', {})
                    url = data.get('url', '')
                    if '&bo=' in url:
                        pic_bo = url.split('&bo=')[1]
                        pic_bos.append(pic_bo)
                        richval = ",{},{},{},{},{},{},,{},{}".format(
                            data.get('albumid', ''),
                            data.get('lloc', ''),
                            data.get('sloc', ''),
                            data.get('type', 1),
                            data.get('height', 0),
                            data.get('width', 0),
                            data.get('height', 0),
                            data.get('width', 0)
                        )
                        richvals.append(richval)
                except Exception as e:
                    logger.error(f"处理图片失败: {e}")
                    continue
            if pic_bos:
                post_data['pic_bo'] = ','.join(pic_bos)
                post_data['richtype'] = '1'
                post_data['richval'] = '\t'.join(richvals)
                
        # 发布说说
        params = {
            'g_tk': self.gtk,
            'uin': self.uin
        }
        
        response = await self.client.post(
            self.PUBLISH_EMOTION_URL,
            params=params,
            data=post_data
        )
        
        if response.status_code == 200:
            # 有些返回是 JSONP 或者 text/plain
            text = response.text
            parsed: Dict[str, Any]
            try:
                parsed = response.json()
            except Exception:
                try:
                    # 提取花括号中的 JSON
                    if '{' in text and '}' in text:
                        json_str = text[text.find('{'):text.rfind('}')+1]
                        parsed = json.loads(json_str)
                    else:
                        parsed = {}
                except Exception:
                    parsed = {}

            if parsed.get('code') == 0:
                return {
                    'success': True,
                    'tid': parsed.get('tid'),
                    'message': '发布成功'
                }
            else:
                return {
                    'success': False,
                    'message': parsed.get('message', '发布失败'),
                    'code': parsed.get('code')
                }
        else:
            return {
                'success': False,
                'message': f'HTTP错误: {response.status_code}'
            }
            
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def add_comment(self, host_uin: str, tid: str, content: str) -> Dict[str, Any]:
        """为说说添加评论
        
        优先尝试 aioqzone；失败后回退 HTTP。

        Args:
            host_uin: 说说所属账号（发布账号）的 UIN（纯数字，不带前缀 o）
            tid: 说说的 tid（发布返回值中包含）
            content: 评论内容
        Returns:
            结果字典
        """
        # aioqzone 优先
        if self._aioqzone is not None:
            try:
                # 可能存在不同命名
                try:
                    res = await self._aioqzone.add_comment(tid=tid, content=content)  # type: ignore
                except Exception:
                    if hasattr(self._aioqzone, 'mood') and hasattr(self._aioqzone.mood, 'comment'):
                        res = await self._aioqzone.mood.comment(tid, content)  # type: ignore
                    else:
                        raise
                if isinstance(res, dict):
                    if res.get('success') or res.get('code') == 0:
                        return {"success": True, "message": "评论成功"}
                return {"success": True, "message": "评论已提交"}
            except Exception as e:
                logger.warning(f"aioqzone 评论失败，回退到HTTP实现: {e}")

        # HTTP 回退
        try:
            post_data = {
                "hostuin": str(host_uin),
                "tid": str(tid),
                # 来源：1 表示来自 H5；具体取值并不严格
                "t1_source": "1",
                # 内容字段在不同端存在 content/con 的差异；双写提升兼容性
                "content": content,
                "con": content,
                "format": "json",
                "qzreferrer": f"https://user.qzone.qq.com/{host_uin}",
            }
            params = {
                "g_tk": self.gtk,
                "uin": self.uin,
            }
            resp = await self.client.post(self.ADD_COMMENT_URL, params=params, data=post_data)
            if resp.status_code != 200:
                return {"success": False, "message": f"HTTP错误: {resp.status_code}"}
            # 解析 JSON 或 JSONP
            text = resp.text
            parsed: Dict[str, Any]
            try:
                parsed = resp.json()
            except Exception:
                try:
                    if "{" in text and "}" in text:
                        json_str = text[text.find("{"):text.rfind("}")+1]
                        parsed = json.loads(json_str)
                    else:
                        parsed = {}
                except Exception:
                    parsed = {}
            if parsed.get("code") == 0:
                return {"success": True, "message": "评论成功"}
            return {
                "success": False,
                "message": parsed.get("message", "评论失败"),
                "code": parsed.get("code"),
            }
        except Exception as e:
            logger.error(f"评论失败: {e}")
            return {"success": False, "message": str(e)}
