from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api.routes import documents
from src.database.models import DocumentModel


class _SingleDocRepo:
    def __init__(self, document: DocumentModel | None):
        self._document = document

    def get_by_id(self, document_id: int):
        return (
            self._document
            if self._document and self._document.id == document_id
            else None
        )


@pytest.mark.asyncio
async def test_download_document_serves_file(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    file_path = docs_dir / "report.pdf"
    file_path.write_bytes(b"pdf-bytes")

    doc = DocumentModel(
        id=1,
        title="Annual Report",
        file_path=str(file_path),
        file_hash="hash",
        file_size=file_path.stat().st_size,
        file_type=".pdf",
    )

    response = await documents.download_document(
        document_id=1,
        doc_repo=_SingleDocRepo(doc),
        documents_dir=docs_dir,
    )

    assert Path(response.path) == file_path
    assert response.filename == "Annual Report.pdf"


@pytest.mark.asyncio
async def test_download_document_404_when_doc_missing(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    with pytest.raises(HTTPException) as exc:
        await documents.download_document(
            document_id=1,
            doc_repo=_SingleDocRepo(None),
            documents_dir=docs_dir,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_download_document_404_when_file_path_missing(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    doc = DocumentModel(
        id=1,
        title="Broken",
        file_path=None,
        file_hash="hash",
        file_size=0,
        file_type=".pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await documents.download_document(
            document_id=1,
            doc_repo=_SingleDocRepo(doc),
            documents_dir=docs_dir,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_download_document_404_when_file_absent(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    missing_path = docs_dir / "missing.pdf"

    doc = DocumentModel(
        id=1,
        title="Missing",
        file_path=str(missing_path),
        file_hash="hash",
        file_size=0,
        file_type=".pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await documents.download_document(
            document_id=1,
            doc_repo=_SingleDocRepo(doc),
            documents_dir=docs_dir,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_download_document_blocks_path_traversal(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"data")

    doc = DocumentModel(
        id=1,
        title="Secret",
        file_path=str(outside),
        file_hash="hash",
        file_size=outside.stat().st_size,
        file_type=".pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await documents.download_document(
            document_id=1,
            doc_repo=_SingleDocRepo(doc),
            documents_dir=docs_dir,
        )

    assert exc.value.status_code == 403
