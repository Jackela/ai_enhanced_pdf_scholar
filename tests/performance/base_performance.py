"""
Base Performance Testing Framework

Provides core infrastructure for performance testing including:
- Concurrent user simulation
- Metrics collection
- Load scenario management
- Performance benchmarking
"""

import asyncio
import time
import statistics
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import aiohttp
import psutil
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
from enum import Enum

T = TypeVar('T')


class LoadPattern(Enum):
    """Load testing patterns"""
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    STEP = "step"
    WAVE = "wave"
    RANDOM = "random"


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    response_times: List[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    throughput: float = 0.0
    concurrent_users: int = 0

    # Memory metrics
    memory_usage_mb: List[float] = field(default_factory=list)
    peak_memory_mb: float = 0.0

    # CPU metrics
    cpu_percent: List[float] = field(default_factory=list)
    peak_cpu: float = 0.0

    # Response time percentiles
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0

    # Timestamps
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def calculate_percentiles(self):
        """Calculate response time percentiles"""
        if self.response_times:
            self.p50 = np.percentile(self.response_times, 50)
            self.p95 = np.percentile(self.response_times, 95)
            self.p99 = np.percentile(self.response_times, 99)

    def calculate_throughput(self):
        """Calculate requests per second"""
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            if duration > 0:
                total_requests = self.success_count + self.error_count
                self.throughput = total_requests / duration

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage"""
        total = self.success_count + self.error_count
        return (self.error_count / total * 100) if total > 0 else 0

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time"""
        return statistics.mean(self.response_times) if self.response_times else 0

    @property
    def std_response_time(self) -> float:
        """Calculate standard deviation of response times"""
        return statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0


@dataclass
class LoadTestScenario:
    """Configuration for a load test scenario"""
    name: str
    pattern: LoadPattern
    duration_seconds: int
    max_users: int
    ramp_up_time: int = 0
    requests_per_user: int = 10
    think_time_ms: int = 1000
    timeout_seconds: int = 30

    # Advanced configuration
    spike_multiplier: float = 3.0
    wave_period_seconds: int = 60
    step_duration_seconds: int = 30
    step_increment: int = 10

    def get_user_count_at_time(self, elapsed_seconds: float) -> int:
        """Calculate number of users at given time based on pattern"""
        if self.pattern == LoadPattern.CONSTANT:
            return self.max_users

        elif self.pattern == LoadPattern.RAMP_UP:
            if elapsed_seconds >= self.ramp_up_time:
                return self.max_users
            return int((elapsed_seconds / self.ramp_up_time) * self.max_users)

        elif self.pattern == LoadPattern.SPIKE:
            # Spike at 50% duration
            spike_time = self.duration_seconds / 2
            if abs(elapsed_seconds - spike_time) < 5:
                return int(self.max_users * self.spike_multiplier)
            return self.max_users

        elif self.pattern == LoadPattern.STEP:
            step_number = int(elapsed_seconds / self.step_duration_seconds)
            return min(self.step_increment * (step_number + 1), self.max_users)

        elif self.pattern == LoadPattern.WAVE:
            # Sinusoidal wave pattern
            import math
            amplitude = self.max_users / 2
            frequency = 2 * math.pi / self.wave_period_seconds
            return int(amplitude + amplitude * math.sin(frequency * elapsed_seconds))

        elif self.pattern == LoadPattern.RANDOM:
            import random
            return random.randint(1, self.max_users)

        return self.max_users


class ConcurrentUserSimulator:
    """Simulates concurrent user behavior"""

    def __init__(self, base_url: str, scenario: LoadTestScenario):
        self.base_url = base_url
        self.scenario = scenario
        self.metrics = PerformanceMetrics()
        self.active_users = 0
        self.stop_flag = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.scenario.timeout_seconds)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()

    async def simulate_user(self, user_id: int, action: Callable):
        """Simulate a single user performing actions"""
        while not self.stop_flag:
            try:
                # Record start time
                start_time = time.perf_counter()

                # Execute user action
                await action(self._session, user_id)

                # Record response time
                response_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
                self.metrics.response_times.append(response_time)
                self.metrics.success_count += 1

                # Think time
                await asyncio.sleep(self.scenario.think_time_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.metrics.error_count += 1
                print(f"User {user_id} error: {e}")

    async def run_load_test(self, action: Callable) -> PerformanceMetrics:
        """Execute the load test scenario"""
        self.metrics.start_time = datetime.now()
        start_time = time.perf_counter()

        # Start resource monitoring
        monitor_task = asyncio.create_task(self._monitor_resources())

        # User tasks container
        user_tasks = []

        try:
            while (time.perf_counter() - start_time) < self.scenario.duration_seconds:
                elapsed = time.perf_counter() - start_time
                target_users = self.scenario.get_user_count_at_time(elapsed)

                # Add users if needed
                while self.active_users < target_users:
                    user_id = self.active_users
                    task = asyncio.create_task(self.simulate_user(user_id, action))
                    user_tasks.append(task)
                    self.active_users += 1

                # Remove users if needed
                while self.active_users > target_users and user_tasks:
                    task = user_tasks.pop()
                    task.cancel()
                    self.active_users -= 1

                self.metrics.concurrent_users = self.active_users
                await asyncio.sleep(0.1)  # Check interval

        finally:
            # Stop all user tasks
            self.stop_flag = True
            for task in user_tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*user_tasks, return_exceptions=True)

            # Stop monitoring
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)

            # Finalize metrics
            self.metrics.end_time = datetime.now()
            self.metrics.calculate_percentiles()
            self.metrics.calculate_throughput()

        return self.metrics

    async def _monitor_resources(self):
        """Monitor system resources during test"""
        process = psutil.Process()

        while not self.stop_flag:
            try:
                # Memory usage
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.metrics.memory_usage_mb.append(memory_mb)
                self.metrics.peak_memory_mb = max(self.metrics.peak_memory_mb, memory_mb)

                # CPU usage
                cpu_percent = process.cpu_percent()
                self.metrics.cpu_percent.append(cpu_percent)
                self.metrics.peak_cpu = max(self.metrics.peak_cpu, cpu_percent)

                await asyncio.sleep(1)  # Monitor interval

            except asyncio.CancelledError:
                break


