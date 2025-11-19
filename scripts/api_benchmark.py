from typing import Any

#!/usr/bin/env python3
"""
API Performance Benchmark Script
Tests actual API endpoint performance with realistic scenarios.
"""

import json
import logging
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    import asyncio

    import httpx
except ImportError:
    logger.error("Missing dependencies. Install with: pip install httpx")
    sys.exit(1)


class APIBenchmark:
    """Benchmark suite for API endpoint performance"""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.results = {}
        self.client = None

    async def setup(self) -> None:
        """Setup HTTP client"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.client:
            await self.client.aclose()

    async def benchmark_endpoint(
        self, method: str, endpoint: str, runs: int = 50, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Benchmark a single API endpoint"""
        logger.info(f"Benchmarking {method} {endpoint} with {runs} runs")

        response_times = []
        status_codes = []
        errors = []

        for run in range(runs):
            try:
                start_time = time.perf_counter()

                if method.upper() == "GET":
                    response = await self.client.get(f"{self.base_url}{endpoint}")
                elif method.upper() == "POST":
                    response = await self.client.post(
                        f"{self.base_url}{endpoint}", json=payload
                    )
                elif method.upper() == "PUT":
                    response = await self.client.put(
                        f"{self.base_url}{endpoint}", json=payload
                    )
                elif method.upper() == "DELETE":
                    response = await self.client.delete(f"{self.base_url}{endpoint}")
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000

                response_times.append(duration_ms)
                status_codes.append(response.status_code)

                # Small delay between requests to avoid overwhelming the server
                await asyncio.sleep(0.01)

            except Exception as e:
                errors.append(str(e))
                logger.warning(f"Request {run + 1} failed: {e}")

        if not response_times:
            return {
                "error": f"All requests failed. Errors: {errors[:5]}",
                "total_errors": len(errors),
            }

        # Calculate statistics
        success_rate = len(response_times) / runs * 100
        error_rate = len(errors) / runs * 100

        # Status code analysis
        status_distribution = {}
        for code in status_codes:
            status_distribution[code] = status_distribution.get(code, 0) + 1

        return {
            "endpoint": f"{method} {endpoint}",
            "runs": runs,
            "successful_requests": len(response_times),
            "success_rate_percent": success_rate,
            "error_rate_percent": error_rate,
            "response_times_ms": {
                "min": min(response_times),
                "max": max(response_times),
                "mean": statistics.mean(response_times),
                "median": statistics.median(response_times),
                "p95": (
                    statistics.quantiles(response_times, n=20)[18]
                    if len(response_times) >= 20
                    else max(response_times)
                ),
                "p99": (
                    statistics.quantiles(response_times, n=100)[98]
                    if len(response_times) >= 100
                    else max(response_times)
                ),
            },
            "status_code_distribution": status_distribution,
            "throughput_rps": (
                len(response_times) / (sum(response_times) / 1000)
                if response_times
                else 0
            ),
            "errors": errors[:10],  # Keep first 10 errors for analysis
        }

    async def benchmark_system_endpoints(self) -> dict[str, Any]:
        """Benchmark system health endpoints"""
        logger.info("Benchmarking system endpoints...")

        endpoints = [
            ("GET", "/health"),
            ("GET", "/api/system/status"),
            ("GET", "/api/system/info"),
            ("GET", "/"),  # Root endpoint
        ]

        results = {}

        for method, endpoint in endpoints:
            try:
                result = await self.benchmark_endpoint(method, endpoint, runs=30)
                results[f"{method}_{endpoint.replace('/', '_').replace('__', '_')}"] = (
                    result
                )
            except Exception as e:
                logger.error(f"Failed to benchmark {method} {endpoint}: {e}")
                results[f"{method}_{endpoint.replace('/', '_').replace('__', '_')}"] = {
                    "error": str(e)
                }

        return results

    async def benchmark_document_endpoints(self) -> dict[str, Any]:
        """Benchmark document management endpoints"""
        logger.info("Benchmarking document endpoints...")

        endpoints = [
            ("GET", "/api/documents"),
            ("GET", "/api/documents?limit=10"),
            ("GET", "/api/documents?search=test"),
            ("GET", "/api/library/documents"),
            ("GET", "/api/library/stats"),
        ]

        results = {}

        for method, endpoint in endpoints:
            try:
                result = await self.benchmark_endpoint(method, endpoint, runs=30)
                endpoint_key = f"{method}_{endpoint.split('?')[0].replace('/', '_').replace('__', '_')}"
                if "?" in endpoint:
                    endpoint_key += "_with_params"
                results[endpoint_key] = result
            except Exception as e:
                logger.error(f"Failed to benchmark {method} {endpoint}: {e}")
                endpoint_key = f"{method}_{endpoint.split('?')[0].replace('/', '_').replace('__', '_')}"
                results[endpoint_key] = {"error": str(e)}

        return results

    async def benchmark_rag_endpoints(self) -> dict[str, Any]:
        """Benchmark RAG query endpoints"""
        logger.info("Benchmarking RAG endpoints...")

        # Test different query complexities
        queries = [
            {"query": "test", "max_results": 5},
            {"query": "What is machine learning?", "max_results": 10},
            {"query": "artificial intelligence", "max_results": 5},
        ]

        results = {}

        # Test query endpoint with different payloads
        for i, query_payload in enumerate(queries):
            try:
                result = await self.benchmark_endpoint(
                    "POST", "/api/rag/query", runs=20, payload=query_payload
                )
                results[f"POST_rag_query_{i+1}"] = result
            except Exception as e:
                logger.error(f"Failed to benchmark RAG query {i+1}: {e}")
                results[f"POST_rag_query_{i+1}"] = {"error": str(e)}

        return results

    async def benchmark_settings_endpoints(self) -> dict[str, Any]:
        """Benchmark settings endpoints"""
        logger.info("Benchmarking settings endpoints...")

        endpoints = [
            ("GET", "/api/settings"),
        ]

        results = {}

        for method, endpoint in endpoints:
            try:
                result = await self.benchmark_endpoint(method, endpoint, runs=20)
                results[f"{method}_{endpoint.replace('/', '_').replace('__', '_')}"] = (
                    result
                )
            except Exception as e:
                logger.error(f"Failed to benchmark {method} {endpoint}: {e}")
                results[f"{method}_{endpoint.replace('/', '_').replace('__', '_')}"] = {
                    "error": str(e)
                }

        return results

    async def run_all_benchmarks(self) -> dict[str, Any]:
        """Run all API benchmarks"""
        logger.info("Starting comprehensive API benchmark suite...")
        start_time = time.time()

        try:
            await self.setup()

            # Test server availability first
            try:
                response = await self.client.get(f"{self.base_url}/health", timeout=5.0)
                logger.info(
                    f"Server available - Health check status: {response.status_code}"
                )
            except Exception as e:
                logger.warning(f"Server may not be available: {e}")
                logger.info("Continuing with benchmarks - some may fail")

            # Run benchmark suites
            system_results = await self.benchmark_system_endpoints()
            document_results = await self.benchmark_document_endpoints()
            rag_results = await self.benchmark_rag_endpoints()
            settings_results = await self.benchmark_settings_endpoints()

            end_time = time.time()

            # Compile results
            self.results = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "base_url": self.base_url,
                    "total_duration_seconds": end_time - start_time,
                    "benchmark_version": "1.0.0",
                },
                "system_endpoints": system_results,
                "document_endpoints": document_results,
                "rag_endpoints": rag_results,
                "settings_endpoints": settings_results,
            }

            logger.info(
                f"API benchmark suite completed in {end_time - start_time:.2f} seconds"
            )

        except Exception as e:
            logger.error(f"API benchmark suite failed: {e}")
            self.results["error"] = str(e)
            raise
        finally:
            await self.cleanup()

        return self.results

    def print_summary(self) -> None:
        """Print comprehensive benchmark summary"""
        print("\n" + "=" * 80)
        print("API PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 80)

        if "error" in self.results:
            print(f"❌ BENCHMARK FAILED: {self.results['error']}")
            return

        # Overall metadata
        if "metadata" in self.results:
            metadata = self.results["metadata"]
            print(f"🌐 Base URL: {metadata['base_url']}")
            print(f"⏱️  Runtime: {metadata['total_duration_seconds']:.2f} seconds")
            print(f"📅 Timestamp: {metadata['timestamp']}")

        # Performance summary by category
        categories = [
            "system_endpoints",
            "document_endpoints",
            "rag_endpoints",
            "settings_endpoints",
        ]

        for category in categories:
            if category not in self.results:
                continue

            print(f"\n📊 {category.upper().replace('_', ' ')}:")

            category_results = self.results[category]
            successful_endpoints = 0
            total_endpoints = 0
            all_response_times = []

            for endpoint, result in category_results.items():
                total_endpoints += 1

                if "error" in result:
                    print(f"   ❌ {endpoint}: {result['error']}")
                    continue

                successful_endpoints += 1
                rt = result.get("response_times_ms", {})
                success_rate = result.get("success_rate_percent", 0)

                mean_time = rt.get("mean", 0)
                all_response_times.append(mean_time)

                status = (
                    "✅"
                    if success_rate >= 95 and mean_time < 100
                    else "⚠️"
                    if success_rate >= 80
                    else "❌"
                )

                print(f"   {status} {endpoint}:")
                print(f"      • Mean: {mean_time:.2f}ms")
                print(f"      • P95: {rt.get('p95', 0):.2f}ms")
                print(f"      • Success: {success_rate:.1f}%")
                print(
                    f"      • Throughput: {result.get('throughput_rps', 0):.1f} req/s"
                )

            # Category summary
            if all_response_times:
                category_avg = statistics.mean(all_response_times)
                print(f"   📈 Category Average: {category_avg:.2f}ms")
                print(
                    f"   ✅ Successful Endpoints: {successful_endpoints}/{total_endpoints}"
                )

        # Overall performance assessment
        print("\n🎯 OVERALL ASSESSMENT:")

        all_times = []
        all_success_rates = []

        for category in categories:
            if category not in self.results:
                continue
            for endpoint, result in self.results[category].items():
                if "error" not in result:
                    rt = result.get("response_times_ms", {})
                    if "mean" in rt:
                        all_times.append(rt["mean"])
                    success_rate = result.get("success_rate_percent", 0)
                    all_success_rates.append(success_rate)

        if all_times and all_success_rates:
            overall_avg_time = statistics.mean(all_times)
            overall_success_rate = statistics.mean(all_success_rates)

            if overall_avg_time < 50 and overall_success_rate >= 95:
                assessment = "✅ EXCELLENT"
            elif overall_avg_time < 200 and overall_success_rate >= 90:
                assessment = "✅ GOOD"
            elif overall_avg_time < 500 and overall_success_rate >= 80:
                assessment = "⚠️ ACCEPTABLE"
            else:
                assessment = "❌ NEEDS IMPROVEMENT"

            print(f"   {assessment}")
            print(f"   📊 Average Response Time: {overall_avg_time:.2f}ms")
            print(f"   🎯 Average Success Rate: {overall_success_rate:.1f}%")
            print(f"   🚀 Total Endpoints Tested: {len(all_times)}")

        print("\n" + "=" * 80)

    def save_results(self, filename: str = None) -> Any:
        """Save results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"api_benchmark_results_{timestamp}.json"

        output_path = Path(filename)
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"Results saved to: {output_path}")
        return output_path


async def main() -> Any:
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="API Performance Benchmark")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="Base URL to test"
    )
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    parser.add_argument("--output", help="Output filename for results")

    args = parser.parse_args()

    try:
        benchmark = APIBenchmark(args.url)
        results = await benchmark.run_all_benchmarks()
        benchmark.print_summary()

        if args.save:
            output_file = benchmark.save_results(args.output)
            print(f"\n💾 Results saved to: {output_file}")

        # Exit with appropriate code based on results
        if "error" not in results:
            return 0
        else:
            return 1

    except Exception as e:
        logger.error(f"API benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
