import pytest
from fastapi import HTTPException, status

from backend.api.routes import indexes as indexes_module


@pytest.fixture(autouse=True)
def disable_index_guard(monkeypatch):
    monkeypatch.setattr(indexes_module, "_require_indexes_enabled", lambda: None)


class _FailingRepo:
    def get_by_id(self, index_id: int):
        raise RuntimeError("db down")


class _FailingManager:
    def cleanup_orphaned_indexes(self):
        raise RuntimeError("cleanup exploded")

    def get_storage_stats(self):
        raise RuntimeError("stats failed")


@pytest.mark.asyncio
async def test_verify_index_chains_exception():
    repo = _FailingRepo()

    with pytest.raises(HTTPException) as exc:
        await indexes_module.verify_index(index_id=123, vector_repo=repo)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_cleanup_orphaned_indexes_chains_exception():
    manager = _FailingManager()

    with pytest.raises(HTTPException) as exc:
        await indexes_module.cleanup_orphaned_indexes(resource_manager=manager)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_get_storage_stats_chains_exception():
    manager = _FailingManager()

    with pytest.raises(HTTPException) as exc:
        await indexes_module.get_storage_stats(resource_manager=manager)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)
