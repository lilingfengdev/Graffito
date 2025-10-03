"""统一缓存客户端（基于 aiocache）

参考: http://aiocache.readthedocs.io/

支持三种后端:
- memory: SimpleMemoryCache (本地内存)
- redis: RedisCache (Redis 服务器)  
- memcached: MemcachedCache (Memcached 服务器)

支持多种序列化器:
- null: NullSerializer (无序列化)
- string: StringSerializer (字符串)
- json: JsonSerializer (JSON)
- pickle: PickleSerializer (Python Pickle)
- msgpack: MsgPackSerializer (MessagePack)
"""

from __future__ import annotations

import asyncio
from typing import Optional, Any, List, Dict
from contextlib import asynccontextmanager

from loguru import logger

try:
    from aiocache import Cache
    from aiocache.serializers import (
        NullSerializer, 
        StringSerializer,
        JsonSerializer, 
        PickleSerializer, 
        MsgPackSerializer
    )
    from aiocache.lock import RedLock
    AIOCACHE_AVAILABLE = True
except ImportError:
    AIOCACHE_AVAILABLE = False
    Cache = None  # type: ignore


class CacheClient:
    """统一缓存客户端（使用 aiocache）
    
    自动根据配置选择后端和序列化器
    """
    
    _instance: Optional[CacheClient] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._cache: Optional[Any] = None  # aiocache.Cache instance
        self._backend_type: str = "memory"
        self._namespace: str = ""
        self._serializer_type: str = "json"
        self._config: Optional[Dict[str, Any]] = None
    
    @classmethod
    async def get_instance(cls) -> CacheClient:
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.initialize()
        return cls._instance
    
    async def initialize(self):
        """初始化缓存客户端"""
        if not AIOCACHE_AVAILABLE:
            logger.warning("aiocache 包未安装，缓存功能不可用")
            return
        
        from config import get_settings
        settings = get_settings()
        cfg = settings.cache
        
        self._backend_type = cfg.backend.lower()
        self._namespace = cfg.namespace
        self._serializer_type = cfg.serializer.lower()
        
        # 选择序列化器
        serializer = self._get_serializer(cfg.serializer)
        
        # 根据后端类型创建缓存实例
        try:
            if self._backend_type == "redis":
                self._cache = await self._create_redis_cache(cfg, serializer)
                logger.success(f"aiocache Redis 后端已启用: {cfg.redis_endpoint}:{cfg.redis_port}")
                
            elif self._backend_type == "memcached":
                self._cache = await self._create_memcached_cache(cfg, serializer)
                logger.success(f"aiocache Memcached 后端已启用: {cfg.memcached_endpoint}:{cfg.memcached_port}")
                
            else:  # memory
                self._cache = Cache(
                    Cache.MEMORY,
                    namespace=cfg.namespace,
                    serializer=serializer,
                    timeout=cfg.timeout
                )
                logger.info("aiocache Memory 后端已启用（本地内存）")
                
        except Exception as e:
            logger.error(f"缓存初始化失败: {e}, 降级到内存缓存")
            self._backend_type = "memory"
            self._serializer_type = cfg.serializer.lower()
            serializer = self._get_serializer(cfg.serializer)
            self._cache = Cache(
                Cache.MEMORY,
                namespace=cfg.namespace,
                serializer=serializer
            )
    
    async def _create_redis_cache(self, cfg, serializer):
        """创建 Redis 缓存"""
        import redis.asyncio as aioredis
        
        # 创建 redis 客户端
        redis_client = aioredis.from_url(
            f"redis://{cfg.redis_endpoint}:{cfg.redis_port}/{cfg.redis_db}",
            password=cfg.redis_password or None,
            max_connections=cfg.redis_pool_size,
            decode_responses=False,  # aiocache 要求
            encoding="utf-8"
        )
        
        # 测试连接
        await redis_client.ping()
        
        # 创建 aiocache RedisCache
        return Cache(
            Cache.REDIS,
            endpoint=cfg.redis_endpoint,
            port=cfg.redis_port,
            namespace=cfg.namespace,
            serializer=serializer,
            timeout=cfg.timeout,
            client=redis_client
        )
    
    async def _create_memcached_cache(self, cfg, serializer):
        """创建 Memcached 缓存"""
        return Cache(
            Cache.MEMCACHED,
            endpoint=cfg.memcached_endpoint,
            port=cfg.memcached_port,
            namespace=cfg.namespace,
            serializer=serializer,
            timeout=cfg.timeout,
            pool_size=cfg.memcached_pool_size
        )
    
    def _get_serializer(self, serializer_type: str):
        """根据配置选择序列化器"""
        serializer_type = serializer_type.lower()
        
        if serializer_type == "null":
            return NullSerializer()
        elif serializer_type == "string":
            return StringSerializer()
        elif serializer_type == "pickle":
            return PickleSerializer()
        elif serializer_type == "msgpack":
            try:
                return MsgPackSerializer()
            except Exception:
                logger.warning("msgpack 不可用，降级到 JSON")
                return JsonSerializer()
        else:  # json (默认)
            return JsonSerializer()
    
    @property
    def backend(self) -> str:
        """当前后端类型"""
        return self._backend_type
    
    @property
    def serializer(self) -> str:
        """当前序列化器类型"""
        return self._serializer_type
    
    @property
    def cache(self):
        """获取 aiocache 实例"""
        return self._cache
    
    # ==================== aiocache 标准 API ====================
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        if not self._cache:
            return default
        try:
            value = await self._cache.get(key)
            return value if value is not None else default
        except Exception as e:
            logger.warning(f"缓存获取失败 [{key}]: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not self._cache:
            return False
        try:
            return await self._cache.set(key, value, ttl=ttl)
        except Exception as e:
            logger.warning(f"缓存设置失败 [{key}]: {e}")
            return False
    
    async def add(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """添加缓存（仅当键不存在时）"""
        if not self._cache:
            return False
        try:
            return await self._cache.add(key, value, ttl=ttl)
        except ValueError:
            return False  # 键已存在
        except Exception as e:
            logger.warning(f"缓存添加失败 [{key}]: {e}")
            return False
    
    async def delete(self, key: str) -> int:
        """删除缓存键"""
        if not self._cache:
            return 0
        try:
            return await self._cache.delete(key)
        except Exception as e:
            logger.warning(f"缓存删除失败 [{key}]: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self._cache:
            return False
        try:
            return await self._cache.exists(key)
        except Exception as e:
            logger.warning(f"缓存检查失败 [{key}]: {e}")
            return False
    
    async def multi_get(self, keys: List[str]) -> List[Any]:
        """批量获取"""
        if not self._cache:
            return [None] * len(keys)
        try:
            return await self._cache.multi_get(keys)
        except Exception as e:
            logger.warning(f"批量获取失败: {e}")
            return [None] * len(keys)
    
    async def multi_set(self, pairs: List[tuple], ttl: Optional[int] = None) -> bool:
        """批量设置"""
        if not self._cache:
            return False
        try:
            return await self._cache.multi_set(pairs, ttl=ttl)
        except Exception as e:
            logger.warning(f"批量设置失败: {e}")
            return False
    
    async def increment(self, key: str, delta: int = 1) -> int:
        """递增计数器"""
        if not self._cache:
            return 0
        try:
            return await self._cache.increment(key, delta=delta)
        except Exception as e:
            logger.warning(f"递增失败 [{key}]: {e}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        if not self._cache:
            return False
        try:
            return await self._cache.expire(key, ttl)
        except Exception as e:
            logger.warning(f"设置过期失败 [{key}]: {e}")
            return False
    
    async def clear(self, namespace: Optional[str] = None) -> bool:
        """清空缓存"""
        if not self._cache:
            return False
        try:
            return await self._cache.clear(namespace=namespace)
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")
            return False
    
    async def raw(self, command: str, *args, **kwargs) -> Any:
        """执行原始命令"""
        if not self._cache:
            return None
        try:
            return await self._cache.raw(command, *args, **kwargs)
        except Exception as e:
            logger.warning(f"原始命令执行失败 [{command}]: {e}")
            return None
    
    # ==================== Redis 特定操作 ====================
    
    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Redis 有序集合添加（仅 Redis 后端）"""
        if self._backend_type != "redis" or not self._cache:
            logger.warning("zadd 仅在 Redis 后端可用")
            return 0
        try:
            # 使用 raw 命令访问底层 Redis
            full_key = f"{self._namespace}:{key}" if self._namespace else key
            return await self._cache.raw("zadd", full_key, mapping)
        except Exception as e:
            logger.warning(f"zadd 失败 [{key}]: {e}")
            return 0
    
    async def zrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """Redis 有序集合范围查询（仅 Redis 后端）"""
        if self._backend_type != "redis" or not self._cache:
            logger.warning("zrange 仅在 Redis 后端可用")
            return []
        try:
            full_key = f"{self._namespace}:{key}" if self._namespace else key
            result = await self._cache.raw("zrange", full_key, start, end)
            # 处理返回的 bytes
            if isinstance(result, list):
                return [item.decode('utf-8') if isinstance(item, bytes) else item for item in result]
            return []
        except Exception as e:
            logger.warning(f"zrange 失败 [{key}]: {e}")
            return []
    
    async def zcard(self, key: str) -> int:
        """Redis 有序集合元素数量（仅 Redis 后端）"""
        if self._backend_type != "redis" or not self._cache:
            logger.warning("zcard 仅在 Redis 后端可用")
            return 0
        try:
            full_key = f"{self._namespace}:{key}" if self._namespace else key
            return await self._cache.raw("zcard", full_key) or 0
        except Exception as e:
            logger.warning(f"zcard 失败 [{key}]: {e}")
            return 0
    
    # ==================== 分布式锁 ====================
    
    @asynccontextmanager
    async def lock(self, key: str, lease: int = 30):
        """分布式锁（使用 aiocache RedLock）
        
        仅 Redis 后端支持真正的分布式锁
        其他后端降级为本地锁
        """
        if self._backend_type == "redis" and self._cache:
            lock = RedLock(self._cache, key, lease=lease)
            async with lock:
                yield
        else:
            # 降级到本地 asyncio 锁
            local_lock = asyncio.Lock()
            async with local_lock:
                yield
    
    # ==================== 清理 ====================
    
    async def close(self):
        """关闭缓存连接"""
        if self._cache:
            try:
                await self._cache.close()
                logger.info("缓存连接已关闭")
            except Exception as e:
                logger.warning(f"关闭缓存失败: {e}")


async def get_cache() -> CacheClient:
    """获取缓存客户端实例"""
    return await CacheClient.get_instance()


async def close_cache():
    """关闭缓存客户端连接"""
    if CacheClient._instance:
        await CacheClient._instance.close()
        CacheClient._instance = None
        logger.info("缓存客户端已关闭")
