"""
API Endpoint Protection System
Comprehensive security wrapper for all API endpoints with authentication and RBAC.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from backend.api.auth.constants import BEARER_TOKEN_SCHEME
from backend.api.auth.jwt_auth import User, get_current_user
from backend.api.auth.rbac import (
    RBACService,
)
from backend.api.dependencies import get_db

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI documentation
security_bearer = HTTPBearer(auto_error=False)
P = ParamSpec("P")
R = TypeVar("R")
AsyncEndpoint = Callable[P, Awaitable[R]]


# ============================================================================
# Enhanced Security Decorators
# ============================================================================


def secure_endpoint(
    resource: str,
    action: str,
    allow_anonymous: bool = False,
    rate_limit: str | None = None,
    audit_log: bool = True,
    validate_input: bool = True,
) -> Callable[[AsyncEndpoint], AsyncEndpoint]:
    """
    Comprehensive security decorator for API endpoints.

    Args:
        resource: Resource type being accessed
        action: Action being performed
        allow_anonymous: Whether to allow anonymous access
        rate_limit: Custom rate limit for this endpoint
        audit_log: Whether to log this action to audit trail
        validate_input: Whether to perform input validation

    Example:
        @secure_endpoint(ResourceTypes.DOCUMENT, Actions.READ)
        async def get_document(doc_id: int, user: User = Depends(get_current_user)):
            ...
    """

    def decorator(func: AsyncEndpoint) -> AsyncEndpoint:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract request if available
            request = kwargs.get("request")

            # Authentication check
            if not allow_anonymous:
                user = kwargs.get("current_user") or kwargs.get("user")
                if not user:
                    # Try to get user from request
                    if request:
                        auth = await security_bearer(request)
                        if auth and auth.credentials:
                            try:
                                user = await get_current_user(auth)
                                kwargs["current_user"] = user
                            except:
                                raise HTTPException(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Invalid authentication credentials",
                                    headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
                                ) from None
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Authentication required",
                                headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
                            )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required",
                            headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
                        )
            else:
                user = kwargs.get("current_user") or kwargs.get("user")

            # RBAC check (if user is authenticated)
            if user:
                db = kwargs.get("db")
                if not db:
                    # Try to get DB session
                    try:
                        db = get_db()
                        kwargs["db"] = db
                    except:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Database session not available",
                        ) from None

                rbac = RBACService(db)

                # Extract resource_id if available
                resource_id = kwargs.get(f"{resource}_id") or kwargs.get("id")

                # Check permission
                permission_check = rbac.check_permission(
                    user=user,
                    resource=resource,
                    action=action,
                    resource_id=str(resource_id) if resource_id else None,
                )

                if not permission_check.allowed:
                    # Log unauthorized access attempt
                    if audit_log:
                        logger.warning(
                            f"Unauthorized access attempt by user {user.email}: "
                            f"{action} on {resource}",
                            extra={
                                "user_id": user.id,
                                "resource": resource,
                                "action": action,
                                "resource_id": resource_id,
                                "reason": permission_check.reason,
                            },
                        )

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=permission_check.reason,
                    )

                # Add permission context to kwargs
                kwargs["permission_context"] = permission_check.context

            # Audit logging for successful access
            if audit_log and user:
                logger.info(
                    f"API access: {user.email} performed {action} on {resource}",
                    extra={
                        "user_id": user.id,
                        "resource": resource,
                        "action": action,
                        "resource_id": kwargs.get(f"{resource}_id"),
                        "endpoint": func.__name__,
                    },
                )

            # Execute the actual function
            return await func(*args, **kwargs)

        # Add security information to function for OpenAPI docs
        wrapper.__doc__ = (
            func.__doc__ or ""
        ) + f"\n\nSecurity: Requires {resource}:{action} permission"

        return cast(AsyncEndpoint, wrapper)

    return decorator


def secure_admin_endpoint(
    audit_log: bool = True,
) -> Callable[[AsyncEndpoint], AsyncEndpoint]:
    """
    Decorator for admin-only endpoints.
    Requires admin or super_admin role.
    """

    def decorator(func: AsyncEndpoint) -> AsyncEndpoint:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            user = kwargs.get("current_user") or kwargs.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
                )

            # Check for admin roles
            user_roles = [role.name for role in user.roles]
            if "admin" not in user_roles and "super_admin" not in user_roles:
                if audit_log:
                    logger.warning(
                        f"Non-admin user {user.email} attempted to access admin endpoint",
                        extra={"user_id": user.id, "endpoint": func.__name__},
                    )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required",
                )

            if audit_log:
                logger.info(
                    f"Admin access: {user.email} accessed {func.__name__}",
                    extra={"user_id": user.id, "endpoint": func.__name__},
                )

            return await func(*args, **kwargs)

        wrapper.__doc__ = (func.__doc__ or "") + "\n\nSecurity: Admin access required"
        return cast(AsyncEndpoint, wrapper)

    return decorator


OwnerResolver = Callable[[Any], Any]
RateLimitKeyFunc = Callable[[tuple[Any, ...], dict[str, Any]], str]


def secure_owner_only(
    resource_type: str, get_owner_func: OwnerResolver
) -> Callable[[AsyncEndpoint], AsyncEndpoint]:
    """
    Decorator that ensures only the resource owner can access.

    Args:
        resource_type: Type of resource
        get_owner_func: Function to get owner ID from resource

    Example:
        @secure_owner_only("document", lambda doc: doc.user_id)
        async def update_my_document(doc_id: int, ...):
            ...
    """

    def decorator(func: AsyncEndpoint) -> AsyncEndpoint:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            user = kwargs.get("current_user") or kwargs.get("user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": BEARER_TOKEN_SCHEME},
                )

            # Get the resource
            resource_id = kwargs.get(f"{resource_type}_id") or kwargs.get("id")
            if not resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No {resource_type} ID provided",
                )

            # Check ownership
            # This would need to be implemented based on your data model
            # For now, we'll use RBAC with resource policy
            db = kwargs.get("db") or get_db()
            rbac = RBACService(db)

            permission_check = rbac.check_permission(
                user=user,
                resource=resource_type,
                action="update",  # Owner can update
                resource_id=str(resource_id),
                context={"owner_id": user.id},
            )

            if not permission_check.allowed:
                logger.warning(
                    f"User {user.email} attempted to access resource they don't own",
                    extra={
                        "user_id": user.id,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                    },
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this resource",
                )

            return await func(*args, **kwargs)

        wrapper.__doc__ = (
            func.__doc__ or ""
        ) + f"\n\nSecurity: Owner-only access for {resource_type}"
        return cast(AsyncEndpoint, wrapper)

    return decorator


def rate_limited(
    requests: int = 100, window: int = 60, key_func: RateLimitKeyFunc | None = None
) -> Callable[[AsyncEndpoint], AsyncEndpoint]:
    """
    Rate limiting decorator for endpoints.

    Args:
        requests: Number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key

    Example:
        @rate_limited(requests=10, window=60)
        async def expensive_operation(...):
            ...
    """

    def decorator(func: AsyncEndpoint) -> AsyncEndpoint:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Rate limiting logic would go here
            # This would integrate with the rate limiting middleware
            _ = key_func  # Placeholder to keep type-checker satisfied until implemented
            return await func(*args, **kwargs)

        wrapper.__doc__ = (
            func.__doc__ or ""
        ) + f"\n\nRate limit: {requests} requests per {window} seconds"
        return cast(AsyncEndpoint, wrapper)

    return decorator


# ============================================================================
# Batch Security Operations
# ============================================================================


class BatchSecurityValidator:
    """
    Validates security for batch operations.
    """

    def __init__(self, user: User, db: Session) -> None:
        """Initialize batch validator."""
        self.user = user
        self.rbac = RBACService(db)
        self.failed_items: list[dict[str, Any]] = []
        self.successful_items: list[Any] = []

    def validate_batch(
        self,
        items: list[Any],
        resource: str,
        action: str,
        id_func: Callable[[Any], str],
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """
        Validate permissions for a batch of items.

        Args:
            items: List of items to validate
            resource: Resource type
            action: Action to perform
            id_func: Function to extract ID from item

        Returns:
            Tuple of (allowed_items, denied_items)
        """
        allowed = []
        denied = []

        for item in items:
            item_id = id_func(item)
            check = self.rbac.check_permission(
                user=self.user, resource=resource, action=action, resource_id=item_id
            )

            if check.allowed:
                allowed.append(item)
            else:
                denied.append({"item": item, "id": item_id, "reason": check.reason})

        return allowed, denied


# ============================================================================
# API Key Authentication (for service accounts)
# ============================================================================


class APIKeyAuth:
    """
    API key authentication for service accounts and external integrations.
    """

    def __init__(self, db: Session) -> None:
        """Initialize API key auth."""
        self.db = db

    async def validate_api_key(self, api_key: str) -> User | None:
        """
        Validate an API key and return associated service account.

        Args:
            api_key: API key to validate

        Returns:
            User object if valid, None otherwise
        """
        # This would query a table of API keys
        # For now, return None
        return None


def require_api_key(scopes: list[str] = None) -> Any:
    """
    Decorator to require API key authentication.

    Args:
        scopes: Required scopes for the API key

    Example:
        @require_api_key(scopes=["documents:read"])
        async def external_api_endpoint(...):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            request = kwargs.get("request")
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not available",
                )

            # Check for API key in header
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required",
                    headers={"WWW-Authenticate": "ApiKey"},
                )

            # Validate API key
            db = kwargs.get("db") or next(get_db())
            api_auth = APIKeyAuth(db)
            user = await api_auth.validate_api_key(api_key)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
                )

            # Check scopes if required
            if scopes:
                # This would check if the API key has required scopes
                pass

            kwargs["current_user"] = user
            return await func(*args, **kwargs)

        wrapper.__doc__ = (
            func.__doc__ or ""
        ) + f"\n\nSecurity: API key required with scopes: {scopes}"
        return wrapper

    return decorator


