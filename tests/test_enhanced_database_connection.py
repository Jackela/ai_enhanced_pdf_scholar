"""
Comprehensive tests for enhanced database connection with pooling and thread safety.
Tests cover:
- Connection pooling and lifecycle management
- Thread safety and concurrent access
- Transaction management with savepoints
- Error handling and recovery
- Performance optimizations
"""

import os
import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import (
    ConnectionPool,
    ConnectionPoolExhaustedError,
    DatabaseConnection,
    DatabaseConnectionError,
    TransactionError,
)


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    def pool(self, temp_db):
        """Create connection pool for testing."""
        pool = ConnectionPool(temp_db, max_connections=5)
        yield pool
        pool.close_all()

    def test_connection_creation(self, pool):
        """Test basic connection creation and return."""
        conn_info = pool.get_connection()
        assert conn_info is not None
        assert conn_info.connection is not None
        assert conn_info.in_use is True
        pool.return_connection(conn_info)
        assert conn_info.in_use is False

    def test_connection_reuse(self, pool):
        """Test connection reuse from pool."""
        # Get and return connection
        conn_info1 = pool.get_connection()
        conn_id1 = conn_info1.connection_id
        pool.return_connection(conn_info1)
        # Get connection again - should reuse
        conn_info2 = pool.get_connection()
        conn_id2 = conn_info2.connection_id
        # Should be the same connection
        assert conn_id1 == conn_id2
        pool.return_connection(conn_info2)

    def test_max_connections_limit(self, pool):
        """Test connection pool limit enforcement."""
        connections = []
        # Get maximum connections
        for i in range(5):
            conn_info = pool.get_connection()
            connections.append(conn_info)
        # Try to get one more - should fail
        with pytest.raises(ConnectionPoolExhaustedError):
            pool.get_connection()
        # Return all connections
        for conn_info in connections:
            pool.return_connection(conn_info)

    def test_connection_stats(self, pool):
        """Test connection pool statistics."""
        stats = pool.get_stats()
        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "pool_size" in stats
        assert "created" in stats
        assert "reused" in stats
        # Get connection and check stats
        conn_info = pool.get_connection()
        stats = pool.get_stats()
        assert stats["active_connections"] == 1
        assert stats["created"] >= 1
        pool.return_connection(conn_info)


class TestDatabaseConnection:
    """Test enhanced database connection functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    def db_connection(self, temp_db):
        """Create database connection for testing."""
        conn = DatabaseConnection(temp_db, max_connections=10)
        yield conn
        conn.close_all_connections()

    def test_basic_connection(self, db_connection):
        """Test basic database connection functionality."""
        conn = db_connection.get_connection()
        assert conn is not None
        # Test basic query
        cursor = db_connection.execute("SELECT 1 as test")
        result = cursor.fetchone()
        assert result is not None
        assert result["test"] == 1

    def test_table_operations(self, db_connection):
        """Test table creation and basic operations."""
        # Create table
        db_connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER
            )
        """
        )
        # Insert data
        db_connection.execute(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("test", 42)
        )
        # Query data
        result = db_connection.fetch_one(
            "SELECT * FROM test_table WHERE name = ?", ("test",)
        )
        assert result is not None
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_transaction_management(self, db_connection):
        """Test transaction management with commit and rollback."""
        # Create test table
        db_connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """
        )
        # Test successful transaction
        with db_connection.transaction():
            db_connection.execute(
                "INSERT INTO test_table (name) VALUES (?)", ("success",)
            )
        # Verify data was committed
        result = db_connection.fetch_one("SELECT COUNT(*) as count FROM test_table")
        assert result["count"] == 1
        # Test transaction rollback
        try:
            with db_connection.transaction():
                db_connection.execute(
                    "INSERT INTO test_table (name) VALUES (?)", ("rollback",)
                )
                # Force an error
                raise Exception("Test error")
        except Exception:
            pass
        # Verify rollback worked
        result = db_connection.fetch_one("SELECT COUNT(*) as count FROM test_table")
        assert result["count"] == 1  # Should still be 1

    def test_nested_transactions(self, db_connection):
        """Test nested transactions with savepoints."""
        # Create test table
        db_connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """
        )
        # Test nested transaction
        with db_connection.transaction():
            db_connection.execute(
                "INSERT INTO test_table (name) VALUES (?)", ("outer",)
            )
            try:
                with db_connection.transaction("inner"):
                    db_connection.execute(
                        "INSERT INTO test_table (name) VALUES (?)", ("inner",)
                    )
                    # Force rollback of inner transaction
                    raise Exception("Inner transaction error")
            except Exception:
                pass
            # Outer transaction should still be valid
            db_connection.execute(
                "INSERT INTO test_table (name) VALUES (?)", ("after_inner",)
            )
        # Verify only outer and after_inner records exist
        results = db_connection.fetch_all("SELECT name FROM test_table ORDER BY name")
        names = [r["name"] for r in results]
        assert "outer" in names
        assert "after_inner" in names
        assert "inner" not in names

    def test_batch_operations(self, db_connection):
        """Test batch insert operations."""
        # Create test table
        db_connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER
            )
        """
        )
        # Batch insert
        params_list = [("item1", 1), ("item2", 2), ("item3", 3)]
        db_connection.execute_many(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", params_list
        )
        # Verify all records inserted
        result = db_connection.fetch_one("SELECT COUNT(*) as count FROM test_table")
        assert result["count"] == 3

    def test_error_handling(self, db_connection):
        """Test comprehensive error handling."""
        # Test invalid SQL
        with pytest.raises(DatabaseConnectionError):
            db_connection.execute("INVALID SQL")
        # Test constraint violation
        db_connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        """
        )
        db_connection.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))
        with pytest.raises(DatabaseConnectionError):
            db_connection.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))


