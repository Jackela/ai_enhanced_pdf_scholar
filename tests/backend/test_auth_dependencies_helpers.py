"""
Unit tests for AuthenticationRequired helper methods.

Tests the refactored helper methods:
- _extract_token()
- _validate_token()
- _fetch_and_validate_user()
- _finalize_authentication()
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.api.auth.dependencies import AuthenticationRequired
from backend.api.auth.models import UserRole


# Mock payload class
class MockPayload:
    def __init__(self, sub: str, version: int = 1):
        self.sub = sub
        self.version = version


# Mock user class
class MockUser:
    def __init__(
        self,
        id: int = 1,
        username: str = "testuser",
        is_active: bool = True,
        is_verified: bool = True,
        locked: bool = False,
        refresh_token_version: int = 1,
        role: str = "user",
    ):
        self.id = id
        self.username = username
        self.is_active = is_active
        self.is_verified = is_verified
        self._locked = locked
        self.refresh_token_version = refresh_token_version
        self.role = role

    def is_account_locked(self) -> bool:
        return self._locked


# Mock request class
class MockRequest:
    def __init__(self):
        self.state = Mock()


# ===== Tests for _extract_token() =====


def test_extract_token_from_header_success():
    """Test extracting token from Authorization header."""
    auth_req = AuthenticationRequired()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="test_token_123"
    )

    token = auth_req._extract_token(credentials, None)

    assert token == "test_token_123"


def test_extract_token_from_cookie_success():
    """Test extracting token from cookie when header is absent."""
    auth_req = AuthenticationRequired()

    token = auth_req._extract_token(None, "cookie_token_456")

    assert token == "cookie_token_456"


def test_extract_token_header_priority():
    """Test that header takes priority over cookie."""
    auth_req = AuthenticationRequired()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="header_token"
    )

    token = auth_req._extract_token(credentials, "cookie_token")

    assert token == "header_token"


def test_extract_token_missing_raises_401():
    """Test that missing token raises 401 Unauthorized."""
    auth_req = AuthenticationRequired()

    with pytest.raises(HTTPException) as exc_info:
        auth_req._extract_token(None, None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Authentication required"
    assert "WWW-Authenticate" in exc_info.value.headers


def test_extract_token_empty_credentials_raises_401():
    """Test that empty credentials object raises 401."""
    auth_req = AuthenticationRequired()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")

    with pytest.raises(HTTPException) as exc_info:
        auth_req._extract_token(credentials, None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ===== Tests for _validate_token() =====


def test_validate_token_success(monkeypatch):
    """Test successful token validation."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="123", version=1)

    # Mock jwt_handler.decode_token to return payload
    mock_jwt_handler = MagicMock()
    mock_jwt_handler.decode_token.return_value = mock_payload

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(deps_module, "jwt_handler", mock_jwt_handler)

    payload = auth_req._validate_token("valid_token")

    assert payload == mock_payload
    assert payload.sub == "123"


def test_validate_token_expired_raises_401(monkeypatch):
    """Test that expired token raises 401."""
    auth_req = AuthenticationRequired()

    # Mock jwt_handler to return None (invalid/expired)
    mock_jwt_handler = MagicMock()
    mock_jwt_handler.decode_token.return_value = None

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(deps_module, "jwt_handler", mock_jwt_handler)

    with pytest.raises(HTTPException) as exc_info:
        auth_req._validate_token("expired_token")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid or expired token"


def test_validate_token_invalid_raises_401(monkeypatch):
    """Test that malformed token raises 401."""
    auth_req = AuthenticationRequired()

    mock_jwt_handler = MagicMock()
    mock_jwt_handler.decode_token.return_value = None

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(deps_module, "jwt_handler", mock_jwt_handler)

    with pytest.raises(HTTPException) as exc_info:
        auth_req._validate_token("malformed_token")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "WWW-Authenticate" in exc_info.value.headers


# ===== Tests for _fetch_and_validate_user() =====


