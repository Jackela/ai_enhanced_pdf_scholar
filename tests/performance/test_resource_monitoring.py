"""
Resource Monitoring and Memory Testing Module

Monitors system resources during load tests:
- Memory usage and leak detection
- CPU utilization
- Database connection pool monitoring
- File handle tracking
- Network bandwidth usage
"""

import asyncio
import psutil
import tracemalloc
import gc
import time
import pytest
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import weakref
import sys
import os
from pathlib import Path
import sqlite3
import json

from .base_performance import PerformanceTestBase
from .metrics_collector import MetricsCollector


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time"""
    timestamp: datetime
    memory_rss_mb: float
    memory_vms_mb: float
    memory_percent: float
    cpu_percent: float
    cpu_count: int
    thread_count: int
    open_files: int
    open_connections: int
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float

    # Python-specific metrics
    gc_objects: int
    gc_collections: Dict[int, int]
    tracemalloc_current_mb: float
    tracemalloc_peak_mb: float


@dataclass
class MemoryLeakDetector:
    """Detects potential memory leaks"""
    baseline_memory_mb: float = 0.0
    growth_threshold_mb: float = 100.0
    growth_rate_threshold: float = 0.1  # 10% growth per minute
    samples: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    def add_sample(self, memory_mb: float):
        """Add memory sample"""
        self.samples.append(memory_mb)
        self.timestamps.append(datetime.now())

        # Keep only last 100 samples
        if len(self.samples) > 100:
            self.samples.pop(0)
            self.timestamps.pop(0)

    def detect_leak(self) -> Tuple[bool, str]:
        """Detect if there's a memory leak"""
        if len(self.samples) < 10:
            return False, "Not enough samples"

        # Check absolute growth
        current = self.samples[-1]
        if self.baseline_memory_mb > 0:
            growth = current - self.baseline_memory_mb
            if growth > self.growth_threshold_mb:
                return True, f"Memory grew by {growth:.2f}MB"

        # Check growth rate over last minute
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        recent_samples = []
        for i, ts in enumerate(self.timestamps):
            if ts >= one_minute_ago:
                recent_samples.append(self.samples[i])

        if len(recent_samples) >= 2:
            growth_rate = (recent_samples[-1] - recent_samples[0]) / recent_samples[0]
            if growth_rate > self.growth_rate_threshold:
                return True, f"Memory growing at {growth_rate*100:.1f}% per minute"

        # Check for consistent upward trend
        if len(self.samples) >= 20:
            # Simple linear regression
            x = list(range(len(self.samples)))
            y = self.samples
            n = len(x)

            x_mean = sum(x) / n
            y_mean = sum(y) / n

            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator > 0:
                slope = numerator / denominator
                # If slope is consistently positive and significant
                if slope > 0.5:  # 0.5 MB per sample
                    return True, f"Consistent memory growth detected (slope: {slope:.2f}MB/sample)"

        return False, "No leak detected"


