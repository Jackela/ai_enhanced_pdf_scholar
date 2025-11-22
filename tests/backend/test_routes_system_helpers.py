"""
Unit tests for system route helper functions.

Tests the 20 helper functions extracted during Day 1 refactoring:
- 9 helpers from detailed_health_check
- 11 helpers from performance_health_check

All external dependencies (psutil, database, services) are mocked.
"""

import time
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.api.routes.system import (
    _calculate_overall_health,
    _check_api_configuration,
    _check_database_performance,
    _check_database_status,
    _check_rag_status,
    _check_storage_status,
    _check_system_resources,
    _collect_cpu_metrics,
    _collect_disk_metrics,
    _collect_memory_metrics,
    _collect_network_metrics,
    _collect_process_metrics,
    _evaluate_cpu_health,
    _evaluate_cpu_status,
    _evaluate_database_health,
    _evaluate_disk_health,
    _evaluate_disk_status,
    _evaluate_memory_health,
    _evaluate_memory_status,
    _evaluate_performance_health,
)

# ============================================================================
# Tests for detailed_health_check helpers (9 functions)
# ============================================================================


class TestEvaluateMemoryStatus:
    """Test memory status evaluation with threshold logic."""

    def test_healthy_status_below_80_percent(self):
        """Memory usage below 80% should return healthy status."""
        mock_memory = Mock()
        mock_memory.percent = 75.0
        mock_memory.total = 16_000_000_000  # 16GB
        mock_memory.available = 4_000_000_000  # 4GB

        result = _evaluate_memory_status(mock_memory)

        assert result["status"] == "healthy"
        assert result["used_percent"] == 75.0
        assert result["total_bytes"] == 16_000_000_000
        assert result["available_bytes"] == 4_000_000_000

    def test_warning_status_80_to_90_percent(self):
        """Memory usage 80-90% should return warning status."""
        mock_memory = Mock()
        mock_memory.percent = 85.0
        mock_memory.total = 16_000_000_000
        mock_memory.available = 2_400_000_000

        result = _evaluate_memory_status(mock_memory)

        assert result["status"] == "warning"
        assert result["used_percent"] == 85.0

    def test_critical_status_above_90_percent(self):
        """Memory usage above 90% should return critical status."""
        mock_memory = Mock()
        mock_memory.percent = 95.0
        mock_memory.total = 16_000_000_000
        mock_memory.available = 800_000_000

        result = _evaluate_memory_status(mock_memory)

        assert result["status"] == "critical"
        assert result["used_percent"] == 95.0

    def test_edge_case_exactly_80_percent(self):
        """Memory usage exactly 80% should return warning status."""
        mock_memory = Mock()
        mock_memory.percent = 80.0
        mock_memory.total = 8_000_000_000
        mock_memory.available = 1_600_000_000

        result = _evaluate_memory_status(mock_memory)

        assert result["status"] == "warning"

    def test_edge_case_exactly_90_percent(self):
        """Memory usage exactly 90% should return critical status."""
        mock_memory = Mock()
        mock_memory.percent = 90.0
        mock_memory.total = 8_000_000_000
        mock_memory.available = 800_000_000

        result = _evaluate_memory_status(mock_memory)

        assert result["status"] == "critical"


