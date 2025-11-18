"""
RAG Performance Monitoring
==========================

This module provides performance monitoring and metrics collection
for the RAG pipeline.
"""

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""

    operation: str
    start_time: float
    end_time: float = 0
    duration: float = 0
    memory_before: float = 0
    memory_after: float = 0
    memory_delta: float = 0
    cpu_percent: float = 0
    success: bool = True
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self):
        """Mark operation as complete and calculate metrics"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.memory_delta = self.memory_after - self.memory_before
        self.cpu_percent = psutil.Process().cpu_percent()


class RAGPerformanceMonitor:
    """Monitor and track RAG pipeline performance"""

    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor

        Args:
            max_history: Maximum number of metrics to keep in history
        """
        self.metrics_history: deque = deque(maxlen=max_history)
        self.active_operations: dict[str, PerformanceMetrics] = {}
        self.thresholds = {
            "query_time": 2.0,  # seconds
            "index_time": 10.0,  # seconds
            "memory_delta": 100,  # MB
            "cpu_threshold": 80,  # percent
        }
        self.alerts: list[dict[str, Any]] = []

    def start_operation(
        self, operation_name: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Start monitoring an operation

        Args:
            operation_name: Name of the operation
            metadata: Optional metadata to attach

        Returns:
            Operation ID
        """
        operation_id = f"{operation_name}_{time.time()}"

        metrics = PerformanceMetrics(
            operation=operation_name,
            start_time=time.time(),
            memory_before=psutil.Process().memory_info().rss / 1024 / 1024,  # MB
            metadata=metadata or {},
        )

        self.active_operations[operation_id] = metrics
        logger.debug(f"Started monitoring operation: {operation_id}")

        return operation_id

    def end_operation(
        self, operation_id: str, success: bool = True, error_message: str | None = None
    ):
        """
        End monitoring an operation

        Args:
            operation_id: ID of the operation
            success: Whether operation succeeded
            error_message: Optional error message
        """
        if operation_id not in self.active_operations:
            logger.warning(f"Operation {operation_id} not found in active operations")
            return

        metrics = self.active_operations[operation_id]
        metrics.success = success
        metrics.error_message = error_message
        metrics.complete()

        # Check thresholds and generate alerts
        self._check_thresholds(metrics)

        # Move to history
        self.metrics_history.append(metrics)
        del self.active_operations[operation_id]

        logger.debug(
            f"Completed monitoring operation: {operation_id} (duration: {metrics.duration:.2f}s)"
        )

    def _check_thresholds(self, metrics: PerformanceMetrics):
        """Check if metrics exceed thresholds and generate alerts"""
        alerts = []

        # Check query time threshold
        if (
            "query" in metrics.operation.lower()
            and metrics.duration > self.thresholds["query_time"]
        ):
            alerts.append(
                {
                    "type": "SLOW_QUERY",
                    "operation": metrics.operation,
                    "duration": metrics.duration,
                    "threshold": self.thresholds["query_time"],
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check indexing time threshold
        if (
            "index" in metrics.operation.lower()
            and metrics.duration > self.thresholds["index_time"]
        ):
            alerts.append(
                {
                    "type": "SLOW_INDEX",
                    "operation": metrics.operation,
                    "duration": metrics.duration,
                    "threshold": self.thresholds["index_time"],
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check memory usage
        if metrics.memory_delta > self.thresholds["memory_delta"]:
            alerts.append(
                {
                    "type": "HIGH_MEMORY",
                    "operation": metrics.operation,
                    "memory_delta": metrics.memory_delta,
                    "threshold": self.thresholds["memory_delta"],
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check CPU usage
        if metrics.cpu_percent > self.thresholds["cpu_threshold"]:
            alerts.append(
                {
                    "type": "HIGH_CPU",
                    "operation": metrics.operation,
                    "cpu_percent": metrics.cpu_percent,
                    "threshold": self.thresholds["cpu_threshold"],
                    "timestamp": datetime.now().isoformat(),
                }
            )

        for alert in alerts:
            logger.warning(f"Performance alert: {alert}")
            self.alerts.append(alert)

    def get_statistics(self) -> dict[str, Any]:
        """Get performance statistics"""
        if not self.metrics_history:
            return {
                "total_operations": 0,
                "average_duration": 0,
                "success_rate": 0,
                "alerts_count": len(self.alerts),
            }

        total_ops = len(self.metrics_history)
        successful_ops = sum(1 for m in self.metrics_history if m.success)
        avg_duration = sum(m.duration for m in self.metrics_history) / total_ops

        # Group by operation type
        operation_stats = {}
        for metric in self.metrics_history:
            op_type = metric.operation
            if op_type not in operation_stats:
                operation_stats[op_type] = {
                    "count": 0,
                    "total_duration": 0,
                    "failures": 0,
                    "avg_memory_delta": 0,
                }

            stats = operation_stats[op_type]
            stats["count"] += 1
            stats["total_duration"] += metric.duration
            if not metric.success:
                stats["failures"] += 1
            stats["avg_memory_delta"] += metric.memory_delta

        # Calculate averages
        for op_type, stats in operation_stats.items():
            stats["avg_duration"] = stats["total_duration"] / stats["count"]
            stats["avg_memory_delta"] = stats["avg_memory_delta"] / stats["count"]
            stats["success_rate"] = (
                (stats["count"] - stats["failures"]) / stats["count"] * 100
            )

        return {
            "total_operations": total_ops,
            "successful_operations": successful_ops,
            "success_rate": (successful_ops / total_ops) * 100,
            "average_duration": avg_duration,
            "operation_stats": operation_stats,
            "alerts_count": len(self.alerts),
            "recent_alerts": self.alerts[-10:] if self.alerts else [],
        }

    def reset_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()

    def get_active_operations(self) -> list[dict[str, Any]]:
        """Get list of currently active operations"""
        return [
            {
                "id": op_id,
                "operation": metrics.operation,
                "duration_so_far": time.time() - metrics.start_time,
                "metadata": metrics.metadata,
            }
            for op_id, metrics in self.active_operations.items()
        ]

    async def monitor_async_operation(
        self, operation_name: str, func: Callable, *args, **kwargs
    ):
        """
        Monitor an async operation

        Args:
            operation_name: Name of the operation
            func: Async function to monitor
            *args, **kwargs: Arguments for the function

        Returns:
            Function result
        """
        op_id = self.start_operation(operation_name)

        try:
            result = await func(*args, **kwargs)
            self.end_operation(op_id, success=True)
            return result
        except Exception as e:
            self.end_operation(op_id, success=False, error_message=str(e))
            raise

    def monitor_operation(self, operation_name: str):
        """
        Decorator to monitor a function's performance

        Args:
            operation_name: Name of the operation
        """

        def decorator(func):
            if asyncio.iscoroutinefunction(func):

                async def async_wrapper(*args, **kwargs):
                    return await self.monitor_async_operation(
                        operation_name, func, *args, **kwargs
                    )

                return async_wrapper
            else:

                def sync_wrapper(*args, **kwargs):
                    op_id = self.start_operation(operation_name)
                    try:
                        result = func(*args, **kwargs)
                        self.end_operation(op_id, success=True)
                        return result
                    except Exception as e:
                        self.end_operation(op_id, success=False, error_message=str(e))
                        raise

                return sync_wrapper

        return decorator


# Global instance for easy access
_global_monitor = None


def get_monitor() -> RAGPerformanceMonitor:
    """Get or create global performance monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = RAGPerformanceMonitor()
    return _global_monitor


# Export main classes
__all__ = ["PerformanceMetrics", "RAGPerformanceMonitor", "get_monitor"]
