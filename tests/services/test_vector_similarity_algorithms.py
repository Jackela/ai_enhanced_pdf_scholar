from __future__ import annotations

import math

from src.services.rag.vector_similarity import (
    RetrievalRelevanceAnalyzer,
    SemanticSearchOptimizer,
    VectorSimilarityCalculator,
)


def test_cosine_similarity_handles_zeros_and_valid_vectors():
    calc = VectorSimilarityCalculator()
    assert calc.calculate_cosine_similarity([], [1, 2]) == 0.0

    score = calc.calculate_cosine_similarity([1, 0], [1, 1])
    assert 0 < score < 1


def test_batch_similarity_unknown_metric_returns_zero_scores():
    calc = VectorSimilarityCalculator()
    scores = calc.batch_similarity([1, 0], [[0, 1], [1, 1]], metric="unknown")
    assert scores == [0.0, 0.0]


def test_semantic_optimizer_threshold_and_rerank():
    optimizer = SemanticSearchOptimizer()
    query = [1.0, 0.0]
    candidates = [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]
    relevance = [0.9, 0.6, 0.1]

    threshold = optimizer.optimize_retrieval_threshold(query, candidates, relevance)
    assert 0.1 <= threshold <= 0.9

    reranked = optimizer.rerank_results(
        query, candidates, initial_scores=[0.2, 0.8, 0.1]
    )
    assert reranked[0] == 1  # initial_scores favours index 1

    expanded = optimizer.expand_query("ai", ["ml", "nlp", "search", "extra"])
    assert expanded.startswith("ai ml nlp search")


def test_retrieval_analyzer_metrics_and_mrr_ndcg():
    analyzer = RetrievalRelevanceAnalyzer()
    query_vec = [1.0, 0.0]
    retrieved = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    ground_truth = [0]

    quality = analyzer.analyze_retrieval_quality(query_vec, retrieved, ground_truth)
    assert quality["precision"] > 0
    assert quality["recall"] > 0
    assert quality["similarity_distribution"]["high"] >= 1

    mrr = analyzer.calculate_mrr(query_vec, retrieved, ground_truth)
    assert math.isclose(mrr, 1.0, rel_tol=1e-6)

    ndcg = analyzer.calculate_ndcg(
        query_vec, retrieved, relevance_scores=[1.0, 0.2, 0.5], k=3
    )
    assert ndcg > 0
