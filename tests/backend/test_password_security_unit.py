from __future__ import annotations

import bcrypt

from backend.api.auth.password_security import PasswordHasher, PasswordPolicy


def test_hash_and_verify_with_short_password(monkeypatch):
    # Use low rounds to keep test fast
    fake_salt = bcrypt.gensalt(rounds=4)
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: fake_salt)

    hashed = PasswordHasher.hash_password("S3cret!")
    assert PasswordHasher.verify_password("S3cret!", hashed) is True
    assert PasswordHasher.verify_password("wrong", hashed) is False


def test_needs_rehash_detects_cost_change(monkeypatch):
    fake_salt = bcrypt.gensalt(rounds=4)
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: fake_salt)
    hashed = PasswordHasher.hash_password("Short1!")
    assert PasswordHasher.needs_rehash(hashed, rounds=4) is False
    assert PasswordHasher.needs_rehash(hashed, rounds=12) is True


def test_password_policy_flags_weak_password():
    ok, errors = PasswordPolicy.validate_password_strength("short", username="user")
    assert ok is False
    assert errors
