"""
Advanced Application Performance Monitoring (APM) Service

Provides comprehensive application performance monitoring, distributed tracing,
and real-time performance analytics for the AI Enhanced PDF Scholar system.
"""

import json
import logging
import threading
import time
import traceback
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any

import psutil

from backend.services.cache_telemetry_service import CacheTelemetryService
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


# ============================================================================
# APM Data Models
# ============================================================================


class TraceType(str, Enum):
    """Types of traces."""

    HTTP_REQUEST = "http_request"
    RAG_QUERY = "rag_query"
    DATABASE_QUERY = "database_query"
    DOCUMENT_PROCESSING = "document_processing"
    CACHE_OPERATION = "cache_operation"
    VECTOR_SEARCH = "vector_search"
    FILE_OPERATION = "file_operation"


class SpanType(str, Enum):
    """Types of spans within traces."""

    ROOT = "root"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    COMPUTATION = "computation"
    IO_OPERATION = "io_operation"


class PerformanceIssueType(str, Enum):
    """Types of performance issues."""

    HIGH_LATENCY = "high_latency"
    HIGH_ERROR_RATE = "high_error_rate"
    MEMORY_LEAK = "memory_leak"
    CPU_SPIKE = "cpu_spike"
    SLOW_QUERY = "slow_query"
    CACHE_MISS_SPIKE = "cache_miss_spike"
    THROUGHPUT_DROP = "throughput_drop"


@dataclass
class TraceContext:
    """Trace context for distributed tracing."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    def child_context(self) -> "TraceContext":
        """Create a child trace context."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
        )


@dataclass
class Span:
    """Individual span within a trace."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation_name: str
    span_type: SpanType
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    status_code: int | None = None

    def finish(self, error: Exception | None = None):
        """Finish the span."""
        self.end_time = datetime.utcnow()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.duration_ms = delta.total_seconds() * 1000

        if error:
            self.error = str(error)
            self.tags["error"] = True
            self.log_event(
                "error",
                {
                    "message": str(error),
                    "type": type(error).__name__,
                    "traceback": traceback.format_exc(),
                },
            )

    def log_event(self, event_type: str, fields: dict[str, Any]):
        """Log an event in the span."""
        self.logs.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event_type,
                "fields": fields,
            }
        )


@dataclass
class Trace:
    """Complete trace with all spans."""

    trace_id: str
    root_span: Span
    spans: list[Span] = field(default_factory=list)
    trace_type: TraceType = TraceType.HTTP_REQUEST
    user_id: str | None = None
    session_id: str | None = None

    @property
    def duration_ms(self) -> float:
        """Total trace duration."""
        return self.root_span.duration_ms or 0

    @property
    def has_errors(self) -> bool:
        """Check if trace has any errors."""
        return any(span.error for span in [self.root_span] + self.spans)

    @property
    def error_count(self) -> int:
        """Count of spans with errors."""
        return sum(1 for span in [self.root_span] + self.spans if span.error)


@dataclass
class PerformanceAlert:
    """Performance alert/issue."""

    alert_id: str
    issue_type: PerformanceIssueType
    severity: str  # low, medium, high, critical
    title: str
    description: str
    timestamp: datetime
    affected_components: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    resolved: bool = False
    resolved_at: datetime | None = None


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance snapshot."""

    timestamp: datetime

    # Request metrics
    total_requests: int
    requests_per_second: float
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate_percent: float

    # System metrics
    cpu_percent: float
    memory_percent: float
    disk_io_mb_per_s: float
    network_io_mb_per_s: float

    # Cache metrics
    cache_hit_rate_percent: float
    cache_miss_rate_percent: float

    # Database metrics
    avg_db_query_time_ms: float
    db_connections_active: int

    # Custom metrics
    rag_queries_per_second: float
    vector_search_avg_time_ms: float
    document_processing_queue_size: int


# ============================================================================
# APM Service
# ============================================================================