def test_fetch_user_success(monkeypatch):
    """Test successfully fetching and validating a user."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=True, is_verified=True, locked=False)
    mock_db = Mock()

    # Mock AuthenticationService
    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    def mock_auth_service_init(db):
        return mock_auth_service

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    user, service = auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert user == mock_user
    assert user.id == 123
    assert service == mock_auth_service
    mock_auth_service.get_user_by_id.assert_called_once_with(123)


def test_fetch_user_not_found_raises_401(monkeypatch):
    """Test that non-existent user raises 401."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="999", version=1)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = None

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "User not found"


def test_fetch_user_inactive_raises_403(monkeypatch):
    """Test that inactive user raises 403."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=False)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "User account is deactivated"


def test_fetch_user_locked_raises_403(monkeypatch):
    """Test that locked user raises 403."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=True, locked=True)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "User account is locked"


def test_fetch_user_unverified_raises_403_when_required(monkeypatch):
    """Test that unverified user raises 403 when verification required."""
    auth_req = AuthenticationRequired(allow_unverified=False)
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=True, is_verified=False)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Email verification required"


def test_fetch_user_unverified_allowed(monkeypatch):
    """Test that unverified user is allowed when allow_unverified=True."""
    auth_req = AuthenticationRequired(allow_unverified=True)
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=True, is_verified=False)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    user, service = auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert user == mock_user


def test_fetch_user_token_version_mismatch_raises_401(monkeypatch):
    """Test that mismatched token version raises 401."""
    auth_req = AuthenticationRequired()
    mock_payload = MockPayload(sub="123", version=1)
    mock_user = MockUser(id=123, is_active=True, refresh_token_version=2)
    mock_db = Mock()

    mock_auth_service = Mock()
    mock_auth_service.get_user_by_id.return_value = mock_user

    import backend.api.auth.dependencies as deps_module

    monkeypatch.setattr(
        deps_module, "AuthenticationService", lambda db: mock_auth_service
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_req._fetch_and_validate_user(mock_payload, mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Token has been invalidated"


# ===== Tests for _finalize_authentication() =====


def test_finalize_no_permission_required():
    """Test finalization when no specific role is required."""
    auth_req = AuthenticationRequired()
    mock_user = MockUser(id=123, role="user")
    mock_auth_service = Mock()
    mock_request = MockRequest()

    result = auth_req._finalize_authentication(
        mock_user, mock_auth_service, mock_request
    )

    assert result == mock_user
    mock_auth_service.update_user_activity.assert_called_once_with(123)
    assert mock_request.state.current_user == mock_user


def test_finalize_user_has_permission():
    """Test finalization when user has required role."""
    auth_req = AuthenticationRequired(required_roles=[UserRole.ADMIN])
    mock_user = MockUser(id=123, role="admin")
    mock_auth_service = Mock()
    mock_request = MockRequest()

    result = auth_req._finalize_authentication(
        mock_user, mock_auth_service, mock_request
    )

    assert result == mock_user
    mock_auth_service.update_user_activity.assert_called_once_with(123)


def test_finalize_user_lacks_permission_raises_403():
    """Test that insufficient permissions raise 403."""
    auth_req = AuthenticationRequired(required_roles=[UserRole.ADMIN])
    mock_user = MockUser(id=123, role="user")
    mock_auth_service = Mock()
    mock_request = MockRequest()

    with pytest.raises(HTTPException) as exc_info:
        auth_req._finalize_authentication(mock_user, mock_auth_service, mock_request)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Insufficient permissions" in exc_info.value.detail


def test_finalize_multiple_allowed_roles():
    """Test finalization with multiple allowed roles."""
    auth_req = AuthenticationRequired(
        required_roles=[UserRole.ADMIN, UserRole.MODERATOR]
    )
    mock_user = MockUser(id=123, role="moderator")
    mock_auth_service = Mock()
    mock_request = MockRequest()

    result = auth_req._finalize_authentication(
        mock_user, mock_auth_service, mock_request
    )

    assert result == mock_user
    mock_auth_service.update_user_activity.assert_called_once_with(123)
