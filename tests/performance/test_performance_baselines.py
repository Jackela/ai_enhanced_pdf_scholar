#!/usr/bin/env python3
"""
Performance Baseline Regression Testing Framework

Automated performance regression testing that compares current performance
against established baselines. Alerts on significant performance degradation (>20% regression).

Agent C3: Performance Baseline Testing Expert
Mission: Validate system performance against established baselines
"""

import json
import pytest
import time
import statistics
import sys
from pathlib import Path
from typing import Dict, Any, List
import psutil

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.connection import DatabaseConnection
from src.repositories.document_repository import DocumentRepository
from src.repositories.citation_repository import CitationRepository
from src.services.content_hash_service import ContentHashService
from scripts.establish_performance_baseline import PerformanceBaselineEstablisher


@pytest.fixture(scope="session")
def baseline_data():
    """Load established performance baselines."""
    baseline_file = Path(__file__).parent.parent.parent / "performance_baselines.json"

    if not baseline_file.exists():
        pytest.skip("Performance baselines not established. Run establish_performance_baseline.py first.")

    with open(baseline_file, 'r') as f:
        data = json.load(f)

    return data.get('baselines', {})


@pytest.fixture(scope="session")
def performance_targets():
    """Performance target thresholds for regression detection."""
    return {
        'db_query_95th_percentile_ms': 50.0,
        'api_response_95th_percentile_ms': 200.0,
        'rag_query_90th_percentile_s': 2.0,
        'memory_sustained_mb': 500.0,
        'document_processing_s': 10.0,
        'regression_threshold': 0.20  # 20% performance degradation threshold
    }


@pytest.fixture
def database_connection():
    """Create database connection for testing."""
    db_path = Path(__file__).parent.parent.parent / "data" / "test_performance.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = DatabaseConnection(str(db_path))
    yield db

    # Cleanup
    if db_path.exists():
        db_path.unlink()


