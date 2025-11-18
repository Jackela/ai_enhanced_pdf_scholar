from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.repositories.vector_repository import VectorIndexRepository

pytestmark = pytest.mark.repositories


class SimpleDB:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
        self.conn.row_factory = sqlite3.Row

    def fetch_one(self, query, params=()):
        return self.conn.execute(query, params).fetchone()

    def fetch_all(self, query, params=()):
        return self.conn.execute(query, params).fetchall()

    def execute(self, query, params=()):
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur

    def get_last_insert_id(self):
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed(conn: sqlite3.Connection, index_dir: Path) -> None:
    conn.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            file_path TEXT,
            file_size INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO documents (id, title, file_path, file_size) VALUES (1, 'Doc1', '/tmp/doc1.pdf', 1024)"
    )
    conn.execute(
        """
        CREATE TABLE vector_indexes (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            index_path TEXT,
            index_hash TEXT,
            chunk_count INTEGER,
            created_at TEXT,
            metadata TEXT
        )
        """
    )
    for name in ["default__vector_store.json", "graph_store.json", "index_store.json"]:
        (index_dir / name).write_text("{}")
    conn.execute(
        """
        INSERT INTO vector_indexes (id, document_id, index_path, index_hash, chunk_count, created_at, metadata)
        VALUES (1, 1, ?, 'hash-1', 10, ?, '{}')
        """,
        (str(index_dir), datetime.utcnow().isoformat()),
    )


@pytest.fixture
def vector_repo(tmp_path: Path) -> VectorIndexRepository:
    conn = sqlite3.connect(tmp_path / "vector.sqlite")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    _seed(conn, index_dir)
    return VectorIndexRepository(SimpleDB(conn))  # type: ignore[arg-type]


def test_delete_by_document_id(vector_repo: VectorIndexRepository) -> None:
    assert vector_repo.delete_by_document_id(1) is True
    assert vector_repo.delete_by_document_id(99) is False


def test_find_all_with_documents(vector_repo: VectorIndexRepository) -> None:
    rows = vector_repo.find_all_with_documents()
    assert rows
    assert rows[0]["document_title"] == "Doc1"


def test_find_invalid_indexes(
    vector_repo: VectorIndexRepository, tmp_path: Path
) -> None:
    # Remove backing files to mark index invalid
    for path in (tmp_path / "index").glob("*"):
        path.unlink()
    invalid = vector_repo.find_invalid_indexes()
    assert len(invalid) == 1


def test_cleanup_orphaned_indexes(
    vector_repo: VectorIndexRepository, tmp_path: Path
) -> None:
    # Insert an index whose document no longer exists
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    for name in ["default__vector_store.json", "graph_store.json", "index_store.json"]:
        (missing_dir / name).write_text("{}")
    vector_repo.db.execute(
        """
        INSERT INTO vector_indexes (document_id, index_path, index_hash, chunk_count, created_at, metadata)
        VALUES (?, ?, ?, ?, ?, '{}')
        """,
        (999, str(missing_dir), "hash-2", 5, datetime.utcnow().isoformat()),
    )
    cleaned = vector_repo.cleanup_orphaned_indexes()
    assert cleaned == 1
    assert (
        vector_repo.db.fetch_one(
            "SELECT COUNT(*) as count FROM vector_indexes WHERE document_id = ?", (999,)
        )["count"]
        == 0
    )


def test_cleanup_invalid_indexes_removes_files(
    vector_repo: VectorIndexRepository, tmp_path: Path
) -> None:
    extra_dir = tmp_path / "invalid_index"
    extra_dir.mkdir()
    for name in ["default__vector_store.json", "graph_store.json", "index_store.json"]:
        (extra_dir / name).write_text("{}")
    vector_repo.db.execute(
        """
        INSERT INTO vector_indexes (document_id, index_path, index_hash, chunk_count, created_at, metadata)
        VALUES (?, ?, ?, ?, ?, '{}')
        """,
        (1, str(extra_dir), "hash-3", 3, datetime.utcnow().isoformat()),
    )
    # Remove files to mark index invalid
    for file in extra_dir.glob("*"):
        file.unlink()
    cleaned = vector_repo.cleanup_invalid_indexes(remove_files=True)
    assert cleaned >= 1
    assert not extra_dir.exists() or not any(extra_dir.iterdir())
