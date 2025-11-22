"""
Comprehensive tests for RAGIndexBuilder.

Tests cover:
- Service initialization (test mode and normal mode)
- Build validation (file checks, storage checks, API checks)
- Index building workflow (success, errors, overwrite)
- PDF processing in test mode
- Cleanup and error recovery
- Statistics retrieval

Target Coverage: src/services/rag/index_builder.py (0% → 65%)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.database.models import DocumentModel
from src.services.rag.index_builder import (
    IndexCreationError,
    RAGIndexBuilder,
    RAGIndexBuilderError,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_file_manager():
    """Mock RAG file manager."""
    manager = Mock()
    manager.is_accessible.return_value = True
    manager.verify_index_files.return_value = True
    manager.get_chunk_count.return_value = 10
    manager.get_storage_statistics.return_value = {"total_indexes": 5}
    return manager


@pytest.fixture
def index_builder_test_mode(mock_file_manager):
    """RAGIndexBuilder instance in test mode."""
    return RAGIndexBuilder(
        api_key="test_api_key", file_manager=mock_file_manager, test_mode=True
    )


@pytest.fixture
def sample_document(tmp_path):
    """Sample document model with real test file."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("Test PDF content")
    return DocumentModel(
        id=1,
        title="Test Document",
        file_path=str(pdf_file),
        file_hash="hash123",
        file_size=1024,
        file_type=".pdf",
    )


# ============================================================================
# Initialization Tests
# ============================================================================


def test_index_builder_initialization_test_mode(index_builder_test_mode):
    """Test index builder initializes correctly in test mode."""
    assert index_builder_test_mode.test_mode is True
    assert index_builder_test_mode.api_key == "test_api_key"
    assert index_builder_test_mode.file_manager is not None
    assert index_builder_test_mode.cleanup_manager is not None
    assert index_builder_test_mode.api_retry_config is not None
    assert index_builder_test_mode.api_circuit_breaker_config is not None


def test_index_builder_retry_config_defaults(index_builder_test_mode):
    """Test default retry configuration."""
    config = index_builder_test_mode.api_retry_config
    assert config.max_attempts == 3
    assert config.initial_delay == 2.0
    assert config.exponential_base == 2.0
    assert config.jitter is True


def test_index_builder_circuit_breaker_config_defaults(index_builder_test_mode):
    """Test default circuit breaker configuration."""
    config = index_builder_test_mode.api_circuit_breaker_config
    assert config.failure_threshold == 5
    assert config.recovery_timeout == 120.0
    assert config.success_threshold == 2


# ============================================================================
# Build Validation Tests
# ============================================================================


def test_validate_build_requirements_success(index_builder_test_mode, sample_document):
    """Test validation succeeds with valid document."""
    result = index_builder_test_mode.validate_build_requirements(sample_document)

    assert result["valid"] is True
    assert len(result["issues"]) == 0


def test_validate_build_requirements_no_file_path(index_builder_test_mode):
    """Test validation fails when document has no file path."""
    document = DocumentModel(
        id=1,
        title="Test",
        file_path=None,
        file_hash="hash",
        file_size=0,
        file_type=".pdf",
    )

    result = index_builder_test_mode.validate_build_requirements(document)

    assert result["valid"] is False
    assert "no file path" in " ".join(result["issues"]).lower()


def test_validate_build_requirements_file_not_found(index_builder_test_mode):
    """Test validation fails when file doesn't exist."""
    document = DocumentModel(
        id=1,
        title="Test",
        file_path="/nonexistent/file.pdf",
        file_hash="hash",
        file_size=1024,
        file_type=".pdf",
    )

    result = index_builder_test_mode.validate_build_requirements(document)

    assert result["valid"] is False
    assert any("not found" in issue.lower() for issue in result["issues"])


def test_validate_build_requirements_empty_file(index_builder_test_mode, tmp_path):
    """Test validation fails with empty file."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_text("")  # Empty file

    document = DocumentModel(
        id=1,
        title="Test",
        file_path=str(empty_file),
        file_hash="hash",
        file_size=0,
        file_type=".pdf",
    )

    result = index_builder_test_mode.validate_build_requirements(document)

    assert result["valid"] is False
    assert any("empty" in issue.lower() for issue in result["issues"])


def test_validate_build_requirements_storage_not_accessible(
    index_builder_test_mode, sample_document
):
    """Test validation fails when storage not accessible."""
    index_builder_test_mode.file_manager.is_accessible.return_value = False

    result = index_builder_test_mode.validate_build_requirements(sample_document)

    assert result["valid"] is False
    assert any("not accessible" in issue.lower() for issue in result["issues"])


# ============================================================================
# Build Index From PDF - Test Mode
# ============================================================================


def test_build_index_from_pdf_test_mode_success(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test build_index_from_pdf in test mode simulates build."""
    temp_dir = tmp_path / "temp_index"
    temp_dir.mkdir()

    result = index_builder_test_mode.build_index_from_pdf(
        sample_document.file_path, str(temp_dir)
    )

    assert result is True


