"""
Integrated Cache Manager
Central orchestrator for multi-layer caching system with monitoring integration.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Import configuration and monitoring
from ..config.caching_config import CachingConfig
from .cache_coherency_manager import CacheCoherencyManager, CoherencyConfig
from .cache_warming_service import CacheWarmingService

# Import cache services
from .l1_memory_cache import L1MemoryCache, create_l1_cache
from .l2_redis_cache import L2RedisCache
from .l3_cdn_cache import ContentType, L3CDNCache
from .metrics_service import ApplicationMetrics
from .redis_cache_service import RedisCacheService
from .redis_cluster_manager import RedisClusterManager
from .smart_cache_manager import SmartCacheManager

logger = logging.getLogger(__name__)


@dataclass
class CacheOperationResult:
    """Result of a cache operation."""

    success: bool
    value: Any = None
    cache_level: str | None = None
    operation_time_ms: float = 0.0
    hit: bool = False
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class CacheStatistics:
    """Comprehensive cache statistics."""

    total_requests: int = 0
    total_hits: int = 0
    total_misses: int = 0

    l1_hits: int = 0
    l1_misses: int = 0
    l1_size_bytes: int = 0

    l2_hits: int = 0
    l2_misses: int = 0

    l3_hits: int = 0
    l3_misses: int = 0

    coherency_operations: int = 0
    warming_operations: int = 0

    avg_response_time_ms: float = 0.0

    def calculate_hit_rate(self) -> float:
        """Calculate overall hit rate percentage."""
        total_ops = self.total_hits + self.total_misses
        return (self.total_hits / total_ops * 100) if total_ops > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for monitoring."""
        return {
            "total_requests": self.total_requests,
            "hit_rate_percent": round(self.calculate_hit_rate(), 2),
            "l1_cache": {
                "hits": self.l1_hits,
                "misses": self.l1_misses,
                "size_bytes": self.l1_size_bytes,
                "hit_rate": round(
                    (
                        (self.l1_hits / (self.l1_hits + self.l1_misses) * 100)
                        if (self.l1_hits + self.l1_misses) > 0
                        else 0
                    ),
                    2,
                ),
            },
            "l2_cache": {
                "hits": self.l2_hits,
                "misses": self.l2_misses,
                "hit_rate": round(
                    (
                        (self.l2_hits / (self.l2_hits + self.l2_misses) * 100)
                        if (self.l2_hits + self.l2_misses) > 0
                        else 0
                    ),
                    2,
                ),
            },
            "l3_cache": {
                "hits": self.l3_hits,
                "misses": self.l3_misses,
                "hit_rate": round(
                    (
                        (self.l3_hits / (self.l3_hits + self.l3_misses) * 100)
                        if (self.l3_hits + self.l3_misses) > 0
                        else 0
                    ),
                    2,
                ),
            },
            "performance": {
                "avg_response_time_ms": round(self.avg_response_time_ms, 2),
                "coherency_operations": self.coherency_operations,
                "warming_operations": self.warming_operations,
            },
        }


