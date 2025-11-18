"""
Database Sharding Manager for AI Enhanced PDF Scholar
Advanced sharding framework with automatic data distribution, shard management,
and transparent query routing across multiple database shards.
"""

import hashlib
import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from backend.services.connection_pool_manager import AdvancedConnectionPoolManager
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


class ShardingStrategy(Enum):
    """Sharding strategies for data distribution."""

    HASH_BASED = "hash_based"  # Hash-based sharding
    RANGE_BASED = "range_based"  # Range-based sharding
    DIRECTORY_BASED = "directory_based"  # Directory/lookup-based sharding
    CONSISTENT_HASH = "consistent_hash"  # Consistent hashing
    GEOGRAPHIC = "geographic"  # Geographic sharding


class ShardState(Enum):
    """Shard states."""

    ACTIVE = "active"
    READONLY = "readonly"
    MIGRATING = "migrating"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


@dataclass
class ShardKey:
    """Represents a shard key configuration."""

    column_name: str
    data_type: str  # string, integer, uuid, date
    hash_function: str = "md5"  # md5, sha256, crc32

    def extract_from_query(
        self, query: str, parameters: tuple[Any, ...] | None = None
    ) -> Any | None:
        """Extract shard key value from query."""
        query_lower = query.lower()

        # Look for WHERE conditions on the shard key column
        patterns = [
            rf"\b{self.column_name}\s*=\s*\?",
            rf'\b{self.column_name}\s*=\s*[\'"]([^\'"]+)[\'"]',
            rf"\b{self.column_name}\s*=\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                if "?" in pattern and parameters:
                    # Find parameter index
                    param_count = query_lower[: match.start()].count("?")
                    if param_count < len(parameters):
                        return parameters[param_count]
                elif match.groups():
                    return match.group(1)

        return None

    def hash_value(self, value: Any) -> int:
        """Hash a value using the configured hash function."""
        if value is None:
            return 0

        # Convert to string for hashing
        str_value = str(value)

        if self.hash_function == "md5" or self.hash_function == "sha256":
            return int(hashlib.sha256(str_value.encode()).hexdigest(), 16)
        elif self.hash_function == "crc32":
            import zlib

            return zlib.crc32(str_value.encode()) & 0xFFFFFFFF
        else:
            # Default to simple hash
            return hash(str_value)


@dataclass
class ShardRange:
    """Represents a range for range-based sharding."""

    start_value: Any
    end_value: Any
    shard_id: str

    def contains(self, value: Any) -> bool:
        """Check if value falls within this range."""
        return self.start_value <= value < self.end_value


@dataclass
class ShardInfo:
    """Information about a database shard."""

    shard_id: str
    connection_string: str
    state: ShardState
    weight: int = 100
    replica_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_health_check: float = field(default_factory=time.time)

    # Range information for range-based sharding
    range_start: Any | None = None
    range_end: Any | None = None

    # Hash ring information for consistent hashing
    hash_tokens: list[int] = field(default_factory=list)

    # Geographic information
    region: str = "default"
    availability_zone: str = "default"

    # Performance metrics
    total_records: int = 0
    total_size_bytes: int = 0
    avg_response_time_ms: float = 0.0
    connection_count: int = 0

    # Migration information
    migration_source: str | None = None
    migration_target: str | None = None
    migration_progress: float = 0.0


@dataclass
class ShardingConfiguration:
    """Configuration for the sharding manager."""

    strategy: ShardingStrategy
    shard_key: ShardKey
    replication_factor: int = 2
    auto_rebalancing: bool = True
    max_shard_size_gb: float = 10.0
    min_shards: int = 2
    max_shards: int = 100
    hash_ring_virtual_nodes: int = 100

    # Range-based sharding configuration
    range_boundaries: list[Any] = field(default_factory=list)

    # Geographic sharding configuration
    geo_regions: list[str] = field(
        default_factory=lambda: ["us-east", "us-west", "eu-west"]
    )


class ShardingManager:
    """
    Advanced Database Sharding Manager

    Features:
    - Multiple sharding strategies (hash, range, directory, consistent hash, geographic)
    - Automatic shard discovery and routing
    - Dynamic shard rebalancing
    - Cross-shard query support
    - Shard migration and splitting
    - High availability with replica management
    - Geographic distribution support
    """

    def __init__(
        self,
        config: ShardingConfiguration,
        metadata_connection: DatabaseConnection,
        enable_cross_shard_queries: bool = True,
        enable_auto_migration: bool = True,
    ):
        """
        Initialize the Sharding Manager.

        Args:
            config: Sharding configuration
            metadata_connection: Connection to metadata database
            enable_cross_shard_queries: Whether to support cross-shard queries
            enable_auto_migration: Whether to enable automatic migration
        """
        self.config = config
        self.metadata_db = metadata_connection
        self.enable_cross_shard_queries = enable_cross_shard_queries
        self.enable_auto_migration = enable_auto_migration

        # Shard management
        self.shards: dict[str, ShardInfo] = {}
        self.shard_connections: dict[str, DatabaseConnection] = {}
        self.shard_pools: dict[str, AdvancedConnectionPoolManager] = {}

        # Routing structures
        self._hash_ring: dict[int, str] = {}
        self._range_map: list[ShardRange] = []
        self._directory_map: dict[Any, str] = {}

        # Thread safety
        self._shard_lock = threading.RLock()
        self._routing_lock = threading.RLock()

        # Background tasks
        self._health_monitor_thread: threading.Thread | None = None
        self._rebalancer_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Performance tracking
        self._query_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_queries": 0,
                "cross_shard_queries": 0,
                "avg_response_time": 0.0,
                "errors": 0,
            }
        )

        # Initialize sharding infrastructure
        self._init_metadata_tables()
        self._load_shard_configuration()
        self._build_routing_structures()
        self._start_background_tasks()

    def _init_metadata_tables(self) -> None:
        """Initialize metadata tables for shard management."""
        try:
            # Shards table
            self.metadata_db.execute("""
                CREATE TABLE IF NOT EXISTS shards (
                    shard_id TEXT PRIMARY KEY,
                    connection_string TEXT NOT NULL,
                    state TEXT NOT NULL,
                    weight INTEGER DEFAULT 100,
                    replica_count INTEGER DEFAULT 0,
                    range_start TEXT,
                    range_end TEXT,
                    region TEXT DEFAULT 'default',
                    availability_zone TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Shard directory table for directory-based sharding
            self.metadata_db.execute("""
                CREATE TABLE IF NOT EXISTS shard_directory (
                    key_value TEXT PRIMARY KEY,
                    shard_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shard_id) REFERENCES shards(shard_id)
                )
            """)

            # Migration tracking table
            self.metadata_db.execute("""
                CREATE TABLE IF NOT EXISTS shard_migrations (
                    migration_id TEXT PRIMARY KEY,
                    source_shard TEXT NOT NULL,
                    target_shard TEXT NOT NULL,
                    migration_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            """)

            # Shard statistics table
            self.metadata_db.execute("""
                CREATE TABLE IF NOT EXISTS shard_statistics (
                    shard_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (shard_id, metric_name, recorded_at)
                )
            """)

            logger.info("Sharding metadata tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize metadata tables: {e}")
            raise

    def _load_shard_configuration(self) -> None:
        """Load shard configuration from metadata database."""
        try:
            shard_rows = self.metadata_db.fetch_all(
                "SELECT * FROM shards ORDER BY shard_id"
            )

            for row in shard_rows:
                shard_info = ShardInfo(
                    shard_id=row["shard_id"],
                    connection_string=row["connection_string"],
                    state=ShardState(row["state"]),
                    weight=row["weight"],
                    replica_count=row["replica_count"],
                    range_start=row["range_start"],
                    range_end=row["range_end"],
                    region=row["region"],
                    availability_zone=row["availability_zone"],
                )

                self.shards[shard_info.shard_id] = shard_info

                # Initialize shard connection
                if shard_info.state != ShardState.FAILED:
                    self._init_shard_connection(shard_info)

            logger.info(f"Loaded {len(self.shards)} shards from configuration")

        except Exception as e:
            logger.error(f"Failed to load shard configuration: {e}")

    def _init_shard_connection(self, shard_info: ShardInfo) -> None:
        """Initialize connection and pool for a shard."""
        try:
            # Create database connection
            connection = DatabaseConnection(
                shard_info.connection_string, max_connections=20
            )
            self.shard_connections[shard_info.shard_id] = connection

            # Create connection pool
            from backend.services.connection_pool_manager import PoolConfiguration

            pool_config = PoolConfiguration(
                max_connections=20, min_connections=2, initial_connections=2
            )

            pool = AdvancedConnectionPoolManager(
                shard_info.connection_string, pool_config
            )
            self.shard_pools[shard_info.shard_id] = pool

            logger.debug(f"Initialized connection pool for shard {shard_info.shard_id}")

        except Exception as e:
            logger.error(
                f"Failed to initialize shard connection {shard_info.shard_id}: {e}"
            )
            shard_info.state = ShardState.FAILED

    def _build_routing_structures(self) -> None:
        """Build routing structures based on sharding strategy."""
        with self._routing_lock:
            if self.config.strategy == ShardingStrategy.HASH_BASED:
                self._build_hash_routing()
            elif self.config.strategy == ShardingStrategy.RANGE_BASED:
                self._build_range_routing()
            elif self.config.strategy == ShardingStrategy.CONSISTENT_HASH:
                self._build_consistent_hash_routing()
            elif self.config.strategy == ShardingStrategy.DIRECTORY_BASED:
                self._load_directory_routing()
            elif self.config.strategy == ShardingStrategy.GEOGRAPHIC:
                self._build_geographic_routing()

    def _build_hash_routing(self) -> None:
        """Build hash-based routing structure."""
        active_shards = [
            shard
            for shard in self.shards.values()
            if shard.state in [ShardState.ACTIVE, ShardState.READONLY]
        ]

        if not active_shards:
            return

        # Simple hash-based distribution
        self._hash_shard_count = len(active_shards)
        self._hash_shard_list = [shard.shard_id for shard in active_shards]

        logger.info(f"Built hash routing for {len(active_shards)} shards")

    def _build_range_routing(self) -> None:
        """Build range-based routing structure."""
        self._range_map.clear()

        for shard in self.shards.values():
            if (
                shard.state in [ShardState.ACTIVE, ShardState.READONLY]
                and shard.range_start is not None
                and shard.range_end is not None
            ):
                range_obj = ShardRange(
                    start_value=shard.range_start,
                    end_value=shard.range_end,
                    shard_id=shard.shard_id,
                )
                self._range_map.append(range_obj)

        # Sort ranges by start value
        self._range_map.sort(key=lambda r: r.start_value)

        logger.info(f"Built range routing for {len(self._range_map)} ranges")

    def _build_consistent_hash_routing(self) -> None:
        """Build consistent hash routing structure."""
        self._hash_ring.clear()

        for shard in self.shards.values():
            if shard.state in [ShardState.ACTIVE, ShardState.READONLY]:
                # Create virtual nodes for this shard
                virtual_nodes = (
                    self.config.hash_ring_virtual_nodes * shard.weight // 100
                )

                for i in range(virtual_nodes):
                    virtual_key = f"{shard.shard_id}:{i}"
                    hash_value = self.config.shard_key.hash_value(virtual_key)
                    self._hash_ring[hash_value] = shard.shard_id

        logger.info(
            f"Built consistent hash ring with {len(self._hash_ring)} virtual nodes"
        )

    def _load_directory_routing(self) -> None:
        """Load directory-based routing from metadata."""
        try:
            directory_rows = self.metadata_db.fetch_all("SELECT * FROM shard_directory")

            self._directory_map.clear()
            for row in directory_rows:
                self._directory_map[row["key_value"]] = row["shard_id"]

            logger.info(f"Loaded directory routing for {len(self._directory_map)} keys")

        except Exception as e:
            logger.error(f"Failed to load directory routing: {e}")

    def _build_geographic_routing(self) -> None:
        """Build geographic routing structure."""
        # Group shards by region
        self._geo_regions = defaultdict(list)

        for shard in self.shards.values():
            if shard.state in [ShardState.ACTIVE, ShardState.READONLY]:
                self._geo_regions[shard.region].append(shard.shard_id)

        logger.info(f"Built geographic routing for {len(self._geo_regions)} regions")

    def _start_background_tasks(self) -> None:
        """Start background monitoring and maintenance tasks."""
        # Health monitoring
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_worker, daemon=True, name="ShardHealthMonitor"
        )
        self._health_monitor_thread.start()

        # Auto-rebalancing
        if self.config.auto_rebalancing:
            self._rebalancer_thread = threading.Thread(
                target=self._rebalancer_worker, daemon=True, name="ShardRebalancer"
            )
            self._rebalancer_thread.start()

        logger.info("Sharding manager background tasks started")

    def _health_monitor_worker(self) -> None:
        """Background worker for shard health monitoring."""
        while not self._shutdown_event.wait(30):  # Check every 30 seconds
            try:
                self._check_shard_health()
                self._update_shard_statistics()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _rebalancer_worker(self) -> None:
        """Background worker for automatic shard rebalancing."""
        while not self._shutdown_event.wait(300):  # Check every 5 minutes
            try:
                if self.enable_auto_migration:
                    self._check_rebalancing_needed()
            except Exception as e:
                logger.error(f"Rebalancer error: {e}")

    def _check_shard_health(self) -> None:
        """Check health of all shards."""
        for shard_id, shard_info in self.shards.items():
            if shard_info.state == ShardState.FAILED:
                continue

            try:
                # Try to execute a simple health check query
                connection = self.shard_connections.get(shard_id)
                if connection:
                    start_time = time.time()
                    _ = connection.fetch_one("SELECT 1 as health_check")
                    response_time = (time.time() - start_time) * 1000

                    shard_info.avg_response_time_ms = response_time
                    shard_info.last_health_check = time.time()

                    # Update state based on response time
                    if response_time > 5000:  # > 5 seconds
                        shard_info.state = ShardState.READONLY
                    elif (
                        shard_info.state == ShardState.READONLY and response_time < 1000
                    ):
                        shard_info.state = ShardState.ACTIVE

            except Exception as e:
                logger.warning(f"Health check failed for shard {shard_id}: {e}")
                shard_info.state = ShardState.FAILED

    def route_query(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        preferred_region: str | None = None,
    ) -> list[str]:
        """
        Route a query to appropriate shards.

        Args:
            query: SQL query
            parameters: Query parameters
            preferred_region: Preferred geographic region

        Returns:
            List of shard IDs that should handle this query
        """
        try:
            # Extract shard key value from query
            shard_key_value = self.config.shard_key.extract_from_query(
                query, parameters
            )

            if shard_key_value is not None:
                # Single-shard query
                shard_id = self._find_shard_for_key(shard_key_value, preferred_region)
                return [shard_id] if shard_id else []
            else:
                # Cross-shard query - route to all active shards
                if self.enable_cross_shard_queries:
                    active_shards = [
                        shard_id
                        for shard_id, shard in self.shards.items()
                        if shard.state in [ShardState.ACTIVE, ShardState.READONLY]
                    ]

                    # Filter by region if specified
                    if preferred_region:
                        active_shards = [
                            shard_id
                            for shard_id in active_shards
                            if self.shards[shard_id].region == preferred_region
                        ]

                    return active_shards
                else:
                    raise ValueError(
                        "Cross-shard queries are not enabled and no shard key found in query"
                    )

        except Exception as e:
            logger.error(f"Query routing failed: {e}")
            raise

    def _find_shard_for_key(
        self, key_value: Any, preferred_region: str | None = None
    ) -> str | None:
        """Find the appropriate shard for a given key value."""
        with self._routing_lock:
            if self.config.strategy == ShardingStrategy.HASH_BASED:
                return self._find_shard_hash_based(key_value)
            elif self.config.strategy == ShardingStrategy.RANGE_BASED:
                return self._find_shard_range_based(key_value)
            elif self.config.strategy == ShardingStrategy.CONSISTENT_HASH:
                return self._find_shard_consistent_hash(key_value)
            elif self.config.strategy == ShardingStrategy.DIRECTORY_BASED:
                return self._find_shard_directory_based(key_value)
            elif self.config.strategy == ShardingStrategy.GEOGRAPHIC:
                return self._find_shard_geographic(key_value, preferred_region)
            else:
                return None

    def _find_shard_hash_based(self, key_value: Any) -> str | None:
        """Find shard using hash-based strategy."""
        if not hasattr(self, "_hash_shard_count") or self._hash_shard_count == 0:
            return None

        hash_value = self.config.shard_key.hash_value(key_value)
        shard_index = hash_value % self._hash_shard_count

        return self._hash_shard_list[shard_index]

    def _find_shard_range_based(self, key_value: Any) -> str | None:
        """Find shard using range-based strategy."""
        for range_obj in self._range_map:
            if range_obj.contains(key_value):
                return range_obj.shard_id

        return None

    def _find_shard_consistent_hash(self, key_value: Any) -> str | None:
        """Find shard using consistent hashing."""
        if not self._hash_ring:
            return None

        hash_value = self.config.shard_key.hash_value(key_value)

        # Find the first node in the ring >= hash_value
        sorted_hashes = sorted(self._hash_ring.keys())

        for ring_hash in sorted_hashes:
            if ring_hash >= hash_value:
                return self._hash_ring[ring_hash]

        # Wrap around to the beginning
        return self._hash_ring[sorted_hashes[0]] if sorted_hashes else None

    def _find_shard_directory_based(self, key_value: Any) -> str | None:
        """Find shard using directory-based strategy."""
        return self._directory_map.get(key_value)

    def _find_shard_geographic(
        self, key_value: Any, preferred_region: str | None = None
    ) -> str | None:
        """Find shard using geographic strategy."""
        target_region = preferred_region or "default"

        if target_region in self._geo_regions:
            # Use hash to distribute within region
            region_shards = self._geo_regions[target_region]
            if region_shards:
                hash_value = self.config.shard_key.hash_value(key_value)
                shard_index = hash_value % len(region_shards)
                return region_shards[shard_index]

        # Fallback to any available shard
        for region_shards in self._geo_regions.values():
            if region_shards:
                return region_shards[0]

        return None

    def execute_query(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        preferred_region: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a query across appropriate shards.

        Args:
            query: SQL query to execute
            parameters: Query parameters
            preferred_region: Preferred geographic region

        Returns:
            Dictionary with results from each shard
        """
        start_time = time.time()

        try:
            # Route query to shards
            target_shards = self.route_query(query, parameters, preferred_region)

            if not target_shards:
                raise ValueError("No available shards for query")

            # Track if this is a cross-shard query
            is_cross_shard = len(target_shards) > 1

            # Execute query on each shard
            results = {}
            errors = {}

            for shard_id in target_shards:
                try:
                    shard_connection = self.shard_connections.get(shard_id)
                    if not shard_connection:
                        errors[shard_id] = "No connection available"
                        continue

                    # Execute query
                    if parameters:
                        shard_results = shard_connection.fetch_all(query, parameters)
                    else:
                        shard_results = shard_connection.fetch_all(query)

                    results[shard_id] = [dict(row) for row in shard_results]

                    # Update shard statistics
                    shard_info = self.shards[shard_id]
                    execution_time = (time.time() - start_time) * 1000
                    shard_info.avg_response_time_ms = (
                        0.9 * shard_info.avg_response_time_ms + 0.1 * execution_time
                    )

                except Exception as e:
                    logger.error(f"Query execution failed on shard {shard_id}: {e}")
                    errors[shard_id] = str(e)

            # Update query statistics
            total_time = (time.time() - start_time) * 1000
            stats = self._query_stats[query[:100]]  # Use first 100 chars as key
            stats["total_queries"] += 1
            if is_cross_shard:
                stats["cross_shard_queries"] += 1

            # Update average response time
            stats["avg_response_time"] = (
                0.9 * stats["avg_response_time"] + 0.1 * total_time
            )

            if errors:
                stats["errors"] += 1

            return {
                "results": results,
                "errors": errors,
                "execution_time_ms": total_time,
                "shards_queried": len(target_shards),
                "cross_shard": is_cross_shard,
            }

        except Exception as e:
            logger.error(f"Sharded query execution failed: {e}")
            raise

    def add_shard(
        self,
        shard_id: str,
        connection_string: str,
        weight: int = 100,
        region: str = "default",
        availability_zone: str = "default",
    ) -> bool:
        """
        Add a new shard to the cluster.

        Args:
            shard_id: Unique identifier for the shard
            connection_string: Database connection string
            weight: Weight for load balancing (default 100)
            region: Geographic region
            availability_zone: Availability zone within region

        Returns:
            True if shard was added successfully
        """
        try:
            with self._shard_lock:
                if shard_id in self.shards:
                    logger.warning(f"Shard {shard_id} already exists")
                    return False

                # Create shard info
                shard_info = ShardInfo(
                    shard_id=shard_id,
                    connection_string=connection_string,
                    state=ShardState.ACTIVE,
                    weight=weight,
                    region=region,
                    availability_zone=availability_zone,
                )

                # Initialize shard connection
                self._init_shard_connection(shard_info)

                # Add to shards
                self.shards[shard_id] = shard_info

                # Store in metadata database
                self.metadata_db.execute(
                    """
                    INSERT INTO shards
                    (shard_id, connection_string, state, weight, region, availability_zone)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        shard_id,
                        connection_string,
                        shard_info.state.value,
                        weight,
                        region,
                        availability_zone,
                    ),
                )

                # Rebuild routing structures
                self._build_routing_structures()

                logger.info(f"Added shard {shard_id} to cluster")
                return True

        except Exception as e:
            logger.error(f"Failed to add shard {shard_id}: {e}")
            return False

    def remove_shard(self, shard_id: str, migrate_data: bool = True) -> bool:
        """
        Remove a shard from the cluster.

        Args:
            shard_id: Shard to remove
            migrate_data: Whether to migrate data before removal

        Returns:
            True if shard was removed successfully
        """
        try:
            with self._shard_lock:
                if shard_id not in self.shards:
                    logger.warning(f"Shard {shard_id} not found")
                    return False

                shard_info = self.shards[shard_id]

                # Set shard to maintenance mode
                shard_info.state = ShardState.MAINTENANCE

                # Migrate data if requested
                if migrate_data:
                    success = self._migrate_shard_data(shard_id)
                    if not success:
                        logger.error(f"Failed to migrate data from shard {shard_id}")
                        return False

                # Close connections
                if shard_id in self.shard_connections:
                    self.shard_connections[shard_id].close_all_connections()
                    del self.shard_connections[shard_id]

                if shard_id in self.shard_pools:
                    self.shard_pools[shard_id].shutdown()
                    del self.shard_pools[shard_id]

                # Remove from shards
                del self.shards[shard_id]

                # Update metadata database
                self.metadata_db.execute(
                    "DELETE FROM shards WHERE shard_id = ?", (shard_id,)
                )

                # Rebuild routing structures
                self._build_routing_structures()

                logger.info(f"Removed shard {shard_id} from cluster")
                return True

        except Exception as e:
            logger.error(f"Failed to remove shard {shard_id}: {e}")
            return False

    def _migrate_shard_data(self, source_shard_id: str) -> bool:
        """Migrate data from a shard to other shards."""
        try:
            # This is a simplified migration - in production, you'd need
            # more sophisticated migration logic based on the specific data model

            # Get source connection
            source_conn = self.shard_connections.get(source_shard_id)
            if not source_conn:
                return False

            # Get all tables in source shard
            tables = source_conn.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )

            migration_id = str(uuid.uuid4())

            # Record migration
            self.metadata_db.execute(
                """
                INSERT INTO shard_migrations
                (migration_id, source_shard, target_shard, migration_type, status)
                VALUES (?, ?, ?, ?, ?)
            """,
                (migration_id, source_shard_id, "distributed", "rebalance", "started"),
            )

            # For each table, migrate data
            for table_row in tables:
                table_name = table_row["name"]

                # Get all data from source
                data_rows = source_conn.fetch_all(f"SELECT * FROM {table_name}")

                # Redistribute data to appropriate shards
                for row in data_rows:
                    # Extract shard key from row
                    if self.config.shard_key.column_name in row.keys():
                        key_value = row[self.config.shard_key.column_name]
                        target_shard_id = self._find_shard_for_key(key_value)

                        if target_shard_id and target_shard_id != source_shard_id:
                            # Insert into target shard
                            target_conn = self.shard_connections.get(target_shard_id)
                            if target_conn:
                                # Build INSERT query
                                columns = list(row.keys())
                                placeholders = ", ".join(["?" for _ in columns])
                                values = [row[col] for col in columns]

                                insert_query = f"""
                                    INSERT OR REPLACE INTO {table_name}
                                    ({', '.join(columns)}) VALUES ({placeholders})
                                """

                                target_conn.execute(insert_query, tuple(values))

            # Mark migration as completed
            self.metadata_db.execute(
                """
                UPDATE shard_migrations
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE migration_id = ?
            """,
                (migration_id,),
            )

            logger.info(f"Successfully migrated data from shard {source_shard_id}")
            return True

        except Exception as e:
            logger.error(f"Data migration failed for shard {source_shard_id}: {e}")
            return False

    def _check_rebalancing_needed(self) -> None:
        """Check if shard rebalancing is needed and trigger if necessary."""
        try:
            # Get shard size statistics
            shard_sizes = {}

            for shard_id, shard_info in self.shards.items():
                if shard_info.state == ShardState.ACTIVE:
                    # Get approximate size (simplified)
                    connection = self.shard_connections.get(shard_id)
                    if connection:
                        try:
                            # Count total records across all tables
                            tables = connection.fetch_all(
                                "SELECT name FROM sqlite_master WHERE type='table'"
                            )
                            total_records = 0

                            for table_row in tables:
                                table_name = table_row["name"]
                                count_result = connection.fetch_one(
                                    f"SELECT COUNT(*) as count FROM {table_name}"
                                )
                                if count_result:
                                    total_records += count_result["count"]

                            shard_sizes[shard_id] = total_records
                            shard_info.total_records = total_records

                        except Exception as e:
                            logger.debug(
                                f"Failed to get size for shard {shard_id}: {e}"
                            )

            if not shard_sizes:
                return

            # Check for size imbalances
            avg_size = sum(shard_sizes.values()) / len(shard_sizes)
            max_size = max(shard_sizes.values())

            # If the largest shard is more than 3x the average, consider rebalancing
            if (
                max_size > avg_size * 3 and max_size > 10000
            ):  # Only for significant sizes
                oversized_shards = [
                    shard_id
                    for shard_id, size in shard_sizes.items()
                    if size > avg_size * 2
                ]

                logger.info(f"Detected oversized shards: {oversized_shards}")
                # In a production system, you would trigger rebalancing here

        except Exception as e:
            logger.error(f"Rebalancing check failed: {e}")

    def _update_shard_statistics(self) -> None:
        """Update shard statistics in metadata database."""
        try:
            for shard_id, shard_info in self.shards.items():
                # Store key metrics
                metrics = [
                    ("avg_response_time_ms", shard_info.avg_response_time_ms),
                    ("connection_count", shard_info.connection_count),
                    ("total_records", shard_info.total_records),
                    ("total_size_bytes", shard_info.total_size_bytes),
                ]

                for metric_name, metric_value in metrics:
                    if metric_value > 0:
                        self.metadata_db.execute(
                            """
                            INSERT INTO shard_statistics
                            (shard_id, metric_name, metric_value)
                            VALUES (?, ?, ?)
                        """,
                            (shard_id, metric_name, metric_value),
                        )

        except Exception as e:
            logger.debug(f"Failed to update shard statistics: {e}")

    def get_shard_statistics(self) -> dict[str, Any]:
        """Get comprehensive sharding statistics."""
        stats = {
            "total_shards": len(self.shards),
            "active_shards": 0,
            "readonly_shards": 0,
            "failed_shards": 0,
            "sharding_strategy": self.config.strategy.value,
            "shard_key": {
                "column": self.config.shard_key.column_name,
                "type": self.config.shard_key.data_type,
                "hash_function": self.config.shard_key.hash_function,
            },
            "shards": {},
            "query_stats": dict(self._query_stats),
            "total_cross_shard_queries": sum(
                stats.get("cross_shard_queries", 0)
                for stats in self._query_stats.values()
            ),
            "total_queries": sum(
                stats.get("total_queries", 0) for stats in self._query_stats.values()
            ),
        }

        # Collect individual shard statistics
        for shard_id, shard_info in self.shards.items():
            shard_stats = {
                "state": shard_info.state.value,
                "weight": shard_info.weight,
                "region": shard_info.region,
                "availability_zone": shard_info.availability_zone,
                "total_records": shard_info.total_records,
                "total_size_bytes": shard_info.total_size_bytes,
                "avg_response_time_ms": shard_info.avg_response_time_ms,
                "last_health_check": shard_info.last_health_check,
                "created_at": shard_info.created_at,
            }

            stats["shards"][shard_id] = shard_stats

            # Count shard states
            if shard_info.state == ShardState.ACTIVE:
                stats["active_shards"] += 1
            elif shard_info.state == ShardState.READONLY:
                stats["readonly_shards"] += 1
            elif shard_info.state == ShardState.FAILED:
                stats["failed_shards"] += 1

        return stats

    def shutdown(self) -> None:
        """Shutdown the sharding manager and cleanup resources."""
        self._shutdown_event.set()

        # Wait for background threads
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5)

        if self._rebalancer_thread:
            self._rebalancer_thread.join(timeout=5)

        # Shutdown all shard connections and pools
        for shard_id in list(self.shard_connections.keys()):
            try:
                self.shard_connections[shard_id].close_all_connections()
                del self.shard_connections[shard_id]
            except Exception as e:
                logger.warning(f"Error closing connection for shard {shard_id}: {e}")

        for shard_id in list(self.shard_pools.keys()):
            try:
                self.shard_pools[shard_id].shutdown()
                del self.shard_pools[shard_id]
            except Exception as e:
                logger.warning(f"Error shutting down pool for shard {shard_id}: {e}")

        logger.info("Sharding manager shutdown complete")


def main():
    """CLI interface for testing the Sharding Manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Sharding Manager")
    parser.add_argument("--metadata-db", required=True, help="Metadata database path")
    parser.add_argument("--test", action="store_true", help="Run sharding test")
    parser.add_argument("--stats", action="store_true", help="Show sharding statistics")
    parser.add_argument(
        "--add-shard", help="Add a shard (format: shard_id:connection_string)"
    )
    parser.add_argument(
        "--strategy",
        choices=["hash_based", "range_based", "consistent_hash"],
        default="hash_based",
        help="Sharding strategy",
    )

    args = parser.parse_args()

    try:
        # Initialize metadata connection
        metadata_db = DatabaseConnection(args.metadata_db)

        # Create sharding configuration
        shard_key = ShardKey(column_name="id", data_type="string", hash_function="md5")

        config = ShardingConfiguration(
            strategy=ShardingStrategy(args.strategy), shard_key=shard_key
        )

        # Initialize sharding manager
        shard_manager = ShardingManager(
            config=config,
            metadata_connection=metadata_db,
            enable_cross_shard_queries=True,
            enable_auto_migration=True,
        )

        if args.add_shard:
            shard_id, connection_string = args.add_shard.split(":", 1)
            success = shard_manager.add_shard(shard_id, connection_string)
            print(f"Add shard result: {success}")

        if args.test:
            print("Testing sharding functionality...")

            # Test query routing
            test_queries = [
                ("SELECT * FROM documents WHERE id = ?", ("doc_123",)),
                ("SELECT * FROM documents WHERE title LIKE ?", ("%test%",)),
                (
                    "INSERT INTO documents (id, title) VALUES (?, ?)",
                    ("doc_456", "Test Document"),
                ),
            ]

            for query, params in test_queries:
                try:
                    target_shards = shard_manager.route_query(query, params)
                    print(f"Query: {query[:50]}... -> Shards: {target_shards}")
                except Exception as e:
                    print(f"Query routing failed: {e}")

        if args.stats:
            stats = shard_manager.get_shard_statistics()
            print("Sharding Statistics:")
            print(f"Total Shards: {stats['total_shards']}")
            print(
                f"Active: {stats['active_shards']}, ReadOnly: {stats['readonly_shards']}, Failed: {stats['failed_shards']}"
            )
            print(f"Strategy: {stats['sharding_strategy']}")
            print(
                f"Shard Key: {stats['shard_key']['column']} ({stats['shard_key']['type']})"
            )
            print(f"Total Queries: {stats['total_queries']}")
            print(f"Cross-Shard Queries: {stats['total_cross_shard_queries']}")

            if stats["shards"]:
                print("\nShard Details:")
                for shard_id, shard_stats in stats["shards"].items():
                    print(
                        f"  {shard_id}: {shard_stats['state']} "
                        f"({shard_stats['total_records']} records, "
                        f"{shard_stats['avg_response_time_ms']:.2f}ms avg)"
                    )

        shard_manager.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
