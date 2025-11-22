from __future__ import annotations

from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from starlette.datastructures import UploadFile

from backend.api.routes import documents
from src.database.models import DocumentModel
from src.exceptions import (
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)


class _StubLibraryService:
    def __init__(
        self, result: DocumentModel | None = None, exc: Exception | None = None
    ):
        self.result = result
        self.exc = exc
        self.called_with: dict[str, str] = {}

    def import_document(
        self,
        file_path: str,
        title: str | None,
        check_duplicates: bool,
        overwrite_duplicates: bool,
    ):
        self.called_with = {
            "file_path": file_path,
            "title": title or "",
            "check_duplicates": check_duplicates,
            "overwrite_duplicates": overwrite_duplicates,
        }
        if self.exc:
            raise self.exc
        return self.result


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    managed = tmp_path / "docs"
    managed.mkdir()
    return managed


def _upload_file(
    content: bytes = b"pdf-data",
    filename: str = "file.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    file_obj = SpooledTemporaryFile()
    file_obj.write(content)
    file_obj.seek(0)
    return UploadFile(
        filename=filename,
        file=file_obj,
        headers={"content-type": content_type},
    )


@pytest.mark.asyncio
async def test_upload_document_succeeds_and_cleans_temp(docs_dir: Path, tmp_path: Path):
    doc = DocumentModel(
        id=1,
        title="Uploaded",
        file_path=str(docs_dir / "file.pdf"),
        file_hash="h",
        file_size=1,
        file_type=".pdf",
    )
    service = _StubLibraryService(result=doc)

    response = await documents.upload_document(
        file=_upload_file(),
        title="Uploaded",
        check_duplicates=True,
        overwrite_duplicates=False,
        library_service=service,
        documents_dir=docs_dir,
    )

    assert response.success is True
    assert response.data.title == "Uploaded"
    # temp upload dir should be cleaned
    tmp_dir = docs_dir.parent / "_tmp_uploads"
    if tmp_dir.exists():
        assert not any(tmp_dir.iterdir())


@pytest.mark.asyncio
async def test_upload_document_conflict_on_duplicate(docs_dir: Path):
    service = _StubLibraryService(exc=DuplicateDocumentError("dup"))
    with pytest.raises(Exception) as exc:
        await documents.upload_document(
            file=_upload_file(),
            title=None,
            check_duplicates=True,
            overwrite_duplicates=False,
            library_service=service,
            documents_dir=docs_dir,
        )
    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_upload_document_bad_request_on_validation_error(docs_dir: Path):
    service = _StubLibraryService(
        exc=DocumentValidationError("invalid", file_path="x", validation_issue="bad")
    )
    with pytest.raises(Exception) as exc:
        await documents.upload_document(
            file=_upload_file(),
            title=None,
            check_duplicates=True,
            overwrite_duplicates=False,
            library_service=service,
            documents_dir=docs_dir,
        )
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_upload_document_bad_request_on_import_error(docs_dir: Path):
    service = _StubLibraryService(exc=DocumentImportError("failed"))
    with pytest.raises(Exception) as exc:
        await documents.upload_document(
            file=_upload_file(),
            title=None,
            check_duplicates=True,
            overwrite_duplicates=False,
            library_service=service,
            documents_dir=docs_dir,
        )
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_upload_document_rejects_non_pdf(docs_dir: Path):
    service = _StubLibraryService(result=None)
    with pytest.raises(Exception) as exc:
        await documents.upload_document(
            file=_upload_file(content_type="text/plain"),
            title=None,
            check_duplicates=True,
            overwrite_duplicates=False,
            library_service=service,
            documents_dir=docs_dir,
        )
    assert getattr(exc.value, "status_code", None) == 415


@pytest.mark.asyncio
async def test_upload_document_requires_file(docs_dir: Path):
    service = _StubLibraryService(result=None)
    with pytest.raises(Exception) as exc:
        await documents.upload_document(
            file=None,  # type: ignore[arg-type]
            title=None,
            check_duplicates=True,
            overwrite_duplicates=False,
            library_service=service,
            documents_dir=docs_dir,
        )
    assert getattr(exc.value, "status_code", None) == 400