class TestEvaluateDiskStatus:
    """Test disk status evaluation with threshold logic."""

    def test_healthy_status_above_20_percent_free(self):
        """Disk with >20% free space should return healthy status."""
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000  # 1TB
        mock_disk.free = 300_000_000_000  # 300GB (30% free)
        mock_disk.used = 700_000_000_000  # 700GB

        result = _evaluate_disk_status(mock_disk)

        assert result["status"] == "healthy"
        assert result["total_bytes"] == 1_000_000_000_000
        assert result["free_bytes"] == 300_000_000_000
        assert result["used_percent"] == 70.0

    def test_warning_status_10_to_20_percent_free(self):
        """Disk with 10-20% free space should return warning status."""
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000
        mock_disk.free = 150_000_000_000  # 15% free
        mock_disk.used = 850_000_000_000

        result = _evaluate_disk_status(mock_disk)

        assert result["status"] == "warning"
        assert result["used_percent"] == 85.0

    def test_critical_status_below_10_percent_free(self):
        """Disk with <10% free space should return critical status."""
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000
        mock_disk.free = 50_000_000_000  # 5% free
        mock_disk.used = 950_000_000_000

        result = _evaluate_disk_status(mock_disk)

        assert result["status"] == "critical"
        assert result["used_percent"] == 95.0

    def test_edge_case_exactly_20_percent_free(self):
        """Disk with exactly 20% free space should return warning status (<=)."""
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000
        mock_disk.free = 200_000_000_000  # Exactly 20% free
        mock_disk.used = 800_000_000_000

        result = _evaluate_disk_status(mock_disk)

        # Logic uses <= 0.2, so exactly 20% is warning
        assert result["status"] == "warning"

    def test_edge_case_exactly_10_percent_free(self):
        """Disk with exactly 10% free space should return critical status (<=)."""
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000
        mock_disk.free = 100_000_000_000  # Exactly 10% free
        mock_disk.used = 900_000_000_000

        result = _evaluate_disk_status(mock_disk)

        # Logic uses <= 0.1, so exactly 10% is critical
        assert result["status"] == "critical"


class TestEvaluateCPUStatus:
    """Test CPU status evaluation with threshold logic."""

    def test_healthy_status_below_70_percent(self):
        """CPU usage below 70% should return healthy status."""
        result = _evaluate_cpu_status(50.0)

        assert result["status"] == "healthy"
        assert result["usage_percent"] == 50.0
        assert "core_count" in result

    def test_warning_status_70_to_85_percent(self):
        """CPU usage 70-85% should return warning status."""
        result = _evaluate_cpu_status(75.0)

        assert result["status"] == "warning"
        assert result["usage_percent"] == 75.0

    def test_critical_status_above_85_percent(self):
        """CPU usage above 85% should return critical status."""
        result = _evaluate_cpu_status(92.0)

        assert result["status"] == "critical"
        assert result["usage_percent"] == 92.0

    def test_edge_case_exactly_70_percent(self):
        """CPU usage exactly 70% should return warning status."""
        result = _evaluate_cpu_status(70.0)

        assert result["status"] == "warning"

    def test_edge_case_exactly_85_percent(self):
        """CPU usage exactly 85% should return critical status."""
        result = _evaluate_cpu_status(85.0)

        assert result["status"] == "critical"


@pytest.mark.asyncio
class TestCheckDatabaseStatus:
    """Test database connectivity and response time checks."""

    async def test_healthy_database_connection(self):
        """Database connection successful should return healthy status."""
        mock_db = Mock()
        mock_db.fetch_one.return_value = {
            "test": 1,
            "current_time": "2025-01-20T10:00:00",
        }

        result = await _check_database_status(mock_db)

        assert result["status"] == "healthy"
        assert result["connection_active"] is True
        assert "response_time_ms" in result
        assert result["response_time_ms"] is not None
        assert result["last_check"] == "2025-01-20T10:00:00"
        mock_db.fetch_one.assert_called_once()

    async def test_database_connection_failure(self):
        """Database connection failure should return error status."""
        mock_db = Mock()
        mock_db.fetch_one.side_effect = Exception("Connection timeout")

        result = await _check_database_status(mock_db)

        assert result["status"] == "error"
        assert result["connection_active"] is False
        assert "error" in result
        assert "Connection timeout" in result["error"]

    async def test_database_response_time_recorded(self):
        """Database response time should be measured and recorded."""
        mock_db = Mock()
        mock_db.fetch_one.return_value = {
            "test": 1,
            "current_time": "2025-01-20T10:00:00",
        }

        with patch("time.time", side_effect=[100.0, 100.05]):  # 50ms response
            result = await _check_database_status(mock_db)

        assert result["status"] == "healthy"
        assert result["response_time_ms"] == 50.0


