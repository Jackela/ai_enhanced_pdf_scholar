"""
RAGRecoveryService Tests

Tests for the specialized service responsible for detecting and recovering
from RAG index corruption, system failures, and data integrity issues.
"""

import json
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.database.models import DocumentModel
from src.services.rag.exceptions import RAGRecoveryError
from src.services.rag.recovery_service import RAGRecoveryService


class TestRAGRecoveryService:
    """Test suite for RAGRecoveryService corruption detection and recovery."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test data."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_index_builder(self):
        """Mock index builder for recovery operations."""
        mock = Mock()
        mock.build_index = AsyncMock(return_value={"status": "success", "chunks": 50})
        mock.verify_index = AsyncMock(return_value=True)
        mock.delete_index = AsyncMock(return_value={"deleted": True})
        return mock

    @pytest.fixture
    def mock_file_manager(self):
        """Mock file manager for file operations."""
        mock = Mock()
        mock.cleanup_orphaned_files = AsyncMock(return_value=5)
        mock.verify_file_integrity = AsyncMock(return_value=True)
        mock.create_backup = AsyncMock(return_value="/path/to/backup")
        mock.restore_from_backup = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_health_monitor(self):
        """Mock health monitoring service."""
        mock = Mock()
        mock.check_system_health = AsyncMock(return_value={
            "status": "healthy",
            "disk_space": 85,  # 85% used
            "memory_usage": 70,  # 70% used
            "cpu_usage": 45     # 45% used
        })
        mock.log_health_event = AsyncMock()
        return mock

    @pytest.fixture
    def recovery_service(self, temp_directory, mock_index_builder,
                        mock_file_manager, mock_health_monitor):
        """Create RAGRecoveryService with mocked dependencies."""
        return RAGRecoveryService(
            index_storage_path=temp_directory,
            index_builder=mock_index_builder,
            file_manager=mock_file_manager,
            health_monitor=mock_health_monitor
        )

    @pytest.fixture
    def sample_document(self):
        """Sample document for testing."""
        return DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test/document.pdf",
            content_hash="abc123",
            mime_type="application/pdf"
        )

    @pytest.fixture
    def corrupted_index_setup(self, temp_directory):
        """Setup corrupted index files for testing."""
        doc_index_path = temp_directory / "document_1"
        doc_index_path.mkdir(exist_ok=True)

        # Create corrupted files
        (doc_index_path / "vectors.pkl").write_bytes(b"corrupted_data")
        (doc_index_path / "metadata.json").write_text("invalid json content")

        return doc_index_path

    def test_recovery_service_initialization(self, recovery_service, temp_directory):
        """Test RAGRecoveryService initializes correctly."""
        assert recovery_service.index_storage_path == temp_directory
        assert recovery_service.index_builder is not None
        assert recovery_service.file_manager is not None
        assert recovery_service.health_monitor is not None
        assert recovery_service._recovery_history == []

    @pytest.mark.asyncio
    async def test_detect_corruption_healthy_index(self, recovery_service):
        """Test corruption detection on healthy index."""
        # Given - setup healthy index metadata
        doc_id = 1
        index_path = recovery_service.index_storage_path / f"document_{doc_id}"
        index_path.mkdir(exist_ok=True)

        metadata = {
            "document_id": doc_id,
            "chunks_count": 50,
            "created_at": "2023-01-01T10:00:00Z",
            "content_hash": "abc123",
            "integrity_hash": "valid_hash"
        }
        (index_path / "metadata.json").write_text(json.dumps(metadata))
        (index_path / "vectors.pkl").write_bytes(b"valid_vector_data")

        # When
        corruption_detected = await recovery_service.detect_corruption(doc_id)

        # Then
        assert corruption_detected is False

    @pytest.mark.asyncio
    async def test_detect_corruption_missing_files(self, recovery_service):
        """Test corruption detection with missing index files."""
        # When
        corruption_detected = await recovery_service.detect_corruption(document_id=999)

        # Then
        assert corruption_detected is True

    @pytest.mark.asyncio
    async def test_detect_corruption_malformed_metadata(self, recovery_service, corrupted_index_setup):
        """Test corruption detection with malformed metadata."""
        # When
        corruption_detected = await recovery_service.detect_corruption(document_id=1)

        # Then
        assert corruption_detected is True

    @pytest.mark.asyncio
    async def test_analyze_corruption_comprehensive(self, recovery_service, corrupted_index_setup):
        """Test comprehensive corruption analysis."""
        # When
        analysis = await recovery_service.analyze_corruption(document_id=1)

        # Then
        assert analysis["corruption_detected"] is True
        assert "missing_files" in analysis
        assert "corrupted_files" in analysis
        assert "severity" in analysis
        assert "recommended_actions" in analysis
        assert analysis["severity"] in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_repair_index_full_rebuild(self, recovery_service, sample_document):
        """Test full index repair through complete rebuild."""
        # Given - simulate corruption requiring full rebuild
        recovery_service.detect_corruption = AsyncMock(return_value=True)
        recovery_service.analyze_corruption = AsyncMock(return_value={
            "corruption_detected": True,
            "severity": "high",
            "recommended_actions": ["full_rebuild"]
        })

        # When
        repair_result = await recovery_service.repair_index(sample_document)

        # Then
        assert repair_result["status"] == "success"
        assert repair_result["action"] == "full_rebuild"
        assert "repair_time" in repair_result

        # Verify repair process
        recovery_service.index_builder.delete_index.assert_called_once_with(sample_document.id)
        recovery_service.index_builder.build_index.assert_called_once_with(sample_document)

    @pytest.mark.asyncio
    async def test_repair_index_partial_recovery(self, recovery_service, sample_document):
        """Test partial index repair for minor corruption."""
        # Given - simulate minor corruption
        recovery_service.detect_corruption = AsyncMock(return_value=True)
        recovery_service.analyze_corruption = AsyncMock(return_value={
            "corruption_detected": True,
            "severity": "low",
            "recommended_actions": ["repair_metadata", "verify_vectors"]
        })

        # When
        repair_result = await recovery_service.repair_index(sample_document)

        # Then
        assert repair_result["status"] == "success"
        assert repair_result["action"] == "partial_repair"

        # Verify partial repair didn't trigger full rebuild
        recovery_service.index_builder.delete_index.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_system_status(self, recovery_service):
        """Test comprehensive system health checking."""
        # When
        health_status = await recovery_service.health_check()

        # Then
        assert health_status["overall_status"] == "healthy"
        assert "system_metrics" in health_status
        assert "index_integrity" in health_status
        assert "storage_status" in health_status
        assert "recovery_readiness" in health_status

        # Verify health monitoring was called
        recovery_service.health_monitor.check_system_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_degraded_performance(self, recovery_service):
        """Test health check detection of degraded performance."""
        # Given - simulate high resource usage
        recovery_service.health_monitor.check_system_health.return_value = {
            "status": "degraded",
            "disk_space": 95,  # 95% used - critical
            "memory_usage": 90,  # 90% used - high
            "cpu_usage": 80     # 80% used - high
        }

        # When
        health_status = await recovery_service.health_check()

        # Then
        assert health_status["overall_status"] == "degraded"
        assert health_status["warnings"] is not None
        assert any("disk space" in warning.lower() for warning in health_status["warnings"])

    @pytest.mark.asyncio
    async def test_recovery_workflow_with_backup(self, recovery_service, sample_document):
        """Test recovery workflow with backup creation and restoration."""
        # Given
        recovery_service.detect_corruption = AsyncMock(return_value=True)

        # When
        recovery_result = await recovery_service.recover_with_backup(sample_document)

        # Then
        assert recovery_result["backup_created"] is True
        assert recovery_result["recovery_successful"] is True

        # Verify backup workflow
        recovery_service.file_manager.create_backup.assert_called_once()
        recovery_service.index_builder.build_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_corruption_detection(self, recovery_service):
        """Test bulk corruption detection across multiple documents."""
        # Given
        document_ids = [1, 2, 3, 4, 5]

        # Mock mixed corruption results
        corruption_results = [True, False, True, False, False]
        recovery_service.detect_corruption = AsyncMock(side_effect=corruption_results)

        # When
        bulk_results = await recovery_service.bulk_corruption_check(document_ids)

        # Then
        assert len(bulk_results) == 5
        assert bulk_results[1]["corrupted"] is True
        assert bulk_results[2]["corrupted"] is False
        assert bulk_results["summary"]["total_checked"] == 5
        assert bulk_results["summary"]["corrupted_count"] == 2

    @pytest.mark.asyncio
    async def test_preventive_maintenance_routine(self, recovery_service):
        """Test preventive maintenance to prevent corruption."""
        # When
        maintenance_result = await recovery_service.run_preventive_maintenance()

        # Then
        assert maintenance_result["status"] == "completed"
        assert "checks_performed" in maintenance_result
        assert "issues_resolved" in maintenance_result
        assert "recommendations" in maintenance_result

        # Verify maintenance activities
        recovery_service.file_manager.cleanup_orphaned_files.assert_called_once()
        recovery_service.health_monitor.check_system_health.assert_called()

    @pytest.mark.asyncio
    async def test_corruption_pattern_analysis(self, recovery_service):
        """Test analysis of corruption patterns for prediction."""
        # Given - simulate corruption history
        corruption_events = [
            {"document_id": 1, "timestamp": "2023-01-01T10:00:00Z", "type": "metadata_corruption"},
            {"document_id": 2, "timestamp": "2023-01-01T11:00:00Z", "type": "vector_corruption"},
            {"document_id": 3, "timestamp": "2023-01-01T12:00:00Z", "type": "metadata_corruption"},
        ]
        recovery_service._recovery_history = corruption_events

        # When
        pattern_analysis = await recovery_service.analyze_corruption_patterns()

        # Then
        assert "most_common_type" in pattern_analysis
        assert "frequency_analysis" in pattern_analysis
        assert "risk_prediction" in pattern_analysis
        assert pattern_analysis["most_common_type"] == "metadata_corruption"

    @pytest.mark.asyncio
    async def test_emergency_recovery_procedure(self, recovery_service):
        """Test emergency recovery for critical system failures."""
        # Given - simulate critical system state
        recovery_service.health_monitor.check_system_health.return_value = {
            "status": "critical",
            "disk_space": 98,  # 98% used
            "memory_usage": 95,  # 95% used
            "cpu_usage": 90     # 90% used
        }

        # When
        emergency_result = await recovery_service.emergency_recovery()

        # Then
        assert emergency_result["status"] == "initiated"
        assert emergency_result["actions_taken"] is not None
        assert "cleanup_performed" in emergency_result
        assert "space_reclaimed" in emergency_result

    @pytest.mark.asyncio
    async def test_recovery_rollback_mechanism(self, recovery_service, sample_document):
        """Test rollback mechanism when recovery fails."""
        # Given - simulate recovery failure
        recovery_service.index_builder.build_index.side_effect = Exception("Recovery failed")
        recovery_service.detect_corruption = AsyncMock(return_value=True)

        # When
        recovery_result = await recovery_service.recover_with_rollback(sample_document)

        # Then
        assert recovery_result["status"] == "failed"
        assert recovery_result["rollback_performed"] is True

        # Verify rollback actions
        recovery_service.file_manager.restore_from_backup.assert_called_once()

    def test_recovery_metrics_collection(self, recovery_service):
        """Test collection of recovery performance metrics."""
        # Given - simulate recovery operations
        recovery_service._recovery_history = [
            {"timestamp": time.time() - 3600, "duration": 120, "success": True},
            {"timestamp": time.time() - 1800, "duration": 95, "success": True},
            {"timestamp": time.time() - 900, "duration": 200, "success": False}
        ]

        # When
        metrics = recovery_service.get_recovery_metrics()

        # Then
        assert "total_recoveries" in metrics
        assert "success_rate" in metrics
        assert "average_duration" in metrics
        assert "recent_activity" in metrics
        assert metrics["total_recoveries"] == 3
        assert 0 <= metrics["success_rate"] <= 1

    @pytest.mark.asyncio
    async def test_proactive_corruption_prevention(self, recovery_service):
        """Test proactive measures to prevent corruption."""
        # When
        prevention_result = await recovery_service.run_corruption_prevention()

        # Then
        assert prevention_result["status"] == "completed"
        assert "preventive_actions" in prevention_result
        assert "risk_mitigation" in prevention_result
        assert "system_hardening" in prevention_result

    @pytest.mark.asyncio
    async def test_recovery_notification_system(self, recovery_service, sample_document):
        """Test notification system for recovery events."""
        # Given
        mock_notifier = Mock()
        mock_notifier.send_alert = AsyncMock()
        recovery_service.notifier = mock_notifier

        # When
        await recovery_service.repair_index(sample_document)

        # Then - verify notification was sent
        recovery_service.notifier.send_alert.assert_called_once()
        call_args = recovery_service.notifier.send_alert.call_args
        assert "recovery_completed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_recovery_audit_logging(self, recovery_service, sample_document):
        """Test comprehensive audit logging for recovery operations."""
        # Given
        recovery_service.detect_corruption = AsyncMock(return_value=True)

        # When
        await recovery_service.repair_index(sample_document)

        # Then - verify audit log entries
        assert len(recovery_service._recovery_history) > 0
        last_entry = recovery_service._recovery_history[-1]
        assert last_entry["document_id"] == sample_document.id
        assert last_entry["action"] == "repair"
        assert "timestamp" in last_entry
        assert "duration" in last_entry


class TestRAGRecoveryServiceErrorHandling:
    """Test error handling and edge cases for RAGRecoveryService."""

    @pytest.fixture
    def failing_recovery_service(self, temp_directory):
        """Create recovery service with failing dependencies."""
        mock_index_builder = Mock()
        mock_index_builder.build_index = AsyncMock(side_effect=Exception("Index builder failed"))

        mock_file_manager = Mock()
        mock_file_manager.cleanup_orphaned_files = AsyncMock(side_effect=Exception("File manager failed"))

        mock_health_monitor = Mock()
        mock_health_monitor.check_system_health = AsyncMock(side_effect=Exception("Health monitor failed"))

        return RAGRecoveryService(
            index_storage_path=temp_directory,
            index_builder=mock_index_builder,
            file_manager=mock_file_manager,
            health_monitor=mock_health_monitor
        )

    @pytest.mark.asyncio
    async def test_recovery_failure_handling(self, failing_recovery_service, sample_document):
        """Test handling of recovery operation failures."""
        # When/Then
        with pytest.raises(RAGRecoveryError) as exc_info:
            await failing_recovery_service.repair_index(sample_document)

        assert "Recovery operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_failure_handling(self, failing_recovery_service):
        """Test handling of health check failures."""
        # When
        health_status = await failing_recovery_service.health_check()

        # Then
        assert health_status["overall_status"] == "unknown"
        assert "health_check_error" in health_status

    @pytest.mark.asyncio
    async def test_cascade_failure_prevention(self, recovery_service, sample_document):
        """Test prevention of cascade failures during recovery."""
        # Given - simulate partial system failure
        recovery_service.index_builder.build_index.side_effect = Exception("Temporary failure")

        # When
        recovery_result = await recovery_service.safe_recovery(sample_document)

        # Then - should handle failure gracefully
        assert recovery_result["status"] == "failed_safely"
        assert recovery_result["cascade_prevented"] is True

    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self, recovery_service):
        """Test handling of resource exhaustion during recovery."""
        # Given - simulate resource exhaustion
        recovery_service.health_monitor.check_system_health.return_value = {
            "status": "critical",
            "disk_space": 99,
            "memory_usage": 98,
            "cpu_usage": 95
        }

        # When
        result = await recovery_service.health_check()

        # Then
        assert result["overall_status"] == "critical"
        assert "resource_exhaustion" in result
        assert result["emergency_actions_required"] is True

    @pytest.mark.asyncio
    async def test_concurrent_recovery_operations(self, recovery_service):
        """Test handling of concurrent recovery operations."""
        import asyncio

        # Given
        document_ids = [1, 2, 3, 4, 5]
        documents = [
            DocumentModel(id=i, title=f"Doc {i}", file_path=f"/test{i}.pdf",
                         content_hash=f"hash{i}", mime_type="application/pdf")
            for i in document_ids
        ]

        # When - trigger concurrent recoveries
        tasks = [recovery_service.repair_index(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Then
        assert len(results) == 5
        # Should handle concurrent operations without conflicts
