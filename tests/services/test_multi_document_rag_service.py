from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import pytest

from src.database.models import DocumentModel
from src.database.multi_document_models import MultiDocumentCollectionModel
from src.services.multi_document_rag_service import MultiDocumentRAGService

pytestmark = pytest.mark.services


class DummyCollectionRepo:
    def __init__(self):
        self.collections: dict[int, MultiDocumentCollectionModel] = {}
        self.created = 0

    def create(self, collection: MultiDocumentCollectionModel):
        self.created += 1
        collection.id = self.created
        self.collections[self.created] = collection
        return collection

    def get_by_id(self, collection_id: int):
        return self.collections.get(collection_id)

    def get_all(self):
        return list(self.collections.values())

    def update(self, collection: MultiDocumentCollectionModel):
        self.collections[collection.id] = collection
        return collection

    def delete(self, collection_id: int):
        return bool(self.collections.pop(collection_id, None))


class DummyIndexRepo:
    def __init__(self):
        self.indexes: dict[int, Any] = {}

    def create(self, index_model):
        index_model.id = len(self.indexes) + 1
        self.indexes[index_model.collection_id] = index_model
        return index_model

    def get_by_collection_id(self, collection_id: int):
        return self.indexes.get(collection_id)

    def delete(self, index_id: int):
        for key, val in list(self.indexes.items()):
            if val.id == index_id:
                del self.indexes[key]

    def cleanup_orphaned_indexes(self):
        cleaned = len(self.indexes)
        self.indexes.clear()
        return cleaned


class DummyQueryRepo:
    def __init__(self):
        self.queries = []

    def create(self, query_model):
        query_model.id = len(self.queries) + 1
        self.queries.append(query_model)
        return query_model

    def update(self, query_model):
        return query_model


class DummyDocumentRepo:
    def __init__(self):
        self.docs = {
            1: DocumentModel(
                id=1,
                title="Doc1",
                file_path="/docs/doc1.pdf",
                file_hash="hash1",
                file_size=100,
                metadata={},
                _from_database=True,
            ),
            2: DocumentModel(
                id=2,
                title="Doc2",
                file_path="/docs/doc2.pdf",
                file_hash="hash2",
                file_size=200,
                metadata={},
                _from_database=True,
            ),
        }

    def get_by_ids(self, ids):
        return [self.docs[i] for i in ids if i in self.docs]

    def get_by_id(self, doc_id):
        return self.docs.get(doc_id)


class DummyEnhancedRAG:
    async def query_documents(self, *args, **kwargs):
        return {"answer": "result"}


class DummyIndexManager:
    def __init__(self):
        self.created = 0
        self.index_exists_flag = False

    def create_index(self, documents, collection_id):
        self.created += 1
        path = f"/tmp/index_{collection_id}"
        Path(path).mkdir(parents=True, exist_ok=True)
        self.index_exists_flag = True
        return path

    def index_exists(self, collection_id):
        return self.index_exists_flag

    def delete_index(self, collection_id):
        self.index_exists_flag = False
        return True


class DummyAnalyzer:
    async def analyze_cross_document_query(self, **kwargs):
        class Response:
            answer = "analysis"
            confidence = 0.9
            sources = []
            cross_references = []
            processing_time_ms = 10
            tokens_used = 42

        return Response()


@pytest.fixture
def multi_doc_service(monkeypatch):
    collection_repo = DummyCollectionRepo()
    index_repo = DummyIndexRepo()
    query_repo = DummyQueryRepo()
    document_repo = DummyDocumentRepo()
    rag_service = DummyEnhancedRAG()

    service = MultiDocumentRAGService(
        collection_repository=collection_repo,
        index_repository=index_repo,
        query_repository=query_repo,
        document_repository=document_repo,
        enhanced_rag_service=rag_service,
    )
    service.index_manager = DummyIndexManager()
    service.analyzer = DummyAnalyzer()
    return service, collection_repo, index_repo


@pytest.mark.asyncio
async def test_create_and_query_collection(multi_doc_service):
    service, collection_repo, index_repo = multi_doc_service
    collection = service.create_collection("Test", [1, 2])
    assert collection.id == 1
    await service.query_collection(collection.id, "What is new?")
    assert index_repo.get_by_collection_id(collection.id) is not None


def test_add_and_remove_document(multi_doc_service):
    service, _, _ = multi_doc_service
    collection = service.create_collection("Bundle", [1])
    updated = service.add_document_to_collection(collection.id, 2)
    assert 2 in updated.document_ids
    updated = service.remove_document_from_collection(collection.id, 2)
    assert 2 not in updated.document_ids


def test_delete_collection(multi_doc_service):
    service, _, index_repo = multi_doc_service
    collection = service.create_collection("Bundle", [1])
    service.create_collection_index(collection.id)
    assert service.delete_collection(collection.id) is True
    assert index_repo.get_by_collection_id(collection.id) is None


@pytest.mark.asyncio
async def test_ensure_collection_index_creates_when_missing(multi_doc_service):
    service, _, index_repo = multi_doc_service
    collection = service.create_collection("NeedsIndex", [1, 2])
    assert index_repo.get_by_collection_id(collection.id) is None
    await service._ensure_collection_index(collection.id)
    assert index_repo.get_by_collection_id(collection.id) is not None


@pytest.mark.asyncio
async def test_ensure_collection_index_skips_when_present(
    multi_doc_service, monkeypatch
):
    service, _, _ = multi_doc_service
    collection = service.create_collection("ExistingIndex", [1])
    service.create_collection_index(collection.id)
    service.index_manager.index_exists_flag = True
    called = {"count": 0}

    def fail_call(_collection_id: int):
        called["count"] += 1

    monkeypatch.setattr(service, "create_collection_index", fail_call)
    await service._ensure_collection_index(collection.id)
    assert called["count"] == 0


def test_invalidate_collection_index(multi_doc_service):
    service, _, index_repo = multi_doc_service
    collection = service.create_collection("Invalidation", [1])
    service.create_collection_index(collection.id)
    assert index_repo.get_by_collection_id(collection.id) is not None
    service._invalidate_collection_index(collection.id)
    assert index_repo.get_by_collection_id(collection.id) is None
    assert service.index_manager.index_exists_flag is False


def test_get_collection_statistics(multi_doc_service):
    service, _, _ = multi_doc_service
    collection = service.create_collection("Stats", [1, 2])
    stats = service.get_collection_statistics(collection.id)
    assert stats["document_count"] == 2
    assert stats["total_file_size"] == 300
    assert stats["avg_file_size"] == 150


def test_add_and_remove_document_trigger_invalidation(multi_doc_service, monkeypatch):
    service, _, _ = multi_doc_service
    collection = service.create_collection("Invalidate", [1])
    calls: list[int] = []

    def tracker(collection_id: int):
        calls.append(collection_id)

    monkeypatch.setattr(service, "_invalidate_collection_index", tracker)
    service.add_document_to_collection(collection.id, 2)
    service.remove_document_from_collection(collection.id, 2)
    assert calls == [collection.id, collection.id]


def test_calculate_index_hash_is_order_invariant(multi_doc_service):
    service, _, _ = multi_doc_service
    docs = service.document_repo.get_by_ids([1, 2])
    hash_one = service._calculate_index_hash(docs)
    hash_two = service._calculate_index_hash(list(reversed(docs)))
    assert hash_one == hash_two
