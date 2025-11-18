import types
from datetime import datetime, timedelta

import backend.api.auth.service as auth_service


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
        self.is_active = kwargs.get("is_active", True)
        self.is_verified = kwargs.get("is_verified", True)

    def is_account_locked(self):
        return bool(
            self.account_locked_until and self.account_locked_until > datetime.utcnow()
        )

    def increment_failed_login(self):
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

    def reset_failed_login_attempts(self):
        self.failed_login_attempts = 0
        self.last_failed_login = None

    def lock_account(self, seconds):
        self.account_locked_until = datetime.utcnow() + timedelta(seconds=seconds)


class _Session:
    def __init__(self, users=None):
        self.users = users or []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.users[0] if self.users else None

    def add(self, obj):
        self.users.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        return obj


def test_register_user_success(monkeypatch):
    session = _Session(users=[])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(
        auth_service.PasswordPolicy, "validate_password_strength", lambda *_: (True, [])
    )
    monkeypatch.setattr(
        auth_service.PasswordHasher, "hash_password", lambda *_: "hashed"
    )
    user, err = service.register_user(
        "newuser", "new@example.com", "Passw0rd!", full_name="Test", auto_verify=True
    )
    assert err is None
    assert user.username == "newuser"
    assert session.committed


def test_register_user_password_fail(monkeypatch):
    session = _Session(users=[])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(
        auth_service.PasswordPolicy,
        "validate_password_strength",
        lambda *_: (False, ["weak"]),
    )
    user, err = service.register_user(
        "weak", "weak@example.com", "bad", full_name=None, auto_verify=False
    )
    assert user is None
    assert "Password validation failed" in err


def test_authenticate_user_success(monkeypatch):
    user = _User(
        id=1, username="ok", email="ok@example.com", is_active=True, is_verified=True
    )
    session = _Session(users=[user])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(auth_service.PasswordHasher, "verify_password", lambda *_: True)
    found, err = service.authenticate_user("ok", "pw")
    assert err is None
    assert found.username == "ok"


def test_change_password_success(monkeypatch):
    user = _User(id=2, username="x", is_active=True, is_verified=True)
    session = _Session(users=[user])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(auth_service.PasswordHasher, "verify_password", lambda *_: True)
    monkeypatch.setattr(
        auth_service.PasswordPolicy, "check_password_age", lambda *_: (True, None)
    )
    monkeypatch.setattr(
        auth_service.PasswordPolicy, "validate_password_strength", lambda *_: (True, [])
    )
    monkeypatch.setattr(
        auth_service.PasswordHasher, "hash_password", lambda *_: "newhash"
    )
    ok, err = service.change_password(
        user_id=2, current_password="pw", new_password="NewPass1!"
    )
    assert ok is True
    assert err is None
    assert session.committed
