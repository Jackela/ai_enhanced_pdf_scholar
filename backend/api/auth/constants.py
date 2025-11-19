"""Authentication constants and enums used across the auth subsystem."""

from __future__ import annotations

from enum import StrEnum


class TokenType(StrEnum):
    """Supported token types for JWT operations."""

    ACCESS = "access"
    REFRESH = "refresh"
    # False positive: static token descriptors, not secrets.
    PASSWORD_RESET = "password_reset"  # noqa: S105 - constant name, not password
    EMAIL_VERIFICATION = "email_verification"  # nosec


# Standard HTTP auth scheme descriptor, not a secret.
BEARER_TOKEN_SCHEME = "Bearer"  # noqa: S105 - constant name, not password


def normalize_token_type(token_type: TokenType | str) -> str:
    """Return the string value for either a TokenType enum or raw string."""
    if isinstance(token_type, TokenType):
        return token_type.value
    return str(token_type)
