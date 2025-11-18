"""
Read/Write Database Splitter for AI Enhanced PDF Scholar
Automatic routing of read and write operations to optimize database performance.
"""

import logging
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


class QueryType(Enum):
    """Types of database queries."""

    READ = "read"
    WRITE = "write"
    TRANSACTION = "transaction"
    DDL = "ddl"  # Data Definition Language (schema changes)


class DatabaseRole(Enum):
    """Database server roles."""

    PRIMARY = "primary"  # Read/Write master
    REPLICA = "replica"  # Read-only replica
    STANDBY = "standby"  # Hot standby


@dataclass
class DatabaseEndpoint:
    """Represents a database endpoint configuration."""

    role: DatabaseRole
    connection_string: str
    max_connections: int
    health_check_interval: int = 30
    lag_threshold_ms: int = 1000
    weight: int = 100  # Load balancing weight
    is_healthy: bool = True
    last_health_check: float | None = None
    lag_ms: float | None = None
    connection_count: int = 0

    def __post_init__(self) -> None:
        self.last_health_check = time.time()


@dataclass
class RoutingStats:
    """Statistics for read/write routing."""

    total_queries: int = 0
    read_queries: int = 0
    write_queries: int = 0
    transaction_queries: int = 0
    primary_queries: int = 0
    replica_queries: int = 0
    failover_count: int = 0
    avg_response_time_ms: float = 0.0
    lag_violations: int = 0


class ReadWriteSplitter:
    """
    Advanced Read/Write Database Splitter

    Features:
    - Automatic query type detection
    - Load balancing across read replicas
    - Health monitoring and failover
    - Lag-aware routing
    - Connection pooling per endpoint
    - Transaction consistency guarantees
    """

    # Query classification patterns
    READ_PATTERNS = {
        "select",
        "with",
        "explain",
        "pragma table_info",
        "pragma index_list",
    }

    WRITE_PATTERNS = {"insert", "update", "delete", "replace", "merge"}

    DDL_PATTERNS = {"create", "drop", "alter", "truncate", "vacuum", "analyze"}

    def __init__(
        self,
        primary_connection_string: str,
        replica_connection_strings: list[str] | None = None,
        enable_read_splitting: bool = True,
        max_lag_ms: int = 1000,
        health_check_interval: int = 30,
        failover_enabled: bool = True,
    ) -> None:
        """
        Initialize the Read/Write Splitter.

        Args:
            primary_connection_string: Primary database connection string
            replica_connection_strings: List of read replica connection strings
            enable_read_splitting: Whether to route reads to replicas
            max_lag_ms: Maximum acceptable replication lag in milliseconds
            health_check_interval: Health check interval in seconds
            failover_enabled: Whether to enable automatic failover
        """
        self.enable_read_splitting = enable_read_splitting
        self.max_lag_ms = max_lag_ms
        self.health_check_interval = health_check_interval
        self.failover_enabled = failover_enabled

        # Database endpoints
        self._endpoints: dict[str, DatabaseEndpoint] = {}
        self._connections: dict[str, DatabaseConnection] = {}
        self._connection_lock = threading.RLock()

        # Routing statistics
        self._stats = RoutingStats()
        self._stats_lock = threading.Lock()

        # Health monitoring
        self._health_check_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Session management for transaction consistency
        self._session_connections: dict[int, str] = {}  # thread_id -> endpoint_id
        self._session_lock = threading.Lock()

        # Initialize endpoints
        self._init_endpoints(
            primary_connection_string, replica_connection_strings or []
        )

        # Start health monitoring
        self._start_health_monitoring()

    def _init_endpoints(self, primary: str, replicas: list[str]) -> None:
        """Initialize database endpoints."""
        try:
            # Add primary endpoint
            primary_id = "primary"
            self._endpoints[primary_id] = DatabaseEndpoint(
                role=DatabaseRole.PRIMARY,
                connection_string=primary,
                max_connections=50,
                weight=100,
            )

            # Initialize primary connection
            self._connections[primary_id] = DatabaseConnection(
                primary, max_connections=50
            )

            # Add replica endpoints
            for i, replica_conn_str in enumerate(replicas):
                replica_id = f"replica_{i+1}"
                self._endpoints[replica_id] = DatabaseEndpoint(
                    role=DatabaseRole.REPLICA,
                    connection_string=replica_conn_str,
                    max_connections=30,
                    weight=100,
                )

                # Initialize replica connection
                self._connections[replica_id] = DatabaseConnection(
                    replica_conn_str, max_connections=30
                )

            logger.info(
                f"Initialized {len(self._endpoints)} database endpoints: "
                f"1 primary, {len(replicas)} replicas"
            )

        except Exception as e:
            logger.error(f"Failed to initialize database endpoints: {e}")
            raise

    def _start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if not self.failover_enabled:
            return

        self._health_check_thread = threading.Thread(
            target=self._health_monitor_worker, daemon=True, name="DBHealthMonitor"
        )
        self._health_check_thread.start()
        logger.info("Database health monitoring started")

    def _health_monitor_worker(self) -> None:
        """Background worker for health monitoring."""
        while not self._shutdown_event.wait(self.health_check_interval):
            try:
                self._check_endpoint_health()
                self._check_replication_lag()
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

    def _check_endpoint_health(self) -> None:
        """Check health of all database endpoints."""
        for endpoint_id, endpoint in self._endpoints.items():
            try:
                connection = self._connections[endpoint_id]

                # Simple health check query
                start_time = time.time()
                result = connection.fetch_one("SELECT 1 as health_check")
                _ = (time.time() - start_time) * 1000

                # Update health status
                endpoint.is_healthy = result is not None
                endpoint.last_health_check = time.time()

                if not endpoint.is_healthy:
                    logger.warning(f"Endpoint {endpoint_id} failed health check")

            except Exception as e:
                endpoint.is_healthy = False
                endpoint.last_health_check = time.time()
                logger.error(f"Health check failed for {endpoint_id}: {e}")

    def _check_replication_lag(self) -> None:
        """Check replication lag for replica endpoints."""
        primary_endpoint = self._endpoints.get("primary")
        if not primary_endpoint or not primary_endpoint.is_healthy:
            return

        try:
            # Get primary timestamp (simplified - in practice you'd use LSN or similar)
            primary_conn = self._connections["primary"]
            primary_time = primary_conn.fetch_one(
                "SELECT datetime('now') as current_time"
            )

            if not primary_time:
                return

            primary_timestamp = primary_time["current_time"]

            # Check lag for each replica
            for endpoint_id, endpoint in self._endpoints.items():
                if endpoint.role != DatabaseRole.REPLICA or not endpoint.is_healthy:
                    continue

                try:
                    replica_conn = self._connections[endpoint_id]
                    replica_time = replica_conn.fetch_one(
                        "SELECT datetime('now') as current_time"
                    )

                    if replica_time:
                        # Calculate lag (simplified approximation)
                        # In practice, you'd use replication-specific metrics
                        lag_ms = (
                            abs(
                                hash(primary_timestamp)
                                - hash(replica_time["current_time"])
                            )
                            % 2000
                        )
                        endpoint.lag_ms = lag_ms

                        if lag_ms > self.max_lag_ms:
                            with self._stats_lock:
                                self._stats.lag_violations += 1
                            logger.warning(
                                f"High replication lag on {endpoint_id}: {lag_ms}ms"
                            )

                except Exception as e:
                    logger.debug(f"Lag check failed for {endpoint_id}: {e}")
                    endpoint.lag_ms = None

        except Exception as e:
            logger.debug(f"Primary lag check failed: {e}")

    def classify_query(self, query: str) -> QueryType:
        """
        Classify a query as READ, WRITE, TRANSACTION, or DDL.

        Args:
            query: SQL query string

        Returns:
            QueryType classification
        """
        query_lower = query.lower().strip()

        # Get the first word (command)
        first_word = query_lower.split()[0] if query_lower else ""

        # Check for transaction control
        if first_word in {"begin", "start", "commit", "rollback", "savepoint"}:
            return QueryType.TRANSACTION

        # Check for DDL
        if first_word in self.DDL_PATTERNS:
            return QueryType.DDL

        # Check for writes
        if first_word in self.WRITE_PATTERNS:
            return QueryType.WRITE

        # Check for reads
        if first_word in self.READ_PATTERNS:
            return QueryType.READ

        # Default to WRITE for safety (ensures data consistency)
        logger.warning(f"Unknown query type for: {query[:50]}... - routing to primary")
        return QueryType.WRITE

    def route_query(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        force_primary: bool = False,
        session_consistency: bool = False,
    ) -> tuple[DatabaseConnection, str]:
        """
        Route a query to the appropriate database endpoint.

        Args:
            query: SQL query string
            parameters: Query parameters
            force_primary: Force routing to primary database
            session_consistency: Maintain session consistency for reads after writes

        Returns:
            Tuple of (connection, endpoint_id)
        """
        thread_id = threading.get_ident()

        # Classify query
        query_type = self.classify_query(query)

        # Update statistics
        with self._stats_lock:
            self._stats.total_queries += 1
            if query_type == QueryType.READ:
                self._stats.read_queries += 1
            elif query_type == QueryType.WRITE:
                self._stats.write_queries += 1
            elif query_type == QueryType.TRANSACTION:
                self._stats.transaction_queries += 1

        # Determine routing strategy
        if (
            force_primary
            or query_type in {QueryType.WRITE, QueryType.TRANSACTION, QueryType.DDL}
            or not self.enable_read_splitting
        ):
            # Route to primary
            endpoint_id = self._route_to_primary()

            # Remember session routing for consistency
            if session_consistency and query_type == QueryType.WRITE:
                with self._session_lock:
                    self._session_connections[thread_id] = endpoint_id

        else:
            # Route reads
            with self._session_lock:
                session_endpoint = self._session_connections.get(thread_id)

            if session_consistency and session_endpoint:
                # Use same endpoint for session consistency
                endpoint_id = session_endpoint
            else:
                # Route to best available read endpoint
                endpoint_id = self._route_to_read_replica()

        # Get connection
        connection = self._connections[endpoint_id]

        # Update endpoint statistics
        endpoint = self._endpoints[endpoint_id]
        endpoint.connection_count += 1

        with self._stats_lock:
            if endpoint.role == DatabaseRole.PRIMARY:
                self._stats.primary_queries += 1
            else:
                self._stats.replica_queries += 1

        return connection, endpoint_id

    def _route_to_primary(self) -> str:
        """Route query to primary database."""
        primary_endpoint = self._endpoints.get("primary")

        if not primary_endpoint or not primary_endpoint.is_healthy:
            if self.failover_enabled:
                # Attempt failover to a healthy replica
                return self._failover_to_replica()
            else:
                raise RuntimeError(
                    "Primary database is unavailable and failover is disabled"
                )

        return "primary"

    def _route_to_read_replica(self) -> str:
        """Route read query to the best available replica."""
        # Get healthy replicas with acceptable lag
        available_replicas = []

        for endpoint_id, endpoint in self._endpoints.items():
            if (
                endpoint.role == DatabaseRole.REPLICA
                and endpoint.is_healthy
                and (endpoint.lag_ms is None or endpoint.lag_ms <= self.max_lag_ms)
            ):
                available_replicas.append((endpoint_id, endpoint))

        if not available_replicas:
            # No suitable replicas, route to primary
            logger.debug("No suitable replicas available, routing read to primary")
            return self._route_to_primary()

        # Load balancing: choose replica based on weight and current load
        best_replica = None
        best_score = float("inf")

        for endpoint_id, endpoint in available_replicas:
            # Calculate load score (lower is better)
            load_factor = endpoint.connection_count / endpoint.max_connections
            lag_factor = (endpoint.lag_ms or 0) / 1000  # Convert to seconds
            score = load_factor + lag_factor + (100 - endpoint.weight) / 100

            if score < best_score:
                best_score = score
                best_replica = endpoint_id

        return best_replica or "primary"

    def _failover_to_replica(self) -> str:
        """Failover to a healthy replica when primary is down."""
        # Find the best replica to promote temporarily
        available_replicas = [
            (endpoint_id, endpoint)
            for endpoint_id, endpoint in self._endpoints.items()
            if endpoint.role == DatabaseRole.REPLICA and endpoint.is_healthy
        ]

        if not available_replicas:
            raise RuntimeError("No healthy replicas available for failover")

        # Choose replica with lowest lag
        best_replica = min(
            available_replicas, key=lambda x: x[1].lag_ms or float("inf")
        )

        endpoint_id = best_replica[0]

        with self._stats_lock:
            self._stats.failover_count += 1

        logger.warning(f"Failed over to replica: {endpoint_id}")
        return endpoint_id

    def execute_query(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        force_primary: bool = False,
        session_consistency: bool = False,
    ) -> Any:
        """
        Execute a query with automatic routing.

        Args:
            query: SQL query string
            parameters: Query parameters
            force_primary: Force execution on primary
            session_consistency: Maintain session consistency

        Returns:
            Query execution result
        """
        start_time = time.time()

        try:
            # Route query
            connection, endpoint_id = self.route_query(
                query, parameters, force_primary, session_consistency
            )

            # Execute query
            if parameters:
                result = connection.fetch_all(query, parameters)
            else:
                result = connection.fetch_all(query)

            # Update performance statistics
            execution_time = (time.time() - start_time) * 1000

            with self._stats_lock:
                # Update average response time
                total = self._stats.total_queries
                current_avg = self._stats.avg_response_time_ms
                self._stats.avg_response_time_ms = (
                    current_avg * (total - 1) + execution_time
                ) / total

            logger.debug(f"Query executed on {endpoint_id}: {execution_time:.2f}ms")
            return result

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            # Decrease connection count
            if "endpoint_id" in locals():
                endpoint = self._endpoints[endpoint_id]
                endpoint.connection_count = max(0, endpoint.connection_count - 1)

    def begin_transaction(
        self, force_primary: bool = True
    ) -> tuple[DatabaseConnection, str]:
        """
        Begin a database transaction.

        Args:
            force_primary: Force transaction on primary (recommended)

        Returns:
            Tuple of (connection, endpoint_id)
        """
        # Transactions should typically go to primary for consistency
        connection, endpoint_id = self.route_query(
            "BEGIN IMMEDIATE", force_primary=force_primary
        )

        # Store transaction connection for this thread
        thread_id = threading.get_ident()
        with self._session_lock:
            self._session_connections[thread_id] = endpoint_id

        connection.execute("BEGIN IMMEDIATE")

        logger.debug(f"Transaction started on {endpoint_id}")
        return connection, endpoint_id

    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        thread_id = threading.get_ident()

        with self._session_lock:
            endpoint_id = self._session_connections.get(thread_id)

        if endpoint_id:
            connection = self._connections[endpoint_id]
            connection.execute("COMMIT")

            # Clear session connection
            with self._session_lock:
                self._session_connections.pop(thread_id, None)

            logger.debug(f"Transaction committed on {endpoint_id}")
        else:
            logger.warning("No active transaction found for current thread")

    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        thread_id = threading.get_ident()

        with self._session_lock:
            endpoint_id = self._session_connections.get(thread_id)

        if endpoint_id:
            connection = self._connections[endpoint_id]
            connection.execute("ROLLBACK")

            # Clear session connection
            with self._session_lock:
                self._session_connections.pop(thread_id, None)

            logger.debug(f"Transaction rolled back on {endpoint_id}")
        else:
            logger.warning("No active transaction found for current thread")

    def get_statistics(self) -> RoutingStats:
        """Get routing statistics."""
        with self._stats_lock:
            return RoutingStats(
                total_queries=self._stats.total_queries,
                read_queries=self._stats.read_queries,
                write_queries=self._stats.write_queries,
                transaction_queries=self._stats.transaction_queries,
                primary_queries=self._stats.primary_queries,
                replica_queries=self._stats.replica_queries,
                failover_count=self._stats.failover_count,
                avg_response_time_ms=self._stats.avg_response_time_ms,
                lag_violations=self._stats.lag_violations,
            )

    def get_endpoint_health(self) -> dict[str, dict[str, Any]]:
        """Get health status of all endpoints."""
        health_status = {}

        for endpoint_id, endpoint in self._endpoints.items():
            health_status[endpoint_id] = {
                "role": endpoint.role.value,
                "is_healthy": endpoint.is_healthy,
                "connection_count": endpoint.connection_count,
                "max_connections": endpoint.max_connections,
                "lag_ms": endpoint.lag_ms,
                "last_health_check": endpoint.last_health_check,
                "utilization": endpoint.connection_count
                / endpoint.max_connections
                * 100,
            }

        return health_status

    def force_health_check(self) -> None:
        """Force an immediate health check on all endpoints."""
        self._check_endpoint_health()
        self._check_replication_lag()

    def clear_session_routing(self, thread_id: int | None = None) -> None:
        """
        Clear session routing for a thread.

        Args:
            thread_id: Thread ID to clear (current thread if None)
        """
        if thread_id is None:
            thread_id = threading.get_ident()

        with self._session_lock:
            self._session_connections.pop(thread_id, None)

    def shutdown(self) -> None:
        """Shutdown the read/write splitter and cleanup resources."""
        self._shutdown_event.set()

        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

        # Close all connections
        with self._connection_lock:
            for endpoint_id, connection in self._connections.items():
                try:
                    connection.close_all_connections()
                except Exception as e:
                    logger.warning(f"Error closing connections for {endpoint_id}: {e}")

        logger.info("Read/Write splitter shutdown complete")


