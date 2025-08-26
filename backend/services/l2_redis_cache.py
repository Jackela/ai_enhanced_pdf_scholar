"""
L2 Redis Cache Service
Distributed L2 cache with intelligent data management and cluster support.
"""

import asyncio
import hashlib
import logging
import pickle
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .l1_memory_cache import CacheLevel, L1MemoryCache

# Import our services
from .redis_cache_service import RedisCacheService
from .redis_cluster_manager import RedisClusterManager

logger = logging.getLogger(__name__)


# ============================================================================
# L2 Cache Configuration
# ============================================================================

class DistributionStrategy(str, Enum):
    """Data distribution strategies for L2 cache."""
    HASH_RING = "hash_ring"  # Consistent hashing
    SHARDED = "sharded"  # Range-based sharding
    REPLICATED = "replicated"  # Full replication
    HYBRID = "hybrid"  # Combination of strategies


class CompressionLevel(str, Enum):
    """Data compression levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class L2CacheConfig:
    """Configuration for L2 Redis cache."""
    # Distribution
    distribution_strategy: DistributionStrategy = DistributionStrategy.HASH_RING
    replication_factor: int = 2

    # Compression
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    compression_threshold_bytes: int = 1024  # Compress items > 1KB

    # TTL and expiration
    default_ttl_seconds: int = 7200  # 2 hours
    max_ttl_seconds: int = 86400  # 24 hours
    ttl_jitter_percent: int = 10  # Add random jitter to prevent thundering herd

    # Performance
    batch_size: int = 100  # Batch operations size
    pipeline_size: int = 50  # Pipeline operations
    connection_timeout_seconds: float = 5.0
    socket_timeout_seconds: float = 2.0

    # Data management
    enable_write_behind: bool = True
    write_behind_batch_size: int = 50
    write_behind_flush_interval_seconds: int = 30

    # Hot data management
    hot_data_ttl_multiplier: float = 2.0  # Hot data lives longer
    promote_after_hits: int = 3  # Promote to hot after N hits

    # Monitoring
    enable_access_logging: bool = True
    log_slow_operations_ms: float = 100.0


@dataclass
class L2CacheEntry:
    """L2 cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: int = 7200
    is_compressed: bool = False
    compression_ratio: float = 1.0
    hit_count: int = 0
    node_affinity: str | None = None  # Preferred node for this key

    def to_redis_value(self) -> bytes:
        """Convert to Redis storage format."""
        metadata = {
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "hit_count": self.hit_count,
            "is_compressed": self.is_compressed,
            "compression_ratio": self.compression_ratio,
            "node_affinity": self.node_affinity
        }

        # Serialize value and metadata
        data = {
            "metadata": metadata,
            "value": self.value
        }

        return pickle.dumps(data)

    @classmethod
    def from_redis_value(cls, key: str, redis_data: bytes, ttl_seconds: int) -> 'L2CacheEntry':
        """Create entry from Redis data."""
        try:
            data = pickle.loads(redis_data)
            metadata = data.get("metadata", {})

            return cls(
                key=key,
                value=data["value"],
                created_at=datetime.fromisoformat(metadata.get("created_at", datetime.utcnow().isoformat())),
                accessed_at=datetime.fromisoformat(metadata.get("accessed_at", datetime.utcnow().isoformat())),
                access_count=metadata.get("access_count", 0),
                size_bytes=metadata.get("size_bytes", 0),
                ttl_seconds=ttl_seconds,
                is_compressed=metadata.get("is_compressed", False),
                compression_ratio=metadata.get("compression_ratio", 1.0),
                hit_count=metadata.get("hit_count", 0),
                node_affinity=metadata.get("node_affinity")
            )
        except Exception as e:
            logger.error(f"Error deserializing cache entry for key {key}: {e}")
            # Return minimal entry
            return cls(
                key=key,
                value=None,
                created_at=datetime.utcnow(),
                accessed_at=datetime.utcnow()
            )


# ============================================================================
# L2 Redis Cache Service
# ============================================================================

