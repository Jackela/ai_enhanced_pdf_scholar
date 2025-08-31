"""
Enhanced Health Check Service
Comprehensive health monitoring with dependency validation and circuit breaker integration.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import psutil
from sqlalchemy import create_engine, text

from backend.database.postgresql_config import PostgreSQLConfig
from backend.services.redis_cache_service import RedisCacheService

logger = logging.getLogger(__name__)


# ============================================================================
# Health Check Models
# ============================================================================

class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckSeverity(str, Enum):
    """Severity levels for health checks."""
    CRITICAL = "critical"  # Service cannot function
    MAJOR = "major"       # Service degraded but functional
    MINOR = "minor"       # Warning, service fully functional
    INFO = "info"         # Informational only


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    severity: CheckSeverity
    message: str
    details: dict[str, Any]
    duration_ms: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SystemHealth:
    """Overall system health summary."""
    status: HealthStatus
    checks: list[HealthCheckResult]
    summary: dict[str, Any]
    uptime: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "uptime_seconds": self.uptime,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks]
        }


# ============================================================================
# Health Check Service
# ============================================================================

class HealthCheckService:
    """
    Comprehensive health check service with dependency validation.
    """

    def __init__(
        self,
        postgres_config: PostgreSQLConfig | None = None,
        redis_service: RedisCacheService | None = None
    ):
        """Initialize health check service."""
        self.postgres_config = postgres_config or PostgreSQLConfig()
        self.redis_service = redis_service

        # Service startup time
        self.startup_time = time.time()

        # Health check registry
        self.health_checks = {}

        # Health history for trend analysis
        self.health_history = []
        self.max_history_size = 100

        # Circuit breaker states
        self.circuit_states = {}

        # Register default health checks
        self._register_default_checks()

        logger.info("Health check service initialized")

    def _register_default_checks(self):
        """Register default health checks."""
        self.register_check(
            name="database",
            check_func=self._check_database,
            severity=CheckSeverity.CRITICAL,
            timeout=5.0
        )

        self.register_check(
            name="redis_cache",
            check_func=self._check_redis,
            severity=CheckSeverity.MAJOR,
            timeout=3.0
        )

        self.register_check(
            name="memory",
            check_func=self._check_memory,
            severity=CheckSeverity.MAJOR,
            timeout=1.0
        )

        self.register_check(
            name="disk_space",
            check_func=self._check_disk_space,
            severity=CheckSeverity.MAJOR,
            timeout=1.0
        )

        self.register_check(
            name="cpu",
            check_func=self._check_cpu,
            severity=CheckSeverity.MINOR,
            timeout=2.0
        )

        self.register_check(
            name="network",
            check_func=self._check_network,
            severity=CheckSeverity.MINOR,
            timeout=3.0
        )

        self.register_check(
            name="external_services",
            check_func=self._check_external_services,
            severity=CheckSeverity.MAJOR,
            timeout=10.0
        )

    def register_check(
        self,
        name: str,
        check_func: callable,
        severity: CheckSeverity = CheckSeverity.MAJOR,
        timeout: float = 5.0,
        enabled: bool = True
    ):
        """Register a health check."""
        self.health_checks[name] = {
            "func": check_func,
            "severity": severity,
            "timeout": timeout,
            "enabled": enabled,
            "last_result": None,
            "failure_count": 0,
            "last_failure": None
        }

        logger.info(f"Registered health check: {name}")

    def unregister_check(self, name: str):
        """Unregister a health check."""
        if name in self.health_checks:
            del self.health_checks[name]
            logger.info(f"Unregistered health check: {name}")

    def enable_check(self, name: str):
        """Enable a health check."""
        if name in self.health_checks:
            self.health_checks[name]["enabled"] = True

    def disable_check(self, name: str):
        """Disable a health check."""
        if name in self.health_checks:
            self.health_checks[name]["enabled"] = False

    async def check_health(
        self,
        include_details: bool = True,
        check_names: list[str] | None = None
    ) -> SystemHealth:
        """
        Perform comprehensive health check.

        Args:
            include_details: Include detailed check information
            check_names: Specific checks to run (None for all)

        Returns:
            SystemHealth object with results
        """
        start_time = time.time()
        results = []

        # Determine which checks to run
        checks_to_run = check_names or list(self.health_checks.keys())
        enabled_checks = {
            name: check for name, check in self.health_checks.items()
            if check["enabled"] and name in checks_to_run
        }

        # Run health checks concurrently
        tasks = []
        for name, check_config in enabled_checks.items():
            task = asyncio.create_task(
                self._run_single_check(name, check_config)
            )
            tasks.append(task)

        # Wait for all checks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    check_name = list(enabled_checks.keys())[i]
                    error_result = HealthCheckResult(
                        name=check_name,
                        status=HealthStatus.UNHEALTHY,
                        severity=enabled_checks[check_name]["severity"],
                        message=f"Health check failed: {str(result)}",
                        details={"error": str(result)},
                        duration_ms=(time.time() - start_time) * 1000,
                        timestamp=datetime.utcnow()
                    )
                    valid_results.append(error_result)
                else:
                    valid_results.append(result)

            results = valid_results

        # Calculate overall health status
        overall_status = self._calculate_overall_status(results)

        # Generate summary
        summary = self._generate_summary(results)

        # Calculate uptime
        uptime = time.time() - self.startup_time

        # Create system health object
        system_health = SystemHealth(
            status=overall_status,
            checks=results if include_details else [],
            summary=summary,
            uptime=uptime,
            timestamp=datetime.utcnow()
        )

        # Store in history for trend analysis
        self._store_health_history(system_health)

        return system_health

    async def _run_single_check(
        self,
        name: str,
        check_config: dict[str, Any]
    ) -> HealthCheckResult:
        """Run a single health check with timeout."""
        start_time = time.time()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                self._execute_check(check_config["func"]),
                timeout=check_config["timeout"]
            )

            # Reset failure count on success
            if result.status == HealthStatus.HEALTHY:
                check_config["failure_count"] = 0
            else:
                check_config["failure_count"] += 1
                check_config["last_failure"] = datetime.utcnow()

            # Store last result
            check_config["last_result"] = result

            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            check_config["failure_count"] += 1
            check_config["last_failure"] = datetime.utcnow()

            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                severity=check_config["severity"],
                message=f"Health check timed out after {check_config['timeout']}s",
                details={"timeout": check_config["timeout"]},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            check_config["failure_count"] += 1
            check_config["last_failure"] = datetime.utcnow()

            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                severity=check_config["severity"],
                message=f"Health check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _execute_check(self, check_func: callable) -> HealthCheckResult:
        """Execute a health check function."""
        if asyncio.iscoroutinefunction(check_func):
            return await check_func()
        else:
            # Run synchronous function in thread pool
            return await asyncio.get_event_loop().run_in_executor(
                None, check_func
            )

    # ========================================================================
    # Individual Health Checks
    # ========================================================================

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity and performance."""
        start_time = time.time()

        try:
            # Create database engine
            engine = create_engine(
                self.postgres_config.get_connection_url(),
                pool_timeout=2,
                pool_recycle=300
            )

            # Test connection and query
            with engine.connect() as conn:
                # Simple connectivity test
                _ = conn.execute(text("SELECT 1")).fetchone()

                # Check database version
                version_result = conn.execute(text("SELECT version()")).fetchone()
                version = version_result[0] if version_result else "unknown"

                # Check connection count
                conn_result = conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity")
                ).fetchone()
                active_connections = conn_result[0] if conn_result else 0

                # Check database size
                size_result = conn.execute(
                    text("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                    """)
                ).fetchone()
                db_size = size_result[0] if size_result else "unknown"

            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on performance
            if duration_ms > 1000:  # > 1 second
                status = HealthStatus.DEGRADED
                message = f"Database responding slowly ({duration_ms:.0f}ms)"
            else:
                status = HealthStatus.HEALTHY
                message = "Database connection healthy"

            return HealthCheckResult(
                name="database",
                status=status,
                severity=CheckSeverity.CRITICAL,
                message=message,
                details={
                    "response_time_ms": round(duration_ms, 2),
                    "active_connections": active_connections,
                    "database_size": db_size,
                    "version": version.split()[0:2]  # Simplified version info
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                severity=CheckSeverity.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "response_time_ms": round(duration_ms, 2)
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and performance."""
        start_time = time.time()

        if not self.redis_service:
            return HealthCheckResult(
                name="redis_cache",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.MAJOR,
                message="Redis service not configured",
                details={},
                duration_ms=0,
                timestamp=datetime.utcnow()
            )

        try:
            # Test basic connectivity
            test_key = "healthcheck:test"
            test_value = f"test_{int(time.time())}"

            # Set and get test value
            success = self.redis_service.set(test_key, test_value, ttl=10)
            if not success:
                raise Exception("Failed to set test value")

            retrieved_value = self.redis_service.get(test_key)
            if retrieved_value != test_value:
                raise Exception("Retrieved value doesn't match")

            # Clean up test key
            self.redis_service.delete(test_key)

            # Get Redis info
            stats = self.redis_service.get_stats()

            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on performance and hit rate
            hit_rate = stats.get("hit_rate", 0)
            if duration_ms > 500:  # > 500ms
                status = HealthStatus.DEGRADED
                message = f"Redis responding slowly ({duration_ms:.0f}ms)"
            elif hit_rate < 50:  # < 50% hit rate
                status = HealthStatus.DEGRADED
                message = f"Low cache hit rate ({hit_rate:.1f}%)"
            else:
                status = HealthStatus.HEALTHY
                message = "Redis cache healthy"

            return HealthCheckResult(
                name="redis_cache",
                status=status,
                severity=CheckSeverity.MAJOR,
                message=message,
                details={
                    "response_time_ms": round(duration_ms, 2),
                    "hit_rate": hit_rate,
                    "total_hits": stats.get("hits", 0),
                    "total_misses": stats.get("misses", 0),
                    "redis_info": stats.get("redis", {})
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="redis_cache",
                status=HealthStatus.UNHEALTHY,
                severity=CheckSeverity.MAJOR,
                message=f"Redis connection failed: {str(e)}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "response_time_ms": round(duration_ms, 2)
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        start_time = time.time()

        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Calculate percentages
            memory_percent = memory.percent
            swap_percent = swap.percent if swap.total > 0 else 0

            # Determine status
            if memory_percent > 90 or swap_percent > 50:
                status = HealthStatus.UNHEALTHY
                message = f"High memory usage: {memory_percent:.1f}% RAM, {swap_percent:.1f}% swap"
            elif memory_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"Elevated memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}%"

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="memory",
                status=status,
                severity=CheckSeverity.MAJOR,
                message=message,
                details={
                    "memory_percent": round(memory_percent, 1),
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "swap_percent": round(swap_percent, 1),
                    "swap_total_gb": round(swap.total / (1024**3), 2) if swap.total > 0 else 0
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNHEALTHY,
                severity=CheckSeverity.MAJOR,
                message=f"Memory check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage."""
        start_time = time.time()

        try:
            # Check root filesystem
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100

            # Check additional mount points if they exist
            additional_disks = {}
            try:
                partitions = psutil.disk_partitions()
                for partition in partitions:
                    if partition.mountpoint != '/':
                        try:
                            partition_usage = psutil.disk_usage(partition.mountpoint)
                            partition_percent = (partition_usage.used / partition_usage.total) * 100
                            additional_disks[partition.mountpoint] = {
                                "usage_percent": round(partition_percent, 1),
                                "total_gb": round(partition_usage.total / (1024**3), 2),
                                "free_gb": round(partition_usage.free / (1024**3), 2)
                            }
                        except (OSError, PermissionError):
                            continue
            except Exception:
                pass

            # Determine status
            if usage_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk space: {usage_percent:.1f}% used"
            elif usage_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {usage_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space normal: {usage_percent:.1f}% used"

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="disk_space",
                status=status,
                severity=CheckSeverity.MAJOR,
                message=message,
                details={
                    "root_usage_percent": round(usage_percent, 1),
                    "root_total_gb": round(disk_usage.total / (1024**3), 2),
                    "root_free_gb": round(disk_usage.free / (1024**3), 2),
                    "additional_disks": additional_disks
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                severity=CheckSeverity.MAJOR,
                message=f"Disk check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_cpu(self) -> HealthCheckResult:
        """Check CPU usage."""
        start_time = time.time()

        try:
            # Get CPU usage over 1 second interval
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)

            # Determine status
            if cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="cpu",
                status=status,
                severity=CheckSeverity.MINOR,
                message=message,
                details={
                    "cpu_percent": round(cpu_percent, 1),
                    "cpu_count": cpu_count,
                    "load_average_1m": round(load_avg[0], 2),
                    "load_average_5m": round(load_avg[1], 2),
                    "load_average_15m": round(load_avg[2], 2)
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="cpu",
                status=HealthStatus.UNHEALTHY,
                severity=CheckSeverity.MINOR,
                message=f"CPU check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_network(self) -> HealthCheckResult:
        """Check network connectivity."""
        start_time = time.time()

        try:
            import socket

            # Test DNS resolution
            socket.gethostbyname("google.com")

            # Get network statistics
            net_io = psutil.net_io_counters()

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="network",
                status=HealthStatus.HEALTHY,
                severity=CheckSeverity.MINOR,
                message="Network connectivity healthy",
                details={
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "dns_resolution_ms": round(duration_ms, 2)
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="network",
                status=HealthStatus.DEGRADED,
                severity=CheckSeverity.MINOR,
                message=f"Network check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    async def _check_external_services(self) -> HealthCheckResult:
        """Check external service dependencies."""
        start_time = time.time()

        try:
            import aiohttp

            external_services = []

            # Check Google API (for Gemini)
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://generativelanguage.googleapis.com/v1/models",
                            params={"key": google_api_key},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status == 200:
                                external_services.append({
                                    "service": "google_gemini",
                                    "status": "healthy",
                                    "response_code": response.status
                                })
                            else:
                                external_services.append({
                                    "service": "google_gemini",
                                    "status": "degraded",
                                    "response_code": response.status
                                })
                except Exception as e:
                    external_services.append({
                        "service": "google_gemini",
                        "status": "unhealthy",
                        "error": str(e)
                    })

            # Determine overall status
            unhealthy_count = sum(1 for svc in external_services if svc.get("status") == "unhealthy")
            degraded_count = sum(1 for svc in external_services if svc.get("status") == "degraded")

            if unhealthy_count > 0:
                status = HealthStatus.DEGRADED
                message = f"{unhealthy_count} external service(s) unhealthy"
            elif degraded_count > 0:
                status = HealthStatus.DEGRADED
                message = f"{degraded_count} external service(s) degraded"
            else:
                status = HealthStatus.HEALTHY
                message = "All external services healthy"

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="external_services",
                status=status,
                severity=CheckSeverity.MAJOR,
                message=message,
                details={
                    "services": external_services,
                    "total_services": len(external_services),
                    "unhealthy_count": unhealthy_count,
                    "degraded_count": degraded_count
                },
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="external_services",
                status=HealthStatus.UNKNOWN,
                severity=CheckSeverity.MAJOR,
                message=f"External services check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=datetime.utcnow()
            )

    # ========================================================================
    # Health Status Analysis
    # ========================================================================

    def _calculate_overall_status(self, results: list[HealthCheckResult]) -> HealthStatus:
        """Calculate overall system health status."""
        if not results:
            return HealthStatus.UNKNOWN

        # Count statuses by severity
        critical_unhealthy = sum(
            1 for r in results
            if r.severity == CheckSeverity.CRITICAL and r.status == HealthStatus.UNHEALTHY
        )

        major_unhealthy = sum(
            1 for r in results
            if r.severity == CheckSeverity.MAJOR and r.status == HealthStatus.UNHEALTHY
        )

        any_degraded = any(r.status == HealthStatus.DEGRADED for r in results)

        # Determine overall status
        if critical_unhealthy > 0:
            return HealthStatus.UNHEALTHY
        elif major_unhealthy > 0 or any_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _generate_summary(self, results: list[HealthCheckResult]) -> dict[str, Any]:
        """Generate health summary statistics."""
        if not results:
            return {}

        status_counts = {}
        severity_counts = {}
        total_duration = 0

        for result in results:
            status_counts[result.status.value] = status_counts.get(result.status.value, 0) + 1
            severity_counts[result.severity.value] = severity_counts.get(result.severity.value, 0) + 1
            total_duration += result.duration_ms

        return {
            "total_checks": len(results),
            "status_counts": status_counts,
            "severity_counts": severity_counts,
            "average_duration_ms": round(total_duration / len(results), 2) if results else 0,
            "total_duration_ms": round(total_duration, 2)
        }

    def _store_health_history(self, system_health: SystemHealth):
        """Store health check result in history."""
        self.health_history.append({
            "timestamp": system_health.timestamp,
            "status": system_health.status.value,
            "summary": system_health.summary
        })

        # Trim history if too large
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size:]

    # ========================================================================
    # Public Health Check Methods
    # ========================================================================

    async def get_health_status(self, detailed: bool = False) -> dict[str, Any]:
        """Get current health status."""
        health = await self.check_health(include_details=detailed)
        return health.to_dict()

    async def get_liveness_probe(self) -> dict[str, Any]:
        """Kubernetes liveness probe endpoint."""
        # Only check critical services for liveness
        critical_checks = [
            name for name, config in self.health_checks.items()
            if config["severity"] == CheckSeverity.CRITICAL and config["enabled"]
        ]

        health = await self.check_health(
            include_details=False,
            check_names=critical_checks
        )

        return {
            "status": health.status.value,
            "timestamp": health.timestamp.isoformat()
        }

    async def get_readiness_probe(self) -> dict[str, Any]:
        """Kubernetes readiness probe endpoint."""
        health = await self.check_health(include_details=False)

        # Service is ready if it's healthy or only degraded
        ready = health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

        return {
            "ready": ready,
            "status": health.status.value,
            "timestamp": health.timestamp.isoformat()
        }

    def get_health_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get health check history."""
        return self.health_history[-limit:] if self.health_history else []

    def get_check_status(self, check_name: str) -> dict[str, Any] | None:
        """Get status of a specific health check."""
        if check_name not in self.health_checks:
            return None

        check_config = self.health_checks[check_name]
        return {
            "name": check_name,
            "enabled": check_config["enabled"],
            "severity": check_config["severity"].value,
            "timeout": check_config["timeout"],
            "failure_count": check_config["failure_count"],
            "last_failure": check_config["last_failure"].isoformat() if check_config["last_failure"] else None,
            "last_result": check_config["last_result"].to_dict() if check_config["last_result"] else None
        }

    def get_all_checks_status(self) -> dict[str, Any]:
        """Get status of all registered health checks."""
        return {
            name: self.get_check_status(name)
            for name in self.health_checks.keys()
        }


if __name__ == "__main__":
    # Example usage
    async def main():
        health_service = HealthCheckService()

        # Check overall health
        health = await health_service.get_health_status(detailed=True)
        print("System Health:")
        print(json.dumps(health, indent=2))

        # Check liveness
        liveness = await health_service.get_liveness_probe()
        print("\nLiveness Probe:")
        print(json.dumps(liveness, indent=2))

        # Check readiness
        readiness = await health_service.get_readiness_probe()
        print("\nReadiness Probe:")
        print(json.dumps(readiness, indent=2))

    asyncio.run(main())
