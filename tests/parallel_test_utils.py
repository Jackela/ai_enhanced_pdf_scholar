"""
Enhanced Parallel Test Utilities for AI Enhanced PDF Scholar

Provides advanced parallel testing capabilities with database isolation,
performance optimization, and intelligent test distribution.
"""

import asyncio
import hashlib
import os
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple
from unittest.mock import Mock

import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.database.connection import DatabaseConnection
from src.database.migrations.manager import MigrationManager
from src.database.migrations.runner import MigrationRunner


@dataclass
class ParallelTestMetrics:
    """Metrics tracking for parallel test execution."""
    
    test_name: str
    worker_id: str
    start_time: float
    end_time: Optional[float] = None
    database_operations: int = 0
    memory_usage_mb: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    isolation_level: str = "function"  # function, class, module, session
    
    @property
    def duration_ms(self) -> float:
        """Calculate test duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    def mark_completed(self, success: bool = True, error: Optional[str] = None):
        """Mark test as completed with results."""
        self.end_time = time.time()
        self.success = success
        self.error_message = error


@dataclass
class IsolationStrategy:
    """Configuration for test database isolation strategies."""
    
    strategy_name: str
    isolation_level: str  # per_test, per_class, per_worker, shared
    cleanup_mode: str     # immediate, batch, session_end
    connection_pooling: bool = True
    transaction_isolation: bool = True
    parallel_safe: bool = True
    memory_limit_mb: int = 100
    
    # Performance characteristics
    setup_time_ms: float = 0.0
    cleanup_time_ms: float = 0.0
    memory_overhead_mb: float = 0.0


class ParallelDatabaseManager:
    """
    Advanced database manager for parallel test execution with isolation guarantees.
    
    Features:
    - Per-worker database isolation
    - Connection pooling optimization
    - Memory leak prevention
    - Performance monitoring
    - Automatic cleanup
    """
    
    _instance: Optional['ParallelDatabaseManager'] = None
    _lock = threading.RLock()
    
    def __init__(self):
        if ParallelDatabaseManager._instance is not None:
            raise RuntimeError("Use get_instance() to get ParallelDatabaseManager")
        
        self.worker_databases: Dict[str, DatabaseConnection] = {}
        self.test_databases: Dict[str, DatabaseConnection] = {}
        self.isolation_strategies: Dict[str, IsolationStrategy] = {}
        self.metrics: Dict[str, ParallelTestMetrics] = {}
        self.temp_files: List[Path] = []
        self.active_connections: Set[str] = set()
        
        # Performance tracking
        self.total_tests_run = 0
        self.total_databases_created = 0
        self.total_cleanup_operations = 0
        self.peak_memory_usage_mb = 0.0
        
        # Initialize isolation strategies
        self._initialize_isolation_strategies()
        
        # Register cleanup
        import atexit
        atexit.register(self.cleanup_all)
    
    @classmethod
    def get_instance(cls) -> 'ParallelDatabaseManager':
        """Get singleton instance with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _initialize_isolation_strategies(self):
        """Initialize available isolation strategies."""
        
        # Strategy 1: Per-test isolation (highest isolation, slower)
        self.isolation_strategies["per_test"] = IsolationStrategy(
            strategy_name="per_test",
            isolation_level="per_test",
            cleanup_mode="immediate",
            connection_pooling=False,
            transaction_isolation=True,
            parallel_safe=True,
            memory_limit_mb=50,
        )
        
        # Strategy 2: Per-worker isolation (balanced)
        self.isolation_strategies["per_worker"] = IsolationStrategy(
            strategy_name="per_worker",
            isolation_level="per_worker", 
            cleanup_mode="batch",
            connection_pooling=True,
            transaction_isolation=True,
            parallel_safe=True,
            memory_limit_mb=100,
        )
        
        # Strategy 3: Optimized parallel (fastest)
        self.isolation_strategies["optimized_parallel"] = IsolationStrategy(
            strategy_name="optimized_parallel",
            isolation_level="per_worker",
            cleanup_mode="batch",
            connection_pooling=True,
            transaction_isolation=False,  # Uses table-level cleanup
            parallel_safe=True,
            memory_limit_mb=150,
        )
        
        # Strategy 4: Memory constrained (for CI environments)
        self.isolation_strategies["memory_constrained"] = IsolationStrategy(
            strategy_name="memory_constrained",
            isolation_level="shared",
            cleanup_mode="immediate",
            connection_pooling=True,
            transaction_isolation=False,
            parallel_safe=True,
            memory_limit_mb=25,
        )
    
    def get_worker_id(self) -> str:
        """Get current pytest-xdist worker ID or create one."""
        # Try to get pytest-xdist worker ID
        worker_id = os.environ.get("PYTEST_XDIST_WORKER")
        if worker_id:
            return worker_id
        
        # Fallback to thread-based ID
        return f"thread_{threading.get_ident()}"
    
    def get_database_for_test(
        self, 
        test_name: str, 
        isolation_strategy: str = "per_worker",
        force_new: bool = False
    ) -> Tuple[DatabaseConnection, ParallelTestMetrics]:
        """
        Get database connection for a test with specified isolation strategy.
        
        Args:
            test_name: Name of the test
            isolation_strategy: Strategy to use for database isolation
            force_new: Force creation of new database
            
        Returns:
            Tuple of (DatabaseConnection, ParallelTestMetrics)
        """
        with self._lock:
            worker_id = self.get_worker_id()
            strategy = self.isolation_strategies.get(isolation_strategy, 
                                                   self.isolation_strategies["per_worker"])
            
            # Create metrics for this test
            metrics = ParallelTestMetrics(
                test_name=test_name,
                worker_id=worker_id,
                start_time=time.time(),
                isolation_level=strategy.isolation_level
            )
            self.metrics[test_name] = metrics
            
            # Determine database key based on strategy
            if strategy.isolation_level == "per_test" or force_new:
                db_key = f"{test_name}_{uuid.uuid4().hex[:8]}"
            elif strategy.isolation_level == "per_worker":
                db_key = f"worker_{worker_id}"
            else:  # shared
                db_key = "shared_test_db"
            
            # Get or create database
            if db_key not in self.worker_databases or force_new:
                db = self._create_isolated_database(db_key, strategy)
                self.worker_databases[db_key] = db
                self.total_databases_created += 1
            else:
                db = self.worker_databases[db_key]
                
            # Clean database state if needed
            if strategy.cleanup_mode == "immediate" or force_new:
                self._clean_database_state(db, strategy)
            
            self.active_connections.add(db_key)
            self.total_tests_run += 1
            
            return db, metrics
    
    def _create_isolated_database(self, db_key: str, strategy: IsolationStrategy) -> DatabaseConnection:
        """Create a new isolated database for testing."""
        start_time = time.time()
        
        # Create temporary database file
        temp_file = tempfile.NamedTemporaryFile(
            suffix=f"_{db_key}.db", 
            delete=False,
            prefix="test_parallel_"
        )
        temp_file.close()
        temp_path = Path(temp_file.name)
        self.temp_files.append(temp_path)
        
        # Create database connection with optimized settings
        max_connections = 10 if strategy.connection_pooling else 5
        db = DatabaseConnection(
            str(temp_path), 
            max_connections=max_connections,
            connection_timeout=5.0,  # Faster timeout for tests
            enable_monitoring=False   # Disable monitoring for test performance
        )
        
        # Run migrations
        try:
            migration_manager = MigrationManager(db)
            migration_runner = MigrationRunner(migration_manager)
            result = migration_runner.migrate_to_latest()
            
            if not result.get("success", False):
                raise Exception(f"Migration failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            # Clean up on failure
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to create test database: {e}") from e
        
        # Update strategy metrics
        setup_time = (time.time() - start_time) * 1000
        strategy.setup_time_ms = max(strategy.setup_time_ms, setup_time)
        
        return db
    
    def _clean_database_state(self, db: DatabaseConnection, strategy: IsolationStrategy):
        """Clean database state between tests."""
        start_time = time.time()
        
        try:
            if strategy.transaction_isolation:
                # Use transaction-based cleanup
                with db.transaction():
                    # Get all user tables (excluding system tables)
                    tables = db.fetch_all(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%' AND name != 'schema_versions'"
                    )
                    
                    # Delete all data from tables
                    for table in tables:
                        table_name = table['name']
                        db.execute(f"DELETE FROM {table_name}")
                        
                    # Reset sequences
                    db.execute("DELETE FROM sqlite_sequence")
            else:
                # Use table-level cleanup (faster)
                tables = db.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name != 'schema_versions'"
                )
                
                for table in tables:
                    table_name = table['name']
                    try:
                        db.execute(f"DELETE FROM {table_name}")
                    except Exception:
                        # Continue with other tables if one fails
                        continue
                
                # Reset sequences
                try:
                    db.execute("DELETE FROM sqlite_sequence")
                except Exception:
                    pass
        
        except Exception as e:
            # Log but don't fail test - database might be in an inconsistent state
            print(f"Warning: Failed to clean database state: {e}")
        
        # Update strategy metrics
        cleanup_time = (time.time() - start_time) * 1000
        strategy.cleanup_time_ms = max(strategy.cleanup_time_ms, cleanup_time)
    
    def return_database(self, test_name: str, success: bool = True, error: Optional[str] = None):
        """Return database after test completion."""
        with self._lock:
            if test_name in self.metrics:
                metrics = self.metrics[test_name]
                metrics.mark_completed(success, error)
                
                # Update performance statistics
                if metrics.duration_ms > 1000:  # Log slow tests
                    print(f"Slow parallel test: {test_name} took {metrics.duration_ms:.2f}ms")
    
    def get_optimal_isolation_strategy(self, test_characteristics: Dict[str, Any]) -> str:
        """
        Determine optimal isolation strategy based on test characteristics.
        
        Args:
            test_characteristics: Dictionary with test metadata
            
        Returns:
            Name of optimal isolation strategy
        """
        # Analyze test characteristics
        is_database_heavy = test_characteristics.get("database_operations", 0) > 10
        requires_clean_state = test_characteristics.get("requires_isolation", False)
        is_concurrent_safe = test_characteristics.get("concurrent_safe", True)
        memory_sensitive = test_characteristics.get("memory_sensitive", False)
        
        # Decision logic
        if memory_sensitive or os.environ.get("CI") == "true":
            return "memory_constrained"
        elif requires_clean_state or not is_concurrent_safe:
            return "per_test"
        elif is_database_heavy:
            return "per_worker"
        else:
            return "optimized_parallel"
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        with self._lock:
            completed_tests = [m for m in self.metrics.values() if m.end_time is not None]
            
            if not completed_tests:
                return {"error": "No completed tests to report"}
            
            # Calculate statistics
            durations = [m.duration_ms for m in completed_tests]
            successful_tests = [m for m in completed_tests if m.success]
            failed_tests = [m for m in completed_tests if not m.success]
            
            # Strategy performance
            strategy_stats = {}
            for strategy_name in self.isolation_strategies:
                strategy_tests = [m for m in completed_tests if m.isolation_level == strategy_name]
                if strategy_tests:
                    strategy_durations = [m.duration_ms for m in strategy_tests]
                    strategy_stats[strategy_name] = {
                        "test_count": len(strategy_tests),
                        "avg_duration_ms": sum(strategy_durations) / len(strategy_durations),
                        "min_duration_ms": min(strategy_durations),
                        "max_duration_ms": max(strategy_durations),
                        "success_rate": len([m for m in strategy_tests if m.success]) / len(strategy_tests)
                    }
            
            return {
                "total_tests_run": self.total_tests_run,
                "completed_tests": len(completed_tests),
                "successful_tests": len(successful_tests),
                "failed_tests": len(failed_tests),
                "success_rate": len(successful_tests) / len(completed_tests) if completed_tests else 0,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "total_databases_created": self.total_databases_created,
                "strategy_performance": strategy_stats,
                "isolation_strategies": {
                    name: {
                        "setup_time_ms": strategy.setup_time_ms,
                        "cleanup_time_ms": strategy.cleanup_time_ms,
                        "memory_limit_mb": strategy.memory_limit_mb,
                        "parallel_safe": strategy.parallel_safe
                    }
                    for name, strategy in self.isolation_strategies.items()
                }
            }
    
    def cleanup_all(self):
        """Cleanup all databases and temporary files."""
        with self._lock:
            # Close all database connections
            for db_key, db in self.worker_databases.items():
                try:
                    db.close_all_connections()
                except Exception as e:
                    print(f"Warning: Error closing database {db_key}: {e}")
            
            # Remove temporary files
            for temp_file in self.temp_files:
                try:
                    temp_file.unlink(missing_ok=True)
                except Exception as e:
                    print(f"Warning: Error removing temp file {temp_file}: {e}")
            
            # Clear collections
            self.worker_databases.clear()
            self.test_databases.clear()
            self.temp_files.clear()
            self.active_connections.clear()
            
            self.total_cleanup_operations += 1


