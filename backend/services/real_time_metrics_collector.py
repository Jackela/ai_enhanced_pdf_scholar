"""
Real-time Metrics Collector Service

Collects and streams real-time system and application metrics for the
performance monitoring dashboard with WebSocket integration.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""
    SYSTEM = "system"
    DATABASE = "database"
    WEBSOCKET = "websocket"
    RAG = "rag"
    API = "api"
    MEMORY = "memory"


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int
    uptime_seconds: float


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    timestamp: datetime
    active_connections: int
    connection_pool_size: int
    connection_pool_available: int
    query_count: int
    slow_queries: int
    avg_query_time_ms: float
    database_size_mb: float
    index_usage_percent: float
    cache_hit_ratio: float


@dataclass
class WebSocketMetrics:
    """WebSocket connection and RAG task metrics."""
    timestamp: datetime
    active_connections: int
    total_rooms: int
    rag_tasks_total: int
    rag_tasks_pending: int
    rag_tasks_processing: int
    rag_tasks_streaming: int
    rag_tasks_completed: int
    rag_tasks_failed: int
    avg_task_duration_ms: float
    concurrent_task_limit: int


@dataclass
class APIMetrics:
    """API performance metrics."""
    timestamp: datetime
    requests_per_second: float
    avg_response_time_ms: float
    error_rate_percent: float
    active_sessions: int
    rate_limit_hits: int
    auth_success_rate: float
    cache_hit_rate: float


@dataclass
class MemoryLeakMetrics:
    """Memory leak detection metrics."""
    timestamp: datetime
    heap_size_mb: float
    heap_growth_rate_mb_per_min: float
    connection_leaks: int
    object_leaks: int
    gc_collections: int
    gc_time_ms: float
    memory_pressure_events: int


@dataclass
class AlertMetric:
    """Alert/notification metric."""
    timestamp: datetime
    metric_type: MetricType
    severity: str  # "info", "warning", "error", "critical"
    message: str
    source: str
    value: float | None = None
    threshold: float | None = None


class RealTimeMetricsCollector:
    """
    Collects real-time metrics from all system components and streams them
    to connected WebSocket clients for dashboard display.
    """

    def __init__(
        self,
        websocket_manager=None,
        integrated_monitor=None,
        collection_interval: float = 1.0,  # seconds
        retention_hours: int = 24
    ):
        self.websocket_manager = websocket_manager
        self.integrated_monitor = integrated_monitor
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours

        # Metric storage (in-memory for real-time, with periodic persistence)
        self.metrics_history: dict[MetricType, list[dict[str, Any]]] = {
            metric_type: [] for metric_type in MetricType
        }
        self.max_history_size = int((retention_hours * 3600) / collection_interval)

        # Background tasks
        self._collector_task: asyncio.Task | None = None
        self._streaming_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

        # Subscribers for real-time updates
        self.metric_subscribers: set[Callable] = set()

        # System baseline for comparisons
        self._system_baseline: SystemMetrics | None = None
        self._last_network_io = None
        self._last_disk_io = None
        self._process_start_time = time.time()

        # Alert thresholds
        self.alert_thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_usage_percent": 90.0,
            "error_rate_percent": 5.0,
            "avg_response_time_ms": 1000.0,
        }

        logger.info(f"RealTimeMetricsCollector initialized with {collection_interval}s interval")

    async def start_collection(self):
        """Start real-time metrics collection."""
        if self._running:
            logger.warning("Metrics collection already running")
            return

        self._running = True

        # Start background tasks
        self._collector_task = asyncio.create_task(self._collect_metrics_loop())
        self._streaming_task = asyncio.create_task(self._stream_metrics_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_old_metrics_loop())

        logger.info("Real-time metrics collection started")

    async def stop_collection(self):
        """Stop metrics collection."""
        self._running = False

        # Cancel tasks
        for task in [self._collector_task, self._streaming_task, self._cleanup_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Real-time metrics collection stopped")

    def subscribe_to_metrics(self, callback: Callable[[dict[str, Any]], None]):
        """Subscribe to real-time metric updates."""
        self.metric_subscribers.add(callback)

    def unsubscribe_from_metrics(self, callback: Callable):
        """Unsubscribe from metric updates."""
        self.metric_subscribers.discard(callback)

    async def _collect_metrics_loop(self):
        """Main metrics collection loop."""
        while self._running:
            try:
                # Collect all metric types
                system_metrics = self._collect_system_metrics()
                db_metrics = self._collect_database_metrics()
                ws_metrics = self._collect_websocket_metrics()
                api_metrics = self._collect_api_metrics()
                memory_metrics = self._collect_memory_leak_metrics()

                # Store metrics
                metrics_update = {
                    MetricType.SYSTEM: asdict(system_metrics) if system_metrics else None,
                    MetricType.DATABASE: asdict(db_metrics) if db_metrics else None,
                    MetricType.WEBSOCKET: asdict(ws_metrics) if ws_metrics else None,
                    MetricType.API: asdict(api_metrics) if api_metrics else None,
                    MetricType.MEMORY: asdict(memory_metrics) if memory_metrics else None,
                }

                # Add to history
                for metric_type, data in metrics_update.items():
                    if data:
                        # Convert datetime to ISO string for JSON serialization
                        if 'timestamp' in data:
                            data['timestamp'] = data['timestamp'].isoformat()

                        self.metrics_history[metric_type].append(data)

                        # Maintain history size limit
                        if len(self.metrics_history[metric_type]) > self.max_history_size:
                            self.metrics_history[metric_type].pop(0)

                # Check for alerts
                alerts = self._check_alert_conditions(metrics_update)
                if alerts:
                    for alert in alerts:
                        self._handle_alert(alert)

                # Notify subscribers
                await self._notify_subscribers(metrics_update)

            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")

            await asyncio.sleep(self.collection_interval)

    def _collect_system_metrics(self) -> SystemMetrics | None:
        """Collect system performance metrics."""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage('/')

            # Network I/O (calculate rate since last measurement)
            net_io = psutil.net_io_counters()
            disk_io = psutil.disk_io_counters()

            # Process information
            process_count = len(psutil.pids())

            # Thread count for current process
            current_process = psutil.Process()
            thread_count = current_process.num_threads()

            # Uptime
            uptime_seconds = time.time() - self._process_start_time

            # Calculate I/O rates
            disk_io_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
            disk_io_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0

            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=(memory.total - memory.available) / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=(disk.used / disk.total) * 100,
                disk_io_read_mb=disk_io_read_mb,
                disk_io_write_mb=disk_io_write_mb,
                network_bytes_sent=net_io.bytes_sent if net_io else 0,
                network_bytes_recv=net_io.bytes_recv if net_io else 0,
                process_count=process_count,
                thread_count=thread_count,
                uptime_seconds=uptime_seconds
            )

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None

    def _collect_database_metrics(self) -> DatabaseMetrics | None:
        """Collect database performance metrics."""
        try:
            # This would integrate with actual database monitoring
            # For now, return mock data based on existing database usage
            return DatabaseMetrics(
                timestamp=datetime.now(),
                active_connections=5,  # Would come from connection pool
                connection_pool_size=10,
                connection_pool_available=5,
                query_count=100,  # Would track actual queries
                slow_queries=2,
                avg_query_time_ms=25.5,
                database_size_mb=125.0,  # Calculate actual size
                index_usage_percent=85.0,
                cache_hit_ratio=92.5
            )

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return None

    def _collect_websocket_metrics(self) -> WebSocketMetrics | None:
        """Collect WebSocket and RAG task metrics."""
        try:
            if not self.websocket_manager:
                return None

            stats = self.websocket_manager.get_stats()

            # Calculate average task duration
            completed_tasks = [
                task for task in self.websocket_manager.rag_tasks.values()
                if task.processing_time_ms is not None
            ]
            avg_duration = (
                sum(task.processing_time_ms for task in completed_tasks) / len(completed_tasks)
                if completed_tasks else 0.0
            )

            return WebSocketMetrics(
                timestamp=datetime.now(),
                active_connections=stats["active_connections"],
                total_rooms=stats["total_rooms"],
                rag_tasks_total=stats["rag_streaming"]["total_tasks"],
                rag_tasks_pending=stats["rag_streaming"]["pending_tasks"],
                rag_tasks_processing=stats["rag_streaming"]["processing_tasks"],
                rag_tasks_streaming=stats["rag_streaming"]["streaming_tasks"],
                rag_tasks_completed=stats["rag_streaming"]["completed_tasks"],
                rag_tasks_failed=stats["rag_streaming"]["failed_tasks"],
                avg_task_duration_ms=avg_duration,
                concurrent_task_limit=stats["rag_config"]["max_concurrent_tasks"]
            )

        except Exception as e:
            logger.error(f"Error collecting WebSocket metrics: {e}")
            return None

    def _collect_api_metrics(self) -> APIMetrics | None:
        """Collect API performance metrics."""
        try:
            # This would integrate with actual API monitoring
            # Mock data for demonstration
            return APIMetrics(
                timestamp=datetime.now(),
                requests_per_second=15.5,
                avg_response_time_ms=125.0,
                error_rate_percent=0.8,
                active_sessions=25,
                rate_limit_hits=3,
                auth_success_rate=98.5,
                cache_hit_rate=87.2
            )

        except Exception as e:
            logger.error(f"Error collecting API metrics: {e}")
            return None

    def _collect_memory_leak_metrics(self) -> MemoryLeakMetrics | None:
        """Collect memory leak detection metrics."""
        try:
            import gc

            # Get current process memory info
            process = psutil.Process()
            memory_info = process.memory_info()

            # Garbage collection stats
            gc_stats = gc.get_stats()
            gc_count = sum(stat['collections'] for stat in gc_stats)

            return MemoryLeakMetrics(
                timestamp=datetime.now(),
                heap_size_mb=memory_info.rss / (1024 * 1024),
                heap_growth_rate_mb_per_min=0.5,  # Would calculate actual growth
                connection_leaks=0,  # Would detect actual leaks
                object_leaks=len(gc.get_objects()),
                gc_collections=gc_count,
                gc_time_ms=10.0,  # Mock value
                memory_pressure_events=0
            )

        except Exception as e:
            logger.error(f"Error collecting memory leak metrics: {e}")
            return None

    def _check_alert_conditions(self, metrics: dict[MetricType, dict[str, Any]]) -> list[AlertMetric]:
        """Check if any metrics exceed alert thresholds."""
        alerts = []

        try:
            # Check system metrics
            if MetricType.SYSTEM in metrics and metrics[MetricType.SYSTEM]:
                system_data = metrics[MetricType.SYSTEM]

                # CPU usage alert
                if system_data['cpu_percent'] > self.alert_thresholds['cpu_percent']:
                    alerts.append(AlertMetric(
                        timestamp=datetime.now(),
                        metric_type=MetricType.SYSTEM,
                        severity="warning",
                        message=f"High CPU usage: {system_data['cpu_percent']:.1f}%",
                        source="system_monitor",
                        value=system_data['cpu_percent'],
                        threshold=self.alert_thresholds['cpu_percent']
                    ))

                # Memory usage alert
                if system_data['memory_percent'] > self.alert_thresholds['memory_percent']:
                    alerts.append(AlertMetric(
                        timestamp=datetime.now(),
                        metric_type=MetricType.SYSTEM,
                        severity="error" if system_data['memory_percent'] > 90 else "warning",
                        message=f"High memory usage: {system_data['memory_percent']:.1f}%",
                        source="system_monitor",
                        value=system_data['memory_percent'],
                        threshold=self.alert_thresholds['memory_percent']
                    ))

            # Check API metrics
            if MetricType.API in metrics and metrics[MetricType.API]:
                api_data = metrics[MetricType.API]

                # Error rate alert
                if api_data['error_rate_percent'] > self.alert_thresholds['error_rate_percent']:
                    alerts.append(AlertMetric(
                        timestamp=datetime.now(),
                        metric_type=MetricType.API,
                        severity="warning",
                        message=f"High API error rate: {api_data['error_rate_percent']:.1f}%",
                        source="api_monitor",
                        value=api_data['error_rate_percent'],
                        threshold=self.alert_thresholds['error_rate_percent']
                    ))

                # Response time alert
                if api_data['avg_response_time_ms'] > self.alert_thresholds['avg_response_time_ms']:
                    alerts.append(AlertMetric(
                        timestamp=datetime.now(),
                        metric_type=MetricType.API,
                        severity="warning",
                        message=f"Slow API responses: {api_data['avg_response_time_ms']:.1f}ms",
                        source="api_monitor",
                        value=api_data['avg_response_time_ms'],
                        threshold=self.alert_thresholds['avg_response_time_ms']
                    ))

        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")

        return alerts

    def _handle_alert(self, alert: AlertMetric):
        """Handle triggered alert."""
        try:
            # Log the alert
            logger.warning(f"ALERT: {alert.message} (severity: {alert.severity})")

            # Add to metrics history
            alert_data = asdict(alert)
            alert_data['timestamp'] = alert.timestamp.isoformat()

            if MetricType.MEMORY not in self.metrics_history:
                self.metrics_history[MetricType.MEMORY] = []

            # Store alert as special metric type
            self.metrics_history[MetricType.MEMORY].append({
                **alert_data,
                'metric_category': 'alert'
            })

        except Exception as e:
            logger.error(f"Error handling alert: {e}")

    async def _notify_subscribers(self, metrics_update: dict[MetricType, dict[str, Any]]):
        """Notify all subscribers of metric updates."""
        for callback in self.metric_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(metrics_update)
                else:
                    callback(metrics_update)
            except Exception as e:
                logger.error(f"Error notifying metric subscriber: {e}")

    async def _stream_metrics_loop(self):
        """Stream metrics to WebSocket clients."""
        while self._running:
            try:
                if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast_json'):
                    # Get latest metrics
                    current_metrics = {}
                    for metric_type, history in self.metrics_history.items():
                        if history:
                            current_metrics[metric_type.value] = history[-1]

                    if current_metrics:
                        # Broadcast to all connected clients
                        await self.websocket_manager.broadcast_json({
                            "type": "metrics_update",
                            "timestamp": datetime.now().isoformat(),
                            "metrics": current_metrics
                        })

            except Exception as e:
                logger.error(f"Error streaming metrics: {e}")

            await asyncio.sleep(self.collection_interval)

    async def _cleanup_old_metrics_loop(self):
        """Clean up old metrics data."""
        while self._running:
            try:
                cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

                for metric_type, history in self.metrics_history.items():
                    # Remove old entries
                    self.metrics_history[metric_type] = [
                        entry for entry in history
                        if 'timestamp' in entry and
                        datetime.fromisoformat(entry['timestamp']) > cutoff_time
                    ]

            except Exception as e:
                logger.error(f"Error cleaning up old metrics: {e}")

            # Run cleanup every hour
            await asyncio.sleep(3600)

    def get_current_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        current_metrics = {}
        for metric_type, history in self.metrics_history.items():
            if history:
                current_metrics[metric_type.value] = history[-1]

        return current_metrics

    def get_metrics_history(
        self,
        metric_type: MetricType,
        hours_back: int = 1
    ) -> list[dict[str, Any]]:
        """Get historical metrics for a specific type."""
        if metric_type not in self.metrics_history:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        return [
            entry for entry in self.metrics_history[metric_type]
            if 'timestamp' in entry and
            datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]

    def get_system_health_summary(self) -> dict[str, Any]:
        """Get overall system health summary."""
        try:
            current_metrics = self.get_current_metrics()

            # Calculate health score (0-100)
            health_score = 100.0
            health_factors = []

            # System health factors
            if MetricType.SYSTEM.value in current_metrics:
                sys_data = current_metrics[MetricType.SYSTEM.value]

                # CPU health (reduce score if > 80%)
                cpu_factor = max(0, 100 - max(0, sys_data['cpu_percent'] - 80) * 2)
                health_score = min(health_score, cpu_factor)
                health_factors.append(f"CPU: {cpu_factor:.1f}")

                # Memory health (reduce score if > 85%)
                mem_factor = max(0, 100 - max(0, sys_data['memory_percent'] - 85) * 3)
                health_score = min(health_score, mem_factor)
                health_factors.append(f"Memory: {mem_factor:.1f}")

            # API health factors
            if MetricType.API.value in current_metrics:
                api_data = current_metrics[MetricType.API.value]

                # Error rate health
                error_factor = max(0, 100 - api_data['error_rate_percent'] * 10)
                health_score = min(health_score, error_factor)
                health_factors.append(f"API: {error_factor:.1f}")

            # Determine health status
            if health_score >= 90:
                status = "excellent"
            elif health_score >= 75:
                status = "good"
            elif health_score >= 50:
                status = "degraded"
            else:
                status = "critical"

            return {
                "health_score": health_score,
                "status": status,
                "factors": health_factors,
                "last_updated": datetime.now().isoformat(),
                "metrics_available": list(current_metrics.keys())
            }

        except Exception as e:
            logger.error(f"Error calculating system health: {e}")
            return {
                "health_score": 0.0,
                "status": "unknown",
                "factors": [],
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }
