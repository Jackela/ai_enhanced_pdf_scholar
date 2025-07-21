"""
Database Connection Manager
Thread-safe SQLite connection pooling with advanced transaction management,
connection lifecycle management, and performance optimizations.
"""

import logging
import sqlite3
import threading
import time
import weakref
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""

    pass


class ConnectionPoolExhaustedError(Exception):
    """Raised when connection pool is exhausted."""

    pass


class TransactionError(Exception):
    """Raised when transaction operations fail."""

    pass


@dataclass
class ConnectionInfo:
    """Information about a database connection."""

    connection: sqlite3.Connection
    thread_id: int
    created_at: float
    last_used: float
    in_use: bool = False
    transaction_level: int = 0
    connection_id: str | None = None

    def __post_init__(self) -> None:
        if self.connection_id is None:
            self.connection_id = str(uuid4())


class ConnectionPool:
    """
    Thread-safe SQLite connection pool with advanced features:
    - Connection lifecycle management
    - Automatic connection cleanup
    - Health monitoring and recovery
    - Performance optimization
    """

    CONNECTION_EXPIRY_SECONDS = 3600  # 1 hour in seconds

    def __init__(
        self, db_path: str, max_connections: int = 20, connection_timeout: float = 30.0
    ) -> None:
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        # Thread-safe connection management
        self._lock = threading.RLock()
        self._pool: Queue[ConnectionInfo] = Queue(maxsize=max_connections)
        self._active_connections: dict[str, ConnectionInfo] = {}
        self._connection_count = 0
        self._stats = {"created": 0, "reused": 0, "expired": 0, "errors": 0}
        # Connection lifecycle management
        self._cleanup_timer: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._start_cleanup_timer()
        # Register cleanup at exit
        import atexit

        atexit.register(self.close_all)
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Connection pool initialized: {self.db_path} (max: {max_connections})"
        )

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with advanced performance optimizations."""
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=self.connection_timeout,
                isolation_level=None,  # Autocommit mode for manual transaction control
            )
            # Enable row factory for dict-like access
            conn.row_factory = sqlite3.Row
            # Performance and safety optimizations
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -128000")  # 128MB cache (increased)
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 536870912")  # 512MB mmap (increased)
            conn.execute(
                "PRAGMA page_size = 65536"
            )  # 64KB page size for better performance
            # Query optimization settings
            conn.execute("PRAGMA automatic_index = ON")
            conn.execute("PRAGMA query_only = OFF")
            conn.execute("PRAGMA trusted_schema = ON")
            # Connection performance settings
            conn.execute("PRAGMA busy_timeout = 30000")  # 30 second busy timeout
            conn.execute(
                "PRAGMA wal_autocheckpoint = 1000"
            )  # Checkpoint every 1000 pages
            # Run optimization
            conn.execute("PRAGMA optimize")
            self._stats["created"] += 1
            logger.debug(
                f"Created optimized connection (total: {self._stats['created']})"
            )
            return conn
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Failed to create database connection: {e}")
            raise DatabaseConnectionError(f"Connection creation failed: {e}") from e

    def get_connection(self) -> ConnectionInfo:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            # Try to get a connection from the pool
            try:
                while True:
                    try:
                        conn_info = self._pool.get_nowait()
                        # Check if connection is still valid
                        if self._is_connection_valid(conn_info):
                            conn_info.in_use = True
                            conn_info.last_used = time.time()
                            conn_info.thread_id = threading.get_ident()
                            if conn_info.connection_id:
                                self._active_connections[conn_info.connection_id] = (
                                    conn_info
                                )
                            self._stats["reused"] += 1
                            return conn_info
                        else:
                            # Connection expired, close it
                            self._close_connection(conn_info)
                            self._stats["expired"] += 1
                            continue
                    except Empty:
                        break
            except Exception as e:
                logger.warning(f"Error retrieving connection from pool: {e}")
            # Create new connection if pool is empty and under limit
            if self._connection_count < self.max_connections:
                conn = self._create_connection()
                conn_info = ConnectionInfo(
                    connection=conn,
                    thread_id=threading.get_ident(),
                    created_at=time.time(),
                    last_used=time.time(),
                    in_use=True,
                )
                self._connection_count += 1
                if conn_info.connection_id:
                    self._active_connections[conn_info.connection_id] = conn_info
                return conn_info
            # Pool exhausted
            raise ConnectionPoolExhaustedError(
                f"Connection pool exhausted (max: {self.max_connections})"
            )

    def return_connection(self, conn_info: ConnectionInfo) -> None:
        """Return a connection to the pool."""
        with self._lock:
            if conn_info.connection_id in self._active_connections:
                del self._active_connections[conn_info.connection_id]
                # Reset connection state
                conn_info.in_use = False
                conn_info.transaction_level = 0
                # Return to pool if still valid
                if self._is_connection_valid(conn_info):
                    try:
                        self._pool.put_nowait(conn_info)
                    except Exception:
                        # Pool is full, close the connection
                        self._close_connection(conn_info)
                else:
                    self._close_connection(conn_info)

    def _is_connection_valid(self, conn_info: ConnectionInfo) -> bool:
        """Check if a connection is still valid and not expired."""
        try:
            # Check if connection is alive
            conn_info.connection.execute("SELECT 1").fetchone()
            # Check if connection is too old (expire after 1 hour)
            age = time.time() - conn_info.created_at
            return not age > self.CONNECTION_EXPIRY_SECONDS
        except Exception:
            return False

    def _close_connection(self, conn_info: ConnectionInfo) -> None:
        """Close a database connection."""
        try:
            conn_info.connection.close()
            self._connection_count -= 1
        except Exception:
            pass

    def cleanup_expired_connections(self) -> None:
        """Clean up expired connections from the pool."""
        with self._lock:
            expired = []
            while True:
                try:
                    conn_info = self._pool.get_nowait()
                    if self._is_connection_valid(conn_info):
                        self._pool.put_nowait(conn_info)
                        break
                    else:
                        expired.append(conn_info)
                except Empty:
                    break
            for conn_info in expired:
                self._close_connection(conn_info)
                self._stats["expired"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            return {
                "total_connections": self._connection_count,
                "active_connections": len(self._active_connections),
                "pool_size": self._pool.qsize(),
                "max_connections": self.max_connections,
                **self._stats,
            }

    def _start_cleanup_timer(self) -> None:
        """Start periodic cleanup timer."""

        def cleanup_worker() -> None:
            while not self._shutdown_event.is_set():
                try:
                    self.cleanup_expired_connections()
                    time.sleep(300)  # Cleanup every 5 minutes
                except Exception as e:
                    logger.error(f"Error in cleanup worker: {e}")
                    time.sleep(60)  # Retry after 1 minute on error

        self._cleanup_timer = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_timer.start()
        logger.debug("Connection cleanup timer started")

    def close_all(self) -> None:
        """Close all connections in the pool."""
        # Signal shutdown
        self._shutdown_event.set()
        with self._lock:
            # Close active connections
            for conn_info in list(self._active_connections.values()):
                self._close_connection(conn_info)
            self._active_connections.clear()
            # Close pooled connections
            while True:
                try:
                    conn_info = self._pool.get_nowait()
                    self._close_connection(conn_info)
                except Empty:
                    break
            self._connection_count = 0
            logger.info("All database connections closed")


class DatabaseConnection:
    """
    {
        "name": "DatabaseConnection",
        "version": "2.0.0",
        "description": "High-performance thread-safe SQLite connection manager.",
        "dependencies": ["sqlite3", "threading", "queue"],
        "interface": {
            "inputs": ["db_path: str", "max_connections: int", "timeout: float"],
            "outputs": "Thread-safe database connection with pooling"
        }
    }
    Enhanced thread-safe SQLite database connection manager.
    Features:
    - Connection pooling with lifecycle management
    - Advanced transaction support with savepoints
    - Performance optimizations
    - Comprehensive error handling
    - Connection health monitoring
    """

    # Constants
    CONNECTION_EXPIRY_SECONDS = 3600  # 1 hour in seconds
    SLOW_QUERY_THRESHOLD_MS = 100  # Threshold for slow query logging in ms

    # Singleton pattern
    _instance = None
    _lock = threading.Lock()

    def __init__(
        self, db_path: str, max_connections: int = 20, connection_timeout: float = 30.0
    ) -> None:
        """
        Initialize enhanced database connection manager.
        Args:
            db_path: Path to SQLite database file
            max_connections: Maximum number of connections in pool
            connection_timeout: Connection timeout in seconds
        Raises:
            DatabaseConnectionError: If connection fails
        """
        # Validate path input
        if not db_path or not str(db_path).strip():
            raise DatabaseConnectionError("Database path cannot be empty")

        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.enable_foreign_keys = True

        # Validate database path
        try:
            # Check if parent directory exists or can be created
            parent_dir = self.db_path.parent
            if not parent_dir.exists():
                # Try to create parent directory
                parent_dir.mkdir(parents=True, exist_ok=True)
            # Try to create a test file to verify write permissions
            test_file = parent_dir / f".test_write_{threading.current_thread().ident}"
            test_file.touch()
            test_file.unlink()  # Clean up test file
        except (OSError, PermissionError) as e:
            raise DatabaseConnectionError(f"Cannot access database path: {e}") from e
        # Initialize connection pool
        self._pool = ConnectionPool(db_path, max_connections, connection_timeout)
        # Thread-local storage for current connection
        self._local = threading.local()
        # Test connection
        try:
            conn_info = self._pool.get_connection()
            self._pool.return_connection(conn_info)
            logger.info(f"Enhanced database connection established: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise DatabaseConnectionError(f"Cannot connect to database: {e}") from e

    @classmethod
    def get_instance(cls, db_path: str | None = None) -> "DatabaseConnection":
        """Get singleton instance of DatabaseConnection."""
        if cls._instance is None:
            if db_path is None:
                raise ValueError("db_path is required for first instance creation")
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    def _get_current_connection(self) -> ConnectionInfo:
        """Get or create a connection for the current thread."""
        if (
            not hasattr(self._local, "connection_info")
            or self._local.connection_info is None
        ):
            self._local.connection_info = self._pool.get_connection()

            # Register cleanup for thread termination
            def cleanup() -> None:
                if (
                    hasattr(self._local, "connection_info")
                    and self._local.connection_info
                ):
                    self._pool.return_connection(self._local.connection_info)
                    self._local.connection_info = None

            # Use weakref callback for cleanup
            self._local.cleanup_ref = weakref.finalize(self._local, cleanup)
        # mypy can't determine connection_info is not None due to check above
        return self._local.connection_info  # type: ignore

    def get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection from pool.
        Returns:
            SQLite connection for current thread
        """
        conn_info = self._get_current_connection()
        return conn_info.connection

    @contextmanager
    def transaction(
        self, savepoint_name: str | None = None
    ) -> Iterator[sqlite3.Connection]:
        """
        Enhanced context manager for database transactions with savepoint support.
        Args:
            savepoint_name: Optional savepoint name for nested transactions
        Usage:
            with db.transaction():
                db.execute("INSERT INTO ...", params)
                with db.transaction("nested"):
                    db.execute("UPDATE ...", params)
        """
        conn_info = self._get_current_connection()
        conn = conn_info.connection
        # Determine transaction type
        is_nested = conn_info.transaction_level > 0
        savepoint_name = (
            savepoint_name
            or f"sp_{conn_info.transaction_level}_{int(time.time() * 1000)}"
        )
        if is_nested:
            # Use savepoint for nested transaction
            try:
                conn.execute(f"SAVEPOINT {savepoint_name}")
                conn_info.transaction_level += 1
                logger.debug(
                    f"Started savepoint: {savepoint_name} "
                    f"(L{conn_info.transaction_level})"
                )
                yield conn
                conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                conn_info.transaction_level -= 1
                logger.debug(
                    f"Released savepoint: {savepoint_name} "
                    f"(L{conn_info.transaction_level})"
                )
            except Exception as e:
                try:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    conn_info.transaction_level -= 1
                    logger.debug(
                        f"Rolled back savepoint: {savepoint_name} "
                        f"(L{conn_info.transaction_level})"
                    )
                except Exception as rollback_error:
                    logger.error(
                        f"Failed rollback savepoint {savepoint_name}: {rollback_error}"
                    )
                logger.error(
                    f"Transaction rolled back to savepoint {savepoint_name}: {e}"
                )
                raise TransactionError(f"Nested transaction failed: {e}") from e
        else:
            # Start new transaction
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn_info.transaction_level = 1
                logger.debug("Started new transaction")
                yield conn
                conn.execute("COMMIT")
                conn_info.transaction_level = 0
                logger.debug("Transaction committed successfully")
            except Exception as e:
                try:
                    conn.execute("ROLLBACK")
                    conn_info.transaction_level = 0
                    logger.debug("Transaction rolled back successfully")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
                logger.error(f"Transaction failed and rolled back: {e}")
                raise TransactionError(f"Transaction failed: {e}") from e

    def _handle_operational_error(
        self, e: sqlite3.OperationalError, attempt: int, max_retries: int
    ) -> bool:
        """Handle operational errors with retry logic. Returns True if should retry."""
        error_msg = str(e).lower()
        if "database is locked" in error_msg or "database is busy" in error_msg:
            if attempt < max_retries:
                wait_time = 0.1 * (2**attempt)  # Exponential backoff
                logger.warning(
                    f"DB busy, retrying in {wait_time}s (attempt {attempt + 1})"
                )
                time.sleep(wait_time)
                return True
            else:
                logger.error(f"Database locked after {max_retries} retries: {e}")
                raise DatabaseConnectionError(
                    f"Database locked after retries: {e}"
                ) from e
        elif "disk i/o error" in error_msg:
            logger.error(f"Disk I/O error: {e}")
            raise DatabaseConnectionError(f"Disk I/O error: {e}") from e
        elif "database disk image is malformed" in error_msg:
            logger.error(f"Database corruption detected: {e}")
            raise DatabaseConnectionError(f"Database corruption: {e}") from e
        elif "no such table" in error_msg or "no such column" in error_msg:
            logger.error(f"Schema error: {e}")
            raise DatabaseConnectionError(f"Schema error: {e}") from e
        else:
            logger.error(f"Operational error in query execution: {e}")
            raise DatabaseConnectionError(f"Query execution failed: {e}") from e

    def _handle_database_error(
        self, e: Exception, query: str, params: tuple[Any, ...] | None
    ) -> None:
        """Handle database errors with appropriate logging."""
        logger.error(f"{type(e).__name__}: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")

        if isinstance(e, sqlite3.IntegrityError):
            raise DatabaseConnectionError(f"Integrity constraint violation: {e}") from e
        elif isinstance(e, sqlite3.DataError):
            raise DatabaseConnectionError(f"Data error: {e}") from e
        elif isinstance(e, sqlite3.DatabaseError):
            raise DatabaseConnectionError(f"Database error: {e}") from e
        else:
            raise DatabaseConnectionError(f"Unexpected error: {e}") from e

    def execute(
        self, query: str, params: tuple[Any, ...] | None = None, max_retries: int = 3
    ) -> sqlite3.Cursor:
        """
        Execute SQL query with parameters and comprehensive error handling.
        Args:
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retries for transient errors
        Returns:
            Cursor object with results
        Raises:
            DatabaseConnectionError: If query execution fails
        """
        conn = self.get_connection()
        start_time = time.time()

        for attempt in range(max_retries + 1):
            try:
                cursor = conn.execute(query, params) if params else conn.execute(query)
                execution_time = (time.time() - start_time) * 1000

                if execution_time > self.SLOW_QUERY_THRESHOLD_MS:
                    logger.warning(
                        f"Slow query ({execution_time:.2f}ms): {query[:100]}..."
                    )
                else:
                    logger.debug(
                        f"Executed query ({execution_time:.2f}ms): {query[:100]}..."
                    )
                return cursor

            except sqlite3.OperationalError as e:
                if self._handle_operational_error(e, attempt, max_retries):
                    continue  # Retry
                # If not retrying, exception was already raised in handler

            except (
                sqlite3.IntegrityError,
                sqlite3.DataError,
                sqlite3.DatabaseError,
                Exception,
            ) as e:
                self._handle_database_error(e, query, params)

        # Should never reach here due to exception handling, but added for safety
        raise DatabaseConnectionError("Maximum retries exceeded")

    def execute_many(
        self, query: str, params_list: list[tuple[Any, ...]]
    ) -> sqlite3.Cursor | None:
        """
        Execute SQL query with multiple parameter sets using optimized batch processing.
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        Returns:
            Cursor object
        Raises:
            DatabaseConnectionError: If batch execution fails
        """
        if not params_list:
            logger.warning("Empty parameter list provided to execute_many")
            return None
        conn = self.get_connection()
        start_time = time.time()
        try:
            # Use transaction for batch operations
            with self.transaction():
                cursor = conn.executemany(query, params_list)
            execution_time = (time.time() - start_time) * 1000
            logger.debug(
                f"Executed batch query ({execution_time:.2f}ms): {query[:100]}... "
                f"with {len(params_list)} parameter sets"
            )
            return cursor
        except Exception as e:
            logger.error(f"Batch query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Batch size: {len(params_list)}")
            raise DatabaseConnectionError(f"Batch execution failed: {e}") from e

    def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> sqlite3.Row | None:
        """
        Execute query and fetch one row.
        Args:
            query: SQL query string
            params: Query parameters tuple
        Returns:
            Single row or None if no results
        """
        cursor = self.execute(query, params)
        result = cursor.fetchone()
        return result  # type: ignore # SQLite Row objects are properly typed

    def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[sqlite3.Row]:
        """
        Execute query and fetch all rows.
        Args:
            query: SQL query string
            params: Query parameters tuple
        Returns:
            List of all matching rows
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def get_last_insert_id(self) -> int | None:
        """
        Get the ID of the last inserted row.
        Returns:
            Last insert row ID
        """
        result = self.fetch_one("SELECT last_insert_rowid() as id")
        return int(result["id"]) if result else None

    def get_last_change_count(self) -> int:
        """
        Get the number of rows affected by the last DML operation.
        Returns:
            Number of rows affected by the last INSERT, UPDATE, or DELETE
        """
        result = self.fetch_one("SELECT changes() as count")
        return int(result["count"]) if result else 0

    def close_connection(self) -> None:
        """Return current thread's connection to the pool."""
        if hasattr(self._local, "connection_info") and self._local.connection_info:
            self._pool.return_connection(self._local.connection_info)
            self._local.connection_info = None
            if hasattr(self._local, "cleanup_ref"):
                self._local.cleanup_ref.detach()
            logger.debug("Database connection returned to pool")

    def close_all_connections(self) -> None:
        """Close all connections in the pool."""
        self._pool.close_all()
        logger.info("All database connections closed")

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        return self._pool.get_stats()

    def cleanup_expired_connections(self) -> None:
        """Clean up expired connections from the pool."""
        self._pool.cleanup_expired_connections()

    def get_database_info(self) -> dict[str, Any]:
        """
        Get database information and statistics.
        Returns:
            Dictionary with database metadata
        """
        try:
            info = {
                "database_path": str(self.db_path),
                "database_exists": self.db_path.exists(),
                "database_size": (
                    self.db_path.stat().st_size if self.db_path.exists() else 0
                ),
            }
            # Get table information
            tables = self.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
            info["tables"] = [table["name"] for table in tables]
            # Get database version
            pragma_info = self.fetch_one("PRAGMA user_version")
            info["schema_version"] = pragma_info[0] if pragma_info else 0
            return info
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

    def __del__(self) -> None:
        """Cleanup database connections on destruction."""
        with suppress(Exception):
            self.close_all_connections()
