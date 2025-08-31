"""
Redis Cache Service with Intelligent Caching Strategy
Production-ready distributed caching implementation.
"""

import builtins
import hashlib
import logging
import pickle
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Union

from redis import ConnectionPool, Redis
from redis.exceptions import RedisError
from redis.sentinel import Sentinel

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Configuration
# ============================================================================

class CacheStrategy(str, Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time-based expiration
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    ADAPTIVE = "adaptive"  # Adaptive based on access patterns


class CacheLevel(str, Enum):
    """Cache levels for multi-tier caching."""
    L1_MEMORY = "l1_memory"  # In-memory cache (process local)
    L2_REDIS = "l2_redis"  # Redis cache (distributed)
    L3_DATABASE = "l3_database"  # Database cache


class RedisConfig:
    """Redis configuration."""

    def __init__(self):
        """Initialize Redis configuration from environment."""
        import os

        # Connection settings
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.password = os.getenv("REDIS_PASSWORD", None)
        self.db = int(os.getenv("REDIS_DB", "0"))
        self.ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

        # Pool settings
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        self.socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
        self.socket_connect_timeout = int(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
        self.socket_keepalive = True
        self.socket_keepalive_options = {}

        # Cluster settings
        self.cluster_enabled = os.getenv("REDIS_CLUSTER", "false").lower() == "true"
        self.cluster_nodes = os.getenv("REDIS_CLUSTER_NODES", "").split(",")

        # Sentinel settings
        self.sentinel_enabled = os.getenv("REDIS_SENTINEL", "false").lower() == "true"
        self.sentinel_hosts = os.getenv("REDIS_SENTINEL_HOSTS", "").split(",")
        self.sentinel_service = os.getenv("REDIS_SENTINEL_SERVICE", "mymaster")

        # Cache settings
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
        self.max_ttl = int(os.getenv("CACHE_MAX_TTL", "86400"))  # 24 hours
        self.compression_threshold = int(os.getenv("CACHE_COMPRESSION_THRESHOLD", "1000"))  # bytes


# ============================================================================
# Redis Cache Service
# ============================================================================

class RedisCacheService:
    """
    Comprehensive Redis cache service with intelligent caching strategies.
    """

    def __init__(self, config: RedisConfig | None = None):
        """Initialize Redis cache service."""
        self.config = config or RedisConfig()
        self._redis_client = None
        self._connection_pool = None
        self._local_cache = {}  # L1 memory cache
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }

        # Initialize Redis connection
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            if self.config.sentinel_enabled:
                # Use Redis Sentinel for high availability
                sentinels = [
                    (host.split(":")[0], int(host.split(":")[1]))
                    for host in self.config.sentinel_hosts if host
                ]
                sentinel = Sentinel(sentinels, socket_timeout=self.config.socket_timeout)
                self._redis_client = sentinel.master_for(
                    self.config.sentinel_service,
                    socket_timeout=self.config.socket_timeout,
                    password=self.config.password,
                    db=self.config.db
                )
            else:
                # Standard Redis connection
                self._connection_pool = ConnectionPool(
                    host=self.config.host,
                    port=self.config.port,
                    password=self.config.password,
                    db=self.config.db,
                    max_connections=self.config.max_connections,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    socket_keepalive=self.config.socket_keepalive,
                    socket_keepalive_options=self.config.socket_keepalive_options,
                    decode_responses=False  # Handle encoding ourselves
                )
                self._redis_client = Redis(connection_pool=self._connection_pool)

            # Test connection
            self._redis_client.ping()
            logger.info("Redis cache service initialized successfully")

        except RedisError as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self._redis_client = None

    # ========================================================================
    # Core Cache Operations
    # ========================================================================

    def get(
        self,
        key: str,
        default: Any = None,
        deserialize: bool = True
    ) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found
            deserialize: Whether to deserialize the value

        Returns:
            Cached value or default
        """
        # Check L1 memory cache first
        if key in self._local_cache:
            self._cache_stats["hits"] += 1
            return self._local_cache[key]

        if not self._redis_client:
            self._cache_stats["misses"] += 1
            return default

        try:
            value = self._redis_client.get(key)

            if value is None:
                self._cache_stats["misses"] += 1
                return default

            self._cache_stats["hits"] += 1

            # Deserialize if needed
            if deserialize:
                value = self._deserialize(value)

            # Store in L1 cache
            self._local_cache[key] = value

            return value

        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {e}")
            self._cache_stats["errors"] += 1
            return default

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        serialize: bool = True,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            serialize: Whether to serialize the value
            nx: Only set if key doesn't exist
            xx: Only set if key exists

        Returns:
            Success status
        """
        if not self._redis_client:
            return False

        try:
            # Serialize if needed
            if serialize:
                value = self._serialize(value)

            # Set TTL
            if ttl is None:
                ttl = self.config.default_ttl
            elif ttl > self.config.max_ttl:
                ttl = self.config.max_ttl

            # Set in Redis
            result = self._redis_client.set(
                key, value,
                ex=ttl if ttl > 0 else None,
                nx=nx,
                xx=xx
            )

            if result:
                # Also set in L1 cache
                self._local_cache[key] = value
                self._cache_stats["sets"] += 1

            return bool(result)

        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {e}")
            self._cache_stats["errors"] += 1
            return False

    def delete(self, *keys: str) -> int:
        """
        Delete keys from cache.

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        if not self._redis_client:
            return 0

        try:
            # Delete from L1 cache
            for key in keys:
                self._local_cache.pop(key, None)

            # Delete from Redis
            deleted = self._redis_client.delete(*keys)
            self._cache_stats["deletes"] += deleted

            return deleted

        except RedisError as e:
            logger.error(f"Redis delete error: {e}")
            self._cache_stats["errors"] += 1
            return 0

    def exists(self, *keys: str) -> int:
        """Check if keys exist in cache."""
        if not self._redis_client:
            return 0

        try:
            return self._redis_client.exists(*keys)
        except RedisError as e:
            logger.error(f"Redis exists error: {e}")
            return 0

    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for a key."""
        if not self._redis_client:
            return False

        try:
            return bool(self._redis_client.expire(key, ttl))
        except RedisError as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    # ========================================================================
    # Batch Operations
    # ========================================================================

    def mget(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache."""
        if not self._redis_client:
            return {}

        try:
            values = self._redis_client.mget(keys)
            result = {}

            for key, value in zip(keys, values, strict=False):
                if value is not None:
                    result[key] = self._deserialize(value)
                    self._cache_stats["hits"] += 1
                else:
                    self._cache_stats["misses"] += 1

            return result

        except RedisError as e:
            logger.error(f"Redis mget error: {e}")
            self._cache_stats["errors"] += 1
            return {}

    def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """Set multiple values in cache."""
        if not self._redis_client:
            return False

        try:
            # Serialize values
            serialized = {k: self._serialize(v) for k, v in mapping.items()}

            # Use pipeline for atomic operation
            with self._redis_client.pipeline() as pipe:
                pipe.mset(serialized)

                if ttl:
                    for key in serialized:
                        pipe.expire(key, ttl)

                pipe.execute()

            # Update L1 cache
            self._local_cache.update(mapping)
            self._cache_stats["sets"] += len(mapping)

            return True

        except RedisError as e:
            logger.error(f"Redis mset error: {e}")
            self._cache_stats["errors"] += 1
            return False

    # ========================================================================
    # Pattern-based Operations
    # ========================================================================

    def get_by_pattern(self, pattern: str) -> dict[str, Any]:
        """Get all keys matching a pattern."""
        if not self._redis_client:
            return {}

        try:
            keys = self._redis_client.keys(pattern)
            if not keys:
                return {}

            return self.mget([key.decode() if isinstance(key, bytes) else key for key in keys])

        except RedisError as e:
            logger.error(f"Redis pattern get error: {e}")
            return {}

    def delete_by_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self._redis_client:
            return 0

        try:
            keys = self._redis_client.keys(pattern)
            if not keys:
                return 0

            return self.delete(*[key.decode() if isinstance(key, bytes) else key for key in keys])

        except RedisError as e:
            logger.error(f"Redis pattern delete error: {e}")
            return 0

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag."""
        return self.delete_by_pattern(f"tag:{tag}:*")

    # ========================================================================
    # Advanced Cache Features
    # ========================================================================

    def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment a counter."""
        if not self._redis_client:
            return None

        try:
            return self._redis_client.incrby(key, amount)
        except RedisError as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return None

    def add_to_set(self, key: str, *values: Any) -> int:
        """Add values to a set."""
        if not self._redis_client:
            return 0

        try:
            serialized = [self._serialize(v) for v in values]
            return self._redis_client.sadd(key, *serialized)
        except RedisError as e:
            logger.error(f"Redis sadd error for key {key}: {e}")
            return 0

    def get_set_members(self, key: str) -> builtins.set[Any]:
        """Get all members of a set."""
        if not self._redis_client:
            return set()

        try:
            members = self._redis_client.smembers(key)
            return {self._deserialize(m) for m in members}
        except RedisError as e:
            logger.error(f"Redis smembers error for key {key}: {e}")
            return set()

    def add_to_sorted_set(self, key: str, mapping: dict[Any, float]) -> int:
        """Add values to a sorted set with scores."""
        if not self._redis_client:
            return 0

        try:
            # Serialize keys in mapping
            serialized = {self._serialize(k): v for k, v in mapping.items()}
            return self._redis_client.zadd(key, serialized)
        except RedisError as e:
            logger.error(f"Redis zadd error for key {key}: {e}")
            return 0

    def get_sorted_set_range(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        withscores: bool = False,
        reverse: bool = False
    ) -> Union[list[Any], list[tuple]]:
        """Get range from sorted set."""
        if not self._redis_client:
            return []

        try:
            if reverse:
                result = self._redis_client.zrevrange(key, start, end, withscores=withscores)
            else:
                result = self._redis_client.zrange(key, start, end, withscores=withscores)

            if withscores:
                return [(self._deserialize(item), score) for item, score in result]
            else:
                return [self._deserialize(item) for item in result]

        except RedisError as e:
            logger.error(f"Redis zrange error for key {key}: {e}")
            return []

    # ========================================================================
    # Cache Decorators
    # ========================================================================

    def cached(
        self,
        ttl: int | None = None,
        key_prefix: str = "",
        key_func: Callable | None = None,
        tags: list[str] | None = None,
        condition: Callable | None = None
    ):
        """
        Decorator for caching function results.

        Args:
            ttl: Time to live in seconds
            key_prefix: Prefix for cache key
            key_func: Custom function to generate cache key
            tags: Tags for cache invalidation
            condition: Function to determine if result should be cached

        Example:
            @cache.cached(ttl=3600, key_prefix="user")
            def get_user(user_id: int):
                return db.query(User).get(user_id)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [key_prefix or func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                    cache_key = ":".join(key_parts)

                # Add tags to key
                if tags:
                    for tag in tags:
                        self.add_to_set(f"tag:{tag}", cache_key)

                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Execute function
                result = func(*args, **kwargs)

                # Check if should cache
                if condition and not condition(result):
                    return result

                # Cache the result
                self.set(cache_key, result, ttl=ttl)

                return result

            # Add cache management methods
            wrapper.invalidate = lambda *args, **kwargs: self.delete(
                key_func(*args, **kwargs) if key_func else
                ":".join([key_prefix or func.__name__] + [str(arg) for arg in args])
            )

            return wrapper
        return decorator

    def cache_aside(
        self,
        key: str,
        loader: Callable,
        ttl: int | None = None
    ) -> Any:
        """
        Cache-aside pattern implementation.

        Args:
            key: Cache key
            loader: Function to load data if not in cache
            ttl: Time to live

        Returns:
            Cached or loaded value
        """
        # Try to get from cache
        value = self.get(key)
        if value is not None:
            return value

        # Load from source
        value = loader()

        # Store in cache
        if value is not None:
            self.set(key, value, ttl=ttl)

        return value

    # ========================================================================
    # Cache Warming and Preloading
    # ========================================================================

    def warm_cache(self, data: dict[str, Any], ttl: int | None = None):
        """Warm cache with pre-computed data."""
        return self.mset(data, ttl=ttl)

    def preload_pattern(
        self,
        pattern_template: str,
        ids: list[Any],
        loader: Callable,
        ttl: int | None = None
    ):
        """
        Preload cache for a pattern of keys.

        Args:
            pattern_template: Template for key pattern (e.g., "user:{}")
            ids: List of IDs to preload
            loader: Function to load data for each ID
            ttl: Time to live
        """
        data = {}
        for id_val in ids:
            key = pattern_template.format(id_val)
            value = loader(id_val)
            if value is not None:
                data[key] = value

        if data:
            self.warm_cache(data, ttl=ttl)

    # ========================================================================
    # Cache Statistics and Monitoring
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = self._cache_stats.copy()

        # Calculate hit rate
        total_requests = stats["hits"] + stats["misses"]
        stats["hit_rate"] = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        # Get Redis info
        if self._redis_client:
            try:
                redis_info = self._redis_client.info()
                stats["redis"] = {
                    "used_memory": redis_info.get("used_memory_human"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "total_commands": redis_info.get("total_commands_processed"),
                    "keyspace_hits": redis_info.get("keyspace_hits"),
                    "keyspace_misses": redis_info.get("keyspace_misses"),
                }
            except:
                pass

        return stats

    def reset_stats(self):
        """Reset cache statistics."""
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }

    def flush_all(self) -> bool:
        """Flush all cache data (use with caution)."""
        if not self._redis_client:
            return False

        try:
            self._redis_client.flushdb()
            self._local_cache.clear()
            logger.warning("All cache data flushed")
            return True
        except RedisError as e:
            logger.error(f"Redis flush error: {e}")
            return False

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        # Use pickle for complex objects
        serialized = pickle.dumps(value)

        # Compress if above threshold
        if len(serialized) > self.config.compression_threshold:
            import zlib
            serialized = b"COMPRESSED:" + zlib.compress(serialized)

        return serialized

    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage."""
        if value.startswith(b"COMPRESSED:"):
            import zlib
            value = zlib.decompress(value[11:])

        return pickle.loads(value)

    def close(self):
        """Close Redis connection."""
        if self._redis_client:
            self._redis_client.close()
        if self._connection_pool:
            self._connection_pool.disconnect()


# ============================================================================
# Intelligent Cache Strategy
# ============================================================================

class IntelligentCacheStrategy:
    """
    Intelligent caching strategy with adaptive TTL and invalidation.
    """

    def __init__(self, cache_service: RedisCacheService):
        """Initialize intelligent cache strategy."""
        self.cache = cache_service
        self.access_patterns = {}  # Track access patterns
        self.ttl_adjustments = {}  # Dynamic TTL adjustments

    def adaptive_ttl(self, key: str, base_ttl: int = 3600) -> int:
        """
        Calculate adaptive TTL based on access patterns.

        Args:
            key: Cache key
            base_ttl: Base TTL in seconds

        Returns:
            Adjusted TTL
        """
        # Get access pattern for key
        pattern = self.access_patterns.get(key, {})

        access_count = pattern.get("count", 0)

        # Adjust TTL based on access frequency
        if access_count > 100:
            # Frequently accessed - longer TTL
            return min(base_ttl * 4, 86400)  # Max 24 hours
        elif access_count > 10:
            # Moderately accessed
            return base_ttl * 2
        else:
            # Rarely accessed
            return base_ttl

    def smart_invalidation(self, entity_type: str, entity_id: Any):
        """
        Smart cache invalidation based on entity relationships.

        Args:
            entity_type: Type of entity (e.g., "user", "document")
            entity_id: Entity ID
        """
        # Define invalidation patterns
        invalidation_patterns = {
            "user": [
                f"user:{entity_id}:*",
                f"documents:user:{entity_id}:*",
                f"permissions:user:{entity_id}:*"
            ],
            "document": [
                f"document:{entity_id}:*",
                f"rag:document:{entity_id}:*",
                f"search:*{entity_id}*"
            ],
            "permission": [
                "permissions:*",
                "rbac:*"
            ]
        }

        patterns = invalidation_patterns.get(entity_type, [f"{entity_type}:{entity_id}:*"])

        for pattern in patterns:
            deleted = self.cache.delete_by_pattern(pattern)
            logger.info(f"Invalidated {deleted} cache entries for pattern: {pattern}")

    def cache_document_query(
        self,
        document_id: int,
        query: str,
        result: Any,
        ttl: int | None = None
    ) -> str:
        """
        Cache document query result with intelligent key generation.

        Args:
            document_id: Document ID
            query: Query string
            result: Query result
            ttl: Time to live

        Returns:
            Cache key
        """
        # Generate cache key with query hash
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
        cache_key = f"rag:document:{document_id}:query:{query_hash}"

        # Use adaptive TTL
        if ttl is None:
            ttl = self.adaptive_ttl(cache_key, base_ttl=7200)  # 2 hours base

        # Cache result
        self.cache.set(cache_key, result, ttl=ttl)

        # Track access pattern
        self._track_access(cache_key)

        # Add to document's query set for invalidation
        self.cache.add_to_set(f"document:{document_id}:queries", cache_key)

        return cache_key

    def _track_access(self, key: str):
        """Track access pattern for a key."""
        if key not in self.access_patterns:
            self.access_patterns[key] = {"count": 0}

        self.access_patterns[key]["count"] += 1
        self.access_patterns[key]["last_access"] = datetime.utcnow()


if __name__ == "__main__":
    # Example usage
    pass