class ParallelTestOrchestrator:
    """
    Orchestrates parallel test execution with intelligent load balancing
    and resource management.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(os.cpu_count() or 4, 8)
        self.db_manager = ParallelDatabaseManager.get_instance()
        self.test_queue: List[Tuple[str, Dict[str, Any]]] = []
        self.results: Dict[str, Any] = {}
        self.active_workers: Set[str] = set()
    
    def add_test(self, test_name: str, test_characteristics: Dict[str, Any]):
        """Add a test to the execution queue."""
        self.test_queue.append((test_name, test_characteristics))
    
    def execute_parallel_tests(self) -> Dict[str, Any]:
        """Execute all queued tests in parallel."""
        if not self.test_queue:
            return {"error": "No tests to execute"}
        
        start_time = time.time()
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tests
            future_to_test = {
                executor.submit(self._execute_single_test, test_name, characteristics): test_name
                for test_name, characteristics in self.test_queue
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_test):
                test_name = future_to_test[future]
                try:
                    test_result = future.result(timeout=300)  # 5 minute timeout per test
                    results[test_name] = test_result
                except Exception as e:
                    results[test_name] = {
                        "success": False,
                        "error": str(e),
                        "duration_ms": 0
                    }
        
        total_duration = (time.time() - start_time) * 1000
        
        return {
            "execution_summary": {
                "total_tests": len(self.test_queue),
                "successful_tests": len([r for r in results.values() if r.get("success", False)]),
                "total_duration_ms": total_duration,
                "parallel_efficiency": len(self.test_queue) / (total_duration / 1000) if total_duration > 0 else 0
            },
            "test_results": results,
            "performance_report": self.db_manager.get_performance_report()
        }
    
    def _execute_single_test(self, test_name: str, characteristics: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single test with optimal isolation strategy."""
        worker_id = self.db_manager.get_worker_id()
        self.active_workers.add(worker_id)
        
        try:
            # Get optimal isolation strategy
            strategy = self.db_manager.get_optimal_isolation_strategy(characteristics)
            
            # Get database for test
            db, metrics = self.db_manager.get_database_for_test(
                test_name, 
                isolation_strategy=strategy
            )
            
            # Execute test (this would be the actual test function)
            # For now, simulate test execution
            test_success = self._simulate_test_execution(db, characteristics)
            
            # Return database
            self.db_manager.return_database(
                test_name, 
                success=test_success, 
                error=None if test_success else "Test failed"
            )
            
            return {
                "success": test_success,
                "duration_ms": metrics.duration_ms,
                "worker_id": worker_id,
                "isolation_strategy": strategy,
                "database_operations": metrics.database_operations
            }
            
        except Exception as e:
            self.db_manager.return_database(test_name, success=False, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "duration_ms": 0,
                "worker_id": worker_id
            }
        finally:
            self.active_workers.discard(worker_id)
    
    def _simulate_test_execution(self, db: DatabaseConnection, characteristics: Dict[str, Any]) -> bool:
        """Simulate test execution for demonstration."""
        # Simulate database operations
        operations = characteristics.get("database_operations", 1)
        
        try:
            for i in range(operations):
                # Simple database operation
                db.execute("SELECT 1")
                
            # Simulate some processing time
            time.sleep(0.01 * operations)
            
            return True
        except Exception:
            return False


