"""
Demonstration of Enhanced Parallel Testing Features

This script demonstrates the key features and improvements of the enhanced
parallel testing infrastructure for AI Enhanced PDF Scholar.
"""

import asyncio
import time
from pathlib import Path
import pytest

# Import the enhanced parallel testing utilities
from tests.parallel_test_utils import (
    ParallelDatabaseManager,
    ParallelTestOrchestrator, 
    ConcurrentTestHelper
)
from tests.test_categorization import TestAnalyzer, TestExecutionPlanner
from tests.performance_optimization import (
    get_performance_cache,
    get_resource_monitor,
    get_test_distributor
)


# =============================================================================
# Demo Test Cases Using Enhanced Parallel Features
# =============================================================================

@pytest.mark.parallel_safe
@pytest.mark.unit
def test_basic_parallel_safe(parallel_db_connection):
    """
    Example of a basic parallel-safe test using enhanced fixtures.
    
    This test automatically gets an optimized database connection based on
    its characteristics (parallel_safe, unit test).
    """
    # The parallel_db_connection fixture automatically provides
    # the optimal database isolation strategy
    
    # Perform basic database operations
    parallel_db_connection.execute("CREATE TABLE IF NOT EXISTS demo_table (id INTEGER PRIMARY KEY, name TEXT)")
    parallel_db_connection.execute("INSERT INTO demo_table (name) VALUES (?)", ("demo_data",))
    
    # Verify data
    result = parallel_db_connection.fetch_one("SELECT COUNT(*) as count FROM demo_table")
    assert result["count"] >= 1
    
    # Database cleanup is handled automatically by the enhanced fixture


@pytest.mark.parallel_isolated
@pytest.mark.integration
def test_integration_with_isolation(parallel_isolated_db):
    """
    Example of an integration test requiring complete database isolation.
    
    This test gets its own dedicated database instance.
    """
    # This test gets complete database isolation - no sharing with other tests
    
    # Perform integration test operations
    parallel_isolated_db.execute("CREATE TABLE integration_test (id INTEGER PRIMARY KEY, data TEXT)")
    
    # Insert test data that might conflict with other tests
    parallel_isolated_db.execute("INSERT INTO integration_test (data) VALUES (?)", ("sensitive_data",))
    
    # Perform complex operations that require clean state
    with parallel_isolated_db.transaction():
        parallel_isolated_db.execute("UPDATE integration_test SET data = ? WHERE id = ?", ("updated_data", 1))
        
        # Verify transaction state
        result = parallel_isolated_db.fetch_one("SELECT data FROM integration_test WHERE id = ?", (1,))
        assert result["data"] == "updated_data"


@pytest.mark.concurrent
@pytest.mark.database
def test_concurrent_operations(concurrent_test_helper):
    """
    Example of testing concurrent operations with the enhanced helper.
    """
    def database_operation(operation_id):
        """Simulate a database operation."""
        # In a real test, this would use a database connection
        time.sleep(0.01)  # Simulate database work
        return f"result_{operation_id}"
    
    # Run 10 operations concurrently with automatic resource management
    operations = list(range(10))
    results, errors = concurrent_test_helper.run_concurrent_operations(
        operations=operations,
        operation_func=database_operation,
        timeout=5.0
    )
    
    # Verify all operations completed successfully
    assert len(results) == 10
    assert len(errors) == 0
    assert all(f"result_{i}" in results for i in range(10))


@pytest.mark.performance
@pytest.mark.slow
def test_performance_monitoring():
    """
    Example of test with automatic performance monitoring.
    """
    # Get the resource monitor (automatically managed)
    monitor = get_resource_monitor()
    monitor_id = monitor.start_monitoring("performance_demo_test")
    
    try:
        # Simulate performance-critical operations
        data = []
        for i in range(1000):
            data.append(f"performance_data_{i}")
        
        # Simulate some processing
        processed = [item.upper() for item in data]
        
        # Check that we processed correctly
        assert len(processed) == 1000
        assert all(item.startswith("PERFORMANCE_DATA_") for item in processed)
        
    finally:
        # Get performance metrics
        metrics = monitor.stop_monitoring(monitor_id)
        print(f"Test used {metrics.memory_usage_mb:.1f}MB memory")
        print(f"Test used {metrics.cpu_usage_percent:.1f}% CPU")


