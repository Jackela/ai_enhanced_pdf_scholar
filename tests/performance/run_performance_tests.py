#!/usr/bin/env python
"""
Main Performance Test Runner

Orchestrates the execution of all performance tests and generates comprehensive reports.
"""

import asyncio
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
import subprocess
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.performance.test_concurrent_users import ConcurrentUserTest
from tests.performance.test_api_benchmarks import APIBenchmarkTest
from tests.performance.test_resource_monitoring import ResourceTestSuite
from tests.performance.metrics_collector import MetricsCollector, PerformanceThresholds, PerformanceReport


class PerformanceTestRunner:
    """Orchestrates performance test execution"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
        self.start_time = None
        self.end_time = None

    async def run_concurrent_tests(self, scenarios: list = None):
        """Run concurrent user tests"""
        print("\n" + "="*80)
        print("CONCURRENT USER TESTS")
        print("="*80)

        test = ConcurrentUserTest(self.base_url)

        if scenarios is None:
            scenarios = [
                "gradual_load_increase",
                "spike_load",
                "document_upload_storm",
                "query_burst"
            ]

        results = {}
        for scenario in scenarios:
            method = getattr(test, f"test_{scenario}", None)
            if method:
                print(f"\nRunning: {scenario}")
                try:
                    metrics = await method()
                    results[scenario] = {
                        "success": True,
                        "metrics": {
                            "response_time_ms": metrics.avg_response_time,
                            "p95_ms": metrics.p95,
                            "p99_ms": metrics.p99,
                            "throughput_rps": metrics.throughput,
                            "error_rate": metrics.error_rate,
                            "peak_memory_mb": metrics.peak_memory_mb
                        }
                    }
                except Exception as e:
                    results[scenario] = {"success": False, "error": str(e)}

        self.results["concurrent_tests"] = results
        return results

    async def run_api_benchmarks(self, establish_baseline: bool = False):
        """Run API endpoint benchmarks"""
        print("\n" + "="*80)
        print("API ENDPOINT BENCHMARKS")
        print("="*80)

        test = APIBenchmarkTest(self.base_url)

        if establish_baseline:
            print("\nEstablishing baselines...")
            baselines = await test.establish_baselines(iterations=100)
            self.results["baselines"] = baselines
        else:
            # Load existing baselines if available
            test.load_baselines()

        # Run benchmarks
        benchmark_results = await test.run_all_benchmarks()

        # Compare with baselines
        if test.baselines:
            comparison = await test.compare_with_baselines()
            self.results["baseline_comparison"] = comparison

        self.results["api_benchmarks"] = benchmark_results
        return benchmark_results

    async def run_resource_tests(self):
        """Run resource monitoring tests"""
        print("\n" + "="*80)
        print("RESOURCE MONITORING TESTS")
        print("="*80)

        test = ResourceTestSuite(self.base_url)

        # Run individual resource tests
        results = {}

        print("\nTesting memory stability...")
        results["memory"] = await test.test_memory_under_load(duration_seconds=30)

        print("\nTesting for memory leaks...")
        results["leak_detection"] = await test.test_memory_leak_detection()

        print("\nTesting resource cleanup...")
        results["cleanup"] = await test.test_resource_cleanup()

        print("\nTesting CPU patterns...")
        results["cpu_patterns"] = await test.test_cpu_usage_patterns()

        self.results["resource_tests"] = results
        return results

    def run_locust_tests(self, users: int = 50, duration: str = "2m"):
        """Run Locust load tests"""
        print("\n" + "="*80)
        print("LOCUST LOAD TESTS")
        print("="*80)

        # Check if Locust is installed
        try:
            import locust
        except ImportError:
            print("Locust not installed. Skipping load tests.")
            print("Install with: pip install locust")
            return None

        # Run Locust programmatically
        from tests.performance.locustfile import run_load_test

        print(f"\nRunning Locust with {users} users for {duration}")
        results = run_load_test(
            host=self.base_url,
            users=users,
            spawn_rate=2,
            run_time=duration
        )

        self.results["locust_tests"] = results
        return results

    async def run_all_tests(self, test_config: dict = None):
        """Run all performance tests"""
        self.start_time = datetime.now()

        config = test_config or {
            "concurrent": True,
            "benchmarks": True,
            "resources": True,
            "locust": False,  # Disabled by default as it takes longer
            "establish_baseline": False
        }

        print("="*80)
        print("COMPREHENSIVE PERFORMANCE TEST SUITE")
        print(f"Started: {self.start_time}")
        print(f"Target: {self.base_url}")
        print("="*80)

        # Run concurrent user tests
        if config.get("concurrent"):
            await self.run_concurrent_tests()

        # Run API benchmarks
        if config.get("benchmarks"):
            await self.run_api_benchmarks(
                establish_baseline=config.get("establish_baseline", False)
            )

        # Run resource tests
        if config.get("resources"):
            await self.run_resource_tests()

        # Run Locust tests
        if config.get("locust"):
            self.run_locust_tests()

        self.end_time = datetime.now()

        # Generate reports
        self.generate_reports()

        return self.results

    def generate_reports(self):
        """Generate comprehensive performance reports"""
        print("\n" + "="*80)
        print("GENERATING REPORTS")
        print("="*80)

        # Create reports directory
        reports_dir = Path("performance_reports")
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON report
        json_report = reports_dir / f"performance_report_{timestamp}.json"
        with open(json_report, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"JSON report: {json_report}")

        # Text summary report
        text_report = reports_dir / f"performance_summary_{timestamp}.txt"
        with open(text_report, "w") as f:
            f.write(self._generate_text_summary())
        print(f"Text report: {text_report}")

        # HTML report
        html_report = reports_dir / f"performance_report_{timestamp}.html"
        with open(html_report, "w") as f:
            f.write(self._generate_html_report())
        print(f"HTML report: {html_report}")

        # Print summary to console
        print("\n" + self._generate_text_summary())

    def _generate_text_summary(self) -> str:
        """Generate text summary of results"""
        lines = []
        lines.append("="*80)
        lines.append("PERFORMANCE TEST SUMMARY")
        lines.append(f"Duration: {self.end_time - self.start_time if self.end_time else 'N/A'}")
        lines.append("="*80)

        # Concurrent tests summary
        if "concurrent_tests" in self.results:
            lines.append("\nCONCURRENT USER TESTS:")
            for scenario, result in self.results["concurrent_tests"].items():
                if result.get("success"):
                    metrics = result["metrics"]
                    lines.append(f"  {scenario}:")
                    lines.append(f"    Response Time: {metrics['response_time_ms']:.2f}ms")
                    lines.append(f"    P95: {metrics['p95_ms']:.2f}ms")
                    lines.append(f"    Throughput: {metrics['throughput_rps']:.2f} req/s")
                    lines.append(f"    Error Rate: {metrics['error_rate']:.2f}%")
                else:
                    lines.append(f"  {scenario}: FAILED - {result.get('error')}")

        # API benchmarks summary
        if "api_benchmarks" in self.results:
            lines.append("\nAPI BENCHMARKS:")
            for endpoint, metrics in self.results["api_benchmarks"].items():
                if "error" not in metrics:
                    rt = metrics.get("response_times", {})
                    lines.append(f"  {endpoint}:")
                    lines.append(f"    Mean: {rt.get('mean', 0):.2f}ms")
                    lines.append(f"    P95: {rt.get('p95', 0):.2f}ms")
                    lines.append(f"    Throughput: {metrics.get('throughput_rps', 0):.2f} req/s")

        # Resource tests summary
        if "resource_tests" in self.results:
            lines.append("\nRESOURCE USAGE:")
            resource = self.results["resource_tests"]

            if "memory" in resource:
                mem = resource["memory"].get("memory", {})
                lines.append(f"  Memory:")
                lines.append(f"    Peak: {mem.get('peak_mb', 0):.2f}MB")
                lines.append(f"    Growth: {mem.get('growth_mb', 0):.2f}MB")
                if mem.get("leak_detected"):
                    lines.append(f"    WARNING: {mem.get('leak_reason')}")

            if "cpu_patterns" in resource:
                cpu = resource["cpu_patterns"]
                if "heavy" in cpu:
                    lines.append(f"  CPU (Heavy Load):")
                    lines.append(f"    Average: {cpu['heavy']['avg_cpu']:.1f}%")
                    lines.append(f"    Peak: {cpu['heavy']['peak_cpu']:.1f}%")

        lines.append("\n" + "="*80)
        return "\n".join(lines)

    def _generate_html_report(self) -> str:
        """Generate HTML report"""
        html = []
        html.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Test Report</title>
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    margin: 20px;
                    background: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 10px;
                }
                h2 {
                    color: #34495e;
                    margin-top: 30px;
                    border-bottom: 1px solid #ecf0f1;
                    padding-bottom: 5px;
                }
                .metric-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 20px 0;
                }
                .metric-card {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 5px;
                    padding: 15px;
                    text-align: center;
                }
                .metric-value {
                    font-size: 28px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 5px 0;
                }
                .metric-label {
                    color: #7f8c8d;
                    font-size: 12px;
                    text-transform: uppercase;
                }
                .status-pass { color: #27ae60; }
                .status-fail { color: #e74c3c; }
                .status-warn { color: #f39c12; }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                th, td {
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #dee2e6;
                }
                th {
                    background: #f8f9fa;
                    font-weight: 600;
                }
                .timestamp {
                    color: #7f8c8d;
                    font-size: 14px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
        """)

        html.append(f"<h1>Performance Test Report</h1>")
        html.append(f'<div class="timestamp">Generated: {datetime.now():%Y-%m-%d %H:%M:%S}</div>')
        html.append(f'<div class="timestamp">Duration: {self.end_time - self.start_time if self.end_time else "N/A"}</div>')

        # Key metrics summary
        html.append('<h2>Key Metrics Summary</h2>')
        html.append('<div class="metric-grid">')

        # Extract key metrics
        if "concurrent_tests" in self.results:
            for scenario, result in self.results["concurrent_tests"].items():
                if result.get("success"):
                    metrics = result["metrics"]
                    status_class = "status-pass" if metrics["error_rate"] < 5 else "status-warn"
                    html.append(f'''
                    <div class="metric-card">
                        <div class="metric-label">{scenario.replace("_", " ").title()}</div>
                        <div class="metric-value {status_class}">{metrics["response_time_ms"]:.0f}ms</div>
                        <div class="metric-label">Avg Response Time</div>
                    </div>
                    ''')

        html.append('</div>')

        # Detailed results tables
        if "api_benchmarks" in self.results:
            html.append('<h2>API Endpoint Performance</h2>')
            html.append('<table>')
            html.append('<tr><th>Endpoint</th><th>Mean (ms)</th><th>P95 (ms)</th><th>P99 (ms)</th><th>Throughput (req/s)</th><th>Status</th></tr>')

            for endpoint, metrics in self.results["api_benchmarks"].items():
                if "error" not in metrics:
                    rt = metrics.get("response_times", {})
                    status = metrics.get("performance_status", {})
                    status_text = "PASS" if status.get("meets_expectations") else "FAIL"
                    status_class = "status-pass" if status.get("meets_expectations") else "status-fail"

                    html.append(f'''
                    <tr>
                        <td>{endpoint}</td>
                        <td>{rt.get("mean", 0):.2f}</td>
                        <td>{rt.get("p95", 0):.2f}</td>
                        <td>{rt.get("p99", 0):.2f}</td>
                        <td>{metrics.get("throughput_rps", 0):.2f}</td>
                        <td class="{status_class}">{status_text}</td>
                    </tr>
                    ''')

            html.append('</table>')

        html.append('</div></body></html>')
        return "".join(html)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run performance tests")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL to test")
    parser.add_argument("--concurrent", action="store_true", help="Run concurrent user tests")
    parser.add_argument("--benchmarks", action="store_true", help="Run API benchmarks")
    parser.add_argument("--resources", action="store_true", help="Run resource tests")
    parser.add_argument("--locust", action="store_true", help="Run Locust load tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--baseline", action="store_true", help="Establish new baselines")
    parser.add_argument("--users", type=int, default=50, help="Number of users for load tests")
    parser.add_argument("--duration", default="2m", help="Duration for load tests")

    args = parser.parse_args()

    # Configure test run
    config = {
        "concurrent": args.concurrent or args.all,
        "benchmarks": args.benchmarks or args.all,
        "resources": args.resources or args.all,
        "locust": args.locust,
        "establish_baseline": args.baseline
    }

    # Run tests
    runner = PerformanceTestRunner(args.url)

    async def run():
        return await runner.run_all_tests(config)

    results = asyncio.run(run())

    # Exit with appropriate code
    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()