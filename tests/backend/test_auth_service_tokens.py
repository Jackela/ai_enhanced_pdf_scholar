import types
from datetime import datetime, timedelta

import pytest

import backend.api.auth.service as auth_service


class _Field:
    """Simple descriptor to mimic SQLAlchemy column comparisons."""

    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return True


class _FakeRefreshTokenModel:
    token_jti = _Field("token_jti")
    token_family = _Field("token_family")
    user_id = _Field("user_id")
    revoked_at = _Field("revoked_at")

    def __init__(
        self,
        user_id: int,
        jti: str | None = None,
        family: str | None = None,
        expires_at: datetime | None = None,
        device_info: str | None = None,
        token_jti: str | None = None,
        token_family: str | None = None,
        **_kwargs,
    ):
        self.user_id = user_id
        self.token_jti = token_jti or jti or ""
        self.token_family = token_family or family or ""
        self.expires_at = expires_at
        self.device_info = device_info
        self.created_at = datetime.utcnow()
        self.revoked_at = None
        self.revoked_reason = None

    def is_valid(self):
        return self.revoked_at is None and self.expires_at > datetime.utcnow()

    def revoke(self, reason: str):
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason


class _FakeUser:
    id = _Field("id")
    email = _Field("email")
    username = ""

    def __init__(
        self,
        user_id: int,
        username: str = "alice",
        role: str = "user",
        version: int = 1,
        active: bool = True,
        email: str = "alice@example.com",
        verified: bool = True,
    ):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.is_active = active
        self.is_verified = verified
        self.refresh_token_version = version
        self.last_activity = None
        self.account_status = "active"
        self.password_hash = "hash"
        self.password_reset_token = None
        self.password_reset_expires = None
        self.email_verification_token = "token"
        self.email_verified_at = None
        self.username = username
        # Methods invoked by service (lockout helpers)
        self.password_changed_at = datetime.utcnow() - timedelta(days=2)
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.last_failed_login = None

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

    def lock_account(self, duration):
        self.account_locked_until = datetime.utcnow() + timedelta(seconds=duration)

    # lockout helpers stubs
    def is_account_locked(self):
        return False

    def increment_failed_login(self):
        return None

    def reset_failed_login_attempts(self):
        return None

    def lock_account(self, *_):
        return None


class _FakeQuery:
    def __init__(self, items):
        self.items = list(items)

    def filter(self, *criteria):
        filtered = self.items
        for criterion in criteria:
            if callable(criterion):
                filtered = [item for item in filtered if criterion(item)]
        return _FakeQuery(filtered)

    def first(self):
        return self.items[0] if self.items else None

    def all(self):
        return list(self.items)

    def update(self, values):
        for item in self.items:
            for key, value in values.items():
                setattr(item, key, value)
        return len(self.items)

    def with_entities(self, *args, **kwargs):
        return self

    def count(self):
        return len(self.items)

    def delete(self):
        removed = len(self.items)
        self.items.clear()
        return removed


class _FakeSession:
    def __init__(self, users=None, tokens=None):
        self.users = users or []
        self.tokens = tokens or []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        if model is auth_service.RefreshTokenModel:
            return _FakeQuery(self.tokens)
        if model is auth_service.UserModel:
            return _FakeQuery(self.users)
        return _FakeQuery([])

    def add(self, item):
        if isinstance(item, auth_service.RefreshTokenModel):
            self.tokens.append(item)

    def filter(self, *args, **kwargs):
        return _FakeQuery(self.users)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


@pytest.fixture(autouse=True)
def patch_models(monkeypatch):
    monkeypatch.setattr(auth_service, "RefreshTokenModel", _FakeRefreshTokenModel)
    monkeypatch.setattr(auth_service, "UserModel", _FakeUser)


