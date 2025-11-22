from __future__ import annotations

import bcrypt

from backend.api.auth import security


def test_hash_and_verify_password_round_trip(monkeypatch):
    # Use deterministic salt to keep test fast and predictable
    fake_salt = bcrypt.gensalt(rounds=4)
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: fake_salt)

    hashed = security.hash_password("secret123")
    assert hashed != "secret123"
    assert security.verify_password("secret123", hashed) is True
    assert security.verify_password("wrong", hashed) is False
