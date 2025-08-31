"""
Advanced Connection Pool Manager for AI Enhanced PDF Scholar
High-performance database connection pooling with intelligent load balancing,
health monitoring, and automatic scaling.
"""

import logging
import queue
import sqlite3
import statistics
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import DatabaseConnection: {e}")
    sys.exit(1)


class PoolStrategy(Enum):
    """Connection pool strategies."""
    FIXED = "fixed"           # Fixed pool size
    DYNAMIC = "dynamic"       # Dynamic sizing based on load
    ADAPTIVE = "adaptive"     # AI-driven adaptive sizing


class ConnectionState(Enum):
    """Connection states."""
    IDLE = "idle"
    ACTIVE = "active"
    STALE = "stale"
    INVALID = "invalid"


@dataclass
class ConnectionMetrics:
    """Metrics for a single connection."""
    connection_id: str
    created_at: float
    last_used: float
    total_queries: int
    total_time_ms: float
    avg_query_time_ms: float
    state: ConnectionState
    thread_id: int | None = None
    errors: int = 0

    def update_usage(self, execution_time_ms: float) -> None:
        """Update connection usage metrics."""
        self.last_used = time.time()
        self.total_queries += 1
        self.total_time_ms += execution_time_ms
        self.avg_query_time_ms = self.total_time_ms / self.total_queries


