from __future__ import annotations

import bcrypt

from backend.api.auth.password_security import PasswordHasher


def test_password_hasher_rehash_flag(monkeypatch):
    salt = bcrypt.gensalt(rounds=4)
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: salt)
    hashed = PasswordHasher.hash_password("Short1!")
    assert PasswordHasher.needs_rehash(hashed, rounds=4) is False
    assert PasswordHasher.needs_rehash(hashed, rounds=12) is True
