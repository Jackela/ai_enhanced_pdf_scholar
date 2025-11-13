import pytest

from backend.api.routes import documents
from src.database.models import DocumentModel


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


def _sample_documents():
    return [
        DocumentModel(
            id=idx,
            title=f"Doc {idx}",
            file_path=f"/tmp/doc_{idx}.pdf",
            file_hash=f"hash{idx}",
            file_size=100 + idx,
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


@pytest.mark.asyncio
async def test_get_document_envelope_handles_missing_file_path():
    docs = _sample_documents()
    docs[0].file_path = None
    repo = _StubDocRepo(docs)

    response = await documents.get_document(document_id=1, doc_repo=repo)

    assert response.success is True
    assert response.data.id == 1
    assert response.data.file_path is None
