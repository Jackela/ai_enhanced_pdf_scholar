from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    get_document_library_service,
    get_document_preview_service,
    get_document_repository,
    get_documents_dir,
)
from backend.api.routes import documents
from src.database.models import DocumentModel
from src.exceptions import (
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)
from src.services.document_preview_service import PreviewContent


class _StubLibraryService:
    def __init__(self, result: DocumentModel, exc: Exception | None = None):
        self.result = result
        self.exc = exc
        self.calls: list[str] = []

    def import_document(
        self,
        file_path: str,
        title: str | None,
        check_duplicates: bool,
        overwrite_duplicates: bool,
    ):
        self.calls.append(file_path)
        if self.exc:
            raise self.exc
        return self.result


class _StubRepository:
    def __init__(self, document: DocumentModel):
        self.document = document

    def get_by_id(self, document_id: int) -> DocumentModel | None:
        return self.document if document_id == self.document.id else None


class _StubPreviewService:
    def __init__(self, content: bytes = b"img-bytes"):
        self.content = content
        self.settings = type("Cfg", (), {"cache_ttl_seconds": 60})

    def get_page_preview(self, document_id: int, page: int, width: int | None):
        width = width or 256
        return PreviewContent(self.content, "image/png", width, 128, page, False)

    def get_thumbnail(self, document_id: int):
        return PreviewContent(self.content, "image/png", 256, 128, 1, True)


@pytest.fixture
def app_factory(
    tmp_path: Path,
) -> Callable[..., tuple[FastAPI, _StubLibraryService, Path]]:
    def _create(
        service_exc: Exception | None = None,
    ) -> tuple[FastAPI, _StubLibraryService, Path]:
        docs_dir = tmp_path / f"docs_{uuid4().hex}"
        docs_dir.mkdir()

        stored = docs_dir / "stored.pdf"
        stored.write_bytes(b"pdf-bytes")
        stored_doc = DocumentModel(
            id=1,
            title="Stored",
            file_path=str(stored),
            file_hash="hash",
            file_size=stored.stat().st_size,
            file_type=".pdf",
        )
        uploaded_doc = DocumentModel(
            id=2,
            title="Uploaded",
            file_path=str(docs_dir / "uploaded.pdf"),
            file_hash="hash2",
            file_size=2,
            file_type=".pdf",
        )

        library_service = _StubLibraryService(result=uploaded_doc, exc=service_exc)
        repository = _StubRepository(document=stored_doc)
        preview_service = _StubPreviewService()

        app = FastAPI()
        app.dependency_overrides[get_document_library_service] = lambda: library_service
        app.dependency_overrides[get_document_repository] = lambda: repository
        app.dependency_overrides[get_document_preview_service] = lambda: preview_service
        app.dependency_overrides[get_documents_dir] = lambda: docs_dir
        app.include_router(documents.router, prefix="/documents")
        return app, library_service, docs_dir

    return _create


def _upload(client: TestClient, content: bytes = b"pdf", filename: str = "file.pdf"):
    return client.post(
        "/documents",
        files={"file": (filename, content, "application/pdf")},
        data={"title": "Uploaded"},
    )


def test_upload_endpoint_contract_success(
    app_factory: Callable[..., tuple[FastAPI, _StubLibraryService, Path]],
):
    app, service, docs_dir = app_factory()

    with TestClient(app) as client:
        response = _upload(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["title"] == "Uploaded"
    assert service.calls  # library service was invoked

    tmp_dir = docs_dir.parent / "_tmp_uploads"
    if tmp_dir.exists():
        assert not any(tmp_dir.iterdir())


@pytest.mark.parametrize(
    "exc, expected_status",
    [
        (DuplicateDocumentError("dup"), 409),
        (
            DocumentValidationError("invalid", file_path="x", validation_issue="bad"),
            400,
        ),
        (DocumentImportError("failed"), 400),
    ],
)
def test_upload_endpoint_contract_errors(
    app_factory: Callable[..., tuple[FastAPI, _StubLibraryService, Path]],
    exc: Exception,
    expected_status: int,
):
    app, _service, _docs_dir = app_factory(service_exc=exc)

    with TestClient(app) as client:
        response = _upload(client)

    assert response.status_code == expected_status
    body = response.json()
    assert "detail" in body


def test_download_endpoint_contract(
    app_factory: Callable[..., tuple[FastAPI, _StubLibraryService, Path]],
):
    app, _service, docs_dir = app_factory()
    with TestClient(app) as client:
        response = client.get("/documents/1/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content == (docs_dir / "stored.pdf").read_bytes()


def test_preview_endpoint_contract(
    app_factory: Callable[..., tuple[FastAPI, _StubLibraryService, Path]],
):
    app, _service, _docs_dir = app_factory()
    with TestClient(app) as client:
        response = client.get("/documents/1/preview?page=1&width=320")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["X-Document-Id"] == "1"
    assert response.headers["Cache-Control"]
