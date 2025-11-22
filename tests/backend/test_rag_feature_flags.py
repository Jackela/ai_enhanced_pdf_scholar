import pytest
from fastapi import HTTPException

from backend.api.models.requests import IndexBuildRequest, QueryRequest
from backend.api.routes import indexes, queries
from src.database.models import DocumentModel


class _StubDocRepo:
    def __init__(self, document: DocumentModel | None):
        self._document = document

    def get_by_id(self, document_id: int):
        return self._document

    def get_by_ids(self, document_ids: list[int]):
        return [self._document] * len(document_ids) if self._document else []


class _StubCacheManager:
    def __init__(self):
        self.cached = {}

    def get_cached_query(self, **kwargs):
        return None

    def cache_query_result(
        self, query: str, document_id: int, result: str, ttl_seconds: int
    ):
        self.cached[(document_id, query)] = result

    def invalidate_document_cache(self, document_id: int):
        return 0

    def get_cache_stats(self):
        return {"entries": 0}


class _StubVectorRepo:
    def find_by_document_id(self, document_id: int):
        return None


class _StubHealthChecker:
    def perform_health_check(self):
        return {"healthy": True, "issues": []}


@pytest.mark.asyncio
async def test_query_document_returns_501_when_flag_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_RAG_SERVICES", raising=False)
    request = QueryRequest(query="test query")

    with pytest.raises(HTTPException) as exc:
        await queries.query_document(
            document_id=1,
            request=request,
            doc_repo=_StubDocRepo(None),
            cache_manager=_StubCacheManager(),
        )

    assert exc.value.status_code == 501


@pytest.mark.asyncio
async def test_query_document_succeeds_when_flag_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_RAG_SERVICES", "1")
    document = DocumentModel(
        id=1,
        title="Doc",
        file_path=str(tmp_path / "doc.pdf"),
        file_hash="hash",
        file_size=10,
    )
    request = QueryRequest(query="summarize findings")
    response = await queries.query_document(
        document_id=1,
        request=request,
        doc_repo=_StubDocRepo(document),
        cache_manager=_StubCacheManager(),
    )

    assert response.success is True
    assert response.data.document_id == 1


@pytest.mark.asyncio
async def test_build_index_returns_503_when_flag_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_RAG_SERVICES", raising=False)
    request = IndexBuildRequest()

    with pytest.raises(HTTPException) as exc:
        await indexes.build_document_index(
            document_id=1,
            request=request,
            doc_repo=_StubDocRepo(None),
            vector_repo=_StubVectorRepo(),
            health_checker=_StubHealthChecker(),
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_build_index_placeholder_when_flag_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_RAG_SERVICES", "1")
    document = DocumentModel(
        id=1,
        title="Doc",
        file_path=str(tmp_path / "doc.pdf"),
        file_hash="hash",
        file_size=10,
    )
    request = IndexBuildRequest()

    response = await indexes.build_document_index(
        document_id=1,
        request=request,
        doc_repo=_StubDocRepo(document),
        vector_repo=_StubVectorRepo(),
        health_checker=_StubHealthChecker(),
    )

    assert response.success is True
    assert response.data.document_id == 1
