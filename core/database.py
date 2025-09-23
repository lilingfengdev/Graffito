"""数据库管理模块"""
import asyncio
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from loguru import logger

from config import get_settings
from .models import Base


class Database:
    """数据库管理器"""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.async_session: Optional[async_sessionmaker] = None
        self.settings = get_settings()
        
    async def initialize(self):
        """初始化数据库"""
        # 确保数据目录存在
        db_url = self.settings.database.url
        if db_url.startswith('sqlite'):
            db_path = db_url.split('///')[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 创建引擎
        self.engine = create_async_engine(
            db_url,
            echo=self.settings.system.debug,
            pool_size=self.settings.database.pool_size,
            pool_pre_ping=True,  # 连接池预检
        )
        
        # 为SQLite设置优化
        if 'sqlite' in db_url:
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                cursor.execute("PRAGMA synchronous=NORMAL")  # 性能优化
                cursor.execute("PRAGMA cache_size=10000")  # 缓存大小
                cursor.execute("PRAGMA temp_store=MEMORY")  # 临时存储在内存
                cursor.close()
        
        # 创建会话工厂
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 创建所有表
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 轻量迁移：为 invite_tokens 增加 max_uses 与 uses_count（若不存在）
            try:
                await conn.execute(text("ALTER TABLE invite_tokens ADD COLUMN max_uses INTEGER"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE invite_tokens ADD COLUMN uses_count INTEGER DEFAULT 0"))
            except Exception:
                pass
            
        logger.info(f"数据库初始化完成: {db_url}")
        
    async def close(self):
        """关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("数据库连接已关闭")
            
    @asynccontextmanager
    async def get_session(self):
        """获取数据库会话"""
        if not self.async_session:
            raise RuntimeError("数据库未初始化")
            
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
                
    async def execute_raw(self, sql: str, params: dict = None):
        """执行原始SQL"""
        async with self.get_session() as session:
            result = await session.execute(text(sql), params or {})
            return result
            
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False


# 全局数据库实例
_database: Optional[Database] = None


async def get_db() -> Database:
    """获取数据库实例（单例）"""
    global _database
    
    if _database is None:
        _database = Database()
        await _database.initialize()
        
    return _database


async def close_db():
    """关闭数据库"""
    global _database
    
    if _database:
        await _database.close()
        _database = None

# ---------------------------------------------------------------------------
# Common high-level query helpers to avoid code duplication across services
# ---------------------------------------------------------------------------

from typing import List, Optional as _Opt


async def fetch_submission_by_id(submission_id: int) -> _Opt["Submission"]:
    """Convenience helper to fetch a single Submission by id.

    It abstracts away boilerplate session handling. Returns ``None`` if not
    found.
    """
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select  # local import to avoid top-level heavy dep
        from core.models import Submission  # import inside to avoid circulars

        stmt = select(Submission).where(Submission.id == submission_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def fetch_submissions_by_ids(submission_ids: List[int]) -> List["Submission"]:
    """Fetch multiple ``Submission`` rows preserving DB ordering."""
    if not submission_ids:
        return []
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Submission

        stmt = select(Submission).where(Submission.id.in_(submission_ids))
        result = await session.execute(stmt)
        return result.scalars().all()
