from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.database.models import DocumentModel
from src.repositories.document_repository import DocumentRepository

pytestmark = pytest.mark.repositories


def _create_in_memory_db(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "db.sqlite")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            file_path TEXT,
            file_hash TEXT,
            content_hash TEXT,
            file_size INTEGER,
            file_type TEXT,
            page_count INTEGER,
            created_at TEXT,
            updated_at TEXT,
            last_accessed TEXT,
            metadata TEXT,
            tags TEXT
        )
        """
    )
    return conn


class SimpleDB:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection

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
def repo(tmp_path: Path) -> DocumentRepository:
    conn = _create_in_memory_db(tmp_path)
    db = SimpleDB(conn)
    repository = DocumentRepository(db)  # type: ignore[arg-type]
    docs = [
        DocumentModel(
            id=1,
            title="Research Paper",
            file_path="/docs/paper.pdf",
            file_hash="filehash",
            content_hash="content-a",
            file_size=100,
            metadata={},
            _from_database=True,
        ),
        DocumentModel(
            id=2,
            title="Analysis Report",
            file_path="/docs/report.pdf",
            file_hash="filehash-2",
            content_hash="content-b",
            file_size=50,
            metadata={},
            _from_database=True,
        ),
        DocumentModel(
            id=3,
            title="Research Summary",
            file_path="/docs/summary.pdf",
            file_hash="filehash-3",
            content_hash="content-a",
            file_size=100,
            metadata={},
            _from_database=True,
        ),
        DocumentModel(
            id=4,
            title="Research Paper",
            file_path="/docs/paper-copy.pdf",
            file_hash="filehash-4",
            content_hash="content-d",
            file_size=130,
            metadata={},
            _from_database=True,
        ),
    ]
    for idx, doc in enumerate(docs, start=1):
        last_accessed = f"2024-01-0{idx}T00:00:00"
        db.execute(
            """
            INSERT INTO documents
              (id, title, file_path, file_hash, content_hash, file_size, created_at, updated_at, last_accessed, metadata, tags)
            VALUES
              (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '')
            """,
            (
                doc.id,
                doc.title,
                doc.file_path,
                doc.file_hash,
                doc.content_hash,
                doc.file_size,
                last_accessed,
                last_accessed,
                last_accessed,
            ),
        )
    return repository


def test_find_by_file_hash(repo: DocumentRepository) -> None:
    result = repo.find_by_file_hash("filehash")
    assert result is not None
    assert result.title == "Research Paper"


def test_find_by_file_path(repo: DocumentRepository) -> None:
    result = repo.find_by_file_path("/docs/paper.pdf")
    assert result is not None
    assert result.file_hash == "filehash"


def test_get_by_ids_returns_multiple(repo: DocumentRepository) -> None:
    documents = repo.get_by_ids([1, 2])
    assert len(documents) == 2
    assert {doc.id for doc in documents} == {1, 2}


def test_search_by_title(repo: DocumentRepository) -> None:
    results = repo.search_by_title("Analysis")
    assert len(results) == 1
    assert results[0].title == "Analysis Report"


def test_find_by_content_hash(repo: DocumentRepository) -> None:
    doc = repo.find_by_content_hash("content-b")
    assert doc is not None
    assert doc.title == "Analysis Report"


def test_search_returns_results_and_total(repo: DocumentRepository) -> None:
    docs, total = repo.search("Research")
    assert total == 3
    assert {d.title for d in docs} == {
        "Research Paper",
        "Research Summary",
    }


def test_get_all_sorting(repo: DocumentRepository) -> None:
    docs = repo.get_all(sort_by="title", sort_order="asc")
    assert [doc.title for doc in docs][:3] == [
        "Analysis Report",
        "Research Paper",
        "Research Paper",
    ]


def test_find_by_size_range(repo: DocumentRepository) -> None:
    docs = repo.find_by_size_range(min_size=90, max_size=130)
    assert {doc.id for doc in docs} == {1, 3, 4}


def test_find_by_date_range(repo: DocumentRepository) -> None:
    docs = repo.find_by_date_range()
    assert len(docs) == 4


def test_update_access_time(repo: DocumentRepository) -> None:
    assert repo.update_access_time(1) is True
    assert repo.update_access_time(99) is False


def test_get_statistics(repo: DocumentRepository) -> None:
    stats = repo.get_statistics()
    assert stats["total_documents"] == 4
    assert stats["total_size_bytes"] >= 0


def test_find_duplicates_by_size(repo: DocumentRepository) -> None:
    dupes = repo.find_duplicates_by_size_and_name()
    sizes = {group[0] for group in dupes}
    assert 100 in sizes


def test_find_duplicates_by_content_hash(repo: DocumentRepository) -> None:
    dupes = repo.find_duplicates_by_content_hash()
    assert dupes
    hashes = [group[0] for group in dupes]
    assert "content-a" in hashes


def test_find_similar_documents_by_title(repo: DocumentRepository) -> None:
    groups = repo.find_similar_documents_by_title(similarity_threshold=0.5)
    assert groups
    reasons = [reason for reason, _ in groups]
    assert any("Similar titles" in reason for reason in reasons)


def test_find_recent_documents(repo: DocumentRepository) -> None:
    recent = repo.find_recent_documents(limit=2)
    assert [doc.id for doc in recent[:2]] == [4, 3]
