"""Persistent task queue abstraction for publisher scheduling (configurable).

Supported backends (configured via settings.queue.backend):
  - AsyncSQLiteQueue: backed by persist-queue SQLiteAckQueue with async wrappers
  - AsyncQueue: backed by persist-queue file Queue with async wrappers
  - MySQLQueue: backed by persist-queue MySQLQueue
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Tuple, Any


class TaskQueueBackend:
    async def ensure_queue(self, name: str):  # pragma: no cover - interface
        raise NotImplementedError

    async def enqueue(self, name: str, job: Dict[str, Any]):  # pragma: no cover
        raise NotImplementedError

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[Any, Dict[str, Any]]]:  # pragma: no cover
        raise NotImplementedError

    async def ack(self, name: str, token: Any):  # pragma: no cover
        raise NotImplementedError

    async def recover_inflight(self, name: str):  # pragma: no cover
        raise NotImplementedError


try:
    from persistqueue import SQLiteAckQueue, Queue as FileQueue  # type: ignore
except Exception:  # pragma: no cover
    SQLiteAckQueue = None  # type: ignore
    FileQueue = None  # type: ignore


try:
    # MySQLQueue may be provided under persistqueue.sqlqueue
    from persistqueue.sqlqueue import MySQLQueue  # type: ignore
except Exception:  # pragma: no cover
    MySQLQueue = None  # type: ignore


try:
    from pathlib import Path
    from persistqueue import SQLiteAckQueue  # type: ignore
except Exception:  # pragma: no cover
    SQLiteAckQueue = None  # type: ignore


class AsyncSQLiteQueueBackend(TaskQueueBackend):
    """Async wrapper over persist-queue SQLiteAckQueue (ack-capable)."""
    def __init__(self, base_dir: str = "data/queues"):
        from pathlib import Path
        if SQLiteAckQueue is None:
            raise RuntimeError("persist-queue not available; cannot use AsyncSQLiteQueue")
        self._queues: Dict[str, Any] = {}
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _get_queue_sync(self, name: str) -> Any:
        q = self._queues.get(name)
        if q is None:
            path = str(self._base_dir / name)
            self._queues[name] = SQLiteAckQueue(path)
            q = self._queues[name]
        return q

    async def ensure_queue(self, name: str):
        await asyncio.to_thread(self._get_queue_sync, name)

    async def enqueue(self, name: str, job: Dict[str, Any]):
        def _put():
            q = self._get_queue_sync(name)
            q.put(job)
        await asyncio.to_thread(_put)

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[Any, Dict[str, Any]]]:
        def _get():
            q = self._get_queue_sync(name)
            try:
                item = q.get(block=True, timeout=timeout)
            except Exception:
                return None
            return item
        item = await asyncio.to_thread(_get)
        if item is None:
            return None
        return item, (item if isinstance(item, dict) else {})

    async def ack(self, name: str, token: Any):
        def _ack():
            q = self._get_queue_sync(name)
            try:
                q.ack(token)
            except Exception:
                pass
        await asyncio.to_thread(_ack)

    async def recover_inflight(self, name: str):
        # Unacked items will be redelivered automatically
        return None


class AsyncFileQueueBackend(TaskQueueBackend):
    """Async wrapper over persist-queue file Queue (no ack)."""
    def __init__(self, base_dir: str = "data/queues"):
        from pathlib import Path
        if FileQueue is None:
            raise RuntimeError("persist-queue not available; cannot use AsyncQueue")
        self._queues: Dict[str, Any] = {}
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _get_queue_sync(self, name: str) -> Any:
        q = self._queues.get(name)
        if q is None:
            path = str(self._base_dir / name)
            self._queues[name] = FileQueue(path)
            q = self._queues[name]
        return q

    async def ensure_queue(self, name: str):
        await asyncio.to_thread(self._get_queue_sync, name)

    async def enqueue(self, name: str, job: Dict[str, Any]):
        def _put():
            q = self._get_queue_sync(name)
            q.put(job)
        await asyncio.to_thread(_put)

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[Any, Dict[str, Any]]]:
        def _get():
            q = self._get_queue_sync(name)
            try:
                item = q.get(block=True, timeout=timeout)
            except Exception:
                return None
            return item
        item = await asyncio.to_thread(_get)
        if item is None:
            return None
        return item, (item if isinstance(item, dict) else {})

    async def ack(self, name: str, token: Any):
        # FileQueue 没有 ack 语义，视为立即完成
        return None

    async def recover_inflight(self, name: str):
        return None


class MySQLQueueBackend(TaskQueueBackend):
    """Wrapper over persist-queue MySQLQueue (ack availability depends on version)."""
    def __init__(self, host: str, port: int, user: str, password: str, database: str, table: str = 'oqq_tasks'):
        if MySQLQueue is None:
            raise RuntimeError("persist-queue MySQLQueue not available")
        self._queues: Dict[str, Any] = {}
        self._conn_kwargs = dict(host=host, port=port, user=user, passwd=password, db=database, table=table)

    def _get_queue_sync(self, name: str) -> Any:
        q = self._queues.get(name)
        if q is None:
            # Some versions don't support table per queue; emulate by table suffix
            kwargs = dict(self._conn_kwargs)
            kwargs['table'] = f"{kwargs.get('table','oqq_tasks')}_{name}"
            self._queues[name] = MySQLQueue(**kwargs)
            q = self._queues[name]
        return q

    async def ensure_queue(self, name: str):
        await asyncio.to_thread(self._get_queue_sync, name)

    async def enqueue(self, name: str, job: Dict[str, Any]):
        def _put():
            q = self._get_queue_sync(name)
            q.put(job)
        await asyncio.to_thread(_put)

    async def pop(self, name: str, timeout: int = 5) -> Optional[Tuple[Any, Dict[str, Any]]]:
        def _get():
            q = self._get_queue_sync(name)
            try:
                item = q.get(block=True, timeout=timeout)
            except Exception:
                return None
            return item
        item = await asyncio.to_thread(_get)
        if item is None:
            return None
        return item, (item if isinstance(item, dict) else {})

    async def ack(self, name: str, token: Any):
        def _ack():
            q = self._get_queue_sync(name)
            # MySQLQueue may or may not support ack; ignore if not
            try:
                q.ack(token)
            except Exception:
                pass
        await asyncio.to_thread(_ack)

    async def recover_inflight(self, name: str):
        return None


def build_queue_backend() -> TaskQueueBackend:
    """Build backend per settings.queue.backend.

    Options: 'AsyncSQLiteQueue' | 'AsyncQueue' | 'MySQLQueue'
    """
    from config import get_settings
    settings = get_settings()
    qcfg = getattr(settings, 'queue', None)
    backend = (getattr(qcfg, 'backend', None) or 'AsyncSQLiteQueue').strip()
    if backend == 'AsyncSQLiteQueue':
        base_dir = getattr(qcfg, 'path', 'data/queues')
        return AsyncSQLiteQueueBackend(base_dir)
    if backend == 'AsyncQueue':
        base_dir = getattr(qcfg, 'path', 'data/queues')
        return AsyncFileQueueBackend(base_dir)
    if backend == 'MySQLQueue':
        mysql = getattr(qcfg, 'mysql', {}) or {}
        host = mysql.get('host', 'localhost')
        port = int(mysql.get('port', 3306))
        user = mysql.get('user', 'root')
        password = mysql.get('password', '')
        database = mysql.get('database', 'oqqqueue')
        table = mysql.get('table', 'oqq_tasks')
        return MySQLQueueBackend(host, port, user, password, database, table)
    raise RuntimeError(f"Unsupported queue backend: {backend}")

