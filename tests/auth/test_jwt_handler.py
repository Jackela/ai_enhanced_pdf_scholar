from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

from backend.api.auth.constants import TokenType
from backend.api.auth.jwt_handler import JWTConfig, JWTHandler


@pytest.fixture(autouse=True)
def patch_jwt_keys(monkeypatch, tmp_path: Path):
    # Avoid generating RSA keys; use symmetric HS256 for fast, hermetic tests.
    monkeypatch.setattr(
        JWTConfig, "ensure_keys_exist", classmethod(lambda cls: (b"secret", b"secret"))
    )
    monkeypatch.setattr(JWTConfig, "ALGORITHM", "HS256")
    monkeypatch.setattr(JWTConfig, "KEYS_DIR", tmp_path / "jwt_keys")
    monkeypatch.setattr(
        JWTConfig, "PRIVATE_KEY_PATH", tmp_path / "jwt_keys" / "priv.pem"
    )
    monkeypatch.setattr(JWTConfig, "PUBLIC_KEY_PATH", tmp_path / "jwt_keys" / "pub.pem")
    return monkeypatch


def test_access_token_round_trip_with_version_check():
    handler = JWTHandler()
    token = handler.create_access_token(
        user_id=1, username="alice", role="admin", version=2
    )

    payload = handler.verify_token(token, token_type=TokenType.ACCESS, user_version=2)

    assert payload is not None
    assert payload.username == "alice"
    assert payload.role == "admin"
    assert payload.version == 2


def test_refresh_token_rejected_as_access():
    handler = JWTHandler()
    token, _jti, _exp = handler.create_refresh_token(
        user_id=2, username="bob", role="user", version=1
    )

    assert (
        handler.verify_token(token, token_type=TokenType.ACCESS, user_version=1) is None
    )


def test_expired_token_returns_none():
    handler = JWTHandler()
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired_payload = {
        "sub": "3",
        "username": "carol",
        "role": "analyst",
        "exp": past,
        "iat": past - timedelta(minutes=1),
        "jti": "expired",
        "token_type": TokenType.ACCESS.value,
        "iss": handler.config.ISSUER,
        "aud": handler.config.AUDIENCE,
    }

    expired_token = jwt.encode(expired_payload, handler.private_key, algorithm="HS256")

    assert (
        handler.decode_token(
            expired_token, verify_exp=True, token_type=TokenType.ACCESS
        )
        is None
    )
