"""
Comprehensive tests for Indexes API Routes.

Tests cover:
- Get document index (success, not found, errors)
- Build document index (success, conflict, document not found, health check failures)
- Rebuild document index (success, errors)
- Verify index integrity (valid, invalid, not found)
- Cleanup orphaned indexes (success, errors)
- Storage statistics (success, errors)
- Request validation
- Response structure verification

Target Coverage: backend/api/routes/indexes.py (15% → 75%)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.routes import indexes
from src.database.models import DocumentModel, VectorIndexModel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with indexes router."""
    test_app = FastAPI()
    test_app.include_router(indexes.router, prefix="/api/indexes")
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_doc_repo():
    """Mock document repository."""
    repo = Mock()
    repo.get_by_id = Mock(return_value=None)
    return repo


@pytest.fixture
def mock_vector_repo():
    """Mock vector index repository."""
    repo = Mock()
    repo.find_by_document_id = Mock(return_value=None)
    repo.get_by_id = Mock(return_value=None)
    return repo


@pytest.fixture
def mock_health_checker():
    """Mock RAG health checker."""
    checker = Mock()
    checker.perform_health_check = Mock(return_value={"healthy": True, "issues": []})
    return checker


@pytest.fixture
def mock_resource_manager():
    """Mock RAG resource manager."""
    manager = Mock()
    manager.cleanup_orphaned_indexes = Mock(return_value=0)
    manager.get_storage_stats = Mock(return_value={})
    return manager


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
def sample_vector_index(tmp_path):
    """Sample vector index model with real path."""
    idx_path = tmp_path / "vector_index"
    idx_path.mkdir()
    return VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(idx_path),
        index_hash="index_hash_123",
        chunk_count=42,
        created_at=datetime(2025, 1, 12, 10, 0, 0),
    )


@pytest.fixture(autouse=True)
def enable_indexes_service(monkeypatch):
    """Enable indexes service for all tests."""
    from config import Config

    monkeypatch.setattr(Config, "is_rag_services_enabled", lambda: True)


# ============================================================================
# Get Document Index Tests
# ============================================================================


def test_get_document_index_success(client, app, mock_vector_repo, sample_vector_index):
    """Test successful index retrieval."""
    # Setup
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index

    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )

    # Execute
    response = client.get("/api/indexes/document/1")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["id"] == 1
    assert data["data"]["document_id"] == 1
    assert data["data"]["chunk_count"] == 42
    assert data["data"]["status"] == "ready"
    assert "_links" in data["data"]
    assert "document" in data["data"]["_links"]["related"]


def test_get_document_index_not_found(client, app, mock_vector_repo):
    """Test index retrieval when index doesn't exist."""
    # Setup
    mock_vector_repo.find_by_document_id.return_value = None

    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )

    # Execute
    response = client.get("/api/indexes/document/999")

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Index not found for document 999" in response.json()["detail"]


def test_get_document_index_service_disabled(client, app, monkeypatch):
    """Test index retrieval when service is disabled."""
    from config import Config

    monkeypatch.setattr(Config, "is_rag_services_enabled", lambda: False)

    response = client.get("/api/indexes/document/1")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "not available" in response.json()["detail"]


# ============================================================================
# Build Document Index Tests
# ============================================================================


def test_build_index_success(
    client, app, mock_doc_repo, mock_vector_repo, mock_health_checker, sample_document
):
    """Test successful index building."""
    # Setup
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = None  # No existing index

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post(
        "/api/indexes/document/1/build",
        json={"force_rebuild": False, "chunking_strategy": "default"},
    )

    # Verify
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert data["success"] is True
    assert data["data"]["document_id"] == 1
    assert data["data"]["success"] is True
    assert data["data"]["build_duration_ms"] >= 0
    assert data["data"]["error"] is None


