"""
Optimized Test Utilities for AI Enhanced PDF Scholar
Provides shared utilities, fixtures, and helpers to reduce test complexity.
"""

import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations.manager import MigrationManager
from src.database.migrations.runner import MigrationRunner


class DatabaseTestManager:
    """Optimized database test management with connection pooling."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._connections = {}
            self._temp_files = []

    def get_test_db(self, test_name: str = "default") -> DatabaseConnection:
        """Get or create a test database connection for the given test."""
        if test_name not in self._connections:
            temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            temp_file.close()
            self._temp_files.append(temp_file.name)

            db = DatabaseConnection(temp_file.name)
            migration_manager = MigrationManager(db)
            migration_runner = MigrationRunner(migration_manager)
            result = migration_runner.migrate_to_latest()
            if not result.get("success", False):
                raise Exception(f"Migration failed: {result.get('error', 'Unknown error')}")

            self._connections[test_name] = db

        return self._connections[test_name]

    def clean_test_db(self, test_name: str = "default") -> None:
        """Clean all tables in the test database."""
        if test_name in self._connections:
            db = self._connections[test_name]
            with db.transaction():
                tables = db.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name != 'schema_versions'"
                )
                for table in tables:
                    db.execute(f"DELETE FROM {table['name']}")

    def cleanup_all(self):
        """Cleanup all database connections and temp files."""
        for db in self._connections.values():
            db.close_all_connections()
        self._connections.clear()

        for temp_file in self._temp_files:
            Path(temp_file).unlink(missing_ok=True)
        self._temp_files.clear()


class MockFactory:
    """Factory for creating commonly used mocks."""

    @staticmethod
    def create_mock_pdf_content() -> bytes:
        """Create mock PDF content for testing."""
        return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF"

    @staticmethod
    def create_mock_document_data() -> Dict[str, Any]:
        """Create mock document data for testing."""
        return {
            "id": 1,
            "title": "Test Document",
            "file_path": "/test/path/document.pdf",
            "content_hash": "abc123",
            "metadata": {"pages": 10, "size": 1024}
        }

    @staticmethod
    def create_mock_llama_index() -> Mock:
        """Create a mock LlamaIndex for testing."""
        mock_index = Mock()
        mock_index.query = Mock(return_value=Mock(response="Mock response"))
        mock_index.insert = Mock()
        mock_index.delete = Mock()
        return mock_index

    @staticmethod
    def create_mock_embedding_service() -> Mock:
        """Create a mock embedding service."""
        mock_service = Mock()
        mock_service.get_embeddings = Mock(return_value=[0.1, 0.2, 0.3])
        mock_service.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
        return mock_service


class PerformanceMonitor:
    """Monitor test performance and identify slow tests."""

    def __init__(self, slow_threshold: float = 1.0):
        self.slow_threshold = slow_threshold
        self.measurements = []
        self.start_time = None

    def start(self):
        """Start performance monitoring."""
        self.start_time = time.perf_counter()

    def stop(self, test_name: str = "") -> float:
        """Stop monitoring and return elapsed time."""
        if self.start_time is None:
            return 0.0

        elapsed = time.perf_counter() - self.start_time
        self.measurements.append({
            "test": test_name,
            "duration": elapsed,
            "slow": elapsed > self.slow_threshold
        })

        if elapsed > self.slow_threshold:
            print(f"\n⚠️  Slow test: {test_name} took {elapsed:.3f}s")

        self.start_time = None
        return elapsed

    @contextmanager
    def measure(self, test_name: str = ""):
        """Context manager for measuring test performance."""
        self.start()
        try:
            yield
        finally:
            self.stop(test_name)

    def get_report(self) -> Dict[str, Any]:
        """Get performance report."""
        if not self.measurements:
            return {"total_tests": 0, "slow_tests": 0}

        slow_tests = [m for m in self.measurements if m["slow"]]
        return {
            "total_tests": len(self.measurements),
            "slow_tests": len(slow_tests),
            "average_duration": sum(m["duration"] for m in self.measurements) / len(self.measurements),
            "slowest_tests": sorted(slow_tests, key=lambda x: x["duration"], reverse=True)[:5]
        }


class TestFixtureManager:
    """Manage test fixtures efficiently with caching and cleanup."""

    def __init__(self):
        self._fixture_cache = {}
        self._cleanup_callbacks = []

    def cache_fixture(self, name: str, fixture_data: Any) -> Any:
        """Cache a fixture for reuse across tests."""
        self._fixture_cache[name] = fixture_data
        return fixture_data

    def get_cached_fixture(self, name: str) -> Optional[Any]:
        """Get a cached fixture."""
        return self._fixture_cache.get(name)

    def register_cleanup(self, callback):
        """Register a cleanup callback."""
        self._cleanup_callbacks.append(callback)

    def cleanup_all(self):
        """Run all cleanup callbacks."""
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Warning: Cleanup callback failed: {e}")
        self._cleanup_callbacks.clear()
        self._fixture_cache.clear()


class AsyncTestHelper:
    """Helper for async test operations."""

    @staticmethod
    async def run_concurrent_operations(operations: List, max_concurrency: int = 5):
        """Run multiple async operations with controlled concurrency."""
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrency)

        async def controlled_op(op):
            async with semaphore:
                return await op

        return await asyncio.gather(*[controlled_op(op) for op in operations])

    @staticmethod
    def create_async_mock(**kwargs):
        """Create an async mock for testing."""
        mock = MagicMock(**kwargs)
        mock.__aenter__ = MagicMock(return_value=mock)
        mock.__aexit__ = MagicMock(return_value=None)
        return mock


# Global instances for test optimization
db_manager = DatabaseTestManager()
mock_factory = MockFactory()
performance_monitor = PerformanceMonitor()
fixture_manager = TestFixtureManager()