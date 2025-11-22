"""
Comprehensive tests for RAGRecoveryService.

Tests cover:
- Service initialization
- Corruption analysis (all severity levels)
- Index recovery operations
- System health checks
- Orphaned resource cleanup

Target Coverage: src/services/rag/recovery_service.py (10% → 65%)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.database.models import VectorIndexModel
from src.services.rag.recovery_service import (
    CorruptionDetectionError,
    RAGRecoveryService,
    RecoveryOperationError,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_vector_repo():
    """Mock vector index repository."""
    return Mock()


@pytest.fixture
def mock_file_manager():
    """Mock RAG file manager."""
    return Mock()


@pytest.fixture
def mock_health_checker():
    """Mock health checker."""
    health_checker = Mock()
    health_checker.run_all_checks.return_value = {
        "vector_storage": True,
        "database_connection": True,
        "system_resources": True,
    }
    return health_checker


@pytest.fixture
def recovery_service(mock_vector_repo, mock_file_manager):
    """RAGRecoveryService instance."""
    return RAGRecoveryService(
        vector_repo=mock_vector_repo, file_manager=mock_file_manager
    )


@pytest.fixture
def sample_vector_index(tmp_path):
    """Sample vector index model with real path."""
    index_path = tmp_path / "test_index"
    index_path.mkdir()
    return VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(index_path),
        index_hash="idx_hash",
        chunk_count=10,
    )


# ============================================================================
# Initialization Tests
# ============================================================================


def test_recovery_service_initialization(recovery_service):
    """Test recovery service initializes correctly."""
    assert recovery_service.vector_repo is not None
    assert recovery_service.file_manager is not None
    assert recovery_service.health_checker is not None
    assert recovery_service.recovery_orchestrator is not None


def test_recovery_service_with_custom_health_checker(
    mock_vector_repo, mock_file_manager, mock_health_checker
):
    """Test recovery service accepts custom health checker."""
    service = RAGRecoveryService(
        vector_repo=mock_vector_repo,
        file_manager=mock_file_manager,
        health_checker=mock_health_checker,
    )

    assert service.health_checker is mock_health_checker


# ============================================================================
# Corruption Analysis - Severity Levels
# ============================================================================


def test_analyze_index_corruption_missing_directory(recovery_service):
    """Test corruption analysis for missing directory."""
    # Create index with non-existent path
    vector_index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/non/existent/path",
        index_hash="hash",
        chunk_count=10,
    )

    # Analyze
    result = recovery_service.analyze_index_corruption(vector_index)

    # Verify critical severity
    assert result["corruption_detected"] is True
    assert result["corruption_severity"] == "critical"
    assert "missing_directory" in result["corruption_types"]
    assert "Rebuild index completely" in result["recommendations"]


def test_analyze_index_corruption_missing_files(recovery_service, sample_vector_index):
    """Test corruption analysis for missing required files."""
    # Index directory exists but files missing (tmp_path creates empty dir)

    # Analyze
    result = recovery_service.analyze_index_corruption(sample_vector_index)

    # Verify
    assert result["corruption_detected"] is True
    assert result["corruption_severity"] == "critical"
    assert "missing_files" in result["corruption_types"]
    assert len(result["missing_files"]) > 0
    assert "default__vector_store.json" in result["missing_files"]


def test_analyze_index_corruption_corrupted_json(recovery_service, sample_vector_index):
    """Test corruption analysis for corrupted JSON files."""
    index_path = Path(sample_vector_index.index_path)

    # Create corrupted JSON file
    vector_store_file = index_path / "default__vector_store.json"
    vector_store_file.write_text("{ invalid json")

    # Analyze
    result = recovery_service.analyze_index_corruption(sample_vector_index)

    # Verify
    assert result["corruption_detected"] is True
    assert "corrupted_files" in result["corruption_types"]
    assert any("JSON decode error" in f for f in result["corrupted_files"])


def test_analyze_index_corruption_empty_files(recovery_service, sample_vector_index):
    """Test corruption analysis for empty files."""
    index_path = Path(sample_vector_index.index_path)

    # Create empty file
    vector_store_file = index_path / "default__vector_store.json"
    vector_store_file.write_text("")

    # Analyze
    result = recovery_service.analyze_index_corruption(sample_vector_index)

    # Verify
    assert result["corruption_detected"] is True
    assert "empty_files" in result["corruption_types"]
    assert "default__vector_store.json" in result["file_size_issues"]


def test_analyze_index_corruption_valid_index(recovery_service, sample_vector_index):
    """Test corruption analysis for valid index."""
    index_path = Path(sample_vector_index.index_path)

    # Create valid files
    (index_path / "default__vector_store.json").write_text(
        json.dumps({"embedding_dict": {}})
    )
    (index_path / "graph_store.json").write_text(json.dumps({}))
    (index_path / "index_store.json").write_text(json.dumps({}))

    # Analyze
    result = recovery_service.analyze_index_corruption(sample_vector_index)

    # Verify
    assert result["corruption_detected"] is False
    assert result["corruption_severity"] == "none"


# ============================================================================
# Corruption Recovery
# ============================================================================


def test_recover_corrupted_index_no_corruption(recovery_service, sample_vector_index):
    """Test recovery when no corruption detected."""
    index_path = Path(sample_vector_index.index_path)

    # Create valid files
    (index_path / "default__vector_store.json").write_text(
        json.dumps({"embedding_dict": {}})
    )
    (index_path / "graph_store.json").write_text(json.dumps({}))
    (index_path / "index_store.json").write_text(json.dumps({}))

    # Recover
    result = recovery_service.recover_corrupted_index(sample_vector_index)

    # Verify
    assert result["recovery_successful"] is True
    assert "no_action_needed" in result["repair_actions"]
    assert result["error"] is None


def test_recover_corrupted_index_critical_with_callback(
    recovery_service, sample_vector_index
):
    """Test recovery of critical corruption with rebuild callback."""
    # Index has missing directory (critical)
    sample_vector_index.index_path = "/non/existent/path"

    # Mock rebuild callback
    rebuild_callback = Mock(return_value=True)

    # Recover
    result = recovery_service.recover_corrupted_index(
        sample_vector_index, rebuild_callback=rebuild_callback
    )

    # Verify
    assert "full_rebuild" in result["repair_actions"]
    assert result["recovery_successful"] is True
    rebuild_callback.assert_called_once_with(sample_vector_index)


def test_recover_corrupted_index_critical_no_callback(recovery_service):
    """Test recovery fails when rebuild needed but no callback provided."""
    vector_index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/non/existent",
        index_hash="hash",
        chunk_count=10,
    )

    # Recover without callback
    result = recovery_service.recover_corrupted_index(vector_index)

    # Verify
    assert result["recovery_successful"] is False
    assert "Rebuild required but no callback provided" in result["error"]


def test_recover_corrupted_index_moderate_partial_success(
    recovery_service, sample_vector_index
):
    """Test moderate corruption triggers partial repair attempt."""
    index_path = Path(sample_vector_index.index_path)

    # Create partially valid index (vector store valid, one other file corrupted/empty)
    (index_path / "default__vector_store.json").write_text(
        json.dumps({"embedding_dict": {}})
    )
    (index_path / "graph_store.json").write_text("")  # Empty file = moderate corruption
    (index_path / "index_store.json").write_text(json.dumps({}))

    # Recover (without callback, so it will attempt partial repair)
    result = recovery_service.recover_corrupted_index(sample_vector_index)

    # Verify partial repair was attempted (may or may not succeed without full mocking)
    assert "partial_repair" in result["repair_actions"]
    # Note: recovery_successful may be False if verify still fails,
    # but we've verified the repair path was taken


def test_recover_corrupted_index_force_rebuild(recovery_service, sample_vector_index):
    """Test force rebuild regardless of corruption level."""
    index_path = Path(sample_vector_index.index_path)

    # Create valid index
    (index_path / "default__vector_store.json").write_text(
        json.dumps({"embedding_dict": {}})
    )
    (index_path / "graph_store.json").write_text(json.dumps({}))
    (index_path / "index_store.json").write_text(json.dumps({}))

    # Mock rebuild callback
    rebuild_callback = Mock(return_value=True)

    # Force rebuild
    result = recovery_service.recover_corrupted_index(
        sample_vector_index, force_rebuild=True, rebuild_callback=rebuild_callback
    )

    # Verify rebuild forced
    assert "full_rebuild" in result["repair_actions"]
    rebuild_callback.assert_called_once()


# ============================================================================
# System Health & Cleanup
# ============================================================================


def test_perform_system_health_check_healthy(
    recovery_service, mock_vector_repo, mock_file_manager
):
    """Test system health check with healthy system."""
    # Mock all components healthy
    mock_vector_repo.get_index_statistics.return_value = {"total_indexes": 5}
    mock_vector_repo.get_all_indexes.return_value = []
    mock_file_manager.find_orphaned_directories.return_value = []

    # Run health check
    report = recovery_service.perform_system_health_check()

    # Verify
    assert report["overall_status"] == "healthy"
    assert len(report["corrupted_indexes"]) == 0


def test_perform_system_health_check_degraded(
    recovery_service, mock_vector_repo, mock_file_manager, sample_vector_index
):
    """Test system health check with degraded system."""
    from unittest.mock import patch

    # Mock health check failure using patch
    with patch.object(
        recovery_service.health_checker,
        "run_all_checks",
        return_value={
            "vector_storage": False,
            "database_connection": True,
            "system_resources": True,
        },
    ):
        # Mock one corrupted index (missing directory)
        corrupted_index = VectorIndexModel(
            id=1,
            document_id=1,
            index_path="/non/existent/path",  # Missing directory = critical corruption
            index_hash="hash",
            chunk_count=10,
        )
        mock_vector_repo.get_all_indexes.return_value = [corrupted_index]
        mock_vector_repo.cleanup_orphaned_indexes.return_value = 0
        mock_file_manager.find_orphaned_directories.return_value = []
        mock_file_manager.cleanup_orphaned_directories.return_value = 0

        # Run health check
        report = recovery_service.perform_system_health_check()

        # Verify degraded or critical status (not healthy)
        assert report["overall_status"] != "healthy"
        assert len(report["recommendations"]) > 0


def test_identify_corrupted_indexes_multiple(
    recovery_service, mock_vector_repo, tmp_path
):
    """Test identifying multiple corrupted indexes."""
    # Create multiple indexes, some corrupted
    indexes = [
        VectorIndexModel(
            id=i,
            document_id=i,
            index_path="/non/existent" if i % 2 == 0 else str(tmp_path / f"idx{i}"),
            index_hash=f"hash{i}",
            chunk_count=10,
        )
        for i in range(1, 4)
    ]

    # Create valid directories for odd indexes
    for idx in indexes:
        if idx.id % 2 != 0:
            Path(idx.index_path).mkdir(exist_ok=True)

    mock_vector_repo.get_all_indexes.return_value = indexes

    # Identify corrupted
    corrupted = recovery_service.identify_corrupted_indexes()

    # Verify at least one corrupted detected
    assert len(corrupted) > 0
    assert all("corruption_severity" in idx for idx in corrupted)


def test_cleanup_orphaned_resources_success(
    recovery_service, mock_vector_repo, mock_file_manager
):
    """Test cleanup of orphaned resources."""
    # Mock orphans
    mock_vector_repo.cleanup_orphaned_indexes.return_value = 2
    mock_vector_repo.get_all_indexes.return_value = []
    mock_file_manager.find_orphaned_directories.return_value = [
        "/orphan1",
        "/orphan2",
        "/orphan3",
    ]
    mock_file_manager.cleanup_orphaned_directories.return_value = 3

    # Cleanup
    total_cleaned = recovery_service.cleanup_orphaned_resources()

    # Verify
    assert total_cleaned == 5  # 2 DB + 3 FS


def test_get_recovery_metrics(recovery_service, mock_vector_repo, mock_file_manager):
    """Test getting recovery metrics."""
    # Mock stats
    mock_vector_repo.get_index_statistics.return_value = {"total_indexes": 10}
    mock_file_manager.get_storage_statistics.return_value = {"total_size_mb": 500}

    # Mock recovery orchestrator metrics
    mock_orchestrator_metrics = {
        "total_operations": 100,
        "successful_operations": 95,
        "failed_operations": 5,
    }
    recovery_service.recovery_orchestrator.get_comprehensive_metrics = (
        lambda: mock_orchestrator_metrics
    )

    # Get metrics
    metrics = recovery_service.get_recovery_metrics()

    # Verify structure
    assert metrics["service_name"] == "RAGRecoveryService"
    assert "health_status" in metrics
    assert "storage_stats" in metrics
    assert "database_stats" in metrics
    assert metrics["database_stats"]["total_indexes"] == 10
    assert metrics["recovery_orchestrator_metrics"]["total_operations"] == 100
