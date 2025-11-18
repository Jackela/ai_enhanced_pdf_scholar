"""
Comprehensive tests for Queries API Routes.

Tests cover:
- Single document query execution (success, cache hits, errors)
- Multi-document query execution
- Cache management (clear, stats)
- Error handling (404, 500, 501)
- Request validation
- Response structure verification

Target Coverage: backend/api/routes/queries.py (15% → 75%)
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.routes import queries
from src.database.models import DocumentModel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with queries router."""
    test_app = FastAPI()
    test_app.include_router(queries.router, prefix="/api/queries")
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
    repo.get_by_ids = Mock(return_value=[])
    return repo


@pytest.fixture
def mock_cache_manager():
    """Mock RAG cache manager."""
    manager = Mock()
    manager.get_cached_query = Mock(return_value=None)
    manager.cache_query_result = Mock()
    manager.invalidate_document_cache = Mock(return_value=0)
    manager.get_cache_stats = Mock(return_value={})
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


@pytest.fixture(autouse=True)
def enable_rag_services(monkeypatch):
    """Enable RAG services for all tests."""
    from config import Config

    monkeypatch.setattr(Config, "is_rag_services_enabled", lambda: True)


# ============================================================================
# Single Document Query Tests
# ============================================================================


def test_query_document_success(
    client, app, mock_doc_repo, mock_cache_manager, sample_document
):
    """Test successful single document query."""
    # Setup mocks
    mock_doc_repo.get_by_id.return_value = sample_document

    # Override dependencies
    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    # Execute
    response = client.post(
        "/api/queries/document/1",
        json={"query": "What is this about?", "temperature": 0.5, "max_results": 5},
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "data" in data
    assert data["data"]["query"] == "What is this about?"
    assert data["data"]["document_id"] == 1
    assert data["data"]["cached"] is False
    assert "response" in data["data"]
    assert "processing_time_ms" in data["data"]


def test_query_document_cache_hit(
    client, app, mock_doc_repo, mock_cache_manager, sample_document
):
    """Test query with cache hit."""
    # Setup mocks
    mock_doc_repo.get_by_id.return_value = sample_document
    mock_cache_manager.get_cached_query.return_value = "Cached response text"

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    # Execute
    response = client.post(
        "/api/queries/document/1", json={"query": "What is this about?"}
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["cached"] is True
    assert data["data"]["response"] == "Cached response text"

    # Verify cache was checked but not written
    mock_cache_manager.get_cached_query.assert_called_once()
    mock_cache_manager.cache_query_result.assert_not_called()


def test_query_document_not_found(client, app, mock_doc_repo, mock_cache_manager):
    """Test query with non-existent document."""
    # Setup mocks
    mock_doc_repo.get_by_id.return_value = None

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    # Execute
    response = client.post(
        "/api/queries/document/999", json={"query": "What is this about?"}
    )

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "Document 999 not found" in data["detail"]


def test_query_document_invalid_query_length(client):
    """Test query with empty query string."""
    # Execute (no mocks needed - validation happens before dependencies)
    response = client.post("/api/queries/document/1", json={"query": ""})

    # Verify
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_query_document_query_too_long(client):
    """Test query with excessive length."""
    # Create query > 2000 chars
    long_query = "x" * 2001

    response = client.post("/api/queries/document/1", json={"query": long_query})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_query_document_invalid_temperature(client):
    """Test query with invalid temperature."""
    response = client.post(
        "/api/queries/document/1", json={"query": "test", "temperature": 1.5}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_query_document_rag_disabled(client, app, monkeypatch):
    """Test query when RAG services are disabled."""
    from config import Config

    monkeypatch.setattr(Config, "is_rag_services_enabled", lambda: False)

    response = client.post("/api/queries/document/1", json={"query": "test"})

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert "not available" in response.json()["detail"]


# ============================================================================
# Multi-Document Query Tests
# ============================================================================


def test_multi_document_query_success(client, app, mock_doc_repo, sample_document):
    """Test successful multi-document query."""
    # Setup mocks
    doc1 = sample_document
    doc2 = DocumentModel(
        id=2,
        title="Doc 2",
        file_path="/test/doc2.pdf",
        file_hash="hash2",
        file_size=2048,
        file_type=".pdf",
    )
    mock_doc_repo.get_by_ids.return_value = [doc1, doc2]

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo

    # Execute
    response = client.post(
        "/api/queries/multi-document",
        json={
            "query": "Compare these documents",
            "document_ids": [1, 2],
            "synthesis_mode": "compare",
        },
    )

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["query"] == "Compare these documents"
    assert data["data"]["document_ids"] == [1, 2]
    assert "response" in data["data"]


def test_multi_document_query_missing_documents(
    client, app, mock_doc_repo, sample_document
):
    """Test multi-document query with missing documents."""
    # Setup: Only return one document when two requested
    mock_doc_repo.get_by_ids.return_value = [sample_document]

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo

    # Execute
    response = client.post(
        "/api/queries/multi-document",
        json={"query": "test", "document_ids": [1, 999]},
    )

    # Verify
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Documents not found" in response.json()["detail"]


def test_multi_document_query_empty_document_list(client):
    """Test multi-document query with empty document list."""
    response = client.post(
        "/api/queries/multi-document",
        json={"query": "test", "document_ids": []},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# Cache Management Tests
# ============================================================================


def test_clear_document_cache_success(client, app, mock_cache_manager):
    """Test successful cache clearing."""
    mock_cache_manager.invalidate_document_cache.return_value = 5

    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    response = client.delete("/api/queries/cache/document/1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_cache_manager.invalidate_document_cache.assert_called_once_with(1)


def test_get_cache_stats_success(client, app, mock_cache_manager):
    """Test cache statistics retrieval."""
    stats = {
        "total_entries": 100,
        "hit_rate": 0.75,
        "total_hits": 75,
        "total_misses": 25,
    }
    mock_cache_manager.get_cache_stats.return_value = stats

    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    response = client.get("/api/queries/cache/stats")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["data"]["total_entries"] == 100
    assert data["data"]["hit_rate"] == 0.75


# ============================================================================
# Response Structure Validation
# ============================================================================


def test_query_response_hateoas_links(
    client, app, mock_doc_repo, mock_cache_manager, sample_document
):
    """Test HATEOAS links in query response."""
    mock_doc_repo.get_by_id.return_value = sample_document

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    response = client.post("/api/queries/document/1", json={"query": "test"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "_links" in data["data"]
    assert "self" in data["data"]["_links"]
    assert "related" in data["data"]["_links"]
    assert "document" in data["data"]["_links"]["related"]


def test_query_response_processing_time(
    client, app, mock_doc_repo, mock_cache_manager, sample_document
):
    """Test processing time is included in response."""
    mock_doc_repo.get_by_id.return_value = sample_document

    app.dependency_overrides[queries.get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[queries.get_rag_cache_manager] = lambda: mock_cache_manager

    response = client.post("/api/queries/document/1", json={"query": "test"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "processing_time_ms" in data["data"]
    assert data["data"]["processing_time_ms"] >= 0
