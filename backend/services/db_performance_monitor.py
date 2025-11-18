"""
Real-time Database Performance Monitor for AI Enhanced PDF Scholar
Comprehensive database monitoring with real-time metrics, alerting, and optimization recommendations.
"""

import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Union

import psutil

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from backend.services.query_cache_manager import IntelligentQueryCacheManager
    from scripts.query_performance_analyzer import QueryPerformanceAnalyzer
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """Types of performance metrics."""

    COUNTER = "counter"  # Incrementing value
    GAUGE = "gauge"  # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Statistical summary


@dataclass
class PerformanceMetric:
    """Represents a performance metric."""

    name: str
    metric_type: MetricType
    value: Union[float, int, dict[str, Any]]
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary format."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "description": self.description,
        }


@dataclass
class PerformanceAlert:
    """Represents a performance alert."""

    alert_id: str
    metric_name: str
    severity: AlertSeverity
    message: str
    threshold_value: float
    current_value: float
    triggered_at: datetime
    resolved_at: datetime | None = None
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary format."""
        return {
            "alert_id": self.alert_id,
            "metric_name": self.metric_name,
            "severity": self.severity.value,
            "message": self.message,
            "threshold_value": self.threshold_value,
            "current_value": self.current_value,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged": self.acknowledged,
        }


@dataclass
class DatabaseHealthStatus:
    """Overall database health status."""

    overall_score: float  # 0-100
    connection_health: float
    query_performance_health: float
    resource_utilization_health: float
    cache_efficiency_health: float
    replication_health: float
    disk_health: float
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Get overall status string."""
        if self.overall_score >= 90:
            return "excellent"
        elif self.overall_score >= 75:
            return "good"
        elif self.overall_score >= 60:
            return "fair"
        elif self.overall_score >= 40:
            return "poor"
        else:
            return "critical"


