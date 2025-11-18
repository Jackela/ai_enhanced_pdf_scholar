"""
Intelligent Query Cache Manager for AI Enhanced PDF Scholar
Advanced query result caching with intelligent cache warming, invalidation, and optimization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from backend.services.redis_cache_service import RedisCacheService
except ImportError as e:
    logger.warning(f"Optional import failed: {e}")
    RedisCacheService = None

try:
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.warning(f"DatabaseConnection import failed: {e}")
    # Create a placeholder type for DatabaseConnection if import fails
    DatabaseConnection = Any


class CacheEvictionPolicy(Enum):
    """Cache eviction policies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    HYBRID = "hybrid"  # Combination of LRU and frequency


@dataclass
class CacheEntry:
    """Represents a cached query result."""

    query_hash: str
    query_text: str
    parameters_hash: str
    result_data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int | None
    size_bytes: int
    tags: set[str] = field(default_factory=set)
    invalidation_triggers: set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if not self.ttl_seconds:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    total_entries: int
    total_size_bytes: int
    hit_count: int
    miss_count: int
    eviction_count: int
    hit_rate: float
    avg_response_time_ms: float
    memory_usage_mb: float


class IntelligentQueryCacheManager:
    """
    Intelligent Query Cache Manager with advanced features:
    - Automatic cache warming based on query patterns
    - Smart invalidation based on data changes
    - Multiple eviction policies
    - Query result compression
    - Distributed caching support via Redis
    """

    # Default cache settings
    DEFAULT_MAX_ENTRIES = 10000
    DEFAULT_MAX_MEMORY_MB = 512
    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    DEFAULT_CACHE_WARMING_THRESHOLD = 10  # Queries accessed 10+ times get warmed

    def __init__(
        self,
        db_connection: DatabaseConnection,
        redis_service: RedisCacheService | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.HYBRID,
        enable_compression: bool = True,
        enable_warming: bool = True,
    ) -> None:
        """
        Initialize the Intelligent Query Cache Manager.

        Args:
            db_connection: Database connection instance
            redis_service: Optional Redis cache service for distributed caching
            max_entries: Maximum number of cache entries
            max_memory_mb: Maximum memory usage in MB
            eviction_policy: Cache eviction policy
            enable_compression: Whether to compress cached results
            enable_warming: Whether to enable automatic cache warming
        """
        self.db = db_connection
        self.redis_service = redis_service
        self.max_entries = max_entries
        self.max_memory_mb = max_memory_mb
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.eviction_policy = eviction_policy
        self.enable_compression = enable_compression
        self.enable_warming = enable_warming

        # In-memory cache storage
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = threading.RLock()

        # Cache statistics
        self._stats = CacheStats(0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
        self._stats_lock = threading.Lock()

        # Query pattern tracking for cache warming
        self._query_patterns: dict[str, dict[str, Any]] = {}
        self._pattern_lock = threading.Lock()

        # Invalidation tracking
        self._table_watchers: dict[str, set[str]] = {}  # table -> cache_keys
        self._invalidation_lock = threading.Lock()

        # Background tasks
        self._cleanup_thread: threading.Thread | None = None
        self._warming_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Initialize cache infrastructure
        self._init_cache_infrastructure()
        self._start_background_tasks()

    def _init_cache_infrastructure(self) -> None:
        """Initialize cache infrastructure including persistent storage if needed."""
        try:
            # Create cache monitoring table
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS query_cache_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL,
                    query_text TEXT,
                    hit_count INTEGER DEFAULT 0,
                    miss_count INTEGER DEFAULT 0,
                    last_access DATETIME,
                    avg_response_time_ms REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            self.db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_stats_hash
                ON query_cache_stats(query_hash)
            """
            )

            self.db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_stats_last_access
                ON query_cache_stats(last_access DESC)
            """
            )

            logger.info("Query cache infrastructure initialized")

        except Exception as e:
            logger.error(f"Failed to initialize cache infrastructure: {e}")

    def _start_background_tasks(self) -> None:
        """Start background tasks for cache maintenance and warming."""
        # Cleanup task
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker, daemon=True, name="QueryCacheCleanup"
        )
        self._cleanup_thread.start()

        # Cache warming task
        if self.enable_warming:
            self._warming_thread = threading.Thread(
                target=self._warming_worker, daemon=True, name="QueryCacheWarming"
            )
            self._warming_thread.start()

        logger.info("Cache background tasks started")

    def _generate_cache_key(
        self, query: str, parameters: tuple[Any, ...] | None = None
    ) -> str:
        """Generate a unique cache key for a query and its parameters."""
        # Normalize query
        normalized_query = " ".join(query.strip().split())

        # Create hash from query and parameters
        content = normalized_query
        if parameters:
            content += str(parameters)

        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _compress_data(self, data: Any) -> bytes:
        """Compress data for storage."""
        if not self.enable_compression:
            return pickle.dumps(data)

        import zlib

        pickled_data = pickle.dumps(data)
        return zlib.compress(pickled_data, level=6)  # Good balance of speed/compression

    def _decompress_data(self, compressed_data: bytes) -> Any:
        """Decompress data from storage."""
        if not self.enable_compression:
            return pickle.loads(compressed_data)

        import zlib

        pickled_data = zlib.decompress(compressed_data)
        return pickle.loads(pickled_data)

    def get(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        tags: set[str] | None = None,
    ) -> Any | None:
        """
        Get cached query result.

        Args:
            query: SQL query
            parameters: Query parameters
            tags: Optional tags for cache invalidation

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._generate_cache_key(query, parameters)

        with self._cache_lock:
            entry = self._cache.get(cache_key)

            if entry is None:
                # Cache miss
                self._record_miss(cache_key, query)
                return None

            if entry.is_expired():
                # Expired entry
                del self._cache[cache_key]
                self._record_miss(cache_key, query)
                return None

            # Cache hit
            entry.update_access()
            self._record_hit(cache_key, query)

            try:
                return self._decompress_data(entry.result_data)
            except Exception as e:
                logger.error(f"Failed to decompress cache data: {e}")
                del self._cache[cache_key]
                return None

    def put(
        self,
        query: str,
        result: Any,
        parameters: tuple[Any, ...] | None = None,
        ttl_seconds: int | None = None,
        tags: set[str] | None = None,
        invalidation_triggers: set[str] | None = None,
    ) -> bool:
        """
        Store query result in cache.

        Args:
            query: SQL query
            result: Query result to cache
            parameters: Query parameters
            ttl_seconds: Time to live for cache entry
            tags: Tags for cache invalidation
            invalidation_triggers: Table names that should invalidate this cache

        Returns:
            True if cached successfully
        """
        try:
            cache_key = self._generate_cache_key(query, parameters)

            # Compress result data
            compressed_data = self._compress_data(result)
            size_bytes = len(compressed_data)

            # Check if entry would exceed memory limits
            if size_bytes > self.max_memory_bytes:
                logger.warning(f"Cache entry too large: {size_bytes} bytes")
                return False

            # Create cache entry
            entry = CacheEntry(
                query_hash=cache_key,
                query_text=query,
                parameters_hash=(
                    self._generate_cache_key("", parameters) if parameters else ""
                ),
                result_data=compressed_data,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=1,
                ttl_seconds=ttl_seconds or self.DEFAULT_TTL_SECONDS,
                size_bytes=size_bytes,
                tags=tags or set(),
                invalidation_triggers=invalidation_triggers or set(),
            )

            with self._cache_lock:
                # Ensure we have space
                self._make_space(size_bytes)

                # Store entry
                self._cache[cache_key] = entry

                # Update invalidation tracking
                self._update_invalidation_tracking(
                    cache_key, invalidation_triggers or set()
                )

            # Track query pattern for warming
            self._track_query_pattern(query, parameters)

            # Store in distributed cache if available
            if self.redis_service:
                self._store_in_distributed_cache(cache_key, entry)

            logger.debug(f"Cached query result: {cache_key} ({size_bytes} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to cache query result: {e}")
            return False

    def _make_space(self, required_bytes: int) -> None:
        """Make space in cache by evicting entries based on policy."""
        current_size = sum(entry.size_bytes for entry in self._cache.values())

        if (
            current_size + required_bytes <= self.max_memory_bytes
            and len(self._cache) < self.max_entries
        ):
            return

        # Collect eviction candidates
        candidates = list(self._cache.items())

        if self.eviction_policy == CacheEvictionPolicy.LRU:
            candidates.sort(key=lambda x: x[1].last_accessed)
        elif self.eviction_policy == CacheEvictionPolicy.LFU:
            candidates.sort(key=lambda x: x[1].access_count)
        elif self.eviction_policy == CacheEvictionPolicy.TTL:
            candidates.sort(key=lambda x: x[1].created_at)
        else:  # HYBRID
            # Combine access time and frequency
            now = datetime.now()
            candidates.sort(
                key=lambda x: (
                    x[1].access_count * 0.3
                    + (now - x[1].last_accessed).total_seconds() / 3600 * 0.7
                )
            )

        # Evict entries until we have enough space
        bytes_to_free = (current_size + required_bytes) - self.max_memory_bytes
        entries_to_free = max(0, len(self._cache) + 1 - self.max_entries)

        evicted_count = 0
        freed_bytes = 0

        for cache_key, entry in candidates:
            if freed_bytes >= bytes_to_free and evicted_count >= entries_to_free:
                break

            del self._cache[cache_key]
            freed_bytes += entry.size_bytes
            evicted_count += 1

            # Remove from invalidation tracking
            self._remove_from_invalidation_tracking(cache_key)

        if evicted_count > 0:
            with self._stats_lock:
                self._stats.eviction_count += evicted_count

            logger.debug(
                f"Evicted {evicted_count} cache entries, freed {freed_bytes} bytes"
            )

    def _update_invalidation_tracking(self, cache_key: str, triggers: set[str]) -> None:
        """Update invalidation tracking for a cache entry."""
        with self._invalidation_lock:
            for table_name in triggers:
                if table_name not in self._table_watchers:
                    self._table_watchers[table_name] = set()
                self._table_watchers[table_name].add(cache_key)

    def _remove_from_invalidation_tracking(self, cache_key: str) -> None:
        """Remove cache key from invalidation tracking."""
        with self._invalidation_lock:
            for table_set in self._table_watchers.values():
                table_set.discard(cache_key)

    def invalidate_by_table(self, table_name: str) -> int:
        """
        Invalidate all cache entries that depend on a specific table.

        Args:
            table_name: Name of the table that was modified

        Returns:
            Number of cache entries invalidated
        """
        invalidated_count = 0

        with self._invalidation_lock:
            cache_keys_to_invalidate = self._table_watchers.get(
                table_name, set()
            ).copy()

        with self._cache_lock:
            for cache_key in cache_keys_to_invalidate:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"Invalidated {invalidated_count} cache entries for table {table_name}"
            )

        return invalidated_count

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """
        Invalidate all cache entries with specific tags.

        Args:
            tags: Tags to invalidate

        Returns:
            Number of cache entries invalidated
        """
        invalidated_count = 0

        with self._cache_lock:
            keys_to_remove = []
            for cache_key, entry in self._cache.items():
                if entry.tags.intersection(tags):
                    keys_to_remove.append(cache_key)

            for cache_key in keys_to_remove:
                del self._cache[cache_key]
                self._remove_from_invalidation_tracking(cache_key)
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"Invalidated {invalidated_count} cache entries by tags: {tags}"
            )

        return invalidated_count

    def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of cache entries cleared
        """
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()

        with self._invalidation_lock:
            self._table_watchers.clear()

        logger.info(f"Cleared all {count} cache entries")
        return count

    def _track_query_pattern(
        self, query: str, parameters: tuple[Any, ...] | None = None
    ) -> None:
        """Track query patterns for cache warming."""
        if not self.enable_warming:
            return

        query_hash = self._generate_cache_key(query, parameters)

        with self._pattern_lock:
            if query_hash not in self._query_patterns:
                self._query_patterns[query_hash] = {
                    "query": query,
                    "parameters": parameters,
                    "access_count": 0,
                    "last_access": datetime.now(),
                    "avg_execution_time": 0.0,
                    "warming_priority": 0.0,
                }

            pattern = self._query_patterns[query_hash]
            pattern["access_count"] += 1
            pattern["last_access"] = datetime.now()

    def _record_hit(self, cache_key: str, query: str) -> None:
        """Record cache hit statistics."""
        with self._stats_lock:
            self._stats.hit_count += 1

        # Update persistent statistics
        try:
            self.db.execute(
                """
                INSERT OR IGNORE INTO query_cache_stats
                (query_hash, query_text, hit_count, last_access)
                VALUES (?, ?, 0, ?)
            """,
                (cache_key, query, datetime.now().isoformat()),
            )

            self.db.execute(
                """
                UPDATE query_cache_stats
                SET hit_count = hit_count + 1, last_access = ?
                WHERE query_hash = ?
            """,
                (datetime.now().isoformat(), cache_key),
            )
        except Exception as e:
            logger.debug(f"Failed to update hit statistics: {e}")

    def _record_miss(self, cache_key: str, query: str) -> None:
        """Record cache miss statistics."""
        with self._stats_lock:
            self._stats.miss_count += 1

        # Update persistent statistics
        try:
            self.db.execute(
                """
                INSERT OR IGNORE INTO query_cache_stats
                (query_hash, query_text, miss_count, last_access)
                VALUES (?, ?, 0, ?)
            """,
                (cache_key, query, datetime.now().isoformat()),
            )

            self.db.execute(
                """
                UPDATE query_cache_stats
                SET miss_count = miss_count + 1, last_access = ?
                WHERE query_hash = ?
            """,
                (datetime.now().isoformat(), cache_key),
            )
        except Exception as e:
            logger.debug(f"Failed to update miss statistics: {e}")

    def _cleanup_worker(self) -> None:
        """Background worker for cache cleanup."""
        while not self._shutdown_event.wait(300):  # Run every 5 minutes
            try:
                self._cleanup_expired_entries()
                self._update_statistics()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    def _cleanup_expired_entries(self) -> None:
        """Remove expired cache entries."""
        expired_keys = []

        with self._cache_lock:
            for cache_key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(cache_key)

            for cache_key in expired_keys:
                del self._cache[cache_key]
                self._remove_from_invalidation_tracking(cache_key)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _warming_worker(self) -> None:
        """Background worker for cache warming."""
        while not self._shutdown_event.wait(600):  # Run every 10 minutes
            try:
                self._warm_cache()
            except Exception as e:
                logger.error(f"Cache warming error: {e}")

    def _warm_cache(self) -> None:
        """Warm cache with frequently accessed queries."""
        with self._pattern_lock:
            # Find queries that should be warmed
            warming_candidates = []

            for query_hash, pattern in self._query_patterns.items():
                if pattern["access_count"] >= self.DEFAULT_CACHE_WARMING_THRESHOLD:
                    # Check if already cached
                    with self._cache_lock:
                        if query_hash not in self._cache:
                            warming_candidates.append(pattern)

            # Sort by access count (most accessed first)
            warming_candidates.sort(key=lambda x: x["access_count"], reverse=True)

        # Warm cache with top candidates
        warmed_count = 0
        for pattern in warming_candidates[:10]:  # Limit to top 10
            try:
                query = pattern["query"]
                parameters = pattern["parameters"]

                # Execute query to warm cache
                start_time = time.time()
                if parameters:
                    result = self.db.fetch_all(query, parameters)
                else:
                    result = self.db.fetch_all(query)
                execution_time = (time.time() - start_time) * 1000

                # Cache the result
                self.put(
                    query=query,
                    result=result,
                    parameters=parameters,
                    tags={"warmed"},
                    ttl_seconds=self.DEFAULT_TTL_SECONDS
                    * 2,  # Longer TTL for warmed queries
                )

                warmed_count += 1
                logger.debug(
                    f"Warmed cache for query: {query[:50]}... ({execution_time:.2f}ms)"
                )

            except Exception as e:
                logger.warning(f"Failed to warm cache for query: {e}")

        if warmed_count > 0:
            logger.info(f"Warmed cache with {warmed_count} frequently accessed queries")

    def _update_statistics(self) -> None:
        """Update cache statistics."""
        with self._cache_lock:
            total_entries = len(self._cache)
            total_size = sum(entry.size_bytes for entry in self._cache.values())

        with self._stats_lock:
            self._stats.total_entries = total_entries
            self._stats.total_size_bytes = total_size
            self._stats.memory_usage_mb = total_size / (1024 * 1024)

            total_requests = self._stats.hit_count + self._stats.miss_count
            if total_requests > 0:
                self._stats.hit_rate = (self._stats.hit_count / total_requests) * 100

    def _store_in_distributed_cache(self, cache_key: str, entry: CacheEntry) -> None:
        """Store cache entry in distributed Redis cache."""
        if not self.redis_service:
            return

        try:
            # Serialize entry for Redis
            entry_data = {
                "query_text": entry.query_text,
                "result_data": entry.result_data.hex(),  # Store as hex string
                "created_at": entry.created_at.isoformat(),
                "ttl_seconds": entry.ttl_seconds,
                "tags": list(entry.tags),
            }

            # Store with TTL
            self.redis_service.set(
                f"query_cache:{cache_key}",
                json.dumps(entry_data),
                expire_time=entry.ttl_seconds,
            )

        except Exception as e:
            logger.debug(f"Failed to store in distributed cache: {e}")

    def get_statistics(self) -> CacheStats:
        """Get current cache statistics."""
        self._update_statistics()

        with self._stats_lock:
            return CacheStats(
                total_entries=self._stats.total_entries,
                total_size_bytes=self._stats.total_size_bytes,
                hit_count=self._stats.hit_count,
                miss_count=self._stats.miss_count,
                eviction_count=self._stats.eviction_count,
                hit_rate=self._stats.hit_rate,
                avg_response_time_ms=self._stats.avg_response_time_ms,
                memory_usage_mb=self._stats.memory_usage_mb,
            )

    def get_cache_info(self) -> dict[str, Any]:
        """Get detailed cache information."""
        stats = self.get_statistics()

        with self._cache_lock:
            entries_by_age = {}
            entries_by_size = {}

            now = datetime.now()
            for entry in self._cache.values():
                age_hours = (now - entry.created_at).total_seconds() / 3600
                age_bucket = f"{int(age_hours)}h"
                entries_by_age[age_bucket] = entries_by_age.get(age_bucket, 0) + 1

                size_bucket = (
                    f"{entry.size_bytes // 1024}KB"
                    if entry.size_bytes < 1024 * 1024
                    else f"{entry.size_bytes // (1024*1024)}MB"
                )
                entries_by_size[size_bucket] = entries_by_size.get(size_bucket, 0) + 1

        return {
            "statistics": stats.__dict__,
            "configuration": {
                "max_entries": self.max_entries,
                "max_memory_mb": self.max_memory_mb,
                "eviction_policy": self.eviction_policy.value,
                "enable_compression": self.enable_compression,
                "enable_warming": self.enable_warming,
            },
            "distribution": {
                "entries_by_age": entries_by_age,
                "entries_by_size": entries_by_size,
            },
        }

    def shutdown(self) -> None:
        """Shutdown the cache manager and cleanup resources."""
        self._shutdown_event.set()

        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        if self._warming_thread:
            self._warming_thread.join(timeout=5)

        self.clear_all()
        logger.info("Query cache manager shut down")


