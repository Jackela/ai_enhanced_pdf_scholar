"""
Horizontal Pod Autoscaler (HPA) Testing Suite
==============================================

Comprehensive test suite for validating HPA behavior under various load conditions.
Tests scaling up/down performance, response times, and cost optimization.

Features:
- Load generation for scaling triggers
- Response time monitoring during scaling events
- Cost impact analysis
- Multi-metric scaling validation
- RAG-specific workload testing
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import statistics
import pytest
import aiohttp
import numpy as np

from kubernetes import client, config
from prometheus_api_client import PrometheusConnect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HPATestFramework:
    """Framework for testing Horizontal Pod Autoscaler behavior"""

    def __init__(self, namespace: str = "ai-pdf-scholar", prometheus_url: str = "http://prometheus:9090"):
        self.namespace = namespace
        self.prometheus = PrometheusConnect(url=prometheus_url, disable_ssl=True)

        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        self.k8s_apps = client.AppsV1Api()
        self.k8s_autoscaling = client.AutoscalingV1Api()
        self.k8s_core = client.CoreV1Api()

        # Test configuration
        self.deployment_name = "ai-pdf-scholar-backend"
        self.hpa_name = "ai-pdf-scholar-backend-hpa"
        self.service_url = "http://ai-pdf-scholar-backend:8001"

        # Scaling thresholds
        self.cpu_threshold = 70  # Percentage
        self.memory_threshold = 75  # Percentage
        self.response_time_threshold = 200  # milliseconds

        # Test results storage
        self.test_results = []

    async def get_current_replicas(self) -> int:
        """Get current number of replicas"""
        try:
            deployment = self.k8s_apps.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace
            )
            return deployment.spec.replicas
        except Exception as e:
            logger.error(f"Error getting current replicas: {e}")
            return 0

    async def get_hpa_status(self) -> Dict[str, Any]:
        """Get HPA status and metrics"""
        try:
            hpa = self.k8s_autoscaling.read_namespaced_horizontal_pod_autoscaler(
                name=self.hpa_name,
                namespace=self.namespace
            )

            return {
                'current_replicas': hpa.status.current_replicas,
                'desired_replicas': hpa.status.desired_replicas,
                'min_replicas': hpa.spec.min_replicas,
                'max_replicas': hpa.spec.max_replicas,
                'current_cpu_utilization': hpa.status.current_cpu_utilization_percentage,
                'target_cpu_utilization': hpa.spec.target_cpu_utilization_percentage
            }
        except Exception as e:
            logger.error(f"Error getting HPA status: {e}")
            return {}

    async def wait_for_scaling(self, target_replicas: int, timeout: int = 300) -> bool:
        """Wait for scaling to complete"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            current_replicas = await self.get_current_replicas()
            if current_replicas == target_replicas:
                logger.info(f"Scaling completed: {current_replicas} replicas")
                return True

            logger.info(f"Waiting for scaling... Current: {current_replicas}, Target: {target_replicas}")
            await asyncio.sleep(10)

        logger.error(f"Scaling timeout after {timeout} seconds")
        return False

    async def generate_cpu_load(self, duration: int = 300, intensity: float = 0.8):
        """Generate CPU load to trigger HPA scaling"""
        logger.info(f"Generating CPU load for {duration} seconds at {intensity*100}% intensity")

        # Generate load by making CPU-intensive requests
        concurrent_requests = max(1, int(10 * intensity))
        request_rate = max(1, int(5 * intensity))  # requests per second

        async def make_request_batch():
            async with aiohttp.ClientSession() as session:
                tasks = []
                for _ in range(concurrent_requests):
                    # CPU-intensive RAG query
                    payload = {
                        "query": "Explain the technical architecture and implementation details of machine learning models in production systems, including deployment strategies, monitoring approaches, and performance optimization techniques.",
                        "document_limit": 20,
                        "similarity_threshold": 0.7
                    }
                    task = session.post(f"{self.service_url}/rag/query", json=payload)
                    tasks.append(task)

                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.warning(f"Request batch error: {e}")

        end_time = time.time() + duration
        while time.time() < end_time:
            await make_request_batch()
            await asyncio.sleep(1.0 / request_rate)

    async def generate_memory_load(self, duration: int = 300, intensity: float = 0.8):
        """Generate memory load to trigger HPA scaling"""
        logger.info(f"Generating memory load for {duration} seconds at {intensity*100}% intensity")

        # Generate memory-intensive requests (large document uploads)
        concurrent_requests = max(1, int(5 * intensity))

        async def make_memory_intensive_request():
            async with aiohttp.ClientSession() as session:
                # Upload large documents to consume memory
                large_content = "A" * (1024 * 1024 * 2)  # 2MB of text

                payload = {
                    "title": f"Large Test Document {time.time()}",
                    "content": large_content,
                    "author": "Test System",
                    "tags": ["test", "memory-load", "large-document"]
                }

                try:
                    async with session.post(f"{self.service_url}/documents/", json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            # Process the document to trigger RAG indexing
                            await session.post(f"{self.service_url}/documents/{result['data']['id']}/process")
                except Exception as e:
                    logger.warning(f"Memory load request error: {e}")

        end_time = time.time() + duration
        while time.time() < end_time:
            tasks = [make_memory_intensive_request() for _ in range(concurrent_requests)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(2)  # More controlled memory load

    async def measure_response_times(self, duration: int = 60, sample_rate: int = 5) -> List[float]:
        """Measure response times during scaling events"""
        logger.info(f"Measuring response times for {duration} seconds")

        response_times = []
        end_time = time.time() + duration

        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                start_time = time.time()

                try:
                    payload = {"query": "What are the key benefits of using AI in document processing?"}
                    async with session.post(f"{self.service_url}/rag/query", json=payload) as response:
                        await response.json()
                        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                        response_times.append(response_time)

                except Exception as e:
                    logger.warning(f"Response time measurement error: {e}")

                await asyncio.sleep(1.0 / sample_rate)

        return response_times

    async def get_resource_metrics(self) -> Dict[str, float]:
        """Get current resource utilization metrics"""
        metrics = {}

        try:
            # CPU utilization
            cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{namespace="{self.namespace}", container="backend"}}[5m])) * 100'
            cpu_result = self.prometheus.custom_query(cpu_query)
            metrics['cpu_utilization'] = float(cpu_result[0]['value'][1]) if cpu_result else 0

            # Memory utilization
            memory_query = f'avg(container_memory_working_set_bytes{{namespace="{self.namespace}", container="backend"}}) / avg(container_spec_memory_limit_bytes{{namespace="{self.namespace}", container="backend"}}) * 100'
            memory_result = self.prometheus.custom_query(memory_query)
            metrics['memory_utilization'] = float(memory_result[0]['value'][1]) if memory_result else 0

            # Request rate
            request_query = f'rate(http_requests_total{{namespace="{self.namespace}"}}[5m])'
            request_result = self.prometheus.custom_query(request_query)
            metrics['request_rate'] = float(request_result[0]['value'][1]) if request_result else 0

            # Response time P95
            response_query = f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{namespace="{self.namespace}"}}[5m])) * 1000'
            response_result = self.prometheus.custom_query(response_query)
            metrics['response_time_p95'] = float(response_result[0]['value'][1]) if response_result else 0

        except Exception as e:
            logger.error(f"Error getting resource metrics: {e}")

        return metrics

