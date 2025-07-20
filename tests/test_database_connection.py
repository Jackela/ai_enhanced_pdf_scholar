"""
Test Database Connection
Unit tests for the DatabaseConnection class, focusing on connection management,
transactions, and thread safety.
"""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection, DatabaseConnectionError


class TestDatabaseConnection:
    """Test cases for DatabaseConnection class."""

    def setup_method(self):
        """Set up test database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db = DatabaseConnection(self.db_path)

    def teardown_method(self):
        """Clean up after each test."""
        try:
            self.db.close_connection()
            Path(self.db_path).unlink(missing_ok=True)
        except (OSError, FileNotFoundError):
            pass

    def test_connection_initialization_success(self):
        """Test successful database connection initialization."""
        # Connection should be established without errors
        assert self.db.db_path == Path(self.db_path)
        assert self.db.enable_foreign_keys is True
        # Should be able to get connection
        conn = self.db.get_connection()
        assert conn is not None
        # Foreign keys should be enabled
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_connection_initialization_invalid_path(self):
        """Test connection initialization with invalid path."""
        with pytest.raises(DatabaseConnectionError):
            # Use an invalid path that should fail on both Windows and Unix
            DatabaseConnection("")

    def test_singleton_pattern(self):
        """Test singleton pattern for get_instance method."""
        # Reset singleton for test
        DatabaseConnection._instance = None
        # First call should create instance
        instance1 = DatabaseConnection.get_instance(self.db_path)
        assert instance1 is not None
        # Second call should return same instance
        instance2 = DatabaseConnection.get_instance()
        assert instance1 is instance2
        # Reset for cleanup
        DatabaseConnection._instance = None

    def test_singleton_requires_path_on_first_call(self):
        """Test that singleton requires db_path on first call."""
        DatabaseConnection._instance = None
        with pytest.raises(ValueError, match="db_path is required"):
            DatabaseConnection.get_instance()
        # Reset for cleanup
        DatabaseConnection._instance = None

    def test_basic_query_execution(self):
        """Test basic SQL query execution."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        # Insert data
        cursor = self.db.execute("INSERT INTO test (name) VALUES (?)", ("test_name",))
        assert cursor.lastrowid > 0
        # Query data
        result = self.db.fetch_one("SELECT name FROM test WHERE id = ?", (1,))
        assert result is not None
        assert result["name"] == "test_name"

    def test_fetch_all_method(self):
        """Test fetch_all method for multiple results."""
        # Create and populate test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value INTEGER)")
        self.db.execute_many(
            "INSERT INTO test (value) VALUES (?)", [(i,) for i in range(5)]
        )
        # Fetch all results
        results = self.db.fetch_all("SELECT value FROM test ORDER BY value")
        assert len(results) == 5
        assert [row["value"] for row in results] == [0, 1, 2, 3, 4]

    def test_execute_many_method(self):
        """Test execute_many method for batch operations."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        # Batch insert
        test_data = [("name1",), ("name2",), ("name3",)]
        self.db.execute_many("INSERT INTO test (name) VALUES (?)", test_data)
        # Verify all records inserted
        results = self.db.fetch_all("SELECT name FROM test ORDER BY id")
        assert len(results) == 3
        assert [row["name"] for row in results] == ["name1", "name2", "name3"]

    def test_transaction_commit(self):
        """Test successful transaction commit."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        # Transaction should commit changes
        with self.db.transaction():
            self.db.execute("INSERT INTO test (name) VALUES (?)", ("test1",))
            self.db.execute("INSERT INTO test (name) VALUES (?)", ("test2",))
        # Data should be committed
        results = self.db.fetch_all("SELECT name FROM test")
        assert len(results) == 2

    def test_transaction_rollback(self):
        """Test transaction rollback on error."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        # Insert initial data
        self.db.execute("INSERT INTO test (name) VALUES (?)", ("test1",))
        # Transaction should rollback on error
        with pytest.raises(Exception):
            with self.db.transaction():
                self.db.execute("INSERT INTO test (name) VALUES (?)", ("test2",))
                # This should cause a constraint violation and rollback
                self.db.execute("INSERT INTO test (name) VALUES (?)", ("test1",))
        # Only initial data should remain
        results = self.db.fetch_all("SELECT name FROM test")
        assert len(results) == 1
        assert results[0]["name"] == "test1"

    def test_thread_safety(self):
        """Test thread-safe database operations."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, thread_id INTEGER)")
        results = []
        errors = []

        def worker_thread(thread_id):
            """Worker function for thread safety test."""
            try:
                # Each thread should get its own connection
                for i in range(5):
                    self.db.execute(
                        "INSERT INTO test (thread_id) VALUES (?)", (thread_id,)
                    )
                    time.sleep(0.001)  # Small delay to encourage race conditions
                results.append(f"thread_{thread_id}_success")
            except Exception as e:
                errors.append(f"thread_{thread_id}_error: {e}")

        # Start multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        # Verify no errors occurred
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 3
        # Verify all records were inserted
        all_records = self.db.fetch_all("SELECT thread_id FROM test")
        assert len(all_records) == 15  # 3 threads * 5 inserts each

    def test_get_last_insert_id(self):
        """Test getting last insert ID."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        # Insert record and get ID
        self.db.execute("INSERT INTO test (name) VALUES (?)", ("test",))
        last_id = self.db.get_last_insert_id()
        assert last_id == 1
        # Insert another record
        self.db.execute("INSERT INTO test (name) VALUES (?)", ("test2",))
        last_id = self.db.get_last_insert_id()
        assert last_id == 2

    def test_get_database_info(self):
        """Test database information retrieval."""
        # Create test table
        self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        info = self.db.get_database_info()
        assert "database_path" in info
        assert "database_exists" in info
        assert "database_size" in info
        assert "tables" in info
        assert "schema_version" in info
        assert info["database_exists"] is True
        assert "test" in info["tables"]

    def test_connection_error_handling(self):
        """Test proper error handling for database operations."""
        # Test query on non-existent table
        with pytest.raises(Exception):
            self.db.execute("SELECT * FROM non_existent_table")
        # Test invalid SQL
        with pytest.raises(Exception):
            self.db.execute("INVALID SQL QUERY")

    def test_performance_optimizations(self):
        """Test that performance optimizations are applied."""
        conn = self.db.get_connection()
        # Check WAL mode
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        # Check synchronous mode
        result = conn.execute("PRAGMA synchronous").fetchone()
        assert result[0] == 1  # NORMAL
        # Check cache size (negative value indicates pages, -128000 = 128MB cache)
        result = conn.execute("PRAGMA cache_size").fetchone()
        assert result[0] == -128000

    def test_row_factory_dict_access(self):
        """Test that row factory allows dict-like access."""
        # Create and populate test table
        self.db.execute(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"
        )
        self.db.execute("INSERT INTO test (name, value) VALUES (?, ?)", ("test", 42))
        # Fetch with dict-like access
        result = self.db.fetch_one("SELECT * FROM test")
        assert result["id"] == 1
        assert result["name"] == "test"
        assert result["value"] == 42
        # Test column access by index still works
        assert result[0] == 1
        assert result[1] == "test"
        assert result[2] == 42
