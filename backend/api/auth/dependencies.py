"""
Authentication Dependencies
FastAPI dependency injection for authentication and authorization.
"""

import logging

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.api.auth.jwt_handler import jwt_handler
from backend.api.auth.models import UserModel, UserRole
from backend.api.auth.service import AuthenticationService
from backend.api.dependencies import get_db

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for Authorization header
security = HTTPBearer(auto_error=False)


class AuthenticationRequired:
    """
    Dependency for requiring authentication.
    Can be customized with specific role requirements.
    """

    def __init__(
        self,
        required_roles: list[UserRole] | None = None,
        allow_unverified: bool = False
    ):
        """
        Initialize authentication requirement.

        Args:
            required_roles: List of allowed roles (None = any authenticated user)
            allow_unverified: Allow unverified email addresses
        """
        self.required_roles = required_roles
        self.allow_unverified = allow_unverified

    async def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
        access_token_cookie: str | None = Cookie(None, alias="access_token"),
        db: Session = Depends(get_db)
    ) -> UserModel:
        """
        Validate authentication and return current user.

        Args:
            request: FastAPI request object
            credentials: Authorization header credentials
            access_token_cookie: Access token from cookie (fallback)
            db: Database session

        Returns:
            Authenticated user model

        Raises:
            HTTPException: If authentication fails
        """
        # Extract token from header or cookie
        token = None

        if credentials and credentials.credentials:
            token = credentials.credentials
        elif access_token_cookie:
            token = access_token_cookie

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Decode and validate token
        payload = jwt_handler.decode_token(token, token_type="access")

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from database
        auth_service = AuthenticationService(db)
        user = auth_service.get_user_by_id(int(payload.sub))

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        # Check if user is locked
        if user.is_account_locked():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is locked",
            )

        # Check email verification requirement
        if not self.allow_unverified and not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email verification required",
            )

        # Check token version (allows invalidating all tokens)
        if payload.version != user.refresh_token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been invalidated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check role requirements
        if self.required_roles:
            user_role = UserRole(user.role)
            if user_role not in self.required_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {[r.value for r in self.required_roles]}",
                )

        # Update user activity
        auth_service.update_user_activity(user.id)

        # Store user in request state for logging/auditing
        request.state.current_user = user

        return user


# Convenience dependencies for common use cases

def get_current_user(
    user: UserModel = Depends(AuthenticationRequired())
) -> UserModel:
    """
    Get current authenticated user.

    Returns:
        Authenticated user model
    """
    return user


def get_current_active_user(
    user: UserModel = Depends(AuthenticationRequired(allow_unverified=False))
) -> UserModel:
    """
    Get current authenticated and verified user.

    Returns:
        Authenticated and verified user model
    """
    return user


def get_admin_user(
    user: UserModel = Depends(AuthenticationRequired(required_roles=[UserRole.ADMIN]))
) -> UserModel:
    """
    Get current authenticated admin user.

    Returns:
        Authenticated admin user model
    """
    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token_cookie: str | None = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db)
) -> UserModel | None:
    """
    Get current user if authenticated, None otherwise.
    Used for endpoints that have different behavior for authenticated vs anonymous users.

    Returns:
        User model if authenticated, None otherwise
    """
    # Extract token from header or cookie
    token = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        return None

    # Try to decode token
    payload = jwt_handler.decode_token(token, token_type="access")

    if not payload:
        return None

    # Get user from database
    auth_service = AuthenticationService(db)
    user = auth_service.get_user_by_id(int(payload.sub))

    if not user or not user.is_active or user.is_account_locked():
        return None

    # Check token version
    if payload.version != user.refresh_token_version:
        return None

    # Update user activity
    auth_service.update_user_activity(user.id)

    # Store user in request state
    request.state.current_user = user

    return user


class RateLimitByUser:
    """
    Rate limiting dependency that uses user ID if authenticated.
    Falls back to IP address for anonymous users.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        user: UserModel | None = Depends(get_optional_user)
    ) -> str:
        """
        Get rate limit key for the current request.

        Args:
            request: FastAPI request
            user: Optional authenticated user

        Returns:
            Rate limit key (user_id or IP address)
        """
        if user:
            return f"user:{user.id}"
        else:
            # Get client IP address
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
            elif "x-real-ip" in request.headers:
                client_ip = request.headers["x-real-ip"]

            return f"ip:{client_ip}"


class PermissionChecker:
    """
    Fine-grained permission checking for resources.
    """

    def __init__(self, resource_type: str, action: str):
        """
        Initialize permission checker.

        Args:
            resource_type: Type of resource (e.g., "document", "user")
            action: Action to perform (e.g., "read", "write", "delete")
        """
        self.resource_type = resource_type
        self.action = action

    async def __call__(
        self,
        user: UserModel = Depends(get_current_user),
        resource_id: int | None = None
    ) -> bool:
        """
        Check if user has permission for the action.

        Args:
            user: Current authenticated user
            resource_id: Optional resource ID for ownership checks

        Returns:
            True if permitted

        Raises:
            HTTPException: If permission denied
        """
        user_role = UserRole(user.role)

        # Admin has all permissions
        if user_role == UserRole.ADMIN:
            return True

        # Define permission matrix
        permissions = {
            UserRole.USER: {
                "document": ["read", "write", "delete"],  # Own documents only
                "user": ["read"],  # Own profile only
                "system": ["read"],
            },
            UserRole.VIEWER: {
                "document": ["read"],
                "user": ["read"],  # Own profile only
                "system": ["read"],
            },
            UserRole.MODERATOR: {
                "document": ["read", "write"],
                "user": ["read"],
                "system": ["read"],
            },
        }

        # Check basic permission
        allowed_actions = permissions.get(user_role, {}).get(self.resource_type, [])

        if self.action not in allowed_actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.action} on {self.resource_type}",
            )

        # Additional ownership checks could be added here
        # For example, checking if user owns the document with resource_id

        return True


# Decorator for protecting routes
def require_auth(
    roles: list[UserRole] | None = None,
    allow_unverified: bool = False
):
    """
    Decorator for protecting FastAPI routes.

    Args:
        roles: Required roles
        allow_unverified: Allow unverified users

    Usage:
        @app.get("/protected")
        @require_auth(roles=[UserRole.ADMIN])
        async def protected_route(user: UserModel = Depends(get_current_user)):
            return {"message": f"Hello {user.username}"}
    """
    def decorator(func):
        # This is a placeholder for route decoration logic
        # In practice, use Dependencies directly in route definitions
        func._auth_required = True
        func._required_roles = roles
        func._allow_unverified = allow_unverified
        return func
    return decorator
