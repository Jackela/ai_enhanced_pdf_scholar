"""
L1 Memory Cache Service
High-performance in-memory cache with intelligent eviction policies.
"""

import asyncio
import logging
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Policies and Configuration
# ============================================================================


class EvictionPolicy(str, Enum):
    """Cache eviction policies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    RANDOM = "random"  # Random eviction
    TTL = "ttl"  # Time-to-live based
    SIZE_AWARE = "size_aware"  # Size-aware LRU
    ADAPTIVE = "adaptive"  # Adaptive based on patterns


class CacheLevel(str, Enum):
    """Cache levels for different data types."""

    HOT = "hot"  # Frequently accessed data
    WARM = "warm"  # Moderately accessed data
    COLD = "cold"  # Rarely accessed data


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: int | None = None
    level: CacheLevel = CacheLevel.WARM

    # Access tracking
    last_access_times: deque = field(default_factory=lambda: deque(maxlen=10))

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl_seconds is None:
            return False

        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry_time

    def update_access(self) -> None:
        """Update access statistics."""
        now = datetime.utcnow()
        self.accessed_at = now
        self.access_count += 1
        self.last_access_times.append(now)

    def calculate_score(self, policy: EvictionPolicy) -> float:
        """Calculate eviction score for this entry."""
        now = datetime.utcnow()

        if policy == EvictionPolicy.LRU:
            # Lower score = more likely to evict (older = lower score)
            seconds_since_access = (now - self.accessed_at).total_seconds()
            return 1.0 / (1.0 + seconds_since_access)

        elif policy == EvictionPolicy.LFU:
            # Higher access count = higher score
            return float(self.access_count)

        elif policy == EvictionPolicy.SIZE_AWARE:
            # Combine recency and size (prefer recent, smaller items)
            seconds_since_access = (now - self.accessed_at).total_seconds()
            recency_score = 1.0 / (1.0 + seconds_since_access)
            size_penalty = 1.0 / (1.0 + self.size_bytes / 1024.0)  # Size in KB
            return recency_score * size_penalty

        elif policy == EvictionPolicy.ADAPTIVE:
            # Adaptive scoring based on access patterns
            if len(self.last_access_times) < 2:
                return self.calculate_score(EvictionPolicy.LRU)

            # Calculate access frequency (accesses per hour)
            time_span = (
                self.last_access_times[-1] - self.last_access_times[0]
            ).total_seconds()
            frequency = len(self.last_access_times) / max(time_span / 3600, 0.1)

            # Combine frequency and recency
            recency = self.calculate_score(EvictionPolicy.LRU)
            return frequency * recency

        else:
            # Default to LRU
            return self.calculate_score(EvictionPolicy.LRU)


@dataclass
class CacheConfig:
    """Configuration for L1 memory cache."""

    max_size_mb: float = 100.0  # Maximum cache size in MB
    max_entries: int = 10000  # Maximum number of entries
    default_ttl_seconds: int = 3600  # Default TTL (1 hour)
    eviction_policy: EvictionPolicy = EvictionPolicy.ADAPTIVE

    # Memory management
    memory_pressure_threshold: float = 0.8  # Trigger cleanup at 80%
    aggressive_cleanup_threshold: float = 0.95  # Aggressive cleanup at 95%
    cleanup_batch_size: int = 100  # Number of entries to clean in one batch

    # Performance tuning
    enable_background_cleanup: bool = True
    cleanup_interval_seconds: int = 60  # Background cleanup interval

    # Level-specific settings
    level_configs: dict[CacheLevel, dict[str, Any]] = field(
        default_factory=lambda: {
            CacheLevel.HOT: {"max_size_mb": 30.0, "ttl_seconds": 1800},  # 30MB, 30min
            CacheLevel.WARM: {"max_size_mb": 50.0, "ttl_seconds": 3600},  # 50MB, 1hour
            CacheLevel.COLD: {"max_size_mb": 20.0, "ttl_seconds": 7200},  # 20MB, 2hours
        }
    )


# ============================================================================
# Cache Statistics and Monitoring
# ============================================================================


@dataclass
class CacheStatistics:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    # Size statistics
    current_size_bytes: int = 0
    current_entries: int = 0
    max_size_bytes: int = 0

    # Performance statistics
    avg_access_time_ms: float = 0.0
    hit_rate_percent: float = 0.0

    # Level statistics
    level_stats: dict[CacheLevel, dict[str, int]] = field(
        default_factory=lambda: {
            level: {"hits": 0, "misses": 0, "entries": 0, "size_bytes": 0}
            for level in CacheLevel
        }
    )

    def calculate_hit_rate(self) -> None:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        self.hit_rate_percent = (self.hits / total * 100) if total > 0 else 0

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        self.calculate_hit_rate()

        return {
            "hit_rate_percent": round(self.hit_rate_percent, 2),
            "total_requests": self.hits + self.misses,
            "current_entries": self.current_entries,
            "current_size_mb": round(self.current_size_bytes / (1024 * 1024), 2),
            "memory_utilization_percent": round(
                (
                    (self.current_size_bytes / self.max_size_bytes * 100)
                    if self.max_size_bytes > 0
                    else 0
                ),
                2,
            ),
            "eviction_count": self.evictions,
            "level_distribution": {
                level.value: stats["entries"]
                for level, stats in self.level_stats.items()
            },
        }


# ============================================================================
# L1 Memory Cache Service
# ============================================================================


class L1MemoryCache:
    """
    High-performance in-memory cache with intelligent eviction and multi-level storage.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize L1 memory cache."""
        self.config = config or CacheConfig()

        # Storage by level
        self.storage: dict[CacheLevel, OrderedDict[str, CacheEntry]] = {
            level: OrderedDict() for level in CacheLevel
        }

        # Index for fast lookups
        self.key_index: dict[str, CacheLevel] = {}

        # Statistics
        self.stats = CacheStatistics()
        self.stats.max_size_bytes = int(self.config.max_size_mb * 1024 * 1024)

        # Thread safety
        self._lock = threading.RLock()

        # Background cleanup
        self._cleanup_task: asyncio.Task | None = None
        self._is_running = False

        # Performance tracking
        self._access_times: deque = deque(maxlen=1000)

        logger.info(
            f"L1 Memory Cache initialized with {self.config.max_size_mb}MB capacity"
        )

    # ========================================================================
    # Core Cache Operations
    # ========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        start_time = time.time()

        try:
            with self._lock:
                # Check if key exists
                level = self.key_index.get(key)
                if level is None:
                    self.stats.misses += 1
                    self.stats.level_stats[CacheLevel.WARM]["misses"] += 1
                    return default

                entry = self.storage[level].get(key)
                if entry is None:
                    # Inconsistent state - clean up
                    del self.key_index[key]
                    self.stats.misses += 1
                    return default

                # Check expiration
                if entry.is_expired():
                    self._remove_entry(key, level)
                    self.stats.misses += 1
                    return default

                # Update access statistics
                entry.update_access()

                # Move to end for LRU (most recent)
                self.storage[level].move_to_end(key)

                # Consider promoting to higher level
                self._consider_promotion(key, entry, level)

                self.stats.hits += 1
                self.stats.level_stats[level]["hits"] += 1

                return entry.value

        finally:
            # Track access time
            access_time_ms = (time.time() - start_time) * 1000
            self._access_times.append(access_time_ms)

            # Update average access time
            if self._access_times:
                self.stats.avg_access_time_ms = sum(self._access_times) / len(
                    self._access_times
                )

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        level: CacheLevel | None = None,
    ) -> bool:
        """Set value in cache."""
        try:
            with self._lock:
                # Calculate value size
                size_bytes = self._estimate_size(value)

                # Determine cache level
                if level is None:
                    level = self._determine_level(key, size_bytes)

                # Check if we need to make space
                if not self._ensure_space(size_bytes, level):
                    logger.warning(f"Cannot cache key {key}: insufficient space")
                    return False

                # Create cache entry
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.utcnow(),
                    accessed_at=datetime.utcnow(),
                    size_bytes=size_bytes,
                    ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
                    level=level,
                )
                entry.update_access()

                # Remove existing entry if present
                if key in self.key_index:
                    old_level = self.key_index[key]
                    self._remove_entry(key, old_level)

                # Store entry
                self.storage[level][key] = entry
                self.key_index[key] = level

                # Update statistics
                self.stats.sets += 1
                self.stats.current_entries += 1
                self.stats.current_size_bytes += size_bytes
                self.stats.level_stats[level]["entries"] += 1
                self.stats.level_stats[level]["size_bytes"] += size_bytes

                return True

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            level = self.key_index.get(key)
            if level is None:
                return False

            return self._remove_entry(key, level)

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            level = self.key_index.get(key)
            if level is None:
                return False

            entry = self.storage[level].get(key)
            if entry is None:
                # Clean up inconsistent state
                del self.key_index[key]
                return False

            # Check expiration
            if entry.is_expired():
                self._remove_entry(key, level)
                return False

            return True

    # ========================================================================
    # Multi-level Operations
    # ========================================================================

    def _determine_level(self, key: str, size_bytes: int) -> CacheLevel:
        """Determine appropriate cache level for a key."""
        # Size-based initial placement
        if size_bytes < 1024:  # < 1KB - hot cache
            return CacheLevel.HOT
        elif size_bytes < 10240:  # < 10KB - warm cache
            return CacheLevel.WARM
        else:  # >= 10KB - cold cache
            return CacheLevel.COLD

    def _consider_promotion(
        self, key: str, entry: CacheEntry, current_level: CacheLevel
    ) -> None:
        """Consider promoting entry to a higher cache level."""
        # Only promote if access count is high enough
        if entry.access_count < 3:
            return

        # Calculate access frequency (accesses per hour)
        if len(entry.last_access_times) >= 2:
            time_span = (
                entry.last_access_times[-1] - entry.last_access_times[0]
            ).total_seconds()
            frequency = len(entry.last_access_times) / max(time_span / 3600, 0.1)

            # Promotion criteria
            promote = False
            target_level = current_level

            if (
                current_level == CacheLevel.COLD and frequency > 2
            ):  # 2+ accesses per hour
                target_level = CacheLevel.WARM
                promote = True
            elif (
                current_level == CacheLevel.WARM and frequency > 10
            ):  # 10+ accesses per hour
                target_level = CacheLevel.HOT
                promote = True

            if promote:
                # Check if target level has space
                target_config = self.config.level_configs[target_level]
                target_max_size = target_config["max_size_mb"] * 1024 * 1024

                current_target_size = self.stats.level_stats[target_level]["size_bytes"]

                if current_target_size + entry.size_bytes <= target_max_size:
                    self._move_entry(key, current_level, target_level)

    def _move_entry(
        self, key: str, from_level: CacheLevel, to_level: CacheLevel
    ) -> None:
        """Move entry between cache levels."""
        entry = self.storage[from_level].pop(key)
        entry.level = to_level

        self.storage[to_level][key] = entry
        self.key_index[key] = to_level

        # Update statistics
        self.stats.level_stats[from_level]["entries"] -= 1
        self.stats.level_stats[from_level]["size_bytes"] -= entry.size_bytes
        self.stats.level_stats[to_level]["entries"] += 1
        self.stats.level_stats[to_level]["size_bytes"] += entry.size_bytes

        logger.debug(f"Moved key {key} from {from_level} to {to_level}")

    # ========================================================================
    # Memory Management and Eviction
    # ========================================================================

    def _ensure_space(self, required_bytes: int, target_level: CacheLevel) -> bool:
        """Ensure sufficient space is available."""
        # Check global memory limit
        if self.stats.current_size_bytes + required_bytes > self.stats.max_size_bytes:
            self._evict_entries(required_bytes)

        # Check level-specific limit
        level_config = self.config.level_configs[target_level]
        level_max_bytes = level_config["max_size_mb"] * 1024 * 1024
        current_level_bytes = self.stats.level_stats[target_level]["size_bytes"]

        if current_level_bytes + required_bytes > level_max_bytes:
            self._evict_from_level(target_level, required_bytes)

        return True  # Assume we can always make space

    def _evict_entries(self, required_bytes: int) -> None:
        """Evict entries to free up space."""
        freed_bytes = 0
        evicted_count = 0

        # Collect all entries for eviction scoring
        all_entries = []
        for level, storage in self.storage.items():
            for key, entry in storage.items():
                score = entry.calculate_score(self.config.eviction_policy)
                all_entries.append((score, key, entry, level))

        # Sort by eviction score (lowest first for LRU-style policies)
        if self.config.eviction_policy in [
            EvictionPolicy.LRU,
            EvictionPolicy.SIZE_AWARE,
        ]:
            all_entries.sort(key=lambda x: x[0])  # Ascending (lowest score first)
        else:
            all_entries.sort(
                key=lambda x: x[0], reverse=True
            )  # Descending (highest score first)

        # Evict entries until we have enough space
        for score, key, entry, level in all_entries:
            if (
                freed_bytes >= required_bytes
                and evicted_count >= self.config.cleanup_batch_size
            ):
                break

            # Skip if entry was already removed
            if key not in self.key_index:
                continue

            self._remove_entry(key, level)
            freed_bytes += entry.size_bytes
            evicted_count += 1

        self.stats.evictions += evicted_count
        logger.debug(f"Evicted {evicted_count} entries, freed {freed_bytes} bytes")

    def _evict_from_level(self, level: CacheLevel, required_bytes: int) -> None:
        """Evict entries from a specific level."""
        storage = self.storage[level]
        if not storage:
            return

        freed_bytes = 0
        evicted_keys = []

        # Collect entries from this level
        entries = []
        for key, entry in storage.items():
            score = entry.calculate_score(self.config.eviction_policy)
            entries.append((score, key, entry))

        # Sort by eviction score
        if self.config.eviction_policy in [
            EvictionPolicy.LRU,
            EvictionPolicy.SIZE_AWARE,
        ]:
            entries.sort(key=lambda x: x[0])
        else:
            entries.sort(key=lambda x: x[0], reverse=True)

        # Evict entries
        for score, key, entry in entries:
            if freed_bytes >= required_bytes:
                break

            evicted_keys.append(key)
            freed_bytes += entry.size_bytes

        # Remove evicted keys
        for key in evicted_keys:
            self._remove_entry(key, level)

        self.stats.evictions += len(evicted_keys)
        logger.debug(f"Evicted {len(evicted_keys)} entries from level {level}")

    def _remove_entry(self, key: str, level: CacheLevel) -> bool:
        """Remove entry from cache."""
        entry = self.storage[level].pop(key, None)
        if entry is None:
            return False

        # Update index
        self.key_index.pop(key, None)

        # Update statistics
        self.stats.current_entries -= 1
        self.stats.current_size_bytes -= entry.size_bytes
        self.stats.deletes += 1
        self.stats.level_stats[level]["entries"] -= 1
        self.stats.level_stats[level]["size_bytes"] -= entry.size_bytes

        return True

    # ========================================================================
    # Background Maintenance
    # ========================================================================

    async def start_background_cleanup(self) -> None:
        """Start background cleanup task."""
        if self._is_running or not self.config.enable_background_cleanup:
            return

        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._background_cleanup_loop())

        logger.info("Started background cache cleanup")

    async def stop_background_cleanup(self) -> None:
        """Stop background cleanup task."""
        self._is_running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped background cache cleanup")

    async def _background_cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)

                # Perform maintenance
                await asyncio.to_thread(self._perform_maintenance)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background cleanup: {e}")
                await asyncio.sleep(5)

    def _perform_maintenance(self) -> None:
        """Perform cache maintenance."""
        with self._lock:
            # Remove expired entries
            self._cleanup_expired_entries()

            # Check memory pressure
            memory_usage_ratio = (
                self.stats.current_size_bytes / self.stats.max_size_bytes
            )

            if memory_usage_ratio > self.config.aggressive_cleanup_threshold:
                # Aggressive cleanup
                target_size = int(self.stats.max_size_bytes * 0.7)  # Clean to 70%
                bytes_to_free = self.stats.current_size_bytes - target_size
                self._evict_entries(bytes_to_free)

            elif memory_usage_ratio > self.config.memory_pressure_threshold:
                # Light cleanup
                target_size = int(self.stats.max_size_bytes * 0.8)  # Clean to 80%
                bytes_to_free = self.stats.current_size_bytes - target_size
                self._evict_entries(bytes_to_free)

    def _cleanup_expired_entries(self) -> None:
        """Remove expired entries."""
        expired_keys = []

        for level, storage in self.storage.items():
            for key, entry in storage.items():
                if entry.is_expired():
                    expired_keys.append((key, level))

        for key, level in expired_keys:
            self._remove_entry(key, level)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value."""
        try:
            import sys

            return sys.getsizeof(value)
        except:
            # Fallback estimation
            if isinstance(value, str):
                return len(value.encode("utf-8"))
            elif isinstance(value, (dict, list)):
                return len(str(value)) * 4  # Rough estimate
            else:
                return 100  # Default size

    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            self.stats.calculate_hit_rate()
            return self.stats.get_summary()

    def get_detailed_stats(self) -> dict[str, Any]:
        """Get detailed cache statistics."""
        with self._lock:
            stats = self.get_stats()

            # Add memory information
            process = psutil.Process()
            memory_info = process.memory_info()

            stats.update(
                {
                    "process_memory_mb": memory_info.rss / (1024 * 1024),
                    "cache_overhead_percent": (
                        (memory_info.rss - self.stats.current_size_bytes)
                        / memory_info.rss
                        * 100
                        if memory_info.rss > 0
                        else 0
                    ),
                    "entries_by_level": {
                        level.value: len(storage)
                        for level, storage in self.storage.items()
                    },
                    "average_entry_size_kb": (
                        self.stats.current_size_bytes
                        / (self.stats.current_entries * 1024)
                        if self.stats.current_entries > 0
                        else 0
                    ),
                    "eviction_policy": self.config.eviction_policy.value,
                    "config": {
                        "max_size_mb": self.config.max_size_mb,
                        "max_entries": self.config.max_entries,
                        "default_ttl_seconds": self.config.default_ttl_seconds,
                    },
                }
            )

            return stats

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            for storage in self.storage.values():
                storage.clear()

            self.key_index.clear()

            # Reset statistics
            self.stats.current_entries = 0
            self.stats.current_size_bytes = 0
            for level_stats in self.stats.level_stats.values():
                level_stats["entries"] = 0
                level_stats["size_bytes"] = 0

            logger.info("Cache cleared")

    def get_memory_usage(self) -> dict[str, Any]:
        """Get detailed memory usage information."""
        with self._lock:
            total_entries = sum(len(storage) for storage in self.storage.values())

            memory_info = {
                "total_size_mb": self.stats.current_size_bytes / (1024 * 1024),
                "total_entries": total_entries,
                "utilization_percent": (
                    self.stats.current_size_bytes / self.stats.max_size_bytes * 100
                ),
                "levels": {},
            }

            for level in CacheLevel:
                level_size = self.stats.level_stats[level]["size_bytes"]
                level_entries = len(self.storage[level])
                level_config = self.config.level_configs[level]
                level_max_size = level_config["max_size_mb"] * 1024 * 1024

                memory_info["levels"][level.value] = {
                    "size_mb": level_size / (1024 * 1024),
                    "entries": level_entries,
                    "utilization_percent": (
                        (level_size / level_max_size * 100) if level_max_size > 0 else 0
                    ),
                    "max_size_mb": level_config["max_size_mb"],
                }

            return memory_info

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self) -> None:
        """Async context manager entry."""
        await self.start_background_cleanup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop_background_cleanup()


