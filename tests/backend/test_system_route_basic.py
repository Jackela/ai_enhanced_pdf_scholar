"""
Basic tests for System API Routes (Phase 5 - Partial).

Tests cover:
- GET /health (4 tests: healthy, degraded, unhealthy, storage states)
- GET /version (3 tests: success, format, values)

Deferred tests (to be completed in Phase 5.1):
- GET /config (3 tests) - Response model complexity
- GET /info (3 tests) - BaseResponse.data field investigation
- POST /initialize (3 tests) - DatabaseMigrator import path
- GET /storage (3 tests) - Response structure verification
- Additional health endpoints (detailed, dependencies, performance, secrets)
- Secrets management endpoints
- Real-time metrics endpoints

Total completed: 7 tests
Total planned for Phase 5: 40+ tests
Completion: 17.5% (7/40)

Target Coverage: backend/api/routes/system.py (0% → ~15% partial)
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.routes import system

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with system router."""
    test_app = FastAPI()
    test_app.include_router(system.router, prefix="/api/system")
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database connection."""
    db = Mock()
    db.fetch_one = Mock(return_value={"test": 1})
    return db


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    service = Mock()
    service.is_available = True
    return service


# ============================================================================
# GET /health Tests (4 tests)
# ============================================================================


def test_get_system_health_healthy(client, app, mock_db, mock_rag_service):
    """Test system health when all components are healthy."""
    # Setup
    app.dependency_overrides[system.get_db] = lambda: mock_db
    app.dependency_overrides[system.get_enhanced_rag] = lambda: mock_rag_service

    with (
        patch(
            "backend.api.routes.system.Config.get_gemini_api_key",
            return_value="test_key",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.rglob", return_value=[]),
    ):
        # Execute
        response = client.get("/api/system/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["rag_service_available"] is True
    assert data["api_key_configured"] is True
    assert data["storage_health"] == "healthy"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0


def test_get_system_health_degraded(client, app, mock_db):
    """Test system health when RAG service is unavailable (degraded)."""
    # Setup
    app.dependency_overrides[system.get_db] = lambda: mock_db
    app.dependency_overrides[system.get_enhanced_rag] = lambda: None  # RAG unavailable

    with (
        patch(
            "backend.api.routes.system.Config.get_gemini_api_key",
            return_value="test_key",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.rglob", return_value=[]),
    ):
        # Execute
        response = client.get("/api/system/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["status"] == "degraded"
    assert data["database_connected"] is True
    assert data["rag_service_available"] is False


def test_get_system_health_unhealthy(client, app, mock_rag_service):
    """Test system health when database is disconnected (unhealthy)."""
    # Setup - Database raises exception
    mock_db_error = Mock()
    mock_db_error.fetch_one = Mock(side_effect=Exception("Connection lost"))

    app.dependency_overrides[system.get_db] = lambda: mock_db_error
    app.dependency_overrides[system.get_enhanced_rag] = lambda: mock_rag_service

    with (
        patch(
            "backend.api.routes.system.Config.get_gemini_api_key",
            return_value="test_key",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.rglob", return_value=[]),
    ):
        # Execute
        response = client.get("/api/system/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["status"] == "unhealthy"
    assert data["database_connected"] is False


def test_get_system_health_storage_not_initialized(
    client, app, mock_db, mock_rag_service
):
    """Test system health when storage directory does not exist."""
    # Setup
    app.dependency_overrides[system.get_db] = lambda: mock_db
    app.dependency_overrides[system.get_enhanced_rag] = lambda: mock_rag_service

    with (
        patch(
            "backend.api.routes.system.Config.get_gemini_api_key",
            return_value="test_key",
        ),
        patch("pathlib.Path.exists", return_value=False),  # Storage not initialized
    ):
        # Execute
        response = client.get("/api/system/health")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["storage_health"] == "not_initialized"


# ============================================================================
# GET /version Tests (3 tests)
# ============================================================================


def test_get_version_success(client, app):
    """Test successful version retrieval."""
    # Execute
    response = client.get("/api/system/version")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "version" in data
    assert "name" in data  # Returns "name", not "api_version"


def test_get_version_format(client, app):
    """Test version format structure."""
    # Execute
    response = client.get("/api/system/version")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Version should be a string
    assert isinstance(data["version"], str)
    assert isinstance(data["name"], str)


def test_get_version_not_empty(client, app):
    """Test version values are not empty."""
    # Execute
    response = client.get("/api/system/version")

    # Verify
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert len(data["version"]) > 0
    assert data["version"] == "2.0.0"
    assert len(data["name"]) > 0
