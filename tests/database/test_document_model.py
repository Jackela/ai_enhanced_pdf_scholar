from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.database.models import DocumentModel

pytestmark = pytest.mark.unit


def test_document_model_post_init_defaults(tmp_path: Path) -> None:
    file_path = tmp_path / "example.pdf"
    file_path.write_text("test")
    model = DocumentModel(
        title="Example",
        file_path=str(file_path),
        file_hash="hash123",
        file_size=4,
    )
    assert model.created_at is not None
    assert model.updated_at == model.created_at
    assert model.metadata == {}
    assert model.file_type == ".pdf"


def test_document_model_from_file_populates_metadata(tmp_path: Path) -> None:
    file_path = tmp_path / "source.PDF"
    file_path.write_text("payload")
    model = DocumentModel.from_file(str(file_path), file_hash="hash456")
    assert model.title == "source"
    assert model.metadata is not None
    assert model.metadata["original_filename"] == "source.PDF"
    assert model.metadata["file_extension"] == ".pdf"
    assert model.file_size == len("payload")


def test_document_model_from_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        DocumentModel.from_file(str(tmp_path / "missing.pdf"), file_hash="hash")


def test_document_model_from_database_row_parses_timestamps() -> None:
    now = datetime.utcnow()
    row = {
        "id": 1,
        "title": "FromDB",
        "file_path": "/tmp/doc.pdf",
        "file_hash": "hash789",
        "file_size": 10,
        "file_type": ".pdf",
        "created_at": now.isoformat(),
        "updated_at": (now + timedelta(seconds=5)).isoformat(),
        "last_accessed": (now + timedelta(seconds=10)).isoformat(),
        "metadata": json.dumps({"key": "value"}),
        "tags": "tag1,tag2",
    }
    model = DocumentModel.from_database_row(row)
    assert model._from_database is True
    assert model.created_at == datetime.fromisoformat(row["created_at"])
    assert model.metadata == {"key": "value"}
    assert model.tags == "tag1,tag2"


def test_document_model_to_database_dict_serializes_metadata(tmp_path: Path) -> None:
    model = DocumentModel(
        id=42,
        title="Serializable",
        file_path=str(tmp_path / "doc.pdf"),
        file_hash="hash",
        file_size=100,
        metadata={"foo": "bar"},
    )
    payload = model.to_database_dict()
    assert payload["id"] == 42
    assert json.loads(payload["metadata"]) == {"foo": "bar"}
    assert isinstance(payload["created_at"], str)


def test_document_model_update_access_and_display(tmp_path: Path) -> None:
    model = DocumentModel(
        title="",
        file_path=str(tmp_path / "doc.pdf"),
        file_hash="hash",
        file_size=1,
        metadata={"original_filename": "doc.pdf"},
    )
    model.update_access_time()
    assert model.last_accessed is not None
    assert model.get_display_name() == "doc.pdf"


def test_document_model_file_helpers(tmp_path: Path) -> None:
    stored = tmp_path / "doc.pdf"
    stored.write_text("data")
    model = DocumentModel(
        title="Doc",
        file_path=str(stored),
        file_hash="hash",
        file_size=4,
    )
    assert model.get_file_extension() == ".pdf"
    assert model.is_file_available() is True
    assert model.is_processed() is False
    model.content_hash = "content"
    model.page_count = 1
    assert model.is_processed() is True
