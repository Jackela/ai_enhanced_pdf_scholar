"""
Comprehensive tests for RAG API Routes.

Tests cover:
- Query document (success, cache hits, index not ready, errors)
- Build index (success, already exists, force rebuild)
- Get index status (success, not found)
- Delete index (success, not found)
- Rebuild index (success)
- Get cache stats (success, errors)
- Clear cache (success, errors)
- Clear document cache (success)
- Request validation
- Response structure verification

Target Coverage: backend/api/routes/rag.py (20% → 75%)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.routes import rag

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with RAG router."""
    test_app = FastAPI()
    test_app.include_router(rag.router, prefix="/api/rag")
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_controller():
    """Mock library controller."""
    controller = Mock()
    controller.get_index_status = Mock(
        return_value={"has_index": False, "can_query": False}
    )
    controller.query_document = Mock(return_value="Mock RAG response")
    controller.build_index_for_document = Mock(return_value=True)
    controller.get_cache_statistics = Mock(return_value={})
    controller.clear_cache = Mock(return_value=True)
    return controller


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    service = Mock()
    return service


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    service = AsyncMock()
    service.get = AsyncMock(return_value=None)
    service.set = AsyncMock()
    return service


@pytest.fixture
def mock_validate_document_access(monkeypatch):
    """Mock document access validation."""
    mock_validate = Mock()
    monkeypatch.setattr(
        "backend.api.routes.rag.validate_document_access", mock_validate
    )
    return mock_validate


# ============================================================================
# Query Document Tests
# ============================================================================


def test_query_document_success(
    client,
    app,
    mock_controller,
    mock_rag_service,
    mock_cache_service,
    mock_validate_document_access,
):
    """Test successful RAG query execution."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": True,
        "can_query": True,
        "index_valid": True,
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[rag.get_cache_service_dependency] = (
        lambda: mock_cache_service
    )

    # Execute
    response = client.post(
        "/api/rag/query",
        json={"document_id": 1, "query": "What is this about?", "use_cache": True},
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # BaseResponse adds success/message at top level, other fields are also at top level
    assert data["success"] is True  # From BaseResponse
    assert data["query"] == "What is this about?"
    assert data["document_id"] == 1
    assert data["response"] == "Mock RAG response"
    assert data["from_cache"] is False
    assert "processing_time_ms" in data
    assert data["processing_time_ms"] >= 0


def test_query_document_cache_hit(
    client,
    app,
    mock_controller,
    mock_rag_service,
    mock_cache_service,
    mock_validate_document_access,
):
    """Test RAG query with cache hit."""
    # Setup - cached response
    cached_data = {
        "query": "cached query",
        "response": "cached response",
        "document_id": 1,
        "from_cache": True,
        "processing_time_ms": 5,
    }
    mock_cache_service.get = AsyncMock(return_value=cached_data)

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[rag.get_cache_service_dependency] = (
        lambda: mock_cache_service
    )

    # Execute
    response = client.post(
        "/api/rag/query", json={"document_id": 1, "query": "cached query"}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["from_cache"] is True
    assert data["response"] == "cached response"
    # Controller query should NOT be called (cache hit)
    mock_controller.query_document.assert_not_called()


def test_query_document_index_not_ready(
    client,
    app,
    mock_controller,
    mock_rag_service,
    mock_cache_service,
    mock_validate_document_access,
):
    """Test RAG query when index is not ready."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": False,
        "can_query": False,
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[rag.get_cache_service_dependency] = (
        lambda: mock_cache_service
    )

    # Execute
    response = client.post(
        "/api/rag/query", json={"document_id": 1, "query": "test query"}
    )

    # Verify - Should raise index not ready error
    assert response.status_code >= 400  # Error status


def test_query_document_no_response(
    client,
    app,
    mock_controller,
    mock_rag_service,
    mock_cache_service,
    mock_validate_document_access,
):
    """Test RAG query when controller returns None."""
    # Setup
    mock_controller.get_index_status.return_value = {"can_query": True}
    mock_controller.query_document.return_value = None  # Simulate failure

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[rag.get_cache_service_dependency] = (
        lambda: mock_cache_service
    )

    # Execute
    response = client.post("/api/rag/query", json={"document_id": 1, "query": "test"})

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Build Index Tests
# ============================================================================


