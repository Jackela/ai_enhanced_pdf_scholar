"""
Enhanced Metrics Collector for Production Monitoring
Collects comprehensive business and system metrics for AI Enhanced PDF Scholar.
"""

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime
from functools import wraps
from typing import Any

import psutil

from backend.services.metrics_service import MetricsService
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logger = logging.getLogger(__name__)


class EnhancedMetricsCollector:
    """
    Enhanced metrics collector with deep application insights.
    Extends the base MetricsService with business-specific monitoring.
    """

    def __init__(self, db_path: str = None, redis_url: str = None):
        """Initialize enhanced metrics collector."""
        self.db_path = db_path or os.getenv("DATABASE_URL", "data/library.db")
        self.redis_url = redis_url or os.getenv("REDIS_URL")

        # Initialize base metrics service
        self.metrics_service = MetricsService(
            app_name="ai_pdf_scholar",
            version="2.0.0",
            enable_push_gateway=bool(os.getenv("PROMETHEUS_PUSH_GATEWAY")),
            push_gateway_url=os.getenv(
                "PROMETHEUS_PUSH_GATEWAY", "http://localhost:9091"
            ),
        )

        # Get metrics reference for convenience
        self.metrics = self.metrics_service.metrics

        # Performance baseline tracking
        self.performance_baselines = {
            "rag_query_p95": 2.0,  # 95th percentile in seconds
            "document_upload_p95": 5.0,
            "cache_hit_rate_min": 0.8,
            "error_rate_max": 0.05,
        }

        # Collection intervals
        self.system_metrics_interval = 30  # seconds
        self.business_metrics_interval = 60  # seconds

        self._logged_missing_file_type_column = False

        # Start background collection
        self._start_background_collection()

        logger.info("Enhanced metrics collector initialized")

    def _start_background_collection(self):
        """Start background threads for metrics collection."""

        # System metrics collection
        def collect_system_metrics():
            while True:
                try:
                    self._collect_system_metrics()
                    self._collect_database_metrics()
                    self._collect_cache_metrics()
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {e}")
                time.sleep(self.system_metrics_interval)

        # Business metrics collection
        def collect_business_metrics():
            while True:
                try:
                    self._collect_document_metrics()
                    self._collect_user_activity_metrics()
                    self._collect_performance_metrics()
                    self._check_performance_baselines()
                except Exception as e:
                    logger.error(f"Error collecting business metrics: {e}")
                time.sleep(self.business_metrics_interval)

        # Start background threads
        import threading

        threading.Thread(target=collect_system_metrics, daemon=True).start()
        threading.Thread(target=collect_business_metrics, daemon=True).start()

    # ========================================================================
    # System Metrics Collection
    # ========================================================================

    def _collect_system_metrics(self):
        """Collect comprehensive system metrics."""
        try:
            # Process information
            process = psutil.Process()

            # Memory metrics
            memory_info = process.memory_info()
            self.metrics.memory_usage_bytes.labels(type="process_rss").set(
                memory_info.rss
            )
            self.metrics.memory_usage_bytes.labels(type="process_vms").set(
                memory_info.vms
            )

            # System memory
            sys_memory = psutil.virtual_memory()
            self.metrics.memory_usage_bytes.labels(type="system_total").set(
                sys_memory.total
            )
            self.metrics.memory_usage_bytes.labels(type="system_available").set(
                sys_memory.available
            )
            self.metrics.memory_usage_bytes.labels(type="system_used").set(
                sys_memory.used
            )

            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.cpu_usage_percent.set(cpu_percent)

            # Disk metrics
            if os.path.exists("/"):
                disk_usage = psutil.disk_usage("/")
                self.metrics.disk_usage_bytes.labels(path="/").set(disk_usage.used)
                self.metrics.disk_usage_bytes.labels(path="/").set(disk_usage.free)

            # File descriptors
            try:
                fd_count = process.num_fds()
                self.metrics.memory_usage_bytes.labels(type="file_descriptors").set(
                    fd_count
                )
            except (AttributeError, psutil.AccessDenied):
                pass  # Not available on all systems

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    def _collect_database_metrics(self):
        """Collect database-specific metrics."""
        try:
            if not os.path.exists(self.db_path):
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Document count
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            self.metrics.documents_total.set(doc_count)

            # Database file size
            db_size = os.path.getsize(self.db_path)
            self.metrics.disk_usage_bytes.labels(path="database").set(db_size)

            # Vector index count
            try:
                cursor.execute("SELECT COUNT(*) FROM vector_embeddings")
                vector_count = cursor.fetchone()[0]
                self.metrics.vector_index_size.labels(index_type="main").set(
                    vector_count
                )
            except sqlite3.OperationalError:
                pass  # Table might not exist

            # Recent activity metrics
            cursor.execute(
                """
                SELECT COUNT(*) FROM documents
                WHERE created_at > datetime('now', '-1 hour')
            """
            )
            recent_uploads = cursor.fetchone()[0]
            self.metrics.user_activity.labels(
                user_id="system", activity_type="recent_uploads"
            ).inc(recent_uploads)

            conn.close()

        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")

    def _collect_cache_metrics(self):
        """Collect cache-specific metrics."""
        try:
            if self.redis_url:
                import redis

                r = redis.from_url(self.redis_url)

                # Redis info
                info = r.info()
                self.metrics.memory_usage_bytes.labels(type="redis").set(
                    info.get("used_memory", 0)
                )
                self.metrics.cache_size_bytes.labels(cache_type="redis").set(
                    info.get("used_memory", 0)
                )

                # Connection count
                connected_clients = info.get("connected_clients", 0)
                self.metrics.db_connections_active.labels(db_type="redis").set(
                    connected_clients
                )

                # Hit/miss ratio (if available)
                keyspace_hits = info.get("keyspace_hits", 0)
                keyspace_misses = info.get("keyspace_misses", 0)
                if keyspace_hits + keyspace_misses > 0:
                    self.metrics.cache_hits_total.labels(
                        cache_type="redis", key_pattern="global"
                    )._value._value = keyspace_hits
                    self.metrics.cache_misses_total.labels(
                        cache_type="redis", key_pattern="global"
                    )._value._value = keyspace_misses

        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")

    # ========================================================================
    # Business Metrics Collection
    # ========================================================================

    def _collect_document_metrics(self):
        """Collect document processing metrics."""
        try:
            if not os.path.exists(self.db_path):
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Document size distribution
            cursor.execute(
                "SELECT file_size FROM documents WHERE file_size IS NOT NULL"
            )
            file_sizes = cursor.fetchall()

            for size_row in file_sizes:
                file_size = size_row[0]
                if file_size:
                    self.metrics.document_size_bytes.observe(file_size)

            # Document types distribution (skip if file_type column is missing)
            file_type_supported = self._table_has_column(
                cursor, "documents", "file_type"
            )
            if file_type_supported:
                cursor.execute(
                    """
                    SELECT COALESCE(file_type, 'unknown') AS file_type, COUNT(*)
                    FROM documents
                    GROUP BY file_type
                """
                )
                type_counts = cursor.fetchall()

                for file_type, count in type_counts:
                    normalized = file_type or "unknown"
                    self.metrics.document_type_total.labels(file_type=normalized).set(
                        count
                    )
            elif not self._logged_missing_file_type_column:
                logger.info(
                    "Skipping document-type metrics; 'file_type' column not found in documents table."
                )
                self._logged_missing_file_type_column = True

            # Processing status
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM documents
                WHERE created_at > datetime('now', '-24 hours')
            """
            )

            result = cursor.fetchone()
            if result:
                total, completed, failed = result
                if total > 0:
                    error_rate = failed / total if total > 0 else 0.0
                    self.metrics.error_rate.labels(component="document_processing").set(
                        error_rate * 100
                    )

            conn.close()

        except Exception as e:
            logger.error(f"Failed to collect document metrics: {e}")

    def _collect_user_activity_metrics(self):
        """Collect user activity and engagement metrics."""
        try:
            if not os.path.exists(self.db_path):
                return

            # Could track user sessions, query patterns, etc.
            # For now, just track system-level activity

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Recent queries (if query log exists)
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM rag_queries
                    WHERE created_at > datetime('now', '-1 hour')
                """
                )
                recent_queries = cursor.fetchone()[0]
                self.metrics.user_activity.labels(
                    user_id="system", activity_type="recent_queries"
                ).inc(recent_queries)
            except sqlite3.OperationalError:
                pass  # Table might not exist

            conn.close()

        except Exception as e:
            logger.error(f"Failed to collect user activity metrics: {e}")

    @staticmethod
    def _table_has_column(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
        """Return True if the given table contains the specified column."""
        try:
            cursor.execute(f"PRAGMA table_info({table})")
        except sqlite3.OperationalError:
            return False
        return any(row[1] == column for row in cursor.fetchall())

    def _collect_performance_metrics(self):
        """Collect application performance metrics."""
        try:
            # Could collect more sophisticated performance metrics
            # For now, just update health status based on system state

            # Check system health
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()

            health_score = 100

            if memory.percent > 90:
                health_score -= 30
            elif memory.percent > 80:
                health_score -= 15

            if cpu_percent > 90:
                health_score -= 30
            elif cpu_percent > 80:
                health_score -= 15

            # Update health status
            if health_score > 80:
                self.metrics_service.update_health_status("healthy")
            elif health_score > 50:
                self.metrics_service.update_health_status("degraded")
            else:
                self.metrics_service.update_health_status("unhealthy")

        except Exception as e:
            logger.error(f"Failed to collect performance metrics: {e}")

    def _check_performance_baselines(self):
        """Check if performance metrics meet baseline requirements."""
        try:
            # This would typically query recent metrics to check baselines
            # For now, just placeholder logic

            # Could implement sophisticated baseline checking here
            # Examples:
            # - Check if 95th percentile latency is within baseline
            # - Check if error rate is below threshold
            # - Check if cache hit rate is above minimum

            pass

        except Exception as e:
            logger.error(f"Failed to check performance baselines: {e}")

    # ========================================================================
    # Custom Recording Methods
    # ========================================================================

    def record_document_processing_start(self, document_id: int, operation: str):
        """Record start of document processing operation."""
        self.metrics.document_processing_duration.labels(operation=operation).observe(0)
        self.metrics.user_activity.labels(
            user_id="system", activity_type=f"processing_{operation}"
        ).inc()

    def record_document_processing_complete(
        self,
        document_id: int,
        operation: str,
        duration: float,
        success: bool,
        error_type: str = None,
    ):
        """Record completion of document processing operation."""
        self.metrics.document_processing_duration.labels(operation=operation).observe(
            duration
        )

        if not success and error_type:
            self.metrics.document_processing_errors.labels(
                operation=operation, error_type=error_type
            ).inc()

    def record_rag_query_detailed(
        self,
        query_type: str,
        query_length: int,
        document_count: int,
        chunk_count: int,
        duration: float,
        success: bool,
        relevance_score: float = None,
        response_length: int = None,
    ):
        """Record detailed RAG query metrics."""
        # Use base service method
        self.metrics_service.record_rag_query(
            query_type, duration, success, relevance_score
        )

        # Add detailed metrics
        if response_length:
            # Could add response length histogram
            pass

        # Track query complexity
        self.metrics.user_activity.labels(
            user_id="system",
            activity_type=(
                "rag_query_complex" if document_count > 1 else "rag_query_simple"
            ),
        ).inc()

    def record_security_incident(
        self, incident_type: str, severity: str, details: dict[str, Any]
    ):
        """Record security incident with detailed context."""
        self.metrics_service.record_security_event(incident_type, severity)

        # Add specific security metrics based on incident type
        if incident_type == "failed_login":
            ip_address = details.get("ip_address", "unknown")
            self.metrics.failed_login_attempts.labels(ip_address=ip_address).inc()
        elif incident_type == "rate_limit_exceeded":
            endpoint = details.get("endpoint", "unknown")
            user_id = details.get("user_id", "anonymous")
            self.metrics.rate_limit_exceeded.labels(
                endpoint=endpoint, user_id=user_id
            ).inc()

    # ========================================================================
    # Health Checking
    # ========================================================================

    async def check_comprehensive_health(self) -> dict[str, Any]:
        """Perform comprehensive health check with detailed diagnostics."""
        health_status = {
            "healthy": True,
            "checks": {},
            "metrics_summary": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # System health
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)

            health_status["checks"]["system"] = {
                "memory_percent": memory.percent,
                "cpu_percent": cpu_percent,
                "status": (
                    "healthy"
                    if memory.percent < 85 and cpu_percent < 85
                    else "degraded"
                ),
            }

            if memory.percent > 90 or cpu_percent > 90:
                health_status["healthy"] = False

        except Exception as e:
            health_status["checks"]["system"] = {"status": "unhealthy", "error": str(e)}
            health_status["healthy"] = False

        # Database health
        try:
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()

                health_status["checks"]["database"] = {"status": "healthy"}
                self.metrics_service.update_dependency_health("database", True)
            else:
                health_status["checks"]["database"] = {
                    "status": "unhealthy",
                    "error": "Database file not found",
                }
                health_status["healthy"] = False
                self.metrics_service.update_dependency_health("database", False)

        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["healthy"] = False
            self.metrics_service.update_dependency_health("database", False)

        # Cache health (Redis)
        if self.redis_url:
            try:
                import redis

                r = redis.from_url(self.redis_url, socket_timeout=5)
                r.ping()

                health_status["checks"]["redis"] = {"status": "healthy"}
                self.metrics_service.update_dependency_health("redis", True)

            except Exception as e:
                health_status["checks"]["redis"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["healthy"] = False
                self.metrics_service.update_dependency_health("redis", False)

        # Update overall health status
        if health_status["healthy"]:
            self.metrics_service.update_health_status("healthy")
        else:
            self.metrics_service.update_health_status("unhealthy")

        # Add metrics summary
        health_status["metrics_summary"] = {
            "total_documents": self._get_metric_value("documents_total"),
            "memory_usage_mb": self._get_metric_value(
                "memory_usage_bytes", "process_rss"
            )
            / (1024 * 1024),
            "cpu_usage_percent": self._get_metric_value("cpu_usage_percent"),
        }

        return health_status

    def _get_metric_value(
        self, metric_name: str, label_value: str | None = None
    ) -> float:
        """Get current value of a metric."""
        try:
            if hasattr(self.metrics, metric_name):
                metric = getattr(self.metrics, metric_name)
                if hasattr(metric, "_value"):
                    if label_value and hasattr(metric, "labels"):
                        return metric.labels(type=label_value)._value._value
                    else:
                        return metric._value._value
            return 0.0
        except Exception:
            return 0.0

    # ========================================================================
    # Metrics Export
    # ========================================================================

    def get_metrics_response(self) -> tuple[str, str]:
        """Get metrics in Prometheus format with proper content type."""
        return generate_latest(self.metrics_service.registry), CONTENT_TYPE_LATEST

    def get_dashboard_metrics(self) -> dict[str, Any]:
        """Get formatted metrics for custom dashboard."""
        return self.metrics_service.get_dashboard_data()


# ============================================================================
# Singleton Instance
# ============================================================================

# Global metrics collector instance
_metrics_collector_instance: EnhancedMetricsCollector | None = None


def get_metrics_collector() -> EnhancedMetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics_collector_instance

    if _metrics_collector_instance is None:
        _metrics_collector_instance = EnhancedMetricsCollector()

    return _metrics_collector_instance


# ============================================================================
# Decorators for Automatic Metrics Collection
# ============================================================================


def track_operation_metrics(operation_name: str, operation_type: str = "general"):
    """Decorator to automatically track operation metrics."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            collector = get_metrics_collector()

            try:
                result = await func(*args, **kwargs)

                # Record success
                collector.metrics_service.record_user_activity(
                    "system", f"{operation_type}_success"
                )

                return result

            except Exception as e:
                # Record failure
                collector.metrics_service.record_user_activity(
                    "system", f"{operation_type}_failure"
                )
                collector.record_security_incident(
                    "operation_failure",
                    "error",
                    {"operation": operation_name, "error": str(e)},
                )

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            collector = get_metrics_collector()

            try:
                result = func(*args, **kwargs)

                # Record success
                collector.metrics_service.record_user_activity(
                    "system", f"{operation_type}_success"
                )

                return result

            except Exception as e:
                # Record failure
                collector.metrics_service.record_user_activity(
                    "system", f"{operation_type}_failure"
                )
                collector.record_security_incident(
                    "operation_failure",
                    "error",
                    {"operation": operation_name, "error": str(e)},
                )

                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


if __name__ == "__main__":
    # Test the metrics collector
    collector = EnhancedMetricsCollector()

    # Simulate some operations
    collector.record_document_processing_complete(1, "upload", 1.5, True)
    collector.record_rag_query_detailed("semantic", 50, 1, 5, 0.8, True, 0.9, 200)

    print("Enhanced metrics collector test completed")
    print("Metrics available at the /metrics endpoint")