class APMService:
    """
    Comprehensive Application Performance Monitoring service.
    """

    def __init__(
        self,
        cache_telemetry: CacheTelemetryService,
        metrics_service: MetricsService,
        max_traces: int = 10000,
        trace_retention_hours: int = 24,
        sampling_rate: float = 1.0,
    ):
        """Initialize APM service."""
        self.cache_telemetry = cache_telemetry
        self.metrics_service = metrics_service
        self.max_traces = max_traces
        self.trace_retention = timedelta(hours=trace_retention_hours)
        self.sampling_rate = sampling_rate

        # Trace storage
        self.traces: deque[Trace] = deque(maxlen=max_traces)
        self.active_spans: dict[str, Span] = {}  # span_id -> Span
        self.trace_contexts: dict[str, TraceContext] = {}  # thread_id -> context

        # Performance monitoring
        self.performance_snapshots: deque[PerformanceSnapshot] = deque(
            maxlen=1440
        )  # 24h at 1min intervals
        self.alerts: list[PerformanceAlert] = []
        self.alert_rules: list[
            Callable[[PerformanceSnapshot], PerformanceAlert | None]
        ] = []

        # Real-time metrics
        self.request_latencies: deque = deque(maxlen=1000)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.throughput_window: deque = deque(maxlen=60)  # 60 seconds

        # Thread-local storage for trace contexts
        self._local = threading.local()

        # Initialize alert rules
        self._setup_default_alert_rules()

        # Start background monitoring
        self._start_background_monitoring()

        logger.info("APM service initialized")

    # ========================================================================
    # Distributed Tracing
    # ========================================================================

    def start_trace(
        self,
        operation_name: str,
        trace_type: TraceType = TraceType.HTTP_REQUEST,
        user_id: str | None = None,
        session_id: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Start a new trace."""
        # Check sampling
        if not self._should_sample():
            return TraceContext(trace_id="", span_id="")

        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        # Create root span
        root_span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            operation_name=operation_name,
            span_type=SpanType.ROOT,
            start_time=datetime.utcnow(),
            tags=tags or {},
        )

        # Create trace
        trace = Trace(
            trace_id=trace_id,
            root_span=root_span,
            trace_type=trace_type,
            user_id=user_id,
            session_id=session_id,
        )

        # Store active span
        self.active_spans[span_id] = root_span

        # Create context
        context = TraceContext(trace_id=trace_id, span_id=span_id)
        self._set_current_context(context)

        # Store trace (will be completed when root span finishes)
        self.traces.append(trace)

        return context

    def start_span(
        self,
        operation_name: str,
        span_type: SpanType = SpanType.COMPUTATION,
        parent_context: TraceContext | None = None,
        tags: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Start a new span within existing trace."""
        parent_context = parent_context or self._get_current_context()

        if not parent_context or not parent_context.trace_id:
            # No active trace, create a new one
            return self.start_trace(operation_name)

        # Create child span
        span_id = str(uuid.uuid4())
        span = Span(
            trace_id=parent_context.trace_id,
            span_id=span_id,
            parent_span_id=parent_context.span_id,
            operation_name=operation_name,
            span_type=span_type,
            start_time=datetime.utcnow(),
            tags=tags or {},
        )

        # Store active span
        self.active_spans[span_id] = span

        # Find parent trace and add span
        for trace in reversed(self.traces):
            if trace.trace_id == parent_context.trace_id:
                trace.spans.append(span)
                break

        # Create child context
        context = parent_context.child_context()
        context.span_id = span_id
        self._set_current_context(context)

        return context

    def finish_span(
        self,
        context: TraceContext | None = None,
        error: Exception | None = None,
        tags: dict[str, Any] | None = None,
    ):
        """Finish a span."""
        context = context or self._get_current_context()

        if not context or context.span_id not in self.active_spans:
            return

        span = self.active_spans[context.span_id]

        # Add tags if provided
        if tags:
            span.tags.update(tags)

        # Finish the span
        span.finish(error)

        # Record metrics
        if span.duration_ms:
            self.request_latencies.append(span.duration_ms)

            # Record in metrics service
            self.metrics_service.record_http_request(
                method=span.tags.get("http.method", "GET"),
                endpoint=span.operation_name,
                status_code=span.status_code or 200,
                duration=span.duration_ms / 1000,  # Convert to seconds
            )

        if span.error:
            error_key = (
                f"{span.operation_name}:{type(error).__name__ if error else 'unknown'}"
            )
            self.error_counts[error_key] += 1

        # Remove from active spans
        del self.active_spans[context.span_id]

        # Reset context to parent or clear
        if context.parent_span_id:
            parent_context = TraceContext(
                trace_id=context.trace_id, span_id=context.parent_span_id
            )
            self._set_current_context(parent_context)
        else:
            self._clear_current_context()

    @contextmanager
    def trace_operation(
        self,
        operation_name: str,
        span_type: SpanType = SpanType.COMPUTATION,
        tags: dict[str, Any] | None = None,
    ):
        """Context manager for tracing operations."""
        context = self.start_span(operation_name, span_type=span_type, tags=tags)
        try:
            yield context
        except Exception as e:
            self.finish_span(context, error=e)
            raise
        else:
            self.finish_span(context)

    def trace_decorator(
        self,
        operation_name: str | None = None,
        span_type: SpanType = SpanType.COMPUTATION,
        tags: dict[str, Any] | None = None,
    ):
        """Decorator for automatic tracing."""

        def decorator(func: Callable) -> Callable:
            op_name = operation_name or f"{func.__module__}.{func.__qualname__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.trace_operation(op_name, span_type=span_type, tags=tags):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    # ========================================================================
    # Performance Monitoring
    # ========================================================================

    def capture_performance_snapshot(self) -> PerformanceSnapshot:
        """Capture current performance snapshot."""
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()

        # Calculate disk I/O (simplified)
        disk_io_mb_per_s = 0  # Would need baseline for accurate calculation

        # Calculate network I/O (simplified)
        network_io_mb_per_s = 0  # Would need baseline for accurate calculation

        # Request metrics from recent traces
        recent_traces = [
            trace
            for trace in self.traces
            if trace.root_span.end_time
            and datetime.utcnow() - trace.root_span.end_time < timedelta(minutes=5)
        ]

        if recent_traces:
            durations = [
                trace.duration_ms for trace in recent_traces if trace.duration_ms
            ]
            error_traces = [trace for trace in recent_traces if trace.has_errors]

            avg_response_time = sum(durations) / len(durations) if durations else 0
            sorted_durations = sorted(durations) if durations else [0]

            p50_response_time = sorted_durations[len(sorted_durations) // 2]
            p95_response_time = sorted_durations[int(len(sorted_durations) * 0.95)]
            p99_response_time = sorted_durations[int(len(sorted_durations) * 0.99)]

            error_rate = (
                (len(error_traces) / len(recent_traces)) * 100 if recent_traces else 0
            )
            requests_per_second = (
                len(recent_traces) / 5 * 60
            )  # 5 minute window to per minute
        else:
            avg_response_time = p50_response_time = p95_response_time = (
                p99_response_time
            ) = 0
            error_rate = requests_per_second = 0

        # Cache metrics from cache telemetry service
        cache_metrics = self.cache_telemetry.get_all_layer_metrics()
        overall_hit_rate = 0
        overall_miss_rate = 0

        if cache_metrics:
            hit_rates = [m.hit_rate_percent for m in cache_metrics.values()]
            miss_rates = [m.miss_rate_percent for m in cache_metrics.values()]
            overall_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0
            overall_miss_rate = sum(miss_rates) / len(miss_rates) if miss_rates else 0

        snapshot = PerformanceSnapshot(
            timestamp=datetime.utcnow(),
            total_requests=len(recent_traces),
            requests_per_second=requests_per_second,
            avg_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate_percent=error_rate,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_io_mb_per_s=disk_io_mb_per_s,
            network_io_mb_per_s=network_io_mb_per_s,
            cache_hit_rate_percent=overall_hit_rate,
            cache_miss_rate_percent=overall_miss_rate,
            avg_db_query_time_ms=0,  # Would integrate with DB metrics
            db_connections_active=0,  # Would integrate with DB pool
            rag_queries_per_second=0,  # Would calculate from RAG traces
            vector_search_avg_time_ms=0,  # Would calculate from vector search traces
            document_processing_queue_size=0,  # Would integrate with processing queue
        )

        # Store snapshot
        self.performance_snapshots.append(snapshot)

        # Check for alerts
        self._check_performance_alerts(snapshot)

        return snapshot

    def _check_performance_alerts(self, snapshot: PerformanceSnapshot):
        """Check for performance issues and generate alerts."""
        for rule in self.alert_rules:
            alert = rule(snapshot)
            if alert:
                self.alerts.append(alert)
                logger.warning(f"Performance alert: {alert.title}")

    def _setup_default_alert_rules(self):
        """Setup default performance alert rules."""

        def high_latency_rule(snapshot: PerformanceSnapshot) -> PerformanceAlert | None:
            if snapshot.p95_response_time_ms > 2000:  # 2 seconds
                return PerformanceAlert(
                    alert_id=str(uuid.uuid4()),
                    issue_type=PerformanceIssueType.HIGH_LATENCY,
                    severity="high",
                    title="High P95 Response Time",
                    description=f"P95 response time is {snapshot.p95_response_time_ms:.1f}ms (threshold: 2000ms)",
                    timestamp=snapshot.timestamp,
                    affected_components=["api", "backend"],
                    metrics={"p95_response_time_ms": snapshot.p95_response_time_ms},
                    recommendations=[
                        "Check for slow database queries",
                        "Review cache hit rates",
                        "Analyze resource usage",
                    ],
                )
            return None

        def high_error_rate_rule(
            snapshot: PerformanceSnapshot,
        ) -> PerformanceAlert | None:
            if snapshot.error_rate_percent > 5:  # 5% error rate
                return PerformanceAlert(
                    alert_id=str(uuid.uuid4()),
                    issue_type=PerformanceIssueType.HIGH_ERROR_RATE,
                    severity="critical",
                    title="High Error Rate",
                    description=f"Error rate is {snapshot.error_rate_percent:.1f}% (threshold: 5%)",
                    timestamp=snapshot.timestamp,
                    affected_components=["api", "backend"],
                    metrics={"error_rate_percent": snapshot.error_rate_percent},
                    recommendations=[
                        "Review recent error logs",
                        "Check external service dependencies",
                        "Verify system resources",
                    ],
                )
            return None

        def high_cpu_rule(snapshot: PerformanceSnapshot) -> PerformanceAlert | None:
            if snapshot.cpu_percent > 85:  # 85% CPU usage
                return PerformanceAlert(
                    alert_id=str(uuid.uuid4()),
                    issue_type=PerformanceIssueType.CPU_SPIKE,
                    severity="medium",
                    title="High CPU Usage",
                    description=f"CPU usage is {snapshot.cpu_percent:.1f}% (threshold: 85%)",
                    timestamp=snapshot.timestamp,
                    affected_components=["system"],
                    metrics={"cpu_percent": snapshot.cpu_percent},
                    recommendations=[
                        "Identify CPU-intensive processes",
                        "Consider scaling resources",
                        "Review algorithm efficiency",
                    ],
                )
            return None

        def cache_miss_spike_rule(
            snapshot: PerformanceSnapshot,
        ) -> PerformanceAlert | None:
            if snapshot.cache_miss_rate_percent > 70:  # 70% miss rate
                return PerformanceAlert(
                    alert_id=str(uuid.uuid4()),
                    issue_type=PerformanceIssueType.CACHE_MISS_SPIKE,
                    severity="medium",
                    title="High Cache Miss Rate",
                    description=f"Cache miss rate is {snapshot.cache_miss_rate_percent:.1f}% (threshold: 70%)",
                    timestamp=snapshot.timestamp,
                    affected_components=["cache"],
                    metrics={
                        "cache_miss_rate_percent": snapshot.cache_miss_rate_percent
                    },
                    recommendations=[
                        "Review cache TTL settings",
                        "Check cache key patterns",
                        "Consider cache warming strategies",
                    ],
                )
            return None

        self.alert_rules.extend(
            [
                high_latency_rule,
                high_error_rate_rule,
                high_cpu_rule,
                cache_miss_spike_rule,
            ]
        )

    # ========================================================================
    # Background Monitoring
    # ========================================================================

    def _start_background_monitoring(self):
        """Start background monitoring thread."""

        def monitor():
            while True:
                try:
                    # Capture performance snapshot every minute
                    self.capture_performance_snapshot()

                    # Clean up old traces
                    self._cleanup_old_traces()

                    # Sleep for 1 minute
                    time.sleep(60)
                except Exception as e:
                    logger.error(f"Error in background monitoring: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        logger.info("Background monitoring thread started")

    def _cleanup_old_traces(self):
        """Clean up traces older than retention period."""
        cutoff_time = datetime.utcnow() - self.trace_retention

        # Count traces to remove
        traces_to_remove = 0
        for trace in self.traces:
            if trace.root_span.end_time and trace.root_span.end_time < cutoff_time:
                traces_to_remove += 1
            else:
                break

        # Remove old traces
        for _ in range(traces_to_remove):
            self.traces.popleft()

        if traces_to_remove > 0:
            logger.debug(f"Cleaned up {traces_to_remove} old traces")

    # ========================================================================
    # Context Management
    # ========================================================================

    def _get_current_context(self) -> TraceContext | None:
        """Get current trace context for this thread."""
        return getattr(self._local, "context", None)

    def _set_current_context(self, context: TraceContext):
        """Set current trace context for this thread."""
        self._local.context = context

    def _clear_current_context(self):
        """Clear current trace context for this thread."""
        if hasattr(self._local, "context"):
            delattr(self._local, "context")

    def _should_sample(self) -> bool:
        """Determine if trace should be sampled."""
        import random

        return random.random() < self.sampling_rate

    # ========================================================================
    # Analysis and Reporting
    # ========================================================================

    def get_slow_traces(
        self, threshold_ms: float = 1000, limit: int = 50
    ) -> list[Trace]:
        """Get slowest traces above threshold."""
        slow_traces = [
            trace
            for trace in self.traces
            if trace.duration_ms and trace.duration_ms > threshold_ms
        ]

        # Sort by duration descending
        slow_traces.sort(key=lambda t: t.duration_ms or 0, reverse=True)

        return slow_traces[:limit]

    def get_error_traces(self, limit: int = 50) -> list[Trace]:
        """Get traces with errors."""
        error_traces = [trace for trace in self.traces if trace.has_errors]

        # Sort by timestamp descending (most recent first)
        error_traces.sort(key=lambda t: t.root_span.start_time, reverse=True)

        return error_traces[:limit]

    def analyze_performance_trends(self, hours_back: int = 24) -> dict[str, Any]:
        """Analyze performance trends over time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_snapshots = [
            snapshot
            for snapshot in self.performance_snapshots
            if snapshot.timestamp >= cutoff_time
        ]

        if not recent_snapshots:
            return {"error": "No data available for analysis"}

        # Calculate trends
        response_times = [s.avg_response_time_ms for s in recent_snapshots]
        error_rates = [s.error_rate_percent for s in recent_snapshots]
        cpu_usage = [s.cpu_percent for s in recent_snapshots]
        memory_usage = [s.memory_percent for s in recent_snapshots]

        def calculate_trend(values: list[float]) -> str:
            if len(values) < 2:
                return "stable"

            recent_avg = sum(values[-5:]) / min(5, len(values))
            older_avg = sum(values[:5]) / min(5, len(values))

            change_percent = (
                ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            )

            if change_percent > 10:
                return "increasing"
            elif change_percent < -10:
                return "decreasing"
            else:
                return "stable"

        return {
            "analysis_period_hours": hours_back,
            "snapshots_analyzed": len(recent_snapshots),
            "trends": {
                "response_time": calculate_trend(response_times),
                "error_rate": calculate_trend(error_rates),
                "cpu_usage": calculate_trend(cpu_usage),
                "memory_usage": calculate_trend(memory_usage),
            },
            "averages": {
                "avg_response_time_ms": sum(response_times) / len(response_times),
                "avg_error_rate_percent": sum(error_rates) / len(error_rates),
                "avg_cpu_percent": sum(cpu_usage) / len(cpu_usage),
                "avg_memory_percent": sum(memory_usage) / len(memory_usage),
            },
            "peaks": {
                "max_response_time_ms": max(response_times) if response_times else 0,
                "max_error_rate_percent": max(error_rates) if error_rates else 0,
                "max_cpu_percent": max(cpu_usage) if cpu_usage else 0,
                "max_memory_percent": max(memory_usage) if memory_usage else 0,
            },
        }

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary."""
        recent_snapshot = (
            self.performance_snapshots[-1] if self.performance_snapshots else None
        )

        if not recent_snapshot:
            return {"error": "No performance data available"}

        # Get active alerts
        active_alerts = [alert for alert in self.alerts if not alert.resolved]

        # Get top error types
        top_errors = sorted(
            self.error_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Calculate uptime (simplified)
        uptime_hours = (
            datetime.utcnow()
            - datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).total_seconds() / 3600

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "current_performance": asdict(recent_snapshot),
            "active_alerts": [asdict(alert) for alert in active_alerts],
            "top_errors": [
                {"error": error, "count": count} for error, count in top_errors
            ],
            "system_health": {
                "uptime_hours": uptime_hours,
                "total_traces": len(self.traces),
                "active_spans": len(self.active_spans),
                "total_alerts": len(self.alerts),
            },
            "performance_trends": self.analyze_performance_trends(6),  # Last 6 hours
            "cache_integration": self.cache_telemetry.get_dashboard_data(),
        }

    # ========================================================================
    # Export and Integration
    # ========================================================================

    def export_traces(
        self,
        output_path: Path,
        format: str = "json",
        filter_func: Callable[[Trace], bool] | None = None,
    ):
        """Export traces to file."""
        traces_to_export = self.traces

        if filter_func:
            traces_to_export = [
                trace for trace in traces_to_export if filter_func(trace)
            ]

        export_data = []
        for trace in traces_to_export:
            trace_data = {
                "trace_id": trace.trace_id,
                "trace_type": trace.trace_type.value,
                "duration_ms": trace.duration_ms,
                "has_errors": trace.has_errors,
                "user_id": trace.user_id,
                "session_id": trace.session_id,
                "root_span": asdict(trace.root_span),
                "spans": [asdict(span) for span in trace.spans],
            }
            export_data.append(trace_data)

        with open(output_path, "w") as f:
            if format == "json":
                json.dump(export_data, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(export_data)} traces to {output_path}")

    def get_opentelemetry_spans(self) -> list[dict[str, Any]]:
        """Export spans in OpenTelemetry format for external tools."""
        otel_spans = []

        for trace in self.traces:
            # Root span
            otel_spans.append(self._convert_to_otel_format(trace.root_span))

            # Child spans
            for span in trace.spans:
                otel_spans.append(self._convert_to_otel_format(span))

        return otel_spans

    def _convert_to_otel_format(self, span: Span) -> dict[str, Any]:
        """Convert span to OpenTelemetry format."""
        return {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "operation_name": span.operation_name,
            "start_time": span.start_time.timestamp() * 1000000,  # microseconds
            "end_time": span.end_time.timestamp() * 1000000 if span.end_time else None,
            "duration_us": span.duration_ms * 1000 if span.duration_ms else None,
            "tags": span.tags,
            "logs": span.logs,
            "status": {"code": "ERROR" if span.error else "OK", "message": span.error},
        }


# ============================================================================
# Middleware and Decorators
# ============================================================================


class FastAPIAPMMiddleware:
    """FastAPI middleware for automatic APM integration."""

    def __init__(self, app, apm_service: APMService):
        self.app = app
        self.apm = apm_service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Start trace
        method = scope["method"]
        path = scope["path"]
        operation_name = f"{method} {path}"

        # Extract user info if available
        user_id = scope.get("user", {}).get("id") if "user" in scope else None
        session_id = scope.get("session", {}).get("id") if "session" in scope else None

        context = self.apm.start_trace(
            operation_name=operation_name,
            trace_type=TraceType.HTTP_REQUEST,
            user_id=user_id,
            session_id=session_id,
            tags={
                "http.method": method,
                "http.url": path,
                "http.scheme": scope.get("scheme"),
                "http.user_agent": next(
                    (
                        v.decode()
                        for k, v in scope.get("headers", [])
                        if k == b"user-agent"
                    ),
                    None,
                ),
            },
        )

        status_code = 200
        error = None

        # Wrap send to capture response
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            error = e
            status_code = 500
            raise
        finally:
            # Finish trace
            self.apm.finish_span(
                context, error=error, tags={"http.status_code": status_code}
            )


def apm_trace(
    operation_name: str | None = None,
    span_type: SpanType = SpanType.COMPUTATION,
    tags: dict[str, Any] | None = None,
):
    """Decorator for APM tracing."""

    def decorator(func: Callable) -> Callable:
        # Import here to avoid circular imports
        from backend.services import apm_service_instance

        return apm_service_instance.trace_decorator(
            operation_name=operation_name, span_type=span_type, tags=tags
        )(func)

    return decorator
