#!/usr/bin/env python3
"""
B6 Database Performance Integration Tests
Comprehensive testing of database performance optimizations and integration with Agent B5 caching.
"""

import json
import logging
import random
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    # B6 Components
    from backend.database.query_optimizer import DynamicQueryOptimizer
    from backend.database.read_write_splitter import ReadWriteSplitter
    from backend.services.connection_pool_manager import AdvancedConnectionPoolManager
    from backend.services.db_performance_monitor import DatabasePerformanceMonitor
    from backend.services.query_cache_manager import IntelligentQueryCacheManager
    from scripts.index_optimization_advisor import IndexOptimizationAdvisor
    from scripts.query_performance_analyzer import QueryPerformanceAnalyzer
    from src.database.connection import DatabaseConnection

    # B5 Components (if available)
    try:
        from backend.services.cache_optimization_service import CacheOptimizationService
        from backend.services.redis_cache_service import RedisCacheService
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False

except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    pytest.skip("Required modules not available", allow_module_level=True)


class PerformanceBenchmark:
    """Performance benchmark results."""

    def __init__(self, name: str):
        self.name = name
        self.execution_times: list[float] = []
        self.throughput_ops_per_sec: float | None = None
        self.cache_hit_rate: float | None = None
        self.memory_usage_mb: float | None = None
        self.connection_efficiency: float | None = None

    def add_execution_time(self, time_ms: float) -> None:
        """Add execution time measurement."""
        self.execution_times.append(time_ms)

    @property
    def avg_execution_time(self) -> float:
        """Average execution time."""
        return statistics.mean(self.execution_times) if self.execution_times else 0.0

    @property
    def p95_execution_time(self) -> float:
        """95th percentile execution time."""
        if not self.execution_times:
            return 0.0

        sorted_times = sorted(self.execution_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)]

    def calculate_improvement(self, baseline: 'PerformanceBenchmark') -> dict[str, float]:
        """Calculate performance improvement compared to baseline."""
        improvements = {}

        if baseline.avg_execution_time > 0:
            time_improvement = (baseline.avg_execution_time - self.avg_execution_time) / baseline.avg_execution_time * 100
            improvements['avg_execution_time'] = time_improvement

        if baseline.throughput_ops_per_sec and self.throughput_ops_per_sec:
            throughput_improvement = (self.throughput_ops_per_sec - baseline.throughput_ops_per_sec) / baseline.throughput_ops_per_sec * 100
            improvements['throughput'] = throughput_improvement

        if baseline.cache_hit_rate is not None and self.cache_hit_rate is not None:
            cache_improvement = self.cache_hit_rate - baseline.cache_hit_rate
            improvements['cache_hit_rate'] = cache_improvement

        return improvements


