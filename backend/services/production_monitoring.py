"""
Production Monitoring and Alerting Integration
Comprehensive integration with Agent A2's monitoring system, providing
production-ready metrics collection, alerting, and health monitoring.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import psutil

from ..config.production import ProductionConfig
from ..config.redis_cluster import RedisClusterManager
from ..config.secrets_integration import ProductionSecretsIntegration
from ..database.production_config import ProductionDatabaseManager
from .alert_service import AlertingService
from .metrics_service import MetricsService

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class SystemMetrics:
    """System resource metrics."""

    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_available_gb: float
    network_bytes_sent: int
    network_bytes_received: int
    load_average_1m: float | None = None
    load_average_5m: float | None = None
    load_average_15m: float | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ApplicationMetrics:
    """Application-specific metrics."""

    active_connections: int
    request_rate: float
    error_rate: float
    response_time_p95: float
    database_connections: int
    redis_connections: int
    cache_hit_rate: float
    queue_size: int = 0
    worker_count: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class HealthCheck:
    """Health check definition."""

    name: str
    description: str
    check_function: Callable
    interval_seconds: int
    timeout_seconds: int
    critical: bool = False
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Health check execution result."""

    name: str
    status: HealthStatus
    message: str
    duration_seconds: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ProductionMonitoringService:
    """
    Production monitoring service that integrates with Agent A2's monitoring
    infrastructure to provide comprehensive application and system monitoring.
    """

    def __init__(
        self,
        production_config: ProductionConfig | None = None,
        metrics_service: MetricsService | None = None,
        alerting_service: AlertingService | None = None,
        secrets_integration: ProductionSecretsIntegration | None = None,
        database_manager: ProductionDatabaseManager | None = None,
        redis_manager: RedisClusterManager | None = None,
    ) -> None:
        """Initialize production monitoring service."""
        self.production_config = production_config
        self.metrics_service = metrics_service or MetricsService()
        self.alerting_service = alerting_service or AlertingService()
        self.secrets_integration = secrets_integration
        self.database_manager = database_manager
        self.redis_manager = redis_manager

        # Monitoring configuration
        self.monitoring_config = self._get_monitoring_config()

        # Health checks registry
        self.health_checks: dict[str, HealthCheck] = {}
        self.health_results: dict[str, HealthCheckResult] = {}

        # Metrics collection
        self.system_metrics_history: list[SystemMetrics] = []
        self.app_metrics_history: list[ApplicationMetrics] = []
        self.max_history_size = 1440  # 24 hours of minute-by-minute data

        # Alert thresholds
        self.alert_thresholds = self._get_alert_thresholds()

        # Background tasks
        self._monitoring_tasks: list[asyncio.Task] = []

        # Initialize default health checks
        self._register_default_health_checks()

        logger.info("Production monitoring service initialized")

    def _get_monitoring_config(self) -> dict[str, Any]:
        """Get monitoring configuration from production config."""
        if self.production_config:
            return self.production_config.get_monitoring_config()

        return {
            "prometheus": {"enabled": True, "port": 9090},
            "health_checks": {"interval": 30, "timeout": 5},
            "logging": {"structured": True, "level": "INFO"},
            "alerting": {"thresholds": {}},
            "tracing": {"enabled": True, "sample_rate": 0.1},
        }

    def _get_alert_thresholds(self) -> dict[str, dict[str, float]]:
        """Get alert thresholds from configuration."""
        if self.production_config:
            return self.production_config.monitoring.alert_thresholds

        return {
            "system": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_percent": 90.0,
                "load_average_1m": 4.0,
            },
            "application": {
                "error_rate_percent": 5.0,
                "response_time_p95_seconds": 2.0,
                "database_connection_percent": 90.0,
                "cache_hit_rate_percent": 80.0,
            },
            "database": {
                "connection_pool_usage_percent": 90.0,
                "slow_query_rate_percent": 10.0,
                "replication_lag_seconds": 60.0,
            },
        }

    def _register_default_health_checks(self) -> None:
        """Register default health checks for core components."""

        # Database health check
        self.register_health_check(
            name="database",
            description="PostgreSQL database connectivity and performance",
            check_function=self._check_database_health,
            interval_seconds=30,
            timeout_seconds=10,
            critical=True,
        )

        # Redis health check
        self.register_health_check(
            name="redis",
            description="Redis cache connectivity and performance",
            check_function=self._check_redis_health,
            interval_seconds=30,
            timeout_seconds=5,
            critical=False,
        )

        # Secrets management health check
        self.register_health_check(
            name="secrets",
            description="Secrets management system health",
            check_function=self._check_secrets_health,
            interval_seconds=300,  # Check every 5 minutes
            timeout_seconds=10,
            critical=True,
        )

        # System resources health check
        self.register_health_check(
            name="system_resources",
            description="System CPU, memory, and disk resources",
            check_function=self._check_system_resources_health,
            interval_seconds=60,
            timeout_seconds=5,
            critical=False,
        )

        # Application health check
        self.register_health_check(
            name="application",
            description="Application performance and error rates",
            check_function=self._check_application_health,
            interval_seconds=60,
            timeout_seconds=5,
            critical=True,
        )

    def register_health_check(
        self,
        name: str,
        description: str,
        check_function: Callable,
        interval_seconds: int,
        timeout_seconds: int,
        critical: bool = False,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a new health check."""
        health_check = HealthCheck(
            name=name,
            description=description,
            check_function=check_function,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            critical=critical,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )

        self.health_checks[name] = health_check
        logger.info(f"Registered health check: {name}")

    async def start_monitoring(self) -> None:
        """Start all monitoring tasks."""
        try:
            # Start system metrics collection
            self._monitoring_tasks.append(
                asyncio.create_task(self._collect_system_metrics())
            )

            # Start application metrics collection
            self._monitoring_tasks.append(
                asyncio.create_task(self._collect_application_metrics())
            )

            # Start health checks
            for health_check in self.health_checks.values():
                task = asyncio.create_task(self._run_health_check_loop(health_check))
                self._monitoring_tasks.append(task)

            # Start alert processing
            self._monitoring_tasks.append(asyncio.create_task(self._process_alerts()))

            # Start metrics cleanup
            self._monitoring_tasks.append(
                asyncio.create_task(self._cleanup_metrics_history())
            )

            logger.info(f"Started {len(self._monitoring_tasks)} monitoring tasks")

        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            raise

    async def stop_monitoring(self) -> None:
        """Stop all monitoring tasks."""
        for task in self._monitoring_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)

        self._monitoring_tasks.clear()
        logger.info("Stopped all monitoring tasks")

    async def _collect_system_metrics(self) -> None:
        """Collect system resource metrics."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_used_gb = memory.used / (1024**3)
                memory_available_gb = memory.available / (1024**3)

                # Disk usage
                disk = psutil.disk_usage("/")
                disk_percent = (disk.used / disk.total) * 100
                disk_used_gb = disk.used / (1024**3)
                disk_available_gb = disk.free / (1024**3)

                # Network I/O
                network = psutil.net_io_counters()

                # Load average (Unix systems)
                load_1m = load_5m = load_15m = None
                if hasattr(psutil, "getloadavg"):
                    load_1m, load_5m, load_15m = psutil.getloadavg()

                # Create metrics object
                metrics = SystemMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_used_gb=memory_used_gb,
                    memory_available_gb=memory_available_gb,
                    disk_percent=disk_percent,
                    disk_used_gb=disk_used_gb,
                    disk_available_gb=disk_available_gb,
                    network_bytes_sent=network.bytes_sent,
                    network_bytes_received=network.bytes_recv,
                    load_average_1m=load_1m,
                    load_average_5m=load_5m,
                    load_average_15m=load_15m,
                )

                # Store metrics
                self.system_metrics_history.append(metrics)

                # Update Prometheus metrics
                if self.metrics_service:
                    self.metrics_service.update_cpu_usage(cpu_percent)
                    self.metrics_service.update_memory_usage("total", memory.total)
                    self.metrics_service.update_memory_usage("used", memory.used)
                    self.metrics_service.update_memory_usage(
                        "available", memory.available
                    )
                    self.metrics_service.update_disk_usage("/", disk.used)

                # Check thresholds and trigger alerts
                await self._check_system_thresholds(metrics)

                await asyncio.sleep(60)  # Collect every minute

            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(60)

    async def _collect_application_metrics(self) -> None:
        """Collect application-specific metrics."""
        while True:
            try:
                # Database connections
                db_connections = 0
                if self.database_manager:
                    db_stats = self.database_manager.get_connection_statistics()
                    db_connections = db_stats.get("active_connections", 0)

                # Redis connections
                redis_connections = 0
                if self.redis_manager:
                    redis_stats = await self.redis_manager.get_stats()
                    # Extract connection count from stats
                    redis_connections = redis_stats.get("available_nodes", 0)

                # Application metrics from metrics service
                active_connections = 0
                request_rate = 0.0
                error_rate = 0.0
                response_time_p95 = 0.0
                cache_hit_rate = 0.0

                if self.metrics_service:
                    # These would be calculated from collected metrics
                    # This is a simplified implementation
                    pass

                # Create application metrics
                app_metrics = ApplicationMetrics(
                    active_connections=active_connections,
                    request_rate=request_rate,
                    error_rate=error_rate,
                    response_time_p95=response_time_p95,
                    database_connections=db_connections,
                    redis_connections=redis_connections,
                    cache_hit_rate=cache_hit_rate,
                )

                # Store metrics
                self.app_metrics_history.append(app_metrics)

                # Check thresholds and trigger alerts
                await self._check_application_thresholds(app_metrics)

                await asyncio.sleep(60)  # Collect every minute

            except Exception as e:
                logger.error(f"Error collecting application metrics: {e}")
                await asyncio.sleep(60)

    async def _run_health_check_loop(self, health_check: HealthCheck) -> None:
        """Run health check in a loop."""
        while True:
            try:
                # Check dependencies first
                if health_check.dependencies:
                    dependencies_healthy = all(
                        self.health_results.get(dep, {}).get("status")
                        == HealthStatus.HEALTHY
                        for dep in health_check.dependencies
                    )

                    if not dependencies_healthy:
                        result = HealthCheckResult(
                            name=health_check.name,
                            status=HealthStatus.UNKNOWN,
                            message="Dependencies not healthy",
                            duration_seconds=0.0,
                            timestamp=time.time(),
                        )
                        self.health_results[health_check.name] = result
                        await asyncio.sleep(health_check.interval_seconds)
                        continue

                # Execute health check
                start_time = time.time()
                try:
                    result = await asyncio.wait_for(
                        health_check.check_function(),
                        timeout=health_check.timeout_seconds,
                    )

                    if not isinstance(result, HealthCheckResult):
                        # Convert simple results
                        if isinstance(result, bool):
                            status = (
                                HealthStatus.HEALTHY
                                if result
                                else HealthStatus.UNHEALTHY
                            )
                            message = "OK" if result else "Check failed"
                        else:
                            status = HealthStatus.HEALTHY
                            message = str(result)

                        result = HealthCheckResult(
                            name=health_check.name,
                            status=status,
                            message=message,
                            duration_seconds=time.time() - start_time,
                            timestamp=time.time(),
                        )

                except asyncio.TimeoutError:
                    result = HealthCheckResult(
                        name=health_check.name,
                        status=HealthStatus.UNHEALTHY,
                        message="Health check timeout",
                        duration_seconds=health_check.timeout_seconds,
                        timestamp=time.time(),
                        error="timeout",
                    )

                except Exception as e:
                    result = HealthCheckResult(
                        name=health_check.name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check failed: {str(e)}",
                        duration_seconds=time.time() - start_time,
                        timestamp=time.time(),
                        error=str(e),
                    )

                # Store result
                self.health_results[health_check.name] = result

                # Update metrics
                if self.metrics_service:
                    healthy = result.status == HealthStatus.HEALTHY
                    self.metrics_service.update_dependency_health(
                        health_check.name, healthy
                    )

                # Trigger alerts for critical checks
                if health_check.critical and result.status != HealthStatus.HEALTHY:
                    await self._trigger_health_alert(health_check, result)

                await asyncio.sleep(health_check.interval_seconds)

            except Exception as e:
                logger.error(f"Error in health check loop for {health_check.name}: {e}")
                await asyncio.sleep(health_check.interval_seconds)

    async def _check_database_health(self) -> HealthCheckResult:
        """Check database health."""
        if not self.database_manager:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNKNOWN,
                message="Database manager not available",
                duration_seconds=0.0,
                timestamp=time.time(),
            )

        try:
            health_info = await self.database_manager.health_check()

            if health_info["status"] == "healthy":
                status = HealthStatus.HEALTHY
                message = "Database connections healthy"
            elif health_info["status"] == "degraded":
                status = HealthStatus.DEGRADED
                message = "Database partially degraded"
            else:
                status = HealthStatus.UNHEALTHY
                message = (
                    f"Database unhealthy: {health_info.get('error', 'Unknown error')}"
                )

            return HealthCheckResult(
                name="database",
                status=status,
                message=message,
                duration_seconds=0.1,  # Would be measured
                timestamp=time.time(),
                metadata=health_info,
            )

        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)}",
                duration_seconds=0.1,
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_redis_health(self) -> HealthCheckResult:
        """Check Redis health."""
        if not self.redis_manager:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNKNOWN,
                message="Redis manager not available",
                duration_seconds=0.0,
                timestamp=time.time(),
            )

        try:
            stats = await self.redis_manager.get_stats()

            if stats["available_nodes"] > 0:
                status = HealthStatus.HEALTHY
                message = f"Redis healthy: {stats['available_nodes']} nodes available"
            else:
                status = HealthStatus.UNHEALTHY
                message = "No Redis nodes available"

            return HealthCheckResult(
                name="redis",
                status=status,
                message=message,
                duration_seconds=0.05,
                timestamp=time.time(),
                metadata=stats,
            )

        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                duration_seconds=0.05,
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_secrets_health(self) -> HealthCheckResult:
        """Check secrets management health."""
        if not self.secrets_integration:
            return HealthCheckResult(
                name="secrets",
                status=HealthStatus.UNKNOWN,
                message="Secrets integration not available",
                duration_seconds=0.0,
                timestamp=time.time(),
            )

        try:
            health_info = self.secrets_integration.get_secrets_health()

            status = HealthStatus.HEALTHY
            message = f"Secrets healthy: {health_info['secrets_loaded']} secrets loaded"

            # Check for overdue rotations
            overdue_rotations = sum(
                1
                for rotation_status in health_info.get("rotation_status", {}).values()
                if rotation_status.get("overdue", False)
            )

            if overdue_rotations > 0:
                status = HealthStatus.DEGRADED
                message += f", {overdue_rotations} secrets need rotation"

            return HealthCheckResult(
                name="secrets",
                status=status,
                message=message,
                duration_seconds=0.02,
                timestamp=time.time(),
                metadata=health_info,
            )

        except Exception as e:
            return HealthCheckResult(
                name="secrets",
                status=HealthStatus.UNHEALTHY,
                message=f"Secrets check failed: {str(e)}",
                duration_seconds=0.02,
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_system_resources_health(self) -> HealthCheckResult:
        """Check system resources health."""
        try:
            if not self.system_metrics_history:
                return HealthCheckResult(
                    name="system_resources",
                    status=HealthStatus.UNKNOWN,
                    message="No system metrics available",
                    duration_seconds=0.0,
                    timestamp=time.time(),
                )

            latest_metrics = self.system_metrics_history[-1]

            issues = []
            status = HealthStatus.HEALTHY

            # Check CPU
            if (
                latest_metrics.cpu_percent
                > self.alert_thresholds["system"]["cpu_percent"]
            ):
                issues.append(f"CPU: {latest_metrics.cpu_percent:.1f}%")
                status = HealthStatus.DEGRADED

            # Check memory
            if (
                latest_metrics.memory_percent
                > self.alert_thresholds["system"]["memory_percent"]
            ):
                issues.append(f"Memory: {latest_metrics.memory_percent:.1f}%")
                status = HealthStatus.DEGRADED

            # Check disk
            if (
                latest_metrics.disk_percent
                > self.alert_thresholds["system"]["disk_percent"]
            ):
                issues.append(f"Disk: {latest_metrics.disk_percent:.1f}%")
                status = HealthStatus.UNHEALTHY

            # Check load average
            if (
                latest_metrics.load_average_1m
                and latest_metrics.load_average_1m
                > self.alert_thresholds["system"]["load_average_1m"]
            ):
                issues.append(f"Load: {latest_metrics.load_average_1m:.2f}")
                status = HealthStatus.DEGRADED

            if issues:
                message = f"Resource issues: {', '.join(issues)}"
            else:
                message = "System resources healthy"

            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                duration_seconds=0.01,
                timestamp=time.time(),
                metadata={
                    "cpu_percent": latest_metrics.cpu_percent,
                    "memory_percent": latest_metrics.memory_percent,
                    "disk_percent": latest_metrics.disk_percent,
                    "load_average_1m": latest_metrics.load_average_1m,
                },
            )

        except Exception as e:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                message=f"System resources check failed: {str(e)}",
                duration_seconds=0.01,
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_application_health(self) -> HealthCheckResult:
        """Check application health."""
        try:
            if not self.app_metrics_history:
                return HealthCheckResult(
                    name="application",
                    status=HealthStatus.UNKNOWN,
                    message="No application metrics available",
                    duration_seconds=0.0,
                    timestamp=time.time(),
                )

            latest_metrics = self.app_metrics_history[-1]

            issues = []
            status = HealthStatus.HEALTHY

            # Check error rate
            if (
                latest_metrics.error_rate
                > self.alert_thresholds["application"]["error_rate_percent"]
            ):
                issues.append(f"Error rate: {latest_metrics.error_rate:.1f}%")
                status = HealthStatus.DEGRADED

            # Check response time
            if (
                latest_metrics.response_time_p95
                > self.alert_thresholds["application"]["response_time_p95_seconds"]
            ):
                issues.append(f"Response time: {latest_metrics.response_time_p95:.2f}s")
                status = HealthStatus.DEGRADED

            # Check cache hit rate
            if (
                latest_metrics.cache_hit_rate
                < self.alert_thresholds["application"]["cache_hit_rate_percent"]
            ):
                issues.append(f"Cache hit rate: {latest_metrics.cache_hit_rate:.1f}%")
                status = HealthStatus.DEGRADED

            if issues:
                message = f"Application issues: {', '.join(issues)}"
            else:
                message = "Application performance healthy"

            return HealthCheckResult(
                name="application",
                status=status,
                message=message,
                duration_seconds=0.02,
                timestamp=time.time(),
                metadata={
                    "error_rate": latest_metrics.error_rate,
                    "response_time_p95": latest_metrics.response_time_p95,
                    "cache_hit_rate": latest_metrics.cache_hit_rate,
                    "database_connections": latest_metrics.database_connections,
                },
            )

        except Exception as e:
            return HealthCheckResult(
                name="application",
                status=HealthStatus.UNHEALTHY,
                message=f"Application check failed: {str(e)}",
                duration_seconds=0.02,
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_system_thresholds(self, metrics: SystemMetrics) -> None:
        """Check system metrics against thresholds and trigger alerts."""
        thresholds = self.alert_thresholds["system"]

        # CPU threshold
        if metrics.cpu_percent > thresholds["cpu_percent"]:
            await self._trigger_alert(
                name="high_cpu_usage",
                severity=AlertSeverity.WARNING,
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                metrics={"cpu_percent": metrics.cpu_percent},
            )

        # Memory threshold
        if metrics.memory_percent > thresholds["memory_percent"]:
            await self._trigger_alert(
                name="high_memory_usage",
                severity=AlertSeverity.WARNING,
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                metrics={"memory_percent": metrics.memory_percent},
            )

        # Disk threshold
        if metrics.disk_percent > thresholds["disk_percent"]:
            await self._trigger_alert(
                name="high_disk_usage",
                severity=AlertSeverity.ERROR,
                message=f"High disk usage: {metrics.disk_percent:.1f}%",
                metrics={"disk_percent": metrics.disk_percent},
            )

    async def _check_application_thresholds(self, metrics: ApplicationMetrics) -> None:
        """Check application metrics against thresholds and trigger alerts."""
        thresholds = self.alert_thresholds["application"]

        # Error rate threshold
        if metrics.error_rate > thresholds["error_rate_percent"]:
            await self._trigger_alert(
                name="high_error_rate",
                severity=AlertSeverity.ERROR,
                message=f"High error rate: {metrics.error_rate:.1f}%",
                metrics={"error_rate": metrics.error_rate},
            )

        # Response time threshold
        if metrics.response_time_p95 > thresholds["response_time_p95_seconds"]:
            await self._trigger_alert(
                name="high_response_time",
                severity=AlertSeverity.WARNING,
                message=f"High response time: {metrics.response_time_p95:.2f}s",
                metrics={"response_time_p95": metrics.response_time_p95},
            )

    async def _trigger_alert(
        self,
        name: str,
        severity: AlertSeverity,
        message: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Trigger an alert through the alerting service."""
        try:
            if self.alerting_service:
                await self.alerting_service.send_alert(
                    alert_name=name,
                    severity=severity.value,
                    message=message,
                    metadata=metrics or {},
                )

            # Also record in metrics service
            if self.metrics_service:
                self.metrics_service.record_security_event(
                    f"alert_{severity.value}", severity.value
                )

            logger.warning(f"Alert triggered: {name} - {message}")

        except Exception as e:
            logger.error(f"Failed to trigger alert {name}: {e}")

    async def _trigger_health_alert(
        self, health_check: HealthCheck, result: HealthCheckResult
    ) -> None:
        """Trigger alert for unhealthy critical components."""
        severity = (
            AlertSeverity.CRITICAL if health_check.critical else AlertSeverity.WARNING
        )

        await self._trigger_alert(
            name=f"health_check_{health_check.name}",
            severity=severity,
            message=f"Health check failed: {health_check.name} - {result.message}",
            metrics={
                "status": result.status.value,
                "duration": result.duration_seconds,
            },
        )

    async def _process_alerts(self) -> None:
        """Process and manage alerts."""
        while True:
            try:
                # Alert processing logic would go here
                # This could include alert deduplication, escalation, etc.
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error processing alerts: {e}")
                await asyncio.sleep(60)

    async def _cleanup_metrics_history(self) -> None:
        """Clean up old metrics history to prevent memory growth."""
        while True:
            try:
                # Keep only recent metrics
                if len(self.system_metrics_history) > self.max_history_size:
                    self.system_metrics_history = self.system_metrics_history[
                        -self.max_history_size :
                    ]

                if len(self.app_metrics_history) > self.max_history_size:
                    self.app_metrics_history = self.app_metrics_history[
                        -self.max_history_size :
                    ]

                await asyncio.sleep(3600)  # Cleanup every hour

            except Exception as e:
                logger.error(f"Error cleaning up metrics: {e}")
                await asyncio.sleep(3600)

    def get_overall_health(self) -> dict[str, Any]:
        """Get overall system health status."""
        overall_status = HealthStatus.HEALTHY
        critical_issues = []
        non_critical_issues = []

        for name, result in self.health_results.items():
            health_check = self.health_checks.get(name)

            if result.status != HealthStatus.HEALTHY:
                if health_check and health_check.critical:
                    critical_issues.append(f"{name}: {result.message}")
                    overall_status = HealthStatus.UNHEALTHY
                else:
                    non_critical_issues.append(f"{name}: {result.message}")
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "health_checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "last_check": result.timestamp,
                    "duration": result.duration_seconds,
                }
                for name, result in self.health_results.items()
            },
            "critical_issues": critical_issues,
            "non_critical_issues": non_critical_issues,
            "metrics_summary": self._get_metrics_summary(),
        }

    def _get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of recent metrics."""
        summary = {}

        if self.system_metrics_history:
            latest_system = self.system_metrics_history[-1]
            summary["system"] = {
                "cpu_percent": latest_system.cpu_percent,
                "memory_percent": latest_system.memory_percent,
                "disk_percent": latest_system.disk_percent,
                "load_average_1m": latest_system.load_average_1m,
            }

        if self.app_metrics_history:
            latest_app = self.app_metrics_history[-1]
            summary["application"] = {
                "error_rate": latest_app.error_rate,
                "response_time_p95": latest_app.response_time_p95,
                "database_connections": latest_app.database_connections,
                "cache_hit_rate": latest_app.cache_hit_rate,
            }

        return summary


def create_production_monitoring_service(
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
    alerting_service: AlertingService | None = None,
    secrets_integration: ProductionSecretsIntegration | None = None,
    database_manager: ProductionDatabaseManager | None = None,
    redis_manager: RedisClusterManager | None = None,
) -> ProductionMonitoringService:
    """Create production monitoring service with all integrations."""
    return ProductionMonitoringService(
        production_config=production_config,
        metrics_service=metrics_service,
        alerting_service=alerting_service,
        secrets_integration=secrets_integration,
        database_manager=database_manager,
        redis_manager=redis_manager,
    )
