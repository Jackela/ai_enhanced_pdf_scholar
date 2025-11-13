"""
Cache Service Integration
Integration service that connects the multi-layer cache system with the application.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

# Import configuration and services
from ..config.application_config import ApplicationConfig, get_application_config
from .integrated_cache_manager import (
    IntegratedCacheManager,
    create_integrated_cache_manager,
)
from .metrics_service import ApplicationMetrics
from .smart_cache_manager import SKLEARN_AVAILABLE

logger = logging.getLogger(__name__)


class CacheServiceIntegration:
    """
    Integration service for the multi-layer cache system.

    Provides a bridge between the application configuration system and
    the integrated cache manager, handling initialization, lifecycle,
    and monitoring integration.
    """

    def __init__(
        self,
        app_config: ApplicationConfig | None = None,
        metrics: ApplicationMetrics | None = None,
    ):
        """Initialize cache service integration."""
        self.app_config = app_config or get_application_config()
        self.metrics = metrics
        self.cache_manager: IntegratedCacheManager | None = None
        self._initialized = False

        logger.info("Cache Service Integration initialized")

    async def initialize(self) -> bool:
        """Initialize the integrated cache system."""
        if self._initialized:
            return True

        try:
            logger.info("Initializing integrated cache system...")

            # Check if caching is configured
            if not self.app_config.caching:
                logger.warning(
                    "Caching configuration not available, cache system disabled"
                )
                return False

            if not self._verify_ml_dependency_status():
                return False

            # Create integrated cache manager
            self.cache_manager = await create_integrated_cache_manager(
                config=self.app_config.caching, metrics=self.metrics
            )

            if not self.cache_manager:
                logger.error("Failed to create integrated cache manager")
                return False

            self._initialized = True
            logger.info("Integrated cache system initialized successfully")

            # Log configuration summary
            self._log_configuration_summary()

            return True

        except Exception as e:
            logger.error(f"Failed to initialize cache service integration: {e}")
            return False

    def _log_configuration_summary(self):
        """Log a summary of the cache configuration."""
        if not self.app_config.caching:
            return

        config_dict = self.app_config.caching.to_dict()

        logger.info("Cache Configuration Summary:")
        logger.info(
            f"  Multi-layer caching: {config_dict.get('multi_layer_enabled', False)}"
        )
        logger.info(
            f"  L1 Memory Cache: {config_dict.get('l1_cache', {}).get('enabled', False)} "
            f"({config_dict.get('l1_cache', {}).get('max_size_mb', 0)}MB)"
        )
        logger.info(
            f"  L2 Redis Cache: {config_dict.get('l2_cache', {}).get('enabled', False)} "
            f"(compression: {config_dict.get('l2_cache', {}).get('compression_enabled', False)})"
        )
        logger.info(
            f"  L3 CDN Cache: {config_dict.get('l3_cdn', {}).get('enabled', False)} "
            f"({config_dict.get('l3_cdn', {}).get('provider', 'none')})"
        )
        logger.info(
            f"  Coherency Protocol: {config_dict.get('coherency', {}).get('protocol', 'none')}"
        )
        logger.info(
            f"  Performance Monitoring: {config_dict.get('performance_monitoring', False)}"
        )
        ml_cfg = config_dict.get("ml_cache", {})
        logger.info(
            "  Smart cache ML: %s (deps required: %s)",
            ml_cfg.get("enabled", False),
            ml_cfg.get("deps_required", False),
        )

    async def get_cache_manager(self) -> IntegratedCacheManager | None:
        """Get the integrated cache manager, initializing if needed."""
        if not self._initialized:
            initialized = await self.initialize()
            if not initialized:
                return None

        return self.cache_manager

    async def shutdown(self):
        """Shutdown the cache service integration."""
        if self.cache_manager:
            await self.cache_manager.shutdown()
            self.cache_manager = None

        self._initialized = False
        logger.info("Cache service integration shutdown complete")

    def _verify_ml_dependency_status(self) -> bool:
        """Ensure ML cache configuration matches installed dependencies."""
        caching = self.app_config.caching
        if not caching:
            return True

        if not caching.enable_ml_cache:
            logger.info("Smart cache ML optimizations disabled via configuration")
            return True

        if SKLEARN_AVAILABLE:
            return True

        message = (
            "Smart cache ML optimizations are enabled but scikit-learn is not installed. "
            "Install the ML cache profile (`pip install -r requirements-scaling.txt` "
            'or `pip install ".[cache-ml]"`) or disable CACHE_ML_OPTIMIZATIONS_ENABLED.'
        )

        if caching.require_ml_dependencies:
            logger.error(
                message
                + " Set CACHE_ML_DEPS_REQUIRED=false if the strict requirement is not desired."
            )
            return False

        logger.warning(message)
        return True

    # ========================================================================
    # Cache Operations Interface
    # ========================================================================

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return default

        result = await cache_manager.get(key, default)
        return result.value if result.success else default

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set value in cache."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return False

        result = await cache_manager.set(key, value, ttl_seconds)
        return result.success

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return False

        result = await cache_manager.delete(key)
        return result.success

    async def mget(self, keys: list) -> dict[str, Any]:
        """Get multiple keys from cache."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return {}

        results = await cache_manager.mget(keys)
        return {k: r.value for k, r in results.items() if r.success}

    async def mset(self, data: dict[str, Any], ttl_seconds: int | None = None) -> bool:
        """Set multiple keys in cache."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return False

        results = await cache_manager.mset(data, ttl_seconds)
        return all(r.success for r in results.values())

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return 0

        return await cache_manager.invalidate_pattern(pattern)

    async def warm_cache(self, keys_and_values: dict[str, Any]) -> int:
        """Warm cache with provided data."""
        cache_manager = await self.get_cache_manager()
        if not cache_manager:
            return 0

        return await cache_manager.warm_cache(keys_and_values)

    # ========================================================================
    # Monitoring and Health
    # ========================================================================

    def get_statistics(self) -> dict[str, Any] | None:
        """Get cache statistics."""
        if not self.cache_manager:
            return None

        return self.cache_manager.get_statistics().to_dict()

    def get_health_status(self) -> dict[str, Any]:
        """Get cache health status."""
        if not self.cache_manager:
            return {
                "overall_status": "not_initialized",
                "cache_manager_available": False,
            }

        return self.cache_manager.get_health_status()

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()


# ============================================================================
# Global Cache Service Instance
# ============================================================================

# Global cache service instance
_cache_service: CacheServiceIntegration | None = None


async def get_cache_service(
    app_config: ApplicationConfig | None = None,
    metrics: ApplicationMetrics | None = None,
    force_recreate: bool = False,
) -> CacheServiceIntegration | None:
    """
    Get the global cache service instance.

    Args:
        app_config: Application configuration
        metrics: Metrics service
        force_recreate: Force recreation of the service

    Returns:
        CacheServiceIntegration instance or None if disabled
    """
    global _cache_service

    if _cache_service is None or force_recreate:
        if _cache_service:
            await _cache_service.shutdown()

        app_config = app_config or get_application_config()

        # Check if caching is enabled in configuration
        if not app_config.caching or not app_config.caching.enable_multi_layer:
            logger.info("Multi-layer caching is disabled in configuration")
            return None

        _cache_service = CacheServiceIntegration(app_config, metrics)
        initialized = await _cache_service.initialize()

        if not initialized:
            logger.error("Failed to initialize cache service")
            _cache_service = None
            return None

        logger.info("Global cache service initialized")

    return _cache_service


async def shutdown_cache_service():
    """Shutdown the global cache service."""
    global _cache_service

    if _cache_service:
        await _cache_service.shutdown()
        _cache_service = None
        logger.info("Global cache service shutdown")


@asynccontextmanager
async def cache_service_context(
    app_config: ApplicationConfig | None = None,
    metrics: ApplicationMetrics | None = None,
):
    """
    Async context manager for cache service.

    Usage:
        async with cache_service_context() as cache:
            if cache:
                await cache.set("key", "value")
                value = await cache.get("key")
    """
    cache_service = None
    try:
        cache_service = CacheServiceIntegration(app_config, metrics)
        initialized = await cache_service.initialize()

        if initialized:
            yield cache_service
        else:
            logger.warning("Cache service initialization failed")
            yield None

    finally:
        if cache_service:
            await cache_service.shutdown()


# ============================================================================
# FastAPI Integration Helpers
# ============================================================================


def create_cache_dependency():
    """
    Create FastAPI dependency for cache service.

    Usage:
        @app.get("/api/data")
        async def get_data(cache: CacheServiceIntegration = Depends(create_cache_dependency())):
            cached_data = await cache.get("data_key")
            if cached_data:
                return cached_data

            # Generate data and cache it
            data = generate_data()
            await cache.set("data_key", data, ttl_seconds=3600)
            return data
    """

    async def get_cache_dependency() -> CacheServiceIntegration | None:
        return await get_cache_service()

    return get_cache_dependency


def cache_response(
    key_pattern: str,
    ttl_seconds: int = 3600,
    use_l1: bool = True,
    use_l2: bool = True,
    use_l3: bool = False,
):
    """
    Decorator for caching API responses.

    Args:
        key_pattern: Cache key pattern (can include {arg} placeholders)
        ttl_seconds: Time to live in seconds
        use_l1: Use L1 memory cache
        use_l2: Use L2 Redis cache
        use_l3: Use L3 CDN cache

    Usage:
        @cache_response("user_profile_{user_id}", ttl_seconds=1800)
        async def get_user_profile(user_id: str, cache: CacheServiceIntegration = Depends(cache_dependency)):
            # Function implementation
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract cache service from kwargs
            cache_service = None
            for key, value in kwargs.items():
                if isinstance(value, CacheServiceIntegration):
                    cache_service = value
                    break

            if not cache_service:
                # No cache service available, execute function normally
                return await func(*args, **kwargs)

            # Generate cache key
            try:
                cache_key = key_pattern.format(**kwargs)
            except KeyError:
                # If key pattern formatting fails, execute without caching
                return await func(*args, **kwargs)

            # Try to get from cache
            cache_manager = await cache_service.get_cache_manager()
            if cache_manager:
                result = await cache_manager.get(
                    cache_key, use_l1=use_l1, use_l2=use_l2, use_l3=use_l3
                )

                if result.success:
                    logger.debug(
                        f"Cache hit for key: {cache_key} from {result.cache_level}"
                    )
                    return result.value

            # Cache miss, execute function
            response = await func(*args, **kwargs)

            # Cache the response
            if cache_manager and response is not None:
                await cache_manager.set(
                    cache_key,
                    response,
                    ttl_seconds=ttl_seconds,
                    write_to_l1=use_l1,
                    write_to_l2=use_l2,
                    write_to_l3=use_l3,
                )
                logger.debug(f"Cached response for key: {cache_key}")

            return response

        return wrapper

    return decorator


