#!/usr/bin/env python3
"""
Lightweight Load Testing Script

Simulates realistic concurrent user scenarios to validate system stability under load.
Monitors system behavior, detects performance degradation, and identifies memory leaks.

Load Test Scenarios:
- Basic Load: 10 concurrent users, 30 seconds
- Moderate Load: 25 concurrent users, 45 seconds
- Stress Test: 50 concurrent users, 60 seconds

Agent C3: Performance Baseline Testing Expert
Mission: Validate system performance under concurrent load
"""

import asyncio
import json
import requests
import subprocess
import time
import threading
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import statistics
import argparse


@dataclass
class LoadTestResult:
    """Results from a single load test request."""
    url: str
    status_code: int
    response_time_ms: float
    content_length: int
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class SystemResourceSnapshot:
    """System resource usage snapshot."""
    timestamp: datetime
    memory_mb: float
    cpu_percent: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float


class LightweightLoadTester:
    """Lightweight concurrent load testing framework."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.project_root = Path(__file__).parent.parent
        self.api_process = None
        self.results: List[LoadTestResult] = []
        self.resource_snapshots: List[SystemResourceSnapshot] = []

        # Test scenarios
        self.scenarios = {
            'basic': {'users': 10, 'duration': 30, 'requests_per_user': 20},
            'moderate': {'users': 25, 'duration': 45, 'requests_per_user': 30},
            'stress': {'users': 50, 'duration': 60, 'requests_per_user': 40}
        }

        # API endpoints to test
        self.endpoints = [
            '/api/system/health',
            '/api/documents/',
            '/api/library/stats',
            '/api/settings'
        ]

    def run_load_test(self, scenario: str = 'basic') -> Dict[str, Any]:
        """Run load test for specified scenario."""
        if scenario not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario}. Available: {list(self.scenarios.keys())}")

        config = self.scenarios[scenario]

        print(f"🔥 Load Test: {scenario.title()} Scenario ({config['users']} users, {config['duration']}s)")

        # Start API server
        self._start_api_server()

        try:
            # Start resource monitoring
            self._start_resource_monitoring(config['duration'])

            # Run load test
            test_results = self._execute_load_test(config)

            # Wait for resource monitoring to complete
            time.sleep(2)

            # Generate report
            return self._generate_load_test_report(scenario, test_results)

        finally:
            # Clean up
            self._stop_api_server()

    def _start_api_server(self) -> None:
        """Start FastAPI server for load testing."""
        print("   🚀 Starting API server...")

        try:
            # Use a different port for load testing
            self.api_process = subprocess.Popen([
                'python', '-m', 'uvicorn',
                'backend.api.main:app',
                '--host', '127.0.0.1',
                '--port', '8002',  # Different port for load testing
                '--log-level', 'error'
            ], cwd=self.project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Update base URL for load testing port
            self.base_url = "http://127.0.0.1:8002"

            # Wait for server to start and verify it's responding
            for attempt in range(15):  # 15 seconds timeout
                time.sleep(1)
                try:
                    response = requests.get(f"{self.base_url}/api/system/health", timeout=2)
                    if response.status_code == 200:
                        print("   ✅ API server ready")
                        return
                except requests.exceptions.RequestException:
                    continue

            raise Exception("API server failed to start")

        except Exception as e:
            print(f"   ❌ Failed to start API server: {e}")
            raise

    def _stop_api_server(self) -> None:
        """Stop the API server."""
        if self.api_process:
            self.api_process.terminate()
            time.sleep(2)
            if self.api_process.poll() is None:
                self.api_process.kill()
            print("   🛑 API server stopped")

    def _start_resource_monitoring(self, duration: int) -> None:
        """Start background resource monitoring."""
        def monitor_resources():
            start_time = time.time()
            process = psutil.Process()

            while time.time() - start_time < duration + 10:  # Monitor a bit longer
                try:
                    # System resources
                    memory_info = psutil.virtual_memory()
                    disk_io = psutil.disk_io_counters()
                    network_io = psutil.net_io_counters()

                    # Process resources
                    process_memory = process.memory_info().rss / 1024 / 1024  # MB
                    cpu_percent = process.cpu_percent()

                    snapshot = SystemResourceSnapshot(
                        timestamp=datetime.now(timezone.utc),
                        memory_mb=process_memory,
                        cpu_percent=cpu_percent,
                        memory_percent=memory_info.percent,
                        disk_io_read_mb=disk_io.read_bytes / 1024 / 1024 if disk_io else 0,
                        disk_io_write_mb=disk_io.write_bytes / 1024 / 1024 if disk_io else 0,
                        network_sent_mb=network_io.bytes_sent / 1024 / 1024 if network_io else 0,
                        network_recv_mb=network_io.bytes_recv / 1024 / 1024 if network_io else 0
                    )

                    self.resource_snapshots.append(snapshot)

                except Exception as e:
                    print(f"   ⚠️  Resource monitoring error: {e}")

                time.sleep(1)  # Sample every second

        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()
        print(f"   📊 Resource monitoring started ({duration}s)")

    def _execute_load_test(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the load test with specified configuration."""
        users = config['users']
        duration = config['duration']
        requests_per_user = config['requests_per_user']

        results = []
        start_time = time.time()

        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=users) as executor:
            # Submit user simulation tasks
            futures = []
            for user_id in range(users):
                future = executor.submit(
                    self._simulate_user_behavior,
                    user_id,
                    duration,
                    requests_per_user
                )
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    user_results = future.result(timeout=duration + 10)
                    results.extend(user_results)
                except Exception as e:
                    print(f"   ⚠️  User simulation error: {e}")

        total_time = time.time() - start_time

        return {
            'total_requests': len(results),
            'successful_requests': sum(1 for r in results if r.status_code == 200),
            'failed_requests': sum(1 for r in results if r.status_code != 200),
            'total_time_s': total_time,
            'requests_per_second': len(results) / total_time if total_time > 0 else 0,
            'results': results
        }

    def _simulate_user_behavior(self, user_id: int, duration: int, requests_per_user: int) -> List[LoadTestResult]:
        """Simulate realistic user behavior with requests to various endpoints."""
        user_results = []
        start_time = time.time()
        request_interval = duration / requests_per_user if requests_per_user > 0 else 1

        request_count = 0
        while time.time() - start_time < duration and request_count < requests_per_user:
            # Choose endpoint (weighted towards common endpoints)
            import random
            endpoint_weights = {
                '/api/system/health': 0.1,     # 10% - health checks
                '/api/documents/': 0.4,        # 40% - main functionality
                '/api/library/stats': 0.3,     # 30% - dashboard views
                '/api/settings': 0.2           # 20% - settings access
            }

            endpoint = random.choices(
                list(endpoint_weights.keys()),
                weights=list(endpoint_weights.values())
            )[0]

            # Make request
            result = self._make_request(f"{self.base_url}{endpoint}")
            user_results.append(result)

            request_count += 1

            # Wait before next request (simulate user think time)
            think_time = max(0, request_interval - 0.1 + random.uniform(-0.05, 0.05))
            time.sleep(think_time)

        return user_results

    def _make_request(self, url: str, timeout: int = 10) -> LoadTestResult:
        """Make a single HTTP request and record the result."""
        start_time = time.perf_counter()

        try:
            response = requests.get(url, timeout=timeout)
            end_time = time.perf_counter()

            return LoadTestResult(
                url=url,
                status_code=response.status_code,
                response_time_ms=(end_time - start_time) * 1000,
                content_length=len(response.content)
            )

        except requests.exceptions.RequestException as e:
            end_time = time.perf_counter()

            return LoadTestResult(
                url=url,
                status_code=0,
                response_time_ms=(end_time - start_time) * 1000,
                content_length=0,
                error=str(e)
            )

    def _generate_load_test_report(self, scenario: str, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive load test report."""
        results = test_results['results']
        successful_results = [r for r in results if r.status_code == 200]

        # Response time analysis
        response_times = [r.response_time_ms for r in successful_results]

        response_stats = {}
        if response_times:
            response_stats = {
                'avg_ms': statistics.mean(response_times),
                'median_ms': statistics.median(response_times),
                'p95_ms': self._percentile(response_times, 95),
                'p99_ms': self._percentile(response_times, 99),
                'min_ms': min(response_times),
                'max_ms': max(response_times)
            }

        # Memory leak detection
        memory_analysis = self._analyze_memory_pattern()

        # Error analysis
        error_analysis = self._analyze_errors(results)

        # Generate report
        report = {
            'scenario': scenario,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'test_summary': {
                'total_requests': test_results['total_requests'],
                'successful_requests': test_results['successful_requests'],
                'failed_requests': test_results['failed_requests'],
                'success_rate_percent': (test_results['successful_requests'] / test_results['total_requests'] * 100) if test_results['total_requests'] > 0 else 0,
                'requests_per_second': test_results['requests_per_second'],
                'total_duration_s': test_results['total_time_s']
            },
            'performance_metrics': response_stats,
            'system_resources': self._analyze_system_resources(),
            'memory_analysis': memory_analysis,
            'error_analysis': error_analysis,
            'pass_criteria': self._evaluate_pass_criteria(response_stats, memory_analysis, error_analysis)
        }

        # Print report
        self._print_load_test_report(report)

        # Save results
        self._save_load_test_results(scenario, report)

        return report

    def _analyze_memory_pattern(self) -> Dict[str, Any]:
        """Analyze memory usage patterns for leak detection."""
        if not self.resource_snapshots:
            return {'error': 'No memory data collected'}

        memory_values = [s.memory_mb for s in self.resource_snapshots]

        # Calculate memory trend
        if len(memory_values) >= 3:
            # Simple linear regression to detect memory growth trend
            x_values = list(range(len(memory_values)))
            n = len(memory_values)

            sum_x = sum(x_values)
            sum_y = sum(memory_values)
            sum_xy = sum(x * y for x, y in zip(x_values, memory_values))
            sum_xx = sum(x * x for x in x_values)

            # Slope calculation (memory growth rate)
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
            memory_growth_rate_mb_per_sample = slope

            # Convert to MB/hour (assuming 1-second sampling)
            memory_growth_rate_mb_per_hour = memory_growth_rate_mb_per_sample * 3600
        else:
            memory_growth_rate_mb_per_hour = 0

        return {
            'initial_memory_mb': memory_values[0] if memory_values else 0,
            'final_memory_mb': memory_values[-1] if memory_values else 0,
            'peak_memory_mb': max(memory_values) if memory_values else 0,
            'memory_growth_mb': (memory_values[-1] - memory_values[0]) if len(memory_values) >= 2 else 0,
            'memory_growth_rate_mb_per_hour': memory_growth_rate_mb_per_hour,
            'memory_stable': abs(memory_growth_rate_mb_per_hour) < 5,  # Stable if growth <5MB/hour
            'samples_count': len(memory_values)
        }

    def _analyze_system_resources(self) -> Dict[str, Any]:
        """Analyze system resource utilization."""
        if not self.resource_snapshots:
            return {'error': 'No resource data collected'}

        cpu_values = [s.cpu_percent for s in self.resource_snapshots]
        memory_percent_values = [s.memory_percent for s in self.resource_snapshots]

        return {
            'cpu_usage': {
                'avg_percent': statistics.mean(cpu_values) if cpu_values else 0,
                'peak_percent': max(cpu_values) if cpu_values else 0
            },
            'system_memory': {
                'avg_percent': statistics.mean(memory_percent_values) if memory_percent_values else 0,
                'peak_percent': max(memory_percent_values) if memory_percent_values else 0
            },
            'monitoring_duration_s': len(self.resource_snapshots)
        }

    def _analyze_errors(self, results: List[LoadTestResult]) -> Dict[str, Any]:
        """Analyze error patterns and types."""
        errors = [r for r in results if r.status_code != 200 or r.error]

        error_types = {}
        for result in errors:
            if result.error:
                error_types[result.error] = error_types.get(result.error, 0) + 1
            else:
                status_key = f"HTTP_{result.status_code}"
                error_types[status_key] = error_types.get(status_key, 0) + 1

        return {
            'total_errors': len(errors),
            'error_rate_percent': (len(errors) / len(results) * 100) if results else 0,
            'error_types': error_types,
            'timeout_errors': sum(1 for r in results if 'timeout' in (r.error or '').lower()),
            'connection_errors': sum(1 for r in results if 'connection' in (r.error or '').lower()),
            'server_errors': sum(1 for r in results if r.status_code >= 500)
        }

    def _evaluate_pass_criteria(self, response_stats: Dict[str, Any], memory_analysis: Dict[str, Any], error_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate whether the load test meets pass criteria."""
        criteria = {
            'response_time_acceptable': True,
            'error_rate_acceptable': True,
            'memory_stable': True,
            'overall_pass': True
        }

        # Response time criteria
        if response_stats and 'p95_ms' in response_stats:
            criteria['response_time_acceptable'] = response_stats['p95_ms'] < 1000  # 1 second p95

        # Error rate criteria
        if 'error_rate_percent' in error_analysis:
            criteria['error_rate_acceptable'] = error_analysis['error_rate_percent'] < 5  # <5% error rate

        # Memory stability criteria
        if 'memory_stable' in memory_analysis:
            criteria['memory_stable'] = memory_analysis['memory_stable']

        # Overall pass
        criteria['overall_pass'] = all([
            criteria['response_time_acceptable'],
            criteria['error_rate_acceptable'],
            criteria['memory_stable']
        ])

        return criteria

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def _print_load_test_report(self, report: Dict[str, Any]) -> None:
        """Print formatted load test report."""
        print(f"📊 Test Results:")

        summary = report['test_summary']
        print(f"  - Total Requests: {summary['total_requests']}")
        print(f"  - Successful: {summary['successful_requests']} ({summary['success_rate_percent']:.1f}%)")
        print(f"  - Failed: {summary['failed_requests']}")
        print(f"  - Requests/sec: {summary['requests_per_second']:.1f}")

        perf = report.get('performance_metrics', {})
        if perf:
            print(f"  - Average Response Time: {perf.get('avg_ms', 0):.0f} ms")
            print(f"  - 95th Percentile: {perf.get('p95_ms', 0):.0f} ms")
            print(f"  - Max Response Time: {perf.get('max_ms', 0):.0f} ms")

        memory = report.get('memory_analysis', {})
        if memory and 'error' not in memory:
            growth = memory.get('memory_growth_mb', 0)
            growth_rate = memory.get('memory_growth_rate_mb_per_hour', 0)
            stable = memory.get('memory_stable', False)

            print(f"📊 System Resources:")
            print(f"  - Memory Usage: Start {memory.get('initial_memory_mb', 0):.0f}MB → "
                  f"Peak {memory.get('peak_memory_mb', 0):.0f}MB → End {memory.get('final_memory_mb', 0):.0f}MB")
            print(f"  - Memory Growth: {growth:+.1f}MB ({growth_rate:+.1f}MB/hour)")
            print(f"  - Memory Stability: {'✅ Stable' if stable else '⚠️ Growing'}")

        errors = report.get('error_analysis', {})
        if errors:
            print(f"📊 Error Analysis:")
            print(f"  - Timeout errors: {errors.get('timeout_errors', 0)}")
            print(f"  - Connection errors: {errors.get('connection_errors', 0)}")
            print(f"  - Server errors: {errors.get('server_errors', 0)}")

        # Pass criteria
        criteria = report.get('pass_criteria', {})
        overall_pass = criteria.get('overall_pass', False)

        print(f"✅ Load test completed {'successfully' if overall_pass else 'with issues'}")

    def _save_load_test_results(self, scenario: str, report: Dict[str, Any]) -> None:
        """Save load test results to file."""
        results_dir = self.project_root / "performance_results"
        results_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_{scenario}_{timestamp}.json"

        results_file = results_dir / filename
        with open(results_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"💾 Results saved to: {results_file}")


def main():
    """Main load testing function with CLI interface."""
    parser = argparse.ArgumentParser(description="Lightweight Load Testing")
    parser.add_argument("--scenario", choices=['basic', 'moderate', 'stress'],
                       default='basic', help="Load test scenario to run")
    parser.add_argument("--url", default="http://127.0.0.1:8000",
                       help="Base URL for load testing")

    args = parser.parse_args()

    try:
        tester = LightweightLoadTester(args.url)
        results = tester.run_load_test(args.scenario)

        # Exit with appropriate code
        pass_criteria = results.get('pass_criteria', {})
        if pass_criteria.get('overall_pass', False):
            print("✅ Load test passed all criteria")
            return 0
        else:
            print("❌ Load test failed some criteria")
            return 1

    except Exception as e:
        print(f"❌ Load test failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())