class IntegratedCacheManager:
    """
    Central manager for the multi-layer caching system.

    Orchestrates L1 (memory), L2 (Redis), and L3 (CDN) caches with
    intelligent coherency management and performance monitoring.
    """

    def __init__(
        self, config: CachingConfig, metrics: ApplicationMetrics | None = None
    ) -> None:
        """Initialize integrated cache manager."""
        self.config = config
        self.metrics = metrics

        # Cache layers
        self.l1_cache: L1MemoryCache | None = None
        self.l2_cache: L2RedisCache | None = None
        self.l3_cache: L3CDNCache | None = None

        # Support services
        self.redis_cache: RedisCacheService | None = None
        self.cluster_manager: RedisClusterManager | None = None
        self.coherency_manager: CacheCoherencyManager | None = None
        self.smart_manager: SmartCacheManager | None = None
        self.warming_service: CacheWarmingService | None = None

        # Statistics and monitoring
        self.statistics = CacheStatistics()
        self.response_times: list[float] = []
        self._last_stats_update = datetime.utcnow()

        # Operational state
        self._initialized = False
        self._background_tasks: set[asyncio.Task[None]] = set[str]()

        logger.info("Integrated Cache Manager created")

    def _record_request_duration(self, start_time: float) -> None:
        """Track request duration for averages."""
        self.statistics.total_requests += 1
        duration = (time.time() - start_time) * 1000
        self.response_times.append(duration)
        if len(self.response_times) > 1000:
            self.response_times.pop(0)

    async def _write_to_l1(
        self, prefixed_key: str, value: Any, ttl_seconds: int | None
    ) -> bool:
        if not self.l1_cache:
            return False
        self.l1_cache.set[str](prefixed_key, value, ttl_seconds=ttl_seconds)
        logger.debug("Successfully wrote key %s to L1 cache", prefixed_key)
        return True

    async def _write_to_l2(
        self, prefixed_key: str, value: Any, ttl_seconds: int | None
    ) -> bool:
        if not self.l2_cache:
            return False
        success = await self.l2_cache.set[str](prefixed_key, value, ttl_seconds)
        if success:
            logger.debug("Successfully wrote key %s to L2 cache", prefixed_key)
        return success

    async def _write_to_l3(self, key: str, value: Any, ttl_seconds: int | None) -> bool:
        if not (self.l3_cache and isinstance(value, (str, bytes))):
            logger.debug("Skipping L3 cache for non-serializable value: %s", key)
            return False

        content_data = value.encode() if isinstance(value, str) else value
        cdn_url = await self.l3_cache.cache_content(
            key, content_data, ContentType.API_RESPONSES, ttl_seconds
        )
        return cdn_url != key

    async def _delete_from_l1(self, prefixed_key: str) -> bool:
        if not self.l1_cache or not self.l1_cache.exists(prefixed_key):
            return False
        self.l1_cache.delete(prefixed_key)
        return True

    async def _delete_from_l2(self, prefixed_key: str) -> bool:
        if not self.l2_cache:
            return False
        return await self.l2_cache.delete(prefixed_key)

    async def _delete_from_l3(self, key: str) -> bool:
        if not self.l3_cache:
            return False
        return await self.l3_cache.invalidate_cache([key])

    async def _run_periodic_task(
        self,
        action: Callable[[], Awaitable[float]],
        error_label: str,
        error_backoff: float,
    ) -> None:
        while self._initialized:
            try:
                interval = await action()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in %s: %s", error_label, e)
                await asyncio.sleep(error_backoff)
                continue

            await asyncio.sleep(interval)

    async def _coherency_step(self) -> float:
        if self.coherency_manager:
            await self.coherency_manager.run_coherency_check()
            self.statistics.coherency_operations += 1
        return self.config.coherency.coherency_check_interval

    async def _performance_step(self) -> float:
        await self._collect_performance_metrics()
        return self.config.metrics_collection_interval

    async def _warming_step(self) -> float:
        if self.warming_service and self.config.prefetch_popular_content:
            # Placeholder for predictive warming cadence
            return 300.0
        return 600.0

    async def _handle_cache_hit(
        self,
        value: Any,
        level: str,
        source: str,
        start_time: float,
    ) -> CacheOperationResult:
        """Common bookkeeping for cache hits."""
        operation_ms = (time.time() - start_time) * 1000
        self.statistics.total_hits += 1
        self.statistics.total_requests += 1

        if level == "L1":
            self.statistics.l1_hits += 1
        elif level == "L2":
            self.statistics.l2_hits += 1
        elif level == "L3":
            self.statistics.l3_hits += 1

        await self._update_metrics("cache_hit", level, operation_ms)

        return CacheOperationResult(
            success=True,
            value=value,
            cache_level=level,
            operation_time_ms=operation_ms,
            hit=True,
            source=source,
        )

    async def _handle_cache_miss(
        self, start_time: float, default: Any = None
    ) -> CacheOperationResult:
        """Record cache miss stats and emit result."""
        operation_ms = (time.time() - start_time) * 1000
        self.statistics.total_misses += 1
        await self._update_metrics("cache_miss", "ALL", operation_ms)
        return CacheOperationResult(
            success=False,
            value=default,
            cache_level=None,
            operation_time_ms=operation_ms,
            hit=False,
            source="miss",
        )

    async def initialize(self) -> bool:
        """Initialize all cache layers and services."""
        if self._initialized:
            return True

        try:
            logger.info("Initializing integrated cache system...")

            # Initialize Redis infrastructure
            await self._initialize_redis()

            # Initialize cache layers
            await self._initialize_cache_layers()

            # Initialize support services
            await self._initialize_support_services()

            # Start background tasks
            await self._start_background_tasks()

            self._initialized = True
            logger.info("Integrated cache system initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}", exc_info=True)
            await self.shutdown()
            return False

    async def _try_l1_get(
        self,
        prefixed_key: str,
        default: Any,
        use_l1: bool,
        start_time: float,
    ) -> CacheOperationResult | None:
        if not (use_l1 and self.l1_cache and self.l1_cache.exists(prefixed_key)):
            return None

        value = self.l1_cache.get(prefixed_key, default)
        if value == default:
            return None

        return await self._handle_cache_hit(
            value=value,
            level="L1",
            source="memory",
            start_time=start_time,
        )

    async def _try_l2_get(
        self,
        prefixed_key: str,
        default: Any,
        use_l1: bool,
        use_l2: bool,
        start_time: float,
    ) -> CacheOperationResult | None:
        if not (use_l2 and self.l2_cache):
            return None

        value = await self.l2_cache.get(prefixed_key, default)
        if value == default:
            return None

        if use_l1 and self.l1_cache:
            self.l1_cache.set[str](prefixed_key, value)

        return await self._handle_cache_hit(
            value=value,
            level="L2",
            source="redis",
            start_time=start_time,
        )

    async def _try_l3_get(
        self,
        prefixed_key: str,
        original_key: str,
        default: Any,
        use_l3: bool,
        start_time: float,
    ) -> CacheOperationResult | None:
        if not (use_l3 and self.l3_cache):
            return None

        try:
            cdn_url = await self.l3_cache.get_cached_url(
                original_key, ContentType.API_RESPONSES
            )
            if cdn_url == original_key:
                return None

            return await self._handle_cache_hit(
                value=cdn_url,
                level="L3",
                source="cdn",
                start_time=start_time,
            )
        except Exception as e:
            logger.warning(f"Error retrieving CDN cache for {prefixed_key}: {e}")
            return None

    async def _initialize_redis(self) -> None:
        """Initialize Redis infrastructure."""
        if not self.config.redis_cluster.enabled:
            logger.info("Redis cluster disabled, skipping Redis initialization")
            return

        from .redis_cache_service import RedisConfig
        from .redis_cluster_manager import RedisClusterConfig as ClusterManagerConfig

        # Create Redis configuration
        redis_config = RedisConfig(
            host=(
                self.config.redis_cluster.nodes[0]["host"]
                if self.config.redis_cluster.nodes
                else "localhost"
            ),
            port=(
                self.config.redis_cluster.nodes[0]["port"]
                if self.config.redis_cluster.nodes
                else 6379
            ),
            max_connections=self.config.redis_cluster.max_connections,
            connection_timeout=self.config.redis_cluster.timeout_seconds,
        )

        # Initialize Redis cache service
        self.redis_cache = RedisCacheService(redis_config)

        # Initialize cluster manager if in cluster mode
        if (
            self.config.redis_cluster.cluster_mode == "cluster"
            and len(self.config.redis_cluster.nodes) > 1
        ):
            cluster_config = ClusterManagerConfig(
                nodes=self.config.redis_cluster.nodes,
                replication_factor=self.config.redis_cluster.replication_factor,
            )
            self.cluster_manager = RedisClusterManager(cluster_config)

            # Initialize cluster
            cluster_initialized = await self.cluster_manager.initialize()
            if not cluster_initialized:
                logger.warning(
                    "Redis cluster initialization failed, falling back to single node"
                )

    async def _initialize_cache_layers(self) -> None:
        """Initialize cache layers (L1, L2, L3)."""

        # Initialize L1 memory cache
        if self.config.l1_cache.enabled:
            self.l1_cache = create_l1_cache(
                max_size_mb=self.config.l1_cache.max_size_mb,
                hot_data_size_mb=self.config.l1_cache.hot_data_size_mb,
                warm_data_size_mb=self.config.l1_cache.warm_data_size_mb,
                cold_data_size_mb=self.config.l1_cache.cold_data_size_mb,
                default_ttl_seconds=self.config.l1_cache.ttl_seconds,
            )
            logger.info(
                f"L1 cache initialized with {self.config.l1_cache.max_size_mb}MB"
            )

        # Initialize L2 Redis cache
        if self.config.l2_cache.enabled and self.redis_cache:
            from .l2_redis_cache import L2CacheConfig

            l2_config = L2CacheConfig(
                default_ttl_seconds=self.config.l2_cache.default_ttl_seconds,
                max_ttl_seconds=self.config.l2_cache.max_ttl_seconds,
                compression_threshold_bytes=self.config.l2_cache.compression_threshold_bytes,
                batch_size=self.config.l2_cache.batch_size,
                enable_write_behind=self.config.l2_cache.write_behind_enabled,
                write_behind_flush_interval_seconds=self.config.l2_cache.write_behind_flush_interval,
            )

            self.l2_cache = L2RedisCache(
                redis_cache=self.redis_cache,
                cluster_manager=self.cluster_manager,
                l1_cache=self.l1_cache,
                config=l2_config,
            )
            logger.info("L2 Redis cache initialized")

        # Initialize L3 CDN cache
        if self.config.l3_cdn.enabled:
            from .l3_cdn_cache import CDNConfig

            cdn_config = CDNConfig(
                provider=self.config.l3_cdn.provider,
                domain_name=self.config.l3_cdn.domain_name,
                distribution_id=self.config.l3_cdn.distribution_id,
                origin_domain=self.config.l3_cdn.origin_domain,
                aws_region=self.config.l3_cdn.aws_region,
                default_ttl_seconds=self.config.l3_cdn.default_ttl_seconds,
                enable_compression=self.config.l3_cdn.enable_compression,
                enable_ssl=self.config.l3_cdn.enable_ssl,
            )

            self.l3_cache = L3CDNCache(cdn_config)
            logger.info(
                f"L3 CDN cache initialized with provider: {self.config.l3_cdn.provider}"
            )

    async def _initialize_support_services(self) -> None:
        """Initialize support services."""

        # Initialize cache coherency manager
        if self.config.coherency.enable_monitoring:
            coherency_config = CoherencyConfig(
                protocol=self.config.coherency.protocol,
                consistency_level=self.config.coherency.consistency_level,
                invalidation_strategy=self.config.coherency.invalidation_strategy,
                max_write_delay_ms=self.config.coherency.max_write_delay_ms,
                coherency_check_interval_seconds=self.config.coherency.coherency_check_interval,
            )

            self.coherency_manager = CacheCoherencyManager(
                l1_cache=self.l1_cache,
                l2_cache=self.l2_cache,
                l3_cache=self.l3_cache,
                config=coherency_config,
            )
            logger.info("Cache coherency manager initialized")

        # Initialize smart cache manager
        if self.l2_cache and self.config.enable_ml_cache:
            self.smart_manager = SmartCacheManager(self.l2_cache)
            logger.info("Smart cache manager initialized")
        elif not self.config.enable_ml_cache:
            logger.info(
                "Smart cache manager disabled via CACHE_ML_OPTIMIZATIONS_ENABLED=false"
            )

        # Initialize cache warming service
        if self.config.enable_cache_warming and self.l2_cache:
            self.warming_service = CacheWarmingService(
                redis_cache=self.redis_cache, batch_size=self.config.warming_batch_size
            )
            logger.info("Cache warming service initialized")

    async def _start_background_tasks(self) -> None:
        """Start background monitoring and maintenance tasks."""

        # Start L2 cache write-behind if enabled
        if self.l2_cache:
            await self.l2_cache.start_write_behind()

        # Start coherency monitoring
        if self.coherency_manager:
            task = asyncio.create_task(self._coherency_monitoring_loop())
            self._background_tasks.add(task)

        # Start performance monitoring
        if self.config.enable_performance_monitoring:
            task = asyncio.create_task(self._performance_monitoring_loop())
            self._background_tasks.add(task)

        # Start cache warming
        if self.warming_service:
            task = asyncio.create_task(self._cache_warming_loop())
            self._background_tasks.add(task)

        logger.info(f"Started {len(self._background_tasks)} background tasks")

    # ========================================================================
    # Core Cache Operations
    # ========================================================================

    async def get(
        self,
        key: str,
        default: Any = None,
        use_l1: bool = True,
        use_l2: bool = True,
        use_l3: bool = False,
    ) -> CacheOperationResult:
        """
        Get value from cache with intelligent layer selection.
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        try:
            prefixed_key = self._add_key_prefix(key)

            for handler in (
                self._try_l1_get(prefixed_key, default, use_l1, start_time),
                self._try_l2_get(
                    prefixed_key,
                    default,
                    use_l1,
                    use_l2,
                    start_time,
                ),
                self._try_l3_get(
                    prefixed_key,
                    key,
                    default,
                    use_l3,
                    start_time,
                ),
            ):
                result = await handler
                if result:
                    return result

            return await self._handle_cache_miss(start_time, default)

        except Exception as e:
            logger.error(f"Error getting key {key} from cache: {e}")
            return await self._handle_cache_miss(start_time, default)

        finally:
            self._record_request_duration(start_time)

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        write_to_l1: bool = True,
        write_to_l2: bool = True,
        write_to_l3: bool = False,
    ) -> CacheOperationResult:
        """Set value in cache with multi-layer write strategy."""
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        prefixed_key = self._add_key_prefix(key)
        success_count = 0
        total_attempts = 0

        layer_operations = [
            (
                write_to_l1 and self.l1_cache,
                "L1",
                self._write_to_l1,
                (prefixed_key, value, ttl_seconds),
            ),
            (
                write_to_l2 and self.l2_cache,
                "L2",
                self._write_to_l2,
                (prefixed_key, value, ttl_seconds),
            ),
            (
                write_to_l3 and self.l3_cache,
                "L3",
                self._write_to_l3,
                (key, value, ttl_seconds),
            ),
        ]

        for enabled, layer_name, writer, args in layer_operations:
            if not enabled:
                continue
            total_attempts += 1
            try:
                if await writer(*args):
                    success_count += 1
                else:
                    logger.warning(
                        "Failed to write key %s to %s cache", key, layer_name
                    )
            except Exception as e:
                logger.warning(
                    "Failed to write key %s to %s cache: %s", key, layer_name, e
                )

        if self.coherency_manager and success_count > 0:
            try:
                await self.coherency_manager.handle_write_operation(
                    prefixed_key, value, ["L1", "L2", "L3"]
                )
                self.statistics.coherency_operations += 1
            except Exception as e:
                logger.warning("Cache coherency handling failed for key %s: %s", key, e)

        operation_success = success_count > 0
        result = CacheOperationResult(
            success=operation_success,
            value=value,
            cache_level=f"{success_count}/{total_attempts}",
            operation_time_ms=(time.time() - start_time) * 1000,
            metadata={
                "successful_layers": success_count,
                "total_layers": total_attempts,
            },
        )

        metric = "cache_set" if operation_success else "cache_error"
        await self._update_metrics(metric, "ALL", result.operation_time_ms)
        return result

    async def delete(
        self,
        key: str,
        from_l1: bool = True,
        from_l2: bool = True,
        from_l3: bool = False,
    ) -> CacheOperationResult:
        """
        Delete key from cache layers.
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        prefixed_key = self._add_key_prefix(key)
        deleted_layers = 0

        layer_deletes = [
            (from_l1 and self.l1_cache, "L1", self._delete_from_l1, (prefixed_key,)),
            (from_l2 and self.l2_cache, "L2", self._delete_from_l2, (prefixed_key,)),
            (from_l3 and self.l3_cache, "L3", self._delete_from_l3, (key,)),
        ]

        for enabled, layer_name, deleter, args in layer_deletes:
            if not enabled:
                continue
            try:
                if await deleter(*args):
                    deleted_layers += 1
                    logger.debug("Deleted key %s from %s cache", key, layer_name)
            except Exception as e:
                logger.warning(
                    "Failed to delete key %s from %s cache: %s", key, layer_name, e
                )

        if self.coherency_manager and deleted_layers > 0:
            try:
                await self.coherency_manager.handle_delete_operation(
                    prefixed_key, ["L1", "L2", "L3"]
                )
                self.statistics.coherency_operations += 1
            except Exception as e:
                logger.warning("Cache coherency handling failed for key %s: %s", key, e)

        result = CacheOperationResult(
            success=deleted_layers > 0,
            operation_time_ms=(time.time() - start_time) * 1000,
            metadata={"deleted_from_layers": deleted_layers},
        )

        metric = "cache_delete" if deleted_layers > 0 else "cache_error"
        await self._update_metrics(metric, "ALL", result.operation_time_ms)
        return result

    # ========================================================================
    # Batch Operations
    # ========================================================================

    async def mget(
        self,
        keys: list[str],
        use_l1: bool = True,
        use_l2: bool = True,
        use_l3: bool = False,
    ) -> dict[str, CacheOperationResult]:
        """Get multiple keys from cache."""
        results = {}

        # Process in smaller batches for better performance
        batch_size = self.config.l2_cache.batch_size if self.l2_cache else 50

        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[
                    self.get(key, use_l1=use_l1, use_l2=use_l2, use_l3=use_l3)
                    for key in batch_keys
                ]
            )

            results.update(dict[str, Any](zip(batch_keys, batch_results, strict=False)))

        return results

    async def mset(
        self,
        data: dict[str, Any],
        ttl_seconds: int | None = None,
        write_to_l1: bool = True,
        write_to_l2: bool = True,
        write_to_l3: bool = False,
    ) -> dict[str, CacheOperationResult]:
        """Set multiple keys in cache."""
        results = {}

        # Process in batches
        items = list[Any](data.items())
        batch_size = self.config.l2_cache.batch_size if self.l2_cache else 50

        for i in range(0, len(items), batch_size):
            batch_items = items[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[
                    self.set[str](
                        key, value, ttl_seconds, write_to_l1, write_to_l2, write_to_l3
                    )
                    for key, value in batch_items
                ]
            )

            results.update(
                dict[str, Any](zip([key for key, _ in batch_items], batch_results, strict=False))
            )

        return results

    # ========================================================================
    # Cache Management
    # ========================================================================

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        invalidated_count = 0

        try:
            # Invalidate from L1
            if self.l1_cache:
                l1_count = self.l1_cache.invalidate_pattern(pattern)
                invalidated_count += l1_count
                logger.debug(
                    f"Invalidated {l1_count} keys from L1 cache matching pattern: {pattern}"
                )

            # Invalidate from L2 (Redis pattern matching)
            if self.l2_cache and self.redis_cache:
                # Get Redis client to scan for keys
                redis_client = self.redis_cache.get_redis_client()
                if redis_client:
                    prefixed_pattern = self._add_key_prefix(pattern)
                    matching_keys = []

                    # Scan for matching keys
                    for key in redis_client.scan_iter(match=prefixed_pattern):
                        if isinstance(key, bytes):
                            key = key.decode("utf-8")
                        matching_keys.append(
                            key.replace(self.config.cache_key_prefix, "")
                        )

                    # Delete matching keys
                    for key in matching_keys:
                        result = await self.delete(
                            key, from_l1=False, from_l2=True, from_l3=False
                        )
                        if result.success:
                            invalidated_count += 1

                    logger.debug(
                        f"Invalidated {len(matching_keys)} keys from L2 cache matching pattern: {pattern}"
                    )

            return invalidated_count

        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            return invalidated_count

    async def warm_cache(self, keys_and_values: dict[str, Any]) -> int:
        """Warm cache with provided key-value pairs."""
        if not self.warming_service:
            logger.warning("Cache warming service not available")
            return 0

        try:
            warmed_count = await self.warming_service.warm_cache_batch(keys_and_values)
            self.statistics.warming_operations += warmed_count
            logger.info(f"Warmed {warmed_count} cache entries")
            return warmed_count

        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return 0

    async def cleanup_expired(self) -> dict[str, int]:
        """Clean up expired entries from all cache layers."""
        cleanup_counts = {"L1": 0, "L2": 0, "L3": 0}

        try:
            # Cleanup L1
            if self.l1_cache:
                cleanup_counts["L1"] = await self.l1_cache.cleanup_expired()

            # Cleanup L3 CDN (expired entries tracking)
            if self.l3_cache:
                await self.l3_cache.cleanup_expired_entries()
                cleanup_counts["L3"] = 1  # CDN cleanup is internal

            logger.info(f"Cleaned up expired entries: {cleanup_counts}")
            return cleanup_counts

        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return cleanup_counts

    # ========================================================================
    # Monitoring and Statistics
    # ========================================================================

    def get_statistics(self) -> CacheStatistics:
        """Get comprehensive cache statistics."""
        # Update average response time
        if self.response_times:
            self.statistics.avg_response_time_ms = sum(self.response_times) / len(
                self.response_times
            )

        # Update L1 cache size
        if self.l1_cache:
            self.statistics.l1_size_bytes = self.l1_cache.get_total_size_bytes()

        return self.statistics

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all cache components."""
        health = {
            "overall_status": "healthy",
            "initialized": self._initialized,
            "components": {
                "l1_cache": self.l1_cache is not None,
                "l2_cache": self.l2_cache is not None,
                "l3_cache": self.l3_cache is not None,
                "redis_cluster": self.cluster_manager is not None,
                "coherency_manager": self.coherency_manager is not None,
                "warming_service": self.warming_service is not None,
            },
            "background_tasks": len(self._background_tasks),
            "statistics": self.get_statistics().to_dict(),
        }

        # Check component health
        unhealthy_components = []

        if self.l1_cache:
            l1_health = self.l1_cache.get_health_status()
            health["l1_health"] = l1_health
            if not l1_health.get("healthy", False):
                unhealthy_components.append("l1_cache")

        if self.cluster_manager:
            try:
                _ = asyncio.create_task(self.cluster_manager.get_cluster_health())
                health["cluster_health"] = "checking"  # Async check
            except Exception as e:
                health["cluster_health"] = f"error: {e}"
                unhealthy_components.append("redis_cluster")

        # Overall health assessment
        if unhealthy_components:
            health["overall_status"] = "degraded"
            health["unhealthy_components"] = unhealthy_components

        return health

    async def _update_metrics(
        self, operation: str, cache_level: str, duration_ms: float
    ) -> None:
        """Update Prometheus metrics if available."""
        if self.metrics:
            try:
                # Update cache operation metrics
                self.metrics.cache_operations_total.labels(
                    operation=operation, cache_level=cache_level.lower()
                ).inc()

                self.metrics.cache_operation_duration.labels(
                    operation=operation, cache_level=cache_level.lower()
                ).observe(duration_ms / 1000)  # Convert to seconds

            except Exception as e:
                logger.warning(f"Failed to update metrics: {e}")

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _coherency_monitoring_loop(self) -> None:
        """Background task for cache coherency monitoring."""
        await self._run_periodic_task(
            self._coherency_step,
            error_label="coherency monitoring",
            error_backoff=30,
        )

    async def _performance_monitoring_loop(self) -> None:
        """Background task for performance monitoring."""
        await self._run_periodic_task(
            self._performance_step,
            error_label="performance monitoring",
            error_backoff=60,
        )

    async def _cache_warming_loop(self) -> None:
        """Background task for predictive cache warming."""
        await self._run_periodic_task(
            self._warming_step,
            error_label="cache warming",
            error_backoff=300,
        )

    async def _collect_performance_metrics(self) -> None:
        """Collect and report performance metrics."""
        try:
            stats = self.get_statistics()

            # Update Prometheus metrics
            if self.metrics:
                # Cache hit rates
                self.metrics.cache_hit_rate.labels(cache_level="l1").set[str](
                    (stats.l1_hits / (stats.l1_hits + stats.l1_misses) * 100)
                    if (stats.l1_hits + stats.l1_misses) > 0
                    else 0
                )
                self.metrics.cache_hit_rate.labels(cache_level="l2").set[str](
                    (stats.l2_hits / (stats.l2_hits + stats.l2_misses) * 100)
                    if (stats.l2_hits + stats.l2_misses) > 0
                    else 0
                )
                self.metrics.cache_hit_rate.labels(cache_level="overall").set[str](
                    stats.calculate_hit_rate()
                )

                # Cache sizes
                if self.l1_cache:
                    self.metrics.cache_size_bytes.labels(cache_level="l1").set[str](
                        stats.l1_size_bytes
                    )

                # Response times
                if self.response_times:
                    recent_times = self.response_times[-100:]  # Last 100 operations
                    avg_time = sum(recent_times) / len(recent_times)
                    self.metrics.cache_response_time.labels(cache_level="overall").set[str](
                        avg_time / 1000
                    )

            logger.debug(
                f"Performance metrics collected: hit_rate={stats.calculate_hit_rate():.1f}%"
            )

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _add_key_prefix(self, key: str) -> str:
        """Add cache key prefix."""
        if not key.startswith(self.config.cache_key_prefix):
            return f"{self.config.cache_key_prefix}{key}"
        return key

    def _remove_key_prefix(self, key: str) -> str:
        """Remove cache key prefix."""
        if key.startswith(self.config.cache_key_prefix):
            return key[len(self.config.cache_key_prefix) :]
        return key

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def shutdown(self) -> None:
        """Shutdown cache manager and cleanup resources."""
        logger.info("Shutting down integrated cache manager...")

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        # Shutdown cache layers
        if self.l2_cache:
            await self.l2_cache.stop_write_behind()

        if self.l3_cache:
            await self.l3_cache.close()

        # Shutdown cluster manager
        if self.cluster_manager:
            await self.cluster_manager.shutdown()

        self._initialized = False
        logger.info("Integrated cache manager shutdown complete")

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self) -> None:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()


# ============================================================================
# Factory Functions
# ============================================================================


async def create_integrated_cache_manager(
    config: CachingConfig | None = None, metrics: ApplicationMetrics | None = None
) -> IntegratedCacheManager:
    """
    Create and initialize integrated cache manager.

    Args:
        config: Caching configuration, if not provided will be loaded from environment
        metrics: Metrics service for monitoring integration

    Returns:
        Initialized IntegratedCacheManager instance
    """
    if config is None:
        from ..config.caching_config import get_caching_config

        config = get_caching_config()

    manager = IntegratedCacheManager(config, metrics)

    # Initialize the manager
    initialized = await manager.initialize()
    if not initialized:
        raise RuntimeError("Failed to initialize integrated cache manager")

    logger.info("Integrated cache manager created and initialized successfully")
    return manager


@asynccontextmanager
async def cache_manager_context(
    config: CachingConfig | None = None, metrics: ApplicationMetrics | None = None
) -> None:
    """
    Async context manager for integrated cache manager.

    Usage:
        async with cache_manager_context() as cache:
            result = await cache.get("key")
    """
    manager = await create_integrated_cache_manager(config, metrics)
    try:
        yield manager
    finally:
        await manager.shutdown()
