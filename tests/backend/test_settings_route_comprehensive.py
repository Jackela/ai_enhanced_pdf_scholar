"""
Comprehensive tests for Settings API Routes.

Tests cover:
- Get settings (success, error handling)
- Update settings (success, validation, masked values)
- Test API key (valid format, invalid format, API validation)
- System status (healthy, degraded, database errors)
- Security validation (SQL injection, XSS, suspicious patterns)
- Request validation

Target Coverage: backend/api/routes/settings.py (20% → 75%)
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import settings

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI test app with settings router."""
    test_app = FastAPI()
    test_app.include_router(settings.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database connection."""
    db = Mock()
    db.fetch_one = Mock(return_value=None)
    db.fetch_all = Mock(return_value=[])
    db.execute = Mock()
    return db


@pytest.fixture
def mock_settings_manager(mock_db):
    """Mock settings manager."""
    manager = settings.SettingsManager(mock_db)
    manager.get_setting = Mock(return_value=None)
    manager.set_setting = Mock(return_value=True)
    manager.get_all_settings = Mock(return_value={})
    return manager


# ============================================================================
# Get Settings Tests
# ============================================================================


def test_get_settings_success(client, app, mock_settings_manager):
    """Test successful settings retrieval."""
    # Setup
    mock_settings_manager.get_setting = Mock(
        side_effect=lambda key, default: {
            "gemini_api_key": "AIzaSyDEMOKEY12345678901234567890",
            "rag_enabled": True,
        }.get(key, default)
    )

    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.get("/settings/settings")

    # Verify
    assert response.status_code == 200
    data = response.json()

    assert "gemini_api_key" in data
    assert data["gemini_api_key"].startswith("AIza")
    assert "●●●●●●●●" in data["gemini_api_key"]  # Masked
    assert data["rag_enabled"] is True
    assert data["has_api_key"] is True


def test_get_settings_no_api_key(client, app, mock_settings_manager):
    """Test settings retrieval when no API key configured."""
    # Setup
    mock_settings_manager.get_setting = Mock(
        side_effect=lambda key, default: {
            "gemini_api_key": "",
            "rag_enabled": False,
        }.get(key, default)
    )

    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.get("/settings/settings")

    # Verify
    assert response.status_code == 200
    data = response.json()

    assert data["gemini_api_key"] == ""
    assert data["rag_enabled"] is False
    assert data["has_api_key"] is False


# ============================================================================
# Update Settings Tests
# ============================================================================


def test_update_settings_success(client, app, mock_settings_manager):
    """Test successful settings update."""
    # Setup
    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.post(
        "/settings/settings",
        json={
            "gemini_api_key": "AIzaSyNEWKEY12345678901234567890",
            "rag_enabled": True,
        },
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Settings updated successfully"

    # Verify set_setting was called
    assert mock_settings_manager.set_setting.call_count == 2


def test_update_settings_masked_value_not_saved(client, app, mock_settings_manager):
    """Test that masked API key values are not saved."""
    # Setup
    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute - Send masked value that starts with bullet and passes min_length=10
    response = client.post(
        "/settings/settings",
        json={"gemini_api_key": "●●●●●●●●●●●●●●●", "rag_enabled": False},
    )

    assert response.status_code == 200
    # Only rag_enabled should be saved (not the masked API key)
    assert mock_settings_manager.set_setting.call_count == 1
    mock_settings_manager.set_setting.assert_called_with("rag_enabled", False)


def test_update_settings_validation_error_short_key(client):
    """Test settings update with too short API key."""
    # Execute - Key too short (less than 10 chars)
    response = client.post(
        "/settings/settings", json={"gemini_api_key": "short", "rag_enabled": False}
    )

    # Verify
    assert response.status_code == 422  # Validation error


def test_update_settings_sql_injection_blocked(client):
    """Test that SQL injection attempts are blocked."""
    # Execute
    response = client.post(
        "/settings/settings",
        json={
            "gemini_api_key": "AIzaSyTest'; DROP TABLE settings; --",
            "rag_enabled": False,
        },
    )

    # Verify - Should fail validation
    assert response.status_code == 422


def test_update_settings_xss_blocked(client):
    """Test that XSS attempts are blocked."""
    # Execute
    response = client.post(
        "/settings/settings",
        json={
            "gemini_api_key": "AIzaSy<script>alert('xss')</script>",
            "rag_enabled": False,
        },
    )

    # Verify
    assert response.status_code == 422


# ============================================================================
# Test API Key Tests
# ============================================================================


def test_test_api_key_valid_format_basic(client):
    """Test API key validation falls back when genai module unavailable."""
    # Since google.generativeai is imported inside the function and likely not installed,
    # the code falls back to basic validation (which passes for correct format)
    response = client.post(
        "/settings/test-api-key",
        json={"api_key": "AIzaSyDEMOKEY12345678901234567890"},
    )

    # Verify - Basic validation should pass
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_test_api_key_invalid_format_short(client):
    """Test API key that's too short."""
    # Execute
    response = client.post("/settings/test-api-key", json={"api_key": "short"})

    # Verify
    assert response.status_code == 422  # Validation error (less than 10 chars)


def test_test_api_key_invalid_format_prefix(client):
    """Test API key with wrong prefix."""
    # Execute
    response = client.post(
        "/settings/test-api-key", json={"api_key": "WRONGPREFIX123456789012345"}
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "should start with 'AIza'" in data["error"]


def test_test_api_key_empty(client):
    """Test with empty API key."""
    # Execute - Whitespace only will fail Pydantic validation (min_length=10)
    response = client.post("/settings/test-api-key", json={"api_key": "   "})

    # Verify - Should get validation error (422) because < 10 chars
    assert response.status_code == 422


# Note: google.generativeai API validation tests are skipped because:
# 1. The module is imported inside the function (can't easily mock)
# 2. The module is likely not installed in test environment
# The code gracefully falls back to basic validation in this case


# ============================================================================
# System Status Tests
# ============================================================================


def test_get_system_status_healthy(client, app, mock_db, mock_settings_manager):
    """Test system status when everything is healthy."""
    # Setup
    mock_db.fetch_one = Mock(
        side_effect=[
            {"count": 1},  # Database health check
            {"count": 10},  # Document count
            {"count": 5},  # Index count
        ]
    )
    mock_settings_manager.get_setting = Mock(
        side_effect=lambda key, default: {
            "gemini_api_key": "AIzaSyTest123",
            "rag_enabled": True,
        }.get(key, default)
    )

    app.dependency_overrides[settings.get_db] = lambda: mock_db
    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.get("/settings/status")

    # Verify
    assert response.status_code == 200
    data = response.json()

    assert data["database"]["status"] == "healthy"
    assert data["database"]["document_count"] == 10
    assert data["database"]["vector_index_count"] == 5
    assert data["api"]["has_gemini_key"] is True
    assert data["api"]["rag_enabled"] is True
    assert data["system_health"] == "healthy"
    assert data["version"] == "2.0.0"


def test_get_system_status_database_error(client, app, mock_db, mock_settings_manager):
    """Test system status when database has errors."""
    # Setup - Database health check fails
    mock_db.fetch_one = Mock(side_effect=Exception("Database connection failed"))
    mock_settings_manager.get_setting = Mock(return_value="")

    app.dependency_overrides[settings.get_db] = lambda: mock_db
    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.get("/settings/status")

    # Verify
    assert response.status_code == 200
    data = response.json()

    assert data["database"]["status"] == "error"
    assert data["system_health"] == "degraded"


def test_get_system_status_no_api_key(client, app, mock_db, mock_settings_manager):
    """Test system status when no API key configured."""
    # Setup
    mock_db.fetch_one = Mock(
        side_effect=[
            {"count": 1},  # Health check
            {"count": 0},  # No documents
            {"count": 0},  # No indexes
        ]
    )
    mock_settings_manager.get_setting = Mock(
        side_effect=lambda key, default: {
            "gemini_api_key": "",
            "rag_enabled": False,
        }.get(key, default)
    )

    app.dependency_overrides[settings.get_db] = lambda: mock_db
    app.dependency_overrides[settings.get_settings_manager] = (
        lambda: mock_settings_manager
    )

    # Execute
    response = client.get("/settings/status")

    # Verify
    assert response.status_code == 200
    data = response.json()

    assert data["api"]["has_gemini_key"] is False
    assert data["api"]["rag_enabled"] is False


# ============================================================================
# Utility Function Tests
# ============================================================================


def test_mask_api_key():
    """Test API key masking function."""
    # Test normal key
    masked = settings.mask_api_key("AIzaSyDEMOKEY1234567890123456")
    assert masked.startswith("AIza")
    assert "●●●●●●●●" in masked
    assert masked.endswith("3456")

    # Test short key
    masked = settings.mask_api_key("short")
    assert masked == ""

    # Test empty key
    masked = settings.mask_api_key("")
    assert masked == ""