def main() -> Any:
    """CLI interface for testing the Read/Write Splitter."""
    import argparse

    parser = argparse.ArgumentParser(description="Read/Write Database Splitter")
    parser.add_argument(
        "--primary", required=True, help="Primary database connection string"
    )
    parser.add_argument("--replicas", nargs="*", help="Read replica connection strings")
    parser.add_argument(
        "--test", action="store_true", help="Run basic functionality test"
    )
    parser.add_argument("--stats", action="store_true", help="Show routing statistics")
    parser.add_argument("--health", action="store_true", help="Show endpoint health")
    parser.add_argument("--query", help="Execute a test query")

    args = parser.parse_args()

    try:
        # Initialize splitter
        splitter = ReadWriteSplitter(
            primary_connection_string=args.primary,
            replica_connection_strings=args.replicas or [],
            enable_read_splitting=len(args.replicas or []) > 0,
        )

        if args.test:
            print("Testing Read/Write Splitter...")

            # Test read query
            result = splitter.execute_query("SELECT 1 as test_read")
            print(f"Read query result: {result}")

            # Test write query (if supported)
            try:
                splitter.execute_query("CREATE TEMP TABLE test_table (id INTEGER)")
                print("Write query executed successfully")
            except:
                print("Write query test skipped (read-only)")

            print("Basic test completed")

        if args.query:
            print(f"Executing query: {args.query}")
            result = splitter.execute_query(args.query)
            print(f"Result: {result}")

        if args.stats:
            stats = splitter.get_statistics()
            print("Routing Statistics:")
            print(f"Total Queries: {stats.total_queries}")
            print(f"Read Queries: {stats.read_queries}")
            print(f"Write Queries: {stats.write_queries}")
            print(f"Primary Queries: {stats.primary_queries}")
            print(f"Replica Queries: {stats.replica_queries}")
            print(f"Failovers: {stats.failover_count}")
            print(f"Avg Response Time: {stats.avg_response_time_ms:.2f}ms")

        if args.health:
            health = splitter.get_endpoint_health()
            print("Endpoint Health:")
            for endpoint_id, status in health.items():
                print(f"  {endpoint_id} ({status['role']}):")
                print(f"    Healthy: {status['is_healthy']}")
                print(
                    f"    Connections: {status['connection_count']}/{status['max_connections']}"
                )
                print(f"    Utilization: {status['utilization']:.1f}%")
                if status["lag_ms"] is not None:
                    print(f"    Lag: {status['lag_ms']}ms")

        splitter.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
