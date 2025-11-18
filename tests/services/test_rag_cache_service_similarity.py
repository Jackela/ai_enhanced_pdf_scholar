from __future__ import annotations

import sqlite3
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

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


@pytest.fixture
def rag_cache(tmp_path: Path) -> RAGCacheService:
    conn = sqlite3.connect(tmp_path / "cache.sqlite")
    db = CacheDB(conn)
    return RAGCacheService(db, max_entries=5, ttl_hours=1, similarity_threshold=0.5)


def test_semantic_similarity_match_returns_cached_response(rag_cache: RAGCacheService):
    rag_cache.cache_response("hello world", 1, "resp-1")
    rag_cache.cache_response("completely different", 1, "resp-2")

    hit = rag_cache.get_cached_response("hello world again", 1)

    assert hit == "resp-1"
    stats = rag_cache.get_cache_statistics()
    assert stats["cache_metrics"]["cache_hits"] >= 1
    assert stats["total_entries"] >= 2


def test_cache_statistics_after_miss_and_hit(rag_cache: RAGCacheService):
    miss = rag_cache.get_cached_response("unknown query", 1)
    assert miss is None

    rag_cache.cache_response("known query", 1, "ok")
    hit = rag_cache.get_cached_response("known query", 1)
    assert hit == "ok"

    stats = rag_cache.get_cache_statistics()
    # metrics collected inside the service
    assert stats["total_entries"] >= 1
    assert stats["cache_metrics"]["cache_hits"] >= 1
    assert stats["hit_rate_percent"] >= 0
