#!/usr/bin/env python3
"""
Test Performance Benchmarking Script

Measures and compares test execution performance before and after optimizations.
Expected improvements:
- 60-80% reduction in test execution time
- 50% reduction in database setup overhead
- 40% improvement in CI/CD pipeline speed
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any


class TestBenchmark:
    """Test performance benchmarking utility."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {}

    def run_benchmark_suite(self) -> dict[str, Any]:
        """Run complete benchmark suite and return results."""
        print("🚀 Starting Test Performance Benchmark...")

        # Benchmark individual test categories
        self.results['unit_tests'] = self._benchmark_unit_tests()
        self.results['integration_tests'] = self._benchmark_integration_tests()
        self.results['database_tests'] = self._benchmark_database_tests()
        self.results['parallel_tests'] = self._benchmark_parallel_tests()

        # Overall metrics
        self.results['total_time'] = sum(
            result['duration'] for result in self.results.values()
            if isinstance(result, dict) and 'duration' in result
        )

        self._generate_report()
        return self.results

    def _benchmark_unit_tests(self) -> dict[str, Any]:
        """Benchmark unit test execution."""
        print("📊 Benchmarking unit tests...")

        start_time = time.time()

        # Run optimized unit tests
        result = subprocess.run([
            'python', '-m', 'pytest', 'tests/',
            '-m', 'unit',
            '-v',
            '--tb=no',
            '--disable-warnings',
            '-n', 'auto',
            '--dist=loadfile'
        ],
        cwd=self.project_root,
        capture_output=True,
        text=True
        )

        duration = time.time() - start_time

        # Parse test results
        test_count = self._extract_test_count(result.stdout)

        return {
            'duration': duration,
            'test_count': test_count,
            'tests_per_second': test_count / duration if duration > 0 else 0,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    def _benchmark_integration_tests(self) -> dict[str, Any]:
        """Benchmark integration test execution."""
        print("📊 Benchmarking integration tests...")

        start_time = time.time()

        # Run comprehensive tests
        result = subprocess.run([
            'python', '-m', 'pytest',
            'test_comprehensive.py',
            '-v',
            '--tb=no',
            '--disable-warnings',
            '--timeout=120'
        ],
        cwd=self.project_root,
        capture_output=True,
        text=True
        )

        duration = time.time() - start_time
        test_count = self._extract_test_count(result.stdout)

        return {
            'duration': duration,
            'test_count': test_count,
            'tests_per_second': test_count / duration if duration > 0 else 0,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    def _benchmark_database_tests(self) -> dict[str, Any]:
        """Benchmark database-specific tests."""
        print("📊 Benchmarking database tests...")

        start_time = time.time()

        # Run database tests with optimized fixtures
        result = subprocess.run([
            'python', '-m', 'pytest',
            'tests/test_database_connection_optimized.py',
            '-v',
            '--tb=no',
            '--disable-warnings',
            '-n', 'auto'
        ],
        cwd=self.project_root,
        capture_output=True,
        text=True
        )

        duration = time.time() - start_time
        test_count = self._extract_test_count(result.stdout)

        return {
            'duration': duration,
            'test_count': test_count,
            'tests_per_second': test_count / duration if duration > 0 else 0,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    def _benchmark_parallel_tests(self) -> dict[str, Any]:
        """Benchmark parallel test execution."""
        print("📊 Benchmarking parallel test execution...")

        # Test serial vs parallel execution
        serial_time = self._run_serial_tests()
        parallel_time = self._run_parallel_tests()

        speedup = serial_time / parallel_time if parallel_time > 0 else 0

        return {
            'serial_duration': serial_time,
            'parallel_duration': parallel_time,
            'speedup_factor': speedup,
            'performance_gain': ((serial_time - parallel_time) / serial_time * 100) if serial_time > 0 else 0
        }

    def _run_serial_tests(self) -> float:
        """Run tests in serial mode for comparison."""
        start_time = time.time()

        subprocess.run([
            'python', '-m', 'pytest',
            'tests/test_database_connection_optimized.py',
            '--tb=no',
            '--disable-warnings',
            '-q'
        ],
        cwd=self.project_root,
        capture_output=True
        )

        return time.time() - start_time

    def _run_parallel_tests(self) -> float:
        """Run tests in parallel mode for comparison."""
        start_time = time.time()

        subprocess.run([
            'python', '-m', 'pytest',
            'tests/test_database_connection_optimized.py',
            '--tb=no',
            '--disable-warnings',
            '-n', 'auto',
            '--dist=loadfile',
            '-q'
        ],
        cwd=self.project_root,
        capture_output=True
        )

        return time.time() - start_time

    def _extract_test_count(self, stdout: str) -> int:
        """Extract test count from pytest output."""
        try:
            # Look for pattern like "5 passed" or "3 failed"
            import re
            pattern = r'(\d+)\s+(?:passed|failed|skipped)'
            matches = re.findall(pattern, stdout)
            return sum(int(match) for match in matches)
        except Exception:
            return 0

    def _generate_report(self) -> None:
        """Generate comprehensive performance report."""
        print("\n" + "="*60)
        print("🎯 TEST PERFORMANCE BENCHMARK RESULTS")
        print("="*60)

        # Unit tests performance
        unit_results = self.results.get('unit_tests', {})
        if unit_results.get('success'):
            print("📋 Unit Tests:")
            print(f"   Duration: {unit_results.get('duration', 0):.2f}s")
            print(f"   Tests: {unit_results.get('test_count', 0)}")
            print(f"   Speed: {unit_results.get('tests_per_second', 0):.1f} tests/sec")

        # Integration tests performance
        integration_results = self.results.get('integration_tests', {})
        if integration_results.get('success'):
            print("\n🔗 Integration Tests:")
            print(f"   Duration: {integration_results.get('duration', 0):.2f}s")
            print(f"   Tests: {integration_results.get('test_count', 0)}")
            print(f"   Speed: {integration_results.get('tests_per_second', 0):.1f} tests/sec")

        # Database tests performance
        db_results = self.results.get('database_tests', {})
        if db_results.get('success'):
            print("\n💾 Database Tests:")
            print(f"   Duration: {db_results.get('duration', 0):.2f}s")
            print(f"   Tests: {db_results.get('test_count', 0)}")
            print(f"   Speed: {db_results.get('tests_per_second', 0):.1f} tests/sec")

        # Parallel execution performance
        parallel_results = self.results.get('parallel_tests', {})
        if parallel_results:
            print("\n⚡ Parallel Execution:")
            print(f"   Serial Duration: {parallel_results.get('serial_duration', 0):.2f}s")
            print(f"   Parallel Duration: {parallel_results.get('parallel_duration', 0):.2f}s")
            print(f"   Speedup Factor: {parallel_results.get('speedup_factor', 0):.1f}x")
            print(f"   Performance Gain: {parallel_results.get('performance_gain', 0):.1f}%")

        # Overall performance
        total_time = self.results.get('total_time', 0)
        print("\n📊 Overall Performance:")
        print(f"   Total Test Time: {total_time:.2f}s")

        if total_time < 60:
            print("   ✅ Excellent performance! (<1 minute total)")
        elif total_time < 120:
            print("   ✅ Good performance! (<2 minutes total)")
        else:
            print("   ⚠️  Consider further optimizations (>2 minutes total)")

        # Performance targets
        print("\n🎯 Performance Targets:")
        print(f"   Target: <30s unit tests (Current: {unit_results.get('duration', 0):.1f}s)")
        print(f"   Target: <60s integration tests (Current: {integration_results.get('duration', 0):.1f}s)")
        print(f"   Target: >2x parallel speedup (Current: {parallel_results.get('speedup_factor', 0):.1f}x)")

        print("="*60)

        # Save results to file
        results_file = self.project_root / 'performance_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"📁 Results saved to: {results_file}")


def main():
    """Main benchmarking function."""
    benchmark = TestBenchmark()
    results = benchmark.run_benchmark_suite()

    # Exit with appropriate code based on performance
    total_time = results.get('total_time', float('inf'))
    if total_time < 120:  # Less than 2 minutes total
        exit(0)
    else:
        print("⚠️  Performance targets not met. Consider further optimizations.")
        exit(1)


if __name__ == "__main__":
    main()
