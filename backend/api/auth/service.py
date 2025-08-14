"""
Authentication Service
Core authentication business logic and user management.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.api.auth.jwt_handler import jwt_handler
from backend.api.auth.models import (
    AccountStatus,
    RefreshTokenModel,
    UserModel,
    UserRole,
)
from backend.api.auth.password_security import (
    AccountLockoutPolicy,
    PasswordHasher,
    PasswordPolicy,
)

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Authentication service handling user registration, login, and token management.
    """

    def __init__(self, db: Session):
        """
        Initialize authentication service.

        Args:
            db: Database session
        """
        self.db = db
        self.password_hasher = PasswordHasher()
        self.password_policy = PasswordPolicy()
        self.lockout_policy = AccountLockoutPolicy()

    # ============================================================================
    # User Registration
    # ============================================================================

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        auto_verify: bool = False
    ) -> Tuple[Optional[UserModel], Optional[str]]:
        """
        Register a new user.

        Args:
            username: Unique username
            email: User email address
            password: Plain text password
            full_name: User's full name
            auto_verify: Auto-verify email (for testing/admin creation)

        Returns:
            Tuple of (user_model, error_message)
        """
        try:
            # Check if username already exists
            existing_user = self.db.query(UserModel).filter(
                or_(
                    UserModel.username == username.lower(),
                    UserModel.email == email.lower()
                )
            ).first()

            if existing_user:
                if existing_user.username == username.lower():
                    return None, "Username already exists"
                else:
                    return None, "Email already registered"

            # Validate password strength
            is_valid, errors = self.password_policy.validate_password_strength(password, username)
            if not is_valid:
                return None, f"Password validation failed: {'; '.join(errors)}"

            # Hash password
            password_hash = self.password_hasher.hash_password(password)

            # Create user
            user = UserModel(
                username=username.lower(),
                email=email.lower(),
                password_hash=password_hash,
                full_name=full_name,
                role=UserRole.USER.value,
                is_active=True,
                is_verified=auto_verify,
                account_status=AccountStatus.ACTIVE.value if auto_verify else AccountStatus.PENDING_VERIFICATION.value,
                password_changed_at=datetime.utcnow(),
                email_verified_at=datetime.utcnow() if auto_verify else None,
            )

            # Generate email verification token if not auto-verified
            if not auto_verify:
                user.email_verification_token = secrets.token_urlsafe(32)

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"User registered successfully: {username}")
            return user, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"User registration failed: {str(e)}")
            return None, "Registration failed due to system error"

    # ============================================================================
    # User Authentication
    # ============================================================================

    def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Tuple[Optional[UserModel], Optional[str]]:
        """
        Authenticate a user with username/email and password.

        Args:
            username: Username or email
            password: Plain text password
            ip_address: Client IP address for logging

        Returns:
            Tuple of (user_model, error_message)
        """
        try:
            # Find user by username or email
            user = self.db.query(UserModel).filter(
                or_(
                    UserModel.username == username.lower(),
                    UserModel.email == username.lower()
                )
            ).first()

            if not user:
                # Log failed attempt (user not found)
                logger.warning(f"Login attempt for non-existent user: {username} from IP: {ip_address}")
                return None, "Invalid username or password"

            # Check if account is locked
            if user.is_account_locked():
                remaining_time = self.lockout_policy.get_remaining_lockout_time(user.account_locked_until)
                minutes = remaining_time // 60
                return None, f"Account is locked. Try again in {minutes} minutes"

            # Check if password needs to be reset after lockout reset
            if self.lockout_policy.should_reset_counter(user.last_failed_login):
                user.reset_failed_login_attempts()
                self.db.commit()

            # Verify password
            if not self.password_hasher.verify_password(password, user.password_hash):
                # Increment failed login attempts
                user.increment_failed_login()

                # Check if account should be locked
                if self.lockout_policy.should_lock_account(user.failed_login_attempts):
                    lockout_duration = self.lockout_policy.get_lockout_duration(user.failed_login_attempts)
                    user.lock_account(lockout_duration)
                    logger.warning(f"Account locked due to failed attempts: {username}")

                self.db.commit()
                return None, "Invalid username or password"

            # Check if account is active
            if not user.is_active:
                return None, "Account is deactivated"

            # Check if email is verified (if required)
            if not user.is_verified:
                return None, "Email verification required. Please check your email"

            # Successful login - reset failed attempts and update login time
            user.reset_failed_login_attempts()
            user.last_login = datetime.utcnow()
            user.last_activity = datetime.utcnow()

            # Check if password hash needs update (different cost factor)
            if self.password_hasher.needs_rehash(user.password_hash):
                user.password_hash = self.password_hasher.hash_password(password)

            self.db.commit()
            self.db.refresh(user)

            logger.info(f"User authenticated successfully: {username}")
            return user, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Authentication failed: {str(e)}")
            return None, "Authentication failed due to system error"

    # ============================================================================
    # Token Management
    # ============================================================================

    def create_tokens(
        self,
        user: UserModel,
        device_info: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """
        Create access and refresh tokens for a user.

        Args:
            user: User model
            device_info: Device/browser information

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds)
        """
        # Create access token
        access_token = jwt_handler.create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            version=user.refresh_token_version
        )

        # Create refresh token
        refresh_token, jti, expires_at = jwt_handler.create_refresh_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            version=user.refresh_token_version
        )

        # Store refresh token in database
        refresh_token_model = RefreshTokenModel(
            user_id=user.id,
            token_jti=jti,
            token_family=jti,  # New family for this login
            expires_at=expires_at,
            device_info=device_info
        )

        self.db.add(refresh_token_model)
        self.db.commit()

        # Calculate expiry in seconds
        expires_in = jwt_handler.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return access_token, refresh_token, expires_in

    def refresh_tokens(
        self,
        refresh_token: str,
        device_info: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
        """
        Refresh access and refresh tokens using refresh token rotation.

        Args:
            refresh_token: Current refresh token
            device_info: Device/browser information

        Returns:
            Tuple of (access_token, new_refresh_token, expires_in, error_message)
        """
        try:
            # Decode refresh token
            payload = jwt_handler.decode_token(refresh_token, token_type="refresh")

            if not payload:
                return None, None, None, "Invalid refresh token"

            # Get stored refresh token
            stored_token = self.db.query(RefreshTokenModel).filter(
                RefreshTokenModel.token_jti == payload.jti
            ).first()

            if not stored_token:
                return None, None, None, "Refresh token not found"

            # Check if token is valid
            if not stored_token.is_valid():
                # Token has been revoked or expired
                # Check for reuse attack - if this token family has newer tokens
                newer_tokens = self.db.query(RefreshTokenModel).filter(
                    and_(
                        RefreshTokenModel.token_family == payload.token_family,
                        RefreshTokenModel.created_at > stored_token.created_at
                    )
                ).all()

                if newer_tokens:
                    # Possible token reuse attack - revoke entire family
                    self._revoke_token_family(payload.token_family, "Possible token reuse detected")
                    logger.warning(f"Possible refresh token reuse attack for user {payload.sub}")

                return None, None, None, "Refresh token is invalid or expired"

            # Get user
            user = self.db.query(UserModel).filter(
                UserModel.id == stored_token.user_id
            ).first()

            if not user or not user.is_active:
                return None, None, None, "User account is not active"

            # Check token version (allows invalidating all tokens)
            if payload.version != user.refresh_token_version:
                stored_token.revoke("Token version mismatch")
                self.db.commit()
                return None, None, None, "Refresh token has been invalidated"

            # Revoke old refresh token
            stored_token.revoke("Token rotation")

            # Create new tokens
            access_token = jwt_handler.create_access_token(
                user_id=user.id,
                username=user.username,
                role=user.role,
                version=user.refresh_token_version
            )

            # Create new refresh token with same family
            new_refresh_token, new_jti, expires_at = jwt_handler.create_refresh_token(
                user_id=user.id,
                username=user.username,
                role=user.role,
                version=user.refresh_token_version,
                token_family=payload.token_family
            )

            # Store new refresh token
            new_token_model = RefreshTokenModel(
                user_id=user.id,
                token_jti=new_jti,
                token_family=payload.token_family,
                expires_at=expires_at,
                device_info=device_info or stored_token.device_info
            )

            self.db.add(new_token_model)

            # Update user activity
            user.last_activity = datetime.utcnow()

            self.db.commit()

            expires_in = jwt_handler.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60

            return access_token, new_refresh_token, expires_in, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Token refresh failed: {str(e)}")
            return None, None, None, "Token refresh failed"

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token (logout).

        Args:
            refresh_token: Refresh token to revoke

        Returns:
            True if successful
        """
        try:
            # Decode token
            payload = jwt_handler.decode_token(refresh_token, token_type="refresh", verify_exp=False)

            if not payload:
                return False

            # Find and revoke token
            stored_token = self.db.query(RefreshTokenModel).filter(
                RefreshTokenModel.token_jti == payload.jti
            ).first()

            if stored_token:
                stored_token.revoke("User logout")
                self.db.commit()

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Token revocation failed: {str(e)}")
            return False

    def revoke_all_user_tokens(self, user_id: int) -> bool:
        """
        Revoke all refresh tokens for a user (logout from all devices).

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            # Increment user's token version to invalidate all tokens
            user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                user.refresh_token_version += 1
                self.db.commit()

            # Also revoke all stored refresh tokens
            self.db.query(RefreshTokenModel).filter(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.revoked_at.is_(None)
                )
            ).update({
                "revoked_at": datetime.utcnow(),
                "revoked_reason": "Logout from all devices"
            })

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to revoke all tokens: {str(e)}")
            return False

    def _revoke_token_family(self, token_family: str, reason: str):
        """
        Revoke all tokens in a family (security measure).

        Args:
            token_family: Token family ID
            reason: Revocation reason
        """
        self.db.query(RefreshTokenModel).filter(
            and_(
                RefreshTokenModel.token_family == token_family,
                RefreshTokenModel.revoked_at.is_(None)
            )
        ).update({
            "revoked_at": datetime.utcnow(),
            "revoked_reason": reason
        })

    # ============================================================================
    # Password Management
    # ============================================================================

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Change user password.

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            Tuple of (success, error_message)
        """
        try:
            user = self.db.query(UserModel).filter(UserModel.id == user_id).first()

            if not user:
                return False, "User not found"

            # Verify current password
            if not self.password_hasher.verify_password(current_password, user.password_hash):
                return False, "Current password is incorrect"

            # Check password age
            can_change, message = self.password_policy.check_password_age(user.password_changed_at)
            if not can_change:
                return False, message

            # Validate new password
            is_valid, errors = self.password_policy.validate_password_strength(new_password, user.username)
            if not is_valid:
                return False, f"Password validation failed: {'; '.join(errors)}"

            # Hash and update password
            user.password_hash = self.password_hasher.hash_password(new_password)
            user.password_changed_at = datetime.utcnow()

            # Invalidate all tokens (force re-login)
            user.refresh_token_version += 1

            self.db.commit()

            return True, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Password change failed: {str(e)}")
            return False, "Password change failed"

    def request_password_reset(self, email: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Request password reset token.

        Args:
            email: User email address

        Returns:
            Tuple of (reset_token, error_message)
        """
        try:
            user = self.db.query(UserModel).filter(
                UserModel.email == email.lower()
            ).first()

            if not user:
                # Don't reveal if email exists
                return None, None

            # Generate reset token
            reset_token = jwt_handler.create_password_reset_token(user.id, user.email)

            # Store token hash
            user.password_reset_token = secrets.token_urlsafe(32)
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)

            self.db.commit()

            return reset_token, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Password reset request failed: {str(e)}")
            return None, "Password reset request failed"

    def reset_password(
        self,
        token: str,
        new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Reset password using reset token.

        Args:
            token: Password reset token
            new_password: New password

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Decode token
            payload = jwt_handler.decode_verification_token(token, "password_reset")

            if not payload:
                return False, "Invalid or expired reset token"

            user = self.db.query(UserModel).filter(
                UserModel.id == int(payload["sub"])
            ).first()

            if not user:
                return False, "Invalid reset token"

            # Check if token is still valid
            if not user.password_reset_expires or datetime.utcnow() > user.password_reset_expires:
                return False, "Reset token has expired"

            # Validate new password
            is_valid, errors = self.password_policy.validate_password_strength(new_password, user.username)
            if not is_valid:
                return False, f"Password validation failed: {'; '.join(errors)}"

            # Update password
            user.password_hash = self.password_hasher.hash_password(new_password)
            user.password_changed_at = datetime.utcnow()
            user.password_reset_token = None
            user.password_reset_expires = None

            # Invalidate all tokens
            user.refresh_token_version += 1

            # Unlock account if it was locked
            if user.is_account_locked():
                user.unlock_account()

            self.db.commit()

            return True, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Password reset failed: {str(e)}")
            return False, "Password reset failed"

    # ============================================================================
    # Email Verification
    # ============================================================================

    def verify_email(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Verify user email address.

        Args:
            token: Email verification token

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Decode token
            payload = jwt_handler.decode_verification_token(token, "email_verification")

            if not payload:
                return False, "Invalid or expired verification token"

            user = self.db.query(UserModel).filter(
                UserModel.id == int(payload["sub"])
            ).first()

            if not user:
                return False, "Invalid verification token"

            if user.is_verified:
                return True, None  # Already verified

            # Verify email
            user.is_verified = True
            user.email_verified_at = datetime.utcnow()
            user.account_status = AccountStatus.ACTIVE.value
            user.email_verification_token = None

            self.db.commit()

            return True, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Email verification failed: {str(e)}")
            return False, "Email verification failed"

    # ============================================================================
    # User Management
    # ============================================================================

    def get_user_by_id(self, user_id: int) -> Optional[UserModel]:
        """Get user by ID."""
        return self.db.query(UserModel).filter(UserModel.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[UserModel]:
        """Get user by username."""
        return self.db.query(UserModel).filter(
            UserModel.username == username.lower()
        ).first()

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email."""
        return self.db.query(UserModel).filter(
            UserModel.email == email.lower()
        ).first()

    def update_user_activity(self, user_id: int):
        """Update user's last activity timestamp."""
        try:
            user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                user.last_activity = datetime.utcnow()
                self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update user activity: {str(e)}")

    def log_login_attempt(self, login_attempt: 'LoginAttemptLog') -> bool:
        """
        Log a login attempt for audit and security monitoring.

        Args:
            login_attempt: Login attempt information

        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # For now, just log to the application log
            # In a production system, you might store this in a separate audit table
            log_message = (
                f"Login attempt - Username: {login_attempt.username}, "
                f"IP: {login_attempt.ip_address}, "
                f"Success: {login_attempt.success}, "
                f"User Agent: {login_attempt.user_agent}"
            )

            if login_attempt.success:
                logger.info(f"[AUDIT] {log_message}")
            else:
                logger.warning(f"[SECURITY] Failed {log_message}, Reason: {login_attempt.failure_reason}")

            # TODO: In production, store in dedicated audit log table
            # audit_record = LoginAuditModel(**login_attempt.dict())
            # self.db.add(audit_record)
            # self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to log login attempt: {e}")
            return False

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired refresh tokens.

        Returns:
            Number of tokens cleaned up
        """
        try:
            expired_tokens = self.db.query(RefreshTokenModel).filter(
                and_(
                    RefreshTokenModel.expires_at < datetime.utcnow(),
                    RefreshTokenModel.revoked_at.is_(None)
                )
            )

            count = expired_tokens.count()
            expired_tokens.delete()
            self.db.commit()

            return count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Token cleanup failed: {str(e)}")
            return 0