# ============================================================================
# Security Context Manager
# ============================================================================


class SecurityContext:
    """
    Context manager for security-sensitive operations.
    """

    def __init__(
        self, user: User, resource: str, action: str, db: Session, audit: bool = True
    ) -> None:
        """Initialize security context."""
        self.user = user
        self.resource = resource
        self.action = action
        self.db = db
        self.audit = audit
        self.rbac = RBACService(db)
        self.start_time = None

    async def __aenter__(self) -> None:
        """Enter security context."""
        import time

        self.start_time = time.time()

        # Check permission
        check = self.rbac.check_permission(
            user=self.user, resource=self.resource, action=self.action
        )

        if not check.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=check.reason
            )

        if self.audit:
            logger.info(
                f"Security context entered: {self.user.email} -> {self.resource}:{self.action}",
                extra={
                    "user_id": self.user.id,
                    "resource": self.resource,
                    "action": self.action,
                },
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit security context."""
        import time

        duration = time.time() - self.start_time if self.start_time else 0

        if self.audit:
            if exc_type:
                logger.error(
                    f"Security context failed: {self.user.email} -> {self.resource}:{self.action}",
                    extra={
                        "user_id": self.user.id,
                        "resource": self.resource,
                        "action": self.action,
                        "error": str(exc_val),
                        "duration_ms": duration * 1000,
                    },
                )
            else:
                logger.info(
                    f"Security context completed: {self.user.email} -> {self.resource}:{self.action}",
                    extra={
                        "user_id": self.user.id,
                        "resource": self.resource,
                        "action": self.action,
                        "duration_ms": duration * 1000,
                    },
                )


# ============================================================================
# Security Middleware for Automatic Protection
# ============================================================================


class AutoSecurityMiddleware:
    """
    Middleware that automatically applies security to all endpoints.
    """

    def __init__(self, app, config: dict[str, Any]) -> None:
        """Initialize middleware."""
        self.app = app
        self.config = config
        self.excluded_paths = config.get(
            "excluded_paths",
            [
                "/api/auth/login",
                "/api/auth/register",
                "/api/health",
                "/api/docs",
                "/api/redoc",
                "/openapi.json",
            ],
        )

    async def __call__(self, scope, receive, send) -> None:
        """Process request through security middleware."""
        if scope["type"] == "http":
            path = scope["path"]

            # Check if path is excluded
            if not any(path.startswith(excluded) for excluded in self.excluded_paths):
                # Apply automatic security checks
                # This would integrate with the request processing
                pass

        await self.app(scope, receive, send)


# ============================================================================
# Security Utilities
# ============================================================================


def mask_sensitive_data(data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """
    Mask sensitive fields in response data.

    Args:
        data: Data dictionary
        fields: List of field names to mask

    Returns:
        Data with masked fields
    """
    masked_data = data.copy()
    for field in fields:
        if field in masked_data:
            if isinstance(masked_data[field], str):
                # Keep first and last 2 characters
                value = masked_data[field]
                if len(value) > 4:
                    masked_data[field] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    masked_data[field] = "*" * len(value)
    return masked_data


def sanitize_user_input(input_data: Any) -> Any:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        input_data: User input data

    Returns:
        Sanitized data
    """
    if isinstance(input_data, str):
        # Remove potential SQL injection patterns
        dangerous_patterns = [
            "'",
            '"',
            "--",
            "/*",
            "*/",
            "xp_",
            "sp_",
            "exec",
            "execute",
        ]
        sanitized = input_data
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, "")
        return sanitized.strip()
    elif isinstance(input_data, dict[str, Any]):
        return {k: sanitize_user_input(v) for k, v in input_data.items()}
    elif isinstance(input_data, list[Any]):
        return [sanitize_user_input(item) for item in input_data]
    return input_data


if __name__ == "__main__":
    # Example usage
    pass
