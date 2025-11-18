from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.database.models import TagModel, VectorIndexModel

pytestmark = pytest.mark.unit


def test_vector_index_model_defaults(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    model = VectorIndexModel(
        document_id=1,
        index_path=str(index_dir),
        index_hash="abc123",
    )
    assert model.created_at is not None
    assert model.metadata == {}


def test_vector_index_model_validation() -> None:
    with pytest.raises(ValueError):
        VectorIndexModel(document_id=0, index_path="path", index_hash="hash")
    with pytest.raises(ValueError):
        VectorIndexModel(document_id=1, index_path=" ", index_hash="hash")
    with pytest.raises(ValueError):
        VectorIndexModel(document_id=1, index_path="path", index_hash=" ")


def test_vector_index_model_from_database_row() -> None:
    now = datetime.utcnow()
    row = {
        "id": 5,
        "document_id": 9,
        "index_path": "/tmp/index",
        "index_hash": "hash",
        "chunk_count": 42,
        "created_at": now.isoformat(),
        "metadata": json.dumps({"engine": "llamaindex"}),
    }
    model = VectorIndexModel.from_database_row(row)
    assert model.id == 5
    assert model.document_id == 9
    assert model.metadata == {"engine": "llamaindex"}


def test_vector_index_model_to_database_dict(tmp_path: Path) -> None:
    model = VectorIndexModel(
        id=2,
        document_id=10,
        index_path=str(tmp_path / "idx"),
        index_hash="hash",
        chunk_count=7,
    )
    payload = model.to_database_dict()
    assert payload["id"] == 2
    assert json.loads(payload["metadata"]) == {}


def test_vector_index_model_is_index_available(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    files = [
        "default__vector_store.json",
        "graph_store.json",
        "index_store.json",
    ]
    for name in files:
        (index_dir / name).write_text("{}")
    model = VectorIndexModel(
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
    )
    assert model.is_index_available() is True
    (index_dir / files[0]).unlink()
    assert model.is_index_available() is False


def test_tag_model_defaults() -> None:
    tag = TagModel(name=" Research ")
    assert tag.name == "research"
    assert tag.color == "#0078d4"


def test_tag_model_from_database_row() -> None:
    tag = TagModel.from_database_row({"id": 1, "name": "notes", "color": "#fff"})
    assert tag._from_database is True
    assert tag.color == "#fff"