class TestParallelTestingDemo:
    """Demo test class showcasing enhanced parallel testing features."""
    
    @pytest.mark.unit
    @pytest.mark.parallel_safe
    def test_shared_database_with_cleanup(self, parallel_db_connection):
        """Test using shared database with automatic cleanup."""
        
        # This test can share a database with other parallel_safe tests
        # but gets clean state thanks to automatic table cleanup
        
        parallel_db_connection.execute("CREATE TABLE IF NOT EXISTS shared_demo (id INTEGER, value TEXT)")
        parallel_db_connection.execute("INSERT INTO shared_demo (id, value) VALUES (?, ?)", (1, "test_value"))
        
        result = parallel_db_connection.fetch_one("SELECT value FROM shared_demo WHERE id = ?", (1,))
        assert result["value"] == "test_value"
    
    @pytest.mark.integration
    @pytest.mark.db_per_worker
    def test_worker_isolated_database(self, parallel_db_connection):
        """Test using per-worker database isolation."""
        
        # This test shares a database with other tests in the same worker
        # but not with tests in other workers
        
        parallel_db_connection.execute("CREATE TABLE IF NOT EXISTS worker_demo (worker_id TEXT, data TEXT)")
        
        # Each worker will see only its own data
        worker_id = "demo_worker"  # In real tests, this would be detected automatically
        parallel_db_connection.execute("INSERT INTO worker_demo (worker_id, data) VALUES (?, ?)", 
                                     (worker_id, "worker_specific_data"))
        
        results = parallel_db_connection.fetch_all("SELECT * FROM worker_demo")
        # This worker should only see its own data
        assert all(row["worker_id"] == worker_id for row in results)
    
    @pytest.mark.e2e
    @pytest.mark.parallel_sequential  
    def test_end_to_end_workflow(self, parallel_isolated_db):
        """End-to-end test that must run sequentially."""
        
        # E2E tests often need complete isolation and sequential execution
        # to avoid conflicts with shared resources
        
        # Simulate complete workflow
        parallel_isolated_db.execute("CREATE TABLE e2e_demo (step INTEGER, status TEXT)")
        
        # Step 1: Initialize
        parallel_isolated_db.execute("INSERT INTO e2e_demo (step, status) VALUES (?, ?)", (1, "initialized"))
        
        # Step 2: Process
        parallel_isolated_db.execute("INSERT INTO e2e_demo (step, status) VALUES (?, ?)", (2, "processed"))
        
        # Step 3: Complete
        parallel_isolated_db.execute("INSERT INTO e2e_demo (step, status) VALUES (?, ?)", (3, "completed"))
        
        # Verify complete workflow
        results = parallel_isolated_db.fetch_all("SELECT step, status FROM e2e_demo ORDER BY step")
        assert len(results) == 3
        assert results[0]["status"] == "initialized"
        assert results[1]["status"] == "processed"
        assert results[2]["status"] == "completed"


# =============================================================================
# Demonstration Functions
# =============================================================================

async def demonstrate_parallel_orchestration():
    """Demonstrate the parallel test orchestration capabilities."""
    
    print("\n🎭 Demonstrating Parallel Test Orchestration")
    print("=" * 50)
    
    orchestrator = ParallelTestOrchestrator(max_workers=4)
    
    # Add some demo tests with different characteristics
    test_characteristics = [
        {
            "database_operations": 5,
            "estimated_duration_ms": 100,
            "memory_requirement_mb": 10,
            "concurrent_safe": True
        },
        {
            "database_operations": 15,
            "estimated_duration_ms": 500,
            "memory_requirement_mb": 50,
            "concurrent_safe": False
        },
        {
            "database_operations": 2,
            "estimated_duration_ms": 50,
            "memory_requirement_mb": 5,
            "concurrent_safe": True
        }
    ]
    
    for i, characteristics in enumerate(test_characteristics):
        orchestrator.add_test(f"demo_test_{i}", characteristics)
    
    # Execute tests in parallel
    print("Executing tests in parallel...")
    start_time = time.time()
    results = orchestrator.execute_parallel_tests()
    execution_time = time.time() - start_time
    
    print(f"✅ Parallel execution completed in {execution_time:.2f}s")
    print(f"📊 Test Results:")
    summary = results["execution_summary"]
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   Successful Tests: {summary['successful_tests']}")
    print(f"   Parallel Efficiency: {summary['parallel_efficiency']:.2f}")
    
    return results