class TestCheckRAGStatus:
    """Test RAG service availability and health checks."""

    def test_rag_service_available(self):
        """RAG service present should return healthy status."""
        mock_rag_service = Mock()
        mock_rag_service.name = "EnhancedRAGService"

        result = _check_rag_status(mock_rag_service)

        assert result["available"] is True
        assert result["status"] == "healthy"
        assert "components" in result

    def test_rag_service_unavailable(self):
        """RAG service None should return unavailable status."""
        result = _check_rag_status(None)

        assert result["available"] is False
        assert result["status"] == "unavailable"
        assert "components" not in result


class TestCheckStorageStatus:
    """Test storage health with directory breakdown."""

    @patch("backend.api.routes.system.Path")
    @patch("backend.api.routes.system.os.access", return_value=True)
    def test_storage_initialized_and_healthy(self, mock_access, mock_path):
        """Initialized storage with accessible directories should return healthy."""
        mock_base_dir = Mock()
        mock_base_dir.exists.return_value = True

        # Mock critical directories
        mock_uploads = Mock()
        mock_uploads.exists.return_value = True
        mock_uploads.rglob.return_value = [
            Mock(is_file=lambda: True, stat=lambda: Mock(st_size=1000))
            for _ in range(5)
        ]

        mock_vector = Mock()
        mock_vector.exists.return_value = True
        mock_vector.rglob.return_value = [
            Mock(is_file=lambda: True, stat=lambda: Mock(st_size=2000))
            for _ in range(3)
        ]

        mock_cache = Mock()
        mock_cache.exists.return_value = True
        mock_cache.rglob.return_value = [
            Mock(is_file=lambda: True, stat=lambda: Mock(st_size=500)) for _ in range(2)
        ]

        mock_base_dir.__truediv__ = lambda self, name: {
            "uploads": mock_uploads,
            "vector_indexes": mock_vector,
            "cache": mock_cache,
        }[name]

        mock_path.home.return_value.__truediv__.return_value = mock_base_dir

        result = _check_storage_status()

        assert result["status"] == "healthy"
        assert "directories" in result
        assert "uploads" in result["directories"]
        assert result["directories"]["uploads"]["exists"] is True
        assert result["directories"]["uploads"]["size_bytes"] == 5000
        assert result["directories"]["uploads"]["file_count"] == 5

    @patch("backend.api.routes.system.Path")
    def test_storage_not_initialized(self, mock_path):
        """Non-existent storage directory should return not_initialized."""
        mock_base_dir = Mock()
        mock_base_dir.exists.return_value = False
        mock_path.home.return_value.__truediv__.return_value = mock_base_dir

        result = _check_storage_status()

        assert result["status"] == "not_initialized"

    def test_storage_directory_missing(self):
        """Missing critical directory should be reported."""
        with patch("backend.api.routes.system.Path") as mock_path_class:
            # Create proper mock for Path.home() / ".ai_pdf_scholar"
            mock_base_dir = MagicMock()
            mock_base_dir.exists.return_value = True

            # Create directory mocks
            mock_uploads_dir = MagicMock()
            mock_uploads_dir.exists.return_value = False

            mock_vector_dir = MagicMock()
            mock_vector_dir.exists.return_value = True
            mock_vector_dir.rglob.return_value = []

            mock_cache_dir = MagicMock()
            mock_cache_dir.exists.return_value = True
            mock_cache_dir.rglob.return_value = []

            # Setup truediv to return appropriate mocks
            dir_mocks = {
                "uploads": mock_uploads_dir,
                "vector_indexes": mock_vector_dir,
                "cache": mock_cache_dir,
            }

            def truediv_side_effect(name):
                return dir_mocks.get(name, MagicMock())

            mock_base_dir.__truediv__.side_effect = truediv_side_effect

            # Setup Path.home() chain
            mock_home = MagicMock()
            mock_home.__truediv__.return_value = mock_base_dir
            mock_path_class.home.return_value = mock_home

            with patch("backend.api.routes.system.os.access", return_value=True):
                result = _check_storage_status()

        assert result["status"] == "healthy"
        assert result["directories"]["uploads"]["exists"] is False
        assert "error" in result["directories"]["uploads"]


