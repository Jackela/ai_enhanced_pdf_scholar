import importlib
import os
from pathlib import Path

import pytest

from backend.api.auth import security


def _reset_security_paths(tmp_path: Path):
    security.SecurityConfig.KEYS_DIR = tmp_path
    security.SecurityConfig.PRIVATE_KEY_PATH = tmp_path / "jwt_private.pem"
    security.SecurityConfig.PUBLIC_KEY_PATH = tmp_path / "jwt_public.pem"
    security.SecurityConfig.BCRYPT_SALT_ROUNDS = 4
    security._key_manager = None


def test_password_hash_and_verify(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _reset_security_paths(tmp_path)

    hashed = security.hash_password("super-secret")
    assert security.verify_password("super-secret", hashed)
    assert not security.verify_password("wrong-password", hashed)


def test_token_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _reset_security_paths(tmp_path)
    importlib.reload(security)  # ensure patched paths are respected
    _reset_security_paths(tmp_path)

    access_token, access_exp = security.create_access_token(
        user_id=1, username="alice", role="admin", additional_claims={"custom": "ok"}
    )
    payload = security.verify_token(access_token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["username"] == "alice"
    assert payload["custom"] == "ok"

    refresh_token, token_family, refresh_exp = security.create_refresh_token(
        user_id=1, token_family="family-1", device_info="chrome"
    )
    refresh_payload = security.verify_token(
        refresh_token, token_type=security.TokenType.REFRESH
    )
    assert refresh_payload and refresh_payload["family"] == "family-1"

    reset_token = security.generate_password_reset_token(1, "alice@example.com")
    reset_payload = security.verify_password_reset_token(reset_token)
    assert reset_payload and reset_payload["email"] == "alice@example.com"

    verification_token = security.generate_email_verification_token(
        2, "bob@example.com"
    )
    verification_payload = security.verify_email_verification_token(verification_token)
    assert verification_payload and verification_payload["email"] == "bob@example.com"

    decoded = security.decode_token_unsafe(access_token)
    assert decoded and decoded["type"] == security.TokenType.ACCESS.value

    secure_token = security.generate_secure_token(8)
    assert isinstance(secure_token, str) and secure_token
    assert security.constant_time_compare("a", "a")
    assert not security.constant_time_compare("a", "b")
    assert security.hash_token("token-value") != "token-value"
