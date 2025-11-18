"""
Comprehensive tests for Library Management API Routes.

Tests cover:
- Get library statistics (success, error response, exception handling)
- Find duplicate documents (success, empty, error)
- Cleanup library (success, partial cleanup, failure)
- Check library health (healthy, degraded)
- Optimize library (success, failure)
- Search documents (success, no results)
- Get recent documents (success, empty)

Target Coverage: backend/api/routes/library.py (0% → 75%)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.routes import library
from src.database.models import DocumentModel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with library router."""
    test_app = FastAPI()
    test_app.include_router(library.router, prefix="/api/library")
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_controller():
    """Mock library controller."""
    controller = Mock()
    controller.get_library_statistics = Mock(return_value={})
    controller.find_duplicate_documents = Mock(return_value=[])
    controller.cleanup_library = Mock(return_value={})
    controller.get_documents = Mock(return_value=[])
    controller.library_service = Mock()
    controller.library_service.get_recent_documents = Mock(return_value=[])
    return controller


@pytest.fixture
def sample_document():
    """Sample document model."""
    doc = DocumentModel(
        id=1,
        title="Test Document",
        file_path="/test/doc.pdf",
        file_hash="hash123",
        file_size=1024,
        file_type=".pdf",
        created_at=datetime(2025, 1, 18, 10, 0, 0),
    )
    # Mock methods
    doc.to_api_dict = Mock(
        return_value={
            "id": 1,
            "title": "Test Document",
            "file_path": "/test/doc.pdf",
            "file_hash": "hash123",
            "file_size": 1024,
            "file_type": ".pdf",
            "created_at": "2025-01-18T10:00:00",
            "updated_at": "2025-01-18T10:00:00",
        }
    )
    doc.is_file_available = Mock(return_value=True)
    return doc


# ============================================================================
# GET /stats Tests
# ============================================================================


