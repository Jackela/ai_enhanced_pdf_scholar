"""
Comprehensive tests for RAGQueryEngine.

Tests cover:
- Initialization in test mode and normal mode
- Index loading (success and error paths)
- Query execution
- Status and info methods
- Statistics retrieval

Target Coverage: src/services/rag/query_engine.py (0% → 70%)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.database.models import DocumentModel, VectorIndexModel
from src.services.rag.query_engine import (
    IndexLoadError,
    QueryExecutionError,
    RAGQueryEngine,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_document_repo():
    """Mock document repository."""
    return Mock()


@pytest.fixture
def mock_vector_repo():
    """Mock vector index repository."""
    return Mock()


@pytest.fixture
def mock_file_manager():
    """Mock RAG file manager."""
    return Mock()


@pytest.fixture
def sample_document():
    """Sample document model for testing."""
    return DocumentModel(
        id=1,
        title="Test Document",
        file_path="/test/document.pdf",
        file_hash="abc123",
        file_size=1024,
        file_type=".pdf",
    )


@pytest.fixture
def sample_vector_index():
    """Sample vector index model for testing."""
    return VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/test/index/1",
        index_hash="idx_hash123",
        chunk_count=10,
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def query_engine_test_mode(mock_document_repo, mock_vector_repo, mock_file_manager):
    """RAGQueryEngine instance in test mode."""
    return RAGQueryEngine(
        document_repo=mock_document_repo,
        vector_repo=mock_vector_repo,
        file_manager=mock_file_manager,
        test_mode=True,
    )


# ============================================================================
# Initialization & State Tests
# ============================================================================


def test_query_engine_initialization_test_mode(query_engine_test_mode):
    """Test query engine initializes correctly in test mode."""
    assert query_engine_test_mode.test_mode is True
    assert query_engine_test_mode.current_index is None
    assert query_engine_test_mode.current_document_id is None
    assert query_engine_test_mode.current_vector_index is None
    assert query_engine_test_mode.current_pdf_path is None


def test_query_engine_initialization_sets_dependencies(
    query_engine_test_mode, mock_document_repo, mock_vector_repo, mock_file_manager
):
    """Test that dependencies are correctly set."""
    assert query_engine_test_mode.document_repo is mock_document_repo
    assert query_engine_test_mode.vector_repo is mock_vector_repo
    assert query_engine_test_mode.file_manager is mock_file_manager


def test_clear_current_index_resets_state(query_engine_test_mode):
    """Test clear_current_index resets all state variables."""
    # Set some state
    query_engine_test_mode.current_index = "mock_index"
    query_engine_test_mode.current_document_id = 1
    query_engine_test_mode.current_vector_index = "mock_vector_index"
    query_engine_test_mode.current_pdf_path = "/test/doc.pdf"

    # Clear
    query_engine_test_mode.clear_current_index()

    # Verify reset
    assert query_engine_test_mode.current_index is None
    assert query_engine_test_mode.current_document_id is None
    assert query_engine_test_mode.current_vector_index is None
    assert query_engine_test_mode.current_pdf_path is None


# ============================================================================
# Index Loading - Success Paths
# ============================================================================


def test_load_index_for_document_success(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test successful index loading."""
    # Setup mocks
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True
    mock_document_repo.update_access_time.return_value = None

    # Execute
    result = query_engine_test_mode.load_index_for_document(1)

    # Verify
    assert result is True
    assert query_engine_test_mode.current_document_id == 1
    assert query_engine_test_mode.current_vector_index == sample_vector_index
    assert query_engine_test_mode.current_pdf_path == sample_document.file_path
    assert query_engine_test_mode.current_index is not None  # Mock index created

    # Verify calls
    mock_document_repo.find_by_id.assert_called_once_with(1)
    mock_vector_repo.find_by_document_id.assert_called_once_with(1)
    mock_file_manager.verify_index_files.assert_called_once_with("/test/index/1")
    mock_document_repo.update_access_time.assert_called_once_with(1)


def test_load_index_creates_mock_in_test_mode(query_engine_test_mode):
    """Test that load_index creates a mock index in test mode."""
    mock_index = query_engine_test_mode._create_mock_index(document_id=1)

    # Verify mock index has required interface
    assert hasattr(mock_index, "as_query_engine")
    query_engine = mock_index.as_query_engine()

    # Verify mock query engine can execute queries
    assert hasattr(query_engine, "query")
    response = query_engine.query("test query")
    assert "Mock response" in str(response)
    assert "document 1" in str(response)


