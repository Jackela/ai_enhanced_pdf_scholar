"""
Authentication Routes
API endpoints for user authentication and management.
"""

import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.api.auth.constants import BEARER_TOKEN_SCHEME, TokenType
from backend.api.auth.dependencies import (
    get_current_user,
    get_optional_user,
)
from backend.api.auth.jwt_handler import jwt_handler
from backend.api.auth.models import (
    EmailVerification,
    LoginAttemptLog,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserModel,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)
from backend.api.auth.service import AuthenticationService
from backend.api.dependencies import get_db
from backend.api.models import BaseResponse

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, request: Request, db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user account.

    - Username must be unique and 3-50 characters
    - Email must be valid and unique
    - Password must meet security requirements
    - Email verification will be required
    """
    auth_service = AuthenticationService(db)

    # Register user
    user, error = auth_service.register_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        auto_verify=False,  # Require email verification
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Send verification email
    from backend.services.email_service import email_service

    try:
        email_sent = email_service.send_verification_email(
            email=user.email,
            username=user.username,
            verification_token=user.email_verification_token,
            base_url=request.base_url.replace(path="/").rstrip("/"),
        )
        if not email_sent:
            logger.warning(f"Failed to send verification email to {user.email}")
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {e}")
        # Don't fail registration if email sending fails

    logger.info(f"New user registered: {user.username} from IP: {request.client.host}")

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and receive access tokens.

    - Returns JWT access token (15 min) and refresh token (7 days)
    - Tokens use RS256 asymmetric signing
    - Failed attempts may result in account lockout
    """
    auth_service = AuthenticationService(db)

    # Get client IP for logging
    client_ip = request.client.host
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in request.headers:
        client_ip = request.headers["x-real-ip"]

    # Get user agent
    user_agent = request.headers.get("user-agent", "Unknown")

    # Authenticate user
    user, error = auth_service.authenticate_user(
        username=credentials.username,
        password=credentials.password,
        ip_address=client_ip,
    )

    # Log attempt
    log_entry = LoginAttemptLog(
        username=credentials.username,
        ip_address=client_ip,
        user_agent=user_agent,
        success=user is not None,
        failure_reason=error,
    )
    # Store login attempt for audit and security monitoring
    try:
        auth_service.log_login_attempt(log_entry)
        logger.debug(
            f"Logged login attempt for user {credentials.username} from {client_ip}"
        )
    except Exception as e:
        logger.error(f"Failed to log login attempt: {e}")
        # Don't fail authentication if logging fails

    if error:
        logger.warning(
            f"Failed login attempt for {credentials.username} from {client_ip}: {error}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
        )

    # Create tokens
    device_info = f"{user_agent} | {client_ip}"
    access_token, refresh_token, expires_in = auth_service.create_tokens(
        user, device_info
    )

    # Set secure cookie if remember_me is true
    if credentials.remember_me:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=7 * 24 * 60 * 60,  # 7 days
            httponly=True,
            secure=True,  # HTTPS only
            samesite="lax",
            path="/api/auth",
        )

    logger.info(f"User logged in: {user.username} from {client_ip}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=BEARER_TOKEN_SCHEME,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    token_data: TokenRefresh, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    - Implements token rotation for security
    - Old refresh token is revoked
    - Returns new access and refresh tokens
    """
    auth_service = AuthenticationService(db)

    # Get device info
    user_agent = request.headers.get("user-agent", "Unknown")
    client_ip = request.client.host
    device_info = f"{user_agent} | {client_ip}"

    # Refresh tokens
    access_token, refresh_token, expires_in, error = auth_service.refresh_tokens(
        refresh_token=token_data.refresh_token, device_info=device_info
    )

    if error:
        logger.warning(f"Token refresh failed from {client_ip}: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=BEARER_TOKEN_SCHEME,
        expires_in=expires_in,
    )


@router.post("/logout", response_model=BaseResponse)
async def logout(
    token_data: TokenRefresh | None = None,
    response: Response = None,
    user: UserModel | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> BaseResponse:
    """
    Logout user by revoking refresh token.

    - Revokes the provided refresh token
    - Clears authentication cookies
    - Access token remains valid until expiry
    """
    auth_service = AuthenticationService(db)

    # Revoke refresh token if provided
    if token_data and token_data.refresh_token:
        auth_service.revoke_refresh_token(token_data.refresh_token)

    # Clear cookies
    if response:
        response.delete_cookie(key="refresh_token", path="/api/auth")
        response.delete_cookie(key="access_token", path="/")

    if user:
        logger.info(f"User logged out: {user.username}")

    return BaseResponse(success=True, message="Logged out successfully")


@router.post("/logout-all", response_model=BaseResponse)
async def logout_all_devices(
    user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)
) -> BaseResponse:
    """
    Logout from all devices by invalidating all tokens.

    - Revokes all refresh tokens for the user
    - Increments token version to invalidate access tokens
    - Forces re-authentication on all devices
    """
    auth_service = AuthenticationService(db)

    # Revoke all tokens
    success = auth_service.revoke_all_user_tokens(user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout from all devices",
        )

    logger.info(f"User logged out from all devices: {user.username}")

    return BaseResponse(
        success=True, message="Logged out from all devices successfully"
    )


@router.post("/password-reset", response_model=BaseResponse)
async def request_password_reset(
    reset_data: PasswordReset, request: Request, db: Session = Depends(get_db)
) -> BaseResponse:
    """
    Request password reset token.

    - Sends reset token to user's email
    - Token is valid for 1 hour
    - Does not reveal if email exists (security)
    """
    auth_service = AuthenticationService(db)

    # Request reset token
    reset_token, error = auth_service.request_password_reset(reset_data.email)

    if reset_token:
        # Send password reset email
        from backend.services.email_service import email_service

        try:
            user = auth_service.get_user_by_email(reset_data.email)
            if user:
                email_sent = email_service.send_password_reset_email(
                    email=reset_data.email,
                    username=user.username,
                    reset_token=reset_token,
                    base_url=str(request.base_url).rstrip("/"),
                )
                if email_sent:
                    logger.info(f"Password reset email sent to: {reset_data.email}")
                else:
                    logger.warning(
                        f"Failed to send password reset email to: {reset_data.email}"
                    )
        except Exception as e:
            logger.error(
                f"Error sending password reset email to {reset_data.email}: {e}"
            )
            # Don't fail the request if email sending fails

    # Always return success (don't reveal if email exists)
    return BaseResponse(
        success=True, message="If the email exists, a password reset link has been sent"
    )


@router.post("/password-reset-confirm", response_model=BaseResponse)
async def reset_password(
    reset_data: PasswordResetConfirm, db: Session = Depends(get_db)
) -> BaseResponse:
    """
    Reset password using reset token.

    - Validates reset token
    - Updates password
    - Invalidates all existing tokens
    - Unlocks account if it was locked
    """
    auth_service = AuthenticationService(db)

    # Reset password
    success, error = auth_service.reset_password(
        token=reset_data.token, new_password=reset_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Password reset failed",
        )

    logger.info("Password reset completed successfully")

    return BaseResponse(success=True, message="Password reset successfully")


@router.post("/verify-email", response_model=BaseResponse)
async def verify_email(
    verification_data: EmailVerification, db: Session = Depends(get_db)
) -> BaseResponse:
    """
    Verify email address using verification token.

    - Validates verification token
    - Marks email as verified
    - Activates user account
    """
    auth_service = AuthenticationService(db)

    # Verify email
    success, error = auth_service.verify_email(verification_data.token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Email verification failed",
        )

    logger.info("Email verified successfully")

    return BaseResponse(success=True, message="Email verified successfully")


# ============================================================================
# Protected Endpoints (Authentication Required)
# ============================================================================


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    user: UserModel = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Get current user's profile information.

    - Returns detailed user profile
    - Requires valid access token
    """
    return UserProfileResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    update_data: UserUpdate,
    request: Request,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Update current user's profile.

    - Updates user profile information
    - Cannot change username or role
    - Email change may require re-verification
    """
    # Update allowed fields
    if update_data.full_name is not None:
        user.full_name = update_data.full_name

    if update_data.email is not None and update_data.email != user.email:
        # Check if email is already taken
        existing = (
            db.query(UserModel)
            .filter(UserModel.email == update_data.email.lower())
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Update email (may require re-verification)
        user.email = update_data.email.lower()
        user.is_verified = False  # Require re-verification
        user.email_verification_token = secrets.token_urlsafe(32)

        # Send new verification email for the updated email
        from backend.services.email_service import email_service

        try:
            email_sent = email_service.send_verification_email(
                email=user.email,
                username=user.username,
                verification_token=user.email_verification_token,
                base_url=str(request.base_url).rstrip("/"),
            )
            if email_sent:
                logger.info(
                    f"New verification email sent to updated address: {user.email}"
                )
            else:
                logger.warning(
                    f"Failed to send verification email to updated address: {user.email}"
                )
        except Exception as e:
            logger.error(
                f"Error sending verification email to updated address {user.email}: {e}"
            )

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    logger.info(f"User profile updated: {user.username}")

    return UserResponse.model_validate(user)


@router.post("/change-password", response_model=BaseResponse)
async def change_password(
    password_data: PasswordChange,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BaseResponse:
    """
    Change current user's password.

    - Requires current password verification
    - Validates new password strength
    - Invalidates all existing tokens
    """
    auth_service = AuthenticationService(db)

    # Change password
    success, error = auth_service.change_password(
        user_id=user.id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Password change failed",
        )

    logger.info(f"Password changed for user: {user.username}")

    return BaseResponse(
        success=True, message="Password changed successfully. Please login again."
    )


@router.get("/sessions", response_model=list)
async def get_active_sessions(
    request: Request,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """
    Get list of active sessions (refresh tokens).

    - Shows all active refresh tokens
    - Includes device information
    - Can be used to manage logged-in devices
    - Marks current session for identification
    """

    from backend.api.auth.jwt_handler import jwt_handler
    from backend.api.auth.models import RefreshTokenModel

    # Extract current token to identify current session
    current_token_id = None
    try:
        # Get token from Authorization header or cookie
        authorization = request.headers.get("authorization", "")
        access_token_cookie = request.cookies.get("access_token")

        token = None
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        elif access_token_cookie:
            token = access_token_cookie

        if token:
            payload = jwt_handler.decode_token(token, token_type=TokenType.ACCESS)
            if payload and hasattr(payload, "jti"):
                # Use JTI (JWT ID) to correlate with refresh token
                # This assumes the access token's JTI matches the refresh token ID
                current_token_id = payload.jti
    except Exception as e:
        logger.debug(f"Could not identify current session: {e}")

    # Get active refresh tokens
    tokens = (
        db.query(RefreshTokenModel)
        .filter(
            RefreshTokenModel.user_id == user.id,
            RefreshTokenModel.revoked_at.is_(None),
            RefreshTokenModel.expires_at > datetime.utcnow(),
        )
        .order_by(RefreshTokenModel.created_at.desc())
        .all()
    )

    sessions = []
    for token in tokens:
        # Try to identify current session by matching token ID or recent activity
        is_current = (
            current_token_id is not None and str(token.id) == str(current_token_id)
        ) or (
            # Fallback: most recently created token if no JTI match
            current_token_id is None and token == tokens[0] if tokens else False
        )

        sessions.append(
            {
                "id": token.id,
                "device_info": token.device_info,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat(),
                "last_used": token.last_used.isoformat()
                if hasattr(token, "last_used") and token.last_used
                else None,
                "is_current": is_current,
            }
        )

    return sessions


@router.delete("/sessions/{session_id}", response_model=BaseResponse)
async def revoke_session(
    session_id: int,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BaseResponse:
    """
    Revoke a specific session (refresh token).

    - Revokes the specified refresh token
    - Can be used to logout specific devices
    """
    from backend.api.auth.models import RefreshTokenModel

    # Find and revoke token
    token = (
        db.query(RefreshTokenModel)
        .filter(
            RefreshTokenModel.id == session_id, RefreshTokenModel.user_id == user.id
        )
        .first()
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    token.revoke("Manual revocation by user")
    db.commit()

    logger.info(f"Session revoked for user: {user.username}, session: {session_id}")

    return BaseResponse(success=True, message="Session revoked successfully")


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health", response_model=BaseResponse)
async def auth_health_check() -> BaseResponse:
    """
    Check authentication service health.

    - Verifies JWT keys are available
    - Returns service status
    """
    try:
        # Check if JWT keys exist
        jwt_handler.config.ensure_keys_exist()

        return BaseResponse(success=True, message="Authentication service is healthy")
    except Exception as e:
        logger.error(f"Authentication health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unhealthy",
        ) from e
