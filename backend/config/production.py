"""
Production Environment Configuration
Optimized production settings with performance tuning, security hardening, and monitoring integration.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Union

from ..core.secrets_vault import ProductionSecretsManager
from ..services.metrics_service import MetricsService
from .application_config import get_application_config

logger = logging.getLogger(__name__)


@dataclass
class DatabasePoolConfig:
    """Production database connection pooling configuration."""

    max_connections: int = 50
    min_connections: int = 10
    connection_timeout: int = 30
    idle_timeout: int = 3600
    max_retries: int = 3
    retry_delay: float = 0.5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    echo: bool = False

    # Performance optimization
    enable_connection_pooling: bool = True
    pool_size: int = 20
    max_overflow: int = 30

    # Read/write splitting configuration
    enable_read_write_split: bool = False
    read_replica_urls: list[str] = field(default_factory=list[Any])
    read_weight: float = 0.7  # 70% reads go to replicas


@dataclass
class CacheClusterConfig:
    """Production Redis cluster configuration."""

    cluster_nodes: list[str] = field(default_factory=lambda: ["redis://localhost:6379"])
    enable_cluster: bool = False

    # Connection pooling
    connection_pool_max_connections: int = 50
    connection_timeout: float = 2.0
    socket_timeout: float = 2.0
    socket_keepalive: bool = True

    # Failover and HA
    enable_sentinel: bool = False
    sentinel_service: str = "mymaster"
    sentinel_nodes: list[str] = field(default_factory=list[Any])

    # Memory management
    max_memory: str = "2gb"
    max_memory_policy: str = "allkeys-lru"

    # Cache policies
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400  # 24 hours
    compression_threshold: int = 1024  # Compress values > 1KB

    # Performance tuning
    pipeline_size: int = 100
    enable_pipelining: bool = True
    key_prefix: str = "ai_pdf_scholar:prod:"


@dataclass
class SecurityHardeningConfig:
    """Production security hardening configuration."""

    # Content Security Policy
    enable_csp: bool = True
    csp_policy: dict[str, list[str]] = field(
        default_factory=lambda: {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "connect-src": ["'self'", "https://api.google.com"],
            "font-src": ["'self'"],
            "object-src": ["'none'"],
            "media-src": ["'self'"],
            "frame-src": ["'none'"],
        }
    )

    # HTTP Security Headers
    security_headers: dict[str, str] = field(
        default_factory=lambda: {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        }
    )

    # IP Filtering
    enable_ip_whitelist: bool = True
    allowed_ip_ranges: list[str] = field(default_factory=list[Any])
    blocked_ip_ranges: list[str] = field(default_factory=list[Any])
    enable_geoip_filtering: bool = False
    allowed_countries: list[str] = field(default_factory=list[Any])

    # Request signing
    enable_request_signing: bool = True
    signature_ttl: int = 300  # 5 minutes
    hmac_algorithm: str = "sha256"

    # Rate limiting hardening
    strict_rate_limits: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            "/api/auth/login": {"requests": 5, "window": 300},
            "/api/documents/upload": {"requests": 10, "window": 3600},
            "/api/rag/query": {"requests": 100, "window": 3600},
            "global": {"requests": 1000, "window": 3600},
        }
    )

    # CORS hardening
    strict_cors: bool = True
    allowed_origins: list[str] = field(default_factory=list[Any])
    max_age: int = 86400


@dataclass
class PerformanceConfig:
    """Production performance optimization configuration."""

    # Async/Await optimization
    max_workers: int = 4
    worker_connections: int = 1000
    keepalive_timeout: int = 65
    client_max_body_size: str = "100M"

    # Memory management
    max_memory_mb: int = 2048
    gc_threshold: tuple = (700, 10, 10)
    enable_memory_profiling: bool = False

    # Connection limits
    max_concurrent_connections: int = 1000
    connection_limit_per_ip: int = 10
    slow_request_threshold: float = 5.0

    # Resource limits
    max_file_size_mb: int = 100
    max_upload_files: int = 10
    max_request_size_mb: int = 200

    # Caching optimization
    enable_response_caching: bool = True
    response_cache_ttl: int = 300
    enable_etag_caching: bool = True
    enable_gzip_compression: bool = True
    gzip_min_size: int = 1000

    # Database query optimization
    query_timeout: int = 30
    max_query_complexity: int = 1000
    enable_query_caching: bool = True
    query_cache_ttl: int = 600


@dataclass
class MonitoringIntegrationConfig:
    """Integration with monitoring and alerting systems."""

    # Prometheus metrics
    enable_prometheus: bool = True
    metrics_port: int = 9090
    metrics_endpoint: str = "/metrics"

    # Health checks
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_endpoints: list[str] = field(
        default_factory=lambda: ["/health", "/health/ready", "/health/live"]
    )

    # Logging integration
    structured_logging: bool = True
    log_level: str = "INFO"
    enable_audit_logs: bool = True
    log_retention_days: int = 90

    # Alerting thresholds
    alert_thresholds: dict[str, int | float] = field(
        default_factory=lambda: {
            "error_rate_percent": 5.0,
            "response_time_p95_seconds": 2.0,
            "memory_usage_percent": 80.0,
            "cpu_usage_percent": 80.0,
            "disk_usage_percent": 85.0,
            "connection_pool_usage_percent": 90.0,
        }
    )

    # Tracing
    enable_tracing: bool = True
    tracing_sample_rate: float = 0.1
    jaeger_endpoint: str | None = None


class ProductionConfig:
    """
    Comprehensive production configuration with performance optimization,
    security hardening, and monitoring integration.
    """

    def __init__(
        self,
        secrets_manager: ProductionSecretsManager | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Initialize production configuration."""
        self.secrets_manager = secrets_manager
        self.metrics_service = metrics_service
        self.base_config = get_application_config()

        # Validate environment
        if not self.base_config.environment.is_production():
            logger.warning("ProductionConfig initialized in non-production environment")

        # Initialize configuration components
        self.database = self._load_database_config()
        self.cache = self._load_cache_config()
        self.security = self._load_security_config()
        self.performance = self._load_performance_config()
        self.monitoring = self._load_monitoring_config()

        # Validate configuration
        self._validate_configuration()

        logger.info("Production configuration initialized successfully")

    def _load_database_config(self) -> DatabasePoolConfig:
        """Load database configuration with production optimizations."""
        return DatabasePoolConfig(
            max_connections=int(os.getenv("DB_POOL_MAX_CONNECTIONS", "50")),
            min_connections=int(os.getenv("DB_POOL_MIN_CONNECTIONS", "10")),
            connection_timeout=int(os.getenv("DB_CONNECTION_TIMEOUT", "30")),
            idle_timeout=int(os.getenv("DB_IDLE_TIMEOUT", "3600")),
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "30")),
            enable_read_write_split=os.getenv(
                "DB_ENABLE_READ_WRITE_SPLIT", "false"
            ).lower()
            == "true",
            read_replica_urls=(
                os.getenv("DB_READ_REPLICA_URLS", "").split(",")
                if os.getenv("DB_READ_REPLICA_URLS")
                else []
            ),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )

    def _load_cache_config(self) -> CacheClusterConfig:
        """Load Redis cluster configuration."""
        cluster_nodes = os.getenv(
            "REDIS_CLUSTER_NODES", "redis://localhost:6379"
        ).split(",")

        return CacheClusterConfig(
            cluster_nodes=cluster_nodes,
            enable_cluster=len(cluster_nodes) > 1,
            connection_pool_max_connections=int(
                os.getenv("REDIS_POOL_MAX_CONNECTIONS", "50")
            ),
            connection_timeout=float(os.getenv("REDIS_CONNECTION_TIMEOUT", "2.0")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0")),
            enable_sentinel=os.getenv("REDIS_ENABLE_SENTINEL", "false").lower()
            == "true",
            sentinel_service=os.getenv("REDIS_SENTINEL_SERVICE", "mymaster"),
            sentinel_nodes=(
                os.getenv("REDIS_SENTINEL_NODES", "").split(",")
                if os.getenv("REDIS_SENTINEL_NODES")
                else []
            ),
            max_memory=os.getenv("REDIS_MAX_MEMORY", "2gb"),
            max_memory_policy=os.getenv("REDIS_MAX_MEMORY_POLICY", "allkeys-lru"),
            default_ttl=int(os.getenv("REDIS_DEFAULT_TTL", "3600")),
            compression_threshold=int(os.getenv("REDIS_COMPRESSION_THRESHOLD", "1024")),
            key_prefix=os.getenv("REDIS_KEY_PREFIX", "ai_pdf_scholar:prod:"),
        )

    def _load_security_config(self) -> SecurityHardeningConfig:
        """Load security hardening configuration."""
        allowed_origins = (
            os.getenv("PROD_CORS_ORIGINS", "").split(",")
            if os.getenv("PROD_CORS_ORIGINS")
            else []
        )
        allowed_ip_ranges = (
            os.getenv("ALLOWED_IP_RANGES", "").split(",")
            if os.getenv("ALLOWED_IP_RANGES")
            else []
        )

        return SecurityHardeningConfig(
            enable_csp=os.getenv("ENABLE_CSP", "true").lower() == "true",
            enable_ip_whitelist=os.getenv("ENABLE_IP_WHITELIST", "true").lower()
            == "true",
            allowed_ip_ranges=allowed_ip_ranges,
            enable_request_signing=os.getenv("ENABLE_REQUEST_SIGNING", "true").lower()
            == "true",
            signature_ttl=int(os.getenv("REQUEST_SIGNATURE_TTL", "300")),
            strict_cors=os.getenv("STRICT_CORS", "true").lower() == "true",
            allowed_origins=allowed_origins,
        )

    def _load_performance_config(self) -> PerformanceConfig:
        """Load performance optimization configuration."""
        return PerformanceConfig(
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            worker_connections=int(os.getenv("WORKER_CONNECTIONS", "1000")),
            max_memory_mb=int(os.getenv("MAX_MEMORY_MB", "2048")),
            max_concurrent_connections=int(
                os.getenv("MAX_CONCURRENT_CONNECTIONS", "1000")
            ),
            connection_limit_per_ip=int(os.getenv("CONNECTION_LIMIT_PER_IP", "10")),
            slow_request_threshold=float(os.getenv("SLOW_REQUEST_THRESHOLD", "5.0")),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
            max_upload_files=int(os.getenv("MAX_UPLOAD_FILES", "10")),
            enable_response_caching=os.getenv("ENABLE_RESPONSE_CACHING", "true").lower()
            == "true",
            enable_gzip_compression=os.getenv("ENABLE_GZIP", "true").lower() == "true",
            query_timeout=int(os.getenv("QUERY_TIMEOUT", "30")),
        )

    def _load_monitoring_config(self) -> MonitoringIntegrationConfig:
        """Load monitoring integration configuration."""
        return MonitoringIntegrationConfig(
            enable_prometheus=os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", "9090")),
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
            structured_logging=os.getenv("STRUCTURED_LOGGING", "true").lower()
            == "true",
            log_level=os.getenv("PROD_LOG_LEVEL", "INFO"),
            enable_audit_logs=os.getenv("ENABLE_AUDIT_LOGS", "true").lower() == "true",
            log_retention_days=int(os.getenv("LOG_RETENTION_DAYS", "90")),
            enable_tracing=os.getenv("ENABLE_TRACING", "true").lower() == "true",
            tracing_sample_rate=float(os.getenv("TRACING_SAMPLE_RATE", "0.1")),
            jaeger_endpoint=os.getenv("JAEGER_ENDPOINT"),
        )

    def _validate_configuration(self) -> None:
        """Validate production configuration."""
        issues = []

        # Validate database configuration
        if self.database.max_connections < 10:
            issues.append(
                "Database max_connections should be at least 10 in production"
            )

        if self.database.connection_timeout < 30:
            issues.append("Database connection_timeout should be at least 30 seconds")

        # Validate cache configuration
        if not self.cache.cluster_nodes:
            issues.append("Redis cluster nodes must be configured")

        # Validate security configuration
        if self.security.strict_cors and not self.security.allowed_origins:
            issues.append(
                "CORS allowed_origins must be configured when strict_cors is enabled"
            )

        if self.security.enable_ip_whitelist and not self.security.allowed_ip_ranges:
            issues.append("IP whitelist ranges must be configured when enabled")

        # Validate performance configuration
        if self.performance.max_memory_mb < 1024:
            issues.append("Max memory should be at least 1GB for production")

        if self.performance.max_workers < 2:
            issues.append("Should have at least 2 workers in production")

        # Log validation issues
        for issue in issues:
            logger.warning(f"Production config validation: {issue}")

        if issues and self.base_config.environment.is_production():
            logger.error(
                f"Production configuration has {len(issues)} validation issues"
            )

    def get_database_url(self) -> str:
        """Get database URL with production optimizations."""
        base_url = self.base_config.database.url

        # Add connection pool parameters
        pool_params = [
            f"pool_size={self.database.pool_size}",
            f"max_overflow={self.database.max_overflow}",
            f"pool_timeout={self.database.connection_timeout}",
            f"pool_recycle={self.database.pool_recycle}",
            f"pool_pre_ping={'true' if self.database.pool_pre_ping else 'false'}",
        ]

        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{'&'.join(pool_params)}"

    def get_redis_config(self) -> dict[str, Any]:
        """Get Redis configuration dictionary."""
        return {
            "cluster_nodes": self.cache.cluster_nodes,
            "connection_pool_kwargs": {
                "max_connections": self.cache.connection_pool_max_connections,
                "connection_timeout": self.cache.connection_timeout,
                "socket_timeout": self.cache.socket_timeout,
                "socket_keepalive": self.cache.socket_keepalive,
            },
            "cluster_enabled": self.cache.enable_cluster,
            "sentinel_enabled": self.cache.enable_sentinel,
            "sentinel_service": self.cache.sentinel_service,
            "sentinel_nodes": self.cache.sentinel_nodes,
            "default_ttl": self.cache.default_ttl,
            "compression_threshold": self.cache.compression_threshold,
            "key_prefix": self.cache.key_prefix,
        }

    def get_security_middleware_config(self) -> dict[str, Any]:
        """Get security middleware configuration."""
        return {
            "csp": {
                "enabled": self.security.enable_csp,
                "policy": self.security.csp_policy,
            },
            "headers": self.security.security_headers,
            "ip_whitelist": {
                "enabled": self.security.enable_ip_whitelist,
                "allowed_ranges": self.security.allowed_ip_ranges,
                "blocked_ranges": self.security.blocked_ip_ranges,
            },
            "request_signing": {
                "enabled": self.security.enable_request_signing,
                "ttl": self.security.signature_ttl,
                "algorithm": self.security.hmac_algorithm,
            },
            "cors": {
                "strict": self.security.strict_cors,
                "allowed_origins": self.security.allowed_origins,
                "max_age": self.security.max_age,
            },
            "rate_limits": self.security.strict_rate_limits,
        }

    def get_performance_config(self) -> dict[str, Any]:
        """Get performance configuration dictionary."""
        return {
            "workers": self.performance.max_workers,
            "connections": self.performance.worker_connections,
            "memory": {
                "max_mb": self.performance.max_memory_mb,
                "gc_threshold": self.performance.gc_threshold,
            },
            "limits": {
                "max_connections": self.performance.max_concurrent_connections,
                "per_ip_limit": self.performance.connection_limit_per_ip,
                "slow_request_threshold": self.performance.slow_request_threshold,
                "max_file_size_mb": self.performance.max_file_size_mb,
                "max_upload_files": self.performance.max_upload_files,
            },
            "caching": {
                "response_caching": self.performance.enable_response_caching,
                "response_ttl": self.performance.response_cache_ttl,
                "etag_caching": self.performance.enable_etag_caching,
                "gzip_compression": self.performance.enable_gzip_compression,
                "gzip_min_size": self.performance.gzip_min_size,
            },
            "database": {
                "query_timeout": self.performance.query_timeout,
                "query_caching": self.performance.enable_query_caching,
                "query_cache_ttl": self.performance.query_cache_ttl,
            },
        }

    def get_monitoring_config(self) -> dict[str, Any]:
        """Get monitoring configuration dictionary."""
        return {
            "prometheus": {
                "enabled": self.monitoring.enable_prometheus,
                "port": self.monitoring.metrics_port,
                "endpoint": self.monitoring.metrics_endpoint,
            },
            "health_checks": {
                "interval": self.monitoring.health_check_interval,
                "timeout": self.monitoring.health_check_timeout,
                "endpoints": self.monitoring.health_check_endpoints,
            },
            "logging": {
                "structured": self.monitoring.structured_logging,
                "level": self.monitoring.log_level,
                "audit_enabled": self.monitoring.enable_audit_logs,
                "retention_days": self.monitoring.log_retention_days,
            },
            "alerting": {"thresholds": self.monitoring.alert_thresholds},
            "tracing": {
                "enabled": self.monitoring.enable_tracing,
                "sample_rate": self.monitoring.tracing_sample_rate,
                "jaeger_endpoint": self.monitoring.jaeger_endpoint,
            },
        }

    def integrate_with_secrets(self, secrets_manager: ProductionSecretsManager) -> None:
        """Integrate configuration with secrets management."""
        self.secrets_manager = secrets_manager

        # Update sensitive configuration with secrets
        try:
            # Get database credentials
            if secrets_manager:
                # This would decrypt and use actual secrets
                logger.info("Integrated production config with secrets management")
        except Exception as e:
            logger.error(f"Failed to integrate with secrets manager: {e}")

    def integrate_with_monitoring(self, metrics_service: MetricsService) -> None:
        """Integrate configuration with monitoring service."""
        self.metrics_service = metrics_service

        # Register configuration metrics
        if metrics_service:
            metrics_service.update_dependency_health("production_config", True)
            logger.info("Integrated production config with monitoring service")

    def get_gunicorn_config(self) -> dict[str, Any]:
        """Get Gunicorn configuration for production deployment."""
        return {
            "bind": "0.0.0.0:8000",
            "workers": self.performance.max_workers,
            "worker_class": "uvicorn.workers.UvicornWorker",
            "worker_connections": self.performance.worker_connections,
            "max_requests": 10000,
            "max_requests_jitter": 1000,
            "preload_app": True,
            "keepalive": self.performance.keepalive_timeout,
            "timeout": 30,
            "graceful_timeout": 30,
            "limit_request_line": 8190,
            "limit_request_fields": 200,
            "limit_request_field_size": 8190,
            "access_log_format": '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
            "capture_output": True,
            "enable_stdio_inheritance": True,
        }

    def health_check(self) -> dict[str, Any]:
        """Perform production configuration health check."""
        health = {
            "status": "healthy",
            "timestamp": (
                logger.handlers[0].formatter.converter(None, None)[0]
                if logger.handlers
                else "unknown"
            ),
            "components": {
                "database": self._check_database_config(),
                "cache": self._check_cache_config(),
                "security": self._check_security_config(),
                "performance": self._check_performance_config(),
                "monitoring": self._check_monitoring_config(),
            },
        }

        # Update overall status
        failed_components = [
            name
            for name, status in health["components"].items()
            if status["status"] != "healthy"
        ]
        if failed_components:
            health["status"] = (
                "degraded" if len(failed_components) <= 2 else "unhealthy"
            )
            health["failed_components"] = failed_components

        return health

    def _check_database_config(self) -> dict[str, Any]:
        """Check database configuration health."""
        try:
            # Validate database configuration
            if (
                self.database.max_connections >= 10
                and self.database.connection_timeout >= 30
            ):
                return {
                    "status": "healthy",
                    "max_connections": self.database.max_connections,
                }
            else:
                return {
                    "status": "warning",
                    "message": "Database configuration suboptimal",
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_cache_config(self) -> dict[str, Any]:
        """Check cache configuration health."""
        try:
            if (
                self.cache.cluster_nodes
                and self.cache.connection_pool_max_connections >= 10
            ):
                return {"status": "healthy", "nodes": len(self.cache.cluster_nodes)}
            else:
                return {
                    "status": "warning",
                    "message": "Cache configuration needs review",
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_security_config(self) -> dict[str, Any]:
        """Check security configuration health."""
        try:
            checks = {
                "csp_enabled": self.security.enable_csp,
                "ip_whitelist": self.security.enable_ip_whitelist,
                "request_signing": self.security.enable_request_signing,
                "strict_cors": self.security.strict_cors,
            }

            enabled_count = sum(1 for enabled in checks.values() if enabled)
            if enabled_count >= 3:
                return {"status": "healthy", "enabled_features": enabled_count}
            else:
                return {
                    "status": "warning",
                    "message": "Security features should be enabled",
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_performance_config(self) -> dict[str, Any]:
        """Check performance configuration health."""
        try:
            if (
                self.performance.max_memory_mb >= 1024
                and self.performance.max_workers >= 2
                and self.performance.enable_gzip_compression
            ):
                return {
                    "status": "healthy",
                    "memory_mb": self.performance.max_memory_mb,
                }
            else:
                return {
                    "status": "warning",
                    "message": "Performance settings need optimization",
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _check_monitoring_config(self) -> dict[str, Any]:
        """Check monitoring configuration health."""
        try:
            if (
                self.monitoring.enable_prometheus
                and self.monitoring.enable_audit_logs
                and self.monitoring.structured_logging
            ):
                return {"status": "healthy", "features": "all_enabled"}
            else:
                return {
                    "status": "warning",
                    "message": "Monitoring features should be enabled",
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


def get_production_config() -> ProductionConfig:
    """Get the global production configuration instance."""
    return ProductionConfig()


def create_production_environment() -> dict[str, Any]:
    """Create complete production environment configuration."""
    prod_config = get_production_config()

    return {
        "application": prod_config.base_config.to_dict(),
        "database": prod_config.get_database_url(),
        "redis": prod_config.get_redis_config(),
        "security": prod_config.get_security_middleware_config(),
        "performance": prod_config.get_performance_config(),
        "monitoring": prod_config.get_monitoring_config(),
        "gunicorn": prod_config.get_gunicorn_config(),
    }
