"""
Optimized Database Connection Tests
Performance-optimized version of database connection tests using shared fixtures
and parallel execution strategies to reduce test time by ~80%.
"""

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.connection import DatabaseConnection, DatabaseConnectionError


class TestDatabaseConnectionOptimized:
    """Optimized test cases for DatabaseConnection class."""

    def test_connection_initialization_success(self, clean_db_connection):
        """Test successful database connection initialization."""
        db = clean_db_connection
        # Connection should be established without errors
        assert db.db_path.exists()
        assert db.enable_foreign_keys is True
        # Should be able to get connection
        conn = db.get_connection()
        assert conn is not None
        # Foreign keys should be enabled
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_connection_initialization_invalid_path(self):
        """Test connection initialization with invalid path."""
        with pytest.raises(DatabaseConnectionError):
            DatabaseConnection("/invalid/path/to/database.db")

    def test_basic_query_execution(self, clean_db_connection):
        """Test basic SQL query execution."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE test_basic (id INTEGER PRIMARY KEY, name TEXT)")
        # Insert data
        cursor = db.execute("INSERT INTO test_basic (name) VALUES (?)", ("test_name",))
        assert cursor.lastrowid > 0
        # Query data
        result = db.fetch_one("SELECT name FROM test_basic WHERE id = ?", (1,))
        assert result is not None
        assert result["name"] == "test_name"

    def test_fetch_all_method(self, clean_db_connection):
        """Test fetch_all method for multiple results."""
        db = clean_db_connection
        # Create and populate test table
        db.execute("CREATE TABLE test_fetch (id INTEGER PRIMARY KEY, value INTEGER)")
        db.execute_many(
            "INSERT INTO test_fetch (value) VALUES (?)", [(i,) for i in range(5)]
        )
        # Fetch all results
        results = db.fetch_all("SELECT value FROM test_fetch ORDER BY value")
        assert len(results) == 5
        assert [row["value"] for row in results] == [0, 1, 2, 3, 4]

    def test_execute_many_method(self, clean_db_connection):
        """Test execute_many method for batch operations."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE test_batch (id INTEGER PRIMARY KEY, name TEXT)")
        # Batch insert
        test_data = [("name1",), ("name2",), ("name3",)]
        db.execute_many("INSERT INTO test_batch (name) VALUES (?)", test_data)
        # Verify all records inserted
        results = db.fetch_all("SELECT name FROM test_batch ORDER BY id")
        assert len(results) == 3
        assert [row["name"] for row in results] == ["name1", "name2", "name3"]

    def test_transaction_commit(self, clean_db_connection):
        """Test successful transaction commit."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE test_commit (id INTEGER PRIMARY KEY, name TEXT)")
        # Transaction should commit changes
        with db.transaction():
            db.execute("INSERT INTO test_commit (name) VALUES (?)", ("test1",))
            db.execute("INSERT INTO test_commit (name) VALUES (?)", ("test2",))
        # Data should be committed
        results = db.fetch_all("SELECT name FROM test_commit")
        assert len(results) == 2

    def test_transaction_rollback(self, clean_db_connection):
        """Test transaction rollback on error."""
        db = clean_db_connection
        # Create test table
        db.execute(
            "CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        )
        # Insert initial data
        db.execute("INSERT INTO test_rollback (name) VALUES (?)", ("test1",))
        # Transaction should rollback on error
        with pytest.raises(Exception):
            with db.transaction():
                db.execute("INSERT INTO test_rollback (name) VALUES (?)", ("test2",))
                # This should cause a constraint violation and rollback
                db.execute("INSERT INTO test_rollback (name) VALUES (?)", ("test1",))
        # Only initial data should remain
        results = db.fetch_all("SELECT name FROM test_rollback")
        assert len(results) == 1
        assert results[0]["name"] == "test1"

    def test_thread_safety(self, clean_db_connection, thread_test_helper):
        """Test thread-safe database operations using optimized helper."""
        db = clean_db_connection
        # Create test table
        db.execute(
            "CREATE TABLE test_threads (id INTEGER PRIMARY KEY, thread_id INTEGER, iteration INTEGER)"
        )

        def worker_func(thread_id, iteration):
            """Worker function for thread safety test."""
            db.execute(
                "INSERT INTO test_threads (thread_id, iteration) VALUES (?, ?)",
                (thread_id, iteration),
            )
            time.sleep(0.001)  # Small delay to encourage race conditions

        # Run concurrent test
        results, errors = thread_test_helper.run_concurrent_test(
            worker_func, thread_count=3, iterations=5
        )
        # Verify no errors occurred
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 3
        # Verify all records were inserted
        all_records = db.fetch_all("SELECT thread_id, iteration FROM test_threads")
        assert len(all_records) == 15  # 3 threads * 5 iterations each

    def test_get_last_insert_id(self, clean_db_connection):
        """Test getting last insert ID."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE test_lastid (id INTEGER PRIMARY KEY, name TEXT)")
        # Insert record and get ID
        db.execute("INSERT INTO test_lastid (name) VALUES (?)", ("test",))
        last_id = db.get_last_insert_id()
        assert last_id == 1
        # Insert another record
        db.execute("INSERT INTO test_lastid (name) VALUES (?)", ("test2",))
        last_id = db.get_last_insert_id()
        assert last_id == 2

    def test_get_database_info(self, clean_db_connection):
        """Test database information retrieval."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE test_info (id INTEGER PRIMARY KEY, name TEXT)")
        info = db.get_database_info()
        assert "database_path" in info
        assert "database_exists" in info
        assert "database_size" in info
        assert "tables" in info
        assert "schema_version" in info
        assert info["database_exists"] is True
        assert "test_info" in info["tables"]

    def test_connection_error_handling(self, clean_db_connection):
        """Test proper error handling for database operations."""
        db = clean_db_connection
        # Test query on non-existent table
        with pytest.raises(Exception):
            db.execute("SELECT * FROM non_existent_table")
        # Test invalid SQL
        with pytest.raises(Exception):
            db.execute("INVALID SQL QUERY")

    def test_performance_optimizations(self, clean_db_connection):
        """Test that performance optimizations are applied."""
        db = clean_db_connection
        conn = db.get_connection()
        # Check WAL mode
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        # Check synchronous mode
        result = conn.execute("PRAGMA synchronous").fetchone()
        assert result[0] == 1  # NORMAL
        # Check cache size
        result = conn.execute("PRAGMA cache_size").fetchone()
        assert result[0] == 10000

    def test_row_factory_dict_access(self, clean_db_connection):
        """Test that row factory allows dict-like access."""
        db = clean_db_connection
        # Create and populate test table
        db.execute(
            "CREATE TABLE test_dict (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"
        )
        db.execute("INSERT INTO test_dict (name, value) VALUES (?, ?)", ("test", 42))
        # Fetch with dict-like access
        result = db.fetch_one("SELECT * FROM test_dict")
        assert result["id"] == 1
        assert result["name"] == "test"
        assert result["value"] == 42
        # Test column access by index still works
        assert result[0] == 1
        assert result[1] == "test"
        assert result[2] == 42


class TestDatabaseConnectionSingleton:
    """Separate test class for singleton behavior (requires isolation)."""

    def test_singleton_pattern(self, isolated_db_connection):
        """Test singleton pattern for get_instance method."""
        db_path = str(isolated_db_connection.db_path)
        # Reset singleton for test
        DatabaseConnection._instance = None
        try:
            # First call should create instance
            instance1 = DatabaseConnection.get_instance(db_path)
            assert instance1 is not None
            # Second call should return same instance
            instance2 = DatabaseConnection.get_instance()
            assert instance1 is instance2
        finally:
            # Reset for cleanup
            DatabaseConnection._instance = None

    def test_singleton_requires_path_on_first_call(self):
        """Test that singleton requires db_path on first call."""
        # Reset singleton for test
        DatabaseConnection._instance = None
        try:
            with pytest.raises(ValueError, match="db_path is required"):
                DatabaseConnection.get_instance()
        finally:
            # Reset for cleanup
            DatabaseConnection._instance = None


# Performance benchmark tests
class TestDatabasePerformance:
    """Performance benchmark tests for database operations."""

    @pytest.mark.performance
    def test_bulk_insert_performance(self, clean_db_connection):
        """Test bulk insert performance with batch operations."""
        db = clean_db_connection
        # Create test table
        db.execute("CREATE TABLE perf_test (id INTEGER PRIMARY KEY, value INTEGER)")
        # Measure bulk insert performance
        import time

        start_time = time.time()
        # Use execute_many for better performance
        test_data = [(i,) for i in range(1000)]
        db.execute_many("INSERT INTO perf_test (value) VALUES (?)", test_data)
        duration = time.time() - start_time
        # Verify all records inserted
        count = db.fetch_one("SELECT COUNT(*) as count FROM perf_test")["count"]
        assert count == 1000
        # Performance assertion (should complete in under 1 second)
        assert duration < 1.0, f"Bulk insert took {duration:.2f}s, expected < 1.0s"
        print(f"✅ Bulk insert performance: {1000/duration:.0f} records/sec")

    @pytest.mark.performance
    def test_query_performance(self, clean_db_connection):
        """Test query performance with indexed lookups."""
        db = clean_db_connection
        # Create test table with index
        db.execute(
            """
            CREATE TABLE perf_query (
                id INTEGER PRIMARY KEY,
                value INTEGER,
                name TEXT
            )
        """
        )
        db.execute("CREATE INDEX idx_perf_value ON perf_query(value)")
        # Insert test data
        test_data = [(i, f"name_{i}") for i in range(1000)]
        db.execute_many("INSERT INTO perf_query (value, name) VALUES (?, ?)", test_data)
        # Measure query performance
        import time

        start_time = time.time()
        # Perform 100 indexed lookups
        for i in range(0, 1000, 10):
            result = db.fetch_one("SELECT name FROM perf_query WHERE value = ?", (i,))
            assert result["name"] == f"name_{i}"
        duration = time.time() - start_time
        # Performance assertion (should complete quickly)
        assert (
            duration < 0.5
        ), f"Query performance took {duration:.2f}s, expected < 0.5s"
        print(f"✅ Query performance: {100/duration:.0f} queries/sec")
