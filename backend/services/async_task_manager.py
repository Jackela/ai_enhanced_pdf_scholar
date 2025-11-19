"""
Async Task Manager
Background task management for concurrent RAG query processing with memory optimization.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels for queue management."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class TaskCategory(Enum):
    """Categories of background tasks."""

    RAG_QUERY = "rag_query"
    INDEX_BUILD = "index_build"
    DOCUMENT_PROCESSING = "document_processing"
    CACHE_CLEANUP = "cache_cleanup"
    SYSTEM_MAINTENANCE = "system_maintenance"


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    used_mb: float
    available_mb: float
    percentage: float
    swap_used_mb: float
    is_critical: bool = field(default=False)


@dataclass
class TaskMetrics:
    """Task execution metrics."""

    start_time: datetime
    end_time: datetime | None = None
    memory_peak_mb: float = 0.0
    cpu_time_seconds: float = 0.0
    error_count: int = 0
    retry_count: int = 0

    @property
    def duration_ms(self) -> float:
        """Get task duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now() - self.start_time).total_seconds() * 1000


@dataclass
class AsyncTask:
    """Background task with memory management."""

    task_id: str
    category: TaskCategory
    priority: TaskPriority
    handler: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict[str, Any])
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: Exception | None = None
    metrics: TaskMetrics = field(default_factory=lambda: TaskMetrics(datetime.now()))
    memory_limit_mb: float | None = None
    timeout_seconds: float | None = None

    # Async task tracking
    asyncio_task: asyncio.Task[None] | None = None
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.asyncio_task and not self.asyncio_task.done()

    @property
    def age_seconds(self) -> float:
        """Get task age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


class MemoryMonitor:
    """System memory monitoring for task management."""

    def __init__(
        self, critical_threshold: float = 85.0, warning_threshold: float = 75.0
    ) -> None:
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold
        self._last_check = datetime.now()
        self._check_interval = timedelta(seconds=5)

    def get_memory_stats(self) -> MemoryStats:
        """Get current system memory statistics."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            used_mb = (memory.total - memory.available) / (1024 * 1024)
            available_mb = memory.available / (1024 * 1024)
            swap_used_mb = swap.used / (1024 * 1024)

            stats = MemoryStats(
                used_mb=used_mb,
                available_mb=available_mb,
                percentage=memory.percent,
                swap_used_mb=swap_used_mb,
                is_critical=memory.percent >= self.critical_threshold,
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return MemoryStats(0, 0, 0, 0, False)

    def should_limit_tasks(self) -> bool:
        """Check if new tasks should be limited due to memory pressure."""
        if datetime.now() - self._last_check < self._check_interval:
            return False

        self._last_check = datetime.now()
        stats = self.get_memory_stats()
        return stats.percentage >= self.warning_threshold

    def is_memory_critical(self) -> bool:
        """Check if memory usage is at critical levels."""
        stats = self.get_memory_stats()
        return stats.is_critical


class AsyncTaskManager:
    """Manages background tasks with memory optimization and concurrency control."""

    def __init__(
        self,
        max_concurrent_tasks: int = 5,
        max_queue_size: int = 100,
        memory_limit_mb: float | None = None,
        enable_memory_monitoring: bool = True,
    ) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        self.memory_limit_mb = memory_limit_mb

        # Task tracking
        self.active_tasks: dict[str, AsyncTask] = {}
        self.task_queue: asyncio.PriorityQueue[Any] = asyncio.PriorityQueue[Any](
            maxsize=max_queue_size
        )
        self.completed_tasks: dict[str, AsyncTask] = {}
        self.task_counter = 0

        # Memory management
        self.memory_monitor = MemoryMonitor() if enable_memory_monitoring else None
        self.thread_pool = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="async_task_"
        )

        # Background processing
        self._processor_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

        # Statistics
        self._stats_start_time = datetime.now()
        self._total_tasks_processed = 0
        self._total_errors = 0

    async def start(self) -> None:
        """Start the background task processor."""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_tasks())
        self._cleanup_task = asyncio.create_task(self._cleanup_completed_tasks())
        logger.info("AsyncTaskManager started")

    async def stop(self) -> None:
        """Stop the background task processor."""
        self._running = False

        # Cancel all active tasks
        for task in self.active_tasks.values():
            if task.asyncio_task and not task.asyncio_task.done():
                task.asyncio_task.cancel()
                task.cancellation_event.set[str]()

        # Wait for processor tasks to complete
        if self._processor_task:
            self._processor_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)

        logger.info("AsyncTaskManager stopped")

    async def submit_task(
        self,
        handler: Callable[..., Any],
        category: TaskCategory = TaskCategory.RAG_QUERY,
        priority: TaskPriority = TaskPriority.NORMAL,
        memory_limit_mb: float | None = None,
        timeout_seconds: float | None = None,
        *args,
        **kwargs,
    ) -> str:
        """Submit a new background task."""

        # Check memory pressure
        if self.memory_monitor and self.memory_monitor.is_memory_critical():
            raise RuntimeError(
                "Cannot submit task: System memory is at critical levels"
            )

        # Generate task ID
        self.task_counter += 1
        task_id = f"task_{int(time.time() * 1000)}_{self.task_counter}"

        # Create task
        task = AsyncTask(
            task_id=task_id,
            category=category,
            priority=priority,
            handler=handler,
            args=args,
            kwargs=kwargs,
            memory_limit_mb=memory_limit_mb or self.memory_limit_mb,
            timeout_seconds=timeout_seconds,
        )

        # Add to queue with priority (lower number = higher priority)
        try:
            priority_value = (
                4 - priority.value,
                time.time(),
            )  # Higher priority = lower number
            await self.task_queue.put((priority_value, task))
            logger.debug(f"Submitted task {task_id} with priority {priority.name}")
            return task_id
        except asyncio.QueueFull as e:
            raise RuntimeError(
                f"Task queue is full ({self.max_queue_size} tasks)"
            ) from e

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.asyncio_task and not task.asyncio_task.done():
                task.asyncio_task.cancel()
                task.cancellation_event.set[str]()
                logger.info(f"Cancelled active task {task_id}")
                return True

        # Note: Cancelling queued tasks would require scanning the queue
        # For now, we only cancel active tasks
        return False

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get status of a task."""
        # Check active tasks
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task_id,
                "status": "running",
                "category": task.category.value,
                "priority": task.priority.name,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "duration_ms": task.metrics.duration_ms,
                "memory_peak_mb": task.metrics.memory_peak_mb,
            }

        # Check completed tasks
        if task_id in self.completed_tasks:
            task = self.completed_tasks[task_id]
            return {
                "task_id": task_id,
                "status": "completed" if task.error is None else "failed",
                "category": task.category.value,
                "priority": task.priority.name,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": (
                    task.completed_at.isoformat() if task.completed_at else None
                ),
                "duration_ms": task.metrics.duration_ms,
                "memory_peak_mb": task.metrics.memory_peak_mb,
                "error": str(task.error) if task.error else None,
            }

        return None

    def get_stats(self) -> dict[str, Any]:
        """Get task manager statistics."""
        memory_stats = (
            self.memory_monitor.get_memory_stats() if self.memory_monitor else None
        )

        uptime_seconds = (datetime.now() - self._stats_start_time).total_seconds()

        return {
            "uptime_seconds": uptime_seconds,
            "active_tasks": len(self.active_tasks),
            "queue_size": self.task_queue.qsize(),
            "completed_tasks": len(self.completed_tasks),
            "total_processed": self._total_tasks_processed,
            "total_errors": self._total_errors,
            "max_concurrent": self.max_concurrent_tasks,
            "max_queue_size": self.max_queue_size,
            "memory_stats": (
                {
                    "used_mb": memory_stats.used_mb,
                    "available_mb": memory_stats.available_mb,
                    "percentage": memory_stats.percentage,
                    "is_critical": memory_stats.is_critical,
                }
                if memory_stats
                else None
            ),
            "active_task_details": [
                {
                    "task_id": task.task_id,
                    "category": task.category.value,
                    "duration_ms": task.metrics.duration_ms,
                    "memory_peak_mb": task.metrics.memory_peak_mb,
                }
                for task in self.active_tasks.values()
            ],
        }

    async def _process_tasks(self) -> None:
        """Background task processor."""
        while self._running:
            try:
                # Check if we can process more tasks
                if len(self.active_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(0.1)
                    continue

                # Check memory pressure
                if self.memory_monitor and self.memory_monitor.should_limit_tasks():
                    await asyncio.sleep(0.5)
                    continue

                try:
                    # Get next task from queue with timeout
                    priority_tuple, task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0
                    )

                    # Start task execution
                    task.started_at = datetime.now()
                    task.metrics.start_time = task.started_at

                    # Create asyncio task
                    task.asyncio_task = asyncio.create_task(self._execute_task(task))

                    # Track active task
                    self.active_tasks[task.task_id] = task

                    logger.debug(f"Started task {task.task_id}")

                except asyncio.TimeoutError:
                    # No tasks in queue, continue loop
                    continue

            except Exception as e:
                logger.error(f"Error in task processor: {e}")
                await asyncio.sleep(1.0)

    async def _execute_task(self, task: AsyncTask) -> None:
        """Execute a single task with monitoring."""
        try:
            # Setup cancellation handling
            if task.timeout_seconds:
                timeout_task = asyncio.create_task(asyncio.sleep(task.timeout_seconds))
                cancel_task = asyncio.create_task(task.cancellation_event.wait())

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(task.handler(*task.args, **task.kwargs)),
                        timeout_task,
                        cancel_task,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for pending_task in pending:
                    pending_task.cancel()

                # Check what completed first
                completed_task = list[Any](done)[0]
                if completed_task == timeout_task:
                    raise asyncio.TimeoutError(
                        f"Task {task.task_id} timed out after {task.timeout_seconds}s"
                    )
                elif completed_task == cancel_task:
                    raise asyncio.CancelledError(f"Task {task.task_id} was cancelled")
                else:
                    task.result = completed_task.result()
            else:
                # Execute without timeout
                task.result = await task.handler(*task.args, **task.kwargs)

            # Mark as completed
            task.completed_at = datetime.now()
            task.metrics.end_time = task.completed_at

            logger.debug(f"Task {task.task_id} completed successfully")

        except asyncio.CancelledError:
            task.error = Exception("Task was cancelled")
            task.completed_at = datetime.now()
            task.metrics.end_time = task.completed_at
            logger.info(f"Task {task.task_id} was cancelled")

        except Exception as e:
            task.error = e
            task.completed_at = datetime.now()
            task.metrics.end_time = task.completed_at
            task.metrics.error_count += 1
            self._total_errors += 1
            logger.error(f"Task {task.task_id} failed: {e}")

        finally:
            # Move to completed tasks
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task
                self._total_tasks_processed += 1

    async def _cleanup_completed_tasks(self) -> None:
        """Cleanup old completed tasks to prevent memory leaks."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                cutoff_time = datetime.now() - timedelta(minutes=10)
                tasks_to_remove = [
                    task_id
                    for task_id, task in self.completed_tasks.items()
                    if task.completed_at and task.completed_at < cutoff_time
                ]

                for task_id in tasks_to_remove:
                    del self.completed_tasks[task_id]

                if tasks_to_remove:
                    logger.debug(f"Cleaned up {len(tasks_to_remove)} completed tasks")

            except Exception as e:
                logger.error(f"Error in task cleanup: {e}")


# Global task manager instance
_task_manager: AsyncTaskManager | None = None


def get_task_manager() -> AsyncTaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager()
    return _task_manager


async def initialize_task_manager() -> Any:
    """Initialize the global task manager."""
    manager = get_task_manager()
    await manager.start()
    return manager


async def shutdown_task_manager() -> None:
    """Shutdown the global task manager."""
    global _task_manager
    if _task_manager:
        await _task_manager.stop()
        _task_manager = None
