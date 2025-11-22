from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import dependencies as auth_deps
from backend.api.auth.dependencies import (
    AuthenticationRequired,
    get_admin_user,
    get_current_user,
    jwt_handler,
)
from backend.api.auth.jwt_handler import JWTConfig
from backend.api.auth.models import UserModel


class _StubUser:
    def __init__(self, user_id: int, role: str = "user"):
        self.id = user_id
        self.username = "user"
        self.role = role
        self.is_active = True
        self.is_verified = True
        self.refresh_token_version = 0

    def is_account_locked(self) -> bool:
        return False


class _StubAuthService:
    def __init__(self, user: _StubUser):
        self._user = user

    def get_user_by_id(self, user_id: int) -> _StubUser | None:
        return self._user if self._user.id == user_id else None

    def update_user_activity(self, user_id: int) -> None:
        return None


def _app_with_guard(dep):
    app = FastAPI()

    @app.get("/protected")
    def protected(user: UserModel = Depends(dep)):
        return {"user_id": user.id, "role": user.role}

    return app


def _issue_token(user_id: int, role: str) -> str:
    handler = jwt_handler
    handler.config.ALGORITHM = "HS256"
    handler.config.ISSUER = "test"
    handler.config.AUDIENCE = "test"
    handler.private_key = b"secret"
    handler.public_key = b"secret"
    return handler.create_access_token(user_id=user_id, username="u", role=role)


def _patch_auth(monkeypatch, stub_user: _StubUser):
    monkeypatch.setattr(
        auth_deps, "AuthenticationService", lambda _db: _StubAuthService(stub_user)
    )
    # Avoid DB wiring
    monkeypatch.setattr(auth_deps, "get_db", lambda: None)
    monkeypatch.setattr(JWTConfig, "ALGORITHM", "HS256")


def test_guard_accepts_valid_token(monkeypatch):
    user = _StubUser(1, "admin")
    _patch_auth(monkeypatch, user)
    monkeypatch.setattr(JWTConfig, "ALGORITHM", "HS256")
    app = _app_with_guard(get_current_user)
    token = _issue_token(1, "admin")

    with TestClient(app) as client:
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["user_id"] == 1


def test_guard_rejects_missing_token():
    app = _app_with_guard(get_current_user)
    with TestClient(app) as client:
        resp = client.get("/protected")

    assert resp.status_code == 401


def test_admin_guard_forbids_non_admin(monkeypatch):
    user = _StubUser(2, "user")
    _patch_auth(monkeypatch, user)
    monkeypatch.setattr(JWTConfig, "ALGORITHM", "HS256")
    app = _app_with_guard(get_admin_user)
    token = _issue_token(2, "user")

    with TestClient(app) as client:
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