class ResourceMonitor:
    """Monitors system resources during tests"""

    def __init__(self, interval_seconds: float = 1.0):
        self.interval = interval_seconds
        self.process = psutil.Process()
        self.snapshots: List[ResourceSnapshot] = []
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.leak_detector = MemoryLeakDetector()

        # Initialize counters
        self.initial_disk_io = self.process.io_counters() if hasattr(self.process, 'io_counters') else None
        self.initial_net_io = psutil.net_io_counters()

    def start_monitoring(self):
        """Start resource monitoring in background thread"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        # Start memory tracking
        tracemalloc.start()

        # Set baseline
        self.leak_detector.baseline_memory_mb = self.process.memory_info().rss / 1024 / 1024

    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        # Stop memory tracking
        tracemalloc.stop()

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)

                # Check for memory leaks
                self.leak_detector.add_sample(snapshot.memory_rss_mb)

                time.sleep(self.interval)
            except Exception as e:
                print(f"Monitoring error: {e}")

    def _take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resources"""
        # Memory metrics
        mem_info = self.process.memory_info()
        mem_percent = self.process.memory_percent()

        # CPU metrics
        cpu_percent = self.process.cpu_percent()
        cpu_count = psutil.cpu_count()

        # Thread and file metrics
        thread_count = self.process.num_threads()
        try:
            open_files = len(self.process.open_files())
        except:
            open_files = 0

        try:
            open_connections = len(self.process.connections())
        except:
            open_connections = 0

        # Disk I/O
        disk_io_read_mb = 0
        disk_io_write_mb = 0
        if hasattr(self.process, 'io_counters'):
            current_io = self.process.io_counters()
            if self.initial_disk_io:
                disk_io_read_mb = (current_io.read_bytes - self.initial_disk_io.read_bytes) / 1024 / 1024
                disk_io_write_mb = (current_io.write_bytes - self.initial_disk_io.write_bytes) / 1024 / 1024

        # Network I/O
        current_net = psutil.net_io_counters()
        network_sent_mb = (current_net.bytes_sent - self.initial_net_io.bytes_sent) / 1024 / 1024
        network_recv_mb = (current_net.bytes_recv - self.initial_net_io.bytes_recv) / 1024 / 1024

        # Python-specific metrics
        gc_stats = gc.get_stats()
        gc_collections = {i: gc.get_count()[i] for i in range(len(gc.get_count()))}
        gc_objects = len(gc.get_objects())

        # Tracemalloc metrics
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc_current_mb = current / 1024 / 1024
            tracemalloc_peak_mb = peak / 1024 / 1024
        else:
            tracemalloc_current_mb = 0
            tracemalloc_peak_mb = 0

        return ResourceSnapshot(
            timestamp=datetime.now(),
            memory_rss_mb=mem_info.rss / 1024 / 1024,
            memory_vms_mb=mem_info.vms / 1024 / 1024,
            memory_percent=mem_percent,
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            thread_count=thread_count,
            open_files=open_files,
            open_connections=open_connections,
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            gc_objects=gc_objects,
            gc_collections=gc_collections,
            tracemalloc_current_mb=tracemalloc_current_mb,
            tracemalloc_peak_mb=tracemalloc_peak_mb
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of resource usage"""
        if not self.snapshots:
            return {}

        memory_samples = [s.memory_rss_mb for s in self.snapshots]
        cpu_samples = [s.cpu_percent for s in self.snapshots]

        # Detect memory leak
        leak_detected, leak_reason = self.leak_detector.detect_leak()

        return {
            "duration": (self.snapshots[-1].timestamp - self.snapshots[0].timestamp).total_seconds(),
            "samples": len(self.snapshots),
            "memory": {
                "initial_mb": memory_samples[0] if memory_samples else 0,
                "final_mb": memory_samples[-1] if memory_samples else 0,
                "peak_mb": max(memory_samples) if memory_samples else 0,
                "average_mb": sum(memory_samples) / len(memory_samples) if memory_samples else 0,
                "growth_mb": (memory_samples[-1] - memory_samples[0]) if memory_samples else 0,
                "leak_detected": leak_detected,
                "leak_reason": leak_reason
            },
            "cpu": {
                "average_percent": sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0,
                "peak_percent": max(cpu_samples) if cpu_samples else 0,
                "min_percent": min(cpu_samples) if cpu_samples else 0
            },
            "threads": {
                "peak": max(s.thread_count for s in self.snapshots),
                "average": sum(s.thread_count for s in self.snapshots) / len(self.snapshots)
            },
            "files": {
                "peak_open": max(s.open_files for s in self.snapshots),
                "average_open": sum(s.open_files for s in self.snapshots) / len(self.snapshots)
            },
            "connections": {
                "peak_open": max(s.open_connections for s in self.snapshots),
                "average_open": sum(s.open_connections for s in self.snapshots) / len(self.snapshots)
            },
            "io": {
                "total_disk_read_mb": self.snapshots[-1].disk_io_read_mb if self.snapshots else 0,
                "total_disk_write_mb": self.snapshots[-1].disk_io_write_mb if self.snapshots else 0,
                "total_network_sent_mb": self.snapshots[-1].network_sent_mb if self.snapshots else 0,
                "total_network_recv_mb": self.snapshots[-1].network_recv_mb if self.snapshots else 0
            },
            "gc": {
                "total_objects": self.snapshots[-1].gc_objects if self.snapshots else 0,
                "collections": self.snapshots[-1].gc_collections if self.snapshots else {}
            }
        }


class DatabaseConnectionMonitor:
    """Monitors database connection pool usage"""

    def __init__(self, db_path: str = "scholar.db"):
        self.db_path = db_path
        self.samples: List[Dict[str, Any]] = []

    def check_connections(self) -> Dict[str, Any]:
        """Check current database connections"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get SQLite internal stats
            cursor.execute("PRAGMA database_list")
            databases = cursor.fetchall()

            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]

            conn.close()

            return {
                "timestamp": datetime.now().isoformat(),
                "databases": len(databases),
                "page_count": page_count,
                "page_size": page_size,
                "cache_size": cache_size,
                "estimated_size_mb": (page_count * page_size) / 1024 / 1024
            }
        except Exception as e:
            return {"error": str(e)}

    def monitor_pool(self, duration_seconds: int = 60, interval: float = 1.0):
        """Monitor connection pool for specified duration"""
        start_time = time.time()

        while (time.time() - start_time) < duration_seconds:
            sample = self.check_connections()
            self.samples.append(sample)
            time.sleep(interval)

        return self.get_pool_summary()

    def get_pool_summary(self) -> Dict[str, Any]:
        """Get summary of connection pool usage"""
        if not self.samples:
            return {}

        valid_samples = [s for s in self.samples if "error" not in s]

        if not valid_samples:
            return {"error": "No valid samples collected"}

        return {
            "total_samples": len(self.samples),
            "valid_samples": len(valid_samples),
            "avg_page_count": sum(s["page_count"] for s in valid_samples) / len(valid_samples),
            "max_page_count": max(s["page_count"] for s in valid_samples),
            "avg_cache_size": sum(s["cache_size"] for s in valid_samples) / len(valid_samples),
            "database_growth_mb": (
                valid_samples[-1]["estimated_size_mb"] - valid_samples[0]["estimated_size_mb"]
                if len(valid_samples) > 1 else 0
            )
        }


