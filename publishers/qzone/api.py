"""QQ空间API接口"""
import hashlib
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import httpx
from loguru import logger


class QzoneAPI:
    """QQ空间API客户端"""
    
    # API地址
    UPLOAD_IMAGE_URL = "https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image"
    PUBLISH_EMOTION_URL = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
    CHECK_LOGIN_URL = "https://h5.qzone.qq.com/proxy/domain/g.qzone.qq.com/cgi-bin/friendshow/cgi_get_visitor_more"
    
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
        
    def _generate_gtk(self, skey: str) -> str:
        """生成gtk参数"""
        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        return str(hash_val & 2147483647)
        
    async def check_login(self) -> bool:
        """检查登录状态"""
        try:
            params = {
                'uin': self.uin,
                'mask': 7,
                'g_tk': self.gtk,
                'page': 1,
                'fupdate': 1
            }
            
            response = await self.client.get(
                self.CHECK_LOGIN_URL.format(self.uin, self.gtk),
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                return 'data' in data
                
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            
        return False
        
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
        
        Args:
            content: 说说内容
            images: 图片数据列表
            
        Returns:
            发布结果，包含tid等信息
        """
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
        
        # 处理图片
        if images:
            pic_bos = []
            richvals = []
            
            for img_data in images:
                try:
                    # 上传图片
                    upload_result = await self.upload_image(img_data)
                    
                    if upload_result.get('ret') != 0:
                        logger.error(f"图片上传失败: {upload_result}")
                        continue
                        
                    # 提取图片信息
                    data = upload_result.get('data', {})
                    url = data.get('url', '')
                    
                    if '&bo=' in url:
                        pic_bo = url.split('&bo=')[1]
                        pic_bos.append(pic_bo)
                        
                        # 构建richval
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
            result = response.json()
            
            if result.get('code') == 0:
                return {
                    'success': True,
                    'tid': result.get('tid'),
                    'message': '发布成功'
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', '发布失败'),
                    'code': result.get('code')
                }
        else:
            return {
                'success': False,
                'message': f'HTTP错误: {response.status_code}'
            }
            
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
