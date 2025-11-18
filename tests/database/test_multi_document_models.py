from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.database.multi_document_models import (
    CrossReference,
    DocumentSource,
    MultiDocumentCollectionModel,
)

pytestmark = pytest.mark.unit


def test_document_source_validation() -> None:
    source = DocumentSource(document_id=1, relevance_score=0.9, excerpt="Summary")
    assert source.document_id == 1
    with pytest.raises(ValueError):
        DocumentSource(document_id=0, relevance_score=0.5, excerpt="Bad")


def test_cross_reference_validation() -> None:
    ref = CrossReference(source_doc_id=1, target_doc_id=2, relation_type="supports")
    assert ref.source_doc_id == 1
    with pytest.raises(ValueError):
        CrossReference(source_doc_id=1, target_doc_id=1, relation_type="supports")


def test_collection_add_remove_documents() -> None:
    collection = MultiDocumentCollectionModel(name="Bundle", document_ids=[1, 2])
    collection.add_document(3)
    assert collection.document_count == 3
    removed = collection.remove_document(2)
    assert removed is True
    assert collection.document_count == 2
    collection.remove_document(3)
    with pytest.raises(ValueError):
        collection.remove_document(1)


def test_collection_from_database_row() -> None:
    now = datetime.utcnow().isoformat()
    row = {
        "id": 5,
        "name": "FromDB",
        "description": "loaded",
        "document_ids": json.dumps([1, 2]),
        "created_at": now,
        "updated_at": now,
    }
    collection = MultiDocumentCollectionModel.from_database_row(row)
    assert collection.id == 5
    assert collection.document_ids == [1, 2]
