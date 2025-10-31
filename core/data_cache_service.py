"""数据缓存服务（使用 aiocache 缓存频繁查询的数据）

缓存策略：
- Submission: 缓存单个投稿查询，TTL 5 分钟（投稿状态会变化）
- BlackList: 缓存黑名单查询，TTL 10 分钟
- User: 缓存用户信息，TTL 30 分钟
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any
from datetime import datetime

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache_client import get_cache
from utils.common import make_cache_key


class DataCacheService:
    """数据缓存服务（缓存频繁查询的数据库记录）"""
    
    # TTL 配置（秒）
    SUBMISSION_TTL = 300  # 5 分钟
    BLACKLIST_TTL = 600   # 10 分钟
    USER_TTL = 1800       # 30 分钟
    COMMENTS_TTL = 300    # 5 分钟（评论缓存）
    
    @staticmethod
    async def get_submission_by_id(
        submission_id: int,
        session: AsyncSession,
        use_cache: bool = True
    ) -> Optional[Any]:
        """获取投稿（带缓存）
        
        Args:
            submission_id: 投稿 ID
            session: 数据库会话
            use_cache: 是否使用缓存（默认 True）
        
        Returns:
            Submission 对象或 None
        """
        from core.models import Submission
        
        cache_key = make_cache_key("submission", submission_id)
        
        # 尝试从缓存获取
        if use_cache:
            try:
                cache = await get_cache()
                cached_data = await cache.get(cache_key)
                
                if cached_data:
                    logger.debug(f"从缓存获取投稿: {submission_id}")
                    # 将字典转换回 Submission 对象（简单处理）
                    # 注意：这里返回的是字典，调用者需要处理
                    return cached_data
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        
        # 从数据库查询
        try:
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if submission and use_cache:
                # 缓存投稿数据（转换为字典）
                try:
                    cache = await get_cache()
                    submission_dict = {
                        "id": submission.id,
                        "sender_id": submission.sender_id,
                        "sender_nickname": submission.sender_nickname,
                        "receiver_id": submission.receiver_id,
                        "group_name": submission.group_name,
                        "status": submission.status,
                        "is_anonymous": submission.is_anonymous,
                        "is_safe": submission.is_safe,
                        "is_complete": submission.is_complete,
                        "publish_id": submission.publish_id,
                        "raw_content": submission.raw_content,
                        "processed_content": submission.processed_content,
                        "llm_result": submission.llm_result,
                        "rendered_images": submission.rendered_images,
                        "comment": submission.comment,
                        "rejection_reason": submission.rejection_reason,
                        "processed_by": submission.processed_by,
                        "created_at": submission.created_at.isoformat() if submission.created_at else None,
                        "updated_at": submission.updated_at.isoformat() if submission.updated_at else None,
                        "processed_at": submission.processed_at.isoformat() if submission.processed_at else None,
                        "published_at": submission.published_at.isoformat() if submission.published_at else None,
                    }
                    await cache.set(cache_key, submission_dict, ttl=DataCacheService.SUBMISSION_TTL)
                    logger.debug(f"缓存投稿: {submission_id}")
                except Exception as e:
                    logger.warning(f"缓存写入失败: {e}")
            
            return submission
        except Exception as e:
            logger.error(f"查询投稿失败: {e}")
            return None
    
    @staticmethod
    async def invalidate_submission(submission_id: int):
        """使投稿缓存失效（当投稿状态更新时调用）"""
        try:
            cache = await get_cache()
            cache_key = make_cache_key("submission", submission_id)
            await cache.delete(cache_key)
            logger.debug(f"清除投稿缓存: {submission_id}")
        except Exception as e:
            logger.warning(f"清除投稿缓存失败: {e}")
    
    @staticmethod
    async def check_blacklist(
        user_id: str,
        group_name: str,
        session: AsyncSession,
        use_cache: bool = True
    ) -> bool:
        """检查用户是否在黑名单（带缓存）
        
        Args:
            user_id: 用户 ID
            group_name: 账号组名称
            session: 数据库会话
            use_cache: 是否使用缓存
        
        Returns:
            True 表示在黑名单中，False 表示不在
        """
        from core.models import BlackList
        
        cache_key = make_cache_key("blacklist", user_id, group_name)
        
        # 尝试从缓存获取
        if use_cache:
            try:
                cache = await get_cache()
                cached_result = await cache.get(cache_key)
                
                if cached_result is not None:
                    logger.debug(f"从缓存获取黑名单状态: {user_id} in {group_name} = {cached_result}")
                    return bool(cached_result)
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        
        # 从数据库查询
        try:
            stmt = select(BlackList).where(
                and_(
                    BlackList.user_id == user_id,
                    BlackList.group_name == group_name
                )
            )
            result = await session.execute(stmt)
            blacklist = result.scalar_one_or_none()
            
            # 检查是否在黑名单且处于激活状态
            is_blacklisted = blacklist is not None and blacklist.is_active()
            
            if use_cache:
                # 缓存结果
                try:
                    cache = await get_cache()
                    await cache.set(cache_key, is_blacklisted, ttl=DataCacheService.BLACKLIST_TTL)
                    logger.debug(f"缓存黑名单状态: {user_id} in {group_name} = {is_blacklisted}")
                except Exception as e:
                    logger.warning(f"缓存写入失败: {e}")
            
            return is_blacklisted
        except Exception as e:
            logger.error(f"查询黑名单失败: {e}")
            return False
    
    @staticmethod
    async def invalidate_blacklist(user_id: str, group_name: str):
        """使黑名单缓存失效（当黑名单状态更新时调用）"""
        try:
            cache = await get_cache()
            cache_key = make_cache_key("blacklist", user_id, group_name)
            await cache.delete(cache_key)
            logger.debug(f"清除黑名单缓存: {user_id} in {group_name}")
        except Exception as e:
            logger.warning(f"清除黑名单缓存失败: {e}")
    
    @staticmethod
    async def get_user_by_id(
        user_id: int,
        session: AsyncSession,
        use_cache: bool = True
    ) -> Optional[Any]:
        """获取用户信息（带缓存）
        
        Args:
            user_id: 用户 ID
            session: 数据库会话
            use_cache: 是否使用缓存
        
        Returns:
            User 对象或 None
        """
        from core.models import User
        
        cache_key = make_cache_key("user", user_id)
        
        # 尝试从缓存获取
        if use_cache:
            try:
                cache = await get_cache()
                cached_data = await cache.get(cache_key)
                
                if cached_data:
                    logger.debug(f"从缓存获取用户: {user_id}")
                    return cached_data
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        
        # 从数据库查询
        try:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user and use_cache:
                # 缓存用户数据
                try:
                    cache = await get_cache()
                    user_dict = {
                        "id": user.id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "role": user.role,
                        "is_active": user.is_active,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                    await cache.set(cache_key, user_dict, ttl=DataCacheService.USER_TTL)
                    logger.debug(f"缓存用户: {user_id}")
                except Exception as e:
                    logger.warning(f"缓存写入失败: {e}")
            
            return user
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None
    
    @staticmethod
    async def invalidate_user(user_id: int):
        """使用户缓存失效（当用户信息更新时调用）"""
        try:
            cache = await get_cache()
            cache_key = make_cache_key("user", user_id)
            await cache.delete(cache_key)
            logger.debug(f"清除用户缓存: {user_id}")
        except Exception as e:
            logger.warning(f"清除用户缓存失败: {e}")
    
    @staticmethod
    async def clear_pattern(pattern: str):
        """清除匹配模式的所有缓存键
        
        Args:
            pattern: 键模式，如 "submission:*"
        """
        try:
            cache = await get_cache()
            # aiocache 不直接支持 pattern 删除，需要使用底层 Redis
            if cache.backend == "redis":
                await cache.clear_pattern(pattern)
                logger.debug(f"清除缓存模式: {pattern}")
        except Exception as e:
            logger.warning(f"清除缓存模式失败: {e}")
    
    @staticmethod
    async def get_platform_comments(
        record_id: int,
        page: int,
        page_size: int,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """获取平台评论（带缓存）
        
        Args:
            record_id: 发布记录 ID
            page: 页码
            page_size: 每页数量
            use_cache: 是否使用缓存
        
        Returns:
            评论数据字典或 None
        """
        cache_key = make_cache_key("comments", record_id, page, page_size)
        
        # 尝试从缓存获取
        if use_cache:
            try:
                cache = await get_cache()
                cached_data = await cache.get(cache_key)
                
                if cached_data:
                    logger.debug(f"从缓存获取评论: record_id={record_id}, page={page}")
                    return cached_data
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        
        return None
    
    @staticmethod
    async def set_platform_comments(
        record_id: int,
        page: int,
        page_size: int,
        data: Dict[str, Any]
    ) -> bool:
        """设置平台评论缓存
        
        Args:
            record_id: 发布记录 ID
            page: 页码
            page_size: 每页数量
            data: 评论数据
        
        Returns:
            是否成功
        """
        cache_key = make_cache_key("comments", record_id, page, page_size)
        
        try:
            cache = await get_cache()
            await cache.set(cache_key, data, ttl=DataCacheService.COMMENTS_TTL)
            logger.debug(f"缓存评论: record_id={record_id}, page={page}")
            return True
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")
            return False
    
    @staticmethod
    async def invalidate_platform_comments(record_id: int):
        """使某个发布记录的所有评论缓存失效
        
        Args:
            record_id: 发布记录 ID
        """
        try:
            cache = await get_cache()
            # 清除该 record_id 的所有评论缓存
            if cache.backend == "redis":
                pattern = f"comments:{record_id}:*"
                # 使用 raw 命令扫描并删除
                keys = []
                cursor = 0
                while True:
                    cursor, batch = await cache.raw("scan", cursor, match=pattern, count=100)
                    keys.extend(batch)
                    if cursor == 0:
                        break
                
                if keys:
                    await cache.raw("delete", *keys)
                    logger.debug(f"清除评论缓存: record_id={record_id}, count={len(keys)}")
            else:
                # 非 Redis 后端，无法批量删除，记录警告
                logger.warning(f"当前缓存后端不支持 pattern 删除: {cache.backend}")
        except Exception as e:
            logger.warning(f"清除评论缓存失败: {e}")

