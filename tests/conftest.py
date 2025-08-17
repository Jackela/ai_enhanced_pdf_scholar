"""
Optimized Shared Test Fixtures for AI Enhanced PDF Scholar

This conftest.py provides optimized fixtures that improve test performance by:
- Using connection pooling and caching
- Implementing efficient cleanup strategies
- Providing categorized fixtures by scope and purpose
- Monitoring test performance automatically
"""

import tempfile
from pathlib import Path
from typing import Generator, Optional

import pytest

from src.database.connection import DatabaseConnection
from tests.test_utils import (
    AsyncTestHelper,
    MockFactory,
    PerformanceMonitor,
    TestFixtureManager,
    db_manager,
    fixture_manager,
    performance_monitor,
)
from tests.parallel_test_utils import (
    ParallelDatabaseManager,
    ParallelTestOrchestrator,
    ConcurrentTestHelper,
    categorize_test_for_parallel_execution,
)


# =============================================================================
# Session-Scoped Fixtures (Shared across entire test session)
# =============================================================================

@pytest.fixture(scope="session")
def test_data_directory() -> Generator[Path, None, None]:
    """Create a session-scoped temporary directory for test data files."""
    with tempfile.TemporaryDirectory(prefix="ai_pdf_test_") as temp_dir:
        test_dir = Path(temp_dir)
        fixture_manager.cache_fixture("test_data_dir", test_dir)
        yield test_dir


@pytest.fixture(scope="session")
def session_performance_monitor() -> PerformanceMonitor:
    """Session-scoped performance monitor for tracking test performance."""
    return performance_monitor


@pytest.fixture(scope="session")
def mock_factory() -> MockFactory:
    """Session-scoped mock factory for creating test objects."""
    return MockFactory()


# =============================================================================
# Parallel Testing Infrastructure (Enhanced isolation and performance)
# =============================================================================

@pytest.fixture(scope="session")
def parallel_db_manager() -> ParallelDatabaseManager:
    """Session-scoped parallel database manager."""
    return ParallelDatabaseManager.get_instance()


@pytest.fixture(scope="function")
def parallel_db_connection(request, parallel_db_manager) -> Generator[DatabaseConnection, None, None]:
    """
    Enhanced parallel-safe database connection with intelligent isolation.

    Automatically determines optimal isolation strategy based on test characteristics.
    """
    test_name = request.node.name
    test_func = request.function

    # Analyze test characteristics
    characteristics = categorize_test_for_parallel_execution(test_func)

    # Get database with optimal isolation strategy
    db, metrics = parallel_db_manager.get_database_for_test(test_name,
                                                          parallel_db_manager.get_optimal_isolation_strategy(characteristics))

    try:
        yield db
        # Mark test as successful
        parallel_db_manager.return_database(test_name, success=True)
    except Exception as e:
        # Mark test as failed
        parallel_db_manager.return_database(test_name, success=False, error=str(e))
        raise


@pytest.fixture(scope="function")
def parallel_isolated_db(request, parallel_db_manager) -> Generator[DatabaseConnection, None, None]:
    """
    Completely isolated database for tests requiring maximum isolation.
    Creates a new database instance for each test.
    """
    test_name = f"{request.node.name}_isolated"

    # Force per-test isolation
    db, metrics = parallel_db_manager.get_database_for_test(
        test_name,
        isolation_strategy="per_test",
        force_new=True
    )

    try:
        yield db
        parallel_db_manager.return_database(test_name, success=True)
    except Exception as e:
        parallel_db_manager.return_database(test_name, success=False, error=str(e))
        raise


@pytest.fixture(scope="function")
def concurrent_test_helper() -> ConcurrentTestHelper:
    """Enhanced concurrent test helper with resource management."""
    return ConcurrentTestHelper(max_concurrency=8)


@pytest.fixture(scope="function")
def parallel_test_orchestrator() -> ParallelTestOrchestrator:
    """Orchestrator for managing parallel test execution."""
    return ParallelTestOrchestrator()


# =============================================================================
# Function-Scoped Database Fixtures (Optimized for performance)
# =============================================================================

@pytest.fixture(scope="function")
def db_connection(request) -> Generator[DatabaseConnection, None, None]:
    """Fast function-scoped database connection with automatic cleanup."""
    test_name = request.node.name
    db = db_manager.get_test_db(test_name)
    db_manager.clean_test_db(test_name)  # Clean before use
    yield db
    # No cleanup needed - handled by session cleanup


@pytest.fixture(scope="function")
def isolated_db() -> Generator[DatabaseConnection, None, None]:
    """Completely isolated database for tests requiring full isolation."""
    from src.database.migrations.manager import MigrationManager

    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_file.close()

    try:
        db = DatabaseConnection(temp_file.name)
        migrator = MigrationManager(db)
        migrator.migrate_to_latest()
        yield db
    finally:
        db.close_all_connections()
        Path(temp_file.name).unlink(missing_ok=True)


# =============================================================================
# Mock and Test Data Fixtures
# =============================================================================

@pytest.fixture
def mock_pdf_content() -> bytes:
    """Mock PDF content for testing."""
    cached = fixture_manager.get_cached_fixture("mock_pdf_content")
    if cached is None:
        cached = fixture_manager.cache_fixture(
            "mock_pdf_content",
            MockFactory.create_mock_pdf_content()
        )
    return cached


@pytest.fixture
def mock_document_data() -> dict:
    """Mock document data for testing."""
    return MockFactory.create_mock_document_data()


