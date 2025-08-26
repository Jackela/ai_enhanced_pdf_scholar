"""
API Performance Benchmarking Module

Establishes and validates performance baselines for all API endpoints:
- Response time benchmarks
- Throughput measurements
- Latency distribution analysis
- Performance regression detection
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
import pytest

from .base_performance import PerformanceTestBase
from .metrics_collector import MetricsCollector


@dataclass
class APIEndpointBenchmark:
    """Benchmark configuration for an API endpoint"""
    name: str
    method: str
    path: str
    payload: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    expected_response_time_ms: float = 1000.0
    expected_p95_ms: float = 2000.0
    expected_p99_ms: float = 3000.0
    iterations: int = 100
    warmup_iterations: int = 10

    # Performance baselines
    baseline_response_time_ms: float | None = None
    baseline_p95_ms: float | None = None
    baseline_p99_ms: float | None = None
    baseline_throughput_rps: float | None = None


class APIBenchmarkTest(PerformanceTestBase):
    """API endpoint performance benchmarking"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__(base_url)
        self.collector = MetricsCollector(storage_path=Path("api_benchmarks.db"))
        self.endpoints = self._define_endpoints()
        self.baselines: dict[str, dict[str, float]] = {}

    def _define_endpoints(self) -> list[APIEndpointBenchmark]:
        """Define API endpoints to benchmark"""
        return [
            # Health check
            APIEndpointBenchmark(
                name="Health Check",
                method="GET",
                path="/health",
                expected_response_time_ms=50,
                expected_p95_ms=100,
                expected_p99_ms=200
            ),

            # Document operations
            APIEndpointBenchmark(
                name="List Documents",
                method="GET",
                path="/api/documents",
                expected_response_time_ms=200,
                expected_p95_ms=500,
                expected_p99_ms=1000
            ),

            APIEndpointBenchmark(
                name="Get Document",
                method="GET",
                path="/api/documents/1",
                expected_response_time_ms=150,
                expected_p95_ms=300,
                expected_p99_ms=500
            ),

            APIEndpointBenchmark(
                name="Create Document Metadata",
                method="POST",
                path="/api/documents/metadata",
                payload={
                    "title": "Test Document",
                    "author": "Test Author",
                    "tags": ["test", "benchmark"]
                },
                expected_response_time_ms=300,
                expected_p95_ms=600,
                expected_p99_ms=1000
            ),

            # RAG operations
            APIEndpointBenchmark(
                name="Simple RAG Query",
                method="POST",
                path="/api/rag/query",
                payload={
                    "query": "machine learning",
                    "k": 5
                },
                expected_response_time_ms=1000,
                expected_p95_ms=2000,
                expected_p99_ms=3000
            ),

            APIEndpointBenchmark(
                name="Complex RAG Query",
                method="POST",
                path="/api/rag/query",
                payload={
                    "query": "explain the relationship between neural networks and deep learning in modern AI applications",
                    "k": 10,
                    "rerank": True
                },
                expected_response_time_ms=2000,
                expected_p95_ms=4000,
                expected_p99_ms=6000
            ),

            # Citation operations
            APIEndpointBenchmark(
                name="List Citations",
                method="GET",
                path="/api/citations",
                expected_response_time_ms=200,
                expected_p95_ms=400,
                expected_p99_ms=600
            ),

            APIEndpointBenchmark(
                name="Search Citations",
                method="GET",
                path="/api/citations/search?q=neural",
                expected_response_time_ms=500,
                expected_p95_ms=1000,
                expected_p99_ms=1500
            ),

            # Vector operations
            APIEndpointBenchmark(
                name="Vector Search",
                method="POST",
                path="/api/vectors/search",
                payload={
                    "query": "artificial intelligence",
                    "top_k": 10
                },
                expected_response_time_ms=800,
                expected_p95_ms=1500,
                expected_p99_ms=2500
            ),

            # Session operations
            APIEndpointBenchmark(
                name="Create Session",
                method="POST",
                path="/api/sessions",
                payload={
                    "user_id": "test_user"
                },
                expected_response_time_ms=100,
                expected_p95_ms=200,
                expected_p99_ms=300
            )
        ]

    async def benchmark_endpoint(
        self,
        endpoint: APIEndpointBenchmark,
        session: aiohttp.ClientSession | None = None
    ) -> dict[str, Any]:
        """Benchmark a single API endpoint"""

        # Create session if not provided
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True
        else:
            close_session = False

        try:
            response_times = []
            errors = 0

            # Warmup
            for _ in range(endpoint.warmup_iterations):
                try:
                    await self._make_request(session, endpoint)
                except:
                    pass  # Ignore warmup errors

            # Actual benchmark
            start_time = time.perf_counter()

            for _ in range(endpoint.iterations):
                try:
                    request_start = time.perf_counter()
                    await self._make_request(session, endpoint)
                    response_time = (time.perf_counter() - request_start) * 1000
                    response_times.append(response_time)
                except Exception as e:
                    errors += 1
                    print(f"Request error: {e}")

            total_time = time.perf_counter() - start_time

            # Calculate metrics
            if response_times:
                metrics = {
                    "endpoint": endpoint.name,
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "iterations": endpoint.iterations,
                    "errors": errors,
                    "error_rate": (errors / endpoint.iterations) * 100,
                    "total_time_seconds": total_time,
                    "throughput_rps": len(response_times) / total_time,
                    "response_times": {
                        "mean": statistics.mean(response_times),
                        "median": statistics.median(response_times),
                        "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                        "min": min(response_times),
                        "max": max(response_times),
                        "p50": np.percentile(response_times, 50),
                        "p75": np.percentile(response_times, 75),
                        "p90": np.percentile(response_times, 90),
                        "p95": np.percentile(response_times, 95),
                        "p99": np.percentile(response_times, 99)
                    }
                }

                # Check against expected performance
                metrics["performance_status"] = self._check_performance(endpoint, metrics)

                return metrics
            else:
                return {
                    "endpoint": endpoint.name,
                    "error": "No successful requests",
                    "errors": errors
                }

        finally:
            if close_session:
                await session.close()

    async def _make_request(
        self,
        session: aiohttp.ClientSession,
        endpoint: APIEndpointBenchmark
    ) -> aiohttp.ClientResponse:
        """Make HTTP request to endpoint"""
        url = f"{self.base_url}{endpoint.path}"

        kwargs = {}
        if endpoint.headers:
            kwargs["headers"] = endpoint.headers
        if endpoint.payload and endpoint.method in ["POST", "PUT", "PATCH"]:
            kwargs["json"] = endpoint.payload

        async with session.request(endpoint.method, url, **kwargs) as response:
            await response.read()  # Ensure response is fully read
            response.raise_for_status()
            return response

    def _check_performance(
        self,
        endpoint: APIEndpointBenchmark,
        metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Check if performance meets expectations"""
        status = {
            "meets_expectations": True,
            "warnings": [],
            "failures": []
        }

        response_times = metrics["response_times"]

        # Check mean response time
        if response_times["mean"] > endpoint.expected_response_time_ms:
            status["warnings"].append(
                f"Mean response time ({response_times['mean']:.2f}ms) "
                f"exceeds expectation ({endpoint.expected_response_time_ms}ms)"
            )
            status["meets_expectations"] = False

        # Check P95
        if response_times["p95"] > endpoint.expected_p95_ms:
            status["warnings"].append(
                f"P95 ({response_times['p95']:.2f}ms) "
                f"exceeds expectation ({endpoint.expected_p95_ms}ms)"
            )
            status["meets_expectations"] = False

        # Check P99
        if response_times["p99"] > endpoint.expected_p99_ms:
            status["warnings"].append(
                f"P99 ({response_times['p99']:.2f}ms) "
                f"exceeds expectation ({endpoint.expected_p99_ms}ms)"
            )
            status["meets_expectations"] = False

        # Check error rate
        if metrics["error_rate"] > 1.0:
            status["failures"].append(
                f"Error rate ({metrics['error_rate']:.2f}%) exceeds 1%"
            )
            status["meets_expectations"] = False

        # Check against baseline if available
        if endpoint.name in self.baselines:
            baseline = self.baselines[endpoint.name]

            # Check for regression (>10% degradation)
            mean_degradation = ((response_times["mean"] - baseline["mean"]) /
                              baseline["mean"] * 100)

            if mean_degradation > 10:
                status["warnings"].append(
                    f"Performance regression detected: "
                    f"{mean_degradation:.1f}% slower than baseline"
                )

        return status

    async def run_all_benchmarks(self) -> dict[str, Any]:
        """Run benchmarks for all endpoints"""
        print("API Performance Benchmark Suite")
        print("=" * 80)

        results = {}

        async with aiohttp.ClientSession() as session:
            for endpoint in self.endpoints:
                print(f"\nBenchmarking: {endpoint.name}")
                print(f"  Method: {endpoint.method}")
                print(f"  Path: {endpoint.path}")
                print(f"  Iterations: {endpoint.iterations}")

                metrics = await self.benchmark_endpoint(endpoint, session)
                results[endpoint.name] = metrics

                if "error" not in metrics:
                    rt = metrics["response_times"]
                    print("  Results:")
                    print(f"    Mean: {rt['mean']:.2f}ms")
                    print(f"    Median: {rt['median']:.2f}ms")
                    print(f"    P95: {rt['p95']:.2f}ms")
                    print(f"    P99: {rt['p99']:.2f}ms")
                    print(f"    Throughput: {metrics['throughput_rps']:.2f} req/s")

                    status = metrics["performance_status"]
                    if status["meets_expectations"]:
                        print("    Status: ✓ Meets expectations")
                    else:
                        print("    Status: ⚠ Performance issues detected")
                        for warning in status["warnings"]:
                            print(f"      - {warning}")
                        for failure in status["failures"]:
                            print(f"      - ERROR: {failure}")
                else:
                    print(f"  Error: {metrics['error']}")

        return results

    async def establish_baselines(self, iterations: int = 1000) -> dict[str, Any]:
        """Establish performance baselines for all endpoints"""
        print("Establishing Performance Baselines")
        print("=" * 80)

        baselines = {}

        async with aiohttp.ClientSession() as session:
            for endpoint in self.endpoints:
                # Use more iterations for baseline
                endpoint.iterations = iterations

                print(f"\nEstablishing baseline for: {endpoint.name}")

                metrics = await self.benchmark_endpoint(endpoint, session)

                if "error" not in metrics:
                    baseline = {
                        "mean": metrics["response_times"]["mean"],
                        "p95": metrics["response_times"]["p95"],
                        "p99": metrics["response_times"]["p99"],
                        "throughput": metrics["throughput_rps"]
                    }

                    baselines[endpoint.name] = baseline
                    self.baselines[endpoint.name] = baseline

                    print("  Baseline established:")
                    print(f"    Mean: {baseline['mean']:.2f}ms")
                    print(f"    P95: {baseline['p95']:.2f}ms")
                    print(f"    P99: {baseline['p99']:.2f}ms")
                    print(f"    Throughput: {baseline['throughput']:.2f} req/s")

        # Save baselines to file
        with open("api_baselines.json", "w") as f:
            json.dump(baselines, f, indent=2)

        print("\nBaselines saved to api_baselines.json")

        return baselines

    def load_baselines(self, filepath: str = "api_baselines.json") -> bool:
        """Load performance baselines from file"""
        try:
            with open(filepath) as f:
                self.baselines = json.load(f)
            print(f"Loaded baselines from {filepath}")
            return True
        except FileNotFoundError:
            print(f"Baseline file not found: {filepath}")
            return False
        except Exception as e:
            print(f"Error loading baselines: {e}")
            return False

    async def compare_with_baselines(self) -> dict[str, Any]:
        """Compare current performance with baselines"""
        if not self.baselines:
            if not self.load_baselines():
                print("No baselines available for comparison")
                return {}

        print("Performance Comparison with Baselines")
        print("=" * 80)

        comparison = {}

        async with aiohttp.ClientSession() as session:
            for endpoint in self.endpoints:
                if endpoint.name not in self.baselines:
                    continue

                print(f"\nComparing: {endpoint.name}")

                # Run benchmark with fewer iterations for comparison
                endpoint.iterations = 50
                metrics = await self.benchmark_endpoint(endpoint, session)

                if "error" not in metrics:
                    baseline = self.baselines[endpoint.name]
                    current = metrics["response_times"]

                    comparison[endpoint.name] = {
                        "baseline": baseline,
                        "current": {
                            "mean": current["mean"],
                            "p95": current["p95"],
                            "p99": current["p99"],
                            "throughput": metrics["throughput_rps"]
                        },
                        "delta": {
                            "mean_percent": ((current["mean"] - baseline["mean"]) /
                                           baseline["mean"] * 100),
                            "p95_percent": ((current["p95"] - baseline["p95"]) /
                                          baseline["p95"] * 100),
                            "p99_percent": ((current["p99"] - baseline["p99"]) /
                                          baseline["p99"] * 100),
                            "throughput_percent": ((metrics["throughput_rps"] - baseline["throughput"]) /
                                                 baseline["throughput"] * 100)
                        }
                    }

                    delta = comparison[endpoint.name]["delta"]

                    print(f"  Mean: {current['mean']:.2f}ms "
                          f"(baseline: {baseline['mean']:.2f}ms, "
                          f"delta: {delta['mean_percent']:+.1f}%)")
                    print(f"  P95: {current['p95']:.2f}ms "
                          f"(baseline: {baseline['p95']:.2f}ms, "
                          f"delta: {delta['p95_percent']:+.1f}%)")
                    print(f"  P99: {current['p99']:.2f}ms "
                          f"(baseline: {baseline['p99']:.2f}ms, "
                          f"delta: {delta['p99_percent']:+.1f}%)")

                    # Check for regression
                    if delta["mean_percent"] > 10:
                        print("  ⚠ WARNING: Performance regression detected!")
                    elif delta["mean_percent"] < -10:
                        print("  ✓ Performance improvement detected!")
                    else:
                        print("  ✓ Performance stable")

        return comparison

    def generate_benchmark_report(self, results: dict[str, Any]) -> str:
        """Generate detailed benchmark report"""
        report = []
        report.append("=" * 80)
        report.append("API PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)

        # Summary statistics
        total_endpoints = len(results)
        successful = sum(1 for r in results.values() if "error" not in r)
        meeting_expectations = sum(
            1 for r in results.values()
            if "error" not in r and r.get("performance_status", {}).get("meets_expectations", False)
        )

        report.append("\nSummary:")
        report.append(f"  Total Endpoints: {total_endpoints}")
        report.append(f"  Successful: {successful}")
        report.append(f"  Meeting Expectations: {meeting_expectations}")
        report.append(f"  Success Rate: {(successful/total_endpoints)*100:.1f}%")

        # Detailed results
        report.append("\nDetailed Results:")
        report.append("-" * 40)

        for endpoint_name, metrics in results.items():
            report.append(f"\n{endpoint_name}:")

            if "error" in metrics:
                report.append(f"  ERROR: {metrics['error']}")
            else:
                rt = metrics["response_times"]
                report.append("  Response Times:")
                report.append(f"    Mean: {rt['mean']:.2f}ms")
                report.append(f"    Median: {rt['median']:.2f}ms")
                report.append(f"    Std Dev: {rt['stdev']:.2f}ms")
                report.append(f"    Min: {rt['min']:.2f}ms")
                report.append(f"    Max: {rt['max']:.2f}ms")
                report.append(f"    P50: {rt['p50']:.2f}ms")
                report.append(f"    P75: {rt['p75']:.2f}ms")
                report.append(f"    P90: {rt['p90']:.2f}ms")
                report.append(f"    P95: {rt['p95']:.2f}ms")
                report.append(f"    P99: {rt['p99']:.2f}ms")
                report.append(f"  Throughput: {metrics['throughput_rps']:.2f} req/s")
                report.append(f"  Error Rate: {metrics['error_rate']:.2f}%")

                status = metrics.get("performance_status", {})
                if status.get("meets_expectations"):
                    report.append("  Status: PASS")
                else:
                    report.append("  Status: FAIL")
                    if status.get("warnings"):
                        report.append("  Warnings:")
                        for warning in status["warnings"]:
                            report.append(f"    - {warning}")

        report.append("\n" + "=" * 80)
        return "\n".join(report)


# Pytest test functions
@pytest.fixture
async def api_benchmark():
    """Fixture for API benchmark testing"""
    return APIBenchmarkTest()


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_health_endpoint_performance(api_benchmark):
    """Test health check endpoint performance"""
    endpoint = APIEndpointBenchmark(
        name="Health Check",
        method="GET",
        path="/health",
        expected_response_time_ms=50,
        iterations=100
    )

    metrics = await api_benchmark.benchmark_endpoint(endpoint)

    assert "error" not in metrics, f"Benchmark failed: {metrics.get('error')}"
    assert metrics["response_times"]["mean"] < 100, "Health check too slow"
    assert metrics["error_rate"] < 1.0, "Health check error rate too high"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_api_baseline_establishment(api_benchmark):
    """Test establishment of API performance baselines"""
    # Run with fewer iterations for testing
    for endpoint in api_benchmark.endpoints:
        endpoint.iterations = 10

    baselines = await api_benchmark.establish_baselines(iterations=10)

    assert len(baselines) > 0, "No baselines established"

    for name, baseline in baselines.items():
        assert "mean" in baseline, f"Missing mean for {name}"
        assert "p95" in baseline, f"Missing p95 for {name}"
        assert baseline["mean"] > 0, f"Invalid mean for {name}"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_performance_regression_detection(api_benchmark):
    """Test detection of performance regressions"""
    # Create artificial baseline
    api_benchmark.baselines = {
        "Test Endpoint": {
            "mean": 100.0,
            "p95": 200.0,
            "p99": 300.0,
            "throughput": 50.0
        }
    }

    # Simulate current metrics with regression
    endpoint = APIEndpointBenchmark(
        name="Test Endpoint",
        method="GET",
        path="/test",
        expected_response_time_ms=100
    )

    metrics = {
        "response_times": {
            "mean": 150.0,  # 50% regression
            "p95": 300.0,
            "p99": 450.0
        },
        "throughput_rps": 35.0,
        "error_rate": 0.5
    }

    status = api_benchmark._check_performance(endpoint, metrics)

    assert not status["meets_expectations"], "Should detect performance issues"
    assert len(status["warnings"]) > 0, "Should have warnings for regression"


if __name__ == "__main__":
    # Run benchmarks
    async def main():
        test = APIBenchmarkTest()

        # Establish baselines or load existing
        if not test.load_baselines():
            print("Establishing new baselines...")
            await test.establish_baselines(iterations=100)

        # Run benchmarks
        results = await test.run_all_benchmarks()

        # Compare with baselines
        await test.compare_with_baselines()

        # Generate report
        report = test.generate_benchmark_report(results)
        print(report)

        # Save report
        with open("api_benchmark_report.txt", "w") as f:
            f.write(report)

    asyncio.run(main())
