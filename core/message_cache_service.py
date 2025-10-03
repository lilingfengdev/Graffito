"""消息缓存服务（使用 aiocache 统一缓存接口）

根据 Redis 配置自动选择存储后端：
- Redis 启用时：使用 Redis 存储（aiocache RedisCache），性能更好
- Redis 未启用：使用内存缓存（aiocache SimpleMemoryCache）或降级到数据库
"""

from __future__ import annotations

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import MessageCache as DBMessageCache
from core.cache_client import get_cache


class MessageCacheService:
    """消息缓存服务（统一接口，支持 Redis/数据库双后端）"""
    
    @staticmethod
    async def add_message(
        sender_id: str,
        receiver_id: str,
        message_id: str,
        message_content: Dict[str, Any],
        message_time: float,
        db: AsyncSession
    ) -> bool:
        """添加消息到缓存（使用 aiocache）
        
        Args:
            sender_id: 发送者 ID
            receiver_id: 接收者 ID
            message_id: 消息 ID
            message_content: 消息内容
            message_time: 消息时间戳
            db: 数据库会话
        
        Returns:
            是否添加成功
        """
        cache = await get_cache()
        
        # aiocache 会根据配置自动选择 Redis 或 Memory
        if cache.backend == "redis":
            return await MessageCacheService._add_to_cache(
                cache, sender_id, receiver_id, message_id, 
                message_content, message_time
            )
        else:
            # Memory 缓存或缓存不可用时降级到数据库
            return await MessageCacheService._add_to_db(
                db, sender_id, receiver_id, message_id,
                message_content, message_time
            )
    
    @staticmethod
    async def _add_to_cache(
        cache,
        sender_id: str,
        receiver_id: str,
        message_id: str,
        message_content: Dict[str, Any],
        message_time: float
    ) -> bool:
        """添加到缓存（使用 aiocache + Redis 有序集合）"""
        try:
            from config import get_settings
            settings = get_settings()
            ttl = settings.cache.message_cache_ttl
            
            cache_key = f"msg_cache:{sender_id}:{receiver_id}"
            
            msg_data = {
                "message_id": message_id,
                "message_content": message_content,
                "message_time": message_time,
                "created_at": datetime.now().isoformat()
            }
            
            # 使用 aiocache 底层的 Redis zadd 支持
            await cache.zadd(
                cache_key,
                {json.dumps(msg_data, ensure_ascii=False): message_time}
            )
            await cache.expire(cache_key, ttl)
            
            logger.debug(f"消息已添加到缓存: {sender_id} -> {receiver_id}")
            return True
            
        except Exception as e:
            logger.warning(f"添加消息到缓存失败: {e}")
            return False
    
    @staticmethod
    async def _add_to_db(
        db: AsyncSession,
        sender_id: str,
        receiver_id: str,
        message_id: str,
        message_content: Dict[str, Any],
        message_time: float
    ) -> bool:
        """添加到数据库"""
        try:
            cache = DBMessageCache(
                sender_id=sender_id,
                receiver_id=receiver_id,
                message_id=message_id,
                message_content=message_content,
                message_time=message_time,
                created_at=datetime.now()
            )
            db.add(cache)
            await db.commit()
            logger.debug(f"消息已添加到数据库缓存: {sender_id} -> {receiver_id}")
            return True
        except Exception as e:
            logger.error(f"添加消息到数据库失败: {e}")
            await db.rollback()
            return False
    
    @staticmethod
    async def get_messages(
        sender_id: str,
        receiver_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取用户的所有缓存消息（按时间排序，使用 aiocache）
        
        Returns:
            消息列表，每个消息包含: message_id, message_content, message_time, created_at
        """
        cache = await get_cache()
        
        if cache.backend == "redis":
            messages = await MessageCacheService._get_from_cache(
                cache, sender_id, receiver_id
            )
            if messages is not None:
                return messages
            logger.debug("缓存获取失败，降级到数据库")
        
        return await MessageCacheService._get_from_db(db, sender_id, receiver_id)
    
    @staticmethod
    async def _get_from_cache(
        cache,
        sender_id: str,
        receiver_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """从缓存获取消息（使用 aiocache）"""
        try:
            cache_key = f"msg_cache:{sender_id}:{receiver_id}"
            
            raw_messages = await cache.zrange(cache_key, 0, -1)
            
            messages = []
            for raw_msg in raw_messages:
                try:
                    messages.append(json.loads(raw_msg))
                except json.JSONDecodeError as e:
                    logger.warning(f"解析消息失败: {e}")
            
            logger.debug(f"从缓存获取到 {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            logger.warning(f"从缓存获取消息失败: {e}")
            return None
    
    @staticmethod
    async def _get_from_db(
        db: AsyncSession,
        sender_id: str,
        receiver_id: str
    ) -> List[Dict[str, Any]]:
        """从数据库获取消息"""
        try:
            stmt = select(DBMessageCache).where(
                DBMessageCache.sender_id == sender_id,
                DBMessageCache.receiver_id == receiver_id
            ).order_by(DBMessageCache.message_time)
            
            result = await db.execute(stmt)
            caches = result.scalars().all()
            
            messages = []
            for cache in caches:
                messages.append({
                    "message_id": cache.message_id,
                    "message_content": cache.message_content,
                    "message_time": cache.message_time,
                    "created_at": cache.created_at.isoformat() if cache.created_at else None
                })
            
            logger.debug(f"从数据库获取到 {len(messages)} 条缓存消息")
            return messages
            
        except Exception as e:
            logger.error(f"从数据库获取消息失败: {e}")
            return []
    
    @staticmethod
    async def clear_messages(
        sender_id: str,
        receiver_id: str,
        db: AsyncSession
    ) -> bool:
        """清空用户的缓存消息（使用 aiocache）
        
        Returns:
            是否清空成功
        """
        cache = await get_cache()
        
        # 同时清理缓存和数据库（确保一致性）
        cache_success = True
        db_success = True
        
        if cache.backend == "redis":
            cache_success = await MessageCacheService._clear_from_cache(
                cache, sender_id, receiver_id
            )
        
        db_success = await MessageCacheService._clear_from_db(
            db, sender_id, receiver_id
        )
        
        return cache_success and db_success
    
    @staticmethod
    async def _clear_from_cache(
        cache,
        sender_id: str,
        receiver_id: str
    ) -> bool:
        """从缓存清空消息（使用 aiocache）"""
        try:
            cache_key = f"msg_cache:{sender_id}:{receiver_id}"
            await cache.delete(cache_key)
            logger.debug(f"已清空缓存: {sender_id} -> {receiver_id}")
            return True
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")
            return False
    
    @staticmethod
    async def _clear_from_db(
        db: AsyncSession,
        sender_id: str,
        receiver_id: str
    ) -> bool:
        """从数据库清空消息"""
        try:
            stmt = delete(DBMessageCache).where(
                DBMessageCache.sender_id == sender_id,
                DBMessageCache.receiver_id == receiver_id
            )
            await db.execute(stmt)
            await db.commit()
            logger.debug(f"已清空数据库缓存: {sender_id} -> {receiver_id}")
            return True
        except Exception as e:
            logger.error(f"清空数据库缓存失败: {e}")
            await db.rollback()
            return False
    
    @staticmethod
    async def clear_all_by_receiver(
        receiver_id: str,
        db: AsyncSession
    ) -> bool:
        """清空指定接收者的所有缓存消息（使用 aiocache）
        
        Args:
            receiver_id: 接收者 ID
            db: 数据库会话
        
        Returns:
            是否清空成功
        """
        cache = await get_cache()
        
        # 数据库清理
        try:
            stmt = delete(DBMessageCache).where(
                DBMessageCache.receiver_id == receiver_id
            )
            await db.execute(stmt)
            await db.commit()
            logger.debug(f"已清空接收者 {receiver_id} 的所有数据库缓存")
        except Exception as e:
            logger.error(f"清空数据库缓存失败: {e}")
            await db.rollback()
            return False
        
        # Redis 缓存清理（使用 aiocache clear 方法或手动删除）
        if cache.backend == "redis":
            try:
                # 使用 aiocache raw 方法执行 Redis scan
                namespace = cache._namespace or ""
                pattern = f"{namespace}:msg_cache:*:{receiver_id}" if namespace else f"msg_cache:*:{receiver_id}"
                
                cursor = 0
                deleted_count = 0
                while True:
                    result = await cache.raw("scan", cursor, match=pattern, count=100)
                    if result:
                        cursor, keys = result[0], result[1] if len(result) > 1 else []
                        if keys:
                            await cache.raw("delete", *keys)
                            deleted_count += len(keys)
                    if cursor == 0:
                        break
                logger.debug(f"已清空接收者 {receiver_id} 的 {deleted_count} 个缓存键")
            except Exception as e:
                logger.warning(f"清空缓存失败: {e}")
        
        return True
    
    @staticmethod
    async def get_cache_count(
        sender_id: str,
        receiver_id: str,
        db: AsyncSession
    ) -> int:
        """获取缓存消息数量（使用 aiocache）
        
        Returns:
            缓存的消息数量
        """
        cache = await get_cache()
        
        if cache.backend == "redis":
            try:
                cache_key = f"msg_cache:{sender_id}:{receiver_id}"
                count = await cache.zcard(cache_key)
                return count
            except Exception as e:
                logger.warning(f"从缓存获取消息数量失败: {e}")
        
        # 降级到数据库
        try:
            from sqlalchemy import func
            stmt = select(func.count()).select_from(DBMessageCache).where(
                DBMessageCache.sender_id == sender_id,
                DBMessageCache.receiver_id == receiver_id
            )
            result = await db.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"从数据库获取消息数量失败: {e}")
            return 0