# ============================================================================
# Utility Functions for Cache Management
# ============================================================================


async def initialize_application_cache(
    app_config: ApplicationConfig | None = None,
    metrics: ApplicationMetrics | None = None,
) -> bool:
    """
    Initialize application-wide cache system.

    This function should be called during application startup.
    """
    try:
        cache_service = await get_cache_service(app_config, metrics)

        if cache_service:
            logger.info("Application cache system initialized successfully")
            return True
        else:
            logger.info("Cache system disabled or unavailable")
            return False

    except Exception as e:
        logger.error(f"Failed to initialize application cache: {e}")
        return False


async def shutdown_application_cache():
    """
    Shutdown application-wide cache system.

    This function should be called during application shutdown.
    """
    try:
        await shutdown_cache_service()
        logger.info("Application cache system shutdown complete")

    except Exception as e:
        logger.error(f"Error during cache system shutdown: {e}")


async def get_application_cache_status() -> dict[str, Any]:
    """Get comprehensive application cache status."""
    cache_service = await get_cache_service()

    if not cache_service:
        return {
            "cache_system_available": False,
            "reason": "Cache service not initialized or disabled",
        }

    health_status = cache_service.get_health_status()
    statistics = cache_service.get_statistics()

    return {
        "cache_system_available": True,
        "health": health_status,
        "statistics": statistics,
        "configuration": cache_service.app_config.caching.to_dict()
        if cache_service.app_config.caching
        else {},
    }