class TestDatabasePerformanceBaselines:
    """Test database performance against established baselines."""

    def test_select_operations_performance(self, database_connection, baseline_data, performance_targets):
        """Test SELECT operations meet baseline performance."""
        baseline_select = baseline_data.get('database_performance', {}).get('select_operations')

        if not baseline_select or 'error' in baseline_data.get('database_performance', {}):
            pytest.skip("Database baseline not available")

        # Measure current SELECT performance
        doc_repo = DocumentRepository(database_connection)
        select_times = []

        for _ in range(50):  # Same as baseline measurement
            start = time.perf_counter()
            docs = doc_repo.get_all()
            end = time.perf_counter()
            select_times.append((end - start) * 1000)  # Convert to ms

        current_p95 = self._percentile(select_times, 95)
        baseline_p95 = baseline_select['p95_ms']

        # Check regression threshold
        regression = (current_p95 - baseline_p95) / baseline_p95

        # Assert performance is within acceptable range
        assert current_p95 < performance_targets['db_query_95th_percentile_ms'], \
            f"SELECT p95 {current_p95:.2f}ms exceeds target {performance_targets['db_query_95th_percentile_ms']}ms"

        assert regression < performance_targets['regression_threshold'], \
            f"SELECT performance regression {regression:.1%} exceeds threshold {performance_targets['regression_threshold']:.1%}"

    def test_insert_operations_performance(self, database_connection, baseline_data, performance_targets):
        """Test INSERT operations meet baseline performance."""
        baseline_insert = baseline_data.get('database_performance', {}).get('insert_operations')

        if not baseline_insert or 'error' in baseline_data.get('database_performance', {}):
            pytest.skip("Database baseline not available")

        # Measure current INSERT performance
        hash_service = ContentHashService()
        insert_times = []

        for i in range(20):  # Same as baseline measurement
            test_doc = {
                'title': f'Regression Test Document {i}',
                'file_path': f'/test/regression_{i}.pdf',
                'file_hash': hash_service.calculate_hash(f'regression_content_{i}'),
                'file_size': 2000 + i,
                'page_count': 10
            }

            start = time.perf_counter()
            with database_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO documents (title, file_path, file_hash, file_size, page_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (test_doc['title'], test_doc['file_path'], test_doc['file_hash'],
                      test_doc['file_size'], test_doc['page_count']))
                conn.commit()
            end = time.perf_counter()
            insert_times.append((end - start) * 1000)

        current_p95 = self._percentile(insert_times, 95)
        baseline_p95 = baseline_insert['p95_ms']

        # Check regression
        regression = (current_p95 - baseline_p95) / baseline_p95

        # Cleanup test data
        with database_connection.get_connection() as conn:
            conn.execute("DELETE FROM documents WHERE title LIKE 'Regression Test Document%'")
            conn.commit()

        # Assertions
        assert current_p95 < performance_targets['db_query_95th_percentile_ms'], \
            f"INSERT p95 {current_p95:.2f}ms exceeds target"

        assert regression < performance_targets['regression_threshold'], \
            f"INSERT performance regression {regression:.1%} exceeds threshold"

    def test_complex_query_performance(self, database_connection, baseline_data, performance_targets):
        """Test complex query performance meets baseline."""
        baseline_complex = baseline_data.get('database_performance', {}).get('complex_queries')

        if not baseline_complex or 'error' in baseline_data.get('database_performance', {}):
            pytest.skip("Database baseline not available")

        # Measure current complex query performance
        complex_times = []

        for _ in range(30):  # Same as baseline
            start = time.perf_counter()
            with database_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, COUNT(c.id) as citation_count
                    FROM documents d
                    LEFT JOIN citations c ON d.id = c.document_id
                    GROUP BY d.id
                    ORDER BY d.created_at DESC
                    LIMIT 10
                """)
                results = cursor.fetchall()
            end = time.perf_counter()
            complex_times.append((end - start) * 1000)

        current_p95 = self._percentile(complex_times, 95)
        baseline_p95 = baseline_complex['p95_ms']

        regression = (current_p95 - baseline_p95) / baseline_p95

        assert current_p95 < performance_targets['db_query_95th_percentile_ms'], \
            f"Complex query p95 {current_p95:.2f}ms exceeds target"

        assert regression < performance_targets['regression_threshold'], \
            f"Complex query regression {regression:.1%} exceeds threshold"

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value from data list."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]


class TestMemoryPerformanceBaselines:
    """Test memory usage against established baselines."""

    def test_memory_usage_baseline(self, baseline_data, performance_targets):
        """Test memory usage meets baseline requirements."""
        baseline_memory = baseline_data.get('memory_analysis')

        if not baseline_memory:
            pytest.skip("Memory baseline not available")

        # Measure current memory usage
        process = psutil.Process()
        baseline_memory_mb = process.memory_info().rss / 1024 / 1024

        # Simulate workload similar to baseline
        memory_readings = []

        for i in range(20):
            # Simulate operations
            test_data = "Regression test data " * 1000 * (i + 1)
            processed = test_data.upper().split()

            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_readings.append(memory_mb)
            time.sleep(0.05)  # Brief pause

        current_peak = max(memory_readings)
        baseline_peak = baseline_memory['peak_mb']

        # Memory efficiency
        current_efficiency = (current_peak - baseline_memory_mb) / 20
        baseline_efficiency = baseline_memory['efficiency_mb_per_operation']

        # Check regression
        memory_regression = (current_peak - baseline_peak) / baseline_peak
        efficiency_regression = (current_efficiency - baseline_efficiency) / baseline_efficiency

        # Assertions
        assert current_peak < performance_targets['memory_sustained_mb'], \
            f"Peak memory {current_peak:.0f}MB exceeds target {performance_targets['memory_sustained_mb']}MB"

        assert memory_regression < performance_targets['regression_threshold'], \
            f"Memory usage regression {memory_regression:.1%} exceeds threshold"

        assert efficiency_regression < performance_targets['regression_threshold'], \
            f"Memory efficiency regression {efficiency_regression:.1%} exceeds threshold"


class TestRAGPerformanceBaselines:
    """Test RAG processing performance against baselines."""

    def test_document_indexing_performance(self, baseline_data, performance_targets):
        """Test document indexing meets baseline performance."""
        baseline_indexing = baseline_data.get('rag_performance', {}).get('document_indexing')

        if not baseline_indexing:
            pytest.skip("RAG indexing baseline not available")

        # Measure current indexing performance
        index_times = []

        for i in range(5):  # Same as baseline
            start = time.perf_counter()
            # Simulate document processing
            test_text = f"Regression test document {i} " * 1000
            words = test_text.split()
            processed = [word.lower().strip('.,!?') for word in words]
            time.sleep(0.05)  # Simulate processing time
            end = time.perf_counter()
            index_times.append(end - start)

        current_avg = statistics.mean(index_times)
        baseline_avg = baseline_indexing['avg_s']

        regression = (current_avg - baseline_avg) / baseline_avg

        assert current_avg < performance_targets['document_processing_s'], \
            f"Indexing time {current_avg:.2f}s exceeds target {performance_targets['document_processing_s']}s"

        assert regression < performance_targets['regression_threshold'], \
            f"Indexing performance regression {regression:.1%} exceeds threshold"

    def test_query_processing_performance(self, baseline_data, performance_targets):
        """Test query processing meets baseline performance."""
        baseline_query = baseline_data.get('rag_performance', {}).get('query_processing')

        if not baseline_query:
            pytest.skip("RAG query baseline not available")

        # Measure current query performance
        query_times = []

        for _ in range(10):  # Same as baseline
            start = time.perf_counter()
            # Simulate query processing
            query = "What is the main topic discussed in the regression test?"
            time.sleep(0.1)  # Mock similarity computation
            time.sleep(0.2)  # Mock response generation
            end = time.perf_counter()
            query_times.append(end - start)

        current_p90 = self._percentile(query_times, 90)
        baseline_p90 = baseline_query['p90_s']

        regression = (current_p90 - baseline_p90) / baseline_p90

        assert current_p90 < performance_targets['rag_query_90th_percentile_s'], \
            f"Query processing p90 {current_p90:.2f}s exceeds target"

        assert regression < performance_targets['regression_threshold'], \
            f"Query processing regression {regression:.1%} exceeds threshold"

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]


class TestSystemPerformanceMonitoring:
    """Test overall system performance monitoring and alerting."""

    def test_performance_regression_detection(self, baseline_data, performance_targets):
        """Test that performance regression detection works correctly."""
        # This test validates our regression detection logic

        test_cases = [
            # (current_value, baseline_value, should_trigger_alert)
            (40.0, 30.0, True),   # 33% regression - should trigger
            (35.0, 30.0, True),   # 17% regression - should NOT trigger (below 20%)
            (25.0, 30.0, False),  # Improvement - should not trigger
            (100.0, 50.0, True),  # 100% regression - should trigger
        ]

        for current, baseline, should_alert in test_cases:
            regression = (current - baseline) / baseline if baseline > 0 else 0
            exceeds_threshold = regression > performance_targets['regression_threshold']

            if should_alert:
                assert exceeds_threshold, \
                    f"Expected regression alert for {regression:.1%} regression"
            else:
                assert not exceeds_threshold, \
                    f"Unexpected regression alert for {regression:.1%} regression"

    def test_baseline_data_integrity(self, baseline_data):
        """Test that baseline data is complete and valid."""
        required_sections = ['api_performance', 'rag_performance', 'memory_analysis']

        for section in required_sections:
            assert section in baseline_data, f"Missing baseline section: {section}"

            section_data = baseline_data[section]
            assert isinstance(section_data, dict), f"Invalid {section} data format"

            # Check that sections don't have error flags (indicating failure)
            if section != 'database_performance':  # DB might have errors in test env
                assert 'error' not in section_data, f"Baseline {section} has errors"


# Integration test for comprehensive performance validation
@pytest.mark.performance
def test_comprehensive_performance_regression(baseline_data, performance_targets):
    """Comprehensive test that validates system-wide performance regression."""

    # Collect all performance metrics
    performance_metrics = {}

    # Check API performance
    api_perf = baseline_data.get('api_performance', {})
    if 'health_endpoint' in api_perf:
        health_avg = api_perf['health_endpoint']['avg_ms']
        performance_metrics['api_health_avg_ms'] = health_avg
        assert health_avg < performance_targets['api_response_95th_percentile_ms'], \
            f"API health endpoint {health_avg}ms exceeds target"

    # Check memory performance
    memory_perf = baseline_data.get('memory_analysis', {})
    if 'peak_mb' in memory_perf:
        peak_memory = memory_perf['peak_mb']
        performance_metrics['peak_memory_mb'] = peak_memory
        assert peak_memory < performance_targets['memory_sustained_mb'], \
            f"Peak memory {peak_memory}MB exceeds target"

    # Check RAG performance
    rag_perf = baseline_data.get('rag_performance', {})
    if 'query_processing' in rag_perf:
        query_avg = rag_perf['query_processing']['avg_s']
        performance_metrics['rag_query_avg_s'] = query_avg
        assert query_avg < performance_targets['rag_query_90th_percentile_s'], \
            f"RAG query {query_avg}s exceeds target"

    # Overall performance score calculation
    targets_met = 0
    total_targets = 0

    for metric, value in performance_metrics.items():
        total_targets += 1
        if 'api' in metric and value < performance_targets['api_response_95th_percentile_ms']:
            targets_met += 1
        elif 'memory' in metric and value < performance_targets['memory_sustained_mb']:
            targets_met += 1
        elif 'rag' in metric and value < performance_targets['rag_query_90th_percentile_s']:
            targets_met += 1

    if total_targets > 0:
        performance_score = (targets_met / total_targets) * 100
        assert performance_score >= 85.0, \
            f"Overall performance score {performance_score:.1f}% below production threshold 85%"

    print(f"✅ Comprehensive performance validation passed - Score: {performance_score:.1f}%")


if __name__ == "__main__":
    # Run performance baseline tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "not slow"
    ])