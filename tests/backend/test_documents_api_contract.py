import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api.routes import documents
from src.database.models import DocumentModel
from src.services.document_preview_service import (
    PreviewContent,
    PreviewDisabledError,
    PreviewError,
    PreviewNotFoundError,
    PreviewUnsupportedError,
)


class _StubDocRepo:
    def __init__(self, documents_list: list[DocumentModel]):
        self._documents = documents_list

    def search(self, query: str, limit: int, offset: int):
        filtered = [
            doc for doc in self._documents if query.lower() in doc.title.lower()
        ]
        return filtered[offset : offset + limit], len(filtered)

    def get_all(self, limit: int, offset: int, sort_by: str, sort_order: str):
        return self._documents[offset : offset + limit]

    def count(self) -> int:
        return len(self._documents)

    def get_by_id(self, document_id: int):
        for doc in self._documents:
            if doc.id == document_id:
                return doc
        return None


class _FailingDocRepo(_StubDocRepo):
    def __init__(self, exception: Exception):
        super().__init__(_sample_documents())
        self._exception = exception

    def get_all(self, limit: int, offset: int, sort_by: str, sort_order: str):
        raise self._exception

    def get_by_id(self, document_id: int):
        raise self._exception


def _sample_documents():
    return [
        DocumentModel(
            id=idx,
            title=f"Doc {idx}",
            file_path=str(Path(tempfile.gettempdir()) / f"doc_{idx}.pdf"),
            file_hash=f"hash{idx}",
            file_size=100 + idx,
            file_type=".pdf",
        )
        for idx in range(1, 5)
    ]


@pytest.mark.asyncio
async def test_list_documents_returns_paginated_response():
    repo = _StubDocRepo(_sample_documents())

    response = await documents.list_documents(
        query="Doc",
        page=1,
        per_page=2,
        sort_by="created_at",
        sort_order="desc",
        doc_repo=repo,
    )

    assert response.success is True
    assert len(response.data) == 2
    assert response.meta.total == 4
    assert response.meta.page == 1
    assert response.meta.total_pages == 2
    assert response.meta.has_next is True
    assert response.meta.has_prev is False


@pytest.mark.asyncio
async def test_list_documents_handles_value_error_from_repo():
    repo = _FailingDocRepo(ValueError("invalid sort"))
    with pytest.raises(HTTPException) as exc:
        await documents.list_documents(
            query=None,
            page=1,
            per_page=10,
            sort_by="invalid",
            sort_order="asc",
            doc_repo=repo,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_list_documents_handles_generic_exception():
    repo = _FailingDocRepo(RuntimeError("db down"))
    with pytest.raises(HTTPException) as exc:
        await documents.list_documents(
            query=None,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_order="desc",
            doc_repo=repo,
        )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_get_document_envelope_handles_missing_file_path():
    docs = _sample_documents()
    docs[0].file_path = None
    repo = _StubDocRepo(docs)

    response = await documents.get_document(document_id=1, doc_repo=repo)

    assert response.success is True
    assert response.data.id == 1
    assert response.data.file_path is None


@pytest.mark.asyncio
async def test_get_document_returns_404_when_missing():
    repo = _StubDocRepo(_sample_documents())

    with pytest.raises(HTTPException) as exc:
        await documents.get_document(document_id=999, doc_repo=repo)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_document_raises_500_on_repo_error():
    repo = _FailingDocRepo(RuntimeError("db down"))

    with pytest.raises(HTTPException) as exc:
        await documents.get_document(document_id=1, doc_repo=repo)

    assert exc.value.status_code == 500


class _StubPreviewService:
    def __init__(self, content: bytes = b"preview-bytes"):
        self.settings = type("Cfg", (), {"cache_ttl_seconds": 60})
        self._content = content

    def get_page_preview(self, document_id: int, page: int, width: int | None):
        width = width or 256
        return PreviewContent(self._content, "image/png", width, 128, page, False)

    def get_thumbnail(self, document_id: int):
        return PreviewContent(self._content, "image/png", 256, 128, 1, True)


class _DisabledPreviewService(_StubPreviewService):
    def get_page_preview(self, document_id: int, page: int, width: int | None):
        raise PreviewDisabledError("disabled")

    def get_thumbnail(self, document_id: int):
        raise PreviewDisabledError("disabled")


@pytest.mark.asyncio
async def test_preview_endpoint_returns_image_response():
    service = _StubPreviewService()

    response = await documents.get_document_preview(
        document_id=1,
        page=1,
        width=320,
        preview_service=service,
    )

    assert response.media_type == "image/png"
    assert response.body == b"preview-bytes"
    assert response.headers["X-Document-Id"] == "1"
    assert "Cache-Control" in response.headers


@pytest.mark.asyncio
async def test_preview_endpoint_handles_disabled_service():
    service = _DisabledPreviewService()

    with pytest.raises(HTTPException) as exc:
        await documents.get_document_thumbnail(
            document_id=1,
            preview_service=service,
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_preview_endpoint_handles_unsupported_media_type():
    service = _UnsupportedPreviewService()

    with pytest.raises(HTTPException) as exc:
        await documents.get_document_preview(
            document_id=1,
            page=1,
            width=None,
            preview_service=service,
        )

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_preview_endpoint_handles_not_found():
    service = _NotFoundPreviewService()

    with pytest.raises(HTTPException) as exc:
        await documents.get_document_preview(
            document_id=1,
            page=1,
            width=None,
            preview_service=service,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_preview_endpoint_handles_generic_preview_error():
    service = _GenericPreviewErrorService()

    with pytest.raises(HTTPException) as exc:
        await documents.get_document_preview(
            document_id=1,
            page=1,
            width=None,
            preview_service=service,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_preview_endpoint_handles_unexpected_exception():
    service = _CrashedPreviewService()

    with pytest.raises(HTTPException) as exc:
        await documents.get_document_preview(
            document_id=1,
            page=1,
            width=None,
            preview_service=service,
        )

    assert exc.value.status_code == 500


def test_build_preview_headers_marks_cache_hit():
    preview = PreviewContent(
        b"", "image/png", width=200, height=100, page=2, from_cache=True
    )
    headers = documents._build_preview_headers(42, preview, ttl_seconds=15)
    assert headers["Cache-Control"] == "private, max-age=15"
    assert headers["X-Document-Id"] == "42"
    assert headers["X-Preview-Cache"] == "hit"
    assert headers["X-Preview-Page"] == "2"


def test_handle_preview_exception_maps_error_codes():
    with pytest.raises(HTTPException) as exc:
        documents._handle_preview_exception("preview", PreviewUnsupportedError("nope"))
    assert exc.value.status_code == 415

    with pytest.raises(HTTPException) as exc:
        documents._handle_preview_exception("preview", RuntimeError("boom"))
    assert exc.value.status_code == 500


class _UnsupportedPreviewService(_StubPreviewService):
    def get_page_preview(self, document_id: int, page: int, width: int | None):
        raise PreviewUnsupportedError("unsupported")


class _NotFoundPreviewService(_StubPreviewService):
    def get_page_preview(self, document_id: int, page: int, width: int | None):
        raise PreviewNotFoundError("missing")


class _GenericPreviewErrorService(_StubPreviewService):
    def get_page_preview(self, document_id: int, page: int, width: int | None):
        raise PreviewError("boom")


class _CrashedPreviewService(_StubPreviewService):
    def get_page_preview(self, document_id: int, page: int, width: int | None):
        raise RuntimeError("failure")