def test_get_library_statistics_success(client, app, mock_controller):
    """Test successful library statistics retrieval."""
    # Setup
    mock_controller.get_library_statistics.return_value = {
        "total_count": 42,
        "total_size_bytes": 104857600,  # 100MB
        "average_size_bytes": 2496552.38,
        "file_extensions": {".pdf": 40, ".txt": 2},
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/stats")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["total_documents"] == 42
    assert data["total_size"] == 104857600
    assert data["average_size"] == 2496552.38
    assert data["file_types"] == {".pdf": 40, ".txt": 2}
    assert data["recent_documents"] == 0


def test_get_library_statistics_error_response(client, app, mock_controller):
    """Test library statistics with error in response."""
    # Setup
    mock_controller.get_library_statistics.return_value = {
        "error": "Database connection failed"
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/stats")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_get_library_statistics_exception(client, app, mock_controller):
    """Test library statistics with controller exception."""
    # Setup
    mock_controller.get_library_statistics.side_effect = Exception("Database error")

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/stats")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# GET /duplicates Tests
# ============================================================================


def test_find_duplicates_success(client, app, mock_controller, sample_document):
    """Test successful duplicate detection."""
    # Setup - Create another document with same hash
    doc2 = DocumentModel(
        id=2,
        title="Test Document Copy",
        file_path="/test/doc_copy.pdf",
        file_hash="hash123",
        file_size=1024,
        file_type=".pdf",
    )
    doc2.to_api_dict = Mock(
        return_value={
            "id": 2,
            "title": "Test Document Copy",
            "file_path": "/test/doc_copy.pdf",
            "file_hash": "hash123",
            "file_size": 1024,
            "file_type": ".pdf",
            "created_at": "2025-01-18T10:00:00",
            "updated_at": "2025-01-18T10:00:00",
        }
    )
    doc2.is_file_available = Mock(return_value=True)

    mock_controller.find_duplicate_documents.return_value = [
        ("content_hash: hash123", [sample_document, doc2])
    ]

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/duplicates")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["total_duplicates"] == 2
    assert len(data["duplicate_groups"]) == 1
    assert data["duplicate_groups"][0]["criteria"] == "content_hash: hash123"
    assert len(data["duplicate_groups"][0]["documents"]) == 2


def test_find_duplicates_empty(client, app, mock_controller):
    """Test duplicate detection when no duplicates found."""
    # Setup
    mock_controller.find_duplicate_documents.return_value = []

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/duplicates")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["total_duplicates"] == 0
    assert len(data["duplicate_groups"]) == 0


def test_find_duplicates_error(client, app, mock_controller):
    """Test duplicate detection with error."""
    # Setup
    mock_controller.find_duplicate_documents.side_effect = Exception("Query failed")

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/duplicates")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# POST /cleanup Tests
# ============================================================================


def test_cleanup_library_success(client, app, mock_controller):
    """Test successful library cleanup."""
    # Setup
    mock_controller.cleanup_library.return_value = {
        "orphaned_indexes_cleaned": 5,
        "invalid_indexes_cleaned": 2,
        "cache_optimized": 10,
        "storage_optimized": 3,
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post(
        "/api/library/cleanup",
        json={
            "remove_orphaned": True,
            "remove_corrupted": True,
            "optimize_cache": True,
        },
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["orphaned_removed"] == 5
    assert data["corrupted_removed"] == 2
    assert data["cache_optimized"] == 10
    assert data["storage_optimized"] == 3
    assert "successfully" in data["message"].lower()


def test_cleanup_library_partial(client, app, mock_controller):
    """Test library cleanup with partial results."""
    # Setup
    mock_controller.cleanup_library.return_value = {
        "orphaned_indexes_cleaned": 0,
        "invalid_indexes_cleaned": 0,
        "cache_optimized": 5,
        "storage_optimized": 0,
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post(
        "/api/library/cleanup", json={"remove_orphaned": False, "optimize_cache": True}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["orphaned_removed"] == 0
    assert data["cache_optimized"] == 5


def test_cleanup_library_error_response(client, app, mock_controller):
    """Test library cleanup with error in response."""
    # Setup
    mock_controller.cleanup_library.return_value = {"error": "Cleanup operation failed"}

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post("/api/library/cleanup", json={"remove_orphaned": True})

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_cleanup_library_exception(client, app, mock_controller):
    """Test library cleanup with controller exception."""
    # Setup
    mock_controller.cleanup_library.side_effect = Exception("Cleanup failed")

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post("/api/library/cleanup", json={"remove_orphaned": True})

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# GET /health Tests
# ============================================================================


def test_library_health_healthy(client, app, mock_controller):
    """Test library health check when healthy."""
    # Setup
    mock_controller.get_library_statistics.return_value = {
        "health": {"orphaned_indexes": 0, "invalid_indexes": 0}
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "healthy" in data["message"].lower()


def test_library_health_degraded(client, app, mock_controller):
    """Test library health check when degraded."""
    # Setup
    mock_controller.get_library_statistics.return_value = {
        "health": {"orphaned_indexes": 5, "invalid_indexes": 2}
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is False
    assert "5 orphaned indexes" in data["message"]
    assert "2 invalid indexes" in data["message"]


def test_library_health_exception(client, app, mock_controller):
    """Test library health check with exception."""
    # Setup
    mock_controller.get_library_statistics.side_effect = Exception(
        "Health check failed"
    )

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/health")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# POST /optimize Tests
# ============================================================================


def test_optimize_library_success(client, app, mock_controller):
    """Test successful library optimization."""
    # Setup
    mock_controller.cleanup_library.return_value = {
        "orphaned_indexes_cleaned": 3,
        "invalid_indexes_cleaned": 1,
        "cache_optimized": 8,
        "storage_optimized": 2,
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post("/api/library/optimize")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "optimized" in data["message"].lower()
    assert "3 orphaned indexes" in data["message"]
    assert "1 invalid indexes" in data["message"]


def test_optimize_library_already_optimized(client, app, mock_controller):
    """Test library optimization when already optimized."""
    # Setup
    mock_controller.cleanup_library.return_value = {
        "orphaned_indexes_cleaned": 0,
        "invalid_indexes_cleaned": 0,
        "cache_optimized": 0,
        "storage_optimized": 0,
    }

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post("/api/library/optimize")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "already optimized" in data["message"].lower()


def test_optimize_library_error(client, app, mock_controller):
    """Test library optimization with error."""
    # Setup
    mock_controller.cleanup_library.return_value = {"error": "Optimization failed"}

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.post("/api/library/optimize")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# GET /search Tests
# ============================================================================


def test_search_documents_success(client, app, mock_controller, sample_document):
    """Test successful document search."""
    # Setup
    mock_controller.get_documents.return_value = [sample_document]

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/search?q=test&limit=10")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == 1
    assert data["documents"][0]["title"] == "Test Document"
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["per_page"] == 10


def test_search_documents_no_results(client, app, mock_controller):
    """Test document search with no results."""
    # Setup
    mock_controller.get_documents.return_value = []

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/search?q=nonexistent")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert len(data["documents"]) == 0
    assert data["total"] == 0


def test_search_documents_error(client, app, mock_controller):
    """Test document search with error."""
    # Setup
    mock_controller.get_documents.side_effect = Exception("Search failed")

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/search?q=test")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# GET /recent Tests
# ============================================================================


def test_get_recent_documents_success(client, app, mock_controller, sample_document):
    """Test successful recent documents retrieval."""
    # Setup
    mock_controller.library_service.get_recent_documents.return_value = [
        sample_document
    ]

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/recent?limit=5")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == 1
    assert data["total"] == 1
    assert data["per_page"] == 5


def test_get_recent_documents_empty(client, app, mock_controller):
    """Test recent documents when empty."""
    # Setup
    mock_controller.library_service.get_recent_documents.return_value = []

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/recent")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert len(data["documents"]) == 0
    assert data["total"] == 0


def test_get_recent_documents_error(client, app, mock_controller):
    """Test recent documents with error."""
    # Setup
    mock_controller.library_service.get_recent_documents.side_effect = Exception(
        "Failed to retrieve"
    )

    app.dependency_overrides[library.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/library/recent")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