class L2RedisCache:
    """
    Advanced L2 distributed cache using Redis with intelligent data management.
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        cluster_manager: RedisClusterManager | None = None,
        l1_cache: L1MemoryCache | None = None,
        config: L2CacheConfig | None = None
    ):
        """Initialize L2 Redis cache."""
        self.redis_cache = redis_cache
        self.cluster_manager = cluster_manager
        self.l1_cache = l1_cache
        self.config = config or L2CacheConfig()

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "promotions": 0,
            "compressions": 0,
            "decompressions": 0,
            "distribution_operations": 0,
            "write_behind_operations": 0
        }

        # Write-behind queue
        self.write_behind_queue: deque = deque()
        self.write_behind_task: asyncio.Task | None = None
        self._write_behind_running = False

        # Hot data tracking
        self.hot_keys: set[str] = set()
        self.key_hit_counts: dict[str, int] = defaultdict(int)

        # Access logging
        self.access_log: deque = deque(maxlen=1000)

        # Performance tracking
        self.operation_times: dict[str, deque] = {
            "get": deque(maxlen=100),
            "set": deque(maxlen=100),
            "delete": deque(maxlen=100)
        }

        logger.info("L2 Redis Cache initialized")

    # ========================================================================
    # Core Cache Operations
    # ========================================================================

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from L2 cache."""
        start_time = time.time()

        try:
            # Try L1 cache first if available
            if self.l1_cache and self.l1_cache.exists(key):
                value = self.l1_cache.get(key, default)
                if value != default:
                    await self._log_access(key, "l1_hit", time.time() - start_time)
                    return value

            # Get from Redis
            redis_data = self.redis_cache.get(key)

            if redis_data is None:
                self.stats["misses"] += 1
                await self._log_access(key, "miss", time.time() - start_time)
                return default

            # Deserialize entry
            ttl = await self._get_ttl(key)
            entry = L2CacheEntry.from_redis_value(key, redis_data, ttl)

            # Update access statistics
            entry.accessed_at = datetime.utcnow()
            entry.access_count += 1
            entry.hit_count += 1

            # Track hit count for promotion
            self.key_hit_counts[key] += 1

            # Consider promotion to hot data
            if (self.key_hit_counts[key] >= self.config.promote_after_hits and
                key not in self.hot_keys):
                await self._promote_to_hot(key, entry)

            # Update entry in Redis (write-behind)
            if self.config.enable_write_behind:
                self.write_behind_queue.append(("update", key, entry))
            else:
                await self._update_entry_metadata(key, entry)

            # Store in L1 cache if available
            if self.l1_cache:
                # Determine L1 cache level based on hit count
                if key in self.hot_keys:
                    l1_level = CacheLevel.HOT
                elif entry.hit_count >= 2:
                    l1_level = CacheLevel.WARM
                else:
                    l1_level = CacheLevel.COLD

                self.l1_cache.set(key, entry.value, ttl_seconds=entry.ttl_seconds, level=l1_level)

            self.stats["hits"] += 1
            operation_time = (time.time() - start_time) * 1000
            self.operation_times["get"].append(operation_time)

            await self._log_access(key, "l2_hit", time.time() - start_time)

            return entry.value

        except Exception as e:
            logger.error(f"Error getting key {key} from L2 cache: {e}")
            operation_time = (time.time() - start_time) * 1000
            self.operation_times["get"].append(operation_time)
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        compress: bool | None = None
    ) -> bool:
        """Set value in L2 cache."""
        start_time = time.time()

        try:
            # Create cache entry
            entry = L2CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                accessed_at=datetime.utcnow(),
                ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
                size_bytes=len(str(value))  # Rough estimate
            )

            # Apply TTL jitter to prevent thundering herd
            if self.config.ttl_jitter_percent > 0:
                jitter = entry.ttl_seconds * (self.config.ttl_jitter_percent / 100)
                import random
                entry.ttl_seconds += random.randint(-int(jitter), int(jitter))

            # Handle hot data TTL extension
            if key in self.hot_keys:
                entry.ttl_seconds = int(entry.ttl_seconds * self.config.hot_data_ttl_multiplier)

            # Compression decision
            if compress is None:
                compress = (entry.size_bytes >= self.config.compression_threshold_bytes and
                           self.config.compression_level != CompressionLevel.NONE)

            if compress:
                entry = await self._compress_entry(entry)

            # Determine target node for distribution
            target_node = await self._get_target_node(key)
            if target_node:
                entry.node_affinity = target_node

            # Store in Redis
            redis_data = entry.to_redis_value()
            success = self.redis_cache.set(key, redis_data, ttl=entry.ttl_seconds)

            if success:
                # Update L1 cache if available
                if self.l1_cache:
                    # Determine L1 cache level
                    if key in self.hot_keys:
                        l1_level = CacheLevel.HOT
                    else:
                        l1_level = CacheLevel.WARM

                    self.l1_cache.set(key, entry.value, ttl_seconds=entry.ttl_seconds, level=l1_level)

                self.stats["sets"] += 1
                operation_time = (time.time() - start_time) * 1000
                self.operation_times["set"].append(operation_time)

                await self._log_access(key, "set", time.time() - start_time)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error setting key {key} in L2 cache: {e}")
            operation_time = (time.time() - start_time) * 1000
            self.operation_times["set"].append(operation_time)
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from L2 cache."""
        start_time = time.time()

        try:
            # Delete from Redis
            deleted = self.redis_cache.delete(key)

            # Delete from L1 cache if available
            if self.l1_cache:
                self.l1_cache.delete(key)

            # Clean up tracking data
            self.hot_keys.discard(key)
            self.key_hit_counts.pop(key, None)

            if deleted > 0:
                self.stats["deletes"] += 1
                operation_time = (time.time() - start_time) * 1000
                self.operation_times["delete"].append(operation_time)

                await self._log_access(key, "delete", time.time() - start_time)
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting key {key} from L2 cache: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in L2 cache."""
        # Check L1 cache first
        if self.l1_cache and self.l1_cache.exists(key):
            return True

        # Check Redis
        return bool(self.redis_cache.exists(key))

    # ========================================================================
    # Batch Operations
    # ========================================================================

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple keys from cache."""
        results = {}

        # Split into batches
        for i in range(0, len(keys), self.config.batch_size):
            batch_keys = keys[i:i + self.config.batch_size]

            # Check L1 cache first
            l1_results = {}
            remaining_keys = []

            if self.l1_cache:
                for key in batch_keys:
                    if self.l1_cache.exists(key):
                        value = self.l1_cache.get(key)
                        if value is not None:
                            l1_results[key] = value
                        else:
                            remaining_keys.append(key)
                    else:
                        remaining_keys.append(key)
            else:
                remaining_keys = batch_keys

            # Get remaining keys from Redis
            if remaining_keys:
                redis_results = self.redis_cache.mget(remaining_keys)

                for key, redis_data in redis_results.items():
                    if redis_data is not None:
                        try:
                            ttl = await self._get_ttl(key)
                            entry = L2CacheEntry.from_redis_value(key, redis_data, ttl)
                            results[key] = entry.value

                            # Store in L1 cache
                            if self.l1_cache:
                                self.l1_cache.set(key, entry.value, ttl_seconds=entry.ttl_seconds)
                        except Exception as e:
                            logger.error(f"Error deserializing key {key}: {e}")

            # Add L1 results
            results.update(l1_results)

        # Update statistics
        self.stats["hits"] += len(results)
        self.stats["misses"] += len(keys) - len(results)

        return results

    async def mset(self, data: dict[str, Any], ttl_seconds: int | None = None) -> bool:
        """Set multiple keys in cache."""
        success_count = 0

        # Split into batches
        items = list(data.items())
        for i in range(0, len(items), self.config.batch_size):
            batch_items = items[i:i + self.config.batch_size]

            # Prepare Redis data
            redis_data = {}

            for key, value in batch_items:
                entry = L2CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.utcnow(),
                    accessed_at=datetime.utcnow(),
                    ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
                    size_bytes=len(str(value))
                )

                # Compression if needed
                if (entry.size_bytes >= self.config.compression_threshold_bytes and
                    self.config.compression_level != CompressionLevel.NONE):
                    entry = await self._compress_entry(entry)

                redis_data[key] = entry.to_redis_value()

            # Store in Redis
            if self.redis_cache.mset(redis_data, ttl=ttl_seconds):
                success_count += len(batch_items)

                # Store in L1 cache
                if self.l1_cache:
                    for key, value in batch_items:
                        self.l1_cache.set(key, value, ttl_seconds=ttl_seconds)

        self.stats["sets"] += success_count
        return success_count == len(items)

    # ========================================================================
    # Data Management
    # ========================================================================

    async def _compress_entry(self, entry: L2CacheEntry) -> L2CacheEntry:
        """Compress cache entry data."""
        try:
            import zlib

            original_data = pickle.dumps(entry.value)

            if self.config.compression_level == CompressionLevel.HIGH:
                compressed_data = zlib.compress(original_data, level=9)
            elif self.config.compression_level == CompressionLevel.MEDIUM:
                compressed_data = zlib.compress(original_data, level=6)
            else:  # LOW
                compressed_data = zlib.compress(original_data, level=1)

            entry.value = compressed_data
            entry.is_compressed = True
            entry.compression_ratio = len(original_data) / len(compressed_data)
            entry.size_bytes = len(compressed_data)

            self.stats["compressions"] += 1

            return entry

        except Exception as e:
            logger.error(f"Error compressing entry for key {entry.key}: {e}")
            return entry

    async def _decompress_entry(self, entry: L2CacheEntry) -> Any:
        """Decompress cache entry data."""
        if not entry.is_compressed:
            return entry.value

        try:
            import zlib
            decompressed_data = zlib.decompress(entry.value)
            value = pickle.loads(decompressed_data)

            self.stats["decompressions"] += 1

            return value

        except Exception as e:
            logger.error(f"Error decompressing entry for key {entry.key}: {e}")
            return entry.value

    async def _promote_to_hot(self, key: str, entry: L2CacheEntry):
        """Promote key to hot data status."""
        self.hot_keys.add(key)

        # Extend TTL for hot data
        new_ttl = int(entry.ttl_seconds * self.config.hot_data_ttl_multiplier)

        # Update in Redis
        self.redis_cache.expire(key, new_ttl)

        self.stats["promotions"] += 1

        logger.debug(f"Promoted key {key} to hot data with TTL {new_ttl}")

    async def _get_target_node(self, key: str) -> str | None:
        """Get target node for distributed storage."""
        if not self.cluster_manager:
            return None

        # Use consistent hashing to determine target node
        if self.config.distribution_strategy == DistributionStrategy.HASH_RING:
            hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)

            # Get cluster info
            cluster_info = await self.cluster_manager.get_cluster_info()
            nodes = list(cluster_info.get("nodes", {}).keys())

            if nodes:
                node_index = hash_value % len(nodes)
                return nodes[node_index]

        return None

    async def _get_ttl(self, key: str) -> int:
        """Get TTL for a key."""
        try:
            # Get TTL from Redis
            client = self.redis_cache.get_redis_client()
            if client:
                ttl = client.ttl(key)
                return ttl if ttl > 0 else self.config.default_ttl_seconds
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")

        return self.config.default_ttl_seconds

    async def _update_entry_metadata(self, key: str, entry: L2CacheEntry):
        """Update entry metadata in Redis."""
        try:
            redis_data = entry.to_redis_value()
            self.redis_cache.set(key, redis_data, ttl=entry.ttl_seconds, xx=True)  # Only update if exists
        except Exception as e:
            logger.error(f"Error updating metadata for key {key}: {e}")

    # ========================================================================
    # Write-Behind Processing
    # ========================================================================

    async def start_write_behind(self):
        """Start write-behind processing."""
        if self._write_behind_running or not self.config.enable_write_behind:
            return

        self._write_behind_running = True
        self.write_behind_task = asyncio.create_task(self._write_behind_loop())

        logger.info("Started L2 cache write-behind processing")

    async def stop_write_behind(self):
        """Stop write-behind processing."""
        self._write_behind_running = False

        if self.write_behind_task:
            self.write_behind_task.cancel()
            try:
                await self.write_behind_task
            except asyncio.CancelledError:
                pass

        # Flush remaining queue
        await self._flush_write_behind_queue()

        logger.info("Stopped L2 cache write-behind processing")

    async def _write_behind_loop(self):
        """Write-behind processing loop."""
        while self._write_behind_running:
            try:
                await asyncio.sleep(self.config.write_behind_flush_interval_seconds)
                await self._flush_write_behind_queue()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in write-behind loop: {e}")
                await asyncio.sleep(5)

    async def _flush_write_behind_queue(self):
        """Flush write-behind queue to Redis."""
        if not self.write_behind_queue:
            return

        batch = []

        # Collect batch
        for _ in range(min(self.config.write_behind_batch_size, len(self.write_behind_queue))):
            if self.write_behind_queue:
                batch.append(self.write_behind_queue.popleft())

        if not batch:
            return

        # Process batch
        update_count = 0

        for operation, key, entry in batch:
            try:
                if operation == "update":
                    await self._update_entry_metadata(key, entry)
                    update_count += 1
            except Exception as e:
                logger.error(f"Error in write-behind operation for key {key}: {e}")

        self.stats["write_behind_operations"] += update_count

        if batch:
            logger.debug(f"Flushed {len(batch)} write-behind operations")

    # ========================================================================
    # Access Logging and Monitoring
    # ========================================================================

    async def _log_access(self, key: str, operation: str, duration: float):
        """Log cache access for monitoring."""
        if not self.config.enable_access_logging:
            return

        access_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "key": key,
            "operation": operation,
            "duration_ms": duration * 1000,
            "is_slow": (duration * 1000) > self.config.log_slow_operations_ms
        }

        self.access_log.append(access_record)

        # Log slow operations
        if access_record["is_slow"]:
            logger.warning(f"Slow L2 cache operation: {operation} for key {key} took {access_record['duration_ms']:.1f}ms")

    # ========================================================================
    # Statistics and Health
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get L2 cache statistics."""
        total_operations = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_operations * 100) if total_operations > 0 else 0

        # Calculate average operation times
        avg_times = {}
        for operation, times in self.operation_times.items():
            avg_times[f"avg_{operation}_time_ms"] = sum(times) / len(times) if times else 0

        stats = {
            "hit_rate_percent": round(hit_rate, 2),
            "total_operations": total_operations,
            "hot_keys_count": len(self.hot_keys),
            "write_behind_queue_size": len(self.write_behind_queue),
            "compression_ratio_avg": self._calculate_avg_compression_ratio(),
            **self.stats,
            **avg_times
        }

        return stats

    def get_hot_keys_analysis(self) -> dict[str, Any]:
        """Get analysis of hot keys."""
        return {
            "hot_keys_count": len(self.hot_keys),
            "top_keys_by_hits": sorted(
                self.key_hit_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20],  # Top 20 keys
            "hot_keys_list": list(self.hot_keys)[:50]  # First 50 hot keys
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get detailed performance metrics."""
        metrics = {
            "operation_times": {},
            "access_patterns": self._analyze_access_patterns(),
            "slow_operations": [
                record for record in self.access_log
                if record["is_slow"]
            ][-10:]  # Last 10 slow operations
        }

        # Operation time statistics
        for operation, times in self.operation_times.items():
            if times:
                metrics["operation_times"][operation] = {
                    "avg_ms": sum(times) / len(times),
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                    "count": len(times)
                }

        return metrics

    def _calculate_avg_compression_ratio(self) -> float:
        """Calculate average compression ratio."""
        if self.stats["compressions"] == 0:
            return 1.0

        # This is simplified - in practice would track compression ratios
        return 2.5  # Average compression ratio estimate

    def _analyze_access_patterns(self) -> dict[str, Any]:
        """Analyze access patterns from logs."""
        if not self.access_log:
            return {}

        # Analyze last 100 accesses
        recent_accesses = list(self.access_log)[-100:]

        operation_counts = defaultdict(int)
        hourly_distribution = defaultdict(int)

        for record in recent_accesses:
            operation_counts[record["operation"]] += 1
            hour = datetime.fromisoformat(record["timestamp"]).hour
            hourly_distribution[hour] += 1

        return {
            "operation_distribution": dict(operation_counts),
            "hourly_access_distribution": dict(hourly_distribution),
            "total_logged_accesses": len(recent_accesses)
        }

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_write_behind()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_write_behind()


# Example usage
if __name__ == "__main__":
    async def main():
        from .l1_memory_cache import create_l1_cache
        from .redis_cache_service import RedisCacheService, RedisConfig

        # Create services
        redis_config = RedisConfig()
        redis_cache = RedisCacheService(redis_config)
        l1_cache = create_l1_cache(max_size_mb=50.0)

        # Create L2 cache
        l2_cache = L2RedisCache(redis_cache, l1_cache=l1_cache)

        async with l2_cache:
            # Set some values
            await l2_cache.set("key1", "value1")
            await l2_cache.set("key2", {"data": "complex_value"})
            await l2_cache.set("large_key", "x" * 2000)  # Will be compressed

            # Get values
            print("key1:", await l2_cache.get("key1"))
            print("key2:", await l2_cache.get("key2"))
            print("large_key length:", len(await l2_cache.get("large_key", "")))

            # Batch operations
            batch_data = {f"batch_key_{i}": f"batch_value_{i}" for i in range(10)}
            await l2_cache.mset(batch_data)

            batch_results = await l2_cache.mget(list(batch_data.keys()))
            print(f"Batch get results: {len(batch_results)} keys retrieved")

            # Check statistics
            stats = l2_cache.get_stats()
            print("L2 Cache stats:", stats)

            # Performance metrics
            perf_metrics = l2_cache.get_performance_metrics()
            print("Performance metrics:", perf_metrics)

    # Run example
    # asyncio.run(main())