class B6PerformanceIntegrationTest:
    """Comprehensive B6 database performance integration test suite."""

    def __init__(self, test_db_path: str | None = None):
        """Initialize the integration test suite."""
        self.test_db_path = test_db_path or self._create_test_database()
        self.test_data_size = 10000  # Number of test records
        self.concurrent_users = 20   # Concurrent test users
        self.test_duration_s = 30    # Test duration in seconds

        # Components
        self.db_connection: DatabaseConnection | None = None
        self.query_analyzer: QueryPerformanceAnalyzer | None = None
        self.query_optimizer: DynamicQueryOptimizer | None = None
        self.cache_manager: IntelligentQueryCacheManager | None = None
        self.index_advisor: IndexOptimizationAdvisor | None = None
        self.read_write_splitter: ReadWriteSplitter | None = None
        self.connection_pool: AdvancedConnectionPoolManager | None = None
        self.performance_monitor: DatabasePerformanceMonitor | None = None

        # B5 Integration
        self.redis_cache: RedisCacheService | None = None
        self.cache_optimizer: CacheOptimizationService | None = None

        # Test results
        self.benchmarks: dict[str, PerformanceBenchmark] = {}

    def _create_test_database(self) -> str:
        """Create a temporary test database."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        return temp_file.name

    def setup(self) -> None:
        """Set up all B6 components and test data."""
        logger.info("Setting up B6 performance integration test...")

        # Initialize database connection
        self.db_connection = DatabaseConnection(self.test_db_path, max_connections=50)

        # Create test schema and data
        self._create_test_schema()
        self._populate_test_data()

        # Initialize B6 components
        self.query_analyzer = QueryPerformanceAnalyzer(self.db_connection, enable_monitoring=True)
        self.query_optimizer = DynamicQueryOptimizer(self.db_connection)
        self.cache_manager = IntelligentQueryCacheManager(self.db_connection, self.redis_cache)
        self.index_advisor = IndexOptimizationAdvisor(self.db_connection, self.query_analyzer)

        # Initialize connection pool
        from backend.services.connection_pool_manager import PoolConfiguration
        pool_config = PoolConfiguration(
            max_connections=50,
            min_connections=5,
            pool_strategy="adaptive"
        )
        self.connection_pool = AdvancedConnectionPoolManager(self.test_db_path, pool_config)

        # Initialize performance monitor
        self.performance_monitor = DatabasePerformanceMonitor(
            self.db_connection,
            self.query_analyzer,
            self.cache_manager,
            monitoring_interval_s=5
        )

        # Initialize B5 components if available
        if REDIS_AVAILABLE:
            try:
                self.redis_cache = RedisCacheService()
                self.cache_optimizer = CacheOptimizationService(self.redis_cache)
                logger.info("B5 Redis caching components initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize B5 components: {e}")

        logger.info("B6 setup complete")

    def _create_test_schema(self) -> None:
        """Create test database schema."""
        schema_queries = [
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                file_path TEXT,
                file_hash TEXT UNIQUE,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                raw_text TEXT,
                authors TEXT,
                title TEXT,
                publication_year INTEGER,
                journal TEXT,
                doi TEXT,
                confidence_score REAL,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                index_path TEXT,
                index_hash TEXT,
                chunk_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
            """
        ]

        for query in schema_queries:
            self.db_connection.execute(query)

        # Create some initial indexes
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title)",
            "CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_citations_document_id ON citations(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_citations_year ON citations(publication_year)",
        ]

        for query in index_queries:
            self.db_connection.execute(query)

    def _populate_test_data(self) -> None:
        """Populate database with test data."""
        logger.info(f"Populating test data ({self.test_data_size} records)...")

        # Generate test documents
        document_data = []
        for i in range(self.test_data_size):
            doc_data = (
                f"Test Document {i:05d}",
                f"This is test content for document {i}. " * (i % 10 + 1),  # Varying content size
                f"/test/path/doc_{i:05d}.pdf",
                f"hash_{i:032d}",
                1024 * (i % 100 + 1),  # Varying file sizes
                json.dumps({
                    "category": f"category_{i % 5}",
                    "priority": i % 10,
                    "tags": [f"tag_{j}" for j in range(i % 3 + 1)]
                })
            )
            document_data.append(doc_data)

        # Batch insert documents
        self.db_connection.execute_many("""
            INSERT INTO documents (title, content, file_path, file_hash, file_size, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, document_data)

        # Generate test citations
        citation_data = []
        for i in range(self.test_data_size // 2):  # Fewer citations than documents
            citation_data.append((
                random.randint(1, self.test_data_size),  # Random document_id
                f"Test citation {i} raw text",
                f"Author {i % 100}, Author {(i+1) % 100}",
                f"Citation Title {i}",
                2020 + (i % 4),  # Years 2020-2023
                f"Test Journal {i % 20}",
                f"10.1000/test.{i:06d}",
                random.uniform(0.7, 1.0)  # Confidence scores
            ))

        self.db_connection.execute_many("""
            INSERT INTO citations (document_id, raw_text, authors, title, publication_year, journal, doi, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, citation_data)

        # Generate test vector indexes
        vector_data = []
        for i in range(self.test_data_size // 3):  # Even fewer vector indexes
            vector_data.append((
                random.randint(1, self.test_data_size),
                f"/test/indexes/index_{i:05d}",
                f"index_hash_{i:032d}",
                random.randint(5, 50)  # Chunk count
            ))

        self.db_connection.execute_many("""
            INSERT INTO vector_indexes (document_id, index_path, index_hash, chunk_count)
            VALUES (?, ?, ?, ?)
        """, vector_data)

        logger.info("Test data population complete")

    def run_baseline_benchmark(self) -> PerformanceBenchmark:
        """Run baseline performance benchmark without optimizations."""
        logger.info("Running baseline benchmark...")

        baseline = PerformanceBenchmark("baseline")

        # Test queries without optimizations
        test_queries = self._get_test_queries()

        # Warm-up
        for query, params in test_queries[:3]:
            self.db_connection.fetch_all(query, params)

        # Benchmark
        start_time = time.time()
        total_operations = 0

        for _ in range(3):  # 3 rounds
            for query, params in test_queries:
                query_start = time.time()
                results = self.db_connection.fetch_all(query, params)
                execution_time = (time.time() - query_start) * 1000

                baseline.add_execution_time(execution_time)
                total_operations += 1

        # Calculate throughput
        total_time = time.time() - start_time
        baseline.throughput_ops_per_sec = total_operations / total_time
        baseline.cache_hit_rate = 0.0  # No caching in baseline

        logger.info(f"Baseline benchmark complete: {baseline.avg_execution_time:.2f}ms avg, {baseline.throughput_ops_per_sec:.2f} ops/sec")

        self.benchmarks["baseline"] = baseline
        return baseline

    def run_optimized_benchmark(self) -> PerformanceBenchmark:
        """Run benchmark with all B6 optimizations enabled."""
        logger.info("Running optimized benchmark...")

        # Apply optimizations first
        self._apply_optimizations()

        optimized = PerformanceBenchmark("optimized")

        # Test queries with optimizations
        test_queries = self._get_test_queries()

        # Warm-up (populate cache)
        for query, params in test_queries:
            self._execute_optimized_query(query, params)

        # Benchmark
        start_time = time.time()
        total_operations = 0
        cache_hits = 0
        cache_total = 0

        for _ in range(3):  # 3 rounds
            for query, params in test_queries:
                query_start = time.time()
                result = self._execute_optimized_query(query, params)
                execution_time = (time.time() - query_start) * 1000

                optimized.add_execution_time(execution_time)
                total_operations += 1

                # Track cache performance
                cache_total += 1
                if hasattr(result, 'from_cache') and result.from_cache:
                    cache_hits += 1

        # Calculate metrics
        total_time = time.time() - start_time
        optimized.throughput_ops_per_sec = total_operations / total_time
        optimized.cache_hit_rate = (cache_hits / max(cache_total, 1)) * 100

        # Get cache statistics
        if self.cache_manager:
            cache_stats = self.cache_manager.get_statistics()
            optimized.cache_hit_rate = cache_stats.hit_rate

        # Get connection pool efficiency
        if self.connection_pool:
            pool_stats = self.connection_pool.get_statistics()
            optimized.connection_efficiency = pool_stats.pool_efficiency

        logger.info(f"Optimized benchmark complete: {optimized.avg_execution_time:.2f}ms avg, "
                   f"{optimized.throughput_ops_per_sec:.2f} ops/sec, {optimized.cache_hit_rate:.1f}% cache hit rate")

        self.benchmarks["optimized"] = optimized
        return optimized

    def run_concurrent_load_test(self) -> PerformanceBenchmark:
        """Run concurrent load test to validate scalability."""
        logger.info(f"Running concurrent load test with {self.concurrent_users} users...")

        concurrent = PerformanceBenchmark("concurrent_load")

        def user_workload(user_id: int, results: list[float]) -> None:
            """Workload for a single concurrent user."""
            user_times = []
            test_queries = self._get_test_queries()

            end_time = time.time() + self.test_duration_s
            while time.time() < end_time:
                query, params = random.choice(test_queries)

                start_time = time.time()
                try:
                    self._execute_optimized_query(query, params)
                    execution_time = (time.time() - start_time) * 1000
                    user_times.append(execution_time)
                except Exception as e:
                    logger.warning(f"User {user_id} query failed: {e}")

            results.extend(user_times)

        # Run concurrent users
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_users) as executor:
            futures = []
            results_lists = [[] for _ in range(self.concurrent_users)]

            for i in range(self.concurrent_users):
                future = executor.submit(user_workload, i, results_lists[i])
                futures.append(future)

            # Wait for completion
            concurrent.futures.wait(futures)

        # Collect all results
        all_times = []
        total_operations = 0
        for results_list in results_lists:
            all_times.extend(results_list)
            total_operations += len(results_list)

        if all_times:
            concurrent.execution_times = all_times
            concurrent.throughput_ops_per_sec = total_operations / self.test_duration_s

        # Get final cache and connection stats
        if self.cache_manager:
            cache_stats = self.cache_manager.get_statistics()
            concurrent.cache_hit_rate = cache_stats.hit_rate

        if self.connection_pool:
            pool_stats = self.connection_pool.get_statistics()
            concurrent.connection_efficiency = pool_stats.pool_efficiency

        logger.info(f"Concurrent load test complete: {concurrent.avg_execution_time:.2f}ms avg, "
                   f"{concurrent.throughput_ops_per_sec:.2f} ops/sec, {concurrent.cache_hit_rate:.1f}% cache hit rate")

        self.benchmarks["concurrent_load"] = concurrent
        return concurrent

    def _apply_optimizations(self) -> None:
        """Apply all B6 optimizations."""
        logger.info("Applying B6 optimizations...")

        # Analyze and optimize indexes
        if self.index_advisor:
            recommendations = self.index_advisor.generate_recommendations()

            # Apply high-priority index recommendations
            for rec in recommendations:
                if rec.priority in ["critical", "high"]:
                    try:
                        create_statement = rec.get_create_statement()
                        self.db_connection.execute(create_statement)
                        logger.info(f"Applied index optimization: {create_statement}")
                    except Exception as e:
                        logger.warning(f"Failed to apply index recommendation: {e}")

        # Warm up cache with common queries
        if self.cache_manager:
            test_queries = self._get_test_queries()
            for query, params in test_queries[:5]:  # Warm up with first 5 queries
                try:
                    result = self.db_connection.fetch_all(query, params)

                    # Cache result with appropriate tags and TTL
                    self.cache_manager.put(
                        query=query,
                        result=result,
                        parameters=params,
                        ttl_seconds=300,  # 5 minutes
                        tags={'benchmark', 'warm_up'}
                    )
                except Exception as e:
                    logger.debug(f"Cache warm-up failed for query: {e}")

        logger.info("B6 optimizations applied")

    def _execute_optimized_query(self, query: str, params: tuple | None = None) -> Any:
        """Execute query with all optimizations applied."""
        # Try cache first
        if self.cache_manager:
            cached_result = self.cache_manager.get(query, params)
            if cached_result is not None:
                # Mark as from cache for tracking
                cached_result.from_cache = True
                return cached_result

        # Optimize query
        if self.query_optimizer:
            optimization_result = self.query_optimizer.optimize_query(query, params)
            if optimization_result.success and optimization_result.optimized_query != query:
                query = optimization_result.optimized_query

        # Execute query
        start_time = time.time()
        result = self.db_connection.fetch_all(query, params)
        execution_time = (time.time() - start_time) * 1000

        # Record in query analyzer
        if self.query_analyzer:
            self.query_analyzer.record_query_execution(
                query_text=query,
                execution_time_ms=execution_time,
                parameters=params,
                rows_returned=len(result) if result else 0
            )

        # Cache result
        if self.cache_manager and execution_time > 10:  # Cache slow queries
            self.cache_manager.put(
                query=query,
                result=result,
                parameters=params,
                ttl_seconds=300,
                tags={'optimized'}
            )

        result.from_cache = False
        return result

    def _get_test_queries(self) -> list[tuple[str, tuple | None]]:
        """Get list of test queries for benchmarking."""
        return [
            # Simple queries
            ("SELECT COUNT(*) FROM documents", None),
            ("SELECT * FROM documents ORDER BY created_at DESC LIMIT 10", None),
            ("SELECT * FROM documents WHERE file_size > ? LIMIT 20", (50000,)),

            # Search queries
            ("SELECT * FROM documents WHERE title LIKE ? LIMIT 15", ("%Test%",)),
            ("SELECT * FROM documents WHERE file_hash = ?", ("hash_000000000000000000000100",)),

            # Join queries
            ("""SELECT d.title, COUNT(c.id) as citation_count
               FROM documents d
               LEFT JOIN citations c ON d.id = c.document_id
               GROUP BY d.id, d.title
               ORDER BY citation_count DESC
               LIMIT 10""", None),

            ("""SELECT d.*, c.authors, c.title as citation_title
               FROM documents d
               JOIN citations c ON d.id = c.document_id
               WHERE c.publication_year >= ?
               ORDER BY c.confidence_score DESC
               LIMIT 25""", (2022,)),

            # Complex analytical queries
            ("""SELECT
                   c.publication_year,
                   c.journal,
                   COUNT(*) as citation_count,
                   AVG(c.confidence_score) as avg_confidence
               FROM citations c
               JOIN documents d ON c.document_id = d.id
               WHERE c.confidence_score >= ?
               GROUP BY c.publication_year, c.journal
               HAVING citation_count > 1
               ORDER BY c.publication_year DESC, citation_count DESC""", (0.8,)),

            # Vector index queries
            ("""SELECT d.title, vi.chunk_count, vi.index_path
               FROM documents d
               JOIN vector_indexes vi ON d.id = vi.document_id
               WHERE vi.chunk_count > ?
               ORDER BY vi.chunk_count DESC
               LIMIT 20""", (10,)),

            # Metadata queries
            ("""SELECT d.*, json_extract(d.metadata, '$.category') as category
               FROM documents d
               WHERE json_extract(d.metadata, '$.priority') > ?
               ORDER BY json_extract(d.metadata, '$.priority') DESC
               LIMIT 15""", (5,))
        ]

    def validate_10x_improvement(self) -> dict[str, Any]:
        """Validate 10x performance improvement target."""
        logger.info("Validating 10x performance improvement...")

        if "baseline" not in self.benchmarks or "optimized" not in self.benchmarks:
            raise ValueError("Both baseline and optimized benchmarks must be run first")

        baseline = self.benchmarks["baseline"]
        optimized = self.benchmarks["optimized"]

        improvements = optimized.calculate_improvement(baseline)

        validation_results = {
            "target_met": False,
            "improvements": improvements,
            "performance_multiplier": 0.0,
            "details": {}
        }

        # Calculate performance multiplier for execution time
        if baseline.avg_execution_time > 0:
            multiplier = baseline.avg_execution_time / optimized.avg_execution_time
            validation_results["performance_multiplier"] = multiplier

            # Check if 10x improvement achieved
            if multiplier >= 10.0:
                validation_results["target_met"] = True

            validation_results["details"]["execution_time"] = {
                "baseline_ms": baseline.avg_execution_time,
                "optimized_ms": optimized.avg_execution_time,
                "improvement_factor": multiplier,
                "improvement_percent": improvements.get("avg_execution_time", 0)
            }

        # Throughput improvement
        if baseline.throughput_ops_per_sec and optimized.throughput_ops_per_sec:
            throughput_multiplier = optimized.throughput_ops_per_sec / baseline.throughput_ops_per_sec

            validation_results["details"]["throughput"] = {
                "baseline_ops_per_sec": baseline.throughput_ops_per_sec,
                "optimized_ops_per_sec": optimized.throughput_ops_per_sec,
                "improvement_factor": throughput_multiplier,
                "improvement_percent": improvements.get("throughput", 0)
            }

        # Cache effectiveness
        validation_results["details"]["caching"] = {
            "cache_hit_rate": optimized.cache_hit_rate,
            "cache_enabled": self.cache_manager is not None
        }

        # Connection pool efficiency
        validation_results["details"]["connection_pooling"] = {
            "efficiency": optimized.connection_efficiency,
            "pool_enabled": self.connection_pool is not None
        }

        logger.info(f"Performance validation: {multiplier:.1f}x improvement "
                   f"({'TARGET MET' if validation_results['target_met'] else 'TARGET NOT MET'})")

        return validation_results

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        logger.info("Generating performance report...")

        report = {
            "test_configuration": {
                "test_data_size": self.test_data_size,
                "concurrent_users": self.concurrent_users,
                "test_duration_s": self.test_duration_s,
                "b5_integration_enabled": REDIS_AVAILABLE and self.redis_cache is not None
            },
            "benchmarks": {},
            "improvements": {},
            "component_health": {},
            "recommendations": []
        }

        # Add benchmark results
        for name, benchmark in self.benchmarks.items():
            report["benchmarks"][name] = {
                "avg_execution_time_ms": benchmark.avg_execution_time,
                "p95_execution_time_ms": benchmark.p95_execution_time,
                "throughput_ops_per_sec": benchmark.throughput_ops_per_sec,
                "cache_hit_rate": benchmark.cache_hit_rate,
                "connection_efficiency": benchmark.connection_efficiency,
                "total_operations": len(benchmark.execution_times)
            }

        # Calculate improvements
        if "baseline" in self.benchmarks and "optimized" in self.benchmarks:
            improvements = self.benchmarks["optimized"].calculate_improvement(self.benchmarks["baseline"])
            report["improvements"] = improvements

            # Validate 10x target
            validation = self.validate_10x_improvement()
            report["performance_validation"] = validation

        # Component health
        if self.performance_monitor:
            health = self.performance_monitor.get_database_health()
            report["component_health"]["database"] = {
                "overall_score": health.overall_score,
                "status": health.status,
                "connection_health": health.connection_health,
                "query_performance_health": health.query_performance_health,
                "cache_efficiency_health": health.cache_efficiency_health,
                "issues": health.issues,
                "recommendations": health.recommendations
            }

        if self.query_analyzer:
            query_summary = self.query_analyzer.get_performance_summary(time_window_hours=1)
            report["component_health"]["query_analyzer"] = query_summary

        if self.cache_manager:
            cache_stats = self.cache_manager.get_statistics()
            report["component_health"]["cache_manager"] = cache_stats.__dict__

        # Generate recommendations
        recommendations = []

        if "performance_validation" in report and not report["performance_validation"]["target_met"]:
            multiplier = report["performance_validation"]["performance_multiplier"]
            recommendations.append(f"Performance improvement of {multiplier:.1f}x achieved, but 10x target not met")
            recommendations.append("Consider additional optimizations: more aggressive caching, query rewriting, or hardware upgrades")

        if report["component_health"].get("database", {}).get("overall_score", 0) < 80:
            recommendations.append("Database health score below 80 - review performance issues and apply recommended fixes")

        if self.cache_manager and report["benchmarks"].get("optimized", {}).get("cache_hit_rate", 0) < 70:
            recommendations.append("Cache hit rate below 70% - review cache configuration and TTL settings")

        report["recommendations"] = recommendations

        return report

    def cleanup(self) -> None:
        """Clean up test resources."""
        logger.info("Cleaning up B6 integration test...")

        try:
            if self.performance_monitor:
                self.performance_monitor.shutdown()

            if self.cache_manager:
                self.cache_manager.shutdown()

            if self.connection_pool:
                self.connection_pool.shutdown()

            if self.db_connection:
                self.db_connection.close_all_connections()

            if hasattr(self, 'test_db_path') and Path(self.test_db_path).exists():
                Path(self.test_db_path).unlink()
                logger.info("Test database cleaned up")

        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


# Pytest fixtures and tests
@pytest.fixture
def b6_test_suite():
    """Fixture for B6 integration test suite."""
    suite = B6PerformanceIntegrationTest()
    suite.setup()
    yield suite
    suite.cleanup()


def test_b6_baseline_benchmark(b6_test_suite):
    """Test baseline performance benchmark."""
    baseline = b6_test_suite.run_baseline_benchmark()

    assert baseline.avg_execution_time > 0
    assert baseline.throughput_ops_per_sec > 0
    assert len(baseline.execution_times) > 0


def test_b6_optimized_benchmark(b6_test_suite):
    """Test optimized performance benchmark."""
    # Run baseline first
    b6_test_suite.run_baseline_benchmark()

    # Run optimized
    optimized = b6_test_suite.run_optimized_benchmark()

    assert optimized.avg_execution_time > 0
    assert optimized.throughput_ops_per_sec > 0
    assert len(optimized.execution_times) > 0

    # Should have some cache hits
    if b6_test_suite.cache_manager:
        assert optimized.cache_hit_rate >= 0


def test_b6_concurrent_load(b6_test_suite):
    """Test concurrent load performance."""
    # Setup optimizations first
    b6_test_suite._apply_optimizations()

    # Run concurrent load test
    concurrent = b6_test_suite.run_concurrent_load_test()

    assert concurrent.avg_execution_time > 0
    assert concurrent.throughput_ops_per_sec > 0
    assert len(concurrent.execution_times) > 0


def test_b6_performance_improvement(b6_test_suite):
    """Test performance improvement validation."""
    # Run both benchmarks
    b6_test_suite.run_baseline_benchmark()
    b6_test_suite.run_optimized_benchmark()

    # Validate improvement
    validation = b6_test_suite.validate_10x_improvement()

    assert "target_met" in validation
    assert "performance_multiplier" in validation
    assert validation["performance_multiplier"] > 1.0  # Should be some improvement
    assert "improvements" in validation
    assert "details" in validation


def test_b6_integration_report(b6_test_suite):
    """Test comprehensive performance report generation."""
    # Run all benchmarks
    b6_test_suite.run_baseline_benchmark()
    b6_test_suite.run_optimized_benchmark()
    b6_test_suite.run_concurrent_load_test()

    # Generate report
    report = b6_test_suite.generate_performance_report()

    assert "test_configuration" in report
    assert "benchmarks" in report
    assert "improvements" in report
    assert "component_health" in report
    assert "recommendations" in report

    # Should have all benchmark types
    assert "baseline" in report["benchmarks"]
    assert "optimized" in report["benchmarks"]
    assert "concurrent_load" in report["benchmarks"]


if __name__ == "__main__":
    # Run integration test as standalone script
    import json

    logger.info("Starting B6 Database Performance Integration Test")

    test_suite = B6PerformanceIntegrationTest()

    try:
        test_suite.setup()

        # Run all benchmarks
        logger.info("=== BASELINE BENCHMARK ===")
        test_suite.run_baseline_benchmark()

        logger.info("=== OPTIMIZED BENCHMARK ===")
        test_suite.run_optimized_benchmark()

        logger.info("=== CONCURRENT LOAD TEST ===")
        test_suite.run_concurrent_load_test()

        # Generate and display report
        logger.info("=== PERFORMANCE REPORT ===")
        report = test_suite.generate_performance_report()

        print("\n" + "="*80)
        print("B6 DATABASE PERFORMANCE INTEGRATION TEST RESULTS")
        print("="*80)

        print("\nTest Configuration:")
        config = report["test_configuration"]
        print(f"  Test Data Size: {config['test_data_size']:,} records")
        print(f"  Concurrent Users: {config['concurrent_users']}")
        print(f"  Test Duration: {config['test_duration_s']}s")
        print(f"  B5 Integration: {'Enabled' if config['b5_integration_enabled'] else 'Disabled'}")

        print("\nBenchmark Results:")
        for bench_name, bench_data in report["benchmarks"].items():
            print(f"  {bench_name.upper()}:")
            print(f"    Avg Execution Time: {bench_data['avg_execution_time_ms']:.2f}ms")
            print(f"    P95 Execution Time: {bench_data['p95_execution_time_ms']:.2f}ms")
            print(f"    Throughput: {bench_data['throughput_ops_per_sec']:.2f} ops/sec")
            if bench_data['cache_hit_rate'] is not None:
                print(f"    Cache Hit Rate: {bench_data['cache_hit_rate']:.1f}%")
            print()

        if "performance_validation" in report:
            validation = report["performance_validation"]
            print("Performance Improvement Validation:")
            print(f"  10x Target Met: {'YES' if validation['target_met'] else 'NO'}")
            print(f"  Actual Improvement: {validation['performance_multiplier']:.1f}x")
            print()

        if report["recommendations"]:
            print("Recommendations:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")

        print("\n" + "="*80)

        # Save detailed report
        report_file = "b6_performance_integration_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Detailed report saved to {report_file}")

    finally:
        test_suite.cleanup()

    logger.info("B6 Integration Test Complete")
