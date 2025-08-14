"""
RAG Concurrency and Performance Stress Tests

Comprehensive stress testing for RAG system including concurrent operations,
high-load scenarios, resource contention, and performance degradation analysis.
"""

import pytest
import asyncio
import time
import threading
import concurrent.futures
import psutil
import gc
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import random
import statistics
from typing import List, Dict, Any, Callable
import json
import numpy as np

from src.services.rag.coordinator import RAGCoordinator
from src.services.rag.index_builder import RAGIndexBuilder
from src.services.rag.query_engine import RAGQueryEngine
from src.services.rag.recovery_service import RAGRecoveryService
from src.services.rag.file_manager import RAGFileManager
from src.services.rag.performance_monitor import RAGPerformanceMonitor
from src.services.rag.exceptions import RAGProcessingError, RAGPerformanceError
from src.database.models import DocumentModel


class TestRAGConcurrencyStress:
    """Test suite for RAG system concurrency and multi-user scenarios."""

    @pytest.fixture
    def stress_test_coordinator(self):
        """Create RAG coordinator configured for stress testing."""
        # Mock components with realistic behavior
        mock_index_builder = Mock(spec=RAGIndexBuilder)
        mock_query_engine = Mock(spec=RAGQueryEngine)
        mock_recovery_service = Mock(spec=RAGRecoveryService)
        mock_file_manager = Mock(spec=RAGFileManager)

        # Configure realistic processing times
        mock_index_builder.build_index = AsyncMock(
            return_value={"status": "success", "chunks": 50, "processing_time": 0.5}
        )

        mock_query_engine.query = AsyncMock(
            return_value={
                "answer": "Test answer from RAG system",
                "sources": [{"page": 1, "confidence": 0.9}],
                "processing_time": 0.2
            }
        )

        coordinator = RAGCoordinator(
            index_builder=mock_index_builder,
            query_engine=mock_query_engine,
            recovery_service=mock_recovery_service,
            file_manager=mock_file_manager,
            max_concurrent_operations=10
        )

        return coordinator

    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitoring service."""
        return RAGPerformanceMonitor(
            metrics_collection_enabled=True,
            real_time_monitoring=True,
            alert_thresholds={
                "response_time_ms": 5000,
                "memory_usage_mb": 1024,
                "cpu_usage_percent": 80,
                "concurrent_operations": 20
            }
        )

    @pytest.fixture
    def stress_test_documents(self):
        """Generate documents for stress testing."""
        documents = []
        for i in range(100):  # 100 test documents
            doc = DocumentModel(
                id=i + 1,
                title=f"Stress Test Document {i + 1}",
                file_path=f"/test/stress_doc_{i + 1}.pdf",
                content_hash=f"hash_{i + 1}",
                mime_type="application/pdf",
                file_size=random.randint(1024 * 1024, 10 * 1024 * 1024)  # 1-10MB
            )
            documents.append(doc)
        return documents

    @pytest.mark.asyncio
    async def test_concurrent_document_processing_stress(self, stress_test_coordinator, stress_test_documents):
        """Test concurrent processing of multiple documents under stress."""
        # Given - high concurrent load
        concurrent_documents = stress_test_documents[:20]  # Process 20 documents concurrently

        start_time = time.time()
        initial_memory = psutil.Process().memory_info().rss

        # When - process all documents concurrently
        processing_tasks = [
            stress_test_coordinator.process_document_complete(doc)
            for doc in concurrent_documents
        ]

        results = await asyncio.gather(*processing_tasks, return_exceptions=True)

        end_time = time.time()
        final_memory = psutil.Process().memory_info().rss

        # Then - analyze stress test results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]

        # Performance assertions
        total_time = end_time - start_time
        throughput = len(successful_results) / total_time if total_time > 0 else 0
        memory_increase_mb = (final_memory - initial_memory) / (1024 * 1024)

        assert len(successful_results) >= 18  # At least 90% success rate under stress
        assert throughput >= 5.0  # At least 5 documents per second
        assert memory_increase_mb < 500  # Memory increase should be reasonable
        assert total_time < 10.0  # Total processing should complete in reasonable time

    @pytest.mark.asyncio
    async def test_concurrent_query_processing_stress(self, stress_test_coordinator, stress_test_documents):
        """Test concurrent query processing with high request volume."""
        # Given - simulate high query load
        test_queries = [
            f"What are the main findings in document {i}?"
            for i in range(1, 51)  # 50 concurrent queries
        ]

        document_ids = [doc.id for doc in stress_test_documents[:10]]  # Query across 10 documents

        start_time = time.time()

        # When - execute concurrent queries
        query_tasks = []
        for i, query in enumerate(test_queries):
            doc_id = document_ids[i % len(document_ids)]  # Distribute queries across documents
            task = stress_test_coordinator.query_document(doc_id, query)
            query_tasks.append(task)

        results = await asyncio.gather(*query_tasks, return_exceptions=True)

        end_time = time.time()

        # Then - analyze query stress performance
        successful_queries = [r for r in results if not isinstance(r, Exception)]
        query_latencies = []

        for result in successful_queries:
            if "processing_time" in result:
                query_latencies.append(result["processing_time"])

        # Performance metrics
        total_time = end_time - start_time
        query_throughput = len(successful_queries) / total_time if total_time > 0 else 0
        avg_latency = statistics.mean(query_latencies) if query_latencies else 0
        p95_latency = np.percentile(query_latencies, 95) if query_latencies else 0

        assert len(successful_queries) >= 45  # At least 90% success rate
        assert query_throughput >= 10.0  # At least 10 queries per second
        assert avg_latency < 1.0  # Average latency under 1 second
        assert p95_latency < 2.0  # 95th percentile under 2 seconds

    @pytest.mark.asyncio
    async def test_mixed_operations_stress(self, stress_test_coordinator, stress_test_documents):
        """Test mixed document processing and querying under stress."""
        # Given - mixed workload
        processing_documents = stress_test_documents[:10]
        query_documents = stress_test_documents[10:20]

        queries = [
            f"Analyze the methodology in document {doc.id}"
            for doc in query_documents
        ]

        # When - execute mixed operations concurrently
        processing_tasks = [
            stress_test_coordinator.process_document_complete(doc)
            for doc in processing_documents
        ]

        query_tasks = [
            stress_test_coordinator.query_document(doc.id, query)
            for doc, query in zip(query_documents, queries)
        ]

        all_tasks = processing_tasks + query_tasks
        random.shuffle(all_tasks)  # Mix task order

        start_time = time.time()
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Then - verify mixed workload performance
        successful_ops = len([r for r in results if not isinstance(r, Exception)])
        total_ops = len(all_tasks)
        success_rate = successful_ops / total_ops

        assert success_rate >= 0.85  # At least 85% success rate for mixed operations
        assert total_time < 15.0  # Mixed workload completes in reasonable time

    @pytest.mark.asyncio
    async def test_memory_pressure_stress_behavior(self, stress_test_coordinator, performance_monitor):
        """Test system behavior under extreme memory pressure."""
        # Given - simulate memory pressure
        initial_memory = psutil.Process().memory_info().rss

        # Create memory-intensive operations
        large_documents = [
            DocumentModel(
                id=i,
                title=f"Large Document {i}",
                file_path=f"/test/large_{i}.pdf",
                content_hash=f"large_hash_{i}",
                mime_type="application/pdf",
                file_size=50 * 1024 * 1024  # 50MB each
            )
            for i in range(10)
        ]

        # When - process under memory pressure
        memory_stats = []

        for doc in large_documents:
            try:
                result = await stress_test_coordinator.process_document_complete(doc)

                current_memory = psutil.Process().memory_info().rss
                memory_increase = (current_memory - initial_memory) / (1024 * 1024)

                memory_stats.append({
                    "document_id": doc.id,
                    "memory_mb": memory_increase,
                    "success": result.get("success", False)
                })

                # Force garbage collection
                gc.collect()

            except Exception as e:
                memory_stats.append({
                    "document_id": doc.id,
                    "memory_mb": (psutil.Process().memory_info().rss - initial_memory) / (1024 * 1024),
                    "success": False,
                    "error": str(e)
                })

        # Then - analyze memory behavior under stress
        successful_docs = [stat for stat in memory_stats if stat["success"]]
        peak_memory = max(stat["memory_mb"] for stat in memory_stats)

        assert len(successful_docs) >= 7  # At least 70% should succeed
        assert peak_memory < 2048  # Should not exceed 2GB peak memory

        # Verify graceful degradation
        if len(successful_docs) < len(large_documents):
            # System should fail gracefully, not crash
            failed_stats = [stat for stat in memory_stats if not stat["success"]]
            assert all("error" in stat for stat in failed_stats)

    @pytest.mark.asyncio
    async def test_resource_contention_stress(self, stress_test_coordinator):
        """Test resource contention with file system and database access."""
        # Given - operations that contend for resources
        contention_operations = []

        # File system intensive operations
        for i in range(15):
            contention_operations.append(
                ("file_cleanup", stress_test_coordinator.cleanup_resources, {"document_id": i})
            )

        # Database intensive operations (mocked)
        for i in range(15):
            contention_operations.append(
                ("health_check", stress_test_coordinator.health_check, {})
            )

        # Index building operations
        documents = [
            DocumentModel(id=i, title=f"Doc {i}", file_path=f"/test/doc_{i}.pdf",
                         content_hash=f"hash_{i}", mime_type="application/pdf", file_size=1024*1024)
            for i in range(10)
        ]

        for doc in documents:
            contention_operations.append(
                ("process_document", stress_test_coordinator.process_document_complete, {"document": doc})
            )

        # When - execute operations with resource contention
        random.shuffle(contention_operations)

        async def execute_operation(op_type, op_func, op_kwargs):
            try:
                start_time = time.time()
                if op_kwargs.get("document"):
                    result = await op_func(op_kwargs["document"])
                elif op_kwargs:
                    result = await op_func(**{k: v for k, v in op_kwargs.items() if k != "document"})
                else:
                    result = await op_func()

                return {
                    "operation": op_type,
                    "success": True,
                    "duration": time.time() - start_time,
                    "result": result
                }
            except Exception as e:
                return {
                    "operation": op_type,
                    "success": False,
                    "duration": time.time() - start_time,
                    "error": str(e)
                }

        # Execute with controlled concurrency to test contention
        semaphore = asyncio.Semaphore(8)  # Limit concurrent operations

        async def controlled_execution(operation):
            async with semaphore:
                return await execute_operation(*operation)

        tasks = [controlled_execution(op) for op in contention_operations]
        results = await asyncio.gather(*tasks)

        # Then - analyze resource contention results
        successful_ops = [r for r in results if r["success"]]
        failed_ops = [r for r in results if not r["success"]]

        operation_types = {}
        for result in results:
            op_type = result["operation"]
            if op_type not in operation_types:
                operation_types[op_type] = {"total": 0, "successful": 0, "avg_duration": 0}

            operation_types[op_type]["total"] += 1
            if result["success"]:
                operation_types[op_type]["successful"] += 1
                operation_types[op_type]["avg_duration"] += result["duration"]

        # Calculate success rates by operation type
        for op_type, stats in operation_types.items():
            if stats["successful"] > 0:
                stats["avg_duration"] /= stats["successful"]
                stats["success_rate"] = stats["successful"] / stats["total"]

        # Verify acceptable performance under contention
        overall_success_rate = len(successful_ops) / len(results)
        assert overall_success_rate >= 0.80  # At least 80% success rate

        # No operation type should have catastrophically low success rate
        for op_type, stats in operation_types.items():
            assert stats["success_rate"] >= 0.70, f"{op_type} has low success rate: {stats['success_rate']}"

    @pytest.mark.asyncio
    async def test_performance_degradation_analysis(self, stress_test_coordinator, performance_monitor):
        """Test performance degradation patterns under increasing load."""
        # Given - increasing load levels
        load_levels = [5, 10, 20, 35, 50]  # Concurrent operations
        performance_results = []

        for load_level in load_levels:
            # Create tasks for current load level
            tasks = []
            for i in range(load_level):
                doc = DocumentModel(
                    id=i,
                    title=f"Load Test Doc {i}",
                    file_path=f"/test/load_{i}.pdf",
                    content_hash=f"load_hash_{i}",
                    mime_type="application/pdf",
                    file_size=2 * 1024 * 1024
                )
                tasks.append(stress_test_coordinator.query_document(doc.id, f"Query for document {i}"))

            # Measure performance at this load level
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss
            start_cpu_percent = psutil.cpu_percent()

            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            end_cpu_percent = psutil.cpu_percent()

            # Analyze results
            successful_results = [r for r in results if not isinstance(r, Exception)]
            total_time = end_time - start_time
            throughput = len(successful_results) / total_time if total_time > 0 else 0
            memory_delta = (end_memory - start_memory) / (1024 * 1024)

            performance_results.append({
                "load_level": load_level,
                "success_count": len(successful_results),
                "success_rate": len(successful_results) / load_level,
                "throughput": throughput,
                "avg_response_time": total_time / len(successful_results) if successful_results else 0,
                "memory_usage_mb": memory_delta,
                "cpu_usage_percent": (start_cpu_percent + end_cpu_percent) / 2,
                "total_time": total_time
            })

            # Brief pause between load levels
            await asyncio.sleep(1)

        # Then - analyze degradation patterns
        throughput_trend = [result["throughput"] for result in performance_results]
        response_time_trend = [result["avg_response_time"] for result in performance_results]
        success_rate_trend = [result["success_rate"] for result in performance_results]

        # Verify acceptable degradation
        assert all(rate >= 0.80 for rate in success_rate_trend), "Success rate degraded too much"
        assert max(response_time_trend) < 5.0, "Response times became unacceptable"

        # Analyze degradation curve
        throughput_degradation = (throughput_trend[0] - throughput_trend[-1]) / throughput_trend[0] if throughput_trend[0] > 0 else 0
        assert throughput_degradation < 0.6, "Throughput degraded more than 60%"

    @pytest.mark.asyncio
    async def test_system_recovery_after_stress(self, stress_test_coordinator, performance_monitor):
        """Test system recovery behavior after stress conditions."""
        # Given - system under heavy stress
        stress_documents = [
            DocumentModel(id=i, title=f"Stress Doc {i}", file_path=f"/test/stress_{i}.pdf",
                         content_hash=f"stress_hash_{i}", mime_type="application/pdf", file_size=5*1024*1024)
            for i in range(30)
        ]

        # Apply stress load
        stress_tasks = [
            stress_test_coordinator.process_document_complete(doc)
            for doc in stress_documents
        ]

        # Execute stress load
        await asyncio.gather(*stress_tasks, return_exceptions=True)

        # When - allow system to recover
        recovery_start_time = time.time()
        await asyncio.sleep(2)  # Recovery period

        # Test normal operations after stress
        recovery_documents = [
            DocumentModel(id=i+100, title=f"Recovery Doc {i}", file_path=f"/test/recovery_{i}.pdf",
                         content_hash=f"recovery_hash_{i}", mime_type="application/pdf", file_size=1024*1024)
            for i in range(5)
        ]

        recovery_tasks = [
            stress_test_coordinator.query_document(doc.id, "Recovery test query")
            for doc in recovery_documents
        ]

        recovery_results = await asyncio.gather(*recovery_tasks, return_exceptions=True)
        recovery_time = time.time() - recovery_start_time

        # Then - verify recovery performance
        successful_recovery = [r for r in recovery_results if not isinstance(r, Exception)]
        recovery_success_rate = len(successful_recovery) / len(recovery_documents)

        assert recovery_success_rate >= 0.90  # Should recover to >90% success rate
        assert recovery_time < 10.0  # Should recover quickly

        # Check if performance metrics are back to normal levels
        current_memory = psutil.Process().memory_info().rss / (1024 * 1024)  # MB
        assert current_memory < 1024  # Memory should not remain elevated

    def test_thread_safety_stress(self, stress_test_coordinator):
        """Test thread safety under concurrent access from multiple threads."""
        import threading
        import concurrent.futures

        # Given - operations to execute from multiple threads
        thread_results = []
        result_lock = threading.Lock()

        def thread_worker(thread_id: int, operations_count: int):
            """Worker function for thread stress testing."""
            thread_start_time = time.time()
            successes = 0

            for i in range(operations_count):
                try:
                    # Simulate RAG operations that might be called from different threads
                    doc = DocumentModel(
                        id=thread_id * 1000 + i,
                        title=f"Thread {thread_id} Doc {i}",
                        file_path=f"/test/thread_{thread_id}_doc_{i}.pdf",
                        content_hash=f"thread_hash_{thread_id}_{i}",
                        mime_type="application/pdf",
                        file_size=1024*1024
                    )

                    # This would normally be async, but we're testing thread safety of coordinator internals
                    result = stress_test_coordinator.get_performance_metrics()

                    if result:
                        successes += 1

                except Exception as e:
                    pass  # Count as failure

            thread_time = time.time() - thread_start_time

            with result_lock:
                thread_results.append({
                    "thread_id": thread_id,
                    "successes": successes,
                    "operations": operations_count,
                    "duration": thread_time,
                    "success_rate": successes / operations_count
                })

        # When - execute from multiple threads
        num_threads = 8
        operations_per_thread = 25

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(thread_worker, thread_id, operations_per_thread)
                for thread_id in range(num_threads)
            ]

            concurrent.futures.wait(futures)

        # Then - verify thread safety
        assert len(thread_results) == num_threads

        overall_success_rate = sum(r["successes"] for r in thread_results) / sum(r["operations"] for r in thread_results)
        assert overall_success_rate >= 0.95  # Very high success rate expected for thread-safe operations

        # Verify no thread had catastrophic failures
        for result in thread_results:
            assert result["success_rate"] >= 0.90, f"Thread {result['thread_id']} had low success rate: {result['success_rate']}"

    @pytest.mark.asyncio
    async def test_long_running_stress_stability(self, stress_test_coordinator):
        """Test system stability during long-running stress conditions."""
        # Given - long-running stress scenario
        duration_seconds = 30  # 30-second stress test
        operation_interval = 0.5  # Operation every 500ms

        start_time = time.time()
        operations_completed = []

        async def continuous_operations():
            """Generate continuous operations for stability testing."""
            op_count = 0

            while time.time() - start_time < duration_seconds:
                try:
                    op_start = time.time()

                    # Alternate between different operation types
                    if op_count % 3 == 0:
                        result = await stress_test_coordinator.health_check()
                    elif op_count % 3 == 1:
                        result = stress_test_coordinator.get_performance_metrics()
                    else:
                        doc = DocumentModel(
                            id=op_count,
                            title=f"Stability Test Doc {op_count}",
                            file_path=f"/test/stability_{op_count}.pdf",
                            content_hash=f"stability_hash_{op_count}",
                            mime_type="application/pdf",
                            file_size=1024*1024
                        )
                        result = await stress_test_coordinator.query_document(doc.id, f"Stability query {op_count}")

                    op_duration = time.time() - op_start

                    operations_completed.append({
                        "operation": op_count,
                        "success": result is not None,
                        "duration": op_duration,
                        "timestamp": time.time()
                    })

                    op_count += 1
                    await asyncio.sleep(operation_interval)

                except Exception as e:
                    operations_completed.append({
                        "operation": op_count,
                        "success": False,
                        "duration": time.time() - op_start,
                        "timestamp": time.time(),
                        "error": str(e)
                    })
                    op_count += 1

        # When - run continuous operations
        await continuous_operations()

        # Then - analyze stability metrics
        total_operations = len(operations_completed)
        successful_operations = len([op for op in operations_completed if op["success"]])
        stability_success_rate = successful_operations / total_operations if total_operations > 0 else 0

        # Calculate performance stability over time
        time_windows = []
        window_size = 5  # 5-second windows

        for window_start in range(0, int(duration_seconds), window_size):
            window_end = window_start + window_size
            window_ops = [
                op for op in operations_completed
                if window_start <= (op["timestamp"] - start_time) < window_end
            ]

            if window_ops:
                window_success_rate = len([op for op in window_ops if op["success"]]) / len(window_ops)
                avg_duration = sum(op["duration"] for op in window_ops if op["success"]) / len([op for op in window_ops if op["success"]]) if any(op["success"] for op in window_ops) else 0

                time_windows.append({
                    "window": f"{window_start}-{window_end}s",
                    "operations": len(window_ops),
                    "success_rate": window_success_rate,
                    "avg_duration": avg_duration
                })

        # Stability assertions
        assert stability_success_rate >= 0.85, f"Overall stability success rate too low: {stability_success_rate}"
        assert total_operations >= 50, "Not enough operations completed during stability test"

        # Verify stability doesn't degrade significantly over time
        if len(time_windows) >= 3:
            first_window_success = time_windows[0]["success_rate"]
            last_window_success = time_windows[-1]["success_rate"]
            degradation = (first_window_success - last_window_success) / first_window_success if first_window_success > 0 else 0

            assert degradation < 0.2, f"Performance degraded too much over time: {degradation}"