"""
Performance Regression Testing Suite
Validates performance benchmarks and detects performance regressions
against baseline performance metrics established for production readiness.
"""

import asyncio
import json
import logging
import os
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import psutil

import pytest
import httpx
from fastapi.testclient import TestClient

# Import application components
from backend.api.main import app
from tests.performance.base_performance import PerformanceTestBase, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class PerformanceBenchmark:
    """Performance benchmark definition."""
    name: str
    description: str
    test_function: str
    baseline_response_time_ms: float
    baseline_throughput_rps: float
    baseline_memory_mb: float
    max_acceptable_degradation_percent: float = 20.0
    critical_threshold_percent: float = 50.0


@dataclass
class RegressionTestResult:
    """Result of a performance regression test."""
    benchmark_name: str
    current_performance: PerformanceMetrics
    baseline_performance: Dict[str, float]
    response_time_change_percent: float
    throughput_change_percent: float
    memory_change_percent: float
    performance_degraded: bool
    critical_regression: bool
    passed: bool
    error_message: Optional[str] = None


class PerformanceRegressionTestSuite(PerformanceTestBase):
    """
    Performance regression testing suite that validates current performance
    against established baselines and detects performance degradations.
    """

    def __init__(self):
        """Initialize performance regression test suite."""
        super().__init__()
        self.client = TestClient(app)
        self.regression_results = []

        # Define performance benchmarks based on production requirements
        self.benchmarks = self._define_performance_benchmarks()

        # Load baseline performance data
        self.baseline_data = self._load_baseline_performance()

    def _define_performance_benchmarks(self) -> List[PerformanceBenchmark]:
        """Define performance benchmarks for regression testing."""
        return [
            PerformanceBenchmark(
                name="api_health_check",
                description="Health check endpoint response time",
                test_function="test_health_check_performance",
                baseline_response_time_ms=50.0,  # <50ms response
                baseline_throughput_rps=2000.0,  # >2000 requests/sec
                baseline_memory_mb=100.0,  # <100MB memory usage
                max_acceptable_degradation_percent=20.0
            ),
            PerformanceBenchmark(
                name="document_upload",
                description="Document upload processing time",
                test_function="test_document_upload_performance",
                baseline_response_time_ms=200.0,  # <200ms for small doc
                baseline_throughput_rps=100.0,  # >100 uploads/sec
                baseline_memory_mb=150.0,  # <150MB memory usage
                max_acceptable_degradation_percent=25.0
            ),
            PerformanceBenchmark(
                name="rag_query",
                description="RAG query processing time",
                test_function="test_rag_query_performance",
                baseline_response_time_ms=500.0,  # <500ms response
                baseline_throughput_rps=50.0,  # >50 queries/sec
                baseline_memory_mb=200.0,  # <200MB memory usage
                max_acceptable_degradation_percent=30.0
            ),
            PerformanceBenchmark(
                name="document_library_search",
                description="Document library search performance",
                test_function="test_library_search_performance",
                baseline_response_time_ms=150.0,  # <150ms response
                baseline_throughput_rps=200.0,  # >200 searches/sec
                baseline_memory_mb=120.0,  # <120MB memory usage
                max_acceptable_degradation_percent=20.0
            ),
            PerformanceBenchmark(
                name="concurrent_user_simulation",
                description="100 concurrent users performance",
                test_function="test_concurrent_users_performance",
                baseline_response_time_ms=300.0,  # <300ms under load
                baseline_throughput_rps=500.0,  # >500 total RPS
                baseline_memory_mb=400.0,  # <400MB under load
                max_acceptable_degradation_percent=25.0,
                critical_threshold_percent=40.0
            ),
            PerformanceBenchmark(
                name="database_query_performance",
                description="Database query response time",
                test_function="test_database_query_performance",
                baseline_response_time_ms=20.0,  # <20ms for simple queries
                baseline_throughput_rps=1000.0,  # >1000 queries/sec
                baseline_memory_mb=80.0,  # <80MB memory usage
                max_acceptable_degradation_percent=15.0
            ),
            PerformanceBenchmark(
                name="cache_performance",
                description="Redis cache operation performance",
                test_function="test_cache_performance",
                baseline_response_time_ms=5.0,  # <5ms cache operations
                baseline_throughput_rps=5000.0,  # >5000 operations/sec
                baseline_memory_mb=60.0,  # <60MB memory usage
                max_acceptable_degradation_percent=15.0
            )
        ]

    def _load_baseline_performance(self) -> Dict[str, Dict[str, float]]:
        """Load baseline performance data from previous test runs."""
        baseline_file = "performance_results/performance_baselines.json"

        if os.path.exists(baseline_file):
            with open(baseline_file, 'r') as f:
                return json.load(f)

        # If no baseline exists, use the benchmark definitions as baseline
        logger.warning("No baseline performance data found, using benchmark definitions")
        return {
            benchmark.name: {
                "response_time_ms": benchmark.baseline_response_time_ms,
                "throughput_rps": benchmark.baseline_throughput_rps,
                "memory_mb": benchmark.baseline_memory_mb
            }
            for benchmark in self.benchmarks
        }

    async def test_health_check_performance(self) -> PerformanceMetrics:
        """Test health check endpoint performance."""
        logger.info("Testing health check performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Measure response time
        response_times = []
        for _ in range(100):  # 100 requests for average
            start_time = time.time()
            response = self.client.get("/api/system/health")
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)

            assert response.status_code == 200, f"Health check failed: {response.status_code}"

        # Measure throughput
        throughput_start = time.time()
        successful_requests = 0

        for _ in range(1000):  # 1000 requests for throughput
            try:
                response = self.client.get("/api/system/health")
                if response.status_code == 200:
                    successful_requests += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = successful_requests / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        return PerformanceMetrics(
            response_time_avg=statistics.mean(response_times),
            response_time_p95=statistics.quantiles(response_times, n=20)[18],
            response_time_p99=statistics.quantiles(response_times, n=100)[98],
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=0.0,
            total_requests=successful_requests
        )

    async def test_document_upload_performance(self) -> PerformanceMetrics:
        """Test document upload performance."""
        logger.info("Testing document upload performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Create test document content
        test_content = "Test PDF content for performance testing. " * 100  # Small document

        response_times = []
        successful_uploads = 0

        # Test upload response times
        for i in range(50):  # 50 uploads for average
            files = {"file": (f"test_{i}.pdf", test_content.encode(), "application/pdf")}

            start_time = time.time()
            try:
                response = self.client.post("/api/documents/upload", files=files)
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if response.status_code < 400:
                    successful_uploads += 1
            except Exception as e:
                logger.warning(f"Upload failed: {e}")

        # Measure throughput
        throughput_start = time.time()
        throughput_uploads = 0

        for i in range(100):
            files = {"file": (f"perf_test_{i}.pdf", test_content.encode(), "application/pdf")}
            try:
                response = self.client.post("/api/documents/upload", files=files)
                if response.status_code < 400:
                    throughput_uploads += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = throughput_uploads / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        error_rate = ((50 - successful_uploads) / 50) * 100 if response_times else 100

        return PerformanceMetrics(
            response_time_avg=statistics.mean(response_times) if response_times else 0,
            response_time_p95=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0,
            response_time_p99=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=successful_uploads
        )

    async def test_rag_query_performance(self) -> PerformanceMetrics:
        """Test RAG query performance."""
        logger.info("Testing RAG query performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        test_queries = [
            "What is the main topic of the document?",
            "Summarize the key findings",
            "What are the conclusions?",
            "List the main sections",
            "What methodology was used?"
        ]

        response_times = []
        successful_queries = 0

        # Test query response times
        for query in test_queries * 10:  # 50 queries total
            start_time = time.time()
            try:
                response = self.client.post("/api/rag/query", json={"query": query})
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if response.status_code < 400:
                    successful_queries += 1
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")

        # Measure throughput
        throughput_start = time.time()
        throughput_queries = 0

        for query in test_queries * 20:  # 100 queries for throughput
            try:
                response = self.client.post("/api/rag/query", json={"query": query})
                if response.status_code < 400:
                    throughput_queries += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = throughput_queries / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        error_rate = ((50 - successful_queries) / 50) * 100 if response_times else 100

        return PerformanceMetrics(
            response_time_avg=statistics.mean(response_times) if response_times else 0,
            response_time_p95=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0,
            response_time_p99=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=successful_queries
        )

    async def test_library_search_performance(self) -> PerformanceMetrics:
        """Test document library search performance."""
        logger.info("Testing library search performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        search_queries = [
            "machine learning",
            "data science",
            "artificial intelligence",
            "neural networks",
            "deep learning"
        ]

        response_times = []
        successful_searches = 0

        # Test search response times
        for query in search_queries * 10:  # 50 searches total
            start_time = time.time()
            try:
                response = self.client.get("/api/library/documents", params={"search": query})
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if response.status_code < 400:
                    successful_searches += 1
            except Exception as e:
                logger.warning(f"Library search failed: {e}")

        # Measure throughput
        throughput_start = time.time()
        throughput_searches = 0

        for query in search_queries * 40:  # 200 searches for throughput
            try:
                response = self.client.get("/api/library/documents", params={"search": query})
                if response.status_code < 400:
                    throughput_searches += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = throughput_searches / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        error_rate = ((50 - successful_searches) / 50) * 100 if response_times else 100

        return PerformanceMetrics(
            response_time_avg=statistics.mean(response_times) if response_times else 0,
            response_time_p95=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0,
            response_time_p99=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=successful_searches
        )

    async def test_concurrent_users_performance(self) -> PerformanceMetrics:
        """Test performance under concurrent user load."""
        logger.info("Testing concurrent users performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        async def simulate_user_requests():
            """Simulate a single user making requests."""
            response_times = []
            successful_requests = 0

            # Each user makes 10 requests
            for _ in range(10):
                start_time = time.time()
                try:
                    response = self.client.get("/api/system/health")
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)

                    if response.status_code == 200:
                        successful_requests += 1

                    await asyncio.sleep(0.1)  # Small delay between requests
                except Exception:
                    pass

            return response_times, successful_requests

        # Simulate 100 concurrent users
        concurrent_users = 100
        user_tasks = [simulate_user_requests() for _ in range(concurrent_users)]

        start_time = time.time()
        user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
        total_duration = time.time() - start_time

        # Aggregate results
        all_response_times = []
        total_successful_requests = 0

        for result in user_results:
            if isinstance(result, tuple):
                response_times, successful_requests = result
                all_response_times.extend(response_times)
                total_successful_requests += successful_requests

        throughput_rps = total_successful_requests / total_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        total_expected_requests = concurrent_users * 10
        error_rate = ((total_expected_requests - total_successful_requests) / total_expected_requests) * 100

        return PerformanceMetrics(
            response_time_avg=statistics.mean(all_response_times) if all_response_times else 0,
            response_time_p95=statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else 0,
            response_time_p99=statistics.quantiles(all_response_times, n=100)[98] if len(all_response_times) >= 100 else 0,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=total_successful_requests
        )

    async def test_database_query_performance(self) -> PerformanceMetrics:
        """Test database query performance."""
        logger.info("Testing database query performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Simulate database queries through API endpoints
        response_times = []
        successful_queries = 0

        # Test various endpoints that involve database queries
        endpoints = [
            "/api/documents",
            "/api/library/documents",
            "/api/system/health"
        ]

        for _ in range(100):  # 100 queries for average
            endpoint = endpoints[successful_queries % len(endpoints)]

            start_time = time.time()
            try:
                response = self.client.get(endpoint)
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if response.status_code < 400:
                    successful_queries += 1
            except Exception:
                pass

        # Measure throughput
        throughput_start = time.time()
        throughput_queries = 0

        for _ in range(1000):  # 1000 queries for throughput
            endpoint = endpoints[throughput_queries % len(endpoints)]
            try:
                response = self.client.get(endpoint)
                if response.status_code < 400:
                    throughput_queries += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = throughput_queries / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        error_rate = ((100 - successful_queries) / 100) * 100 if response_times else 100

        return PerformanceMetrics(
            response_time_avg=statistics.mean(response_times) if response_times else 0,
            response_time_p95=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0,
            response_time_p99=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=successful_queries
        )

    async def test_cache_performance(self) -> PerformanceMetrics:
        """Test cache performance."""
        logger.info("Testing cache performance")

        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Test cache performance through repeated identical queries
        # (should hit cache after first request)
        cache_query = "test cache performance query"

        response_times = []
        successful_requests = 0

        # First request (cache miss)
        start_time = time.time()
        try:
            response = self.client.post("/api/rag/query", json={"query": cache_query})
            first_response_time = (time.time() - start_time) * 1000

            if response.status_code < 400:
                successful_requests += 1
        except Exception:
            first_response_time = 1000  # Default high value if fails

        # Subsequent requests (should be cache hits)
        for _ in range(100):
            start_time = time.time()
            try:
                response = self.client.post("/api/rag/query", json={"query": cache_query})
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)

                if response.status_code < 400:
                    successful_requests += 1
            except Exception:
                pass

        # Measure cache throughput
        throughput_start = time.time()
        throughput_requests = 0

        for _ in range(1000):  # High volume for cache throughput
            try:
                response = self.client.post("/api/rag/query", json={"query": cache_query})
                if response.status_code < 400:
                    throughput_requests += 1
            except Exception:
                pass

        throughput_duration = time.time() - throughput_start
        throughput_rps = throughput_requests / throughput_duration

        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_usage = end_memory - start_memory

        error_rate = ((101 - successful_requests) / 101) * 100 if response_times else 100

        # Cache should make subsequent requests much faster
        avg_cache_response_time = statistics.mean(response_times) if response_times else first_response_time

        return PerformanceMetrics(
            response_time_avg=avg_cache_response_time,
            response_time_p95=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_cache_response_time,
            response_time_p99=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_cache_response_time,
            throughput_rps=throughput_rps,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=psutil.cpu_percent(),
            error_rate=error_rate,
            total_requests=successful_requests
        )

    async def run_regression_test(self, benchmark: PerformanceBenchmark) -> RegressionTestResult:
        """Run a specific performance regression test."""
        logger.info(f"Running regression test: {benchmark.name}")

        try:
            # Get the test function by name and execute it
            test_method = getattr(self, benchmark.test_function)
            current_metrics = await test_method()

            # Get baseline performance data
            baseline = self.baseline_data.get(benchmark.name, {
                "response_time_ms": benchmark.baseline_response_time_ms,
                "throughput_rps": benchmark.baseline_throughput_rps,
                "memory_mb": benchmark.baseline_memory_mb
            })

            # Calculate performance changes
            response_time_change = (
                (current_metrics.response_time_avg - baseline["response_time_ms"]) /
                baseline["response_time_ms"] * 100
            )

            throughput_change = (
                (current_metrics.throughput_rps - baseline["throughput_rps"]) /
                baseline["throughput_rps"] * 100
            )

            memory_change = (
                (current_metrics.memory_usage_mb - baseline["memory_mb"]) /
                baseline["memory_mb"] * 100
            )

            # Determine if performance degraded
            performance_degraded = (
                response_time_change > benchmark.max_acceptable_degradation_percent or
                throughput_change < -benchmark.max_acceptable_degradation_percent or
                memory_change > benchmark.max_acceptable_degradation_percent
            )

            # Determine if this is a critical regression
            critical_regression = (
                response_time_change > benchmark.critical_threshold_percent or
                throughput_change < -benchmark.critical_threshold_percent or
                memory_change > benchmark.critical_threshold_percent
            )

            # Test passes if performance is acceptable
            passed = not critical_regression

            result = RegressionTestResult(
                benchmark_name=benchmark.name,
                current_performance=current_metrics,
                baseline_performance=baseline,
                response_time_change_percent=response_time_change,
                throughput_change_percent=throughput_change,
                memory_change_percent=memory_change,
                performance_degraded=performance_degraded,
                critical_regression=critical_regression,
                passed=passed
            )

            logger.info(f"Regression test {benchmark.name}: {'PASSED' if passed else 'FAILED'}")
            if performance_degraded:
                logger.warning(f"Performance degradation detected in {benchmark.name}")
                logger.warning(f"Response time change: {response_time_change:+.1f}%")
                logger.warning(f"Throughput change: {throughput_change:+.1f}%")
                logger.warning(f"Memory change: {memory_change:+.1f}%")

            return result

        except Exception as e:
            logger.error(f"Regression test {benchmark.name} failed with error: {e}")
            return RegressionTestResult(
                benchmark_name=benchmark.name,
                current_performance=PerformanceMetrics(),
                baseline_performance={},
                response_time_change_percent=0.0,
                throughput_change_percent=0.0,
                memory_change_percent=0.0,
                performance_degraded=True,
                critical_regression=True,
                passed=False,
                error_message=str(e)
            )

    async def run_all_regression_tests(self) -> Dict[str, Any]:
        """Run all performance regression tests."""
        logger.info("Starting comprehensive performance regression testing")

        test_start_time = time.time()
        regression_results = []

        # Run each benchmark test
        for benchmark in self.benchmarks:
            result = await self.run_regression_test(benchmark)
            regression_results.append(result)

        # Calculate summary statistics
        total_tests = len(regression_results)
        passed_tests = len([r for r in regression_results if r.passed])
        degraded_tests = len([r for r in regression_results if r.performance_degraded])
        critical_regressions = len([r for r in regression_results if r.critical_regression])

        # Calculate overall performance score
        performance_score = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        test_summary = {
            "performance_regression_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "degraded_tests": degraded_tests,
                "critical_regressions": critical_regressions,
                "performance_score": performance_score,
                "test_duration_seconds": time.time() - test_start_time,
                "test_timestamp": datetime.utcnow().isoformat(),
                "baseline_data_source": "loaded" if os.path.exists("performance_results/performance_baselines.json") else "benchmark_definitions"
            },
            "detailed_results": [
                {
                    "benchmark_name": r.benchmark_name,
                    "passed": r.passed,
                    "performance_degraded": r.performance_degraded,
                    "critical_regression": r.critical_regression,
                    "response_time_change_percent": r.response_time_change_percent,
                    "throughput_change_percent": r.throughput_change_percent,
                    "memory_change_percent": r.memory_change_percent,
                    "current_response_time_ms": r.current_performance.response_time_avg,
                    "current_throughput_rps": r.current_performance.throughput_rps,
                    "current_memory_mb": r.current_performance.memory_usage_mb,
                    "baseline_response_time_ms": r.baseline_performance.get("response_time_ms", 0),
                    "baseline_throughput_rps": r.baseline_performance.get("throughput_rps", 0),
                    "baseline_memory_mb": r.baseline_performance.get("memory_mb", 0),
                    "error_message": r.error_message
                }
                for r in regression_results
            ]
        }

        return test_summary

    def update_performance_baselines(self, results: Dict[str, Any]):
        """Update performance baselines with current test results."""
        logger.info("Updating performance baselines")

        new_baselines = {}

        for result in results["detailed_results"]:
            if result["passed"] and not result["performance_degraded"]:
                # Update baseline with better performance
                benchmark_name = result["benchmark_name"]
                new_baselines[benchmark_name] = {
                    "response_time_ms": result["current_response_time_ms"],
                    "throughput_rps": result["current_throughput_rps"],
                    "memory_mb": result["current_memory_mb"],
                    "last_updated": datetime.utcnow().isoformat()
                }

        # Save updated baselines
        baseline_file = "performance_results/performance_baselines.json"
        os.makedirs(os.path.dirname(baseline_file), exist_ok=True)

        with open(baseline_file, 'w') as f:
            json.dump(new_baselines, f, indent=2)

        logger.info(f"Updated {len(new_baselines)} performance baselines")