class ConcurrentTestHelper:
    """
    Enhanced helper for concurrent test operations with resource management
    and performance optimization.
    """
    
    def __init__(self, max_concurrency: int = 10):
        self.max_concurrency = max_concurrency
        self.results: List[Any] = []
        self.errors: List[Exception] = []
        self.lock = threading.Lock()
        
    def run_concurrent_operations(
        self, 
        operations: List[Any], 
        operation_func: callable,
        timeout: float = 30.0
    ) -> Tuple[List[Any], List[Exception]]:
        """
        Run operations concurrently with controlled concurrency and timeout.
        
        Args:
            operations: List of operation parameters
            operation_func: Function to execute for each operation
            timeout: Maximum time to wait for all operations
            
        Returns:
            Tuple of (results, errors)
        """
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            # Submit all operations
            future_to_operation = {
                executor.submit(operation_func, op): op 
                for op in operations
            }
            
            # Collect results with timeout
            for future in as_completed(future_to_operation, timeout=timeout):
                operation = future_to_operation[future]
                try:
                    result = future.result()
                    with self.lock:
                        self.results.append(result)
                except Exception as e:
                    with self.lock:
                        self.errors.append(e)
        
        return self.results.copy(), self.errors.copy()
    
    async def run_async_concurrent_operations(
        self,
        operations: List[Any],
        async_operation_func: callable,
        max_concurrent: int = 10
    ) -> Tuple[List[Any], List[Exception]]:
        """Run async operations with controlled concurrency."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        errors = []
        
        async def controlled_operation(operation):
            async with semaphore:
                try:
                    result = await async_operation_func(operation)
                    results.append(result)
                    return result
                except Exception as e:
                    errors.append(e)
                    raise
        
        # Execute all operations
        await asyncio.gather(
            *[controlled_operation(op) for op in operations],
            return_exceptions=True
        )
        
        return results, errors


# Utility functions for test categorization and optimization
def categorize_test_for_parallel_execution(test_func) -> Dict[str, Any]:
    """
    Analyze test function to determine optimal parallel execution strategy.
    
    Args:
        test_func: Test function to analyze
        
    Returns:
        Dictionary with test characteristics
    """
    # Analyze test markers
    markers = getattr(test_func, "pytestmark", [])
    marker_names = {m.name for m in markers} if markers else set()
    
    # Analyze test name and docstring for hints
    test_name = test_func.__name__
    test_doc = test_func.__doc__ or ""
    
    # Determine characteristics
    characteristics = {
        "database_operations": 5 if "database" in marker_names else 2,
        "requires_isolation": "integration" in marker_names or "isolation" in test_name.lower(),
        "concurrent_safe": "concurrent" not in marker_names or "thread" not in test_name.lower(),
        "memory_sensitive": "memory" in test_name.lower() or "large" in test_doc.lower(),
        "expected_duration_ms": 1000 if "slow" in marker_names else 100,
        "markers": list(marker_names)
    }
    
    return characteristics


def optimize_test_execution_order(test_list: List[Tuple[str, Dict[str, Any]]]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Optimize test execution order for better parallel performance.
    
    Args:
        test_list: List of (test_name, characteristics) tuples
        
    Returns:
        Optimized test execution order
    """
    # Sort by isolation requirements (isolated tests first to avoid blocking)
    # Then by expected duration (longer tests first for better load balancing)
    def sort_key(test_item):
        _, characteristics = test_item
        isolation_priority = 1 if characteristics.get("requires_isolation", False) else 2
        duration_priority = -characteristics.get("expected_duration_ms", 0)  # Negative for descending
        return (isolation_priority, duration_priority)
    
    return sorted(test_list, key=sort_key)