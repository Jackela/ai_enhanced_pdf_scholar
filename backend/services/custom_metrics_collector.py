"""
Custom Metrics Collector Service
=================================

Business-aware scaling metrics collection for AI PDF Scholar application.
Provides detailed metrics that enable intelligent auto-scaling decisions
beyond basic CPU/memory utilization.

Features:
- RAG-specific performance metrics
- Document processing queue metrics
- User activity and request patterns
- Quality and error rate metrics
- Cost-aware resource utilization
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from datetime import datetime

import psutil
from sqlalchemy import text

from backend.core.secrets import SecretsManager
from backend.database.postgresql_config import get_async_session
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    start_http_server,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BusinessMetric:
    """Business-specific metric data"""

    name: str
    value: float
    labels: dict[str, str]
    timestamp: datetime
    description: str


class CustomMetricsCollector:
    """Collect custom business and application metrics for scaling decisions"""

    def __init__(self, registry: CollectorRegistry | None = None):
        self.registry = registry or CollectorRegistry()
        self.secrets_manager = SecretsManager()

        # Initialize Prometheus metrics
        self._init_prometheus_metrics()

        # Tracking variables
        self.request_times = []
        self.rag_query_times = []
        self.document_processing_queue = []
        self.error_counts = {"last_hour": 0, "last_day": 0}
        self.user_sessions = {}
        self.cache_stats = {"hits": 0, "misses": 0, "total": 0}

        # Configuration
        self.collection_interval = 15  # seconds
        self.metric_retention_hours = 24

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""

        # Request and Response Metrics
        self.http_requests_per_second = Gauge(
            "http_requests_per_second",
            "Current HTTP requests per second",
            registry=self.registry,
        )

        self.http_request_duration_p95_seconds = Gauge(
            "http_request_duration_p95_seconds",
            "95th percentile HTTP request duration in seconds",
            registry=self.registry,
        )

        self.http_request_duration_p50_seconds = Gauge(
            "http_request_duration_p50_seconds",
            "50th percentile HTTP request duration in seconds",
            registry=self.registry,
        )

        # RAG-specific metrics
        self.rag_queries_per_second = Gauge(
            "rag_queries_per_second",
            "Current RAG queries per second",
            registry=self.registry,
        )

        self.rag_query_duration_p95_seconds = Gauge(
            "rag_query_duration_p95_seconds",
            "95th percentile RAG query duration in seconds",
            registry=self.registry,
        )

        self.rag_index_size_mb = Gauge(
            "rag_index_size_mb",
            "Current RAG index size in megabytes",
            registry=self.registry,
        )

        self.rag_cache_hit_rate = Gauge(
            "rag_cache_hit_rate", "RAG cache hit rate (0-1)", registry=self.registry
        )

        # Document processing metrics
        self.document_processing_queue_depth = Gauge(
            "document_processing_queue_depth",
            "Current document processing queue depth",
            registry=self.registry,
        )

        self.document_processing_rate_per_minute = Gauge(
            "document_processing_rate_per_minute",
            "Documents processed per minute",
            registry=self.registry,
        )

        self.document_processing_errors_rate = Gauge(
            "document_processing_errors_rate",
            "Document processing errors per minute",
            registry=self.registry,
        )

        # User activity metrics
        self.active_user_sessions = Gauge(
            "active_user_sessions",
            "Number of active user sessions",
            registry=self.registry,
        )

        self.concurrent_users = Gauge(
            "concurrent_users", "Number of concurrent users", registry=self.registry
        )

        self.user_activity_score = Gauge(
            "user_activity_score",
            "Weighted user activity score (higher = more active)",
            registry=self.registry,
        )

        # Resource efficiency metrics
        self.memory_efficiency_ratio = Gauge(
            "memory_efficiency_ratio",
            "Memory efficiency ratio (requests per GB of memory)",
            registry=self.registry,
        )

        self.cpu_efficiency_ratio = Gauge(
            "cpu_efficiency_ratio",
            "CPU efficiency ratio (requests per CPU core)",
            registry=self.registry,
        )

        self.cost_per_request = Gauge(
            "cost_per_request",
            "Estimated cost per request in USD",
            registry=self.registry,
        )

        # Quality metrics
        self.service_quality_score = Gauge(
            "service_quality_score",
            "Overall service quality score (0-1, higher is better)",
            registry=self.registry,
        )

        self.rag_answer_quality_score = Gauge(
            "rag_answer_quality_score",
            "RAG answer quality score (0-1)",
            registry=self.registry,
        )

        # Error and reliability metrics
        self.error_rate_5xx = Gauge(
            "error_rate_5xx", "Rate of 5xx errors per minute", registry=self.registry
        )

        self.error_rate_4xx = Gauge(
            "error_rate_4xx", "Rate of 4xx errors per minute", registry=self.registry
        )

        self.service_availability_ratio = Gauge(
            "service_availability_ratio",
            "Service availability ratio (0-1)",
            registry=self.registry,
        )

        # Business metrics
        self.business_value_score = Gauge(
            "business_value_score",
            "Business value score based on user engagement",
            registry=self.registry,
        )

        self.peak_hour_indicator = Gauge(
            "peak_hour_indicator",
            "Indicates if currently in peak hours (0 or 1)",
            registry=self.registry,
        )

        # Scaling prediction inputs
        self.scaling_prediction_confidence = Gauge(
            "scaling_prediction_confidence",
            "ML model confidence for scaling predictions (0-1)",
            registry=self.registry,
        )

        self.predicted_load_next_15min = Gauge(
            "predicted_load_next_15min",
            "Predicted request load for next 15 minutes",
            registry=self.registry,
        )

    async def collect_database_metrics(self) -> dict[str, float]:
        """Collect database-related metrics"""
        metrics = {}

        try:
            async with get_async_session() as session:
                # Document count and growth
                result = await session.execute(text("SELECT COUNT(*) FROM documents"))
                document_count = result.scalar() or 0
                metrics["total_documents"] = float(document_count)

                # Recent document uploads (last 24 hours)
                result = await session.execute(
                    text("""
                    SELECT COUNT(*) FROM documents
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
                )
                recent_documents = result.scalar() or 0
                metrics["documents_uploaded_24h"] = float(recent_documents)

                # Average document size
                result = await session.execute(
                    text("""
                    SELECT AVG(LENGTH(content)) FROM documents WHERE content IS NOT NULL
                """)
                )
                avg_doc_size = result.scalar() or 0
                metrics["average_document_size_chars"] = float(avg_doc_size)

                # RAG queries in last hour
                result = await session.execute(
                    text("""
                    SELECT COUNT(*) FROM rag_queries
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)
                )
                rag_queries_1h = result.scalar() or 0
                metrics["rag_queries_last_hour"] = float(rag_queries_1h)

                # Database connection count
                result = await session.execute(
                    text("""
                    SELECT count(*) FROM pg_stat_activity
                    WHERE state = 'active'
                """)
                )
                active_connections = result.scalar() or 0
                metrics["db_active_connections"] = float(active_connections)

                # Database size
                result = await session.execute(
                    text("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                )
                db_size_str = result.scalar() or "0 MB"
                # Extract numeric value (simplified parsing)
                try:
                    if "GB" in db_size_str:
                        db_size_mb = float(db_size_str.split()[0]) * 1024
                    elif "MB" in db_size_str:
                        db_size_mb = float(db_size_str.split()[0])
                    else:
                        db_size_mb = 0
                    metrics["database_size_mb"] = db_size_mb
                except:
                    metrics["database_size_mb"] = 0

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            # Return default values for essential metrics
            for metric in [
                "total_documents",
                "documents_uploaded_24h",
                "rag_queries_last_hour",
            ]:
                metrics[metric] = 0.0

        return metrics

    async def collect_system_metrics(self) -> dict[str, float]:
        """Collect system resource metrics"""
        metrics = {}

        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            metrics["cpu_usage_percent"] = cpu_percent
            metrics["cpu_count"] = float(cpu_count)

            # Memory metrics
            memory = psutil.virtual_memory()
            metrics["memory_usage_percent"] = memory.percent
            metrics["memory_total_gb"] = memory.total / (1024**3)
            metrics["memory_available_gb"] = memory.available / (1024**3)

            # Disk metrics
            disk = psutil.disk_usage("/")
            metrics["disk_usage_percent"] = (disk.used / disk.total) * 100
            metrics["disk_total_gb"] = disk.total / (1024**3)

            # Network metrics (simplified)
            network = psutil.net_io_counters()
            metrics["network_bytes_sent"] = float(network.bytes_sent)
            metrics["network_bytes_recv"] = float(network.bytes_recv)

            # Process metrics
            process_count = len(psutil.pids())
            metrics["process_count"] = float(process_count)

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            # Return default values
            metrics = {
                "cpu_usage_percent": 0.0,
                "memory_usage_percent": 0.0,
                "memory_total_gb": 8.0,  # Default assumption
                "memory_available_gb": 4.0,
            }

        return metrics

    async def collect_application_metrics(self) -> dict[str, float]:
        """Collect application-specific metrics"""
        metrics = {}

        try:
            # Request rate calculation
            current_time = time.time()
            recent_requests = [t for t in self.request_times if current_time - t < 60]
            metrics["requests_per_minute"] = float(len(recent_requests))
            metrics["requests_per_second"] = float(len(recent_requests) / 60.0)

            # Response time percentiles
            if self.request_times:
                recent_durations = [
                    d for d in self.request_times if current_time - d < 300
                ]  # Last 5 minutes
                if recent_durations:
                    metrics["response_time_p50_ms"] = (
                        statistics.median(recent_durations) * 1000
                    )
                    metrics["response_time_p95_ms"] = (
                        statistics.quantiles(recent_durations, n=20)[18] * 1000
                    )  # 95th percentile
                    metrics["response_time_avg_ms"] = (
                        statistics.mean(recent_durations) * 1000
                    )
                else:
                    metrics["response_time_p50_ms"] = 0.0
                    metrics["response_time_p95_ms"] = 0.0
                    metrics["response_time_avg_ms"] = 0.0
            else:
                metrics["response_time_p50_ms"] = 0.0
                metrics["response_time_p95_ms"] = 0.0
                metrics["response_time_avg_ms"] = 0.0

            # RAG query metrics
            recent_rag_queries = [
                t for t in self.rag_query_times if current_time - t < 60
            ]
            metrics["rag_queries_per_minute"] = float(len(recent_rag_queries))

            if self.rag_query_times:
                recent_rag_durations = [
                    d for d in self.rag_query_times if current_time - d < 300
                ]
                if recent_rag_durations:
                    metrics["rag_response_time_p95_ms"] = (
                        statistics.quantiles(recent_rag_durations, n=20)[18] * 1000
                    )
                else:
                    metrics["rag_response_time_p95_ms"] = 0.0
            else:
                metrics["rag_response_time_p95_ms"] = 0.0

            # Queue depth
            metrics["processing_queue_depth"] = float(
                len(self.document_processing_queue)
            )

            # Error rates
            metrics["error_rate_per_minute"] = float(
                self.error_counts["last_hour"] / 60.0
            )

            # Cache hit rate
            if self.cache_stats["total"] > 0:
                metrics["cache_hit_rate"] = (
                    self.cache_stats["hits"] / self.cache_stats["total"]
                )
            else:
                metrics["cache_hit_rate"] = 0.0

            # User activity
            active_sessions = len(
                [
                    s
                    for s in self.user_sessions.values()
                    if current_time - s["last_activity"] < 300
                ]
            )  # 5 minutes
            metrics["active_user_sessions"] = float(active_sessions)

            # Peak hour detection (simplified business logic)
            current_hour = datetime.now().hour
            is_peak = 1.0 if 9 <= current_hour <= 17 else 0.0  # Business hours
            metrics["peak_hour_indicator"] = is_peak

        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            # Return default values
            metrics = {
                "requests_per_second": 0.0,
                "response_time_p95_ms": 100.0,
                "rag_queries_per_minute": 0.0,
                "processing_queue_depth": 0.0,
            }

        return metrics

    async def calculate_efficiency_metrics(
        self, system_metrics: dict[str, float], app_metrics: dict[str, float]
    ) -> dict[str, float]:
        """Calculate efficiency and quality metrics"""
        metrics = {}

        try:
            # Memory efficiency (requests per GB of memory used)
            memory_used_gb = (
                system_metrics["memory_total_gb"]
                - system_metrics["memory_available_gb"]
            )
            if memory_used_gb > 0 and app_metrics["requests_per_second"] > 0:
                metrics["memory_efficiency_ratio"] = (
                    app_metrics["requests_per_second"] / memory_used_gb
                )
            else:
                metrics["memory_efficiency_ratio"] = 0.0

            # CPU efficiency (requests per CPU core)
            if (
                system_metrics["cpu_count"] > 0
                and app_metrics["requests_per_second"] > 0
            ):
                metrics["cpu_efficiency_ratio"] = (
                    app_metrics["requests_per_second"] / system_metrics["cpu_count"]
                )
            else:
                metrics["cpu_efficiency_ratio"] = 0.0

            # Cost estimation (simplified)
            cpu_cost_per_hour = system_metrics["cpu_count"] * 0.05  # $0.05 per CPU hour
            memory_cost_per_hour = (
                system_metrics["memory_total_gb"] * 0.01
            )  # $0.01 per GB hour
            total_cost_per_hour = cpu_cost_per_hour + memory_cost_per_hour

            if app_metrics["requests_per_second"] > 0:
                requests_per_hour = app_metrics["requests_per_second"] * 3600
                metrics["cost_per_request"] = total_cost_per_hour / requests_per_hour
            else:
                metrics["cost_per_request"] = 0.1  # Default cost per request

            # Service quality score (0-1, higher is better)
            quality_factors = []

            # Response time factor (lower is better)
            if app_metrics["response_time_p95_ms"] > 0:
                response_time_factor = max(
                    0, 1 - (app_metrics["response_time_p95_ms"] / 1000)
                )  # Normalized to 1 second
                quality_factors.append(response_time_factor)

            # Error rate factor (lower is better)
            error_rate_factor = max(
                0, 1 - (app_metrics["error_rate_per_minute"] / 10)
            )  # Normalized to 10 errors/minute
            quality_factors.append(error_rate_factor)

            # Cache hit rate factor
            quality_factors.append(app_metrics["cache_hit_rate"])

            # Resource utilization factor (around 70% is optimal)
            cpu_util_factor = 1 - abs(system_metrics["cpu_usage_percent"] - 70) / 100
            memory_util_factor = (
                1 - abs(system_metrics["memory_usage_percent"] - 70) / 100
            )
            quality_factors.extend([cpu_util_factor, memory_util_factor])

            if quality_factors:
                metrics["service_quality_score"] = statistics.mean(quality_factors)
            else:
                metrics["service_quality_score"] = 0.5

            # Business value score (simplified)
            user_activity_weight = min(
                1.0, app_metrics["active_user_sessions"] / 10
            )  # Normalized to 10 users
            request_volume_weight = min(
                1.0, app_metrics["requests_per_second"] / 100
            )  # Normalized to 100 RPS
            peak_hour_weight = app_metrics["peak_hour_indicator"]

            metrics["business_value_score"] = (
                user_activity_weight * 0.4
                + request_volume_weight * 0.4
                + peak_hour_weight * 0.2
            )

        except Exception as e:
            logger.error(f"Error calculating efficiency metrics: {e}")
            # Return default values
            metrics = {
                "memory_efficiency_ratio": 1.0,
                "cpu_efficiency_ratio": 1.0,
                "cost_per_request": 0.01,
                "service_quality_score": 0.5,
                "business_value_score": 0.5,
            }

        return metrics

    async def update_prometheus_metrics(self, all_metrics: dict[str, float]):
        """Update Prometheus metrics with collected values"""
        try:
            # Update all Prometheus gauges
            metric_mappings = {
                "requests_per_second": self.http_requests_per_second,
                "response_time_p95_ms": lambda x: self.http_request_duration_p95_seconds.set(
                    x / 1000
                ),
                "response_time_p50_ms": lambda x: self.http_request_duration_p50_seconds.set(
                    x / 1000
                ),
                "rag_queries_per_minute": lambda x: self.rag_queries_per_second.set(
                    x / 60
                ),
                "rag_response_time_p95_ms": lambda x: self.rag_query_duration_p95_seconds.set(
                    x / 1000
                ),
                "processing_queue_depth": self.document_processing_queue_depth,
                "documents_uploaded_24h": lambda x: self.document_processing_rate_per_minute.set(
                    x / (24 * 60)
                ),
                "active_user_sessions": self.active_user_sessions,
                "memory_efficiency_ratio": self.memory_efficiency_ratio,
                "cpu_efficiency_ratio": self.cpu_efficiency_ratio,
                "cost_per_request": self.cost_per_request,
                "service_quality_score": self.service_quality_score,
                "cache_hit_rate": self.rag_cache_hit_rate,
                "error_rate_per_minute": self.error_rate_5xx,
                "business_value_score": self.business_value_score,
                "peak_hour_indicator": self.peak_hour_indicator,
                "database_size_mb": lambda x: self.rag_index_size_mb.set(x),
            }

            for metric_name, prometheus_metric in metric_mappings.items():
                if metric_name in all_metrics:
                    try:
                        if callable(prometheus_metric):
                            prometheus_metric(all_metrics[metric_name])
                        else:
                            prometheus_metric.set(all_metrics[metric_name])
                    except Exception as e:
                        logger.warning(
                            f"Error updating Prometheus metric {metric_name}: {e}"
                        )

            # Set some default values for scaling prediction
            self.scaling_prediction_confidence.set(
                0.8
            )  # This would be set by the ML predictor
            self.predicted_load_next_15min.set(
                all_metrics.get("requests_per_second", 0) * 1.2
            )  # Simple prediction

        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")

    async def collect_all_metrics(self) -> dict[str, float]:
        """Collect all metrics and return combined dictionary"""
        try:
            # Collect metrics from different sources
            db_metrics = await self.collect_database_metrics()
            system_metrics = await self.collect_system_metrics()
            app_metrics = await self.collect_application_metrics()
            efficiency_metrics = await self.calculate_efficiency_metrics(
                system_metrics, app_metrics
            )

            # Combine all metrics
            all_metrics = {
                **db_metrics,
                **system_metrics,
                **app_metrics,
                **efficiency_metrics,
            }

            # Update Prometheus metrics
            await self.update_prometheus_metrics(all_metrics)

            return all_metrics

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {}

    def record_request(self, duration: float):
        """Record a request for metrics calculation"""
        current_time = time.time()
        self.request_times.append(current_time)

        # Keep only recent requests (last hour)
        cutoff_time = current_time - 3600
        self.request_times = [t for t in self.request_times if t > cutoff_time]

    def record_rag_query(self, duration: float):
        """Record a RAG query for metrics calculation"""
        current_time = time.time()
        self.rag_query_times.append(current_time)

        # Keep only recent queries (last hour)
        cutoff_time = current_time - 3600
        self.rag_query_times = [t for t in self.rag_query_times if t > cutoff_time]

    def record_error(self):
        """Record an error for metrics calculation"""
        self.error_counts["last_hour"] += 1

    def record_cache_hit(self, hit: bool):
        """Record cache hit/miss for metrics calculation"""
        self.cache_stats["total"] += 1
        if hit:
            self.cache_stats["hits"] += 1
        else:
            self.cache_stats["misses"] += 1

    def update_user_activity(self, user_id: str):
        """Update user activity for metrics calculation"""
        self.user_sessions[user_id] = {"last_activity": time.time()}

    async def run_continuous_collection(self):
        """Run continuous metrics collection"""
        logger.info("Starting continuous metrics collection...")

        while True:
            try:
                metrics = await self.collect_all_metrics()
                logger.debug(f"Collected {len(metrics)} metrics")

                # Wait for next collection interval
                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds before retrying

    def start_metrics_server(self, port: int = 8000):
        """Start Prometheus metrics HTTP server"""
        try:
            start_http_server(port, registry=self.registry)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Error starting metrics server: {e}")


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> CustomMetricsCollector:
    """Get or create the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = CustomMetricsCollector()
    return _metrics_collector


# Convenience functions for the FastAPI app
async def record_request_metric(duration: float):
    """Record a request metric"""
    collector = get_metrics_collector()
    collector.record_request(duration)


async def record_rag_query_metric(duration: float):
    """Record a RAG query metric"""
    collector = get_metrics_collector()
    collector.record_rag_query(duration)


async def record_error_metric():
    """Record an error metric"""
    collector = get_metrics_collector()
    collector.record_error()


async def record_cache_metric(hit: bool):
    """Record a cache hit/miss metric"""
    collector = get_metrics_collector()
    collector.record_cache_hit(hit)


async def update_user_activity_metric(user_id: str):
    """Update user activity metric"""
    collector = get_metrics_collector()
    collector.update_user_activity(user_id)


# CLI interface
async def main():
    """Main entry point for the metrics collector"""
    import argparse

    parser = argparse.ArgumentParser(description="Custom Metrics Collector")
    parser.add_argument("--port", type=int, default=8000, help="Metrics server port")
    parser.add_argument(
        "--interval", type=int, default=15, help="Collection interval in seconds"
    )

    args = parser.parse_args()

    collector = CustomMetricsCollector()
    collector.collection_interval = args.interval

    # Start metrics HTTP server
    collector.start_metrics_server(args.port)

    # Run continuous collection
    await collector.run_continuous_collection()


if __name__ == "__main__":
    asyncio.run(main())
