"""
Cache Coherency Manager
Manages data consistency across multi-layer cache architecture.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Union

# Import our cache services
from .l1_memory_cache import L1MemoryCache
from .l2_redis_cache import L2RedisCache
from .l3_cdn_cache import ContentType, L3CDNCache

logger = logging.getLogger(__name__)


# ============================================================================
# Coherency Configuration
# ============================================================================


class CoherencyProtocol(str, Enum):
    """Cache coherency protocols."""

    WRITE_THROUGH = "write_through"  # Write to all levels synchronously
    WRITE_BEHIND = "write_behind"  # Write to higher levels asynchronously
    WRITE_BACK = "write_back"  # Write only when evicted or expired
    INVALIDATE = "invalidate"  # Invalidate other levels on write
    BROADCAST = "broadcast"  # Broadcast all changes


class ConsistencyLevel(str, Enum):
    """Data consistency levels."""

    EVENTUAL = "eventual"  # Eventually consistent
    STRONG = "strong"  # Strong consistency
    WEAK = "weak"  # Weak consistency
    CAUSAL = "causal"  # Causal consistency


class InvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""

    IMMEDIATE = "immediate"  # Invalidate immediately
    LAZY = "lazy"  # Invalidate on next access
    TTL_BASED = "ttl_based"  # Invalidate based on TTL
    VERSION_BASED = "version_based"  # Version-based invalidation


@dataclass
class CoherencyConfig:
    """Configuration for cache coherency management."""

    # Coherency protocol
    protocol: CoherencyProtocol = CoherencyProtocol.WRITE_THROUGH
    consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    invalidation_strategy: InvalidationStrategy = InvalidationStrategy.IMMEDIATE

    # Timing configuration
    max_write_delay_ms: int = 100  # Maximum delay for write-behind
    invalidation_batch_size: int = 50  # Batch size for invalidations
    coherency_check_interval_seconds: int = 300  # 5 minutes

    # Versioning
    enable_versioning: bool = True
    version_header_name: str = "X-Cache-Version"

    # Conflict resolution
    conflict_resolution_strategy: str = "last_write_wins"  # timestamp, version, custom

    # Monitoring
    enable_coherency_monitoring: bool = True
    log_coherency_violations: bool = True


@dataclass
class CacheEntryVersion:
    """Version information for cache entries."""

    version: int
    timestamp: datetime
    source_level: str  # Which cache level this version came from
    checksum: str  # Data integrity checksum

    def is_newer_than(self, other: "CacheEntryVersion") -> bool:
        """Check if this version is newer than another."""
        if self.version != other.version:
            return self.version > other.version
        return self.timestamp > other.timestamp


@dataclass
class CoherencyEvent:
    """Cache coherency event for tracking."""

    event_type: str  # write, read, invalidate, sync
    key: str
    cache_level: str
    timestamp: datetime
    version: CacheEntryVersion | None = None
    data_size: int = 0
    success: bool = True
    error: str | None = None


# ============================================================================
# Cache Level Wrapper
# ============================================================================


class CacheLevelWrapper:
    """Wrapper for cache levels with coherency support."""

    def __init__(
        self,
        cache: L1MemoryCache | L2RedisCache | L3CDNCache,
        level_name: str,
        coherency_manager: "CacheCoherencyManager",
    ) -> None:
        """Initialize cache level wrapper."""
        self.cache = cache
        self.level_name = level_name
        self.coherency_manager = coherency_manager

        # Level-specific configuration
        self.is_local = isinstance(cache, L1MemoryCache)
        self.supports_ttl = True
        self.supports_versioning = True

    async def get(
        self, key: str, default: Any = None
    ) -> tuple[Any, CacheEntryVersion | None]:
        """Get value with version information."""
        try:
            # L1 Memory Cache
            if isinstance(self.cache, L1MemoryCache):
                value = self.cache.get(key, default)
                if value != default:
                    # Create version from L1 cache metadata
                    version = CacheEntryVersion(
                        version=1,  # L1 doesn't track versions
                        timestamp=datetime.utcnow(),
                        source_level=self.level_name,
                        checksum=self._calculate_checksum(value),
                    )
                    return value, version
                return default, None

            # L2 Redis Cache
            elif isinstance(self.cache, L2RedisCache):
                value = await self.cache.get(key, default)
                if value != default:
                    version = CacheEntryVersion(
                        version=1,  # Simplified for demo
                        timestamp=datetime.utcnow(),
                        source_level=self.level_name,
                        checksum=self._calculate_checksum(value),
                    )
                    return value, version
                return default, None

            # L3 CDN Cache
            elif isinstance(self.cache, L3CDNCache):
                # CDN cache doesn't have direct get - would check if URL is cached
                return default, None

            return default, None

        except Exception as e:
            logger.error(f"Error getting value from {self.level_name}: {e}")
            return default, None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        version: CacheEntryVersion | None = None,
    ) -> bool:
        """Set value with version information."""
        try:
            # Create or update version
            if version is None:
                version = CacheEntryVersion(
                    version=int(time.time()),
                    timestamp=datetime.utcnow(),
                    source_level=self.level_name,
                    checksum=self._calculate_checksum(value),
                )

            # L1 Memory Cache
            if isinstance(self.cache, L1MemoryCache):
                success = self.cache.set[str](key, value, ttl_seconds=ttl_seconds)

            # L2 Redis Cache
            elif isinstance(self.cache, L2RedisCache):
                success = await self.cache.set[str](key, value, ttl_seconds=ttl_seconds)

            # L3 CDN Cache
            elif isinstance(self.cache, L3CDNCache):
                # Convert value to bytes for CDN
                if isinstance(value, (dict[str, Any], list[Any])):
                    content_data = json.dumps(value).encode()
                    content_type = ContentType.API_RESPONSES
                else:
                    content_data = str(value).encode()
                    content_type = ContentType.DYNAMIC

                cdn_url = await self.cache.cache_content(
                    f"https://cache/{key}", content_data, content_type, ttl_seconds
                )
                success = cdn_url != f"https://cache/{key}"

            else:
                success = False

            # Record coherency event
            if success:
                await self.coherency_manager._record_event(
                    CoherencyEvent(
                        event_type="write",
                        key=key,
                        cache_level=self.level_name,
                        timestamp=datetime.utcnow(),
                        version=version,
                        data_size=len(str(value)),
                        success=True,
                    )
                )

            return success

        except Exception as e:
            logger.error(f"Error setting value in {self.level_name}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache level."""
        try:
            # L1 Memory Cache
            if isinstance(self.cache, L1MemoryCache):
                success = self.cache.delete(key)

            # L2 Redis Cache
            elif isinstance(self.cache, L2RedisCache):
                success = await self.cache.delete(key)

            # L3 CDN Cache
            elif isinstance(self.cache, L3CDNCache):
                success = await self.cache.invalidate_cache(f"https://cache/{key}")

            else:
                success = False

            # Record coherency event
            if success:
                await self.coherency_manager._record_event(
                    CoherencyEvent(
                        event_type="invalidate",
                        key=key,
                        cache_level=self.level_name,
                        timestamp=datetime.utcnow(),
                        success=True,
                    )
                )

            return success

        except Exception as e:
            logger.error(f"Error deleting key from {self.level_name}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache level."""
        try:
            if isinstance(self.cache, L1MemoryCache):
                return self.cache.exists(key)
            elif isinstance(self.cache, L2RedisCache):
                return await self.cache.exists(key)
            elif isinstance(self.cache, L3CDNCache):
                return key in self.cache.cached_urls
            return False
        except Exception as e:
            logger.error(f"Error checking existence in {self.level_name}: {e}")
            return False

    def _calculate_checksum(self, value: Any) -> str:
        """Calculate checksum for data integrity."""
        try:
            data_str = (
                json.dumps(value, sort_keys=True)
                if isinstance(value, (dict[str, Any], list[Any]))
                else str(value)
            )
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception:
            return ""


# ============================================================================
# Cache Coherency Manager
# ============================================================================


class CacheCoherencyManager:
    """
    Manages coherency across multi-layer cache architecture.
    """

    def __init__(
        self,
        l1_cache: L1MemoryCache | None = None,
        l2_cache: L2RedisCache | None = None,
        l3_cache: L3CDNCache | None = None,
        config: CoherencyConfig | None = None,
    ) -> None:
        """Initialize cache coherency manager."""
        self.config = config or CoherencyConfig()

        # Cache levels
        self.cache_levels: dict[str, CacheLevelWrapper] = {}

        if l1_cache:
            self.cache_levels["L1"] = CacheLevelWrapper(l1_cache, "L1", self)
        if l2_cache:
            self.cache_levels["L2"] = CacheLevelWrapper(l2_cache, "L2", self)
        if l3_cache:
            self.cache_levels["L3"] = CacheLevelWrapper(l3_cache, "L3", self)

        # Coherency tracking
        self.entry_versions: dict[str, dict[str, CacheEntryVersion]] = defaultdict(
            dict[str, Any]
        )
        self.coherency_events: deque[Any] = deque[Any](maxlen=10000)
        self.invalidation_queue: deque[Any] = deque[Any]()

        # Statistics
        self.stats = {
            "coherency_violations": 0,
            "write_through_operations": 0,
            "write_behind_operations": 0,
            "invalidations": 0,
            "version_conflicts": 0,
            "sync_operations": 0,
        }

        # Background tasks
        self.background_tasks: list[asyncio.Task[None]] = []
        self.is_running = False

        logger.info(
            f"Cache Coherency Manager initialized with {len(self.cache_levels)} levels"
        )

    # ========================================================================
    # Core Coherency Operations
    # ========================================================================

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value with coherency management."""

        try:
            # Try cache levels in order (L1 -> L2 -> L3)
            for level_name in ["L1", "L2", "L3"]:
                if level_name in self.cache_levels:
                    level = self.cache_levels[level_name]
                    value, version = await level.get(key, default)

                    if value != default and version:
                        # Record successful read
                        await self._record_event(
                            CoherencyEvent(
                                event_type="read",
                                key=key,
                                cache_level=level_name,
                                timestamp=datetime.utcnow(),
                                version=version,
                                success=True,
                            )
                        )

                        # Update version tracking
                        self.entry_versions[key][level_name] = version

                        # Promote to higher cache levels if configured
                        await self._promote_to_higher_levels(
                            key, value, version, level_name
                        )

                        return value

            # Not found in any cache level
            return default

        except Exception as e:
            logger.error(f"Error getting key {key} with coherency: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Set value with coherency management."""

        try:
            # Create new version
            new_version = CacheEntryVersion(
                version=int(time.time() * 1000),  # Timestamp-based version
                timestamp=datetime.utcnow(),
                source_level="coherency_manager",
                checksum=self._calculate_checksum(value),
            )

            # Apply coherency protocol
            if self.config.protocol == CoherencyProtocol.WRITE_THROUGH:
                return await self._write_through(key, value, ttl_seconds, new_version)

            elif self.config.protocol == CoherencyProtocol.WRITE_BEHIND:
                return await self._write_behind(key, value, ttl_seconds, new_version)

            elif self.config.protocol == CoherencyProtocol.INVALIDATE:
                return await self._write_with_invalidation(
                    key, value, ttl_seconds, new_version
                )

            elif self.config.protocol == CoherencyProtocol.BROADCAST:
                return await self._broadcast_write(key, value, ttl_seconds, new_version)

            else:
                # Default to write-through
                return await self._write_through(key, value, ttl_seconds, new_version)

        except Exception as e:
            logger.error(f"Error setting key {key} with coherency: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key with coherency management."""
        try:
            success_count = 0

            # Delete from all cache levels
            for _level_name, level in self.cache_levels.items():
                if await level.delete(key):
                    success_count += 1

            # Clean up version tracking
            self.entry_versions.pop(key, None)

            # Record invalidation
            await self._record_event(
                CoherencyEvent(
                    event_type="invalidate",
                    key=key,
                    cache_level="all",
                    timestamp=datetime.utcnow(),
                    success=success_count > 0,
                )
            )

            self.stats["invalidations"] += 1

            return success_count > 0

        except Exception as e:
            logger.error(f"Error deleting key {key} with coherency: {e}")
            return False

    # ========================================================================
    # Coherency Protocol Implementations
    # ========================================================================

    async def _write_through(
        self, key: str, value: Any, ttl_seconds: int | None, version: CacheEntryVersion
    ) -> bool:
        """Write-through coherency protocol."""
        success_count = 0

        # Write to all cache levels synchronously
        for level_name, level in self.cache_levels.items():
            try:
                if await level.set[str](key, value, ttl_seconds, version):
                    success_count += 1
                    self.entry_versions[key][level_name] = version
            except Exception as e:
                logger.error(f"Write-through failed for level {level_name}: {e}")

        self.stats["write_through_operations"] += 1

        # Consider success if at least one level succeeded
        return success_count > 0

    async def _write_behind(
        self, key: str, value: Any, ttl_seconds: int | None, version: CacheEntryVersion
    ) -> bool:
        """Write-behind coherency protocol."""
        # Write to L1 (fastest) immediately
        l1_success = False
        if "L1" in self.cache_levels:
            l1_success = await self.cache_levels["L1"].set[str](
                key, value, ttl_seconds, version
            )
            if l1_success:
                self.entry_versions[key]["L1"] = version

        # Queue writes for other levels
        for level_name in ["L2", "L3"]:
            if level_name in self.cache_levels:
                self.invalidation_queue.append(
                    {
                        "operation": "set[str]",
                        "key": key,
                        "value": value,
                        "ttl_seconds": ttl_seconds,
                        "version": version,
                        "level_name": level_name,
                        "timestamp": datetime.utcnow(),
                    }
                )

        self.stats["write_behind_operations"] += 1

        return l1_success

    async def _write_with_invalidation(
        self, key: str, value: Any, ttl_seconds: int | None, version: CacheEntryVersion
    ) -> bool:
        """Write with invalidation protocol."""
        # Write to primary cache level (L1 if available, otherwise L2)
        primary_level = "L1" if "L1" in self.cache_levels else "L2"

        if primary_level in self.cache_levels:
            success = await self.cache_levels[primary_level].set[str](
                key, value, ttl_seconds, version
            )

            if success:
                self.entry_versions[key][primary_level] = version

                # Invalidate in other levels
                for level_name, level in self.cache_levels.items():
                    if level_name != primary_level:
                        await level.delete(key)
                        self.entry_versions[key].pop(level_name, None)

                self.stats["invalidations"] += len(self.cache_levels) - 1

                return True

        return False

    async def _broadcast_write(
        self, key: str, value: Any, ttl_seconds: int | None, version: CacheEntryVersion
    ) -> bool:
        """Broadcast write protocol."""
        # Similar to write-through but with better error handling
        tasks = []

        for level_name, level in self.cache_levels.items():
            task = asyncio.create_task(
                self._safe_write_to_level(level, key, value, ttl_seconds, version)
            )
            tasks.append((level_name, task))

        # Wait for all writes with timeout
        success_count = 0

        try:
            # Wait with timeout
            await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=self.config.max_write_delay_ms / 1000,
            )

            # Check results
            for level_name, task in tasks:
                try:
                    if task.done() and await task:
                        success_count += 1
                        self.entry_versions[key][level_name] = version
                except Exception as e:
                    logger.error(f"Broadcast write failed for level {level_name}: {e}")

        except asyncio.TimeoutError:
            logger.warning(f"Broadcast write timeout for key {key}")

        return success_count > 0

    async def _safe_write_to_level(
        self,
        level: CacheLevelWrapper,
        key: str,
        value: Any,
        ttl_seconds: int | None,
        version: CacheEntryVersion,
    ) -> bool:
        """Safely write to cache level with error handling."""
        try:
            return await level.set[str](key, value, ttl_seconds, version)
        except Exception as e:
            logger.error(f"Error writing to level {level.level_name}: {e}")
            return False

    # ========================================================================
    # Cache Promotion and Demotion
    # ========================================================================

    async def _promote_to_higher_levels(
        self, key: str, value: Any, version: CacheEntryVersion, source_level: str
    ) -> None:
        """Promote cache entry to higher levels."""
        # Determine promotion targets
        promotion_targets = []

        if source_level == "L3" and "L2" in self.cache_levels:
            promotion_targets.append("L2")
        if source_level in ["L3", "L2"] and "L1" in self.cache_levels:
            promotion_targets.append("L1")

        # Promote to target levels
        for target_level in promotion_targets:
            try:
                level = self.cache_levels[target_level]

                # Check if we should promote (not if already exists with newer version)
                if target_level in self.entry_versions.get(key, {}):
                    existing_version = self.entry_versions[key][target_level]
                    if existing_version.is_newer_than(version):
                        continue  # Don't promote older version

                # Promote
                await level.set[str](key, value, ttl_seconds=None, version=version)
                self.entry_versions[key][target_level] = version

                logger.debug(
                    f"Promoted key {key} from {source_level} to {target_level}"
                )

            except Exception as e:
                logger.error(f"Error promoting key {key} to {target_level}: {e}")

    # ========================================================================
    # Version Management and Conflict Resolution
    # ========================================================================

    async def check_coherency(self, key: str) -> dict[str, Any]:
        """Check coherency status for a key."""
        coherency_info = {
            "key": key,
            "consistent": True,
            "versions": {},
            "conflicts": [],
            "recommendations": [],
        }

        # Get versions from all levels
        versions = {}

        for level_name, level in self.cache_levels.items():
            try:
                value, version = await level.get(key)
                if version:
                    versions[level_name] = {
                        "version": version.version,
                        "timestamp": version.timestamp.isoformat(),
                        "checksum": version.checksum,
                    }
            except Exception as e:
                logger.error(f"Error checking coherency for {level_name}: {e}")

        coherency_info["versions"] = versions

        # Check for conflicts
        if len(versions) > 1:
            version_values = [v["version"] for v in versions.values()]
            checksums = [v["checksum"] for v in versions.values()]

            # Version conflicts
            if len(set[str](version_values)) > 1:
                coherency_info["consistent"] = False
                coherency_info["conflicts"].append("version_mismatch")

            # Data conflicts
            if len(set[str](checksums)) > 1:
                coherency_info["consistent"] = False
                coherency_info["conflicts"].append("data_mismatch")

        # Generate recommendations
        if not coherency_info["consistent"]:
            coherency_info[
                "recommendations"
            ] = await self._generate_coherency_recommendations(key, versions)

        return coherency_info

    async def _generate_coherency_recommendations(
        self, key: str, versions: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Generate recommendations for resolving coherency issues."""
        recommendations: list[Any] = []

        if not versions:
            return recommendations

        # Find the most recent version
        latest_level = max(
            versions.keys(), key=lambda level: versions[level]["version"]
        )

        recommendations.append(f"Sync all levels to version from {latest_level}")

        # Check for missing levels
        expected_levels = set[str](self.cache_levels.keys())
        present_levels = set[str](versions.keys())
        missing_levels = expected_levels - present_levels

        if missing_levels:
            recommendations.append(
                f"Populate missing cache levels: {', '.join(missing_levels)}"
            )

        return recommendations

    async def resolve_conflicts(self, key: str) -> bool:
        """Resolve coherency conflicts for a key."""
        try:
            coherency_info = await self.check_coherency(key)

            if coherency_info["consistent"]:
                return True  # No conflicts to resolve

            # Apply conflict resolution strategy
            if self.config.conflict_resolution_strategy == "last_write_wins":
                return await self._resolve_last_write_wins(key)
            elif self.config.conflict_resolution_strategy == "version":
                return await self._resolve_by_version(key)
            else:
                return await self._resolve_custom(key)

        except Exception as e:
            logger.error(f"Error resolving conflicts for key {key}: {e}")
            return False

    async def _resolve_last_write_wins(self, key: str) -> bool:
        """Resolve conflicts using last-write-wins strategy."""
        latest_version = None
        latest_value = None

        # Find the latest version across all levels
        for level_name, level in self.cache_levels.items():
            try:
                value, version = await level.get(key)
                if version and (
                    latest_version is None or version.is_newer_than(latest_version)
                ):
                    latest_version = version
                    latest_value = value
            except Exception as e:
                logger.error(f"Error getting version from {level_name}: {e}")

        # Sync all levels to the latest version
        if latest_version and latest_value is not None:
            await self._sync_all_levels(key, latest_value, latest_version)
            return True

        return False

    async def _resolve_by_version(self, key: str) -> bool:
        """Resolve conflicts by version number."""
        # Similar to last_write_wins but strictly by version number
        return await self._resolve_last_write_wins(key)

    async def _resolve_custom(self, key: str) -> bool:
        """Custom conflict resolution logic."""
        # Placeholder for custom resolution logic
        return await self._resolve_last_write_wins(key)

    async def _sync_all_levels(
        self, key: str, value: Any, version: CacheEntryVersion
    ) -> None:
        """Sync all cache levels to a specific version."""
        for level_name, level in self.cache_levels.items():
            try:
                await level.set[str](key, value, ttl_seconds=None, version=version)
                self.entry_versions[key][level_name] = version
            except Exception as e:
                logger.error(f"Error syncing level {level_name}: {e}")

        self.stats["sync_operations"] += 1

    # ========================================================================
    # Background Processing
    # ========================================================================

    async def start_background_processing(self) -> None:
        """Start background coherency processing."""
        if self.is_running:
            return

        self.is_running = True

        # Start background tasks
        self.background_tasks = [
            asyncio.create_task(self._process_write_behind_queue()),
            asyncio.create_task(self._periodic_coherency_check()),
            asyncio.create_task(self._cleanup_expired_versions()),
        ]

        logger.info("Started cache coherency background processing")

    async def stop_background_processing(self) -> None:
        """Stop background coherency processing."""
        self.is_running = False

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()

        logger.info("Stopped cache coherency background processing")

    async def _process_write_behind_queue(self) -> None:
        """Process write-behind operations."""
        while self.is_running:
            try:
                # Process batch of operations
                batch = []
                for _ in range(self.config.invalidation_batch_size):
                    if self.invalidation_queue:
                        batch.append(self.invalidation_queue.popleft())
                    else:
                        break

                if not batch:
                    await asyncio.sleep(self.config.max_write_delay_ms / 1000)
                    continue

                # Execute batch operations
                for operation in batch:
                    try:
                        if operation["operation"] == "set[str]":
                            level_name = operation["level_name"]
                            level = self.cache_levels.get(level_name)

                            if level:
                                await level.set[str](
                                    operation["key"],
                                    operation["value"],
                                    operation["ttl_seconds"],
                                    operation["version"],
                                )

                                # Update version tracking
                                self.entry_versions[operation["key"]][level_name] = (
                                    operation["version"]
                                )

                    except Exception as e:
                        logger.error(f"Error in write-behind operation: {e}")

                logger.debug(f"Processed {len(batch)} write-behind operations")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in write-behind processing: {e}")
                await asyncio.sleep(1)

    async def _periodic_coherency_check(self) -> None:
        """Periodically check cache coherency."""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.coherency_check_interval_seconds)

                # Check coherency for a sample of keys
                keys_to_check = list[Any](self.entry_versions.keys())[
                    :100
                ]  # Sample of 100 keys

                violations = 0

                for key in keys_to_check:
                    coherency_info = await self.check_coherency(key)

                    if not coherency_info["consistent"]:
                        violations += 1

                        if self.config.log_coherency_violations:
                            logger.warning(
                                f"Coherency violation detected for key {key}: {coherency_info['conflicts']}"
                            )

                        # Auto-resolve if configured
                        if (
                            self.config.invalidation_strategy
                            == InvalidationStrategy.IMMEDIATE
                        ):
                            await self.resolve_conflicts(key)

                self.stats["coherency_violations"] += violations

                if violations > 0:
                    logger.info(
                        f"Coherency check completed: {violations}/{len(keys_to_check)} violations detected"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic coherency check: {e}")

    async def _cleanup_expired_versions(self) -> None:
        """Clean up expired version information."""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Clean up hourly

                now = datetime.utcnow()
                expired_keys = []

                for key, levels in self.entry_versions.items():
                    for level_name, version in list[Any](levels.items()):
                        # Remove versions older than 24 hours
                        if (now - version.timestamp).total_seconds() > 86400:
                            expired_keys.append((key, level_name))

                # Remove expired versions
                for key, level_name in expired_keys:
                    if (
                        key in self.entry_versions
                        and level_name in self.entry_versions[key]
                    ):
                        del self.entry_versions[key][level_name]

                        # Remove key entry if no levels left
                        if not self.entry_versions[key]:
                            del self.entry_versions[key]

                if expired_keys:
                    logger.debug(
                        f"Cleaned up {len(expired_keys)} expired version entries"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in version cleanup: {e}")

    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================

    async def _record_event(self, event: CoherencyEvent) -> None:
        """Record coherency event."""
        self.coherency_events.append(event)

        if self.config.enable_coherency_monitoring:
            # Log significant events
            if event.event_type in ["write", "invalidate"]:
                logger.debug(
                    f"Coherency event: {event.event_type} for key {event.key} in {event.cache_level}"
                )

    def get_coherency_stats(self) -> dict[str, Any]:
        """Get coherency statistics."""
        return {
            "stats": self.stats.copy(),
            "cache_levels": len(self.cache_levels),
            "tracked_keys": len(self.entry_versions),
            "write_behind_queue_size": len(self.invalidation_queue),
            "recent_events": len(self.coherency_events),
            "config": {
                "protocol": self.config.protocol.value,
                "consistency_level": self.config.consistency_level.value,
                "invalidation_strategy": self.config.invalidation_strategy.value,
            },
        }

    def get_coherency_health(self) -> dict[str, Any]:
        """Get coherency health status."""
        total_keys = len(self.entry_versions)
        violations = self.stats.get("coherency_violations", 0)

        violation_rate = (violations / max(total_keys, 1)) * 100

        health_status = "healthy"
        if violation_rate > 10:
            health_status = "critical"
        elif violation_rate > 5:
            health_status = "degraded"
        elif violation_rate > 1:
            health_status = "warning"

        return {
            "status": health_status,
            "violation_rate_percent": round(violation_rate, 2),
            "total_violations": violations,
            "queue_health": (
                "healthy" if len(self.invalidation_queue) < 1000 else "overloaded"
            ),
            "recommendations": self._get_health_recommendations(violation_rate),
        }

    def _get_health_recommendations(self, violation_rate: float) -> list[str]:
        """Get health recommendations."""
        recommendations = []

        if violation_rate > 10:
            recommendations.append(
                "Critical coherency violations detected. Consider stronger consistency level."
            )
        elif violation_rate > 5:
            recommendations.append(
                "High coherency violations. Review cache invalidation strategy."
            )

        if len(self.invalidation_queue) > 1000:
            recommendations.append(
                "Write-behind queue is overloaded. Consider increasing batch size or processing frequency."
            )

        return recommendations

    def _calculate_checksum(self, value: Any) -> str:
        """Calculate checksum for data integrity."""
        try:
            data_str = (
                json.dumps(value, sort_keys=True)
                if isinstance(value, (dict[str, Any], list[Any]))
                else str(value)
            )
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception:
            return ""

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self) -> None:
        """Async context manager entry."""
        await self.start_background_processing()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop_background_processing()


# Example usage
if __name__ == "__main__":

    async def main() -> None:
        from .l1_memory_cache import create_l1_cache
        from .l2_redis_cache import L2RedisCache
        from .redis_cache_service import RedisCacheService, RedisConfig

        # Create cache levels
        l1_cache = create_l1_cache(max_size_mb=50.0)
        redis_cache = RedisCacheService(RedisConfig())
        l2_cache = L2RedisCache(redis_cache)

        # Create coherency manager
        coherency_config = CoherencyConfig(
            protocol=CoherencyProtocol.WRITE_THROUGH,
            consistency_level=ConsistencyLevel.STRONG,
        )

        coherency_manager = CacheCoherencyManager(
            l1_cache=l1_cache, l2_cache=l2_cache, config=coherency_config
        )

        async with coherency_manager:
            # Set values with coherency
            await coherency_manager.set[str]("user:123", {"name": "John", "age": 30})
            await coherency_manager.set[str](
                "document:456", {"title": "Test Doc", "size": 1024}
            )

            # Get values
            user = await coherency_manager.get("user:123")
            document = await coherency_manager.get("document:456")

            print(f"User: {user}")
            print(f"Document: {document}")

            # Check coherency
            coherency_info = await coherency_manager.check_coherency("user:123")
            print(f"Coherency info: {coherency_info}")

            # Get statistics
            stats = coherency_manager.get_coherency_stats()
            print(f"Coherency stats: {stats}")

            # Get health status
            health = coherency_manager.get_coherency_health()
            print(f"Coherency health: {health}")

    # Run example
    # asyncio.run(main())