def test_preload_index_success(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test successful index preloading."""
    # Setup mocks
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True

    # Execute
    result = query_engine_test_mode.preload_index(1)

    # Verify
    assert result is True
    assert query_engine_test_mode.current_document_id == 1


def test_preload_index_failure_returns_false(
    query_engine_test_mode, mock_document_repo
):
    """Test preload_index returns False on failure without raising."""
    # Setup mock to fail
    mock_document_repo.find_by_id.return_value = None

    # Execute (should not raise)
    result = query_engine_test_mode.preload_index(999)

    # Verify
    assert result is False


# ============================================================================
# Index Loading - Error Paths
# ============================================================================


def test_load_index_document_not_found(query_engine_test_mode, mock_document_repo):
    """Test load_index raises IndexLoadError when document not found."""
    mock_document_repo.find_by_id.return_value = None

    with pytest.raises(IndexLoadError, match="Document not found: 999"):
        query_engine_test_mode.load_index_for_document(999)


def test_load_index_no_vector_index_found(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    sample_document,
):
    """Test load_index raises IndexLoadError when no vector index exists."""
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = None

    with pytest.raises(IndexLoadError, match="No vector index found for document 1"):
        query_engine_test_mode.load_index_for_document(1)


def test_load_index_files_missing_or_corrupted(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test load_index raises IndexLoadError when index files are missing."""
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = False

    with pytest.raises(IndexLoadError, match="files missing or corrupted"):
        query_engine_test_mode.load_index_for_document(1)


def test_load_index_unexpected_error_wrapped(
    query_engine_test_mode, mock_document_repo
):
    """Test load_index wraps unexpected errors in IndexLoadError."""
    mock_document_repo.find_by_id.side_effect = RuntimeError("Database connection lost")

    with pytest.raises(IndexLoadError, match="Unexpected error loading index"):
        query_engine_test_mode.load_index_for_document(1)


# ============================================================================
# Query Execution Tests
# ============================================================================


def test_query_document_success_in_test_mode(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test query_document returns test mode response."""
    # Setup mocks for successful load
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True

    # Execute query
    response = query_engine_test_mode.query_document("What is this about?", 1)

    # Verify test mode response
    assert response == "Test mode response for query: What is this about?"


def test_query_document_auto_loads_index(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test query_document auto-loads index if not current."""
    # Setup mocks
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True

    # Verify no index loaded initially
    assert query_engine_test_mode.current_document_id is None

    # Execute query (should auto-load)
    response = query_engine_test_mode.query_document("test query", 1)

    # Verify index was loaded
    assert query_engine_test_mode.current_document_id == 1
    assert response is not None


def test_query_current_document_success(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test query_current_document delegates to query_document."""
    # First load an index
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True
    query_engine_test_mode.load_index_for_document(1)

    # Execute query on current document
    response = query_engine_test_mode.query_current_document("test query")

    # Verify
    assert "Test mode response" in response


def test_query_current_document_no_document_loaded(query_engine_test_mode):
    """Test query_current_document raises error when no document loaded."""
    # Don't load any document
    with pytest.raises(QueryExecutionError, match="No document currently loaded"):
        query_engine_test_mode.query_current_document("test query")


def test_execute_query_no_index_loaded(query_engine_test_mode):
    """Test _execute_query raises error when no index loaded."""
    # Clear any index
    query_engine_test_mode.clear_current_index()

    with pytest.raises(QueryExecutionError, match="No vector index loaded"):
        query_engine_test_mode._execute_query("test query")


# ============================================================================
# Status & Info Methods
# ============================================================================


def test_get_current_document_info_with_loaded_index(
    query_engine_test_mode,
    mock_document_repo,
    mock_vector_repo,
    mock_file_manager,
    sample_document,
    sample_vector_index,
):
    """Test get_current_document_info with loaded index."""
    # Load index
    mock_document_repo.find_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True
    query_engine_test_mode.load_index_for_document(1)

    # Get info
    info = query_engine_test_mode.get_current_document_info()

    # Verify structure
    assert info["current_document_id"] == 1
    assert info["has_loaded_index"] is True
    assert info["current_pdf_path"] == "/test/document.pdf"
    assert info["test_mode"] is True
    assert "vector_index_info" in info
    assert info["vector_index_info"]["index_id"] == 1
    assert info["vector_index_info"]["chunk_count"] == 10


def test_get_current_document_info_no_index(query_engine_test_mode):
    """Test get_current_document_info when no index loaded."""
    info = query_engine_test_mode.get_current_document_info()

    assert info["current_document_id"] is None
    assert info["has_loaded_index"] is False
    assert info["current_pdf_path"] is None
    assert info["vector_index_info"] is None


def test_get_document_query_status_valid_index(
    query_engine_test_mode, mock_vector_repo, mock_file_manager, sample_vector_index
):
    """Test get_document_query_status with valid index."""
    # Setup mocks
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = True

    # Get status
    status = query_engine_test_mode.get_document_query_status(1)

    # Verify
    assert status["document_id"] == 1
    assert status["can_query"] is True
    assert status["has_index"] is True
    assert status["index_valid"] is True
    assert status["index_path"] == "/test/index/1"
    assert status["chunk_count"] == 10
    assert status["is_currently_loaded"] is False
    assert status["error"] is None


def test_get_document_query_status_invalid_index(
    query_engine_test_mode, mock_vector_repo, mock_file_manager, sample_vector_index
):
    """Test get_document_query_status with invalid index files."""
    # Setup mocks - index exists but files invalid
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index
    mock_file_manager.verify_index_files.return_value = False

    # Get status
    status = query_engine_test_mode.get_document_query_status(1)

    # Verify
    assert status["can_query"] is False
    assert status["has_index"] is True
    assert status["index_valid"] is False


def test_get_document_query_status_no_index(query_engine_test_mode, mock_vector_repo):
    """Test get_document_query_status when no index exists."""
    mock_vector_repo.find_by_document_id.return_value = None

    status = query_engine_test_mode.get_document_query_status(999)

    assert status["has_index"] is False
    assert status["can_query"] is False


# ============================================================================
# Statistics & Misc
# ============================================================================


def test_get_query_statistics(query_engine_test_mode, mock_file_manager):
    """Test get_query_statistics returns correct structure."""
    # Mock storage stats
    mock_file_manager.get_storage_statistics.return_value = {
        "total_indexes": 5,
        "total_size_mb": 100,
    }

    # Get statistics
    stats = query_engine_test_mode.get_query_statistics()

    # Verify structure
    assert stats["service_name"] == "RAGQueryEngine"
    assert stats["test_mode"] is True
    assert "current_state" in stats
    assert "storage_stats" in stats
    assert stats["storage_stats"]["total_indexes"] == 5