@dataclass
class PoolStatistics:
    """Connection pool statistics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    stale_connections: int = 0
    invalid_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_wait_time_ms: float = 0.0
    avg_response_time_ms: float = 0.0
    peak_connections: int = 0
    pool_efficiency: float = 0.0
    connection_churn_rate: float = 0.0


@dataclass
class PoolConfiguration:
    """Connection pool configuration."""
    min_connections: int = 5
    max_connections: int = 50
    initial_connections: int = 10
    connection_timeout_ms: int = 30000
    idle_timeout_ms: int = 300000  # 5 minutes
    stale_timeout_ms: int = 3600000  # 1 hour
    health_check_interval_s: int = 60
    pool_strategy: PoolStrategy = PoolStrategy.DYNAMIC
    enable_load_balancing: bool = True
    enable_connection_warming: bool = True
    max_connection_age_ms: int = 7200000  # 2 hours


class ManagedConnection:
    """Wrapper for database connections with metrics and lifecycle management."""

    def __init__(self, connection: sqlite3.Connection, pool_manager: 'AdvancedConnectionPoolManager'):
        self.connection = connection
        self.pool_manager = pool_manager
        self.metrics = ConnectionMetrics(
            connection_id=f"conn_{id(connection)}",
            created_at=time.time(),
            last_used=time.time(),
            total_queries=0,
            total_time_ms=0.0,
            avg_query_time_ms=0.0,
            state=ConnectionState.IDLE
        )
        self._lock = threading.Lock()
        self._in_use = False

    def acquire(self, thread_id: int) -> sqlite3.Connection:
        """Acquire the connection for use."""
        with self._lock:
            if self._in_use:
                raise RuntimeError("Connection already in use")

            self._in_use = True
            self.metrics.thread_id = thread_id
            self.metrics.state = ConnectionState.ACTIVE
            self.metrics.last_used = time.time()

            return self.connection

    def release(self) -> None:
        """Release the connection back to the pool."""
        with self._lock:
            self._in_use = False
            self.metrics.thread_id = None
            self.metrics.state = ConnectionState.IDLE

    def record_query(self, execution_time_ms: float, success: bool = True) -> None:
        """Record query execution metrics."""
        with self._lock:
            self.metrics.update_usage(execution_time_ms)
            if not success:
                self.metrics.errors += 1

    def is_stale(self, stale_timeout_ms: int) -> bool:
        """Check if connection is stale."""
        return (time.time() - self.metrics.last_used) * 1000 > stale_timeout_ms

    def is_expired(self, max_age_ms: int) -> bool:
        """Check if connection has exceeded maximum age."""
        return (time.time() - self.metrics.created_at) * 1000 > max_age_ms

    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        try:
            cursor = self.connection.execute("SELECT 1")
            cursor.fetchone()
            return True
        except:
            return False


class AdvancedConnectionPoolManager:
    """
    Advanced Connection Pool Manager

    Features:
    - Multiple pooling strategies (fixed, dynamic, adaptive)
    - Intelligent load balancing
    - Health monitoring and auto-recovery
    - Connection lifecycle management
    - Performance metrics and optimization
    - Thread-safe operations
    """

    def __init__(
        self,
        database_url: str,
        config: PoolConfiguration | None = None
    ):
        """
        Initialize the Advanced Connection Pool Manager.

        Args:
            database_url: Database connection URL
            config: Pool configuration (uses defaults if None)
        """
        self.database_url = database_url
        self.config = config or PoolConfiguration()

        # Connection pools by priority/type
        self._idle_connections: queue.Queue[ManagedConnection] = queue.Queue()
        self._active_connections: dict[str, ManagedConnection] = {}
        self._all_connections: dict[str, ManagedConnection] = {}

        # Thread safety
        self._pool_lock = threading.RLock()
        self._stats_lock = threading.Lock()

        # Statistics and monitoring
        self._stats = PoolStatistics()
        self._wait_times: list[float] = []
        self._response_times: list[float] = []

        # Background tasks
        self._health_monitor_thread: threading.Thread | None = None
        self._pool_optimizer_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Initialize pool
        self._initialize_pool()
        self._start_background_tasks()

    def _initialize_pool(self) -> None:
        """Initialize the connection pool with initial connections."""
        try:
            logger.info(f"Initializing connection pool with {self.config.initial_connections} connections")

            for i in range(self.config.initial_connections):
                connection = self._create_new_connection()
                managed_conn = ManagedConnection(connection, self)

                with self._pool_lock:
                    self._all_connections[managed_conn.metrics.connection_id] = managed_conn
                    self._idle_connections.put(managed_conn)
                    self._stats.total_connections += 1

            logger.info(f"Connection pool initialized with {self._stats.total_connections} connections")

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    def _create_new_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        try:
            # Handle different database URL formats
            if self.database_url.startswith('sqlite://'):
                db_path = self.database_url.replace('sqlite://', '')
            else:
                db_path = self.database_url

            connection = sqlite3.connect(
                db_path,
                check_same_thread=False,
                timeout=self.config.connection_timeout_ms / 1000,
                isolation_level=None  # Autocommit mode
            )

            # Configure connection for performance
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA cache_size = -64000")  # 64MB cache
            connection.execute("PRAGMA temp_store = MEMORY")
            connection.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap

            return connection

        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise

    def _start_background_tasks(self) -> None:
        """Start background monitoring and optimization tasks."""
        # Health monitoring thread
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_worker,
            daemon=True,
            name="PoolHealthMonitor"
        )
        self._health_monitor_thread.start()

        # Pool optimization thread
        self._pool_optimizer_thread = threading.Thread(
            target=self._pool_optimizer_worker,
            daemon=True,
            name="PoolOptimizer"
        )
        self._pool_optimizer_thread.start()

        logger.info("Connection pool background tasks started")

    def _health_monitor_worker(self) -> None:
        """Background worker for connection health monitoring."""
        while not self._shutdown_event.wait(self.config.health_check_interval_s):
            try:
                self._check_connection_health()
                self._cleanup_stale_connections()
                self._update_pool_statistics()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _pool_optimizer_worker(self) -> None:
        """Background worker for pool optimization."""
        while not self._shutdown_event.wait(60):  # Run every minute
            try:
                if self.config.pool_strategy == PoolStrategy.DYNAMIC:
                    self._optimize_pool_size_dynamic()
                elif self.config.pool_strategy == PoolStrategy.ADAPTIVE:
                    self._optimize_pool_size_adaptive()

                self._balance_connection_load()
            except Exception as e:
                logger.error(f"Pool optimizer error: {e}")

    def _check_connection_health(self) -> None:
        """Check health of all connections and remove invalid ones."""
        invalid_connections = []

        with self._pool_lock:
            for conn_id, managed_conn in self._all_connections.items():
                if not managed_conn.is_healthy():
                    invalid_connections.append(conn_id)
                    managed_conn.metrics.state = ConnectionState.INVALID

        # Remove invalid connections
        for conn_id in invalid_connections:
            self._remove_connection(conn_id)
            logger.warning(f"Removed invalid connection: {conn_id}")

    def _cleanup_stale_connections(self) -> None:
        """Remove stale and expired connections."""
        stale_connections = []

        with self._pool_lock:
            for conn_id, managed_conn in self._all_connections.items():
                if (managed_conn.metrics.state == ConnectionState.IDLE and
                    (managed_conn.is_stale(self.config.stale_timeout_ms) or
                     managed_conn.is_expired(self.config.max_connection_age_ms))):
                    stale_connections.append(conn_id)
                    managed_conn.metrics.state = ConnectionState.STALE

        # Remove stale connections (but keep minimum pool size)
        current_size = len(self._all_connections)

        for conn_id in stale_connections:
            if current_size > self.config.min_connections:
                self._remove_connection(conn_id)
                current_size -= 1
                logger.debug(f"Removed stale connection: {conn_id}")

    def _remove_connection(self, conn_id: str) -> None:
        """Remove a connection from the pool."""
        with self._pool_lock:
            managed_conn = self._all_connections.pop(conn_id, None)
            if managed_conn:
                # Remove from active connections if present
                self._active_connections.pop(conn_id, None)

                # Remove from idle queue (if present)
                try:
                    # Create new queue without the connection
                    new_idle_queue = queue.Queue()
                    while True:
                        try:
                            conn = self._idle_connections.get_nowait()
                            if conn.metrics.connection_id != conn_id:
                                new_idle_queue.put(conn)
                        except queue.Empty:
                            break
                    self._idle_connections = new_idle_queue
                except:
                    pass

                # Close the actual connection
                try:
                    managed_conn.connection.close()
                except:
                    pass

                self._stats.total_connections -= 1

    def _optimize_pool_size_dynamic(self) -> None:
        """Optimize pool size based on current load (dynamic strategy)."""
        with self._pool_lock:
            active_count = len(self._active_connections)
            idle_count = self._idle_connections.qsize()
            total_count = len(self._all_connections)

            # Calculate utilization
            utilization = active_count / max(total_count, 1)

            # Scale up if high utilization
            if utilization > 0.8 and total_count < self.config.max_connections:
                connections_to_add = min(5, self.config.max_connections - total_count)
                for _ in range(connections_to_add):
                    try:
                        connection = self._create_new_connection()
                        managed_conn = ManagedConnection(connection, self)
                        self._all_connections[managed_conn.metrics.connection_id] = managed_conn
                        self._idle_connections.put(managed_conn)
                        self._stats.total_connections += 1
                    except Exception as e:
                        logger.error(f"Failed to create new connection during scaling: {e}")
                        break

                logger.info(f"Scaled up pool by {connections_to_add} connections (utilization: {utilization:.2f})")

            # Scale down if low utilization
            elif utilization < 0.3 and total_count > self.config.min_connections:
                excess_connections = min(
                    idle_count // 2,
                    total_count - self.config.min_connections
                )

                for _ in range(excess_connections):
                    try:
                        if not self._idle_connections.empty():
                            managed_conn = self._idle_connections.get_nowait()
                            self._remove_connection(managed_conn.metrics.connection_id)
                    except queue.Empty:
                        break

                if excess_connections > 0:
                    logger.info(f"Scaled down pool by {excess_connections} connections (utilization: {utilization:.2f})")

    def _optimize_pool_size_adaptive(self) -> None:
        """Optimize pool size using adaptive AI-driven strategy."""
        # This is a simplified adaptive algorithm
        # In production, you might use more sophisticated ML techniques

        with self._stats_lock:
            recent_wait_times = self._wait_times[-100:] if self._wait_times else [0]
            recent_response_times = self._response_times[-100:] if self._response_times else [0]

            avg_wait_time = statistics.mean(recent_wait_times)
            avg_response_time = statistics.mean(recent_response_times)

        # Decision matrix based on performance metrics
        if avg_wait_time > 100:  # High wait times
            self._scale_up_adaptive(reason="high_wait_times")
        elif avg_response_time > 500:  # Slow responses
            self._scale_up_adaptive(reason="slow_responses")
        elif avg_wait_time < 10 and avg_response_time < 100:  # Low load
            self._scale_down_adaptive(reason="low_load")

    def _scale_up_adaptive(self, reason: str) -> None:
        """Scale up connections based on adaptive algorithm."""
        with self._pool_lock:
            current_size = len(self._all_connections)
            if current_size < self.config.max_connections:
                # Adaptive scaling: scale more aggressively under high load
                scale_factor = 0.2 if reason == "high_wait_times" else 0.1
                connections_to_add = max(1, int(current_size * scale_factor))
                connections_to_add = min(connections_to_add, self.config.max_connections - current_size)

                for _ in range(connections_to_add):
                    try:
                        connection = self._create_new_connection()
                        managed_conn = ManagedConnection(connection, self)
                        self._all_connections[managed_conn.metrics.connection_id] = managed_conn
                        self._idle_connections.put(managed_conn)
                        self._stats.total_connections += 1
                    except Exception as e:
                        logger.error(f"Failed to create connection during adaptive scaling: {e}")
                        break

                logger.info(f"Adaptive scale-up: +{connections_to_add} connections (reason: {reason})")

    def _scale_down_adaptive(self, reason: str) -> None:
        """Scale down connections based on adaptive algorithm."""
        with self._pool_lock:
            current_size = len(self._all_connections)
            idle_count = self._idle_connections.qsize()

            if current_size > self.config.min_connections and idle_count > 2:
                # Conservative scaling down
                connections_to_remove = min(idle_count // 3, current_size - self.config.min_connections)

                for _ in range(connections_to_remove):
                    try:
                        if not self._idle_connections.empty():
                            managed_conn = self._idle_connections.get_nowait()
                            self._remove_connection(managed_conn.metrics.connection_id)
                    except queue.Empty:
                        break

                if connections_to_remove > 0:
                    logger.info(f"Adaptive scale-down: -{connections_to_remove} connections (reason: {reason})")

    def _balance_connection_load(self) -> None:
        """Balance load across connections if load balancing is enabled."""
        if not self.config.enable_load_balancing:
            return

        # This is a simplified load balancing implementation
        # In practice, you might implement more sophisticated algorithms

        with self._pool_lock:
            # Find connections with very different usage patterns
            connection_loads = []
            for managed_conn in self._all_connections.values():
                if managed_conn.metrics.state == ConnectionState.IDLE:
                    load_score = managed_conn.metrics.total_queries * managed_conn.metrics.avg_query_time_ms
                    connection_loads.append((managed_conn, load_score))

            # Sort by load (highest first)
            connection_loads.sort(key=lambda x: x[1], reverse=True)

            # If we have significant load imbalance, we could implement
            # connection rotation or other load balancing strategies here
            if len(connection_loads) > 1:
                highest_load = connection_loads[0][1]
                lowest_load = connection_loads[-1][1]

                if highest_load > 0 and highest_load / max(lowest_load, 1) > 3:
                    logger.debug("Detected connection load imbalance - considering rebalancing")

    def acquire_connection(self, timeout_ms: int | None = None) -> ManagedConnection:
        """
        Acquire a connection from the pool.

        Args:
            timeout_ms: Maximum time to wait for a connection

        Returns:
            ManagedConnection instance

        Raises:
            TimeoutError: If no connection is available within timeout
        """
        start_time = time.time()
        timeout_s = (timeout_ms or self.config.connection_timeout_ms) / 1000
        thread_id = threading.get_ident()

        try:
            with self._stats_lock:
                self._stats.total_requests += 1

            # Try to get an idle connection
            try:
                managed_conn = self._idle_connections.get(timeout=timeout_s)

                # Verify connection is still healthy
                if not managed_conn.is_healthy():
                    self._remove_connection(managed_conn.metrics.connection_id)
                    # Recursively try again
                    return self.acquire_connection(timeout_ms)

                # Acquire the connection
                connection = managed_conn.acquire(thread_id)

                with self._pool_lock:
                    self._active_connections[managed_conn.metrics.connection_id] = managed_conn

                # Record wait time
                wait_time = (time.time() - start_time) * 1000
                with self._stats_lock:
                    self._wait_times.append(wait_time)
                    if len(self._wait_times) > 1000:  # Keep only recent 1000 measurements
                        self._wait_times = self._wait_times[-500:]

                    self._stats.successful_requests += 1
                    self._stats.active_connections += 1
                    self._stats.idle_connections -= 1

                logger.debug(f"Acquired connection {managed_conn.metrics.connection_id} (wait: {wait_time:.2f}ms)")
                return managed_conn

            except queue.Empty as e:
                # No idle connections available
                with self._pool_lock:
                    current_size = len(self._all_connections)

                    # Try to create a new connection if under limit
                    if current_size < self.config.max_connections:
                        try:
                            connection = self._create_new_connection()
                            managed_conn = ManagedConnection(connection, self)

                            self._all_connections[managed_conn.metrics.connection_id] = managed_conn
                            self._stats.total_connections += 1

                            # Acquire immediately
                            _ = managed_conn.acquire(thread_id)
                            self._active_connections[managed_conn.metrics.connection_id] = managed_conn

                            with self._stats_lock:
                                self._stats.successful_requests += 1
                                self._stats.active_connections += 1

                            logger.debug(f"Created and acquired new connection {managed_conn.metrics.connection_id}")
                            return managed_conn

                        except Exception as create_err:
                            logger.error(f"Failed to create new connection: {create_err}")

                # Pool is exhausted
                with self._stats_lock:
                    self._stats.failed_requests += 1

                raise TimeoutError(f"No database connections available within {timeout_ms}ms timeout") from e

        except Exception as e:
            with self._stats_lock:
                self._stats.failed_requests += 1
            logger.error(f"Failed to acquire connection: {e}")
            raise

    def release_connection(self, managed_conn: ManagedConnection, execution_time_ms: float = 0, success: bool = True) -> None:
        """
        Release a connection back to the pool.

        Args:
            managed_conn: The managed connection to release
            execution_time_ms: Execution time of the last operation
            success: Whether the last operation was successful
        """
        try:
            # Record metrics
            if execution_time_ms > 0:
                managed_conn.record_query(execution_time_ms, success)

                with self._stats_lock:
                    self._response_times.append(execution_time_ms)
                    if len(self._response_times) > 1000:  # Keep only recent 1000 measurements
                        self._response_times = self._response_times[-500:]

            # Release the connection
            managed_conn.release()

            with self._pool_lock:
                # Remove from active connections
                self._active_connections.pop(managed_conn.metrics.connection_id, None)

                # Return to idle pool if connection is still healthy
                if managed_conn.is_healthy() and managed_conn.metrics.state != ConnectionState.INVALID:
                    self._idle_connections.put(managed_conn)

                    with self._stats_lock:
                        self._stats.active_connections -= 1
                        self._stats.idle_connections += 1
                else:
                    # Remove unhealthy connection
                    self._remove_connection(managed_conn.metrics.connection_id)

            logger.debug(f"Released connection {managed_conn.metrics.connection_id}")

        except Exception as e:
            logger.error(f"Failed to release connection: {e}")

    def _update_pool_statistics(self) -> None:
        """Update pool statistics."""
        with self._pool_lock:
            active_count = len(self._active_connections)
            idle_count = self._idle_connections.qsize()
            total_count = len(self._all_connections)

            with self._stats_lock:
                self._stats.total_connections = total_count
                self._stats.active_connections = active_count
                self._stats.idle_connections = idle_count

                # Update peak connections
                if active_count > self._stats.peak_connections:
                    self._stats.peak_connections = active_count

                # Calculate efficiency
                if self._stats.total_requests > 0:
                    self._stats.pool_efficiency = (
                        self._stats.successful_requests / self._stats.total_requests * 100
                    )

                # Calculate average times
                if self._wait_times:
                    self._stats.avg_wait_time_ms = statistics.mean(self._wait_times[-100:])

                if self._response_times:
                    self._stats.avg_response_time_ms = statistics.mean(self._response_times[-100:])

    def get_statistics(self) -> PoolStatistics:
        """Get current pool statistics."""
        self._update_pool_statistics()

        with self._stats_lock:
            return PoolStatistics(
                total_connections=self._stats.total_connections,
                active_connections=self._stats.active_connections,
                idle_connections=self._stats.idle_connections,
                stale_connections=self._stats.stale_connections,
                invalid_connections=self._stats.invalid_connections,
                total_requests=self._stats.total_requests,
                successful_requests=self._stats.successful_requests,
                failed_requests=self._stats.failed_requests,
                avg_wait_time_ms=self._stats.avg_wait_time_ms,
                avg_response_time_ms=self._stats.avg_response_time_ms,
                peak_connections=self._stats.peak_connections,
                pool_efficiency=self._stats.pool_efficiency,
                connection_churn_rate=self._stats.connection_churn_rate
            )

    def get_connection_details(self) -> list[dict[str, Any]]:
        """Get detailed information about all connections."""
        connection_details = []

        with self._pool_lock:
            for managed_conn in self._all_connections.values():
                details = {
                    'connection_id': managed_conn.metrics.connection_id,
                    'state': managed_conn.metrics.state.value,
                    'created_at': managed_conn.metrics.created_at,
                    'last_used': managed_conn.metrics.last_used,
                    'total_queries': managed_conn.metrics.total_queries,
                    'avg_query_time_ms': managed_conn.metrics.avg_query_time_ms,
                    'errors': managed_conn.metrics.errors,
                    'thread_id': managed_conn.metrics.thread_id,
                    'age_seconds': time.time() - managed_conn.metrics.created_at,
                    'idle_time_seconds': time.time() - managed_conn.metrics.last_used
                }
                connection_details.append(details)

        return connection_details

    def warm_pool(self, target_size: int | None = None) -> int:
        """
        Warm the connection pool by creating connections up to target size.

        Args:
            target_size: Target number of connections (uses initial_connections if None)

        Returns:
            Number of connections created
        """
        if not self.config.enable_connection_warming:
            return 0

        target = target_size or self.config.initial_connections
        connections_created = 0

        with self._pool_lock:
            current_size = len(self._all_connections)
            connections_needed = min(target - current_size, self.config.max_connections - current_size)

            for _ in range(connections_needed):
                try:
                    connection = self._create_new_connection()
                    managed_conn = ManagedConnection(connection, self)

                    self._all_connections[managed_conn.metrics.connection_id] = managed_conn
                    self._idle_connections.put(managed_conn)
                    self._stats.total_connections += 1
                    connections_created += 1

                except Exception as e:
                    logger.error(f"Failed to create connection during warming: {e}")
                    break

        if connections_created > 0:
            logger.info(f"Warmed connection pool with {connections_created} connections")

        return connections_created

    def shutdown(self) -> None:
        """Shutdown the connection pool and cleanup all resources."""
        self._shutdown_event.set()

        # Wait for background threads to finish
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5)

        if self._pool_optimizer_thread:
            self._pool_optimizer_thread.join(timeout=5)

        # Close all connections
        with self._pool_lock:
            connection_ids = list(self._all_connections.keys())

            for conn_id in connection_ids:
                self._remove_connection(conn_id)

        logger.info("Connection pool manager shutdown complete")


def main():
    """CLI interface for testing the Connection Pool Manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Advanced Connection Pool Manager")
    parser.add_argument("--db-url", required=True, help="Database URL")
    parser.add_argument("--test", action="store_true", help="Run performance test")
    parser.add_argument("--stats", action="store_true", help="Show pool statistics")
    parser.add_argument("--details", action="store_true", help="Show connection details")
    parser.add_argument("--warm", type=int, help="Warm pool to specified size")
    parser.add_argument("--strategy", choices=["fixed", "dynamic", "adaptive"],
                       default="dynamic", help="Pool strategy")
    parser.add_argument("--max-connections", type=int, default=20, help="Maximum connections")

    args = parser.parse_args()

    try:
        # Configure pool
        config = PoolConfiguration(
            max_connections=args.max_connections,
            pool_strategy=PoolStrategy(args.strategy),
            enable_load_balancing=True,
            enable_connection_warming=True
        )

        # Initialize pool manager
        pool_manager = AdvancedConnectionPoolManager(args.db_url, config)

        if args.warm:
            warmed = pool_manager.warm_pool(args.warm)
            print(f"Warmed pool with {warmed} connections")

        if args.test:
            print("Running connection pool performance test...")

            # Simulate concurrent load
            import concurrent.futures

            def test_connection():
                try:
                    managed_conn = pool_manager.acquire_connection()
                    start_time = time.time()

                    # Simulate query
                    cursor = managed_conn.connection.execute("SELECT 1")
                    _ = cursor.fetchone()

                    execution_time = (time.time() - start_time) * 1000
                    pool_manager.release_connection(managed_conn, execution_time, True)

                    return execution_time
                except Exception as e:
                    return f"Error: {e}"

            # Run concurrent tests
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(test_connection) for _ in range(100)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            successful_results = [r for r in results if isinstance(r, float)]
            print(f"Test completed: {len(successful_results)}/100 successful")
            if successful_results:
                print(f"Average response time: {statistics.mean(successful_results):.2f}ms")

        if args.stats:
            stats = pool_manager.get_statistics()
            print("Connection Pool Statistics:")
            print(f"Total Connections: {stats.total_connections}")
            print(f"Active Connections: {stats.active_connections}")
            print(f"Idle Connections: {stats.idle_connections}")
            print(f"Total Requests: {stats.total_requests}")
            print(f"Successful Requests: {stats.successful_requests}")
            print(f"Pool Efficiency: {stats.pool_efficiency:.1f}%")
            print(f"Average Wait Time: {stats.avg_wait_time_ms:.2f}ms")
            print(f"Average Response Time: {stats.avg_response_time_ms:.2f}ms")

        if args.details:
            details = pool_manager.get_connection_details()
            print("Connection Details:")
            for detail in details:
                print(f"  ID: {detail['connection_id']}")
                print(f"    State: {detail['state']}")
                print(f"    Queries: {detail['total_queries']}")
                print(f"    Avg Time: {detail['avg_query_time_ms']:.2f}ms")
                print(f"    Age: {detail['age_seconds']:.1f}s")
                print(f"    Idle: {detail['idle_time_seconds']:.1f}s")
                print()

        pool_manager.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