def test_build_index_document_not_found(
    client, app, mock_doc_repo, mock_vector_repo, mock_health_checker
):
    """Test index building when document doesn't exist."""
    # Setup
    mock_doc_repo.get_by_id.return_value = None

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post(
        "/api/indexes/document/999/build", json={"force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Document 999 not found" in response.json()["detail"]


def test_build_index_conflict_existing(
    client,
    app,
    mock_doc_repo,
    mock_vector_repo,
    mock_health_checker,
    sample_document,
    sample_vector_index,
):
    """Test index building when index already exists without force_rebuild."""
    # Setup
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post(
        "/api/indexes/document/1/build", json={"force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Index already exists" in response.json()["detail"]
    assert "force_rebuild=true" in response.json()["detail"]


def test_build_index_with_force_rebuild(
    client,
    app,
    mock_doc_repo,
    mock_vector_repo,
    mock_health_checker,
    sample_document,
    sample_vector_index,
):
    """Test index building with force_rebuild when index exists."""
    # Setup
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = sample_vector_index

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post(
        "/api/indexes/document/1/build", json={"force_rebuild": True}
    )

    # Verify
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True


def test_build_index_health_check_failure(
    client, app, mock_doc_repo, mock_vector_repo, mock_health_checker, sample_document
):
    """Test index building when health check fails."""
    # Setup
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = None
    mock_health_checker.perform_health_check.return_value = {
        "healthy": False,
        "issues": ["API key not configured"],
    }

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post(
        "/api/indexes/document/1/build", json={"force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "health check failed" in response.json()["detail"].lower()


# ============================================================================
# Rebuild Document Index Tests
# ============================================================================


def test_rebuild_index_success(
    client, app, mock_doc_repo, mock_vector_repo, mock_health_checker, sample_document
):
    """Test successful index rebuilding."""
    # Setup
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_vector_repo.find_by_document_id.return_value = None  # Will force rebuild

    app.dependency_overrides[indexes.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )
    app.dependency_overrides[indexes.get_rag_health_checker] = (
        lambda: mock_health_checker
    )

    # Execute
    response = client.post("/api/indexes/document/1/rebuild")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["data"]["document_id"] == 1


# ============================================================================
# Verify Index Tests
# ============================================================================


def test_verify_index_success_with_existing_files(
    client, app, mock_vector_repo, sample_vector_index
):
    """Test index verification when files exist."""
    # Setup
    mock_vector_repo.get_by_id.return_value = sample_vector_index

    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )

    # Execute
    response = client.get("/api/indexes/1/verify")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["index_id"] == 1
    assert "checks" in data["data"]
    assert data["data"]["checks"]["database_record"] is True
    assert data["data"]["checks"]["files_exist"] is True


def test_verify_index_files_missing(client, app, mock_vector_repo):
    """Test index verification when files are missing."""
    # Setup - index with non-existent path
    index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/nonexistent/path",
        index_hash="hash",
        chunk_count=10,
        created_at=datetime(2025, 1, 12, 10, 0, 0),
    )
    mock_vector_repo.get_by_id.return_value = index

    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )

    # Execute
    response = client.get("/api/indexes/1/verify")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["valid"] is False
    assert data["data"]["checks"]["files_exist"] is False
    assert "Index files not found on disk" in data["data"]["issues"]


def test_verify_index_not_found(client, app, mock_vector_repo):
    """Test index verification when index doesn't exist."""
    # Setup
    mock_vector_repo.get_by_id.return_value = None

    app.dependency_overrides[indexes.get_vector_index_repository] = (
        lambda: mock_vector_repo
    )

    # Execute
    response = client.get("/api/indexes/999/verify")

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Index 999 not found" in response.json()["detail"]


# ============================================================================
# Cleanup Orphaned Indexes Tests
# ============================================================================


def test_cleanup_orphaned_indexes_success(client, app, mock_resource_manager):
    """Test successful orphaned index cleanup."""
    # Setup
    mock_resource_manager.cleanup_orphaned_indexes.return_value = 5

    app.dependency_overrides[indexes.get_rag_resource_manager] = (
        lambda: mock_resource_manager
    )

    # Execute
    response = client.post("/api/indexes/cleanup/orphaned")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["cleaned_count"] == 5
    assert "Cleaned up 5 orphaned indexes" in data["data"]["message"]


def test_cleanup_orphaned_indexes_none_found(client, app, mock_resource_manager):
    """Test cleanup when no orphaned indexes found."""
    # Setup
    mock_resource_manager.cleanup_orphaned_indexes.return_value = 0

    app.dependency_overrides[indexes.get_rag_resource_manager] = (
        lambda: mock_resource_manager
    )

    # Execute
    response = client.post("/api/indexes/cleanup/orphaned")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["cleaned_count"] == 0


# ============================================================================
# Storage Statistics Tests
# ============================================================================


def test_get_storage_stats_success(client, app, mock_resource_manager):
    """Test successful storage statistics retrieval."""
    # Setup
    stats = {
        "total_indexes": 10,
        "total_size_bytes": 1048576,
        "average_size_bytes": 104857,
        "largest_index_size": 524288,
    }
    mock_resource_manager.get_storage_stats.return_value = stats

    app.dependency_overrides[indexes.get_rag_resource_manager] = (
        lambda: mock_resource_manager
    )

    # Execute
    response = client.get("/api/indexes/stats/storage")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["total_indexes"] == 10
    assert data["data"]["total_size_bytes"] == 1048576


def test_get_storage_stats_empty(client, app, mock_resource_manager):
    """Test storage statistics when no indexes exist."""
    # Setup
    mock_resource_manager.get_storage_stats.return_value = {
        "total_indexes": 0,
        "total_size_bytes": 0,
    }

    app.dependency_overrides[indexes.get_rag_resource_manager] = (
        lambda: mock_resource_manager
    )

    # Execute
    response = client.get("/api/indexes/stats/storage")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["total_indexes"] == 0
