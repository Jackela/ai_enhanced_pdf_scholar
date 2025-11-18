"""
Comprehensive tests for RAGCoordinator.

Tests cover:
- Service initialization and dependency setup
- Index building operations (success, validation, overwrite)
- Index loading and querying delegation
- Index rebuilding coordination
- Recovery operations with callbacks
- System health checks
- Orphaned resource cleanup
- Cache and service information methods
- Legacy compatibility methods

Target Coverage: src/services/rag/coordinator.py (15% → 70%)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.database.models import DocumentModel, VectorIndexModel
from src.services.rag.coordinator import RAGCoordinator, RAGCoordinatorError

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    return Mock()


@pytest.fixture
def sample_document():
    """Sample document model."""
    return DocumentModel(
        id=1,
        title="Test Document",
        file_path="/test/doc.pdf",
        file_hash="hash123",
        file_size=1024,
        file_type=".pdf",
    )


@pytest.fixture
def sample_vector_index():
    """Sample vector index model."""
    return VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/test/vector_indexes/1",
        index_hash="idx_hash123",
        chunk_count=10,
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def coordinator_test_mode(mock_db_connection):
    """RAGCoordinator instance in test mode."""
    return RAGCoordinator(
        api_key="test_api_key",
        db_connection=mock_db_connection,
        vector_storage_dir="vector_indexes",
        test_mode=True,
    )


# ============================================================================
# Initialization Tests
# ============================================================================


def test_coordinator_initialization_test_mode(coordinator_test_mode):
    """Test coordinator initializes correctly in test mode."""
    assert coordinator_test_mode.test_mode is True
    assert coordinator_test_mode.api_key == "test_api_key"
    assert coordinator_test_mode.document_repo is not None
    assert coordinator_test_mode.vector_repo is not None
    assert coordinator_test_mode.file_manager is not None
    assert coordinator_test_mode.index_builder is not None
    assert coordinator_test_mode.query_engine is not None
    assert coordinator_test_mode.recovery_service is not None
    assert coordinator_test_mode.health_checker is not None
    assert coordinator_test_mode.transaction_manager is not None


def test_coordinator_services_use_test_mode(coordinator_test_mode):
    """Test that all services are initialized with test_mode=True."""
    assert coordinator_test_mode.index_builder.test_mode is True
    assert coordinator_test_mode.query_engine.test_mode is True


# ============================================================================
# Index Building - Success Paths
# ============================================================================


def test_build_index_from_document_success(
    coordinator_test_mode, sample_document, sample_vector_index
):
    """Test successful index building from document."""
    # Mock vector repo: no existing index
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(return_value=None)
    coordinator_test_mode.vector_repo.create = Mock(return_value=sample_vector_index)

    # Mock transaction manager context
    from unittest.mock import MagicMock

    mock_transaction = MagicMock()
    mock_transaction.__enter__ = Mock(return_value=None)
    mock_transaction.__exit__ = Mock(return_value=None)
    coordinator_test_mode.transaction_manager.transaction_scope = Mock(
        return_value=mock_transaction
    )

    # Mock index builder validation and build
    coordinator_test_mode.index_builder.validate_build_requirements = Mock(
        return_value={"valid": True, "issues": []}
    )
    coordinator_test_mode.index_builder.build_index_for_document = Mock(
        return_value={
            "success": True,
            "index_path": "/test/vector_indexes/1",
            "index_hash": "idx_hash123",
            "chunk_count": 10,
        }
    )

    # Execute
    result = coordinator_test_mode.build_index_from_document(sample_document)

    # Verify
    assert result.document_id == 1
    assert result.chunk_count == 10
    coordinator_test_mode.index_builder.validate_build_requirements.assert_called_once_with(
        sample_document
    )
    coordinator_test_mode.index_builder.build_index_for_document.assert_called_once_with(
        sample_document, False
    )
    coordinator_test_mode.vector_repo.create.assert_called_once()


def test_build_index_from_document_with_overwrite(
    coordinator_test_mode, sample_document, sample_vector_index
):
    """Test index building with overwrite=True updates existing record."""
    # Mock existing index
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(
        return_value=sample_vector_index
    )
    coordinator_test_mode.vector_repo.update = Mock(return_value=sample_vector_index)

    # Mock transaction manager context
    from unittest.mock import MagicMock

    mock_transaction = MagicMock()
    mock_transaction.__enter__ = Mock(return_value=None)
    mock_transaction.__exit__ = Mock(return_value=None)
    coordinator_test_mode.transaction_manager.transaction_scope = Mock(
        return_value=mock_transaction
    )

    # Mock validation and build
    coordinator_test_mode.index_builder.validate_build_requirements = Mock(
        return_value={"valid": True, "issues": []}
    )
    coordinator_test_mode.index_builder.build_index_for_document = Mock(
        return_value={
            "success": True,
            "index_path": "/test/vector_indexes/1_new",
            "index_hash": "new_hash",
            "chunk_count": 15,
        }
    )

    # Execute with overwrite
    coordinator_test_mode.build_index_from_document(sample_document, overwrite=True)

    # Verify update was called instead of create
    coordinator_test_mode.vector_repo.update.assert_called_once()
    # Note: create is a real method, not replaced, so we just verify update was called


# ============================================================================
# Index Building - Error Paths
# ============================================================================


def test_build_index_existing_without_overwrite_raises(
    coordinator_test_mode, sample_document, sample_vector_index
):
    """Test building fails when index exists and overwrite=False."""
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(
        return_value=sample_vector_index
    )

    with pytest.raises(
        RAGCoordinatorError, match="Vector index already exists for document"
    ):
        coordinator_test_mode.build_index_from_document(
            sample_document, overwrite=False
        )


def test_build_index_validation_failure_raises(coordinator_test_mode, sample_document):
    """Test building fails when validation fails."""
    # Mock no existing index
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(return_value=None)

    # Mock validation failure
    coordinator_test_mode.index_builder.validate_build_requirements = Mock(
        return_value={"valid": False, "issues": ["File not found", "Invalid PDF"]}
    )

    with pytest.raises(RAGCoordinatorError, match="Build validation failed"):
        coordinator_test_mode.build_index_from_document(sample_document)


def test_build_index_build_failure_raises(coordinator_test_mode, sample_document):
    """Test building fails when build operation fails."""
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(return_value=None)
    coordinator_test_mode.index_builder.validate_build_requirements = Mock(
        return_value={"valid": True, "issues": []}
    )
    coordinator_test_mode.index_builder.build_index_for_document = Mock(
        return_value={"success": False, "error": "Build process crashed"}
    )

    with pytest.raises(RAGCoordinatorError, match="Index building failed"):
        coordinator_test_mode.build_index_from_document(sample_document)


# ============================================================================
# Delegation Methods - Load & Query
# ============================================================================


def test_load_index_for_document_delegates_to_query_engine(coordinator_test_mode):
    """Test load_index_for_document delegates to query engine."""
    coordinator_test_mode.query_engine.load_index_for_document = Mock(return_value=True)

    result = coordinator_test_mode.load_index_for_document(1)

    assert result is True
    coordinator_test_mode.query_engine.load_index_for_document.assert_called_once_with(
        1
    )


def test_query_document_delegates_to_query_engine(coordinator_test_mode):
    """Test query_document delegates to query engine."""
    coordinator_test_mode.query_engine.query_document = Mock(
        return_value="Test response"
    )

    result = coordinator_test_mode.query_document("test query", 1)

    assert result == "Test response"
    coordinator_test_mode.query_engine.query_document.assert_called_once_with(
        "test query", 1
    )


def test_get_document_index_status_delegates(coordinator_test_mode):
    """Test get_document_index_status delegates to query engine."""
    status = {"document_id": 1, "can_query": True, "has_index": True}
    coordinator_test_mode.query_engine.get_document_query_status = Mock(
        return_value=status
    )

    result = coordinator_test_mode.get_document_index_status(1)

    assert result == status
    coordinator_test_mode.query_engine.get_document_query_status.assert_called_once_with(
        1
    )


# ============================================================================
# Rebuild Operations
# ============================================================================


def test_rebuild_index_success(
    coordinator_test_mode, sample_document, sample_vector_index
):
    """Test successful index rebuild."""
    # Mock document retrieval
    coordinator_test_mode.document_repo.find_by_id = Mock(return_value=sample_document)

    # Mock existing index cleanup
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(
        return_value=sample_vector_index
    )
    coordinator_test_mode.vector_repo.delete = Mock()
    coordinator_test_mode.file_manager.cleanup_index_files = Mock()

    # Mock transaction manager context
    from unittest.mock import MagicMock

    mock_transaction = MagicMock()
    mock_transaction.__enter__ = Mock(return_value=None)
    mock_transaction.__exit__ = Mock(return_value=None)
    coordinator_test_mode.transaction_manager.transaction_scope = Mock(
        return_value=mock_transaction
    )

    # Mock rebuild (calls build_index_from_document internally)
    coordinator_test_mode.index_builder.validate_build_requirements = Mock(
        return_value={"valid": True, "issues": []}
    )
    coordinator_test_mode.index_builder.build_index_for_document = Mock(
        return_value={
            "success": True,
            "index_path": "/test/new_index",
            "index_hash": "new_hash",
            "chunk_count": 12,
        }
    )
    coordinator_test_mode.vector_repo.update = Mock(return_value=sample_vector_index)

    # Execute
    result = coordinator_test_mode.rebuild_index(1)

    # Verify cleanup occurred with original index path from sample_vector_index
    coordinator_test_mode.file_manager.cleanup_index_files.assert_called_once_with(
        "/test/vector_indexes/1"  # Original index path before rebuild
    )
    coordinator_test_mode.vector_repo.delete.assert_called_once_with(
        sample_vector_index.id
    )

    # Verify rebuild occurred
    assert result is not None


def test_rebuild_index_document_not_found_raises(coordinator_test_mode):
    """Test rebuild fails when document not found."""
    coordinator_test_mode.document_repo.find_by_id = Mock(return_value=None)

    with pytest.raises(RAGCoordinatorError, match="Document not found"):
        coordinator_test_mode.rebuild_index(999)


# ============================================================================
# Recovery Operations
# ============================================================================


def test_recover_corrupted_index_success(
    coordinator_test_mode, sample_document, sample_vector_index
):
    """Test successful index recovery."""
    # Mock document and index retrieval
    coordinator_test_mode.document_repo.find_by_id = Mock(return_value=sample_document)
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(
        return_value=sample_vector_index
    )

    # Mock recovery result
    recovery_result = {
        "recovery_successful": True,
        "repair_actions": ["partial_repair"],
        "error": None,
    }
    coordinator_test_mode.recovery_service.recover_corrupted_index = Mock(
        return_value=recovery_result
    )

    # Execute
    result = coordinator_test_mode.recover_corrupted_index(1)

    # Verify
    assert result["recovery_successful"] is True
    coordinator_test_mode.recovery_service.recover_corrupted_index.assert_called_once()
    # Verify callback was passed
    call_args = coordinator_test_mode.recovery_service.recover_corrupted_index.call_args
    assert call_args[0][0] == sample_vector_index  # vector_index argument
    assert call_args[0][1] is False  # force_rebuild=False
    assert callable(call_args[0][2])  # rebuild_callback is callable


def test_recover_corrupted_index_no_index_raises(
    coordinator_test_mode, sample_document
):
    """Test recovery fails when no index exists."""
    coordinator_test_mode.document_repo.find_by_id = Mock(return_value=sample_document)
    coordinator_test_mode.vector_repo.find_by_document_id = Mock(return_value=None)

    with pytest.raises(RAGCoordinatorError, match="No index found for document"):
        coordinator_test_mode.recover_corrupted_index(1)


# ============================================================================
# Cleanup & Health Operations
# ============================================================================


def test_cleanup_orphaned_indexes_delegates(coordinator_test_mode):
    """Test cleanup_orphaned_indexes delegates to recovery service."""
    coordinator_test_mode.recovery_service.cleanup_orphaned_resources = Mock(
        return_value=5
    )

    result = coordinator_test_mode.cleanup_orphaned_indexes()

    assert result == 5
    coordinator_test_mode.recovery_service.cleanup_orphaned_resources.assert_called_once()


def test_perform_system_recovery_check_delegates(coordinator_test_mode):
    """Test perform_system_recovery_check delegates to recovery service."""
    health_report = {"overall_status": "healthy", "corrupted_indexes": []}
    coordinator_test_mode.recovery_service.perform_system_health_check = Mock(
        return_value=health_report
    )

    result = coordinator_test_mode.perform_system_recovery_check()

    assert result["overall_status"] == "healthy"
    coordinator_test_mode.recovery_service.perform_system_health_check.assert_called_once()


# ============================================================================
# Cache & Service Information
# ============================================================================


def test_get_enhanced_cache_info_success(coordinator_test_mode):
    """Test get_enhanced_cache_info aggregates service statistics."""
    # Mock all service stats
    coordinator_test_mode.query_engine.get_current_document_info = Mock(
        return_value={"current_document_id": 1, "has_loaded_index": True}
    )
    coordinator_test_mode.file_manager.get_storage_statistics = Mock(
        return_value={"total_indexes": 5, "total_size_mb": 100}
    )
    coordinator_test_mode.index_builder.get_build_statistics = Mock(
        return_value={"total_builds": 10}
    )
    coordinator_test_mode.query_engine.get_query_statistics = Mock(
        return_value={"total_queries": 50}
    )
    coordinator_test_mode.recovery_service.get_recovery_metrics = Mock(
        return_value={"total_recoveries": 2}
    )
    coordinator_test_mode.vector_repo.get_index_statistics = Mock(
        return_value={"total_indexes": 5}
    )

    # Execute
    result = coordinator_test_mode.get_enhanced_cache_info()

    # Verify structure
    assert "coordinator_info" in result
    assert result["coordinator_info"]["test_mode"] is True
    assert "service_stats" in result
    assert result["service_stats"]["file_manager"]["total_indexes"] == 5
    assert result["database_stats"]["total_indexes"] == 5


def test_get_service_health_status_healthy(coordinator_test_mode):
    """Test get_service_health_status when all services healthy."""
    # Mock healthy file manager
    coordinator_test_mode.file_manager.is_accessible = Mock(return_value=True)

    # Mock successful database stats
    coordinator_test_mode.vector_repo.get_index_statistics = Mock(
        return_value={"total_indexes": 5}
    )

    # Mock healthy recovery checks
    coordinator_test_mode.recovery_service.health_checker.run_all_checks = Mock(
        return_value={
            "vector_storage": True,
            "database_connection": True,
            "system_resources": True,
        }
    )

    # Execute
    result = coordinator_test_mode.get_service_health_status()

    # Verify
    assert result["overall_healthy"] is True
    assert result["services"]["file_manager"]["healthy"] is True
    assert result["services"]["database"]["healthy"] is True
    assert result["services"]["recovery_service"]["healthy"] is True
    assert len(result["recommendations"]) == 0


def test_get_service_health_status_degraded(coordinator_test_mode):
    """Test get_service_health_status when some checks fail."""
    coordinator_test_mode.file_manager.is_accessible = Mock(return_value=True)
    coordinator_test_mode.vector_repo.get_index_statistics = Mock(
        return_value={"total_indexes": 5}
    )

    # Mock failed health checks
    coordinator_test_mode.recovery_service.health_checker.run_all_checks = Mock(
        return_value={
            "vector_storage": False,  # Failed check
            "database_connection": True,
            "system_resources": True,
        }
    )

    result = coordinator_test_mode.get_service_health_status()

    assert result["overall_healthy"] is False
    assert result["services"]["recovery_service"]["healthy"] is False
    assert len(result["recommendations"]) > 0


# ============================================================================
# Legacy Compatibility Methods
# ============================================================================


def test_legacy_query_method(coordinator_test_mode):
    """Test legacy query() method delegates to query_current_document."""
    coordinator_test_mode.query_engine.query_current_document = Mock(
        return_value="Legacy response"
    )

    result = coordinator_test_mode.query("test query")

    assert result == "Legacy response"
    coordinator_test_mode.query_engine.query_current_document.assert_called_once_with(
        "test query"
    )


def test_legacy_get_cache_info_method(coordinator_test_mode):
    """Test legacy get_cache_info() method returns compatible format."""
    coordinator_test_mode.query_engine.get_current_document_info = Mock(
        return_value={
            "has_loaded_index": True,
            "current_pdf_path": "/test/doc.pdf",
            "current_document_id": 1,
        }
    )
    coordinator_test_mode.file_manager.get_storage_statistics = Mock(
        return_value={"total_indexes": 5}
    )

    result = coordinator_test_mode.get_cache_info()

    # Verify legacy format
    assert result["has_current_index"] is True
    assert result["current_pdf_path"] == "/test/doc.pdf"
    assert result["current_document_id"] == 1
    assert result["test_mode"] is True
    assert result["vector_indexes_count"] == 5


# ============================================================================
# Convenience Methods
# ============================================================================


def test_preload_document_index_success(coordinator_test_mode):
    """Test preload_document_index delegates to query engine."""
    coordinator_test_mode.query_engine.preload_index = Mock(return_value=True)

    result = coordinator_test_mode.preload_document_index(1)

    assert result is True
    coordinator_test_mode.query_engine.preload_index.assert_called_once_with(1)


def test_clear_current_index_delegates(coordinator_test_mode):
    """Test clear_current_index delegates to query engine."""
    coordinator_test_mode.query_engine.clear_current_index = Mock()

    coordinator_test_mode.clear_current_index()

    coordinator_test_mode.query_engine.clear_current_index.assert_called_once()


def test_get_current_document_info_delegates(coordinator_test_mode):
    """Test get_current_document_info delegates to query engine."""
    info = {"current_document_id": 1, "has_loaded_index": True}
    coordinator_test_mode.query_engine.get_current_document_info = Mock(
        return_value=info
    )

    result = coordinator_test_mode.get_current_document_info()

    assert result == info
    coordinator_test_mode.query_engine.get_current_document_info.assert_called_once()