@pytest.mark.asyncio
@pytest.mark.performance
class TestPerformanceRegression:
    """Performance regression testing."""

    @pytest.fixture(autouse=True)
    async def setup_regression_test(self):
        """Set up performance regression testing environment."""
        self.test_suite = PerformanceRegressionTestSuite()
        yield

    async def test_api_health_check_regression(self):
        """Test API health check performance regression."""
        benchmark = next(b for b in self.test_suite.benchmarks if b.name == "api_health_check")
        result = await self.test_suite.run_regression_test(benchmark)

        # Health check should not have critical regressions
        assert not result.critical_regression, f"Critical regression in health check: {result.error_message}"
        assert result.current_performance.response_time_avg < 100, f"Health check too slow: {result.current_performance.response_time_avg}ms"

        logger.info("API health check regression test PASSED")

    async def test_document_upload_regression(self):
        """Test document upload performance regression."""
        benchmark = next(b for b in self.test_suite.benchmarks if b.name == "document_upload")
        result = await self.test_suite.run_regression_test(benchmark)

        # Document upload should maintain acceptable performance
        assert not result.critical_regression, f"Critical regression in document upload: {result.error_message}"

        logger.info("Document upload regression test PASSED")

    async def test_rag_query_regression(self):
        """Test RAG query performance regression."""
        benchmark = next(b for b in self.test_suite.benchmarks if b.name == "rag_query")
        result = await self.test_suite.run_regression_test(benchmark)

        # RAG queries should maintain acceptable performance
        assert not result.critical_regression, f"Critical regression in RAG query: {result.error_message}"

        logger.info("RAG query regression test PASSED")

    async def test_concurrent_users_regression(self):
        """Test concurrent users performance regression."""
        benchmark = next(b for b in self.test_suite.benchmarks if b.name == "concurrent_user_simulation")
        result = await self.test_suite.run_regression_test(benchmark)

        # Concurrent user performance should not critically degrade
        assert not result.critical_regression, f"Critical regression in concurrent users: {result.error_message}"
        assert result.current_performance.error_rate < 10, f"High error rate under load: {result.current_performance.error_rate}%"

        logger.info("Concurrent users regression test PASSED")


