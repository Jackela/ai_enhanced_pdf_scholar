from __future__ import annotations

from pathlib import Path

import pytest

from src.database.models import DocumentModel
from src.exceptions import (
    ContentHashError,
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)
from src.services.document_library_service import DocumentLibraryService


class _StubRepo:
    def __init__(self):
        self.documents = {}
        self.db = type("DB", (), {})()

    def find_by_file_hash(self, file_hash: str):
        return next(
            (doc for doc in self.documents.values() if doc.file_hash == file_hash), None
        )

    def create(self, document: DocumentModel):
        self.documents[document.id or len(self.documents) + 1] = document
        return document

    def update(self, document: DocumentModel):
        self.documents[document.id] = document
        return document


class _StubHashService:
    def __init__(self, is_valid: bool = True):
        self.is_valid = is_valid
        self.raise_hash_error = False
        self.hashes = ("filehash", "contenthash")

    def validate_pdf_file(self, file_path: str) -> bool:
        return self.is_valid

    def calculate_combined_hashes(self, file_path: str):
        if self.raise_hash_error:
            raise ContentHashError("hash failure")
        return self.hashes

    def get_file_info(self, file_path: str):
        return {"page_count": 1, "file_size": 1, "mime_type": "application/pdf"}


@pytest.fixture
def tmp_pdf(tmp_path: Path) -> Path:
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"pdf data")
    return file_path


@pytest.fixture
def service(tmp_path: Path) -> DocumentLibraryService:
    repo = _StubRepo()
    hash_service = _StubHashService()
    return DocumentLibraryService(repo, hash_service, documents_dir=str(tmp_path))


def test_validate_import_file_rejects_missing(service: DocumentLibraryService):
    with pytest.raises(DocumentImportError):
        service._validate_import_file("/nonexistent.pdf")


def test_validate_import_file_rejects_invalid_pdf(
    tmp_pdf: Path, service: DocumentLibraryService
):
    service.hash_service.is_valid = False
    with pytest.raises(DocumentValidationError):
        service._validate_import_file(str(tmp_pdf))


def test_calculate_hashes_raises_import_error(
    tmp_pdf: Path, service: DocumentLibraryService
):
    service.hash_service.raise_hash_error = True
    with pytest.raises(DocumentImportError):
        service._calculate_file_hashes(str(tmp_pdf))


def test_create_managed_file_path_uses_hash(service: DocumentLibraryService):
    path = service._create_managed_file_path("abcdefgh1234", "file.pdf")
    assert path.name.startswith("abcdefgh")


def test_remove_document_file_handles_missing(
    tmp_path: Path, service: DocumentLibraryService
):
    doc = DocumentModel(
        id=1,
        title="Missing",
        file_path=str(tmp_path / "missing.pdf"),
        file_hash="hash",
        file_size=0,
    )
    service._remove_document_file(doc)


def test_duplicate_detection_raises(tmp_pdf: Path, service: DocumentLibraryService):
    doc = DocumentModel(
        id=1,
        title="Existing",
        file_path=str(tmp_pdf),
        file_hash="filehash",
        file_size=1,
    )
    service.document_repo.documents[1] = doc
    with pytest.raises(DuplicateDocumentError):
        service._handle_duplicate_document(
            doc,
            overwrite=False,
            file_path=str(tmp_pdf),
            managed_file_path=tmp_pdf,
            title=None,
        )