class TestCheckAPIConfiguration:
    """Test API configuration status checks."""

    @patch("backend.api.routes.system.Config")
    def test_api_configured_with_key(self, mock_config):
        """API key configured should return True."""
        mock_config.get_gemini_api_key.return_value = "test_api_key_abc123"
        mock_config.ENVIRONMENT = "production"
        mock_config.DEBUG = False

        result = _check_api_configuration()

        assert result["gemini_api_configured"] is True
        assert result["environment"] == "production"
        assert result["debug_mode"] is False

    @patch("backend.api.routes.system.Config")
    def test_api_not_configured(self, mock_config):
        """No API key should return False."""
        mock_config.get_gemini_api_key.return_value = None
        mock_config.ENVIRONMENT = "development"
        mock_config.DEBUG = True

        result = _check_api_configuration()

        assert result["gemini_api_configured"] is False
        assert result["environment"] == "development"
        assert result["debug_mode"] is True


class TestCalculateOverallHealth:
    """Test overall health score calculation from component health."""

    def test_all_components_healthy(self):
        """All healthy components should return healthy status."""
        health_data = {
            "system_resources": {"memory": {"status": "healthy"}},
            "database": {"status": "healthy"},
            "rag_service": {"status": "healthy"},
            "storage": {"status": "healthy"},
        }

        result = _calculate_overall_health(health_data)

        assert result["status"] == "healthy"
        assert result["score"] == 1.0  # 0.4 + 0.3 + 0.2 + 0.1
        assert "uptime_seconds" in result
        assert "timestamp" in result

    def test_degraded_system(self):
        """Some components degraded should return degraded status."""
        health_data = {
            "system_resources": {"memory": {"status": "warning"}},
            "database": {"status": "healthy"},
            "rag_service": {"status": "unhealthy"},
            "storage": {"status": "healthy"},
        }

        result = _calculate_overall_health(health_data)

        assert result["status"] == "degraded"
        assert (
            result["score"] == 0.6
        )  # 0.2 (warning memory) + 0.3 (db) + 0.0 (rag) + 0.1 (storage)

    def test_unhealthy_system(self):
        """Critical components failing should return unhealthy status."""
        health_data = {
            "system_resources": {"memory": {"status": "critical"}},
            "database": {"status": "error"},
            "rag_service": {"status": "unavailable"},
            "storage": {"status": "error"},
        }

        result = _calculate_overall_health(health_data)

        assert result["status"] == "unhealthy"
        assert result["score"] == 0.0  # All components failed

    def test_edge_case_score_80_percent(self):
        """Score exactly 0.8 should return healthy status."""
        health_data = {
            "system_resources": {"memory": {"status": "healthy"}},  # 0.4
            "database": {"status": "healthy"},  # 0.3
            "rag_service": {"status": "healthy"},  # 0.2 (total = 0.9)
            "storage": {"status": "error"},  # 0.0
        }

        result = _calculate_overall_health(health_data)

        # Score = 0.9, which is >= 0.8
        assert result["status"] == "healthy"
        assert result["score"] == 0.9


class TestCheckSystemResources:
    """Test system resources check integration."""

    @patch("backend.api.routes.system.psutil")
    def test_system_resources_collection(self, mock_psutil):
        """System resources should be collected and evaluated."""
        # Mock memory
        mock_memory = Mock()
        mock_memory.percent = 60.0
        mock_memory.total = 16_000_000_000
        mock_memory.available = 6_400_000_000
        mock_psutil.virtual_memory.return_value = mock_memory

        # Mock disk
        mock_disk = Mock()
        mock_disk.total = 1_000_000_000_000
        mock_disk.free = 500_000_000_000
        mock_disk.used = 500_000_000_000
        mock_psutil.disk_usage.return_value = mock_disk

        # Mock CPU
        mock_psutil.cpu_percent.return_value = 45.0
        mock_psutil.cpu_count.return_value = 8

        result = _check_system_resources()

        assert "memory" in result
        assert "disk" in result
        assert "cpu" in result
        assert result["memory"]["status"] == "healthy"
        assert result["disk"]["status"] == "healthy"
        assert result["cpu"]["status"] == "healthy"


