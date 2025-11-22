from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.services.rag_cache_service import RAGCacheService


class CacheDB:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
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

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


@pytest.fixture
def rag_cache(tmp_path: Path) -> RAGCacheService:
    conn = sqlite3.connect(tmp_path / "cache.sqlite")
    db = CacheDB(conn)
    return RAGCacheService(db, max_entries=5, ttl_hours=1, similarity_threshold=0.5)


def test_rag_cache_store_and_fetch(rag_cache: RAGCacheService) -> None:
    assert (
        rag_cache.cache_response("What is RAG?", 1, "Retrieval augmented generation")
        is True
    )
    cached = rag_cache.get_cached_response("What is RAG?", 1)
    assert cached == "Retrieval augmented generation"


def test_rag_cache_expiration(rag_cache: RAGCacheService) -> None:
    rag_cache.cache_response("Old Query", 1, "Old response")
    cutoff = datetime.utcnow() - timedelta(hours=2)
    rag_cache.db.execute(
        "UPDATE rag_query_cache SET created_at = ?, accessed_at = ? WHERE query_text = ?",
        (cutoff.isoformat(), cutoff.isoformat(), "Old Query"),
    )
    assert rag_cache.get_cached_response("Old Query", 1) is None


def test_rag_cache_invalidate_and_stats(rag_cache: RAGCacheService) -> None:
    rag_cache.cache_response("Doc query", 1, "Response")
    stats_before = rag_cache.get_cache_statistics()
    assert stats_before["total_entries"] == 1
    invalidated = rag_cache.invalidate_document_cache(1)
    assert invalidated >= 1
    assert rag_cache.get_cached_response("Doc query", 1) is None
