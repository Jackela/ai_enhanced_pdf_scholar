import pytest
from fastapi import HTTPException, status

from backend.api.routes import queries as queries_module


@pytest.fixture(autouse=True)
def disable_query_guard(monkeypatch):
    monkeypatch.setattr(queries_module, "_require_queries_enabled", lambda: None)


class _FailingDocRepo:
    def get_by_id(self, document_id: int):
        raise RuntimeError("doc repo down")

    def get_by_ids(self, ids):
        raise RuntimeError("doc repo down")


class _FailingCacheManager:
    def invalidate_document_cache(self, document_id: int):
        raise RuntimeError("cache clear failed")

    def get_cache_stats(self):
        raise RuntimeError("cache stats failed")


@pytest.mark.asyncio
async def test_query_document_chains_exception():
    repo = _FailingDocRepo()

    with pytest.raises(HTTPException) as exc:
        await queries_module.query_document(
            document_id=1,
            request=queries_module.QueryRequest(query="hello", mode="semantic"),
            doc_repo=repo,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_query_multiple_documents_chains_exception():
    repo = _FailingDocRepo()

    with pytest.raises(HTTPException) as exc:
        await queries_module.query_multiple_documents(
            request=queries_module.MultiDocumentQueryRequest(
                query="hello", document_ids=[1], synthesis_mode="summarize"
            ),
            doc_repo=repo,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_clear_document_cache_chains_exception():
    cache_manager = _FailingCacheManager()

    with pytest.raises(HTTPException) as exc:
        await queries_module.clear_document_cache(
            document_id=1, cache_manager=cache_manager
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_get_cache_stats_chains_exception():
    cache_manager = _FailingCacheManager()

    with pytest.raises(HTTPException) as exc:
        await queries_module.get_cache_stats(cache_manager=cache_manager)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)