def main() -> Any:
    """CLI interface for the Query Cache Manager."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Query Cache Manager")
    parser.add_argument("--db-path", required=True, help="Database file path")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all cache entries")
    parser.add_argument(
        "--invalidate-table", help="Invalidate cache for specific table"
    )
    parser.add_argument(
        "--info", action="store_true", help="Show detailed cache information"
    )
    parser.add_argument("--output", help="Output file for results (JSON)")

    args = parser.parse_args()

    try:
        # Initialize cache manager
        db = DatabaseConnection(args.db_path)
        cache_manager = IntelligentQueryCacheManager(db)

        results = {}

        if args.stats:
            stats = cache_manager.get_statistics()
            results["statistics"] = stats.__dict__

            print("Cache Statistics:")
            print(f"Total Entries: {stats.total_entries}")
            print(f"Memory Usage: {stats.memory_usage_mb:.2f} MB")
            print(f"Hit Rate: {stats.hit_rate:.1f}%")
            print(f"Total Hits: {stats.hit_count}")
            print(f"Total Misses: {stats.miss_count}")
            print(f"Evictions: {stats.eviction_count}")

        if args.info:
            info = cache_manager.get_cache_info()
            results["cache_info"] = info

            print("Cache Configuration:")
            config = info["configuration"]
            print(f"Max Entries: {config['max_entries']}")
            print(f"Max Memory: {config['max_memory_mb']} MB")
            print(f"Eviction Policy: {config['eviction_policy']}")
            print(f"Compression: {config['enable_compression']}")
            print(f"Warming: {config['enable_warming']}")

        if args.clear:
            cleared = cache_manager.clear_all()
            results["cleared_entries"] = cleared
            print(f"Cleared {cleared} cache entries")

        if args.invalidate_table:
            invalidated = cache_manager.invalidate_by_table(args.invalidate_table)
            results["invalidated_entries"] = invalidated
            print(
                f"Invalidated {invalidated} cache entries for table {args.invalidate_table}"
            )

        # Save results if requested
        if args.output and results:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Results saved to {args.output}")

        cache_manager.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
