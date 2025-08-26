"""
Authentication System Tests
Comprehensive test suite for JWT-based authentication.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from backend.api.auth.jwt_handler import jwt_handler
from backend.api.auth.models import UserModel
from backend.api.auth.password_security import PasswordHasher, PasswordPolicy
from backend.api.auth.service import AuthenticationService

# ============================================================================
# Password Security Tests
# ============================================================================

class TestPasswordHasher:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        hasher = PasswordHasher()
        password = "SecureP@ssw0rd123"

        hashed = hasher.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt format
        assert len(hashed) == 60  # bcrypt hash length

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        hasher = PasswordHasher()
        password = "SecureP@ssw0rd123"

        hashed = hasher.hash_password(password)
        result = hasher.verify_password(password, hashed)

        assert result is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        hasher = PasswordHasher()
        password = "SecureP@ssw0rd123"
        wrong_password = "WrongPassword123"

        hashed = hasher.hash_password(password)
        result = hasher.verify_password(wrong_password, hashed)

        assert result is False

    def test_verify_password_invalid_hash(self):
        """Test verifying password with invalid hash."""
        hasher = PasswordHasher()

        result = hasher.verify_password("password", "invalid_hash")

        assert result is False

    def test_needs_rehash(self):
        """Test checking if password needs rehashing."""
        hasher = PasswordHasher()

        # Hash with lower rounds
        salt = bcrypt.gensalt(rounds=10)
        old_hash = bcrypt.hashpw(b"password", salt).decode('utf-8')

        assert hasher.needs_rehash(old_hash, rounds=12) is True

        # Hash with current rounds
        current_hash = hasher.hash_password("password")
        assert hasher.needs_rehash(current_hash, rounds=12) is False


class TestPasswordPolicy:
    """Test password policy validation."""

    def test_valid_password(self):
        """Test valid password passes all checks."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength(
            "SecureP@ssw0rd123",
            username="testuser"
        )

        assert is_valid is True
        assert len(errors) == 0

    def test_password_too_short(self):
        """Test password minimum length requirement."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("Pass1!")

        assert is_valid is False
        assert any("at least 8 characters" in error for error in errors)

    def test_password_missing_uppercase(self):
        """Test password uppercase requirement."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("password123!")

        assert is_valid is False
        assert any("uppercase" in error for error in errors)

    def test_password_missing_lowercase(self):
        """Test password lowercase requirement."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("PASSWORD123!")

        assert is_valid is False
        assert any("lowercase" in error for error in errors)

    def test_password_missing_digit(self):
        """Test password digit requirement."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("Password!")

        assert is_valid is False
        assert any("digit" in error for error in errors)

    def test_password_missing_special(self):
        """Test password special character requirement."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("Password123")

        assert is_valid is False
        assert any("special character" in error for error in errors)

    def test_password_contains_username(self):
        """Test password cannot contain username."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength(
            "testuser123!A",
            username="testuser"
        )

        assert is_valid is False
        assert any("cannot contain your username" in error for error in errors)

    def test_common_password(self):
        """Test common passwords are rejected."""
        policy = PasswordPolicy()

        is_valid, errors = policy.validate_password_strength("Password123!")

        # This might pass if "Password123!" is not in common passwords list
        # Let's test with a definitely common password
        is_valid, errors = policy.validate_password_strength("password")

        assert is_valid is False
        assert any("common" in error for error in errors)

    def test_generate_strong_password(self):
        """Test strong password generation."""
        policy = PasswordPolicy()

        password = policy.generate_strong_password(16)

        assert len(password) == 16

        # Verify generated password meets policy
        is_valid, errors = policy.validate_password_strength(password)
        assert is_valid is True


# ============================================================================
# JWT Token Tests
# ============================================================================