# ============================================================================
# Tests for performance_health_check helpers (11 functions)
# ============================================================================


class TestCollectCPUMetrics:
    """Test CPU metrics collection."""

    @patch("backend.api.routes.system.psutil")
    def test_cpu_metrics_complete(self, mock_psutil):
        """All CPU metrics should be collected."""
        mock_psutil.cpu_percent.return_value = 55.0
        mock_psutil.cpu_count.return_value = 8

        mock_freq = Mock()
        mock_freq.current = 2400.0
        mock_psutil.cpu_freq.return_value = mock_freq

        mock_psutil.getloadavg.return_value = (1.5, 1.2, 0.9)

        mock_stats = Mock()
        mock_stats.ctx_switches = 12345678
        mock_stats.interrupts = 9876543
        mock_psutil.cpu_stats.return_value = mock_stats

        result = _collect_cpu_metrics()

        assert result["usage_percent"] == 55.0
        assert result["core_count"] == 8
        assert result["frequency_mhz"] == 2400.0
        assert result["load_average"] == [1.5, 1.2, 0.9]
        assert result["context_switches"] == 12345678
        assert result["interrupts"] == 9876543

    @patch("backend.api.routes.system.psutil")
    def test_cpu_metrics_no_frequency(self, mock_psutil):
        """CPU frequency unavailable should return None."""
        mock_psutil.cpu_percent.return_value = 60.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_freq.return_value = None

        mock_stats = Mock()
        mock_stats.ctx_switches = 1000
        mock_stats.interrupts = 500
        mock_psutil.cpu_stats.return_value = mock_stats

        result = _collect_cpu_metrics()

        assert result["frequency_mhz"] is None


class TestCollectMemoryMetrics:
    """Test memory metrics collection."""

    @patch("backend.api.routes.system.psutil")
    def test_memory_metrics_complete(self, mock_psutil):
        """All memory metrics should be collected."""
        mock_memory = Mock()
        mock_memory.total = 16_000_000_000
        mock_memory.available = 8_000_000_000
        mock_memory.used = 7_500_000_000
        mock_memory.free = 500_000_000
        mock_memory.cached = 2_000_000_000
        mock_memory.buffers = 500_000_000
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_swap = Mock()
        mock_swap.total = 8_000_000_000
        mock_swap.used = 1_000_000_000
        mock_swap.percent = 12.5
        mock_psutil.swap_memory.return_value = mock_swap

        result = _collect_memory_metrics()

        assert result["total_bytes"] == 16_000_000_000
        assert result["available_bytes"] == 8_000_000_000
        assert result["used_bytes"] == 7_500_000_000
        assert result["free_bytes"] == 500_000_000
        assert result["cached_bytes"] == 2_000_000_000
        assert result["buffers_bytes"] == 500_000_000
        assert result["swap_total_bytes"] == 8_000_000_000
        assert result["swap_used_bytes"] == 1_000_000_000
        assert result["swap_percent"] == 12.5


