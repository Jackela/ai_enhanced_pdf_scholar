"""
Performance Impact Tests for SQL Injection Prevention

Verify that security measures don't significantly impact performance.
"""

import statistics
import time
from unittest.mock import Mock

import pytest

from backend.api.models import DocumentQueryParams, DocumentSortField, SortOrder
from src.repositories.document_repository import DocumentRepository


class TestSecurityPerformanceImpact:
    """Test performance impact of security measures."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        mock_db = Mock()
        mock_db.fetch_all.return_value = []
        return mock_db

    @pytest.fixture
    def document_repository(self, mock_db_connection):
        """Create document repository with mocked database."""
        return DocumentRepository(mock_db_connection)

    def test_whitelist_validation_performance(self, document_repository, mock_db_connection):
        """Test that whitelist validation has minimal performance impact."""
        # Simulate database delay
        mock_db_connection.fetch_all.return_value = []

        # Measure execution times
        execution_times = []

        for _ in range(100):
            start_time = time.perf_counter()
            result = document_repository.get_all(
                sort_by="title",
                sort_order="asc",
                limit=50
            )
            end_time = time.perf_counter()
            execution_times.append(end_time - start_time)

        # Calculate statistics
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)

        # Performance assertions (validation should be <1ms overhead)
        assert avg_time < 0.001, f"Average execution time too high: {avg_time:.4f}s"
        assert max_time < 0.002, f"Maximum execution time too high: {max_time:.4f}s"

        # Verify database was called correctly
        assert mock_db_connection.fetch_all.call_count == 100

    def test_pydantic_validation_performance(self):
        """Test that Pydantic validation has acceptable performance."""
        # Measure Pydantic model creation times
        creation_times = []

        for _ in range(1000):
            start_time = time.perf_counter()
            params = DocumentQueryParams(
                search_query="Machine Learning",
                sort_by=DocumentSortField.TITLE,
                sort_order=SortOrder.ASC,
                page=1,
                per_page=50
            )
            end_time = time.perf_counter()
            creation_times.append(end_time - start_time)

        # Calculate statistics
        avg_time = statistics.mean(creation_times)
        max_time = max(creation_times)

        # Performance assertions (validation should be <0.5ms overhead)
        assert avg_time < 0.0005, f"Average validation time too high: {avg_time:.6f}s"
        assert max_time < 0.001, f"Maximum validation time too high: {max_time:.6f}s"

    def test_enum_validation_performance(self):
        """Test enum validation performance."""
        validation_times = []

        # Test enum validation speed
        for _ in range(10000):
            start_time = time.perf_counter()

            # This is what happens internally during validation
            sort_field = DocumentSortField.TITLE
            sort_order = SortOrder.ASC

            end_time = time.perf_counter()
            validation_times.append(end_time - start_time)

        avg_time = statistics.mean(validation_times)

        # Enum validation should be extremely fast
        assert avg_time < 0.00001, f"Enum validation too slow: {avg_time:.8f}s"

    def test_search_pattern_detection_performance(self):
        """Test performance of dangerous pattern detection."""
        detection_times = []

        # Test with various search queries
        test_queries = [
            "Machine Learning",
            "Deep Learning and AI",
            "Neural Networks: A Comprehensive Guide",
            "Advanced Algorithm Design Patterns",
            "Database Management Systems Overview"
        ]

        for _ in range(1000):
            for query in test_queries:
                start_time = time.perf_counter()

                try:
                    params = DocumentQueryParams(search_query=query)
                except ValueError:
                    pass  # Expected for malicious queries

                end_time = time.perf_counter()
                detection_times.append(end_time - start_time)

        avg_time = statistics.mean(detection_times)
        max_time = max(detection_times)

        # Pattern detection should be fast
        assert avg_time < 0.0001, f"Pattern detection too slow: {avg_time:.6f}s"
        assert max_time < 0.0005, f"Max pattern detection time too slow: {max_time:.6f}s"

    def test_malicious_pattern_detection_performance(self):
        """Test performance when detecting malicious patterns."""
        malicious_queries = [
            "search'; DROP TABLE documents; --",
            "query UNION SELECT * FROM users",
            "text; INSERT INTO malicious_table",
            "search/**/UNION/**/SELECT",
            "query -- malicious comment"
        ]

        detection_times = []

        for _ in range(100):
            for query in malicious_queries:
                start_time = time.perf_counter()

                try:
                    params = DocumentQueryParams(search_query=query)
                    # Should not reach here
                    assert False, f"Malicious query not detected: {query}"
                except ValueError:
                    # Expected - malicious pattern detected
                    pass

                end_time = time.perf_counter()
                detection_times.append(end_time - start_time)

        avg_time = statistics.mean(detection_times)

        # Even malicious pattern detection should be fast
        assert avg_time < 0.001, f"Malicious pattern detection too slow: {avg_time:.6f}s"

    def test_memory_usage_validation(self):
        """Test that security validation doesn't consume excessive memory."""
        import tracemalloc

        # Start memory tracing
        tracemalloc.start()

        # Create many validation objects
        params_list = []
        for i in range(1000):
            params = DocumentQueryParams(
                search_query=f"Query {i}",
                sort_by=DocumentSortField.CREATED_AT,
                sort_order=SortOrder.DESC,
                page=i % 10 + 1,
                per_page=50
            )
            params_list.append(params)

        # Get current memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory usage should be reasonable (less than 10MB for 1000 objects)
        assert current < 10 * 1024 * 1024, f"Memory usage too high: {current} bytes"
        assert peak < 15 * 1024 * 1024, f"Peak memory usage too high: {peak} bytes"

    @pytest.mark.benchmark
    def test_repository_security_benchmark(self, document_repository, mock_db_connection, benchmark):
        """Benchmark the secure repository method."""
        mock_db_connection.fetch_all.return_value = []

        # Benchmark the secure get_all method
        result = benchmark(
            document_repository.get_all,
            sort_by="title",
            sort_order="desc",
            limit=50
        )

        # Verify the result
        assert isinstance(result, list)

    @pytest.mark.benchmark
    def test_pydantic_validation_benchmark(self, benchmark):
        """Benchmark Pydantic model validation."""

        def create_validated_params():
            return DocumentQueryParams(
                search_query="Machine Learning Research",
                sort_by=DocumentSortField.TITLE,
                sort_order=SortOrder.ASC,
                page=1,
                per_page=50
            )

        # Benchmark the validation
        result = benchmark(create_validated_params)

        # Verify the result
        assert result.search_query == "Machine Learning Research"
        assert result.sort_by == DocumentSortField.TITLE

    def test_concurrent_validation_performance(self):
        """Test performance under concurrent validation scenarios."""
        import queue
        import threading

        results = queue.Queue()

        def validation_worker():
            """Worker function for concurrent validation."""
            try:
                start_time = time.perf_counter()
                for _ in range(100):
                    params = DocumentQueryParams(
                        search_query="Concurrent Test",
                        sort_by=DocumentSortField.CREATED_AT,
                        sort_order=SortOrder.DESC
                    )
                end_time = time.perf_counter()
                results.put(end_time - start_time)
            except Exception as e:
                results.put(f"Error: {e}")

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=validation_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Collect results
        execution_times = []
        while not results.empty():
            result = results.get()
            if isinstance(result, float):
                execution_times.append(result)
            else:
                pytest.fail(f"Thread error: {result}")

        # Verify performance under concurrency
        assert len(execution_times) == 10
        avg_time = statistics.mean(execution_times)

        # Should handle concurrency well
        assert avg_time < 0.1, f"Concurrent validation too slow: {avg_time:.4f}s"
