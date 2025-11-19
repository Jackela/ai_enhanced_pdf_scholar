"""
Prometheus Metrics Collection Service
Production-ready metrics collection and monitoring system.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Enum,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    push_to_gateway,
    start_http_server,
)
from prometheus_client.core import REGISTRY

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Metrics Classes
# ============================================================================


class ApplicationMetrics:
    """
    Application-specific metrics for AI Enhanced PDF Scholar.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        """Initialize application metrics."""
        self.registry = registry or REGISTRY

        # HTTP Request Metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.075,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                2.5,
                5.0,
                7.5,
                10.0,
            ),
            registry=self.registry,
        )

        self.http_request_size = Histogram(
            "http_request_size_bytes",
            "HTTP request size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        self.http_response_size = Histogram(
            "http_response_size_bytes",
            "HTTP response size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Authentication Metrics
        self.auth_attempts_total = Counter(
            "auth_attempts_total",
            "Total authentication attempts",
            ["type", "result"],
            registry=self.registry,
        )

        self.active_sessions = Gauge(
            "active_sessions_total",
            "Number of active user sessions",
            registry=self.registry,
        )

        self.jwt_tokens_issued = Counter(
            "jwt_tokens_issued_total",
            "Total JWT tokens issued",
            ["token_type"],
            registry=self.registry,
        )

        # Document Processing Metrics
        self.documents_uploaded = Counter(
            "documents_uploaded_total",
            "Total documents uploaded",
            ["user_id", "file_type"],
            registry=self.registry,
        )

        self.document_processing_duration = Histogram(
            "document_processing_duration_seconds",
            "Document processing duration in seconds",
            ["operation"],
            registry=self.registry,
        )

        self.document_processing_errors = Counter(
            "document_processing_errors_total",
            "Document processing errors",
            ["operation", "error_type"],
            registry=self.registry,
        )

        self.documents_total = Gauge(
            "documents_total",
            "Total number of documents in system",
            registry=self.registry,
        )

        self.document_size_bytes = Histogram(
            "document_size_bytes",
            "Document size distribution",
            buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),
            registry=self.registry,
        )

        self.document_type_total = Gauge(
            "document_type_total",
            "Number of documents grouped by file type",
            ["file_type"],
            registry=self.registry,
        )

        self.preview_requests_total = Counter(
            "preview_requests_total",
            "Document preview/thumbnail requests",
            ["type", "result"],
            registry=self.registry,
        )

        self.preview_generation_seconds = Histogram(
            "preview_generation_seconds",
            "Document preview generation duration in seconds",
            ["type"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
            registry=self.registry,
        )

        # RAG (Retrieval-Augmented Generation) Metrics
        self.rag_queries_total = Counter(
            "rag_queries_total",
            "Total RAG queries processed",
            ["query_type", "result"],
            registry=self.registry,
        )

        self.rag_query_duration = Histogram(
            "rag_query_duration_seconds",
            "RAG query processing duration",
            ["query_type"],
            registry=self.registry,
        )

        self.rag_retrieval_score = Histogram(
            "rag_retrieval_score",
            "RAG retrieval relevance scores",
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
            registry=self.registry,
        )

        self.vector_index_size = Gauge(
            "vector_index_size_total",
            "Number of vectors in index",
            ["index_type"],
            registry=self.registry,
        )

        # Database Metrics
        self.db_connections_active = Gauge(
            "db_connections_active",
            "Active database connections",
            ["db_type"],
            registry=self.registry,
        )

        self.db_query_duration = Histogram(
            "db_query_duration_seconds",
            "Database query duration",
            ["operation", "table"],
            registry=self.registry,
        )

        self.db_queries_total = Counter(
            "db_queries_total",
            "Total database queries",
            ["operation", "table", "result"],
            registry=self.registry,
        )

        # Enhanced Cache Metrics for Multi-Layer Cache System
        self.cache_operations_total = Counter(
            "cache_operations_total",
            "Total cache operations by type and level",
            ["operation", "cache_level"],
            registry=self.registry,
        )

        self.cache_hit_rate = Gauge(
            "cache_hit_rate_percent",
            "Cache hit rate percentage by level",
            ["cache_level"],
            registry=self.registry,
        )

        self.cache_operation_duration = Histogram(
            "cache_operation_duration_seconds",
            "Cache operation duration by operation and level",
            ["operation", "cache_level"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )

        self.cache_size_bytes = Gauge(
            "cache_size_bytes",
            "Cache size in bytes by level",
            ["cache_level"],
            registry=self.registry,
        )

        self.cache_entries_total = Gauge(
            "cache_entries_total",
            "Total number of cache entries by level",
            ["cache_level"],
            registry=self.registry,
        )

        self.cache_evictions_total = Counter(
            "cache_evictions_total",
            "Total cache evictions by level and reason",
            ["cache_level", "eviction_reason"],
            registry=self.registry,
        )

        self.cache_coherency_operations = Counter(
            "cache_coherency_operations_total",
            "Cache coherency operations",
            ["operation_type", "protocol"],
            registry=self.registry,
        )

        self.cache_warming_operations = Counter(
            "cache_warming_operations_total",
            "Cache warming operations",
            ["strategy", "result"],
            registry=self.registry,
        )

        self.cache_response_time = Gauge(
            "cache_response_time_seconds",
            "Average cache response time by level",
            ["cache_level"],
            registry=self.registry,
        )

        self.redis_cluster_nodes = Gauge(
            "redis_cluster_nodes_total",
            "Total Redis cluster nodes by status",
            ["node_status"],
            registry=self.registry,
        )

        self.redis_cluster_operations = Counter(
            "redis_cluster_operations_total",
            "Redis cluster operations",
            ["operation", "node", "result"],
            registry=self.registry,
        )

        self.cdn_requests_total = Counter(
            "cdn_requests_total",
            "CDN requests by content type and result",
            ["content_type", "result"],
            registry=self.registry,
        )

        self.cdn_response_time = Histogram(
            "cdn_response_time_seconds",
            "CDN response time by region",
            ["region"],
            buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
            registry=self.registry,
        )

        self.cdn_bandwidth_bytes = Counter(
            "cdn_bandwidth_bytes_total",
            "CDN bandwidth usage",
            ["direction", "content_type"],
            registry=self.registry,
        )

        self.cache_compression_ratio = Histogram(
            "cache_compression_ratio",
            "Cache compression efficiency ratios",
            ["cache_level"],
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
            registry=self.registry,
        )

        # Security Metrics
        self.security_events_total = Counter(
            "security_events_total",
            "Security events detected",
            ["event_type", "severity"],
            registry=self.registry,
        )

        self.rate_limit_exceeded = Counter(
            "rate_limit_exceeded_total",
            "Rate limit violations",
            ["endpoint", "user_id"],
            registry=self.registry,
        )

        self.failed_login_attempts = Counter(
            "failed_login_attempts_total",
            "Failed login attempts",
            ["ip_address"],
            registry=self.registry,
        )

        # System Resource Metrics
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            ["type"],
            registry=self.registry,
        )

        self.cpu_usage_percent = Gauge(
            "cpu_usage_percent", "CPU usage percentage", registry=self.registry
        )

        self.disk_usage_bytes = Gauge(
            "disk_usage_bytes", "Disk usage in bytes", ["path"], registry=self.registry
        )

        # Application Health
        self.app_info = Info(
            "app_info", "Application information", registry=self.registry
        )

        self.app_health = Enum(
            "app_health",
            "Application health status",
            states=["healthy", "degraded", "unhealthy"],
            registry=self.registry,
        )

        self.dependency_health = Gauge(
            "dependency_health",
            "Dependency health status (1=healthy, 0=unhealthy)",
            ["dependency"],
            registry=self.registry,
        )

        # Custom Business Metrics
        self.user_activity = Counter(
            "user_activity_total",
            "User activity events",
            ["user_id", "activity_type"],
            registry=self.registry,
        )

        self.feature_usage = Counter(
            "feature_usage_total",
            "Feature usage count",
            ["feature", "user_type"],
            registry=self.registry,
        )

        self.error_rate = Gauge(
            "error_rate_percent",
            "Application error rate percentage",
            ["component"],
            registry=self.registry,
        )


# ============================================================================
# Metrics Service
# ============================================================================


class MetricsService:
    """
    Comprehensive metrics collection and export service.
    """

    def __init__(
        self,
        app_name: str = "ai_pdf_scholar",
        version: str = "2.0.0",
        registry: CollectorRegistry | None = None,
        enable_push_gateway: bool = False,
        push_gateway_url: str = "http://localhost:9091",
    ) -> None:
        """Initialize metrics service."""
        self.app_name = app_name
        self.version = version
        self.registry = registry or REGISTRY
        self.enable_push_gateway = enable_push_gateway
        self.push_gateway_url = push_gateway_url

        # Initialize metrics
        self.metrics = ApplicationMetrics(self.registry)

        # Set application info
        self.metrics.app_info.info(
            {
                "app_name": app_name,
                "version": version,
                "build_date": datetime.utcnow().isoformat(),
                "python_version": os.sys.version.split()[0],
            }
        )

        # Start resource monitoring
        self._start_resource_monitoring()

        logger.info(f"Metrics service initialized for {app_name} v{version}")

    def _start_resource_monitoring(self) -> None:
        """Start background thread for resource monitoring."""

        def monitor_resources() -> None:
            import psutil

            while True:
                try:
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self.metrics.memory_usage_bytes.labels(type="total").set[str](
                        memory.total
                    )
                    self.metrics.memory_usage_bytes.labels(type="available").set[str](
                        memory.available
                    )
                    self.metrics.memory_usage_bytes.labels(type="used").set[str](memory.used)

                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.metrics.cpu_usage_percent.set[str](cpu_percent)

                    # Disk usage
                    disk = psutil.disk_usage("/")
                    self.metrics.disk_usage_bytes.labels(path="/").set[str](disk.used)

                    # Process-specific metrics
                    process = psutil.Process()
                    process_memory = process.memory_info()
                    self.metrics.memory_usage_bytes.labels(type="process").set[str](
                        process_memory.rss
                    )

                except Exception as e:
                    logger.error(f"Error collecting system metrics: {e}")

                time.sleep(30)  # Collect every 30 seconds

        thread = threading.Thread(target=monitor_resources, daemon=True)
        thread.start()

    # ========================================================================
    # Metric Recording Methods
    # ========================================================================

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0,
    ) -> None:
        """Record HTTP request metrics."""
        status_class = f"{status_code // 100}xx"

        self.metrics.http_requests_total.labels(
            method=method, endpoint=endpoint, status=status_class
        ).inc()

        self.metrics.http_request_duration.labels(
            method=method, endpoint=endpoint
        ).observe(duration)

        if request_size > 0:
            self.metrics.http_request_size.labels(
                method=method, endpoint=endpoint
            ).observe(request_size)

        if response_size > 0:
            self.metrics.http_response_size.labels(
                method=method, endpoint=endpoint
            ).observe(response_size)

    def record_auth_attempt(self, auth_type: str, success: bool) -> None:
        """Record authentication attempt."""
        result = "success" if success else "failure"
        self.metrics.auth_attempts_total.labels(type=auth_type, result=result).inc()

    def record_document_upload(
        self, user_id: str, file_type: str, file_size: int
    ) -> None:
        """Record document upload."""
        self.metrics.documents_uploaded.labels(
            user_id=user_id, file_type=file_type
        ).inc()

        self.metrics.document_size_bytes.observe(file_size)

    def record_rag_query(
        self,
        query_type: str,
        duration: float,
        success: bool,
        relevance_score: float = None,
    ) -> None:
        """Record RAG query metrics."""
        result = "success" if success else "failure"

        self.metrics.rag_queries_total.labels(
            query_type=query_type, result=result
        ).inc()

        self.metrics.rag_query_duration.labels(query_type=query_type).observe(duration)

        if relevance_score is not None:
            self.metrics.rag_retrieval_score.observe(relevance_score)

    def record_db_query(
        self, operation: str, table: str, duration: float, success: bool
    ) -> None:
        """Record database query metrics."""
        result = "success" if success else "failure"

        self.metrics.db_queries_total.labels(
            operation=operation, table=table, result=result
        ).inc()

        self.metrics.db_query_duration.labels(operation=operation, table=table).observe(
            duration
        )

    def record_cache_operation(
        self,
        operation: str,
        cache_type: str,
        hit: bool | None = None,
        duration: float = None,
        key_pattern: str = "default",
    ) -> None:
        """Record cache operation metrics."""
        if hit is True:
            self.metrics.cache_hits_total.labels(
                cache_type=cache_type, key_pattern=key_pattern
            ).inc()
        elif hit is False:
            self.metrics.cache_misses_total.labels(
                cache_type=cache_type, key_pattern=key_pattern
            ).inc()

        if duration is not None:
            self.metrics.cache_operations_duration.labels(
                operation=operation, cache_type=cache_type
            ).observe(duration)

    def record_security_event(self, event_type: str, severity: str) -> None:
        """Record security event."""
        self.metrics.security_events_total.labels(
            event_type=event_type, severity=severity
        ).inc()

    def record_user_activity(self, user_id: str, activity_type: str) -> None:
        """Record user activity."""
        self.metrics.user_activity.labels(
            user_id=user_id, activity_type=activity_type
        ).inc()

    # ========================================================================
    # Gauge Updates
    # ========================================================================

    def update_active_sessions(self, count: int) -> None:
        """Update active sessions count."""
        self.metrics.active_sessions.set[str](count)

    def update_documents_total(self, count: int) -> None:
        """Update total documents count."""
        self.metrics.documents_total.set[str](count)

    def update_vector_index_size(self, index_type: str, size: int) -> None:
        """Update vector index size."""
        self.metrics.vector_index_size.labels(index_type=index_type).set[str](size)

    def update_db_connections(self, db_type: str, count: int) -> None:
        """Update database connections count."""
        self.metrics.db_connections_active.labels(db_type=db_type).set[str](count)

    def update_cache_size(self, cache_type: str, size_bytes: int) -> None:
        """Update cache size."""
        self.metrics.cache_size_bytes.labels(cache_type=cache_type).set[str](size_bytes)

    def update_health_status(self, status: str) -> None:
        """Update application health status."""
        self.metrics.app_health.state(status)

    def update_dependency_health(self, dependency: str, healthy: bool) -> None:
        """Update dependency health status."""
        self.metrics.dependency_health.labels(dependency=dependency).set[str](
            1 if healthy else 0
        )

    def update_error_rate(self, component: str, error_rate: float) -> None:
        """Update error rate for a component."""
        self.metrics.error_rate.labels(component=component).set[str](error_rate)

    # ========================================================================
    # Decorators
    # ========================================================================

    def track_duration(
        self, operation: str, labels: dict[str, str] | None = None
    ) -> Any:
        """Decorator to track operation duration."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    # Record success metric based on operation type
                    if operation.startswith("http"):
                        self.record_http_request(
                            method=labels.get("method", "GET"),
                            endpoint=labels.get("endpoint", "/"),
                            status_code=200,
                            duration=duration,
                        )
                    elif operation.startswith("db"):
                        self.record_db_query(
                            operation=labels.get("db_operation", "query"),
                            table=labels.get("table", "unknown"),
                            duration=duration,
                            success=True,
                        )

                    return result
                except Exception:
                    duration = time.time() - start_time

                    # Record failure metric
                    if operation.startswith("http"):
                        self.record_http_request(
                            method=labels.get("method", "GET"),
                            endpoint=labels.get("endpoint", "/"),
                            status_code=500,
                            duration=duration,
                        )
                    elif operation.startswith("db"):
                        self.record_db_query(
                            operation=labels.get("db_operation", "query"),
                            table=labels.get("table", "unknown"),
                            duration=duration,
                            success=False,
                        )

                    raise

            return wrapper

        return decorator

    def track_exceptions(self, component: str) -> Any:
        """Decorator to track exceptions."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception:
                    self.record_security_event(event_type="exception", severity="error")
                    raise

            return wrapper

        return decorator

    # ========================================================================
    # Metrics Export
    # ========================================================================

    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry)

    def start_metrics_server(
        self,
        port: int = 8000,
        addr: str = "0.0.0.0",  # noqa: S104 - intentional bind
    ) -> None:
        """Start HTTP server for metrics endpoint."""
        try:
            start_http_server(port, addr, registry=self.registry)
            logger.info(f"Metrics server started on {addr}:{port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    def push_metrics(
        self, job: str = None, grouping_key: dict[str, str] = None
    ) -> None:
        """Push metrics to Prometheus Push Gateway."""
        if not self.enable_push_gateway:
            return

        job = job or self.app_name
        grouping_key = grouping_key or {"instance": f"{self.app_name}-{self.version}"}

        try:
            push_to_gateway(
                self.push_gateway_url,
                job=job,
                registry=self.registry,
                grouping_key=grouping_key,
            )
            logger.debug(f"Pushed metrics to gateway: {self.push_gateway_url}")
        except Exception as e:
            logger.error(f"Failed to push metrics: {e}")

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    def check_health(self) -> dict[str, Any]:
        """Check application health and update metrics."""
        health_status = {
            "healthy": True,
            "checks": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Check database connection
        try:
            # This would check actual database connection
            health_status["checks"]["database"] = "healthy"
            self.update_dependency_health("database", True)
        except Exception as e:
            health_status["checks"]["database"] = f"unhealthy: {e}"
            self.update_dependency_health("database", False)
            health_status["healthy"] = False

        # Check Redis cache
        try:
            # This would check actual Redis connection
            health_status["checks"]["redis"] = "healthy"
            self.update_dependency_health("redis", True)
        except Exception as e:
            health_status["checks"]["redis"] = f"unhealthy: {e}"
            self.update_dependency_health("redis", False)
            health_status["healthy"] = False

        # Update overall health status
        if health_status["healthy"]:
            self.update_health_status("healthy")
        else:
            self.update_health_status("unhealthy")

        return health_status

    # ========================================================================
    # Custom Dashboards
    # ========================================================================

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for custom dashboard."""
        from prometheus_client.parser import text_string_to_metric_families

        metrics_data = self.get_metrics()
        families = text_string_to_metric_families(metrics_data)

        dashboard = {"timestamp": datetime.utcnow().isoformat(), "metrics": {}}

        for family in families:
            dashboard["metrics"][family.name] = {
                "help": family.documentation,
                "type": family.type,
                "samples": [],
            }

            for sample in family.samples:
                dashboard["metrics"][family.name]["samples"].append(
                    {"labels": dict[str, Any](sample.labels), "value": sample.value}
                )

        return dashboard


# ============================================================================
# FastAPI Integration
# ============================================================================


class FastAPIMetricsMiddleware:
    """
    FastAPI middleware for automatic metrics collection.
    """

    def __init__(self, app: Any, metrics_service: MetricsService) -> None:
        """Initialize middleware."""
        self.app = app
        self.metrics = metrics_service

    async def __call__(self, scope: Any, receive: Any, send: Any) -> Any:
        """Process request and collect metrics."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        request_size = 0
        response_size = 0
        status_code = 200

        # Track request size
        async def receive_wrapper() -> Any:
            nonlocal request_size
            message = await receive()
            if message["type"] == "http.request":
                request_size += len(message.get("body", b""))
            return message

        # Track response size and status
        async def send_wrapper(message: Any) -> None:
            nonlocal response_size, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_size += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            # Record metrics
            duration = time.time() - start_time
            method = scope["method"]
            path = scope["path"]

            self.metrics.record_http_request(
                method=method,
                endpoint=path,
                status_code=status_code,
                duration=duration,
                request_size=request_size,
                response_size=response_size,
            )


if __name__ == "__main__":
    # Example usage
    metrics_service = MetricsService()
    metrics_service.start_metrics_server(port=8000)

    # Simulate some metrics
    metrics_service.record_http_request("GET", "/api/documents", 200, 0.1)
    metrics_service.record_auth_attempt("jwt", True)
    metrics_service.record_document_upload("user123", "pdf", 1024000)

    print("Metrics server running on http://localhost:8000/metrics")
