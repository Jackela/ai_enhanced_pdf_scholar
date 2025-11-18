import types
from datetime import datetime, timedelta

import backend.api.auth.service as auth_service


class _Session:
    def __init__(self, user=None):
        self.user = user
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.user

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _User(types.SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failed_login_attempts = kwargs.get("failed_login_attempts", 0)
        self.account_locked_until = kwargs.get("account_locked_until")
        self.last_failed_login = kwargs.get("last_failed_login")
        self.password_changed_at = kwargs.get(
            "password_changed_at", datetime.utcnow() - timedelta(days=2)
        )
        self.refresh_token_version = kwargs.get("refresh_token_version", 1)
        self.password_hash = "hash"

    def is_account_locked(self):
        return bool(
            self.account_locked_until and self.account_locked_until > datetime.utcnow()
        )

    def increment_failed_login(self):
        self.failed_login_attempts += 1

    def reset_failed_login_attempts(self):
        self.failed_login_attempts = 0

    def lock_account(self, seconds):
        self.account_locked_until = datetime.utcnow() + timedelta(seconds=seconds)


def test_register_user_duplicate(monkeypatch):
    existing = _User(username="bob", email="bob@example.com")
    session = _Session(user=existing)
    service = auth_service.AuthenticationService(db=session)
    user, err = service.register_user("bob", "bob@example.com", "Passw0rd!")
    assert user is None
    assert "already" in err


def test_authenticate_user_requires_verification(monkeypatch):
    user = _User(
        username="carol", email="c@example.com", is_active=True, is_verified=False
    )
    session = _Session(user=user)
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(auth_service.PasswordHasher, "verify_password", lambda *_: True)
    result, err = service.authenticate_user("carol", "pw")
    assert result is None
    assert "verification required" in err.lower()


def test_change_password_policy_failure(monkeypatch):
    user = _User(id=1, username="dave", is_active=True, is_verified=True)
    session = _Session(user=user)
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(auth_service.PasswordHasher, "verify_password", lambda *_: True)
    monkeypatch.setattr(
        auth_service.PasswordPolicy,
        "validate_password_strength",
        lambda *_a, **_k: (False, ["weak"]),
    )
    ok, err = service.change_password(
        user_id=1, current_password="ok", new_password="weak"
    )
    assert ok is False
    assert "Password validation failed" in err
