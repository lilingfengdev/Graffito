"""异步操作辅助工具"""
import asyncio
from typing import Set, Optional, Callable, Any, Coroutine, List, Dict
from contextlib import asynccontextmanager
from loguru import logger


class TaskManager:
    """后台任务管理器，确保任务正确追踪和清理"""
    
    def __init__(self, name: str = "default"):
        self.name = name
        self._tasks: Set[asyncio.Task] = set()
        self.logger = logger.bind(module=f"task_manager.{name}")
        
    def create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: Optional[str] = None,
        error_handler: Optional[Callable[[Exception], None]] = None
    ) -> asyncio.Task:
        """创建并追踪一个后台任务
        
        Args:
            coro: 要执行的协程
            name: 任务名称（用于日志）
            error_handler: 自定义错误处理器
            
        Returns:
            创建的任务
        """
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        
        # 任务完成时自动移除
        task.add_done_callback(self._tasks.discard)
        
        # 添加错误处理
        def handle_result(t: asyncio.Task):
            try:
                t.result()
            except asyncio.CancelledError:
                self.logger.debug(f"任务被取消: {name or t.get_name()}")
            except Exception as e:
                if error_handler:
                    try:
                        error_handler(e)
                    except Exception:
                        self.logger.exception(f"错误处理器失败: {name or t.get_name()}")
                else:
                    self.logger.error(f"任务失败 {name or t.get_name()}: {e}", exc_info=True)
        
        task.add_done_callback(handle_result)
        return task
    
    async def cancel_all(self, timeout: float = 5.0) -> None:
        """取消所有任务
        
        Args:
            timeout: 等待任务取消的超时时间
        """
        if not self._tasks:
            return
            
        self.logger.info(f"取消 {len(self._tasks)} 个任务...")
        
        # 复制任务集合，避免迭代时修改
        tasks = list(self._tasks)
        
        # 取消所有任务
        for task in tasks:
            task.cancel()
        
        # 等待任务完成
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"{len([t for t in tasks if not t.done()])} 个任务未能在 {timeout}s 内取消")
    
    def __len__(self) -> int:
        """返回活动任务数量"""
        return len(self._tasks)
    
    @property
    def tasks(self) -> List[asyncio.Task]:
        """返回活动任务列表（只读）"""
        return list(self._tasks)


# 全局任务管理器实例
_task_managers: Dict[str, TaskManager] = {}


def get_task_manager(name: str = "default") -> TaskManager:
    """获取命名的任务管理器（单例）"""
    if name not in _task_managers:
        _task_managers[name] = TaskManager(name)
    return _task_managers[name]


@asynccontextmanager
async def managed_tasks(name: str = "default"):
    """上下文管理器，自动管理任务生命周期
    
    Usage:
        async with managed_tasks("my_service") as tm:
            tm.create_task(some_async_func())
            tm.create_task(another_async_func())
            # 退出时自动取消所有任务
    """
    tm = get_task_manager(name)
    try:
        yield tm
    finally:
        await tm.cancel_all()


async def gather_with_timeout(
    *coros: Coroutine[Any, Any, Any],
    timeout: Optional[float] = None,
    return_exceptions: bool = True
) -> List[Any]:
    """带超时的 gather
    
    Args:
        *coros: 要并发执行的协程
        timeout: 超时时间（秒）
        return_exceptions: 是否返回异常而不是抛出
        
    Returns:
        结果列表
    """
    if timeout is None:
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    
    try:
        return await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=return_exceptions),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        # 取消未完成的任务
        for coro in coros:
            if asyncio.iscoroutine(coro):
                coro.close()
        raise


class AsyncBatcher:
    """异步批处理器，将多个请求合并批量处理"""
    
    def __init__(
        self,
        batch_fn: Callable[[List[Any]], Coroutine[Any, Any, List[Any]]],
        max_batch_size: int = 100,
        max_wait_time: float = 0.1
    ):
        """
        Args:
            batch_fn: 批量处理函数
            max_batch_size: 最大批次大小
            max_wait_time: 最大等待时间（秒）
        """
        self.batch_fn = batch_fn
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self._pending: List[tuple] = []  # (item, future)
        self._lock = asyncio.Lock()
        self._timer: Optional[asyncio.Task] = None
        
    async def add(self, item: Any) -> Any:
        """添加一个项目到批处理队列"""
        future = asyncio.Future()
        
        async with self._lock:
            self._pending.append((item, future))
            
            if len(self._pending) >= self.max_batch_size:
                # 达到批次大小，立即处理
                await self._process_batch()
            elif self._timer is None:
                # 启动定时器
                self._timer = asyncio.create_task(self._wait_and_process())
        
        return await future
    
    async def _wait_and_process(self):
        """等待并处理批次"""
        await asyncio.sleep(self.max_wait_time)
        async with self._lock:
            await self._process_batch()
            self._timer = None
    
    async def _process_batch(self):
        """处理当前批次"""
        if not self._pending:
            return
            
        batch = self._pending
        self._pending = []
        
        items = [item for item, _ in batch]
        futures = [future for _, future in batch]
        
        try:
            results = await self.batch_fn(items)
            for i, future in enumerate(futures):
                if not future.done():
                    if i < len(results):
                        future.set_result(results[i])
                    else:
                        future.set_exception(IndexError("批处理结果数量不匹配"))
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)
