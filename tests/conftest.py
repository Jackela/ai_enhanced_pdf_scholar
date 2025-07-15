"""
Shared test fixtures for performance optimization.

This module provides optimized fixtures that reduce test execution time by:
- Reusing database connections across tests
- Implementing proper cleanup strategies
- Providing shared test data
"""

import pytest
import tempfile
import threading
from pathlib import Path
from typing import Generator

from src.database.connection import DatabaseConnection
from src.database.migrations import DatabaseMigrator


@pytest.fixture(scope="session")
def shared_db_path() -> Generator[str, None, None]:
    """Create a shared temporary database for the entire test session."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        db_path = temp_db.name
    
    yield db_path
    
    # Cleanup after all tests
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def shared_db_connection(shared_db_path: str) -> Generator[DatabaseConnection, None, None]:
    """Create a shared database connection for the entire test session."""
    db = DatabaseConnection(shared_db_path)
    
    # Initialize database schema
    migrator = DatabaseMigrator(db)
    migrator.create_tables_if_not_exist()
    
    yield db
    
    # Cleanup connections
    db.close_all_connections()


@pytest.fixture(scope="function")
def clean_db_connection(shared_db_connection: DatabaseConnection) -> Generator[DatabaseConnection, None, None]:
    """Provide a clean database connection for each test function."""
    # Clear all tables before each test
    with shared_db_connection.transaction():
        tables = shared_db_connection.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        for table in tables:
            shared_db_connection.execute(f"DELETE FROM {table['name']}")
    
    yield shared_db_connection


@pytest.fixture(scope="function")
def isolated_db_connection() -> Generator[DatabaseConnection, None, None]:
    """Create an isolated database connection for tests that need complete isolation."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        db_path = temp_db.name
    
    try:
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.create_tables_if_not_exist()
        
        yield db
        
    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def test_data_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for test data files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


# Performance measurement fixtures
@pytest.fixture(autouse=True)
def track_test_performance(request):
    """Automatically track test performance for optimization analysis."""
    import time
    start_time = time.time()
    
    yield
    
    duration = time.time() - start_time
    if duration > 1.0:  # Log slow tests (>1 second)
        print(f"\n⚠️  Slow test detected: {request.node.name} took {duration:.2f}s")


# Thread safety testing fixture
@pytest.fixture
def thread_test_helper():
    """Helper for testing thread safety with proper synchronization."""
    class ThreadTestHelper:
        def __init__(self):
            self.results = []
            self.errors = []
            self.lock = threading.Lock()
        
        def run_concurrent_test(self, worker_func, thread_count=3, iterations=5):
            """Run a function concurrently with multiple threads."""
            def worker_wrapper(thread_id):
                try:
                    for i in range(iterations):
                        worker_func(thread_id, i)
                    with self.lock:
                        self.results.append(f"thread_{thread_id}_success")
                except Exception as e:
                    with self.lock:
                        self.errors.append(f"thread_{thread_id}_error: {e}")
            
            threads = []
            for thread_id in range(thread_count):
                thread = threading.Thread(target=worker_wrapper, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            return self.results, self.errors
    
    return ThreadTestHelper()