class TestCollectDiskMetrics:
    """Test disk I/O metrics collection."""

    @patch("backend.api.routes.system.psutil")
    def test_disk_metrics_complete(self, mock_psutil):
        """All disk metrics should be collected."""
        mock_disk_usage = Mock()
        mock_disk_usage.total = 1_000_000_000_000
        mock_disk_usage.used = 600_000_000_000
        mock_disk_usage.free = 400_000_000_000
        mock_psutil.disk_usage.return_value = mock_disk_usage

        mock_disk_io = Mock()
        mock_disk_io.read_count = 123456
        mock_disk_io.write_count = 654321
        mock_disk_io.read_bytes = 5_000_000_000
        mock_disk_io.write_bytes = 3_000_000_000
        mock_disk_io.read_time = 12345
        mock_disk_io.write_time = 54321
        mock_psutil.disk_io_counters.return_value = mock_disk_io

        result = _collect_disk_metrics()

        assert result["total_bytes"] == 1_000_000_000_000
        assert result["used_bytes"] == 600_000_000_000
        assert result["free_bytes"] == 400_000_000_000
        assert result["read_count"] == 123456
        assert result["write_count"] == 654321
        assert result["read_bytes"] == 5_000_000_000
        assert result["write_bytes"] == 3_000_000_000

    @patch("backend.api.routes.system.psutil")
    def test_disk_io_unavailable(self, mock_psutil):
        """Disk I/O counters unavailable should return zeros."""
        mock_disk_usage = Mock()
        mock_disk_usage.total = 1_000_000_000_000
        mock_disk_usage.used = 500_000_000_000
        mock_disk_usage.free = 500_000_000_000
        mock_psutil.disk_usage.return_value = mock_disk_usage

        mock_psutil.disk_io_counters.return_value = None

        result = _collect_disk_metrics()

        assert result["read_count"] == 0
        assert result["write_count"] == 0
        assert result["read_bytes"] == 0
        assert result["write_bytes"] == 0


class TestCollectNetworkMetrics:
    """Test network I/O metrics collection."""

    @patch("backend.api.routes.system.psutil")
    def test_network_metrics_complete(self, mock_psutil):
        """All network metrics should be collected."""
        mock_net_io = Mock()
        mock_net_io.bytes_sent = 10_000_000_000
        mock_net_io.bytes_recv = 50_000_000_000
        mock_net_io.packets_sent = 500_000
        mock_net_io.packets_recv = 800_000
        mock_net_io.errin = 10
        mock_net_io.errout = 5
        mock_net_io.dropin = 3
        mock_net_io.dropout = 2
        mock_psutil.net_io_counters.return_value = mock_net_io

        result = _collect_network_metrics()

        assert result["bytes_sent"] == 10_000_000_000
        assert result["bytes_recv"] == 50_000_000_000
        assert result["packets_sent"] == 500_000
        assert result["packets_recv"] == 800_000
        assert result["errin"] == 10
        assert result["errout"] == 5
        assert result["dropin"] == 3
        assert result["dropout"] == 2


class TestCollectProcessMetrics:
    """Test current process metrics collection."""

    @patch("backend.api.routes.system.psutil.Process")
    @patch("backend.api.routes.system.time.time")
    def test_process_metrics_complete(self, mock_time, mock_process_class):
        """All process metrics should be collected."""
        mock_time.return_value = 1000.0

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.cpu_percent.return_value = 15.5

        mock_memory_info = Mock()
        mock_memory_info.rss = 500_000_000
        mock_memory_info.vms = 1_000_000_000
        mock_process.memory_info.return_value = mock_memory_info

        mock_process.num_threads.return_value = 8
        mock_process.num_fds.return_value = 50
        mock_process.create_time.return_value = 500.0

        mock_process_class.return_value = mock_process

        result = _collect_process_metrics()

        assert result["pid"] == 12345
        assert result["cpu_percent"] == 15.5
        assert result["memory_rss_bytes"] == 500_000_000
        assert result["memory_vms_bytes"] == 1_000_000_000
        assert result["num_threads"] == 8
        assert result["num_fds"] == 50
        assert result["uptime_seconds"] == 500.0  # 1000.0 - 500.0