def test_refresh_tokens_success(monkeypatch):
    user = _FakeUser(user_id=1, version=1)
    stored_token = _FakeRefreshTokenModel(
        user_id=1,
        jti="j1",
        family="fam",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        device_info="chrome",
    )
    session = _FakeSession(users=[user], tokens=[stored_token])
    service = auth_service.AuthenticationService(db=session)

    class Payload(types.SimpleNamespace):
        pass

    payload = Payload(jti="j1", token_family="fam", version=1, sub="1")

    monkeypatch.setattr(
        auth_service.jwt_handler,
        "decode_token",
        lambda token, token_type=None, verify_exp=True: payload,
    )
    monkeypatch.setattr(
        auth_service.jwt_handler,
        "create_access_token",
        lambda user_id, username, role, version: "access-token",
    )

    def _create_refresh(user_id, username, role, version, token_family=None):
        return "new-refresh", "new-jti", datetime.utcnow() + timedelta(hours=2)

    monkeypatch.setattr(
        auth_service.jwt_handler, "create_refresh_token", _create_refresh
    )
    result = service.refresh_tokens("refresh-token", device_info="firefox")

    access_token, new_refresh, expires_in, error = result
    assert error is None
    assert access_token == "access-token"
    assert new_refresh == "new-refresh"
    assert (
        expires_in == auth_service.jwt_handler.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    # Old token revoked, new token stored
    assert stored_token.revoked_at is not None
    assert any(t.token_jti == "new-jti" for t in session.tokens)


def test_refresh_tokens_version_mismatch(monkeypatch):
    user = _FakeUser(user_id=1, version=2)
    stored_token = _FakeRefreshTokenModel(
        user_id=1,
        jti="j1",
        family="fam",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        device_info=None,
    )
    session = _FakeSession(users=[user], tokens=[stored_token])
    service = auth_service.AuthenticationService(db=session)

    class Payload(types.SimpleNamespace):
        pass

    payload = Payload(jti="j1", token_family="fam", version=1, sub="1")
    monkeypatch.setattr(
        auth_service.jwt_handler,
        "decode_token",
        lambda token, token_type=None, verify_exp=True: payload,
    )

    access_token, new_refresh, expires_in, error = service.refresh_tokens("old-refresh")
    assert access_token is None
    assert error == "Refresh token has been invalidated"
    assert stored_token.revoked_at is not None


def test_request_password_reset_success(monkeypatch):
    user = _FakeUser(user_id=5, email="user@example.com")
    session = _FakeSession(users=[user], tokens=[])
    service = auth_service.AuthenticationService(db=session)

    monkeypatch.setattr(
        auth_service.jwt_handler,
        "create_password_reset_token",
        lambda user_id, email: f"reset-{user_id}",
    )

    token, err = service.request_password_reset("user@example.com")
    assert err is None
    assert token == "reset-5"
    assert user.password_reset_token is not None
    assert user.password_reset_expires is not None


def test_request_password_reset_missing_user():
    session = _FakeSession(users=[], tokens=[])
    service = auth_service.AuthenticationService(db=session)
    token, err = service.request_password_reset("absent@example.com")
    assert token is None
    assert err is None


def test_authenticate_user_invalid_password(monkeypatch):
    user = _FakeUser(user_id=10, username="bob", active=True, verified=True)
    session = _FakeSession(users=[user], tokens=[])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(
        auth_service.PasswordHasher, "verify_password", lambda *_: False
    )
    result, err = service.authenticate_user("bob", "wrong")
    assert result is None
    assert "Invalid username or password" in err


def test_authenticate_user_locked(monkeypatch):
    user = _FakeUser(user_id=11, username="kate", active=True, verified=True)
    user.account_locked_until = datetime.utcnow() + timedelta(minutes=5)
    monkeypatch.setattr(user, "is_account_locked", lambda: True)
    session = _FakeSession(users=[user], tokens=[])
    service = auth_service.AuthenticationService(db=session)
    result, err = service.authenticate_user("kate", "pw")
    assert result is None
    assert "locked" in err.lower()


def test_change_password_invalid_current(monkeypatch):
    user = _FakeUser(user_id=12, username="sam", active=True, verified=True)
    session = _FakeSession(users=[user], tokens=[])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(
        auth_service.PasswordHasher, "verify_password", lambda *_: False
    )
    ok, err = service.change_password(
        user_id=12, current_password="bad", new_password="Newpass1!"
    )
    assert ok is False
    assert "incorrect" in err


def test_verify_email_success(monkeypatch):
    user = _FakeUser(user_id=7, verified=False, active=True)
    session = _FakeSession(users=[user], tokens=[])
    service = auth_service.AuthenticationService(db=session)

    monkeypatch.setattr(
        auth_service.jwt_handler,
        "decode_verification_token",
        lambda token, token_type=None: {"sub": "7"},
    )

    ok, err = service.verify_email("ignored-token")
    assert ok is True
    assert err is None
    assert user.is_verified is True
    assert user.email_verified_at is not None


def test_verify_email_invalid_token(monkeypatch):
    session = _FakeSession(users=[], tokens=[])
    service = auth_service.AuthenticationService(db=session)
    monkeypatch.setattr(
        auth_service.jwt_handler,
        "decode_verification_token",
        lambda *_args, **_kwargs: None,
    )
    ok, err = service.verify_email("bad-token")
    assert ok is False
    assert err == "Invalid or expired verification token"
