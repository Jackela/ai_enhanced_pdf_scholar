from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.database.models import VectorIndexModel
from src.services.vector_index_manager import (
    VectorIndexManager,
    VectorIndexManagerError,
)


class _StubRepo:
    def __init__(self):
        self.created = []
        self.updated = []
        self.by_id: VectorIndexModel | None = None

    def create(self, model: VectorIndexModel):
        model.id = 1
        self.created.append(model)
        return model

    def update(self, model: VectorIndexModel):
        self.updated.append(model)
        return model

    def find_by_id(self, idx: int):
        return self.by_id


class _StubDB:
    def close_all_connections(self):
        return None


@pytest.fixture
def manager(tmp_path: Path) -> VectorIndexManager:
    mgr = VectorIndexManager(db_connection=_StubDB(), storage_base_dir=str(tmp_path))
    mgr.vector_repo = _StubRepo()  # type: ignore[assignment]
    return mgr


def test_create_index_storage_writes_metadata_and_returns_model(
    manager: VectorIndexManager, tmp_path: Path
):
    idx = manager.create_index_storage(
        document_id=1, index_hash="abcd1234", chunk_count=2
    )
    assert idx.id == 1
    meta_path = Path(idx.index_path) / "index_metadata.json"
    assert meta_path.exists()
    data = json.loads(meta_path.read_text())
    assert data["index_hash"] == "abcd1234"


def test_move_index_to_storage_missing_files_raises(
    manager: VectorIndexManager, tmp_path: Path
):
    vector_index = VectorIndexModel(
        document_id=1, index_path=str(tmp_path / "dest"), index_hash="hash"
    )
    with pytest.raises(VectorIndexManagerError):
        manager.move_index_to_storage(vector_index, source_path=tmp_path / "missing")


def test_verify_index_integrity_success(manager: VectorIndexManager, tmp_path: Path):
    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()
    for name in ["default__vector_store.json", "graph_store.json", "index_store.json"]:
        (idx_dir / name).write_text("{}")
    model = VectorIndexModel(document_id=1, index_path=str(idx_dir), index_hash="hash")
    manager.vector_repo.by_id = model  # type: ignore[attr-defined]
    result = manager.verify_index_integrity(vector_index_id=1)
    assert "errors" in result
