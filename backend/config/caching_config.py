"""
Caching Configuration Integration
Integrates advanced caching configurations with the unified application config system.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from .environment import Environment
from .validation import ConfigValidator, ConfigValidationError

logger = logging.getLogger(__name__)


@dataclass
class RedisClusterConfig:
    """Redis cluster configuration."""
    enabled: bool = True
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    cluster_mode: str = "cluster"  # cluster, sentinel, standalone
    replication_factor: int = 2
    max_connections: int = 50
    timeout_seconds: float = 5.0
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate Redis cluster configuration."""
        issues = []
        
        if self.enabled and not self.nodes:
            issues.append("Redis cluster enabled but no nodes configured")
        
        for node in self.nodes:
            if not all(key in node for key in ['host', 'port']):
                issues.append("Redis node missing required host/port configuration")
        
        if self.max_connections <= 0:
            issues.append("Redis max_connections must be positive")
        
        if environment.is_production() and self.replication_factor < 2:
            issues.append("Production Redis cluster should have replication_factor >= 2")
        
        return issues


@dataclass
class L1CacheConfig:
    """L1 memory cache configuration."""
    enabled: bool = True
    max_size_mb: float = 128.0
    hot_data_size_mb: float = 32.0
    warm_data_size_mb: float = 64.0
    cold_data_size_mb: float = 32.0
    ttl_seconds: int = 3600
    cleanup_interval_seconds: int = 60
    enable_metrics: bool = True
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate L1 cache configuration."""
        issues = []
        
        total_size = self.hot_data_size_mb + self.warm_data_size_mb + self.cold_data_size_mb
        if total_size > self.max_size_mb:
            issues.append("L1 cache level sizes exceed maximum cache size")
        
        if self.max_size_mb <= 0:
            issues.append("L1 cache max_size_mb must be positive")
        
        if environment.is_production() and self.max_size_mb > 512:
            issues.append("L1 cache size may be too large for production (>512MB)")
        
        return issues


@dataclass
class L2CacheConfig:
    """L2 Redis cache configuration."""
    enabled: bool = True
    default_ttl_seconds: int = 7200
    max_ttl_seconds: int = 86400
    compression_enabled: bool = True
    compression_threshold_bytes: int = 1024
    batch_size: int = 100
    write_behind_enabled: bool = True
    write_behind_flush_interval: int = 30
    hot_data_ttl_multiplier: float = 2.0
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate L2 cache configuration."""
        issues = []
        
        if self.default_ttl_seconds <= 0:
            issues.append("L2 cache default_ttl_seconds must be positive")
        
        if self.max_ttl_seconds < self.default_ttl_seconds:
            issues.append("L2 cache max_ttl_seconds cannot be less than default_ttl_seconds")
        
        if self.batch_size <= 0:
            issues.append("L2 cache batch_size must be positive")
        
        return issues


@dataclass 
class L3CDNConfig:
    """L3 CDN cache configuration."""
    enabled: bool = False
    provider: str = "cloudfront"
    domain_name: str = ""
    distribution_id: str = ""
    origin_domain: str = ""
    aws_region: str = "us-east-1"
    default_ttl_seconds: int = 86400
    static_assets_ttl: int = 2592000  # 30 days
    api_responses_ttl: int = 3600  # 1 hour
    enable_compression: bool = True
    enable_ssl: bool = True
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate L3 CDN configuration."""
        issues = []
        
        if self.enabled:
            if not self.domain_name:
                issues.append("CDN enabled but domain_name not configured")
            
            if self.provider == "cloudfront" and not self.distribution_id:
                issues.append("CloudFront provider requires distribution_id")
            
            if not self.origin_domain:
                issues.append("CDN enabled but origin_domain not configured")
            
            if environment.is_production() and not self.enable_ssl:
                issues.append("CDN SSL must be enabled in production")
        
        if self.default_ttl_seconds <= 0:
            issues.append("CDN default_ttl_seconds must be positive")
        
        return issues


@dataclass
class CacheCoherencyConfig:
    """Cache coherency configuration."""
    protocol: str = "write_through"
    consistency_level: str = "eventual"
    invalidation_strategy: str = "immediate"
    max_write_delay_ms: int = 100
    coherency_check_interval: int = 300
    enable_versioning: bool = True
    enable_monitoring: bool = True
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate cache coherency configuration."""
        issues = []
        
        valid_protocols = {"write_through", "write_behind", "write_back", "invalidate", "broadcast"}
        if self.protocol not in valid_protocols:
            issues.append(f"Invalid coherency protocol: {self.protocol}")
        
        valid_consistency = {"eventual", "strong", "weak", "causal"}
        if self.consistency_level not in valid_consistency:
            issues.append(f"Invalid consistency level: {self.consistency_level}")
        
        valid_invalidation = {"immediate", "lazy", "ttl_based", "version_based"}
        if self.invalidation_strategy not in valid_invalidation:
            issues.append(f"Invalid invalidation strategy: {self.invalidation_strategy}")
        
        if environment.is_production() and self.consistency_level == "weak":
            issues.append("Weak consistency not recommended for production")
        
        return issues