def demonstrate_test_categorization():
    """Demonstrate automatic test categorization."""
    
    print("\n🏷️ Demonstrating Test Categorization")
    print("=" * 50)
    
    analyzer = TestAnalyzer()
    
    # Analyze current test files
    test_dir = Path(__file__).parent
    test_files = list(test_dir.glob("test_*.py"))[:5]  # Analyze first 5 test files
    
    categorized_tests = []
    
    for test_file in test_files:
        print(f"Analyzing {test_file.name}...")
        characteristics_list = analyzer.analyze_test_file(test_file)
        categorized_tests.extend(characteristics_list)
    
    # Display categorization results
    categories = {}
    for char in categorized_tests:
        category = char.category.value
        if category not in categories:
            categories[category] = []
        categories[category].append(char)
    
    print("\n📋 Categorization Results:")
    for category, tests in categories.items():
        print(f"   {category.upper()}: {len(tests)} tests")
        for test in tests[:2]:  # Show first 2 tests per category
            print(f"     - {test.test_name} ({test.estimated_duration_ms}ms)")
    
    return categorized_tests


def demonstrate_performance_caching():
    """Demonstrate performance caching capabilities."""
    
    print("\n🏎️ Demonstrating Performance Caching")
    print("=" * 50)
    
    cache = get_performance_cache()
    cache.clear()  # Start fresh
    
    # Demonstrate cache miss (slow)
    print("Testing cache miss performance...")
    miss_start = time.time()
    result = cache.get("demo_key")
    miss_time = (time.time() - miss_start) * 1000
    print(f"Cache miss took {miss_time:.2f}ms (expected: slower)")
    assert result is None
    
    # Set cache value
    cache.set("demo_key", {"data": "cached_value", "metadata": {"size": 1024}})
    
    # Demonstrate cache hit (fast)
    print("Testing cache hit performance...")
    hit_start = time.time()
    result = cache.get("demo_key")
    hit_time = (time.time() - hit_start) * 1000
    print(f"Cache hit took {hit_time:.2f}ms (expected: faster)")
    assert result is not None
    assert result["data"] == "cached_value"
    
    # Show cache statistics
    stats = cache.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Hit Rate: {stats['hit_rate']:.1%}")
    print(f"   Total Requests: {stats['total_requests']}")
    print(f"   Memory Usage: {stats['memory_usage_mb']:.1f}MB")
    
    print(f"✅ Cache speedup: {miss_time / hit_time:.1f}x faster")


def demonstrate_resource_monitoring():
    """Demonstrate resource monitoring capabilities."""
    
    print("\n💾 Demonstrating Resource Monitoring")
    print("=" * 50)
    
    monitor = get_resource_monitor()
    
    # Start monitoring
    monitor_id = monitor.start_monitoring("demo_resource_test")
    
    # Simulate resource-intensive work
    print("Performing resource-intensive operations...")
    data = []
    for i in range(10000):
        data.append(f"resource_test_data_{i}")
    
    # Process data (CPU intensive)
    processed = [item.upper() for item in data if len(item) > 10]
    
    # Stop monitoring
    metrics = monitor.stop_monitoring(monitor_id)
    
    print(f"📊 Resource Usage:")
    print(f"   Memory Usage: {metrics.memory_usage_mb:.1f}MB")
    print(f"   CPU Usage: {metrics.cpu_usage_percent:.1f}%")
    
    # Check for resource pressure
    pressure_check = monitor.check_resource_pressure()
    if pressure_check["resource_pressure"]:
        print(f"⚠️ Resource Pressure Detected:")
        for alert in pressure_check["alerts"]:
            print(f"   - {alert['message']}")
        print(f"💡 Recommendations:")
        for rec in pressure_check["recommendations"]:
            print(f"   - {rec}")
    else:
        print("✅ No resource pressure detected")
    
    return metrics


async def run_comprehensive_demo():
    """Run a comprehensive demonstration of all features."""
    
    print("🚀 AI Enhanced PDF Scholar - Enhanced Parallel Testing Demo")
    print("=" * 70)
    
    try:
        # 1. Test Categorization Demo
        categorized_tests = demonstrate_test_categorization()
        
        # 2. Performance Caching Demo
        demonstrate_performance_caching()
        
        # 3. Resource Monitoring Demo
        demonstrate_resource_monitoring()
        
        # 4. Parallel Orchestration Demo
        await demonstrate_parallel_orchestration()
        
        print("\n🎉 All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✅ Automatic test categorization and analysis")
        print("✅ Intelligent performance caching")
        print("✅ Resource monitoring and pressure detection")
        print("✅ Parallel test orchestration")
        print("✅ Database isolation strategies")
        print("✅ Concurrent operation management")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    """Run the demonstration."""
    success = asyncio.run(run_comprehensive_demo())
    exit(0 if success else 1)