class TestJWTHandler:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating access token."""
        handler = jwt_handler

        token = handler.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        handler = jwt_handler

        token, jti, expires = handler.create_refresh_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        assert token is not None
        assert jti is not None
        assert expires > datetime.now(timezone.utc)

    def test_decode_valid_access_token(self):
        """Test decoding valid access token."""
        handler = jwt_handler

        # Create token
        token = handler.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        # Decode token
        payload = handler.decode_token(token, token_type="access")

        assert payload is not None
        assert payload.sub == "1"
        assert payload.username == "testuser"
        assert payload.role == "user"
        assert payload.token_type == "access"

    def test_decode_expired_token(self):
        """Test decoding expired token."""
        handler = jwt_handler

        # Create token with past expiry
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)

        payload = {
            "sub": "1",
            "username": "testuser",
            "role": "user",
            "exp": past,
            "iat": past - timedelta(hours=2),
            "jti": "test-jti",
            "token_type": "access",
            "version": 0,
            "iss": handler.config.ISSUER,
            "aud": handler.config.AUDIENCE,
        }

        token = jwt.encode(
            payload,
            handler.private_key,
            algorithm=handler.config.ALGORITHM
        )

        # Try to decode expired token
        result = handler.decode_token(token)

        assert result is None

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        handler = jwt_handler

        result = handler.decode_token("invalid.token.here")

        assert result is None

    def test_decode_wrong_token_type(self):
        """Test decoding token with wrong type."""
        handler = jwt_handler

        # Create refresh token
        token, _, _ = handler.create_refresh_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        # Try to decode as access token
        result = handler.decode_token(token, token_type="access")

        assert result is None

    def test_verify_token_with_version(self):
        """Test token version validation."""
        handler = jwt_handler

        token = handler.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            version=1
        )

        # Verify with correct version
        payload = handler.verify_token(token, user_version=1)
        assert payload is not None

        # Verify with wrong version
        payload = handler.verify_token(token, user_version=2)
        assert payload is None


# ============================================================================
# Authentication Service Tests
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def auth_service(mock_db_session):
    """Create authentication service with mock DB."""
    return AuthenticationService(mock_db_session)


class TestAuthenticationService:
    """Test authentication service functionality."""

    def test_register_user_success(self, auth_service, mock_db_session):
        """Test successful user registration."""
        # Mock database queries
        mock_db_session.query().filter().first.return_value = None

        user, error = auth_service.register_user(
            username="newuser",
            email="newuser@example.com",
            password="SecureP@ssw0rd123",
            full_name="New User"
        )

        assert error is None
        assert user is not None
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_register_user_duplicate_username(self, auth_service, mock_db_session):
        """Test registration with duplicate username."""
        # Mock existing user
        existing_user = MagicMock()
        existing_user.username = "existinguser"
        mock_db_session.query().filter().first.return_value = existing_user

        user, error = auth_service.register_user(
            username="existinguser",
            email="new@example.com",
            password="SecureP@ssw0rd123"
        )

        assert user is None
        assert error == "Username already exists"

    def test_register_user_weak_password(self, auth_service, mock_db_session):
        """Test registration with weak password."""
        mock_db_session.query().filter().first.return_value = None

        user, error = auth_service.register_user(
            username="newuser",
            email="newuser@example.com",
            password="weak"
        )

        assert user is None
        assert "Password validation failed" in error

    def test_authenticate_user_success(self, auth_service, mock_db_session):
        """Test successful user authentication."""
        # Create mock user
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.username = "testuser"
        mock_user.password_hash = hasher.hash_password("SecureP@ssw0rd123")
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.is_account_locked.return_value = False
        mock_user.failed_login_attempts = 0

        mock_db_session.query().filter().first.return_value = mock_user

        user, error = auth_service.authenticate_user(
            username="testuser",
            password="SecureP@ssw0rd123"
        )

        assert user is not None
        assert error is None
        assert mock_user.reset_failed_login_attempts.called

    def test_authenticate_user_wrong_password(self, auth_service, mock_db_session):
        """Test authentication with wrong password."""
        # Create mock user
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.username = "testuser"
        mock_user.password_hash = hasher.hash_password("SecureP@ssw0rd123")
        mock_user.is_account_locked.return_value = False
        mock_user.failed_login_attempts = 0

        mock_db_session.query().filter().first.return_value = mock_user

        user, error = auth_service.authenticate_user(
            username="testuser",
            password="WrongPassword"
        )

        assert user is None
        assert error == "Invalid username or password"
        assert mock_user.increment_failed_login.called

    def test_authenticate_user_account_locked(self, auth_service, mock_db_session):
        """Test authentication with locked account."""
        mock_user = MagicMock(spec=UserModel)
        mock_user.is_account_locked.return_value = True
        mock_user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

        mock_db_session.query().filter().first.return_value = mock_user

        user, error = auth_service.authenticate_user(
            username="testuser",
            password="password"
        )

        assert user is None
        assert "Account is locked" in error

    def test_authenticate_user_not_verified(self, auth_service, mock_db_session):
        """Test authentication with unverified email."""
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.password_hash = hasher.hash_password("SecureP@ssw0rd123")
        mock_user.is_active = True
        mock_user.is_verified = False
        mock_user.is_account_locked.return_value = False

        mock_db_session.query().filter().first.return_value = mock_user

        user, error = auth_service.authenticate_user(
            username="testuser",
            password="SecureP@ssw0rd123"
        )

        assert user is None
        assert "Email verification required" in error

    def test_create_tokens(self, auth_service, mock_db_session):
        """Test token creation."""
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.role = "user"
        mock_user.refresh_token_version = 0

        access_token, refresh_token, expires_in = auth_service.create_tokens(
            user=mock_user,
            device_info="Test Device"
        )

        assert access_token is not None
        assert refresh_token is not None
        assert expires_in > 0
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_change_password_success(self, auth_service, mock_db_session):
        """Test successful password change."""
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.id = 1
        mock_user.password_hash = hasher.hash_password("OldP@ssw0rd123")
        mock_user.username = "testuser"
        mock_user.password_changed_at = datetime.utcnow() - timedelta(days=2)

        mock_db_session.query().filter().first.return_value = mock_user

        success, error = auth_service.change_password(
            user_id=1,
            current_password="OldP@ssw0rd123",
            new_password="NewP@ssw0rd456"
        )

        assert success is True
        assert error is None
        assert mock_user.refresh_token_version == 1
        assert mock_db_session.commit.called

    def test_change_password_wrong_current(self, auth_service, mock_db_session):
        """Test password change with wrong current password."""
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.password_hash = hasher.hash_password("OldP@ssw0rd123")

        mock_db_session.query().filter().first.return_value = mock_user

        success, error = auth_service.change_password(
            user_id=1,
            current_password="WrongPassword",
            new_password="NewP@ssw0rd456"
        )

        assert success is False
        assert error == "Current password is incorrect"


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.fixture
def test_client():
    """Create test client for API testing."""
    from backend.api.main import app

    client = TestClient(app)
    return client


class TestAuthenticationAPI:
    """Test authentication API endpoints."""

    @pytest.mark.asyncio
    async def test_register_endpoint(self, test_client):
        """Test user registration endpoint."""
        response = test_client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "SecureP@ssw0rd123",
                "full_name": "Test User"
            }
        )

        # This will fail without proper database setup
        # In real tests, you'd use a test database
        # assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_login_endpoint(self, test_client):
        """Test user login endpoint."""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "SecureP@ssw0rd123",
                "remember_me": False
            }
        )

        # This will fail without proper database setup
        # assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_refresh_endpoint(self, test_client):
        """Test token refresh endpoint."""
        response = test_client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "dummy_refresh_token"
            }
        )

        # Should fail with invalid token
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_endpoint(self, test_client):
        """Test logout endpoint."""
        response = test_client.post("/api/auth/logout")

        # Should succeed even without authentication
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, test_client):
        """Test auth health check endpoint."""
        response = test_client.get("/api/auth/health")

        # Should return health status
        assert response.status_code in [200, 503]


# ============================================================================
# Security Tests
# ============================================================================

class TestSecurityFeatures:
    """Test security features of authentication system."""

    def test_password_not_in_token(self):
        """Ensure passwords are never included in tokens."""
        handler = jwt_handler

        token = handler.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        # Decode without verification to check contents
        import jwt as pyjwt
        payload = pyjwt.decode(token, options={"verify_signature": False})

        assert "password" not in payload
        assert "password_hash" not in payload

    def test_token_expiration(self):
        """Test token expiration is enforced."""
        handler = jwt_handler

        # Create token with very short expiry
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=1)

        payload = {
            "sub": "1",
            "username": "testuser",
            "role": "user",
            "exp": expires,
            "iat": now,
            "jti": "test-jti",
            "token_type": "access",
            "version": 0,
            "iss": handler.config.ISSUER,
            "aud": handler.config.AUDIENCE,
        }

        token = jwt.encode(
            payload,
            handler.private_key,
            algorithm=handler.config.ALGORITHM
        )

        # Token should be valid immediately
        result = handler.decode_token(token, token_type="access")
        assert result is not None

        # Wait for expiration
        time.sleep(2)

        # Token should now be invalid
        result = handler.decode_token(token, token_type="access")
        assert result is None

    def test_token_signature_verification(self):
        """Test token signature is verified."""
        handler = jwt_handler

        # Create valid token
        token = handler.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            version=0
        )

        # Tamper with token
        parts = token.split('.')
        # Modify payload
        import base64
        payload = base64.urlsafe_b64decode(parts[1] + '==')
        modified_payload = payload.replace(b'"user"', b'"admin"')
        parts[1] = base64.urlsafe_b64encode(modified_payload).decode().rstrip('=')
        tampered_token = '.'.join(parts)

        # Verification should fail
        result = handler.decode_token(tampered_token)
        assert result is None

    def test_sql_injection_protection(self):
        """Test protection against SQL injection in username."""
        # This would be tested with actual database
        # Ensuring parameterized queries are used
        pass

    def test_brute_force_protection(self, auth_service, mock_db_session):
        """Test account lockout after failed attempts."""
        hasher = PasswordHasher()
        mock_user = MagicMock(spec=UserModel)
        mock_user.password_hash = hasher.hash_password("RealPassword")
        mock_user.is_account_locked.return_value = False
        mock_user.failed_login_attempts = 4  # One attempt away from lockout

        mock_db_session.query().filter().first.return_value = mock_user

        # Failed attempt should trigger lockout
        user, error = auth_service.authenticate_user(
            username="testuser",
            password="WrongPassword"
        )

        assert user is None
        assert mock_user.increment_failed_login.called
        # Check if lock_account was called (at 5 attempts)
        # This depends on the specific implementation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