@dataclass
class CachingConfig:
    """
    Comprehensive caching configuration for the multi-layer cache system.
    """
    redis_cluster: RedisClusterConfig = field(default_factory=RedisClusterConfig)
    l1_cache: L1CacheConfig = field(default_factory=L1CacheConfig)
    l2_cache: L2CacheConfig = field(default_factory=L2CacheConfig)
    l3_cdn: L3CDNConfig = field(default_factory=L3CDNConfig)
    coherency: CacheCoherencyConfig = field(default_factory=CacheCoherencyConfig)
    
    # Global cache settings
    enable_multi_layer: bool = True
    cache_key_prefix: str = "pdf_scholar:"
    enable_performance_monitoring: bool = True
    metrics_collection_interval: int = 60
    
    # Cache warming and prefetching
    enable_cache_warming: bool = True
    warming_batch_size: int = 50
    prefetch_popular_content: bool = True
    
    @classmethod
    def from_environment(cls, environment: Environment) -> 'CachingConfig':
        """Create caching configuration from environment variables."""
        config = cls()
        
        # Load Redis cluster config
        config._load_redis_cluster_config(environment)
        
        # Load cache layer configs
        config._load_l1_config(environment)
        config._load_l2_config(environment)
        config._load_l3_config(environment)
        config._load_coherency_config(environment)
        
        # Load global settings
        config._load_global_config(environment)
        
        return config
    
    def _load_redis_cluster_config(self, environment: Environment):
        """Load Redis cluster configuration."""
        # Parse Redis nodes from environment
        redis_nodes = []
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        # Support both single URL and cluster configuration
        if os.getenv("REDIS_CLUSTER_NODES"):
            nodes_str = os.getenv("REDIS_CLUSTER_NODES")
            for node_str in nodes_str.split(","):
                if ":" in node_str:
                    host, port = node_str.strip().split(":")
                    redis_nodes.append({"host": host, "port": int(port)})
        else:
            # Single node configuration
            if redis_url.startswith("redis://"):
                url_parts = redis_url.replace("redis://", "").split(":")
                host = url_parts[0] if url_parts[0] else "localhost"
                port = int(url_parts[1]) if len(url_parts) > 1 and url_parts[1] else 6379
                redis_nodes.append({"host": host, "port": port})
        
        self.redis_cluster = RedisClusterConfig(
            enabled=os.getenv("REDIS_CLUSTER_ENABLED", "true").lower() == "true",
            nodes=redis_nodes,
            cluster_mode=os.getenv("REDIS_CLUSTER_MODE", "cluster"),
            replication_factor=int(os.getenv("REDIS_REPLICATION_FACTOR", "2")),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
            timeout_seconds=float(os.getenv("REDIS_TIMEOUT", "5.0")),
            health_check_interval=int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))
        )
    
    def _load_l1_config(self, environment: Environment):
        """Load L1 cache configuration."""
        # Environment-specific defaults
        if environment.is_production():
            default_size = 256.0
            hot_size = 64.0
            warm_size = 128.0
            cold_size = 64.0
        elif environment.is_testing():
            default_size = 32.0
            hot_size = 8.0
            warm_size = 16.0
            cold_size = 8.0
        else:  # development
            default_size = 128.0
            hot_size = 32.0
            warm_size = 64.0
            cold_size = 32.0
        
        self.l1_cache = L1CacheConfig(
            enabled=os.getenv("L1_CACHE_ENABLED", "true").lower() == "true",
            max_size_mb=float(os.getenv("L1_CACHE_SIZE_MB", str(default_size))),
            hot_data_size_mb=float(os.getenv("L1_HOT_SIZE_MB", str(hot_size))),
            warm_data_size_mb=float(os.getenv("L1_WARM_SIZE_MB", str(warm_size))),
            cold_data_size_mb=float(os.getenv("L1_COLD_SIZE_MB", str(cold_size))),
            ttl_seconds=int(os.getenv("L1_CACHE_TTL", "3600")),
            cleanup_interval_seconds=int(os.getenv("L1_CLEANUP_INTERVAL", "60"))
        )
    
    def _load_l2_config(self, environment: Environment):
        """Load L2 cache configuration."""
        self.l2_cache = L2CacheConfig(
            enabled=os.getenv("L2_CACHE_ENABLED", "true").lower() == "true",
            default_ttl_seconds=int(os.getenv("L2_DEFAULT_TTL", "7200")),
            max_ttl_seconds=int(os.getenv("L2_MAX_TTL", "86400")),
            compression_enabled=os.getenv("L2_COMPRESSION_ENABLED", "true").lower() == "true",
            compression_threshold_bytes=int(os.getenv("L2_COMPRESSION_THRESHOLD", "1024")),
            batch_size=int(os.getenv("L2_BATCH_SIZE", "100")),
            write_behind_enabled=os.getenv("L2_WRITE_BEHIND_ENABLED", "true").lower() == "true",
            write_behind_flush_interval=int(os.getenv("L2_WRITE_BEHIND_INTERVAL", "30"))
        )
    
    def _load_l3_config(self, environment: Environment):
        """Load L3 CDN cache configuration."""
        self.l3_cdn = L3CDNConfig(
            enabled=os.getenv("L3_CDN_ENABLED", "false").lower() == "true",
            provider=os.getenv("CDN_PROVIDER", "cloudfront"),
            domain_name=os.getenv("CDN_DOMAIN_NAME", ""),
            distribution_id=os.getenv("CLOUDFRONT_DISTRIBUTION_ID", ""),
            origin_domain=os.getenv("CDN_ORIGIN_DOMAIN", ""),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            default_ttl_seconds=int(os.getenv("CDN_DEFAULT_TTL", "86400")),
            static_assets_ttl=int(os.getenv("CDN_STATIC_TTL", "2592000")),
            api_responses_ttl=int(os.getenv("CDN_API_TTL", "3600")),
            enable_compression=os.getenv("CDN_COMPRESSION", "true").lower() == "true",
            enable_ssl=os.getenv("CDN_SSL", "true").lower() == "true"
        )
    
    def _load_coherency_config(self, environment: Environment):
        """Load cache coherency configuration."""
        self.coherency = CacheCoherencyConfig(
            protocol=os.getenv("CACHE_COHERENCY_PROTOCOL", "write_through"),
            consistency_level=os.getenv("CACHE_CONSISTENCY_LEVEL", "eventual"),
            invalidation_strategy=os.getenv("CACHE_INVALIDATION_STRATEGY", "immediate"),
            max_write_delay_ms=int(os.getenv("CACHE_MAX_WRITE_DELAY", "100")),
            coherency_check_interval=int(os.getenv("CACHE_COHERENCY_CHECK_INTERVAL", "300")),
            enable_versioning=os.getenv("CACHE_VERSIONING_ENABLED", "true").lower() == "true",
            enable_monitoring=os.getenv("CACHE_MONITORING_ENABLED", "true").lower() == "true"
        )
    
    def _load_global_config(self, environment: Environment):
        """Load global cache configuration."""
        self.enable_multi_layer = os.getenv("MULTI_LAYER_CACHE_ENABLED", "true").lower() == "true"
        self.cache_key_prefix = os.getenv("CACHE_KEY_PREFIX", f"pdf_scholar:{environment.value}:")
        self.enable_performance_monitoring = os.getenv("CACHE_PERFORMANCE_MONITORING", "true").lower() == "true"
        self.metrics_collection_interval = int(os.getenv("CACHE_METRICS_INTERVAL", "60"))
        
        # Cache warming settings
        self.enable_cache_warming = os.getenv("CACHE_WARMING_ENABLED", "true").lower() == "true"
        self.warming_batch_size = int(os.getenv("CACHE_WARMING_BATCH_SIZE", "50"))
        self.prefetch_popular_content = os.getenv("CACHE_PREFETCH_POPULAR", "true").lower() == "true"
    
    def validate(self, environment: Environment) -> List[str]:
        """Validate entire caching configuration."""
        all_issues = []
        
        # Validate each configuration section
        for config_name, config_obj in [
            ("redis_cluster", self.redis_cluster),
            ("l1_cache", self.l1_cache),
            ("l2_cache", self.l2_cache),
            ("l3_cdn", self.l3_cdn),
            ("coherency", self.coherency)
        ]:
            if hasattr(config_obj, 'validate'):
                issues = config_obj.validate(environment)
                for issue in issues:
                    all_issues.append(f"{config_name}: {issue}")
        
        # Cross-configuration validation
        if self.enable_multi_layer:
            if not self.l1_cache.enabled and not self.l2_cache.enabled:
                all_issues.append("Multi-layer caching enabled but no cache layers configured")
        
        if self.l3_cdn.enabled and not self.l2_cache.enabled:
            all_issues.append("L3 CDN cache requires L2 cache to be enabled")
        
        # Performance validation
        if (self.l1_cache.enabled and self.l1_cache.max_size_mb > 1024 and 
            environment.is_production()):
            all_issues.append("L1 cache size >1GB may impact application memory usage")
        
        return all_issues
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "multi_layer_enabled": self.enable_multi_layer,
            "cache_key_prefix": self.cache_key_prefix,
            "performance_monitoring": self.enable_performance_monitoring,
            "redis_cluster": {
                "enabled": self.redis_cluster.enabled,
                "nodes_count": len(self.redis_cluster.nodes),
                "cluster_mode": self.redis_cluster.cluster_mode,
                "replication_factor": self.redis_cluster.replication_factor
            },
            "l1_cache": {
                "enabled": self.l1_cache.enabled,
                "max_size_mb": self.l1_cache.max_size_mb,
                "ttl_seconds": self.l1_cache.ttl_seconds
            },
            "l2_cache": {
                "enabled": self.l2_cache.enabled,
                "default_ttl": self.l2_cache.default_ttl_seconds,
                "compression_enabled": self.l2_cache.compression_enabled,
                "write_behind_enabled": self.l2_cache.write_behind_enabled
            },
            "l3_cdn": {
                "enabled": self.l3_cdn.enabled,
                "provider": self.l3_cdn.provider,
                "domain_configured": bool(self.l3_cdn.domain_name),
                "ssl_enabled": self.l3_cdn.enable_ssl
            },
            "coherency": {
                "protocol": self.coherency.protocol,
                "consistency_level": self.coherency.consistency_level,
                "versioning_enabled": self.coherency.enable_versioning
            }
        }


def get_caching_config(environment: Optional[Environment] = None) -> CachingConfig:
    """
    Get caching configuration for the specified environment.
    
    Args:
        environment: Environment instance, if not provided will be detected
        
    Returns:
        CachingConfig instance
    """
    if environment is None:
        from .environment import get_current_environment
        environment = get_current_environment()
    
    config = CachingConfig.from_environment(environment)
    
    # Validate configuration
    issues = config.validate(environment)
    if issues:
        for issue in issues:
            logger.warning(f"Caching configuration issue: {issue}")
        
        # Raise error for critical issues in production
        critical_keywords = ["must", "required", "invalid", "not allowed"]
        critical_issues = [
            issue for issue in issues 
            if any(keyword in issue.lower() for keyword in critical_keywords)
        ]
        
        if critical_issues and environment.requires_strict_security():
            raise ConfigValidationError(
                "Critical caching configuration issues found",
                issues=critical_issues
            )
    
    return config