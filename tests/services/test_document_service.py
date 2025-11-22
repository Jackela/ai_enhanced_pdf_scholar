from __future__ import annotations

from pathlib import Path

import pytest

from src.database.models import DocumentModel
from src.services import document_service as document_service_module
from src.services.document_service import DocumentService

pytestmark = pytest.mark.services


class DummyDB:
    def fetch_one(self, *args, **kwargs):
        return None

    def fetch_all(self, *args, **kwargs):
        return []

    def execute(self, *args, **kwargs):
        class Result:
            rowcount = 0

            def fetchone(self_inner):
                return None

        return Result()

    def get_last_insert_id(self) -> int:
        return 1

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


class DummyLibrary:
    def __init__(self, document_repository, hash_service):
        self.document_repository = document_repository
        self.hash_service = hash_service
        self.called_with: tuple[Path, str | None] | None = None

    def import_document(
        self, file_path: Path, title: str | None = None
    ) -> DocumentModel:
        self.called_with = (Path(file_path), title)
        return DocumentModel(
            title=title or "Doc",
            file_path=str(file_path),
            file_hash="hash",
            file_size=0,
        )


@pytest.fixture(autouse=True)
def patch_library_and_repo(monkeypatch):
    dummy_library = DummyLibrary
    monkeypatch.setattr(
        document_service_module, "DocumentLibraryService", dummy_library
    )

    class InitRepoStub:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(document_service_module, "DocumentRepository", InitRepoStub)
    yield


@pytest.mark.asyncio
async def test_upload_document_uses_library(tmp_path: Path):
    service = DocumentService(DummyDB())
    target = tmp_path / "doc.pdf"
    target.write_text("data")
    result = await service.upload_document(str(target), title="MyDoc")
    assert result.title == "MyDoc"


@pytest.mark.asyncio
async def test_upload_document_fallback_on_error(monkeypatch, tmp_path: Path):
    class FailingLibrary(DummyLibrary):
        def import_document(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        document_service_module, "DocumentLibraryService", FailingLibrary
    )
    service = DocumentService(DummyDB())
    target = tmp_path / "doc.pdf"
    target.write_text("payload")
    doc = await service.upload_document({"path": str(target)}, title="Fallback")
    assert doc.title == "Fallback"
    assert doc.file_size == len("payload")
    assert doc.id == 1


@pytest.mark.asyncio
async def test_get_document_handles_repository_error(monkeypatch):
    class FailingRepo:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("db down")

    monkeypatch.setattr(
        "src.repositories.document_repository.DocumentRepository", FailingRepo
    )
    service = DocumentService(DummyDB())
    assert await service.get_document(1) is None


@pytest.mark.asyncio
async def test_list_documents_handles_error(monkeypatch):
    class FailingRepo:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("db down")

    monkeypatch.setattr(
        "src.repositories.document_repository.DocumentRepository", FailingRepo
    )
    service = DocumentService(DummyDB())
    assert await service.list_documents() == []


@pytest.mark.asyncio
async def test_delete_document_handles_error(monkeypatch):
    class FailingRepo:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("db down")

    monkeypatch.setattr(
        "src.repositories.document_repository.DocumentRepository", FailingRepo
    )
    service = DocumentService(DummyDB())
    assert await service.delete_document(1) is False


@pytest.mark.asyncio
async def test_get_document_success(monkeypatch):
    class Repo:
        def __init__(self, *args, **kwargs):
            pass

        def get_by_id(self, doc_id: int):
            return DocumentModel(
                id=doc_id,
                title="Loaded",
                file_path="/tmp/doc.pdf",
                file_hash="hash",
                file_size=1,
                _from_database=True,
            )

    monkeypatch.setattr("src.repositories.document_repository.DocumentRepository", Repo)
    service = DocumentService(DummyDB())
    doc = await service.get_document(5)
    assert doc is not None and doc.id == 5


@pytest.mark.asyncio
async def test_list_documents_success(monkeypatch):
    class Repo:
        def __init__(self, *args, **kwargs):
            pass

        def get_all(self):
            return [
                DocumentModel(
                    id=1,
                    title="Doc1",
                    file_path="/tmp/doc1.pdf",
                    file_hash="hash1",
                    file_size=1,
                )
            ]

    monkeypatch.setattr("src.repositories.document_repository.DocumentRepository", Repo)
    service = DocumentService(DummyDB())
    docs = await service.list_documents()
    assert len(docs) == 1 and docs[0].title == "Doc1"


@pytest.mark.asyncio
async def test_delete_document_success(monkeypatch):
    class Repo:
        def __init__(self, *args, **kwargs):
            pass

        def delete(self, doc_id: int) -> bool:
            return doc_id == 1

    monkeypatch.setattr("src.repositories.document_repository.DocumentRepository", Repo)
    service = DocumentService(DummyDB())
    assert await service.delete_document(1) is True