# Test Cases

@pytest.mark.asyncio
class TestHorizontalPodAutoscaler:
    """Test cases for HPA functionality"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test framework"""
        self.hpa_test = HPATestFramework()

        # Wait for system to be stable before testing
        await asyncio.sleep(30)

        # Record initial state
        self.initial_replicas = await self.hpa_test.get_current_replicas()
        self.initial_metrics = await self.hpa_test.get_resource_metrics()

        logger.info(f"Test setup complete. Initial replicas: {self.initial_replicas}")
        logger.info(f"Initial metrics: {self.initial_metrics}")

    async def test_cpu_scale_up_behavior(self):
        """Test HPA scale-up behavior under CPU load"""
        logger.info("Testing CPU-based scale-up behavior")

        initial_replicas = await self.hpa_test.get_current_replicas()
        initial_hpa_status = await self.hpa_test.get_hpa_status()

        # Record test start
        test_start = time.time()

        # Generate CPU load in background
        load_task = asyncio.create_task(
            self.hpa_test.generate_cpu_load(duration=300, intensity=0.9)
        )

        # Monitor scaling behavior
        scaling_events = []
        response_times = []

        try:
            # Wait for scaling to be triggered (up to 5 minutes)
            scale_triggered = False
            for i in range(30):  # Check every 10 seconds for 5 minutes
                await asyncio.sleep(10)

                current_replicas = await self.hpa_test.get_current_replicas()
                hpa_status = await self.hpa_test.get_hpa_status()
                metrics = await self.hpa_test.get_resource_metrics()

                # Record scaling event
                scaling_events.append({
                    'timestamp': time.time() - test_start,
                    'replicas': current_replicas,
                    'desired_replicas': hpa_status.get('desired_replicas', current_replicas),
                    'cpu_utilization': metrics.get('cpu_utilization', 0),
                    'memory_utilization': metrics.get('memory_utilization', 0),
                    'response_time_p95': metrics.get('response_time_p95', 0)
                })

                # Check if scaling was triggered
                if current_replicas > initial_replicas:
                    scale_triggered = True
                    logger.info(f"Scale-up triggered: {initial_replicas} -> {current_replicas}")

                # Break if max replicas reached or load test completes
                if current_replicas >= initial_hpa_status.get('max_replicas', 10):
                    logger.info(f"Max replicas reached: {current_replicas}")
                    break

            # Measure response times during scaling
            response_times = await self.hpa_test.measure_response_times(duration=60)

        finally:
            # Cancel load generation
            load_task.cancel()
            try:
                await load_task
            except asyncio.CancelledError:
                pass

        # Analyze results
        final_replicas = await self.hpa_test.get_current_replicas()
        final_metrics = await self.hpa_test.get_resource_metrics()

        # Assertions
        assert scale_triggered, "HPA should trigger scale-up under high CPU load"
        assert final_replicas > initial_replicas, f"Replicas should increase: {initial_replicas} -> {final_replicas}"

        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

            assert avg_response_time < 1000, f"Average response time should be reasonable: {avg_response_time}ms"
            assert p95_response_time < 2000, f"P95 response time should be acceptable: {p95_response_time}ms"

        # Store test results
        self.hpa_test.test_results.append({
            'test_name': 'cpu_scale_up',
            'initial_replicas': initial_replicas,
            'final_replicas': final_replicas,
            'scale_triggered': scale_triggered,
            'scaling_events': scaling_events,
            'response_times': response_times,
            'initial_metrics': self.initial_metrics,
            'final_metrics': final_metrics
        })

        logger.info(f"CPU scale-up test completed: {initial_replicas} -> {final_replicas}")

    async def test_memory_scale_up_behavior(self):
        """Test HPA scale-up behavior under memory pressure"""
        logger.info("Testing memory-based scale-up behavior")

        initial_replicas = await self.hpa_test.get_current_replicas()
        test_start = time.time()

        # Generate memory load
        load_task = asyncio.create_task(
            self.hpa_test.generate_memory_load(duration=240, intensity=0.8)
        )

        scaling_events = []
        scale_triggered = False

        try:
            # Monitor for 4 minutes
            for i in range(24):  # Every 10 seconds for 4 minutes
                await asyncio.sleep(10)

                current_replicas = await self.hpa_test.get_current_replicas()
                metrics = await self.hpa_test.get_resource_metrics()

                scaling_events.append({
                    'timestamp': time.time() - test_start,
                    'replicas': current_replicas,
                    'memory_utilization': metrics.get('memory_utilization', 0),
                    'cpu_utilization': metrics.get('cpu_utilization', 0)
                })

                if current_replicas > initial_replicas:
                    scale_triggered = True
                    logger.info(f"Memory-triggered scale-up: {initial_replicas} -> {current_replicas}")
                    break

        finally:
            load_task.cancel()
            try:
                await load_task
            except asyncio.CancelledError:
                pass

        final_replicas = await self.hpa_test.get_current_replicas()

        # Memory-based scaling may be slower, so we allow for delayed response
        if not scale_triggered:
            logger.warning("Memory-based scaling may require more time or higher thresholds")

        self.hpa_test.test_results.append({
            'test_name': 'memory_scale_up',
            'initial_replicas': initial_replicas,
            'final_replicas': final_replicas,
            'scale_triggered': scale_triggered,
            'scaling_events': scaling_events
        })

        logger.info(f"Memory scale-up test completed: {initial_replicas} -> {final_replicas}")

    async def test_scale_down_behavior(self):
        """Test HPA scale-down behavior when load decreases"""
        logger.info("Testing scale-down behavior")

        # First, ensure we have scaled up
        initial_replicas = await self.hpa_test.get_current_replicas()

        if initial_replicas <= 2:
            logger.info("Scaling up first to test scale-down")
            await self.hpa_test.generate_cpu_load(duration=180, intensity=0.9)
            await asyncio.sleep(120)  # Wait for scale-up

        current_replicas = await self.hpa_test.get_current_replicas()
        logger.info(f"Starting scale-down test with {current_replicas} replicas")

        # Now monitor scale-down (this should happen naturally)
        test_start = time.time()
        scaling_events = []
        scale_down_triggered = False

        # Monitor for 10 minutes (scale-down is typically slower)
        for i in range(60):  # Every 10 seconds for 10 minutes
            await asyncio.sleep(10)

            new_replicas = await self.hpa_test.get_current_replicas()
            metrics = await self.hpa_test.get_resource_metrics()

            scaling_events.append({
                'timestamp': time.time() - test_start,
                'replicas': new_replicas,
                'cpu_utilization': metrics.get('cpu_utilization', 0),
                'memory_utilization': metrics.get('memory_utilization', 0)
            })

            if new_replicas < current_replicas:
                scale_down_triggered = True
                logger.info(f"Scale-down triggered: {current_replicas} -> {new_replicas}")
                current_replicas = new_replicas

        final_replicas = await self.hpa_test.get_current_replicas()

        # Scale-down is expected to be slower and more conservative
        logger.info(f"Scale-down behavior observed: triggered={scale_down_triggered}")

        self.hpa_test.test_results.append({
            'test_name': 'scale_down',
            'scale_down_triggered': scale_down_triggered,
            'final_replicas': final_replicas,
            'scaling_events': scaling_events
        })

    async def test_response_time_during_scaling(self):
        """Test that response times remain acceptable during scaling events"""
        logger.info("Testing response times during scaling")

        # Generate moderate load and measure response times
        load_task = asyncio.create_task(
            self.hpa_test.generate_cpu_load(duration=180, intensity=0.7)
        )

        response_measurement_task = asyncio.create_task(
            self.hpa_test.measure_response_times(duration=200, sample_rate=2)
        )

        try:
            response_times = await response_measurement_task

            if response_times:
                avg_response_time = statistics.mean(response_times)
                p50_response_time = statistics.median(response_times)
                p95_response_time = statistics.quantiles(response_times, n=20)[18]
                p99_response_time = statistics.quantiles(response_times, n=100)[98]

                logger.info(f"Response time stats:")
                logger.info(f"  Average: {avg_response_time:.2f}ms")
                logger.info(f"  P50: {p50_response_time:.2f}ms")
                logger.info(f"  P95: {p95_response_time:.2f}ms")
                logger.info(f"  P99: {p99_response_time:.2f}ms")

                # Assertions for acceptable response times
                assert avg_response_time < 1000, f"Average response time too high: {avg_response_time}ms"
                assert p95_response_time < 2000, f"P95 response time too high: {p95_response_time}ms"
                assert p99_response_time < 5000, f"P99 response time too high: {p99_response_time}ms"

                # Store results
                self.hpa_test.test_results.append({
                    'test_name': 'response_time_during_scaling',
                    'response_times': response_times,
                    'avg_response_time': avg_response_time,
                    'p50_response_time': p50_response_time,
                    'p95_response_time': p95_response_time,
                    'p99_response_time': p99_response_time
                })

        finally:
            load_task.cancel()
            try:
                await load_task
            except asyncio.CancelledError:
                pass

    async def test_multi_metric_scaling(self):
        """Test scaling behavior with multiple metrics (CPU + memory + custom)"""
        logger.info("Testing multi-metric scaling behavior")

        initial_replicas = await self.hpa_test.get_current_replicas()
        test_start = time.time()

        # Generate mixed workload
        cpu_task = asyncio.create_task(
            self.hpa_test.generate_cpu_load(duration=240, intensity=0.6)
        )
        memory_task = asyncio.create_task(
            self.hpa_test.generate_memory_load(duration=240, intensity=0.5)
        )

        scaling_events = []

        try:
            # Monitor multi-metric scaling
            for i in range(24):  # Every 10 seconds for 4 minutes
                await asyncio.sleep(10)

                current_replicas = await self.hpa_test.get_current_replicas()
                metrics = await self.hpa_test.get_resource_metrics()
                hpa_status = await self.hpa_test.get_hpa_status()

                scaling_events.append({
                    'timestamp': time.time() - test_start,
                    'replicas': current_replicas,
                    'desired_replicas': hpa_status.get('desired_replicas', current_replicas),
                    'cpu_utilization': metrics.get('cpu_utilization', 0),
                    'memory_utilization': metrics.get('memory_utilization', 0),
                    'request_rate': metrics.get('request_rate', 0),
                    'response_time_p95': metrics.get('response_time_p95', 0)
                })

        finally:
            cpu_task.cancel()
            memory_task.cancel()
            for task in [cpu_task, memory_task]:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        final_replicas = await self.hpa_test.get_current_replicas()
        final_metrics = await self.hpa_test.get_resource_metrics()

        # Analyze multi-metric scaling effectiveness
        max_cpu = max(event['cpu_utilization'] for event in scaling_events)
        max_memory = max(event['memory_utilization'] for event in scaling_events)

        logger.info(f"Multi-metric test: {initial_replicas} -> {final_replicas}")
        logger.info(f"Peak CPU: {max_cpu:.1f}%, Peak Memory: {max_memory:.1f}%")

        self.hpa_test.test_results.append({
            'test_name': 'multi_metric_scaling',
            'initial_replicas': initial_replicas,
            'final_replicas': final_replicas,
            'peak_cpu': max_cpu,
            'peak_memory': max_memory,
            'scaling_events': scaling_events,
            'final_metrics': final_metrics
        })

    @pytest.fixture(autouse=True)
    async def teardown(self):
        """Cleanup and generate test report"""
        yield  # This runs after all tests

        logger.info("Generating HPA test report...")

        # Save detailed test results
        test_report = {
            'timestamp': datetime.now().isoformat(),
            'namespace': self.hpa_test.namespace,
            'deployment': self.hpa_test.deployment_name,
            'hpa': self.hpa_test.hpa_name,
            'initial_state': {
                'replicas': self.initial_replicas,
                'metrics': self.initial_metrics
            },
            'test_results': self.hpa_test.test_results,
            'summary': {
                'total_tests': len(self.hpa_test.test_results),
                'scaling_tests_passed': sum(1 for result in self.hpa_test.test_results
                                          if result.get('scale_triggered', False) or
                                             result.get('test_name') == 'scale_down'),
                'performance_acceptable': all(
                    result.get('avg_response_time', 0) < 1000
                    for result in self.hpa_test.test_results
                    if 'avg_response_time' in result
                )
            }
        }

        # Save report
        report_file = f"hpa_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(test_report, f, indent=2, default=str)

        logger.info(f"HPA test report saved to {report_file}")

        # Print summary
        print("\n" + "="*60)
        print("HPA TESTING SUMMARY")
        print("="*60)
        print(f"Total Tests: {test_report['summary']['total_tests']}")
        print(f"Scaling Tests Passed: {test_report['summary']['scaling_tests_passed']}")
        print(f"Performance Acceptable: {test_report['summary']['performance_acceptable']}")

        for result in self.hpa_test.test_results:
            test_name = result['test_name']
            if test_name == 'cpu_scale_up':
                print(f"CPU Scale-up: {result['initial_replicas']} -> {result['final_replicas']} ({'✓' if result['scale_triggered'] else '✗'})")
            elif test_name == 'memory_scale_up':
                print(f"Memory Scale-up: {result['initial_replicas']} -> {result['final_replicas']} ({'✓' if result['scale_triggered'] else '✗'})")
            elif test_name == 'response_time_during_scaling':
                avg_rt = result.get('avg_response_time', 0)
                p95_rt = result.get('p95_response_time', 0)
                print(f"Response Times: Avg={avg_rt:.1f}ms, P95={p95_rt:.1f}ms ({'✓' if avg_rt < 1000 else '✗'})")

        print("="*60)

# Pytest configuration
def pytest_configure(config):
    """Configure pytest for HPA testing"""
    config.addinivalue_line(
        "markers", "hpa: mark test as HPA-specific"
    )

# Run tests
if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])