class DatabasePerformanceMonitor:
    """
    Real-time Database Performance Monitor

    Features:
    - Real-time performance metrics collection
    - Intelligent alerting with thresholds
    - Query performance analysis
    - Resource utilization monitoring
    - Cache efficiency tracking
    - Health scoring and recommendations
    - Historical trend analysis
    - Integration with external monitoring systems
    """

    # Default alert thresholds
    DEFAULT_THRESHOLDS = {
        "connection_pool_utilization": 80.0,  # %
        "avg_query_response_time": 100.0,  # ms
        "slow_query_rate": 5.0,  # %
        "cache_hit_rate": 80.0,  # % (minimum)
        "cpu_usage": 80.0,  # %
        "memory_usage": 85.0,  # %
        "disk_usage": 90.0,  # %
        "disk_io_wait": 20.0,  # %
        "connection_errors": 1.0,  # %
        "lock_waits": 10.0,  # per second
        "deadlocks": 0.1,  # per minute
    }

    def __init__(
        self,
        db_connection: DatabaseConnection,
        query_analyzer: QueryPerformanceAnalyzer | None = None,
        cache_manager: IntelligentQueryCacheManager | None = None,
        monitoring_interval_s: int = 10,
        alert_thresholds: dict[str, float] | None = None,
        enable_system_monitoring: bool = True,
    ) -> None:
        """
        Initialize the Database Performance Monitor.

        Args:
            db_connection: Database connection instance
            query_analyzer: Optional query performance analyzer
            cache_manager: Optional query cache manager
            monitoring_interval_s: Monitoring interval in seconds
            alert_thresholds: Custom alert thresholds
            enable_system_monitoring: Whether to monitor system resources
        """
        self.db = db_connection
        self.query_analyzer = query_analyzer
        self.cache_manager = cache_manager
        self.monitoring_interval_s = monitoring_interval_s
        self.enable_system_monitoring = enable_system_monitoring

        # Alert configuration
        self.alert_thresholds = {**self.DEFAULT_THRESHOLDS, **(alert_thresholds or {})}

        # Metrics storage
        self._metrics: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )  # Keep last 1000 samples
        self._current_metrics: dict[str, PerformanceMetric] = {}
        self._alerts: dict[str, PerformanceAlert] = {}

        # Thread safety
        self._metrics_lock = threading.RLock()
        self._alerts_lock = threading.RLock()

        # Background monitoring
        self._monitor_thread: threading.Thread | None = None
        self._alert_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Performance baselines (learned over time)
        self._baselines: dict[str, dict[str, float]] = {}

        # Initialize monitoring infrastructure
        self._init_monitoring_tables()
        self._start_background_monitoring()

    def _init_monitoring_tables(self) -> None:
        """Initialize monitoring tables in database."""
        try:
            # Performance metrics table
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value TEXT NOT NULL,
                    labels TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_metrics_name_timestamp (metric_name, timestamp)
                )
            """
            )

            # Performance alerts table
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_alerts (
                    alert_id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    threshold_value REAL NOT NULL,
                    current_value REAL NOT NULL,
                    triggered_at DATETIME NOT NULL,
                    resolved_at DATETIME,
                    acknowledged BOOLEAN DEFAULT FALSE
                )
            """
            )

            # Monitoring configuration table
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS monitoring_config (
                    config_key TEXT PRIMARY KEY,
                    config_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            logger.info("Database performance monitoring tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize monitoring tables: {e}")

    def _start_background_monitoring(self) -> None:
        """Start background monitoring threads."""
        # Main monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker, daemon=True, name="DBPerformanceMonitor"
        )
        self._monitor_thread.start()

        # Alert processing thread
        self._alert_thread = threading.Thread(
            target=self._alert_worker, daemon=True, name="DBPerformanceAlerts"
        )
        self._alert_thread.start()

        logger.info("Database performance monitoring started")

    def _monitor_worker(self) -> None:
        """Main monitoring worker thread."""
        while not self._shutdown_event.wait(self.monitoring_interval_s):
            try:
                self._collect_database_metrics()
                self._collect_query_metrics()
                self._collect_cache_metrics()

                if self.enable_system_monitoring:
                    self._collect_system_metrics()

                self._update_baselines()
                self._persist_metrics()

            except Exception as e:
                logger.error(f"Monitoring error: {e}")

    def _alert_worker(self) -> None:
        """Alert processing worker thread."""
        while not self._shutdown_event.wait(5):  # Check alerts every 5 seconds
            try:
                self._check_alert_conditions()
                self._resolve_alerts()
            except Exception as e:
                logger.error(f"Alert processing error: {e}")

    def _collect_database_metrics(self) -> None:
        """Collect database-specific metrics."""
        try:
            current_time = datetime.now()

            # Connection pool metrics
            pool_stats = self.db.get_pool_stats()

            metrics = [
                PerformanceMetric(
                    name="db_connection_pool_total",
                    metric_type=MetricType.GAUGE,
                    value=pool_stats.get("total_connections", 0),
                    timestamp=current_time,
                    description="Total connections in pool",
                ),
                PerformanceMetric(
                    name="db_connection_pool_active",
                    metric_type=MetricType.GAUGE,
                    value=pool_stats.get("active_connections", 0),
                    timestamp=current_time,
                    description="Active connections",
                ),
                PerformanceMetric(
                    name="db_connection_pool_utilization",
                    metric_type=MetricType.GAUGE,
                    value=self._calculate_pool_utilization(pool_stats),
                    timestamp=current_time,
                    description="Connection pool utilization percentage",
                ),
                PerformanceMetric(
                    name="db_connection_errors",
                    metric_type=MetricType.COUNTER,
                    value=pool_stats.get("errors", 0),
                    timestamp=current_time,
                    description="Total connection errors",
                ),
            ]

            # Database size and table metrics
            try:
                db_info = self.db.get_database_info()

                metrics.append(
                    PerformanceMetric(
                        name="db_size_bytes",
                        metric_type=MetricType.GAUGE,
                        value=db_info.get("database_size", 0),
                        timestamp=current_time,
                        description="Database size in bytes",
                    )
                )

                metrics.append(
                    PerformanceMetric(
                        name="db_table_count",
                        metric_type=MetricType.GAUGE,
                        value=len(db_info.get("tables", [])),
                        timestamp=current_time,
                        description="Number of database tables",
                    )
                )

            except Exception as e:
                logger.debug(f"Failed to collect database info: {e}")

            # SQLite-specific metrics
            try:
                pragma_stats = [
                    ("cache_size", "PRAGMA cache_size"),
                    ("page_count", "PRAGMA page_count"),
                    ("freelist_count", "PRAGMA freelist_count"),
                    ("wal_checkpoint", "PRAGMA wal_checkpoint(PASSIVE)"),
                ]

                for stat_name, pragma_query in pragma_stats:
                    try:
                        result = self.db.fetch_one(pragma_query)
                        if result:
                            value = (
                                next(iter(result))
                                if isinstance(result, dict)
                                else result[0]
                            )
                            metrics.append(
                                PerformanceMetric(
                                    name=f"db_{stat_name}",
                                    metric_type=MetricType.GAUGE,
                                    value=float(value) if value is not None else 0.0,
                                    timestamp=current_time,
                                    description=f"SQLite {stat_name}",
                                )
                            )
                    except Exception:
                        pass  # Skip failed PRAGMA queries

            except Exception as e:
                logger.debug(f"Failed to collect SQLite metrics: {e}")

            # Store metrics
            with self._metrics_lock:
                for metric in metrics:
                    self._current_metrics[metric.name] = metric
                    self._metrics[metric.name].append(metric)

        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")

    def _collect_query_metrics(self) -> None:
        """Collect query performance metrics."""
        if not self.query_analyzer:
            return

        try:
            current_time = datetime.now()

            # Get query performance summary
            perf_summary = self.query_analyzer.get_performance_summary(
                time_window_hours=1
            )

            metrics = [
                PerformanceMetric(
                    name="query_total_count",
                    metric_type=MetricType.COUNTER,
                    value=perf_summary.get("total_queries", 0),
                    timestamp=current_time,
                    description="Total queries executed",
                ),
                PerformanceMetric(
                    name="query_avg_response_time_ms",
                    metric_type=MetricType.GAUGE,
                    value=perf_summary.get("avg_execution_time_ms", 0),
                    timestamp=current_time,
                    description="Average query response time",
                ),
                PerformanceMetric(
                    name="query_max_response_time_ms",
                    metric_type=MetricType.GAUGE,
                    value=perf_summary.get("max_execution_time_ms", 0),
                    timestamp=current_time,
                    description="Maximum query response time",
                ),
                PerformanceMetric(
                    name="query_slow_count",
                    metric_type=MetricType.COUNTER,
                    value=perf_summary.get("slow_queries_count", 0),
                    timestamp=current_time,
                    description="Number of slow queries",
                ),
                PerformanceMetric(
                    name="query_performance_score",
                    metric_type=MetricType.GAUGE,
                    value=perf_summary.get("overall_performance_score", 0),
                    timestamp=current_time,
                    description="Overall query performance score",
                ),
            ]

            # Calculate slow query rate
            total_queries = perf_summary.get("total_queries", 0)
            slow_queries = perf_summary.get("slow_queries_count", 0)
            slow_query_rate = (slow_queries / max(total_queries, 1)) * 100

            metrics.append(
                PerformanceMetric(
                    name="query_slow_rate",
                    metric_type=MetricType.GAUGE,
                    value=slow_query_rate,
                    timestamp=current_time,
                    description="Slow query rate percentage",
                )
            )

            # Store metrics
            with self._metrics_lock:
                for metric in metrics:
                    self._current_metrics[metric.name] = metric
                    self._metrics[metric.name].append(metric)

        except Exception as e:
            logger.error(f"Failed to collect query metrics: {e}")

    def _collect_cache_metrics(self) -> None:
        """Collect cache performance metrics."""
        if not self.cache_manager:
            return

        try:
            current_time = datetime.now()

            # Get cache statistics
            cache_stats = self.cache_manager.get_statistics()

            # Calculate cache hit rate
            total_requests = cache_stats.hit_count + cache_stats.miss_count
            hit_rate = (cache_stats.hit_count / max(total_requests, 1)) * 100

            metrics = [
                PerformanceMetric(
                    name="cache_hit_count",
                    metric_type=MetricType.COUNTER,
                    value=cache_stats.hit_count,
                    timestamp=current_time,
                    description="Cache hit count",
                ),
                PerformanceMetric(
                    name="cache_miss_count",
                    metric_type=MetricType.COUNTER,
                    value=cache_stats.miss_count,
                    timestamp=current_time,
                    description="Cache miss count",
                ),
                PerformanceMetric(
                    name="cache_hit_rate",
                    metric_type=MetricType.GAUGE,
                    value=hit_rate,
                    timestamp=current_time,
                    description="Cache hit rate percentage",
                ),
                PerformanceMetric(
                    name="cache_entries_count",
                    metric_type=MetricType.GAUGE,
                    value=cache_stats.total_entries,
                    timestamp=current_time,
                    description="Total cache entries",
                ),
                PerformanceMetric(
                    name="cache_memory_usage_mb",
                    metric_type=MetricType.GAUGE,
                    value=cache_stats.memory_usage_mb,
                    timestamp=current_time,
                    description="Cache memory usage in MB",
                ),
                PerformanceMetric(
                    name="cache_eviction_count",
                    metric_type=MetricType.COUNTER,
                    value=cache_stats.eviction_count,
                    timestamp=current_time,
                    description="Cache eviction count",
                ),
            ]

            # Store metrics
            with self._metrics_lock:
                for metric in metrics:
                    self._current_metrics[metric.name] = metric
                    self._metrics[metric.name].append(metric)

        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")

    def _collect_system_metrics(self) -> None:
        """Collect system resource metrics."""
        try:
            current_time = datetime.now()

            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory metrics
            memory = psutil.virtual_memory()

            # Disk metrics
            disk_usage = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()

            metrics = [
                PerformanceMetric(
                    name="system_cpu_usage",
                    metric_type=MetricType.GAUGE,
                    value=cpu_percent,
                    timestamp=current_time,
                    description="CPU usage percentage",
                ),
                PerformanceMetric(
                    name="system_memory_usage",
                    metric_type=MetricType.GAUGE,
                    value=memory.percent,
                    timestamp=current_time,
                    description="Memory usage percentage",
                ),
                PerformanceMetric(
                    name="system_memory_available_mb",
                    metric_type=MetricType.GAUGE,
                    value=memory.available / (1024 * 1024),
                    timestamp=current_time,
                    description="Available memory in MB",
                ),
                PerformanceMetric(
                    name="system_disk_usage",
                    metric_type=MetricType.GAUGE,
                    value=(disk_usage.used / disk_usage.total) * 100,
                    timestamp=current_time,
                    description="Disk usage percentage",
                ),
                PerformanceMetric(
                    name="system_disk_free_gb",
                    metric_type=MetricType.GAUGE,
                    value=disk_usage.free / (1024**3),
                    timestamp=current_time,
                    description="Free disk space in GB",
                ),
            ]

            # Disk I/O metrics
            if disk_io:
                metrics.extend(
                    [
                        PerformanceMetric(
                            name="system_disk_read_bytes",
                            metric_type=MetricType.COUNTER,
                            value=disk_io.read_bytes,
                            timestamp=current_time,
                            description="Disk read bytes",
                        ),
                        PerformanceMetric(
                            name="system_disk_write_bytes",
                            metric_type=MetricType.COUNTER,
                            value=disk_io.write_bytes,
                            timestamp=current_time,
                            description="Disk write bytes",
                        ),
                    ]
                )

            # Store metrics
            with self._metrics_lock:
                for metric in metrics:
                    self._current_metrics[metric.name] = metric
                    self._metrics[metric.name].append(metric)

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    def _calculate_pool_utilization(self, pool_stats: dict[str, Any]) -> float:
        """Calculate connection pool utilization percentage."""
        total = pool_stats.get("total_connections", 0)
        active = pool_stats.get("active_connections", 0)

        if total == 0:
            return 0.0

        return (active / total) * 100

    def _update_baselines(self) -> None:
        """Update performance baselines for anomaly detection."""
        try:
            with self._metrics_lock:
                for metric_name, metric_history in self._metrics.items():
                    if len(metric_history) >= 10:  # Need minimum samples
                        values = [
                            m.value
                            for m in metric_history
                            if isinstance(m.value, (int, float))
                        ]

                        if values:
                            baseline = {
                                "mean": statistics.mean(values),
                                "median": statistics.median(values),
                                "stdev": (
                                    statistics.stdev(values) if len(values) > 1 else 0
                                ),
                                "min": min(values),
                                "max": max(values),
                                "p95": self._calculate_percentile(values, 0.95),
                                "p99": self._calculate_percentile(values, 0.99),
                            }

                            self._baselines[metric_name] = baseline

        except Exception as e:
            logger.debug(f"Failed to update baselines: {e}")

    def _calculate_percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(percentile * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _persist_metrics(self) -> None:
        """Persist metrics to database for historical analysis."""
        try:
            current_metrics = []

            with self._metrics_lock:
                # Only persist latest metric for each name
                for metric in self._current_metrics.values():
                    current_metrics.append(metric)

            # Batch insert metrics
            for metric in current_metrics:
                try:
                    self.db.execute(
                        """
                        INSERT INTO performance_metrics
                        (metric_name, metric_type, metric_value, labels, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            metric.name,
                            metric.metric_type.value,
                            json.dumps(metric.value),
                            json.dumps(metric.labels),
                            metric.timestamp.isoformat(),
                        ),
                    )
                except Exception as e:
                    logger.debug(f"Failed to persist metric {metric.name}: {e}")

        except Exception as e:
            logger.debug(f"Failed to persist metrics: {e}")

    def _check_alert_conditions(self) -> None:
        """Check alert conditions and trigger alerts."""
        try:
            with self._metrics_lock:
                for metric_name, threshold in self.alert_thresholds.items():
                    if metric_name in self._current_metrics:
                        metric = self._current_metrics[metric_name]

                        if isinstance(metric.value, (int, float)):
                            # Check threshold violation
                            violated = self._check_threshold_violation(
                                metric_name, metric.value, threshold
                            )

                            if violated:
                                self._trigger_alert(metric, threshold)

        except Exception as e:
            logger.error(f"Failed to check alert conditions: {e}")

    def _check_threshold_violation(
        self, metric_name: str, value: float, threshold: float
    ) -> bool:
        """Check if a metric value violates its threshold."""
        # Different threshold logic for different metrics
        if metric_name in ["cache_hit_rate"]:
            # For cache hit rate, alert if BELOW threshold
            return value < threshold
        elif metric_name in [
            "db_connection_pool_utilization",
            "avg_query_response_time",
            "slow_query_rate",
            "cpu_usage",
            "memory_usage",
            "disk_usage",
        ]:
            # For these metrics, alert if ABOVE threshold
            return value > threshold
        elif metric_name in ["connection_errors", "lock_waits", "deadlocks"]:
            # For error metrics, alert if above threshold
            return value > threshold

        return False

    def _trigger_alert(self, metric: PerformanceMetric, threshold: float) -> None:
        """Trigger a performance alert."""
        try:
            # Determine severity based on how much threshold is exceeded
            if isinstance(metric.value, (int, float)):
                severity = self._calculate_alert_severity(
                    metric.name, metric.value, threshold
                )

                alert_id = f"{metric.name}_{int(time.time())}"

                # Check if similar alert already exists
                existing_alert = None
                with self._alerts_lock:
                    for alert in self._alerts.values():
                        if (
                            alert.metric_name == metric.name
                            and alert.resolved_at is None
                            and (datetime.now() - alert.triggered_at).seconds < 300
                        ):  # Within 5 minutes
                            existing_alert = alert
                            break

                if existing_alert:
                    # Update existing alert
                    existing_alert.current_value = metric.value
                    return

                # Create new alert
                alert = PerformanceAlert(
                    alert_id=alert_id,
                    metric_name=metric.name,
                    severity=severity,
                    message=self._generate_alert_message(
                        metric.name, metric.value, threshold, severity
                    ),
                    threshold_value=threshold,
                    current_value=metric.value,
                    triggered_at=datetime.now(),
                )

                with self._alerts_lock:
                    self._alerts[alert_id] = alert

                # Persist alert
                self._persist_alert(alert)

                logger.warning(f"Performance alert triggered: {alert.message}")

        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")

    def _calculate_alert_severity(
        self, metric_name: str, value: float, threshold: float
    ) -> AlertSeverity:
        """Calculate alert severity based on threshold violation degree."""
        if metric_name in ["cache_hit_rate"]:
            # For cache hit rate (lower is worse)
            deviation = (threshold - value) / threshold
        else:
            # For other metrics (higher is worse)
            deviation = (value - threshold) / threshold

        if deviation >= 0.5:  # 50% over threshold
            return AlertSeverity.CRITICAL
        elif deviation >= 0.25:  # 25% over threshold
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    def _generate_alert_message(
        self, metric_name: str, value: float, threshold: float, severity: AlertSeverity
    ) -> str:
        """Generate human-readable alert message."""
        messages = {
            "db_connection_pool_utilization": f"Connection pool utilization is {value:.1f}% (threshold: {threshold:.1f}%)",
            "query_avg_response_time_ms": f"Average query response time is {value:.2f}ms (threshold: {threshold:.2f}ms)",
            "query_slow_rate": f"Slow query rate is {value:.1f}% (threshold: {threshold:.1f}%)",
            "cache_hit_rate": f"Cache hit rate is {value:.1f}% (threshold: {threshold:.1f}%)",
            "system_cpu_usage": f"CPU usage is {value:.1f}% (threshold: {threshold:.1f}%)",
            "system_memory_usage": f"Memory usage is {value:.1f}% (threshold: {threshold:.1f}%)",
            "system_disk_usage": f"Disk usage is {value:.1f}% (threshold: {threshold:.1f}%)",
        }

        base_message = messages.get(
            metric_name, f"Metric {metric_name} is {value} (threshold: {threshold})"
        )

        return f"{severity.value.upper()}: {base_message}"

    def _persist_alert(self, alert: PerformanceAlert) -> None:
        """Persist alert to database."""
        try:
            self.db.execute(
                """
                INSERT INTO performance_alerts
                (alert_id, metric_name, severity, message, threshold_value,
                 current_value, triggered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    alert.alert_id,
                    alert.metric_name,
                    alert.severity.value,
                    alert.message,
                    alert.threshold_value,
                    alert.current_value,
                    alert.triggered_at.isoformat(),
                ),
            )

        except Exception as e:
            logger.debug(f"Failed to persist alert: {e}")

    def _resolve_alerts(self) -> None:
        """Check if active alerts should be resolved."""
        try:
            with self._alerts_lock:
                alerts_to_resolve = []

                for alert in self._alerts.values():
                    if alert.resolved_at is not None:
                        continue

                    # Check if metric is back within threshold
                    if alert.metric_name in self._current_metrics:
                        current_metric = self._current_metrics[alert.metric_name]

                        if isinstance(current_metric.value, (int, float)):
                            violation = self._check_threshold_violation(
                                alert.metric_name,
                                current_metric.value,
                                alert.threshold_value,
                            )

                            if not violation:
                                alerts_to_resolve.append(alert)

                # Resolve alerts
                for alert in alerts_to_resolve:
                    alert.resolved_at = datetime.now()

                    # Update in database
                    try:
                        self.db.execute(
                            """
                            UPDATE performance_alerts
                            SET resolved_at = ?
                            WHERE alert_id = ?
                        """,
                            (alert.resolved_at.isoformat(), alert.alert_id),
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update resolved alert: {e}")

                    logger.info(f"Performance alert resolved: {alert.metric_name}")

        except Exception as e:
            logger.error(f"Failed to resolve alerts: {e}")

    def get_current_metrics(self) -> dict[str, PerformanceMetric]:
        """Get current performance metrics."""
        with self._metrics_lock:
            return dict(self._current_metrics)

    def get_metric_history(
        self, metric_name: str, hours: int = 24
    ) -> list[PerformanceMetric]:
        """Get historical data for a specific metric."""
        with self._metrics_lock:
            if metric_name not in self._metrics:
                return []

            cutoff_time = datetime.now() - timedelta(hours=hours)

            return [
                metric
                for metric in self._metrics[metric_name]
                if metric.timestamp >= cutoff_time
            ]

    def get_active_alerts(self) -> list[PerformanceAlert]:
        """Get list of active (unresolved) alerts."""
        with self._alerts_lock:
            return [
                alert for alert in self._alerts.values() if alert.resolved_at is None
            ]

    def get_database_health(self) -> DatabaseHealthStatus:
        """Calculate overall database health status."""
        try:
            health_scores = {}
            issues = []
            recommendations = []

            with self._metrics_lock:
                # Connection health
                if "db_connection_pool_utilization" in self._current_metrics:
                    utilization = self._current_metrics[
                        "db_connection_pool_utilization"
                    ].value
                    if isinstance(utilization, (int, float)):
                        health_scores["connection"] = max(0, 100 - utilization)
                        if utilization > 80:
                            issues.append(
                                f"High connection pool utilization: {utilization:.1f}%"
                            )
                            recommendations.append(
                                "Consider increasing connection pool size"
                            )

                # Query performance health
                if "query_performance_score" in self._current_metrics:
                    perf_score = self._current_metrics["query_performance_score"].value
                    if isinstance(perf_score, (int, float)):
                        health_scores["query_performance"] = perf_score
                        if perf_score < 70:
                            issues.append(
                                f"Poor query performance score: {perf_score:.1f}"
                            )
                            recommendations.append(
                                "Review slow queries and add indexes"
                            )

                # Resource utilization health
                cpu_score = 100
                memory_score = 100
                disk_score = 100

                if "system_cpu_usage" in self._current_metrics:
                    cpu_usage = self._current_metrics["system_cpu_usage"].value
                    if isinstance(cpu_usage, (int, float)):
                        cpu_score = max(0, 100 - cpu_usage)
                        if cpu_usage > 80:
                            issues.append(f"High CPU usage: {cpu_usage:.1f}%")

                if "system_memory_usage" in self._current_metrics:
                    memory_usage = self._current_metrics["system_memory_usage"].value
                    if isinstance(memory_usage, (int, float)):
                        memory_score = max(0, 100 - memory_usage)
                        if memory_usage > 85:
                            issues.append(f"High memory usage: {memory_usage:.1f}%")

                if "system_disk_usage" in self._current_metrics:
                    disk_usage = self._current_metrics["system_disk_usage"].value
                    if isinstance(disk_usage, (int, float)):
                        disk_score = max(0, 100 - disk_usage)
                        if disk_usage > 90:
                            issues.append(f"High disk usage: {disk_usage:.1f}%")
                            recommendations.append(
                                "Clean up old data or expand storage"
                            )

                health_scores["resource_utilization"] = (
                    cpu_score + memory_score + disk_score
                ) / 3

                # Cache efficiency health
                if "cache_hit_rate" in self._current_metrics:
                    cache_hit_rate = self._current_metrics["cache_hit_rate"].value
                    if isinstance(cache_hit_rate, (int, float)):
                        health_scores["cache_efficiency"] = cache_hit_rate
                        if cache_hit_rate < 70:
                            issues.append(f"Low cache hit rate: {cache_hit_rate:.1f}%")
                            recommendations.append(
                                "Review cache configuration and TTL settings"
                            )

                # Replication health (placeholder for future multi-master setup)
                health_scores["replication"] = 100  # Assume healthy for now

                # Disk health
                health_scores["disk"] = disk_score

            # Calculate overall score
            if health_scores:
                overall_score = sum(health_scores.values()) / len(health_scores)
            else:
                overall_score = 50  # Default score if no metrics available

            return DatabaseHealthStatus(
                overall_score=overall_score,
                connection_health=health_scores.get("connection", 100),
                query_performance_health=health_scores.get("query_performance", 100),
                resource_utilization_health=health_scores.get(
                    "resource_utilization", 100
                ),
                cache_efficiency_health=health_scores.get("cache_efficiency", 100),
                replication_health=health_scores.get("replication", 100),
                disk_health=health_scores.get("disk", 100),
                issues=issues,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Failed to calculate database health: {e}")
            return DatabaseHealthStatus(
                overall_score=0,
                connection_health=0,
                query_performance_health=0,
                resource_utilization_health=0,
                cache_efficiency_health=0,
                replication_health=0,
                disk_health=0,
                issues=[f"Health calculation failed: {e}"],
                recommendations=["Check monitoring system health"],
            )

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        try:
            with self._alerts_lock:
                if alert_id in self._alerts:
                    self._alerts[alert_id].acknowledged = True

                    # Update in database
                    self.db.execute(
                        """
                        UPDATE performance_alerts
                        SET acknowledged = TRUE
                        WHERE alert_id = ?
                    """,
                        (alert_id,),
                    )

                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False

    def update_alert_threshold(self, metric_name: str, threshold: float) -> bool:
        """Update alert threshold for a metric."""
        try:
            self.alert_thresholds[metric_name] = threshold

            # Store in database
            self.db.execute(
                """
                INSERT OR REPLACE INTO monitoring_config
                (config_key, config_value)
                VALUES (?, ?)
            """,
                (f"threshold_{metric_name}", str(threshold)),
            )

            logger.info(f"Updated alert threshold for {metric_name}: {threshold}")
            return True

        except Exception as e:
            logger.error(f"Failed to update threshold for {metric_name}: {e}")
            return False

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        try:
            with self._metrics_lock:
                metrics_data = {
                    metric_name: [m.to_dict() for m in metric_history]
                    for metric_name, metric_history in self._metrics.items()
                }

            if format.lower() == "json":
                return json.dumps(metrics_data, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return ""

    def shutdown(self) -> None:
        """Shutdown the performance monitor and cleanup resources."""
        self._shutdown_event.set()

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        if self._alert_thread:
            self._alert_thread.join(timeout=5)

        logger.info("Database performance monitor shutdown complete")


def main() -> Any:
    """CLI interface for the Database Performance Monitor."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Performance Monitor")
    parser.add_argument("--db-path", required=True, help="Database file path")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring")
    parser.add_argument("--health", action="store_true", help="Show database health")
    parser.add_argument("--alerts", action="store_true", help="Show active alerts")
    parser.add_argument("--metrics", help="Show specific metric history")
    parser.add_argument("--export", help="Export metrics to file")
    parser.add_argument(
        "--duration", type=int, default=60, help="Monitoring duration in seconds"
    )

    args = parser.parse_args()

    try:
        # Initialize database connection
        db = DatabaseConnection(args.db_path)

        # Initialize performance monitor
        monitor = DatabasePerformanceMonitor(
            db_connection=db,
            monitoring_interval_s=5,  # 5-second intervals for demo
            enable_system_monitoring=True,
        )

        if args.monitor:
            print(f"Starting database monitoring for {args.duration} seconds...")
            time.sleep(args.duration)
            print("Monitoring completed")

        if args.health:
            health = monitor.get_database_health()
            print("Database Health Status:")
            print(
                f"Overall Score: {health.overall_score:.1f}/100 ({health.status.upper()})"
            )
            print(f"Connection Health: {health.connection_health:.1f}")
            print(f"Query Performance: {health.query_performance_health:.1f}")
            print(f"Resource Utilization: {health.resource_utilization_health:.1f}")
            print(f"Cache Efficiency: {health.cache_efficiency_health:.1f}")

            if health.issues:
                print("\nIssues:")
                for issue in health.issues:
                    print(f"  - {issue}")

            if health.recommendations:
                print("\nRecommendations:")
                for rec in health.recommendations:
                    print(f"  - {rec}")

        if args.alerts:
            alerts = monitor.get_active_alerts()
            print(f"Active Alerts ({len(alerts)}):")
            for alert in alerts:
                print(f"  {alert.severity.value.upper()}: {alert.message}")
                print(f"    Triggered: {alert.triggered_at}")
                print(f"    Acknowledged: {alert.acknowledged}")
                print()

        if args.metrics:
            history = monitor.get_metric_history(args.metrics, hours=1)
            print(f"Metric History for {args.metrics} (last hour):")
            for metric in history[-10:]:  # Show last 10 samples
                print(f"  {metric.timestamp}: {metric.value}")

        if args.export:
            exported = monitor.export_metrics()
            with open(args.export, "w") as f:
                f.write(exported)
            print(f"Metrics exported to {args.export}")

        monitor.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