# ============================================================================
# Cache Factory
# ============================================================================


def create_l1_cache(
    max_size_mb: float = 100.0,
    eviction_policy: EvictionPolicy = EvictionPolicy.ADAPTIVE,
    enable_background_cleanup: bool = True,
) -> L1MemoryCache:
    """Create L1 memory cache with specified configuration."""
    config = CacheConfig(
        max_size_mb=max_size_mb,
        eviction_policy=eviction_policy,
        enable_background_cleanup=enable_background_cleanup,
    )

    return L1MemoryCache(config)


# Example usage
if __name__ == "__main__":

    async def main() -> None:
        # Create cache
        cache = create_l1_cache(max_size_mb=50.0)

        async with cache:
            # Set some values
            cache.set("key1", "value1", level=CacheLevel.HOT)
            cache.set("key2", {"data": "value2"}, level=CacheLevel.WARM)
            cache.set("key3", "large_value" * 100, level=CacheLevel.COLD)

            # Get values
            print("key1:", cache.get("key1"))
            print("key2:", cache.get("key2"))
            print("key3 exists:", cache.exists("key3"))

            # Check statistics
            stats = cache.get_detailed_stats()
            print("Cache stats:", stats)

            # Wait for background cleanup to run
            await asyncio.sleep(5)

            print("Final stats:", cache.get_stats())

    # Run example
    # asyncio.run(main())
