"""
Concurrent User Testing Module

Tests system behavior with multiple simultaneous users performing various operations:
- Document uploads
- RAG queries
- Library management
- Mixed workloads
"""

import asyncio
import aiohttp
import pytest
import random
import string
import io
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from .base_performance import (
    PerformanceTestBase,
    LoadTestScenario,
    LoadPattern,
    PerformanceMetrics
)
from .metrics_collector import (
    MetricsCollector,
    PerformanceThresholds,
    PerformanceReport,
    MetricsSnapshot
)


class ConcurrentUserTest(PerformanceTestBase):
    """Test concurrent user scenarios"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__(base_url)
        self.collector = MetricsCollector()
        self.thresholds = PerformanceThresholds(
            max_response_time_ms=2000,
            max_p95_ms=3000,
            max_p99_ms=5000,
            min_throughput_rps=5,
            max_error_rate_percent=5,
            max_memory_mb=2048,
            max_cpu_percent=90
        )
        self.test_files = self._prepare_test_files()
    
    def _prepare_test_files(self) -> List[bytes]:
        """Prepare test PDF files for upload"""
        # Generate simple test PDFs (in reality, use actual PDF files)
        test_files = []
        for i in range(10):
            # Create a simple text file as placeholder
            content = f"Test PDF Content {i}\n" * 100
            test_files.append(content.encode())
        return test_files
    
    def _generate_random_query(self) -> str:
        """Generate random search query"""
        queries = [
            "machine learning algorithms",
            "neural network architecture",
            "deep learning optimization",
            "transformer models",
            "computer vision techniques",
            "natural language processing",
            "reinforcement learning",
            "data preprocessing methods",
            "model evaluation metrics",
            "feature engineering"
        ]
        return random.choice(queries)
    
    async def user_action_upload(self, session: aiohttp.ClientSession, user_id: int):
        """User action: Upload a document"""
        file_content = random.choice(self.test_files)
        
        data = aiohttp.FormData()
        data.add_field('file',
                      io.BytesIO(file_content),
                      filename=f'test_doc_{user_id}_{random.randint(1000, 9999)}.pdf',
                      content_type='application/pdf')
        
        async with session.post(
            f"{self.base_url}/api/documents/upload",
            data=data
        ) as response:
            if response.status != 200:
                raise Exception(f"Upload failed: {response.status}")
            return await response.json()
    
    async def user_action_query(self, session: aiohttp.ClientSession, user_id: int):
        """User action: Perform RAG query"""
        query = self._generate_random_query()
        
        async with session.post(
            f"{self.base_url}/api/rag/query",
            json={"query": query, "k": 5}
        ) as response:
            if response.status != 200:
                raise Exception(f"Query failed: {response.status}")
            return await response.json()
    
    async def user_action_list_documents(self, session: aiohttp.ClientSession, user_id: int):
        """User action: List documents"""
        async with session.get(
            f"{self.base_url}/api/documents"
        ) as response:
            if response.status != 200:
                raise Exception(f"List failed: {response.status}")
            return await response.json()
    
    async def user_action_mixed(self, session: aiohttp.ClientSession, user_id: int):
        """User action: Mixed operations"""
        action = random.choice([
            self.user_action_upload,
            self.user_action_query,
            self.user_action_list_documents
        ])
        return await action(session, user_id)
    
    async def user_action_heavy_query(self, session: aiohttp.ClientSession, user_id: int):
        """User action: Heavy computational query"""
        # Complex query that requires more processing
        query = " ".join([self._generate_random_query() for _ in range(3)])
        
        async with session.post(
            f"{self.base_url}/api/rag/query",
            json={"query": query, "k": 10, "rerank": True}
        ) as response:
            if response.status != 200:
                raise Exception(f"Heavy query failed: {response.status}")
            return await response.json()
    
    async def test_gradual_load_increase(self):
        """Test system with gradually increasing load"""
        scenario = LoadTestScenario(
            name="Gradual Load Increase",
            pattern=LoadPattern.RAMP_UP,
            duration_seconds=300,  # 5 minutes
            max_users=50,
            ramp_up_time=180,  # 3 minute ramp-up
            requests_per_user=10,
            think_time_ms=2000
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_mixed)
        
        # Record metrics
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_spike_load(self):
        """Test system response to sudden load spikes"""
        scenario = LoadTestScenario(
            name="Spike Load Test",
            pattern=LoadPattern.SPIKE,
            duration_seconds=180,  # 3 minutes
            max_users=20,
            spike_multiplier=5.0,  # 5x spike
            requests_per_user=5,
            think_time_ms=1000
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_query)
        
        # Record and analyze
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_sustained_load(self):
        """Test system under sustained load (endurance test)"""
        scenario = LoadTestScenario(
            name="Sustained Load Test",
            pattern=LoadPattern.CONSTANT,
            duration_seconds=600,  # 10 minutes
            max_users=30,
            requests_per_user=100,
            think_time_ms=3000
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_mixed)
        
        # Check for memory leaks or degradation
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_document_upload_storm(self):
        """Test multiple users uploading documents simultaneously"""
        scenario = LoadTestScenario(
            name="Document Upload Storm",
            pattern=LoadPattern.CONSTANT,
            duration_seconds=120,  # 2 minutes
            max_users=25,
            requests_per_user=5,
            think_time_ms=500
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_upload)
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_query_burst(self):
        """Test concurrent RAG queries"""
        scenario = LoadTestScenario(
            name="RAG Query Burst",
            pattern=LoadPattern.STEP,
            duration_seconds=240,  # 4 minutes
            max_users=40,
            step_duration_seconds=60,
            step_increment=10,
            requests_per_user=20,
            think_time_ms=1500
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_query)
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_heavy_computation_load(self):
        """Test system with computationally intensive queries"""
        scenario = LoadTestScenario(
            name="Heavy Computation Load",
            pattern=LoadPattern.CONSTANT,
            duration_seconds=180,  # 3 minutes
            max_users=15,
            requests_per_user=10,
            think_time_ms=5000  # Longer think time for heavy queries
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_heavy_query)
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def test_wave_pattern_load(self):
        """Test system with wave pattern load (simulating daily usage patterns)"""
        scenario = LoadTestScenario(
            name="Wave Pattern Load",
            pattern=LoadPattern.WAVE,
            duration_seconds=360,  # 6 minutes
            max_users=35,
            wave_period_seconds=120,  # 2 minute waves
            requests_per_user=15,
            think_time_ms=2500
        )
        
        metrics = await self.run_scenario(scenario, self.user_action_mixed)
        
        snapshot = MetricsSnapshot(
            timestamp=datetime.now(),
            scenario=scenario.name,
            concurrent_users=metrics.concurrent_users,
            throughput=metrics.throughput,
            avg_response_time=metrics.avg_response_time,
            p50=metrics.p50,
            p95=metrics.p95,
            p99=metrics.p99,
            error_rate=metrics.error_rate,
            memory_mb=metrics.peak_memory_mb,
            cpu_percent=metrics.peak_cpu
        )
        self.collector.record_snapshot(snapshot)
        
        return metrics
    
    async def run_full_test_suite(self):
        """Run complete concurrent user test suite"""
        print("Starting Concurrent User Test Suite")
        print("=" * 80)
        
        test_scenarios = [
            ("Gradual Load Increase", self.test_gradual_load_increase),
            ("Spike Load", self.test_spike_load),
            ("Sustained Load", self.test_sustained_load),
            ("Document Upload Storm", self.test_document_upload_storm),
            ("Query Burst", self.test_query_burst),
            ("Heavy Computation", self.test_heavy_computation_load),
            ("Wave Pattern", self.test_wave_pattern_load)
        ]
        
        results = {}
        
        for name, test_func in test_scenarios:
            print(f"\nRunning: {name}")
            print("-" * 40)
            
            try:
                metrics = await test_func()
                results[name] = metrics
                
                print(f"  Completed: {metrics.success_count + metrics.error_count} requests")
                print(f"  Success Rate: {100 - metrics.error_rate:.2f}%")
                print(f"  Avg Response: {metrics.avg_response_time:.2f}ms")
                print(f"  P95: {metrics.p95:.2f}ms")
                print(f"  Throughput: {metrics.throughput:.2f} req/s")
                
                # Check thresholds
                violations = self.thresholds.validate_metrics({
                    'avg_response_time': metrics.avg_response_time,
                    'p95': metrics.p95,
                    'p99': metrics.p99,
                    'throughput': metrics.throughput,
                    'error_rate': metrics.error_rate,
                    'peak_memory_mb': metrics.peak_memory_mb,
                    'peak_cpu': metrics.peak_cpu
                })
                
                if violations:
                    print("\n  Threshold Violations:")
                    for violation in violations:
                        print(f"    - {violation}")
                
            except Exception as e:
                print(f"  Error: {e}")
                results[name] = None
        
        # Generate report
        report = PerformanceReport(self.collector, self.thresholds)
        summary = report.generate_summary(list(results.keys()))
        print("\n" + summary)
        
        # Export results
        self.collector.export_metrics(format="json")
        
        # Generate HTML report
        html_report = report.generate_html_report(list(results.keys()))
        with open("performance_report.html", "w") as f:
            f.write(html_report)
        
        print("\nReports generated:")
        print("  - performance_report.html")
        print("  - metrics_export_*.json")
        
        return results


# Pytest fixtures and test functions
@pytest.fixture
async def concurrent_test():
    """Fixture for concurrent user testing"""
    return ConcurrentUserTest()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_gradual_load(concurrent_test):
    """Test gradual load increase"""
    metrics = await concurrent_test.test_gradual_load_increase()
    
    assert metrics.error_rate < 5.0, f"Error rate too high: {metrics.error_rate}%"
    assert metrics.avg_response_time < 2000, f"Response time too high: {metrics.avg_response_time}ms"
    assert metrics.throughput > 5, f"Throughput too low: {metrics.throughput} req/s"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_spike_recovery(concurrent_test):
    """Test system recovery from load spikes"""
    metrics = await concurrent_test.test_spike_load()
    
    # Allow higher error rate during spikes but should recover
    assert metrics.error_rate < 10.0, f"Error rate too high during spike: {metrics.error_rate}%"
    assert metrics.p99 < 10000, f"P99 too high during spike: {metrics.p99}ms"


@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.slow
async def test_concurrent_endurance(concurrent_test):
    """Test system endurance under sustained load"""
    metrics = await concurrent_test.test_sustained_load()
    
    # Check for stability over time
    assert metrics.error_rate < 3.0, f"Error rate degraded: {metrics.error_rate}%"
    
    # Check for memory leaks (memory should stabilize)
    memory_samples = metrics.memory_usage_mb[-10:]  # Last 10 samples
    if len(memory_samples) > 1:
        memory_growth = memory_samples[-1] - memory_samples[0]
        assert memory_growth < 100, f"Potential memory leak: {memory_growth}MB growth"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_document_upload_concurrency(concurrent_test):
    """Test concurrent document uploads"""
    metrics = await concurrent_test.test_document_upload_storm()
    
    assert metrics.error_rate < 5.0, f"Upload error rate too high: {metrics.error_rate}%"
    assert metrics.throughput > 2, f"Upload throughput too low: {metrics.throughput} req/s"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_query_concurrency(concurrent_test):
    """Test concurrent RAG queries"""
    metrics = await concurrent_test.test_query_burst()
    
    assert metrics.error_rate < 5.0, f"Query error rate too high: {metrics.error_rate}%"
    assert metrics.p95 < 5000, f"Query P95 too high: {metrics.p95}ms"


if __name__ == "__main__":
    # Run full test suite
    async def main():
        test = ConcurrentUserTest()
        await test.run_full_test_suite()
    
    asyncio.run(main())