@pytest.mark.asyncio
async def test_complete_performance_regression():
    """Run complete performance regression test suite."""
    logger.info("Starting complete performance regression testing")

    # Initialize test suite
    test_suite = PerformanceRegressionTestSuite()

    # Run all regression tests
    results = await test_suite.run_all_regression_tests()

    # Save detailed results
    results_file = "performance_results/performance_regression_results.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Validate results
    summary = results["performance_regression_summary"]

    # Require >80% performance score (allow some degradation)
    assert summary["performance_score"] >= 80.0, f"Performance score too low: {summary['performance_score']:.1f}%"

    # No critical regressions allowed
    assert summary["critical_regressions"] == 0, f"Critical performance regressions found: {summary['critical_regressions']}"

    # Update baselines if all tests passed
    if summary["performance_score"] >= 90.0:
        test_suite.update_performance_baselines(results)

    logger.info(f"Complete performance regression testing PASSED")
    logger.info(f"Performance score: {summary['performance_score']:.1f}%")
    logger.info(f"Tests passed: {summary['passed_tests']}/{summary['total_tests']}")
    logger.info(f"Performance degraded: {summary['degraded_tests']}")
    logger.info(f"Critical regressions: {summary['critical_regressions']}")
    logger.info(f"Results saved to: {results_file}")

    return results


if __name__ == "__main__":
    """Run performance regression tests standalone."""
    import asyncio

    async def main():
        results = await test_complete_performance_regression()
        print(f"Performance Score: {results['performance_regression_summary']['performance_score']:.1f}%")
        return results

    asyncio.run(main())