from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.repositories.vector_repository import VectorIndexRepository

pytestmark = pytest.mark.repositories


def _prepare_db(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "vector.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            file_path TEXT,
            file_size INTEGER
        );
        CREATE TABLE vector_indexes (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            index_path TEXT,
            index_hash TEXT,
            chunk_count INTEGER,
            created_at TEXT,
            metadata TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO documents (id, title, file_path, file_size) VALUES (1, 'Doc 1', '/docs/doc1.pdf', 2048)"
    )
    return conn


class SimpleDB:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def fetch_one(self, query, params=()):
        cur = self.conn.execute(query, params)
        return cur.fetchone()

    def fetch_all(self, query, params=()):
        cur = self.conn.execute(query, params)
        return cur.fetchall()

    def execute(self, query, params=()):
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur

    def get_last_insert_id(self):
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


@pytest.fixture
def repo(tmp_path: Path) -> VectorIndexRepository:
    conn = _prepare_db(tmp_path)
    db = SimpleDB(conn)
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    for name in ["default__vector_store.json", "graph_store.json", "index_store.json"]:
        (index_dir / name).write_text("{}")
    db.execute(
        """
        INSERT INTO vector_indexes
            (id, document_id, index_path, index_hash, chunk_count, created_at, metadata)
        VALUES
            (1, 1, ?, 'hash-1', 10, '2024-01-01T00:00:00', '{}')
        """,
        (str(index_dir),),
    )
    return VectorIndexRepository(db)  # type: ignore[arg-type]


def test_find_by_document_id(repo: VectorIndexRepository) -> None:
    result = repo.find_by_document_id(1)
    assert result is not None
    assert result.index_hash == "hash-1"


def test_find_by_index_hash(repo: VectorIndexRepository) -> None:
    result = repo.find_by_index_hash("hash-1")
    assert result is not None
    assert result.document_id == 1


def test_find_all_with_documents(repo: VectorIndexRepository) -> None:
    rows = repo.find_all_with_documents()
    assert rows
    assert rows[0]["document_title"] == "Doc 1"


def test_find_invalid_indexes(tmp_path: Path, repo: VectorIndexRepository) -> None:
    # Remove files to mark index invalid
    for path in Path(repo.find_by_document_id(1).index_path).glob("*"):
        path.unlink()
    invalid = repo.find_invalid_indexes()
    assert len(invalid) == 1


def test_find_orphaned_indexes(repo: VectorIndexRepository) -> None:
    # Remove document reference to create orphan
    repo.db.execute("DELETE FROM documents WHERE id = 1")
    orphaned = repo.find_orphaned_indexes()
    assert len(orphaned) == 1


def test_cleanup_orphaned_indexes(repo: VectorIndexRepository) -> None:
    repo.db.execute("DELETE FROM documents WHERE id = 1")
    removed = repo.cleanup_orphaned_indexes()
    assert removed == 1


def test_delete_by_document_id(repo: VectorIndexRepository) -> None:
    assert repo.delete_by_document_id(1) is True
    assert repo.delete_by_document_id(999) is False