@pytest.fixture
def mock_llama_index():
    """Mock LlamaIndex for testing RAG operations."""
    cached = fixture_manager.get_cached_fixture("mock_llama_index")
    if cached is None:
        cached = fixture_manager.cache_fixture(
            "mock_llama_index",
            MockFactory.create_mock_llama_index()
        )
    return cached


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    return MockFactory.create_mock_embedding_service()


# =============================================================================
# Performance and Concurrency Testing
# =============================================================================

@pytest.fixture
def performance_tracker(request):
    """Track performance of individual tests."""
    monitor = PerformanceMonitor(slow_threshold=0.5)  # 500ms threshold
    monitor.start()
    yield monitor
    duration = monitor.stop(request.node.name)

    # Store performance data for reporting
    if not hasattr(request.config, '_test_performance'):
        request.config._test_performance = []
    request.config._test_performance.append({
        'name': request.node.name,
        'duration': duration
    })


@pytest.fixture
def async_helper() -> AsyncTestHelper:
    """Helper for async operations in tests."""
    return AsyncTestHelper()


@pytest.fixture
def concurrent_test_helper():
    """Optimized helper for concurrent testing."""
    import concurrent.futures
    import threading

    class ConcurrentTestHelper:
        def __init__(self):
            self.results = []
            self.errors = []
            self.lock = threading.Lock()

        def run_parallel(self, func, args_list, max_workers=4):
            """Run function in parallel with controlled concurrency."""
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(func, *args) for args in args_list]

                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        with self.lock:
                            self.results.append(result)
                    except Exception as e:
                        with self.lock:
                            self.errors.append(e)

            return self.results, self.errors

    return ConcurrentTestHelper()


# =============================================================================
# Auto-use Fixtures (Applied to all tests)
# =============================================================================

@pytest.fixture(autouse=True)
def auto_performance_tracking(request):
    """Automatically track test performance and log slow tests."""
    import time

    start_time = time.perf_counter()
    yield
    duration = time.perf_counter() - start_time

    # Log slow tests (>500ms)
    if duration > 0.5:
        print(f"\n🐌 Slow test: {request.node.name} took {duration:.3f}s")

    # Track in session performance monitor
    performance_monitor.measurements.append({
        "test": request.node.name,
        "duration": duration,
        "slow": duration > 0.5
    })


# =============================================================================
# Session Management and Cleanup
# =============================================================================

def pytest_sessionstart(session):
    """Initialize session-wide test resources."""
    print("\n🚀 Starting optimized test session")


def pytest_sessionfinish(session):
    """Clean up session-wide resources and generate reports."""
    # Cleanup WebSocket Manager
    try:
        import asyncio
        from backend.api.main import websocket_manager
        
        # Only cleanup if there's a running event loop or we can create one
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(websocket_manager.cleanup())
        except RuntimeError:
            # No running loop, create one for cleanup
            asyncio.run(websocket_manager.cleanup())
            
        print("   WebSocketManager cleanup completed")
    except Exception as e:
        print(f"   Warning: WebSocketManager cleanup error: {e}")
    
    # Cleanup database manager
    db_manager.cleanup_all()

    # Cleanup parallel database manager
    try:
        parallel_db_manager = ParallelDatabaseManager.get_instance()
        parallel_report = parallel_db_manager.get_performance_report()
        parallel_db_manager.cleanup_all()

        # Generate parallel testing report
        if parallel_report and not parallel_report.get("error"):
            print(f"\n🚀 Parallel Testing Report:")
            print(f"   Total tests: {parallel_report['total_tests_run']}")
            print(f"   Success rate: {parallel_report['success_rate']:.1%}")
            print(f"   Databases created: {parallel_report['total_databases_created']}")
            print(f"   Average duration: {parallel_report['avg_duration_ms']:.1f}ms")

            # Strategy performance
            if parallel_report.get('strategy_performance'):
                print("   Isolation Strategy Performance:")
                for strategy, stats in parallel_report['strategy_performance'].items():
                    print(f"     - {strategy}: {stats['test_count']} tests, "
                          f"{stats['avg_duration_ms']:.1f}ms avg, "
                          f"{stats['success_rate']:.1%} success")

    except Exception as e:
        print(f"   Warning: Error in parallel database cleanup: {e}")

    # Cleanup fixture manager
    fixture_manager.cleanup_all()

    # Generate performance report
    report = performance_monitor.get_report()
    if report["total_tests"] > 0:
        print(f"\n📊 Performance Report:")
        print(f"   Total tests: {report['total_tests']}")
        print(f"   Slow tests: {report['slow_tests']}")
        print(f"   Average duration: {report['average_duration']:.3f}s")

        if report['slowest_tests']:
            print("   Slowest tests:")
            for test in report['slowest_tests']:
                print(f"     - {test['test']}: {test['duration']:.3f}s")

    print("✅ Test session cleanup completed")


# =============================================================================
# Test Collection and Marking
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Optimize test collection and add automatic markers."""
    # Add markers based on file paths
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark performance tests
        if "performance" in str(item.fspath) or "benchmark" in item.name.lower():
            item.add_marker(pytest.mark.slow)

        # Mark security tests
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)

        # Mark database tests
        if any(keyword in item.name.lower() for keyword in ["database", "db", "repository"]):
            item.add_marker(pytest.mark.database)


# =============================================================================
# Configuration Validation
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "database: Database-related tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "unit: Fast unit tests")

    # Initialize performance tracking
    config._test_performance = []