class TestThreadSafety:
    """Test thread safety and concurrent access."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    def db_connection(self, temp_db):
        """Create database connection for testing."""
        conn = DatabaseConnection(temp_db, max_connections=20)
        # Create test table
        conn.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                thread_id INTEGER,
                operation_id INTEGER,
                timestamp REAL
            )
        """
        )
        yield conn
        conn.close_all_connections()

    def test_concurrent_connections(self, db_connection):
        """Test multiple threads can get connections simultaneously."""
        num_threads = 10
        connections = {}
        errors = []

        def get_connection(thread_id):
            try:
                conn = db_connection.get_connection()
                connections[thread_id] = conn
                time.sleep(0.1)  # Hold connection briefly
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=get_connection, args=(i,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        assert len(errors) == 0
        assert len(connections) == num_threads

    def test_concurrent_operations(self, db_connection):
        """Test concurrent database operations."""
        num_threads = 10
        operations_per_thread = 20
        errors = []

        def worker(thread_id):
            try:
                for op_id in range(operations_per_thread):
                    with db_connection.transaction():
                        db_connection.execute(
                            "INSERT INTO test_table (thread_id, operation_id, timestamp) VALUES (?, ?, ?)",
                            (thread_id, op_id, time.time()),
                        )
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # Start threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker, thread_id) for thread_id in range(num_threads)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors.append(str(e))
        assert len(errors) == 0
        # Verify all operations completed
        result = db_connection.fetch_one("SELECT COUNT(*) as count FROM test_table")
        expected_count = num_threads * operations_per_thread
        assert result["count"] == expected_count

    def test_connection_isolation(self, db_connection):
        """Test that transactions in different threads are isolated."""
        barrier = threading.Barrier(2)
        results = {}

        def thread1():
            try:
                with db_connection.transaction():
                    db_connection.execute(
                        "INSERT INTO test_table (thread_id, operation_id) VALUES (1, 1)"
                    )
                    barrier.wait()  # Sync with thread2
                    barrier.wait()  # Wait for thread2 to check
                # Transaction commits here
                results["thread1"] = "success"
            except Exception as e:
                results["thread1"] = str(e)

        def thread2():
            try:
                barrier.wait()  # Wait for thread1 to start transaction
                # Check if we can see thread1's uncommitted data (should not)
                result = db_connection.fetch_one(
                    "SELECT COUNT(*) as count FROM test_table WHERE thread_id = 1"
                )
                results["thread2_during"] = result["count"]
                barrier.wait()  # Signal thread1 to continue
                # Wait a bit for thread1 to commit
                time.sleep(0.1)
                # Now we should see the committed data
                result = db_connection.fetch_one(
                    "SELECT COUNT(*) as count FROM test_table WHERE thread_id = 1"
                )
                results["thread2_after"] = result["count"]
            except Exception as e:
                results["thread2"] = str(e)

        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # Verify isolation worked
        assert results.get("thread2_during", 1) == 0  # Should not see uncommitted data
        assert results.get("thread2_after", 0) == 1  # Should see committed data


class TestPerformance:
    """Test performance characteristics of the enhanced connection."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            os.unlink(db_path)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    def db_connection(self, temp_db):
        """Create database connection for testing."""
        conn = DatabaseConnection(temp_db, max_connections=20)
        # Create test table with index
        conn.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.execute("CREATE INDEX idx_name ON test_table(name)")
        conn.execute("CREATE INDEX idx_value ON test_table(value)")
        yield conn
        conn.close_all_connections()

    def test_bulk_insert_performance(self, db_connection):
        """Test performance of bulk insert operations."""
        num_records = 1000
        start_time = time.time()
        # Bulk insert using batch operations
        params_list = [(f"item_{i}", i, time.time()) for i in range(num_records)]
        db_connection.execute_many(
            "INSERT INTO test_table (name, value, created_at) VALUES (?, ?, ?)",
            params_list,
        )
        end_time = time.time()
        duration = end_time - start_time
        print(
            f"Inserted {num_records} records in {duration:.3f}s ({num_records/duration:.0f} records/sec)"
        )
        # Verify all records inserted
        result = db_connection.fetch_one("SELECT COUNT(*) as count FROM test_table")
        assert result["count"] == num_records
        # Performance should be reasonable (more than 100 records/sec)
        assert num_records / duration > 100

    def test_connection_pool_efficiency(self, db_connection):
        """Test connection pool reuse efficiency."""
        # Perform multiple operations
        for i in range(100):
            db_connection.execute("SELECT 1")
        stats_after = db_connection.get_pool_stats()
        # Should have good reuse ratio
        total_operations = stats_after["created"] + stats_after["reused"]
        reuse_ratio = (
            stats_after["reused"] / total_operations if total_operations > 0 else 0
        )
        print(f"Connection reuse ratio: {reuse_ratio:.2%}")
        # Should reuse connections efficiently
        assert reuse_ratio >= 0.5  # At least 50% reuse


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
