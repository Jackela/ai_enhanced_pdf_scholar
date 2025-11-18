"""Minimal jwt_auth stub for tests.

This project references backend.api.auth.jwt_auth.User from RBAC; the real
implementation is absent, so we provide a simple User model to keep imports
working during testing and lightweight runs.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    id: int
    username: str | None = None
    role: str | None = None
    email: str | None = None
    is_active: bool = True
    is_verified: bool = True
    refresh_token_version: int = 1
    extra: dict[str, Any] | None = None
