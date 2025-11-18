"""
Authentication Models
User and authentication-related database models and Pydantic schemas.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from backend.api.auth.constants import BEARER_TOKEN_SCHEME

# SQLAlchemy Base
Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================


class UserRole(str, Enum):
    """User role enumeration for RBAC."""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    MODERATOR = "moderator"


class AccountStatus(str, Enum):
    """Account status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


# ============================================================================
# SQLAlchemy Models
# ============================================================================


class UserModel(Base):
    """
    SQLAlchemy User model for database persistence.
    Stores user authentication and profile information.
    """

    __tablename__ = "users"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Profile fields
    full_name = Column(String(255), nullable=True)
    role = Column(String(20), default=UserRole.USER.value, nullable=False)

    # Security fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    account_status = Column(
        String(30), default=AccountStatus.PENDING_VERIFICATION.value, nullable=False
    )
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_failed_login = Column(DateTime, nullable=True)
    account_locked_until = Column(DateTime, nullable=True)

    # Password management
    password_changed_at = Column(DateTime, nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)

    # Email verification
    email_verification_token = Column(String(255), nullable=True)
    email_verified_at = Column(DateTime, nullable=True)

    # Session management
    refresh_token_version = Column(Integer, default=0, nullable=False)
    last_login = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Additional security metadata (JSON field for flexibility)
    security_metadata = Column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "account_status": self.account_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def increment_failed_login(self) -> None:
        """Increment failed login attempts and update timestamp."""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

    def reset_failed_login_attempts(self) -> None:
        """Reset failed login attempts after successful login."""
        self.failed_login_attempts = 0
        self.last_failed_login = None

    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock account for specified duration."""
        from datetime import timedelta

        self.account_locked_until = datetime.utcnow() + timedelta(
            minutes=duration_minutes
        )
        self.account_status = AccountStatus.LOCKED.value

    def is_account_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.account_locked_until:
            return datetime.utcnow() < self.account_locked_until
        return False

    def unlock_account(self) -> None:
        """Unlock account."""
        self.account_locked_until = None
        self.account_status = (
            AccountStatus.ACTIVE.value
            if self.is_verified
            else AccountStatus.PENDING_VERIFICATION.value
        )
        self.failed_login_attempts = 0


class RefreshTokenModel(Base):
    """
    SQLAlchemy model for refresh token storage and management.
    Implements token blacklisting and rotation.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    token_jti = Column(String(255), unique=True, index=True, nullable=False)  # JWT ID
    token_family = Column(String(255), index=True, nullable=False)  # For token rotation
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    device_info = Column(String(500), nullable=True)  # User agent, IP, etc.

    def is_valid(self) -> bool:
        """Check if token is still valid."""
        if self.revoked_at:
            return False
        return datetime.utcnow() < self.expires_at

    def revoke(self, reason: str = "Manual revocation") -> None:
        """Revoke this token."""
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason


# ============================================================================
# Pydantic Schemas
# ============================================================================


class PasswordValidation:
    """Password validation rules."""

    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    @classmethod
    def validate(cls, password: str) -> tuple[bool, list[str]]:
        """
        Validate password against security requirements.
        Returns: (is_valid, list_of_errors)
        """
        errors = []

        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long")

        if len(password) > cls.MAX_LENGTH:
            errors.append(
                f"Password must be no more than {cls.MAX_LENGTH} characters long"
            )

        if cls.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        if cls.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        if cls.REQUIRE_DIGIT and not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")

        if cls.REQUIRE_SPECIAL and not re.search(
            f"[{re.escape(cls.SPECIAL_CHARS)}]", password
        ):
            errors.append(
                f"Password must contain at least one special character from: {cls.SPECIAL_CHARS}"
            )

        # Check for common weak passwords
        weak_passwords = ["password", "123456", "password123", "admin", "letmein"]
        if password.lower() in weak_passwords:
            errors.append("Password is too common and easily guessable")

        return len(errors) == 0, errors


class UserCreate(BaseModel):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format and reserved names."""
        reserved_names = ["admin", "root", "system", "api", "auth", "user", "test"]
        if v.lower() in reserved_names:
            raise ValueError(f"Username '{v}' is reserved and cannot be used")
        return v.lower()  # Store usernames in lowercase

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, errors = PasswordValidation.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower()


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(..., description="Username or email")
    password: str = Field(...)
    remember_me: bool = Field(False, description="Extended session duration")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        """Normalize username/email to lowercase."""
        return v.lower().strip()


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    full_name: str | None = Field(None, max_length=255)
    email: EmailStr | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Normalize email to lowercase."""
        return v.lower() if v else None


class PasswordChange(BaseModel):
    """Schema for password change."""

    current_password: str = Field(...)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        is_valid, errors = PasswordValidation.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v

    @model_validator(mode="after")
    def validate_passwords_different(self) -> Any:
        """Ensure new password is different from current."""
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self


class PasswordReset(BaseModel):
    """Schema for password reset request."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower()


class PasswordResetConfirm(BaseModel):
    """Schema for confirming password reset."""

    token: str = Field(...)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate new password strength."""
        is_valid, errors = PasswordValidation.validate(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = BEARER_TOKEN_SCHEME
    expires_in: int = Field(..., description="Access token expiry in seconds")


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(...)


class UserResponse(BaseModel):
    """Schema for user response (public info)."""

    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    """Extended user profile response (for authenticated user)."""

    account_status: str
    email_verified_at: datetime | None
    password_changed_at: datetime | None
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailVerification(BaseModel):
    """Schema for email verification."""

    token: str = Field(...)


class LoginAttemptLog(BaseModel):
    """Schema for logging login attempts."""

    username: str
    ip_address: str
    user_agent: str | None
    success: bool
    failure_reason: str | None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