class PerformanceTestBase:
    """Base class for performance tests"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: Dict[str, PerformanceMetrics] = {}

    async def run_scenario(
        self,
        scenario: LoadTestScenario,
        action: Callable
    ) -> PerformanceMetrics:
        """Run a single load test scenario"""
        async with ConcurrentUserSimulator(self.base_url, scenario) as simulator:
            metrics = await simulator.run_load_test(action)
            self.results[scenario.name] = metrics
            return metrics

    async def run_benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ) -> Dict[str, float]:
        """Run performance benchmark"""
        # Warmup
        for _ in range(warmup):
            await func()

        # Actual benchmark
        times = []
        memory_snapshots = []

        for _ in range(iterations):
            # Memory snapshot
            tracemalloc.start()

            # Time execution
            start = time.perf_counter()
            await func()
            elapsed = (time.perf_counter() - start) * 1000  # ms

            # Memory usage
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            times.append(elapsed)
            memory_snapshots.append(peak / 1024 / 1024)  # MB

        return {
            "name": name,
            "iterations": iterations,
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "min_ms": min(times),
            "max_ms": max(times),
            "p95_ms": np.percentile(times, 95),
            "p99_ms": np.percentile(times, 99),
            "peak_memory_mb": max(memory_snapshots),
            "avg_memory_mb": statistics.mean(memory_snapshots)
        }

    @asynccontextmanager
    async def measure_performance(self, name: str):
        """Context manager for measuring performance"""
        start_time = time.perf_counter()
        tracemalloc.start()

        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start_time) * 1000
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print(f"\n{name} Performance:")
            print(f"  Time: {elapsed:.2f}ms")
            print(f"  Memory: {peak / 1024 / 1024:.2f}MB")

    def generate_report(self) -> str:
        """Generate performance test report"""
        report = []
        report.append("=" * 80)
        report.append("PERFORMANCE TEST REPORT")
        report.append("=" * 80)

        for scenario_name, metrics in self.results.items():
            report.append(f"\nScenario: {scenario_name}")
            report.append("-" * 40)
            report.append(f"Duration: {metrics.end_time - metrics.start_time}")
            report.append(f"Total Requests: {metrics.success_count + metrics.error_count}")
            report.append(f"Success Rate: {100 - metrics.error_rate:.2f}%")
            report.append(f"Throughput: {metrics.throughput:.2f} req/s")
            report.append(f"Concurrent Users: {metrics.concurrent_users}")
            report.append(f"\nResponse Times:")
            report.append(f"  Average: {metrics.avg_response_time:.2f}ms")
            report.append(f"  Std Dev: {metrics.std_response_time:.2f}ms")
            report.append(f"  P50: {metrics.p50:.2f}ms")
            report.append(f"  P95: {metrics.p95:.2f}ms")
            report.append(f"  P99: {metrics.p99:.2f}ms")
            report.append(f"\nResource Usage:")
            report.append(f"  Peak Memory: {metrics.peak_memory_mb:.2f}MB")
            report.append(f"  Peak CPU: {metrics.peak_cpu:.2f}%")

        report.append("\n" + "=" * 80)
        return "\n".join(report)