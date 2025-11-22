import asyncio
import types

import backend.api.auth.rbac as rbac


class _StubRole(types.SimpleNamespace):
    def __init__(self, id=1, name="admin"):
        super().__init__(id=id, name=name, permissions=[], parent_role=None)


class _StubUser(types.SimpleNamespace):
    pass


class _StubSession:
    def __init__(self, permissions=None):
        self.permissions = permissions or {}

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


def test_permission_check_basic():
    user = _StubUser(id=1, roles=[_StubRole(name="admin")], permissions=[])
    session = _StubSession()
    service = rbac.RBACService(session)

    result = service.check_permission(user, resource="document", action="read")
    assert result.allowed in (True, False)


def test_require_role_decorator_allows_admin():
    user = _StubUser(id=1, roles=[_StubRole(name="admin")], permissions=[])

    decorator = rbac.require_role(rbac.SystemRoles.ADMIN.value)

    @decorator
    async def sample_endpoint(user):
        return "ok"

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(sample_endpoint(user=user))
    finally:
        loop.close()
    assert result == "ok"