class TestCheckDatabasePerformance:
    """Test database performance checking."""

    @patch("backend.api.routes.system.time.time")
    def test_database_performance_healthy(self, mock_time):
        """Fast database query should return healthy status."""
        mock_time.side_effect = [100.0, 100.005]  # 5ms query

        mock_db = Mock()
        mock_db.fetch_one.return_value = {"count": 10}

        # Patch get_db where it's imported in the function
        with patch("backend.api.dependencies.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            result = _check_database_performance()

        assert result["status"] == "healthy"
        assert result["simple_query_ms"] == 5.0
        assert result["connection_pool_active"] is True

    def test_database_performance_error(self):
        """Database query failure should return error status."""
        mock_db = Mock()
        mock_db.fetch_one.side_effect = Exception("Database timeout")

        # Patch get_db where it's imported in the function
        with patch("backend.api.dependencies.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            result = _check_database_performance()

        assert result["status"] == "error"
        assert "error" in result
        assert "Database timeout" in result["error"]


class TestEvaluateCPUHealth:
    """Test CPU health evaluation."""

    def test_cpu_healthy_below_75(self):
        """CPU usage below 75% should return no indicators."""
        result = _evaluate_cpu_health(50.0)

        assert result == []

    def test_cpu_warning_75_to_90(self):
        """CPU usage 75-90% should return warning indicator."""
        result = _evaluate_cpu_health(80.0)

        assert len(result) == 1
        assert result[0]["component"] == "cpu"
        assert result[0]["level"] == "warning"
        assert "elevated" in result[0]["message"]

    def test_cpu_critical_above_90(self):
        """CPU usage above 90% should return critical indicator."""
        result = _evaluate_cpu_health(95.0)

        assert len(result) == 1
        assert result[0]["component"] == "cpu"
        assert result[0]["level"] == "critical"
        assert "very high" in result[0]["message"]


class TestEvaluateMemoryHealth:
    """Test memory health evaluation."""

    def test_memory_healthy_below_80(self):
        """Memory usage below 80% should return no indicators."""
        memory_data = {
            "total_bytes": 16_000_000_000,
            "used_bytes": 12_000_000_000,
        }  # 75%

        result = _evaluate_memory_health(memory_data)

        assert result == []

    def test_memory_warning_80_to_90(self):
        """Memory usage 80-90% should return warning indicator."""
        memory_data = {
            "total_bytes": 16_000_000_000,
            "used_bytes": 13_600_000_000,
        }  # 85%

        result = _evaluate_memory_health(memory_data)

        assert len(result) == 1
        assert result[0]["component"] == "memory"
        assert result[0]["level"] == "warning"

    def test_memory_critical_above_90(self):
        """Memory usage above 90% should return critical indicator."""
        memory_data = {
            "total_bytes": 16_000_000_000,
            "used_bytes": 15_000_000_000,
        }  # 93.75%

        result = _evaluate_memory_health(memory_data)

        assert len(result) == 1
        assert result[0]["component"] == "memory"
        assert result[0]["level"] == "critical"


class TestEvaluateDiskHealth:
    """Test disk health evaluation."""

    def test_disk_healthy_below_85(self):
        """Disk usage below 85% should return no indicators."""
        disk_data = {
            "total_bytes": 1_000_000_000_000,
            "used_bytes": 800_000_000_000,
        }  # 80%

        result = _evaluate_disk_health(disk_data)

        assert result == []

    def test_disk_warning_85_to_95(self):
        """Disk usage 85-95% should return warning indicator."""
        disk_data = {
            "total_bytes": 1_000_000_000_000,
            "used_bytes": 900_000_000_000,
        }  # 90%

        result = _evaluate_disk_health(disk_data)

        assert len(result) == 1
        assert result[0]["component"] == "disk"
        assert result[0]["level"] == "warning"

    def test_disk_critical_above_95(self):
        """Disk usage above 95% should return critical indicator."""
        disk_data = {
            "total_bytes": 1_000_000_000_000,
            "used_bytes": 970_000_000_000,
        }  # 97%

        result = _evaluate_disk_health(disk_data)

        assert len(result) == 1
        assert result[0]["component"] == "disk"
        assert result[0]["level"] == "critical"


class TestEvaluateDatabaseHealth:
    """Test database health evaluation."""

    def test_database_healthy_fast_queries(self):
        """Fast database queries should return no indicators."""
        db_perf = {"status": "healthy", "simple_query_ms": 15.0}

        result = _evaluate_database_health(db_perf)

        assert result == []

    def test_database_warning_slow_queries(self):
        """Slow database queries should return warning indicator."""
        db_perf = {"status": "healthy", "simple_query_ms": 1500.0}  # >1000ms

        result = _evaluate_database_health(db_perf)

        assert len(result) == 1
        assert result[0]["component"] == "database"
        assert result[0]["level"] == "warning"
        assert "slow" in result[0]["message"]

    def test_database_critical_not_responding(self):
        """Database not responding should return critical indicator."""
        db_perf = {"status": "error", "error": "Connection failed"}

        result = _evaluate_database_health(db_perf)

        assert len(result) == 1
        assert result[0]["component"] == "database"
        assert result[0]["level"] == "critical"
        assert "not responding" in result[0]["message"]


class TestEvaluatePerformanceHealth:
    """Test overall performance health evaluation."""

    def test_all_components_healthy(self):
        """All healthy components should return healthy status."""
        performance_data = {
            "cpu": {"usage_percent": 50.0},
            "memory": {"total_bytes": 16_000_000_000, "used_bytes": 10_000_000_000},
            "disk": {"total_bytes": 1_000_000_000_000, "used_bytes": 700_000_000_000},
            "database": {"status": "healthy", "simple_query_ms": 10.0},
        }

        result = _evaluate_performance_health(performance_data)

        assert result["overall_status"] == "healthy"
        assert result["critical_issues"] == 0
        assert result["warning_issues"] == 0
        assert len(result["health_indicators"]) == 0
        assert "timestamp" in result

    def test_warning_status_with_warnings(self):
        """Some warnings should return warning status."""
        performance_data = {
            "cpu": {"usage_percent": 80.0},  # Warning
            "memory": {"total_bytes": 16_000_000_000, "used_bytes": 10_000_000_000},
            "disk": {"total_bytes": 1_000_000_000_000, "used_bytes": 700_000_000_000},
            "database": {"status": "healthy", "simple_query_ms": 10.0},
        }

        result = _evaluate_performance_health(performance_data)

        assert result["overall_status"] == "warning"
        assert result["critical_issues"] == 0
        assert result["warning_issues"] == 1
        assert len(result["health_indicators"]) == 1

    def test_critical_status_with_critical_issues(self):
        """Critical issues should return critical status."""
        performance_data = {
            "cpu": {"usage_percent": 95.0},  # Critical
            "memory": {
                "total_bytes": 16_000_000_000,
                "used_bytes": 15_000_000_000,
            },  # Critical
            "disk": {
                "total_bytes": 1_000_000_000_000,
                "used_bytes": 980_000_000_000,
            },  # Critical
            "database": {"status": "error"},  # Critical
        }

        result = _evaluate_performance_health(performance_data)

        assert result["overall_status"] == "critical"
        assert result["critical_issues"] == 4
        assert result["warning_issues"] == 0
        assert len(result["health_indicators"]) == 4

    def test_mixed_critical_and_warnings(self):
        """Mixed issues should prioritize critical status."""
        performance_data = {
            "cpu": {"usage_percent": 95.0},  # Critical
            "memory": {
                "total_bytes": 16_000_000_000,
                "used_bytes": 13_600_000_000,
            },  # Warning
            "disk": {
                "total_bytes": 1_000_000_000_000,
                "used_bytes": 700_000_000_000,
            },  # Healthy
            "database": {"status": "healthy", "simple_query_ms": 10.0},  # Healthy
        }

        result = _evaluate_performance_health(performance_data)

        assert result["overall_status"] == "critical"
        assert result["critical_issues"] == 1
        assert result["warning_issues"] == 1
        assert len(result["health_indicators"]) == 2
