from __future__ import annotations

import asyncio

import pytest

from src.services.rag.vector_similarity import VectorSimilarityCalculator
from src.services.rag_cache_service import RAGCacheService


class _StubEmbeddingRepo:
    def __init__(self):
        self.stored = {}

    async def store_embedding(self, doc_id: int, embedding):
        self.stored[doc_id] = embedding
        return True

    async def fetch_embeddings(self, doc_ids):
        return {doc_id: self.stored.get(doc_id, []) for doc_id in doc_ids}


class _StubCoordinator:
    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.emb_repo = _StubEmbeddingRepo()
        self.sim = VectorSimilarityCalculator()

    async def run_query(self, query_vec, candidates: dict[int, list[float]]):
        scores = {
            doc_id: self.sim.calculate_cosine_similarity(query_vec, vec)
            for doc_id, vec in candidates.items()
        }
        best = max(scores.items(), key=lambda kv: kv[1])[0]
        return best, scores[best]


def test_vector_similarity_coordinator_flow():
    coord = _StubCoordinator()
    best, score = asyncio.run(coord.run_query([1, 0], {1: [1, 0], 2: [0, 1]}))
    assert best == 1
    assert score > 0.5


def test_rag_cache_service_hit_miss(tmp_path):
    import sqlite3

    conn = sqlite3.connect(tmp_path / "cache.sqlite")

    class _DB:
        def __init__(self, conn):
            self.conn = conn
            self.conn.row_factory = sqlite3.Row

        def fetch_one(self, q, params=()):
            return self.conn.execute(q, params).fetchone()

        def fetch_all(self, q, params=()):
            return self.conn.execute(q, params).fetchall()

        def execute(self, q, params=()):
            cur = self.conn.execute(q, params)
            self.conn.commit()
            return cur

        def transaction(self):
            from contextlib import nullcontext

            return nullcontext()

    cache = RAGCacheService(
        _DB(conn), max_entries=2, ttl_hours=1, similarity_threshold=0.1
    )
    cache.cache_response("q1", 1, "r1")
    hit = cache.get_cached_response("q1", 1)
    assert hit == "r1"

    miss = cache.get_cached_response("q2", 1)
    assert miss is None