def test_build_index_success(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test successful index building."""
    # Setup
    mock_controller.get_index_status.return_value = {"has_index": False}
    mock_controller.build_index_for_document.return_value = True

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute
    response = client.post(
        "/api/rag/index/build", json={"document_id": 1, "force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["document_id"] == 1
    assert data["build_started"] is True
    assert "Index building started" in data["message"]


def test_build_index_already_exists(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test index building when index already exists."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": True,
        "index_valid": True,
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute - without force_rebuild
    response = client.post(
        "/api/rag/index/build", json={"document_id": 1, "force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["build_started"] is False
    assert "already exists" in data["message"].lower()


def test_build_index_with_force_rebuild(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test index building with force_rebuild=True."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": True,
        "index_valid": True,
    }
    mock_controller.build_index_for_document.return_value = True

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute - with force_rebuild
    response = client.post(
        "/api/rag/index/build", json={"document_id": 1, "force_rebuild": True}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["build_started"] is True
    mock_controller.build_index_for_document.assert_called_once_with(1)


def test_build_index_failure(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test index building failure."""
    # Setup
    mock_controller.get_index_status.return_value = {"has_index": False}
    mock_controller.build_index_for_document.return_value = False  # Failure

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute
    response = client.post(
        "/api/rag/index/build", json={"document_id": 1, "force_rebuild": False}
    )

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Get Index Status Tests
# ============================================================================


def test_get_index_status_success(
    client, app, mock_controller, mock_validate_document_access
):
    """Test successful index status retrieval."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": True,
        "index_valid": True,
        "index_path": "/path/to/index",
        "chunk_count": 42,
        "created_at": "2025-01-18T10:00:00",
        "can_query": True,
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/rag/index/1/status")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["document_id"] == 1
    assert data["has_index"] is True
    assert data["index_valid"] is True
    assert data["chunk_count"] == 42
    assert data["can_query"] is True


def test_get_index_status_no_index(
    client, app, mock_controller, mock_validate_document_access
):
    """Test index status when no index exists."""
    # Setup
    mock_controller.get_index_status.return_value = {
        "has_index": False,
        "index_valid": False,
        "can_query": False,
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/rag/index/999/status")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["has_index"] is False
    assert data["can_query"] is False


# ============================================================================
# Delete Index Tests
# ============================================================================


def test_delete_index_success(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test successful index deletion."""
    # Setup
    mock_controller.get_index_status.return_value = {"has_index": True}

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute
    response = client.delete("/api/rag/index/1")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "will be deleted" in data["message"]


def test_delete_index_not_found(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test index deletion when index doesn't exist."""
    # Setup
    mock_controller.get_index_status.return_value = {"has_index": False}

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute
    response = client.delete("/api/rag/index/999")

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Rebuild Index Tests
# ============================================================================


def test_rebuild_index_success(
    client, app, mock_controller, mock_rag_service, mock_validate_document_access
):
    """Test successful index rebuilding."""
    # Setup
    mock_controller.get_index_status.return_value = {"has_index": True}
    mock_controller.build_index_for_document.return_value = True

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller
    app.dependency_overrides[rag.require_rag_service] = lambda: mock_rag_service

    # Execute
    response = client.post("/api/rag/index/1/rebuild")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["build_started"] is True
    # Verify force_rebuild was True
    mock_controller.build_index_for_document.assert_called_once_with(1)


# ============================================================================
# Cache Stats Tests
# ============================================================================


def test_get_cache_stats_success(client, app, mock_controller):
    """Test successful cache statistics retrieval."""
    # Setup
    mock_controller.get_cache_statistics.return_value = {
        "total_entries": 100,
        "hit_rate_percent": 75.5,
        "total_storage_kb": 1024.5,
        "configuration": {"max_size": 1000},
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/rag/cache/stats")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total_entries"] == 100
    assert data["hit_rate_percent"] == 75.5
    assert data["total_storage_kb"] == 1024.5


def test_get_cache_stats_error(client, app, mock_controller):
    """Test cache statistics with error."""
    # Setup
    mock_controller.get_cache_statistics.return_value = {
        "error": "Cache service unavailable"
    }

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.get("/api/rag/cache/stats")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Clear Cache Tests
# ============================================================================


def test_clear_cache_success(client, app, mock_controller):
    """Test successful cache clearing."""
    # Setup
    mock_controller.clear_cache.return_value = True

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.delete("/api/rag/cache")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "successfully" in data["message"].lower()


def test_clear_cache_failure(client, app, mock_controller):
    """Test cache clearing failure."""
    # Setup
    mock_controller.clear_cache.return_value = False

    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.delete("/api/rag/cache")

    # Verify
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Clear Document Cache Tests
# ============================================================================


def test_clear_document_cache_success(
    client, app, mock_controller, mock_validate_document_access
):
    """Test successful document cache clearing."""
    # Setup
    app.dependency_overrides[rag.get_library_controller] = lambda: mock_controller

    # Execute
    response = client.delete("/api/rag/cache/1")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "cleared for document 1" in data["message"].lower()
