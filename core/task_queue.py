"""Persistent task queue abstraction for publisher scheduling.

Supports Redis-backed persistent queues when enabled via settings.redis.enabled,
and falls back to in-memory asyncio queues otherwise.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Tuple, Any

import orjson

try:
    from redis.asyncio import Redis, from_url  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore
    from_url = None  # type: ignore


class TaskQueueBackend:
    async def ensure_queue(self, name: str):  # pragma: no cover - interface
        raise NotImplementedError

    async def enqueue(self, name: str, job: Dict[str, Any]):  # pragma: no cover
        raise NotImplementedError

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[bytes, Dict[str, Any]]]:  # pragma: no cover
        raise NotImplementedError

    async def ack(self, name: str, raw: bytes):  # pragma: no cover
        raise NotImplementedError

    async def recover_inflight(self, name: str):  # pragma: no cover
        raise NotImplementedError


class RedisQueueBackend(TaskQueueBackend):
    def __init__(self, url: str):
        if from_url is None:
            raise RuntimeError("redis-py not available; cannot use RedisQueueBackend")
        self._redis: Redis = from_url(url, encoding=None, decode_responses=False)

    def _keys(self, name: str) -> Tuple[str, str]:
        base = f"oqqwall:queue:{name}"
        return base + ":pending", base + ":processing"

    async def ensure_queue(self, name: str):
        # No-op for Redis
        return None

    async def enqueue(self, name: str, job: Dict[str, Any]):
        pending, _ = self._keys(name)
        payload = orjson.dumps(job)
        await self._redis.rpush(pending, payload)

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        pending, processing = self._keys(name)
        # Atomically move from pending to processing
        data = await self._redis.brpoplpush(pending, processing, timeout=timeout)
        if data is None:
            return None
        try:
            job = orjson.loads(data)
        except Exception:
            job = {}
        return data, job

    async def ack(self, name: str, raw: bytes):
        _, processing = self._keys(name)
        # Remove one occurrence from processing list
        await self._redis.lrem(processing, 1, raw)

    async def recover_inflight(self, name: str):
        pending, processing = self._keys(name)
        # Move all items from processing back to pending
        while True:
            data = await self._redis.rpoplpush(processing, pending)
            if data is None:
                break


class MemoryQueueBackend(TaskQueueBackend):
    def __init__(self):
        self._pending: Dict[str, asyncio.Queue] = {}
        self._processing: Dict[str, list] = {}

    async def ensure_queue(self, name: str):
        if name not in self._pending:
            self._pending[name] = asyncio.Queue(maxsize=100)
        if name not in self._processing:
            self._processing[name] = []

    async def enqueue(self, name: str, job: Dict[str, Any]):
        await self.ensure_queue(name)
        raw = orjson.dumps(job)
        await self._pending[name].put(raw)

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        await self.ensure_queue(name)
        try:
            raw = await asyncio.wait_for(self._pending[name].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        self._processing[name].append(raw)
        try:
            job = orjson.loads(raw)
        except Exception:
            job = {}
        return raw, job

    async def ack(self, name: str, raw: bytes):
        await self.ensure_queue(name)
        try:
            self._processing[name].remove(raw)
        except ValueError:
            pass

    async def recover_inflight(self, name: str):
        # Move all processing back to pending
        await self.ensure_queue(name)
        items = list(self._processing[name])
        self._processing[name].clear()
        for raw in items:
            await self._pending[name].put(raw)


def build_queue_backend() -> TaskQueueBackend:
    """Create a queue backend based on settings.redis.enabled.
    Falls back to in-memory if Redis unavailable or disabled.
    """
    try:
        from config import get_settings
        settings = get_settings()
        redis_cfg = settings.redis
        if getattr(redis_cfg, 'enabled', False):
            host = getattr(redis_cfg, 'host', 'localhost')
            port = int(getattr(redis_cfg, 'port', 6379))
            db = int(getattr(redis_cfg, 'db', 0))
            url = f"redis://{host}:{port}/{db}"
            return RedisQueueBackend(url)
    except Exception:
        pass
    return MemoryQueueBackend()