class ResourceTestSuite(PerformanceTestBase):
    """Comprehensive resource testing suite"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__(base_url)
        self.resource_monitor = ResourceMonitor()
        self.db_monitor = DatabaseConnectionMonitor()

    async def test_memory_under_load(self, duration_seconds: int = 60):
        """Test memory usage under sustained load"""
        print("Testing memory usage under load...")

        # Start monitoring
        self.resource_monitor.start_monitoring()

        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            request_count = 0

            while (time.time() - start_time) < duration_seconds:
                # Make various requests
                tasks = []
                for _ in range(10):
                    tasks.append(self._make_request(session))

                await asyncio.gather(*tasks, return_exceptions=True)
                request_count += len(tasks)

                # Small delay
                await asyncio.sleep(0.1)

        # Stop monitoring
        self.resource_monitor.stop_monitoring()

        # Get results
        summary = self.resource_monitor.get_summary()
        summary["request_count"] = request_count

        return summary

    async def _make_request(self, session: aiohttp.ClientSession):
        """Make a random request"""
        endpoints = [
            ("GET", "/api/documents"),
            ("GET", "/health"),
            ("POST", "/api/rag/query", {"query": "test", "k": 5})
        ]

        import random
        method, path, data = random.choice(endpoints + [(endpoints[0][0], endpoints[0][1], None)])

        url = f"{self.base_url}{path}"

        if method == "GET":
            async with session.get(url) as response:
                await response.read()
        else:
            async with session.post(url, json=data) as response:
                await response.read()

    async def test_memory_leak_detection(self):
        """Test for memory leaks during extended operation"""
        print("Testing for memory leaks...")

        # Start monitoring
        self.resource_monitor.start_monitoring()

        # Run garbage collection to establish baseline
        gc.collect()
        await asyncio.sleep(2)

        # Perform operations that might leak memory
        for iteration in range(5):
            print(f"  Iteration {iteration + 1}/5")

            async with aiohttp.ClientSession() as session:
                # Create many objects
                tasks = []
                for _ in range(100):
                    tasks.append(self._make_request(session))

                await asyncio.gather(*tasks, return_exceptions=True)

            # Force garbage collection
            gc.collect()
            await asyncio.sleep(2)

        # Stop monitoring
        self.resource_monitor.stop_monitoring()

        # Analyze results
        summary = self.resource_monitor.get_summary()

        # Check for leak
        if summary["memory"]["leak_detected"]:
            print(f"  WARNING: Potential memory leak detected!")
            print(f"  Reason: {summary['memory']['leak_reason']}")
            print(f"  Memory growth: {summary['memory']['growth_mb']:.2f}MB")
        else:
            print(f"  No memory leak detected")
            print(f"  Memory growth: {summary['memory']['growth_mb']:.2f}MB")

        return summary

    async def test_resource_cleanup(self):
        """Test that resources are properly cleaned up"""
        print("Testing resource cleanup...")

        # Track weak references to objects
        objects_to_track = []
        weak_refs = []

        # Create objects and track them
        async with aiohttp.ClientSession() as session:
            for _ in range(10):
                response = await session.get(f"{self.base_url}/health")
                data = await response.json()
                objects_to_track.append(data)
                weak_refs.append(weakref.ref(data))

        # Objects should be garbage collected after scope
        del objects_to_track
        gc.collect()

        # Check if objects were cleaned up
        alive_count = sum(1 for ref in weak_refs if ref() is not None)

        results = {
            "total_tracked": len(weak_refs),
            "still_alive": alive_count,
            "cleanup_rate": ((len(weak_refs) - alive_count) / len(weak_refs)) * 100
        }

        print(f"  Cleanup rate: {results['cleanup_rate']:.1f}%")

        return results

    async def test_database_connections(self):
        """Test database connection handling under load"""
        print("Testing database connections...")

        # Start DB monitoring in background
        import threading
        monitor_thread = threading.Thread(
            target=self.db_monitor.monitor_pool,
            args=(30, 1.0)
        )
        monitor_thread.start()

        # Generate database load
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(50):
                tasks.append(session.get(f"{self.base_url}/api/documents"))
                tasks.append(session.get(f"{self.base_url}/api/citations"))

            await asyncio.gather(*[
                self._execute_request(task) for task in tasks
            ], return_exceptions=True)

        # Wait for monitoring to complete
        monitor_thread.join()

        # Get results
        summary = self.db_monitor.get_pool_summary()

        print(f"  Database growth: {summary.get('database_growth_mb', 0):.2f}MB")
        print(f"  Max page count: {summary.get('max_page_count', 0)}")

        return summary

    async def _execute_request(self, request_coro):
        """Execute a request coroutine"""
        async with request_coro as response:
            await response.read()

    async def test_cpu_usage_patterns(self):
        """Test CPU usage patterns under different loads"""
        print("Testing CPU usage patterns...")

        patterns = {
            "idle": [],
            "light": [],
            "moderate": [],
            "heavy": []
        }

        # Test idle
        self.resource_monitor.start_monitoring()
        await asyncio.sleep(5)
        self.resource_monitor.stop_monitoring()
        patterns["idle"] = [s.cpu_percent for s in self.resource_monitor.snapshots]
        self.resource_monitor.snapshots.clear()

        # Test light load
        self.resource_monitor.start_monitoring()
        async with aiohttp.ClientSession() as session:
            for _ in range(10):
                await session.get(f"{self.base_url}/health")
                await asyncio.sleep(0.5)
        self.resource_monitor.stop_monitoring()
        patterns["light"] = [s.cpu_percent for s in self.resource_monitor.snapshots]
        self.resource_monitor.snapshots.clear()

        # Test moderate load
        self.resource_monitor.start_monitoring()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(20):
                tasks.append(session.get(f"{self.base_url}/api/documents"))
            await asyncio.gather(*[self._execute_request(t) for t in tasks])
        self.resource_monitor.stop_monitoring()
        patterns["moderate"] = [s.cpu_percent for s in self.resource_monitor.snapshots]
        self.resource_monitor.snapshots.clear()

        # Test heavy load
        self.resource_monitor.start_monitoring()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(50):
                tasks.append(session.post(
                    f"{self.base_url}/api/rag/query",
                    json={"query": "complex query", "k": 10}
                ))
            await asyncio.gather(*[self._execute_request(t) for t in tasks],
                               return_exceptions=True)
        self.resource_monitor.stop_monitoring()
        patterns["heavy"] = [s.cpu_percent for s in self.resource_monitor.snapshots]

        # Analyze patterns
        results = {}
        for pattern_name, samples in patterns.items():
            if samples:
                results[pattern_name] = {
                    "avg_cpu": sum(samples) / len(samples),
                    "peak_cpu": max(samples),
                    "min_cpu": min(samples)
                }

        return results

    async def run_full_resource_test(self):
        """Run complete resource test suite"""
        print("Running Full Resource Test Suite")
        print("=" * 80)

        results = {}

        # Test 1: Memory under load
        print("\n1. Memory Under Load Test")
        results["memory_load"] = await self.test_memory_under_load(duration_seconds=30)

        # Test 2: Memory leak detection
        print("\n2. Memory Leak Detection")
        results["memory_leak"] = await self.test_memory_leak_detection()

        # Test 3: Resource cleanup
        print("\n3. Resource Cleanup Test")
        results["resource_cleanup"] = await self.test_resource_cleanup()

        # Test 4: Database connections
        print("\n4. Database Connection Test")
        results["database"] = await self.test_database_connections()

        # Test 5: CPU patterns
        print("\n5. CPU Usage Pattern Test")
        results["cpu_patterns"] = await self.test_cpu_usage_patterns()

        # Generate report
        self._generate_resource_report(results)

        return results

    def _generate_resource_report(self, results: Dict[str, Any]):
        """Generate resource test report"""
        print("\n" + "=" * 80)
        print("RESOURCE TEST SUMMARY")
        print("=" * 80)

        # Memory results
        if "memory_load" in results:
            mem = results["memory_load"]["memory"]
            print(f"\nMemory Usage:")
            print(f"  Initial: {mem['initial_mb']:.2f}MB")
            print(f"  Final: {mem['final_mb']:.2f}MB")
            print(f"  Peak: {mem['peak_mb']:.2f}MB")
            print(f"  Growth: {mem['growth_mb']:.2f}MB")
            if mem["leak_detected"]:
                print(f"  ⚠ LEAK DETECTED: {mem['leak_reason']}")

        # CPU results
        if "cpu_patterns" in results:
            print(f"\nCPU Usage Patterns:")
            for pattern, stats in results["cpu_patterns"].items():
                print(f"  {pattern.capitalize()}:")
                print(f"    Average: {stats['avg_cpu']:.1f}%")
                print(f"    Peak: {stats['peak_cpu']:.1f}%")

        # Database results
        if "database" in results:
            db = results["database"]
            print(f"\nDatabase:")
            print(f"  Growth: {db.get('database_growth_mb', 0):.2f}MB")
            print(f"  Max Pages: {db.get('max_page_count', 0)}")

        # Resource cleanup
        if "resource_cleanup" in results:
            cleanup = results["resource_cleanup"]
            print(f"\nResource Cleanup:")
            print(f"  Cleanup Rate: {cleanup['cleanup_rate']:.1f}%")

        print("\n" + "=" * 80)


# Pytest test functions
@pytest.fixture
async def resource_suite():
    """Fixture for resource testing"""
    return ResourceTestSuite()


@pytest.mark.asyncio
@pytest.mark.resource
async def test_memory_stability(resource_suite):
    """Test memory stability under load"""
    results = await resource_suite.test_memory_under_load(duration_seconds=10)

    assert results["memory"]["growth_mb"] < 50, f"Excessive memory growth: {results['memory']['growth_mb']}MB"
    assert not results["memory"]["leak_detected"], f"Memory leak detected: {results['memory']['leak_reason']}"


@pytest.mark.asyncio
@pytest.mark.resource
async def test_resource_cleanup_efficiency(resource_suite):
    """Test resource cleanup efficiency"""
    results = await resource_suite.test_resource_cleanup()

    assert results["cleanup_rate"] > 90, f"Poor cleanup rate: {results['cleanup_rate']:.1f}%"


@pytest.mark.asyncio
@pytest.mark.resource
async def test_cpu_usage_reasonable(resource_suite):
    """Test that CPU usage is reasonable"""
    results = await resource_suite.test_cpu_usage_patterns()

    # Check that heavy load doesn't exceed reasonable CPU usage
    if "heavy" in results:
        assert results["heavy"]["avg_cpu"] < 80, f"CPU usage too high: {results['heavy']['avg_cpu']:.1f}%"


if __name__ == "__main__":
    # Run full resource test suite
    async def main():
        suite = ResourceTestSuite()
        await suite.run_full_resource_test()

    asyncio.run(main())