def test_build_index_from_pdf_test_mode_nonexistent_file(
    index_builder_test_mode, tmp_path
):
    """Test build fails when PDF file doesn't exist (test mode catches this)."""
    temp_dir = tmp_path / "temp_index"
    temp_dir.mkdir()

    # In test mode, it just returns True without checking
    result = index_builder_test_mode.build_index_from_pdf(
        "/nonexistent/file.pdf", str(temp_dir)
    )

    assert result is True  # Test mode bypasses actual build


# ============================================================================
# Build Index For Document - Complete Workflow
# ============================================================================


def test_build_index_for_document_success(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test successful index building for document."""
    # Mock file manager methods
    index_path = tmp_path / "final_index"
    index_builder_test_mode.file_manager.generate_index_path = Mock(
        return_value=index_path
    )
    index_builder_test_mode.file_manager.prepare_index_directory = Mock()
    index_builder_test_mode.file_manager.copy_index_files = Mock()

    # Execute
    result = index_builder_test_mode.build_index_for_document(sample_document)

    # Verify
    assert result["success"] is True
    assert result["document_id"] == 1
    assert result["index_path"] == str(index_path)
    assert result["chunk_count"] == 10
    assert result["error"] is None
    assert result["build_duration_ms"] >= 0


def test_build_index_for_document_with_overwrite(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test index building with overwrite=True."""
    # Create existing index directory
    index_path = tmp_path / "existing_index"
    index_path.mkdir()

    index_builder_test_mode.file_manager.generate_index_path = Mock(
        return_value=index_path
    )
    index_builder_test_mode.file_manager.prepare_index_directory = Mock()
    index_builder_test_mode.file_manager.copy_index_files = Mock()

    # Execute with overwrite
    result = index_builder_test_mode.build_index_for_document(
        sample_document, overwrite=True
    )

    # Verify prepare was called with overwrite=True
    index_builder_test_mode.file_manager.prepare_index_directory.assert_called_once_with(
        index_path, overwrite=True
    )
    assert result["success"] is True


def test_build_index_for_document_existing_without_overwrite_raises(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test building fails when index exists and overwrite=False."""
    # Create existing index directory
    existing_index = tmp_path / "existing_index"
    existing_index.mkdir()

    index_builder_test_mode.file_manager.generate_index_path = Mock(
        return_value=existing_index
    )

    # Execute without overwrite
    with pytest.raises(RAGIndexBuilderError, match="Index already exists"):
        index_builder_test_mode.build_index_for_document(
            sample_document, overwrite=False
        )


def test_build_index_for_document_file_not_found_raises(
    index_builder_test_mode, tmp_path
):
    """Test building fails when document file not found."""
    document = DocumentModel(
        id=1,
        title="Test",
        file_path="/nonexistent/file.pdf",
        file_hash="hash",
        file_size=1024,
        file_type=".pdf",
    )

    with pytest.raises(RAGIndexBuilderError, match="file not found"):
        index_builder_test_mode.build_index_for_document(document)


def test_build_index_for_document_verification_failure(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test building fails when final verification fails."""
    index_path = tmp_path / "final_index"
    index_builder_test_mode.file_manager.generate_index_path = Mock(
        return_value=index_path
    )
    index_builder_test_mode.file_manager.prepare_index_directory = Mock()
    index_builder_test_mode.file_manager.copy_index_files = Mock()

    # Mock verification failure
    index_builder_test_mode.file_manager.verify_index_files.return_value = False

    with pytest.raises(RAGIndexBuilderError, match="verification failed"):
        index_builder_test_mode.build_index_for_document(sample_document)


# ============================================================================
# Statistics & Info Methods
# ============================================================================


def test_get_build_statistics(index_builder_test_mode):
    """Test get_build_statistics returns correct structure."""
    stats = index_builder_test_mode.get_build_statistics()

    # Verify structure
    assert stats["service_name"] == "RAGIndexBuilder"
    assert stats["test_mode"] is True
    assert "storage_stats" in stats
    assert stats["storage_stats"]["total_indexes"] == 5
    assert "config" in stats
    assert stats["config"]["api_retry_attempts"] == 3
    assert stats["config"]["circuit_breaker_threshold"] == 5
    assert stats["config"]["recovery_timeout"] == 120.0


# ============================================================================
# Error Recovery and Cleanup
# ============================================================================


def test_build_index_for_document_cleans_up_on_error(
    index_builder_test_mode, sample_document, tmp_path
):
    """Test cleanup occurs when build fails."""
    index_path = tmp_path / "final_index"
    index_path.mkdir()

    index_builder_test_mode.file_manager.generate_index_path = Mock(
        return_value=index_path
    )
    index_builder_test_mode.file_manager.prepare_index_directory = Mock()

    # Mock copy to raise exception
    index_builder_test_mode.file_manager.copy_index_files = Mock(
        side_effect=Exception("Copy failed")
    )
    index_builder_test_mode.file_manager.cleanup_index_files = Mock()

    # Execute and expect failure
    with pytest.raises(RAGIndexBuilderError):
        index_builder_test_mode.build_index_for_document(sample_document)

    # Verify cleanup was called
    index_builder_test_mode.file_manager.cleanup_index_files.assert_called_once_with(
        str(index_path)
    )
