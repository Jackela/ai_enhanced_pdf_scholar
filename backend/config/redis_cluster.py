"""
Redis Cluster Configuration and Management
High-availability Redis cluster setup with failover, connection pooling,
and distributed caching strategies for production deployment.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

try:
    import redis
    import redis.asyncio as aioredis
    from redis.cluster import RedisCluster
    from redis.exceptions import (
        ConnectionError as RedisConnectionError,
    )
    from redis.exceptions import (
        TimeoutError as RedisTimeoutError,
    )
    from redis.sentinel import Sentinel

    REDIS_AVAILABLE = True
except ImportError:
    # Redis is optional - gracefully handle when not installed
    redis = None
    aioredis = None
    RedisCluster = None
    RedisConnectionError = Exception
    RedisTimeoutError = Exception
    Sentinel = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


def check_redis_availability() -> Any:
    """Check if Redis is available and log status."""
    if not REDIS_AVAILABLE:
        logger.warning(
            "Redis package not installed. Redis cluster features will be disabled."
        )
        return False
    return True


class RedisBackendType(str, Enum):
    """Redis backend deployment types."""

    STANDALONE = "standalone"
    CLUSTER = "cluster"
    SENTINEL = "sentinel"


class CacheEvictionPolicy(str, Enum):
    """Redis cache eviction policies."""

    ALLKEYS_LRU = "allkeys-lru"
    VOLATILE_LRU = "volatile-lru"
    ALLKEYS_LFU = "allkeys-lfu"
    VOLATILE_LFU = "volatile-lfu"
    ALLKEYS_RANDOM = "allkeys-random"
    VOLATILE_RANDOM = "volatile-random"
    VOLATILE_TTL = "volatile-ttl"
    NOEVICTION = "noeviction"


@dataclass
class RedisNodeConfig:
    """Configuration for a Redis node."""

    host: str
    port: int = 6379
    password: str | None = None
    db: int = 0
    ssl: bool = False
    ssl_cert_reqs: str | None = None
    ssl_ca_certs: str | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    weight: int = 1  # For load balancing


@dataclass
class ConnectionPoolConfig:
    """Redis connection pool configuration."""

    max_connections: int = 50
    connection_timeout: float = 5.0
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    socket_keepalive: bool = True
    socket_keepalive_options: dict[str, int] = field(
        default_factory=lambda: {
            1: 1,  # TCP_KEEPIDLE
            2: 3,  # TCP_KEEPINTVL
            3: 5,  # TCP_KEEPCNT
        }
    )
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    max_connections_per_node: int = 10


@dataclass
class ClusterConfig:
    """Redis cluster configuration."""

    startup_nodes: list[RedisNodeConfig] = field(default_factory=list)
    max_connections: int = 50
    skip_full_coverage_check: bool = False
    require_full_coverage: bool = True
    reinitialize_steps: int = 10
    read_from_replicas: bool = True
    cluster_error_retry_attempts: int = 3
    cluster_error_retry_delay: float = 0.25


@dataclass
class SentinelConfig:
    """Redis Sentinel configuration."""

    sentinel_nodes: list[tuple[str, int]] = field(default_factory=list)
    service_name: str = "mymaster"
    socket_timeout: float = 0.5
    sentinel_kwargs: dict[str, Any] = field(default_factory=dict)
    password: str | None = None
    db: int = 0


@dataclass
class CachingConfig:
    """Caching behavior configuration."""

    default_ttl: int = 3600
    max_ttl: int = 86400
    key_prefix: str = "ai_pdf_scholar:"
    compression_threshold: int = 1024
    compression_level: int = 6
    serialization_format: str = "json"  # json, msgpack
    enable_pipelining: bool = True
    pipeline_buffer_size: int = 100

    # Memory optimization
    max_memory: str = "2gb"
    eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.ALLKEYS_LRU

    # Performance tuning
    lazy_free: bool = True  # Non-blocking deletes
    enable_keyspace_notifications: bool = False
    hash_max_ziplist_entries: int = 512
    hash_max_ziplist_value: int = 64


class RedisClusterManager:
    """
    Production-ready Redis cluster manager with high availability,
    connection pooling, and intelligent failover capabilities.
    """

    def __init__(
        self,
        backend_type: RedisBackendType = RedisBackendType.STANDALONE,
        nodes: list[RedisNodeConfig] | None = None,
        pool_config: ConnectionPoolConfig | None = None,
        cluster_config: ClusterConfig | None = None,
        sentinel_config: SentinelConfig | None = None,
        caching_config: CachingConfig | None = None,
    ) -> None:
        """Initialize Redis cluster manager."""
        self.backend_type = backend_type
        self.nodes = nodes or [RedisNodeConfig("localhost", 6379)]
        self.pool_config = pool_config or ConnectionPoolConfig()
        self.cluster_config = cluster_config or ClusterConfig()
        self.sentinel_config = sentinel_config or SentinelConfig()
        self.caching_config = caching_config or CachingConfig()

        # Connection management
        self._redis_client: redis.Redis | RedisCluster | None = None
        self._async_redis_client: aioredis.Redis | aioredis.RedisCluster | None = None
        self._connection_pools: dict[str, redis.ConnectionPool] = {}
        self._health_status: dict[str, bool] = {}

        # Failover and load balancing
        self._current_master: RedisNodeConfig | None = None
        self._available_nodes: list[RedisNodeConfig] = []
        self._failed_nodes: list[RedisNodeConfig] = []
        self._last_health_check: float = 0

        # Performance monitoring
        self._connection_stats: dict[str, dict[str, int]] = {}
        self._operation_metrics: dict[str, list[float]] = {
            "response_times": [],
            "error_rates": [],
            "throughput": [],
        }

        logger.info(f"Initialized RedisClusterManager with {backend_type} backend")

    async def initialize(self) -> None:
        """Initialize Redis connections based on backend type."""
        try:
            if self.backend_type == RedisBackendType.STANDALONE:
                await self._initialize_standalone()
            elif self.backend_type == RedisBackendType.CLUSTER:
                await self._initialize_cluster()
            elif self.backend_type == RedisBackendType.SENTINEL:
                await self._initialize_sentinel()

            # Start health monitoring
            asyncio.create_task(self._health_monitor())

            logger.info(f"Successfully initialized {self.backend_type} Redis backend")
        except Exception as e:
            logger.error(f"Failed to initialize Redis backend: {e}")
            raise

    async def _initialize_standalone(self) -> None:
        """Initialize standalone Redis connection."""
        primary_node = self.nodes[0]

        # Create connection pool
        pool = redis.ConnectionPool(
            host=primary_node.host,
            port=primary_node.port,
            password=primary_node.password,
            db=primary_node.db,
            max_connections=self.pool_config.max_connections,
            socket_timeout=self.pool_config.socket_timeout,
            socket_connect_timeout=self.pool_config.socket_connect_timeout,
            socket_keepalive=self.pool_config.socket_keepalive,
            socket_keepalive_options=self.pool_config.socket_keepalive_options,
            retry_on_timeout=self.pool_config.retry_on_timeout,
            ssl=primary_node.ssl,
            ssl_cert_reqs=primary_node.ssl_cert_reqs,
            ssl_ca_certs=primary_node.ssl_ca_certs,
            ssl_certfile=primary_node.ssl_certfile,
            ssl_keyfile=primary_node.ssl_keyfile,
        )

        # Create Redis clients
        self._redis_client = redis.Redis(connection_pool=pool)
        self._async_redis_client = aioredis.Redis(
            host=primary_node.host,
            port=primary_node.port,
            password=primary_node.password,
            db=primary_node.db,
            socket_timeout=self.pool_config.socket_timeout,
            socket_connect_timeout=self.pool_config.socket_connect_timeout,
            socket_keepalive=self.pool_config.socket_keepalive,
            socket_keepalive_options=self.pool_config.socket_keepalive_options,
            max_connections=self.pool_config.max_connections,
            ssl=primary_node.ssl,
        )

        # Test connection
        await self._async_redis_client.ping()
        self._current_master = primary_node
        self._available_nodes = [primary_node]

    async def _initialize_cluster(self) -> None:
        """Initialize Redis cluster connection."""
        startup_nodes = [
            {"host": node.host, "port": node.port, "password": node.password}
            for node in self.cluster_config.startup_nodes or self.nodes
        ]

        # Create cluster client
        self._redis_client = RedisCluster(
            startup_nodes=startup_nodes,
            max_connections=self.cluster_config.max_connections,
            skip_full_coverage_check=self.cluster_config.skip_full_coverage_check,
            require_full_coverage=self.cluster_config.require_full_coverage,
            socket_timeout=self.pool_config.socket_timeout,
            socket_connect_timeout=self.pool_config.socket_connect_timeout,
            socket_keepalive=self.pool_config.socket_keepalive,
            socket_keepalive_options=self.pool_config.socket_keepalive_options,
            read_from_replicas=self.cluster_config.read_from_replicas,
        )

        # Create async cluster client
        self._async_redis_client = aioredis.RedisCluster(
            startup_nodes=startup_nodes,
            max_connections=self.cluster_config.max_connections,
            socket_timeout=self.pool_config.socket_timeout,
            socket_connect_timeout=self.pool_config.socket_connect_timeout,
            skip_full_coverage_check=self.cluster_config.skip_full_coverage_check,
        )

        # Test cluster connection
        await self._async_redis_client.ping()
        self._available_nodes = self.cluster_config.startup_nodes or self.nodes

    async def _initialize_sentinel(self) -> None:
        """Initialize Redis Sentinel connection."""
        sentinel = Sentinel(
            self.sentinel_config.sentinel_nodes,
            socket_timeout=self.sentinel_config.socket_timeout,
            **self.sentinel_config.sentinel_kwargs,
        )

        # Discover master
        master = sentinel.master_for(
            self.sentinel_config.service_name,
            password=self.sentinel_config.password,
            db=self.sentinel_config.db,
            socket_timeout=self.pool_config.socket_timeout,
            socket_connect_timeout=self.pool_config.socket_connect_timeout,
            socket_keepalive=self.pool_config.socket_keepalive,
            socket_keepalive_options=self.pool_config.socket_keepalive_options,
        )

        self._redis_client = master

        # Create async sentinel client
        async_sentinel = aioredis.Sentinel(self.sentinel_config.sentinel_nodes)
        self._async_redis_client = async_sentinel.master_for(
            self.sentinel_config.service_name,
            password=self.sentinel_config.password,
            db=self.sentinel_config.db,
        )

        # Test sentinel connection
        await self._async_redis_client.ping()

    async def _health_monitor(self) -> None:
        """Background health monitoring for all nodes."""
        while True:
            try:
                await self._check_node_health()
                await self._update_connection_stats()
                await asyncio.sleep(self.pool_config.health_check_interval)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.pool_config.health_check_interval)

    async def _check_node_health(self) -> None:
        """Check health of all Redis nodes."""
        if self.backend_type == RedisBackendType.CLUSTER:
            # For cluster, check all nodes
            for node in self._available_nodes:
                try:
                    client = aioredis.Redis(
                        host=node.host,
                        port=node.port,
                        password=node.password,
                        socket_timeout=2.0,
                    )
                    await client.ping()
                    self._health_status[f"{node.host}:{node.port}"] = True
                    await client.aclose()
                except Exception:
                    self._health_status[f"{node.host}:{node.port}"] = False
        else:
            # For standalone/sentinel, check primary connection
            try:
                await self._async_redis_client.ping()
                if self._current_master:
                    self._health_status[
                        f"{self._current_master.host}:{self._current_master.port}"
                    ] = True
            except Exception:
                if self._current_master:
                    self._health_status[
                        f"{self._current_master.host}:{self._current_master.port}"
                    ] = False

        self._last_health_check = time.time()

    async def _update_connection_stats(self) -> None:
        """Update connection pool statistics."""
        if self.backend_type == RedisBackendType.STANDALONE and self._redis_client:
            pool = self._redis_client.connection_pool
            node_key = f"{self._current_master.host}:{self._current_master.port}"

            self._connection_stats[node_key] = {
                "created_connections": pool.created_connections,
                "available_connections": len(pool._available_connections),
                "in_use_connections": len(pool._in_use_connections),
            }

    # ========================================================================
    # Core Redis Operations with Failover
    # ========================================================================

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value with automatic failover and retries."""
        full_key = f"{self.caching_config.key_prefix}{key}"

        for attempt in range(3):
            try:
                start_time = time.time()
                value = await self._async_redis_client.get(full_key)

                # Record metrics
                response_time = time.time() - start_time
                self._operation_metrics["response_times"].append(response_time)

                if value is None:
                    return default

                # Decompress and deserialize if needed
                return self._deserialize(value)

            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Redis get failed (attempt {attempt + 1}): {e}")
                if attempt == 2:  # Last attempt
                    await self._handle_connection_error()
                    return default
                await asyncio.sleep(0.1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Redis get error for key {key}: {e}")
                return default

        return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Set value with automatic failover and retries."""
        full_key = f"{self.caching_config.key_prefix}{key}"
        ttl = ttl or self.caching_config.default_ttl

        # Serialize and compress if needed
        serialized_value = self._serialize(value)

        for attempt in range(3):
            try:
                start_time = time.time()

                result = await self._async_redis_client.set(
                    full_key, serialized_value, ex=ttl, nx=nx, xx=xx
                )

                # Record metrics
                response_time = time.time() - start_time
                self._operation_metrics["response_times"].append(response_time)

                return bool(result)

            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Redis set failed (attempt {attempt + 1}): {e}")
                if attempt == 2:  # Last attempt
                    await self._handle_connection_error()
                    return False
                await asyncio.sleep(0.1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Redis set error for key {key}: {e}")
                return False

        return False

    async def delete(self, *keys: str) -> int:
        """Delete keys with automatic failover."""
        full_keys = [f"{self.caching_config.key_prefix}{key}" for key in keys]

        try:
            return await self._async_redis_client.delete(*full_keys)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis delete failed: {e}")
            await self._handle_connection_error()
            return 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return 0

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        full_keys = [f"{self.caching_config.key_prefix}{key}" for key in keys]

        try:
            return await self._async_redis_client.exists(*full_keys)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis exists failed: {e}")
            await self._handle_connection_error()
            return 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set key expiration."""
        full_key = f"{self.caching_config.key_prefix}{key}"

        try:
            return await self._async_redis_client.expire(full_key, ttl)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis expire failed: {e}")
            await self._handle_connection_error()
            return False
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False

    # ========================================================================
    # Advanced Operations
    # ========================================================================

    @asynccontextmanager
    async def pipeline(self) -> AsyncIterator[Any]:  # Fixed: aioredis pipeline type
        """Context manager for Redis pipeline operations."""
        if not self.caching_config.enable_pipelining:
            yield None
            return

        try:
            pipeline = self._async_redis_client.pipeline(transaction=False)
            yield pipeline
            await pipeline.execute()
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")

    async def mget(self, *keys: str) -> list[Any]:
        """Get multiple values efficiently."""
        full_keys = [f"{self.caching_config.key_prefix}{key}" for key in keys]

        try:
            values = await self._async_redis_client.mget(*full_keys)
            return [self._deserialize(value) if value else None for value in values]
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            return [None] * len(keys)

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """Set multiple values efficiently."""
        full_mapping = {
            f"{self.caching_config.key_prefix}{key}": self._serialize(value)
            for key, value in mapping.items()
        }

        try:
            async with self.pipeline() as pipe:
                if pipe:
                    await pipe.mset(full_mapping)
                    if ttl:
                        for key in full_mapping:
                            await pipe.expire(key, ttl)
                    return True
                else:
                    # Fallback to individual sets
                    results = []
                    for key, value in mapping.items():
                        results.append(await self.set(key, value, ttl))
                    return all(results)
        except Exception as e:
            logger.error(f"Redis mset error: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment a counter."""
        full_key = f"{self.caching_config.key_prefix}{key}"

        try:
            return await self._async_redis_client.incr(full_key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return None

    async def get_stats(self) -> dict[str, Any]:
        """Get Redis cluster statistics."""
        stats = {
            "backend_type": self.backend_type.value,
            "health_status": dict(self._health_status),
            "connection_stats": dict(self._connection_stats),
            "last_health_check": self._last_health_check,
            "available_nodes": len(self._available_nodes),
            "failed_nodes": len(self._failed_nodes),
        }

        # Add performance metrics
        if self._operation_metrics["response_times"]:
            response_times = self._operation_metrics["response_times"][
                -100:
            ]  # Last 100
            stats["performance"] = {
                "avg_response_time": sum(response_times) / len(response_times),
                "max_response_time": max(response_times),
                "min_response_time": min(response_times),
            }

        return stats

    # ========================================================================
    # Serialization and Compression
    # ========================================================================

    def _serialize(self, value: Any) -> bytes:
        """Serialize value based on configuration."""
        import json

        try:
            format_name = (self.caching_config.serialization_format or "json").lower()
            if format_name == "json":
                serialized = json.dumps(value).encode()
            elif format_name == "msgpack":
                import msgpack

                serialized = msgpack.packb(value)
            else:
                raise ValueError(f"Unsupported serialization format: {format_name}")

            # Compress if above threshold
            if len(serialized) > self.caching_config.compression_threshold:
                import zlib

                serialized = b"COMPRESSED:" + zlib.compress(
                    serialized, self.caching_config.compression_level
                )

            return serialized

        except Exception as e:
            logger.error(f"Serialization error: {e}")
            return b""

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value based on configuration."""
        import json

        try:
            # Check if compressed
            if data.startswith(b"COMPRESSED:"):
                import zlib

                data = zlib.decompress(data[11:])  # Remove "COMPRESSED:" prefix

            format_name = (self.caching_config.serialization_format or "json").lower()
            if format_name == "json":
                return json.loads(data.decode())
            elif format_name == "msgpack":
                import msgpack

                return msgpack.unpackb(data, raw=False)
            raise ValueError(f"Unsupported serialization format: {format_name}")

        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            return None

    # ========================================================================
    # Connection Management and Failover
    # ========================================================================

    async def _handle_connection_error(self) -> None:
        """Handle connection errors and attempt failover."""
        if self.backend_type == RedisBackendType.SENTINEL:
            # Sentinel handles failover automatically
            try:
                await self._async_redis_client.ping()
                logger.info("Sentinel failover completed successfully")
            except Exception as e:
                logger.error(f"Sentinel failover failed: {e}")
        elif self.backend_type == RedisBackendType.CLUSTER:
            # Cluster handles node failures automatically
            try:
                await self._async_redis_client.ping()
                logger.info("Cluster node failover completed")
            except Exception as e:
                logger.error(f"Cluster failover failed: {e}")
        else:
            # For standalone, try to reconnect
            await self._reconnect_standalone()

    async def _reconnect_standalone(self) -> None:
        """Reconnect to standalone Redis."""
        if len(self.nodes) > 1:
            # Try other nodes
            for node in self.nodes:
                if node != self._current_master:
                    try:
                        client = aioredis.Redis(
                            host=node.host,
                            port=node.port,
                            password=node.password,
                            db=node.db,
                        )
                        await client.ping()

                        # Update current master
                        self._current_master = node
                        self._async_redis_client = client
                        logger.info(
                            f"Failed over to Redis node {node.host}:{node.port}"
                        )
                        return

                    except Exception as exc:
                        logger.warning(
                            "Failed to failover to Redis node %s:%s: %s",
                            node.host,
                            node.port,
                            exc,
                        )
                        continue

            logger.error("All Redis nodes are unavailable")
        else:
            logger.error("Single Redis node unavailable, no failover possible")

    async def close(self) -> None:
        """Close all Redis connections."""
        try:
            if self._async_redis_client:
                await self._async_redis_client.aclose()
            if self._redis_client:
                self._redis_client.close()
            logger.info("Redis connections closed")
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")


# ============================================================================
# Factory Functions
# ============================================================================


def create_redis_cluster_manager(
    nodes: list[str],
    backend_type: str = "standalone",
    max_connections: int = 50,
    **kwargs,
) -> RedisClusterManager:
    """
    Factory function to create Redis cluster manager.

    Args:
        nodes: List of Redis node URLs (redis://host:port)
        backend_type: Type of Redis deployment (standalone/cluster/sentinel)
        max_connections: Maximum connections per pool
        **kwargs: Additional configuration options

    Returns:
        Configured RedisClusterManager instance
    """
    # Parse node URLs
    redis_nodes = []
    for node_url in nodes:
        if node_url.startswith("redis://"):
            url_parts = node_url[8:].split(":")
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 6379
        else:
            url_parts = node_url.split(":")
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 6379

        redis_nodes.append(RedisNodeConfig(host=host, port=port))

    # Create configuration
    pool_config = ConnectionPoolConfig(max_connections=max_connections)
    caching_config = CachingConfig(
        **{k: v for k, v in kwargs.items() if k in CachingConfig.__dataclass_fields__}
    )

    if backend_type == "cluster":
        cluster_config = ClusterConfig(startup_nodes=redis_nodes)
        return RedisClusterManager(
            backend_type=RedisBackendType.CLUSTER,
            nodes=redis_nodes,
            pool_config=pool_config,
            cluster_config=cluster_config,
            caching_config=caching_config,
        )
    elif backend_type == "sentinel":
        sentinel_nodes = [(node.host, node.port) for node in redis_nodes]
        sentinel_config = SentinelConfig(sentinel_nodes=sentinel_nodes)
        return RedisClusterManager(
            backend_type=RedisBackendType.SENTINEL,
            nodes=redis_nodes,
            pool_config=pool_config,
            sentinel_config=sentinel_config,
            caching_config=caching_config,
        )
    else:
        return RedisClusterManager(
            backend_type=RedisBackendType.STANDALONE,
            nodes=redis_nodes,
            pool_config=pool_config,
            caching_config=caching_config,
        )


async def main() -> None:
    """Example usage of Redis cluster manager."""
    # Create cluster manager
    manager = create_redis_cluster_manager(
        nodes=["redis://localhost:6379"],
        backend_type="standalone",
        max_connections=20,
        default_ttl=3600,
    )

    # Initialize
    await manager.initialize()

    # Test operations
    await manager.set("test_key", {"message": "Hello, Redis!"}, ttl=60)
    value = await manager.get("test_key")
    print(f"Retrieved value: {value}")

    # Get statistics
    stats = await manager.get_stats()
    print(f"Redis stats: {stats}")

    # Clean up
    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
