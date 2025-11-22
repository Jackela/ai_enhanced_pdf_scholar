import types

from fastapi.testclient import TestClient

from backend.api.auth import routes


class _StubUser(types.SimpleNamespace):
    pass


def _build_app(monkeypatch):
    # Stub dependencies
    monkeypatch.setattr("backend.api.auth.dependencies.get_db", lambda: iter([None]))
    monkeypatch.setattr(
        "backend.api.auth.dependencies.get_current_user",
        lambda: _StubUser(id=1, username="u", role="user"),
    )

    # Stub service behaviors
    monkeypatch.setattr(
        "backend.api.auth.service.AuthenticationService.authenticate_user",
        lambda self, *_a, **_k: (_StubUser(id=1, username="u", role="user"), None),
    )
    monkeypatch.setattr(
        "backend.api.auth.service.AuthenticationService.create_tokens",
        lambda self, user, device_info=None: ("access-token", "refresh-token", 60),
    )
    monkeypatch.setattr(
        "backend.api.auth.service.AuthenticationService.refresh_tokens",
        lambda self, refresh_token, device_info=None: (
            "new-access",
            "new-refresh",
            60,
            None,
        ),
    )
    monkeypatch.setattr(
        "backend.api.auth.service.AuthenticationService.verify_email",
        lambda self, token: (True, None),
    )

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(routes.router, prefix="/api", tags=["auth"])
    return app


def test_login_and_refresh(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)

    res = client.post("/api/auth/login", json={"username": "u", "password": "pw"})
    assert res.status_code == 200
    assert res.json()["access_token"] == "access-token"

    res_refresh = client.post(
        "/api/auth/refresh", json={"refresh_token": "refresh-token"}
    )
    assert res_refresh.status_code == 200
    assert res_refresh.json()["access_token"] == "new-access"


def test_verify_email_route(monkeypatch):
    app = _build_app(monkeypatch)
    client = TestClient(app)
    res_verify = client.post("/api/auth/verify-email", json={"token": "tok"})
    assert res_verify.status_code == 200
