import math

import pytest

from src.services.rag.vector_similarity import (
    RetrievalRelevanceAnalyzer,
    SemanticSearchOptimizer,
    VectorSimilarityCalculator,
)

pytestmark = pytest.mark.services


@pytest.fixture
def calculator() -> VectorSimilarityCalculator:
    return VectorSimilarityCalculator()


def test_cosine_similarity_identical_vectors(
    calculator: VectorSimilarityCalculator,
) -> None:
    assert calculator.calculate_cosine_similarity(
        [1.0, 0.0], [1.0, 0.0]
    ) == pytest.approx(1.0)


def test_cosine_similarity_handles_zero_vector(
    calculator: VectorSimilarityCalculator,
) -> None:
    assert calculator.calculate_cosine_similarity(
        [0.0, 0.0], [1.0, 0.0]
    ) == pytest.approx(0.0)


def test_euclidean_distance(calculator: VectorSimilarityCalculator) -> None:
    assert calculator.calculate_euclidean_distance(
        [0.0, 0.0], [3.0, 4.0]
    ) == pytest.approx(5.0)


def test_batch_similarity_dot_product_metric(
    calculator: VectorSimilarityCalculator,
) -> None:
    query = [1.0, 2.0]
    candidates = [[1.0, 2.0], [2.0, 0.0]]
    scores = calculator.batch_similarity(query, candidates, metric="dot_product")
    assert scores == [5.0, 2.0]


def test_semantic_optimizer_reranks_by_combined_scores() -> None:
    optimizer = SemanticSearchOptimizer()
    query = [1.0, 0.0]
    candidates = [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]
    initial_scores = [0.2, 0.6, 0.8]
    reranked = optimizer.rerank_results(query, candidates, initial_scores)
    assert reranked == [1, 0, 2]


def test_semantic_optimizer_expand_query_limits_terms() -> None:
    optimizer = SemanticSearchOptimizer()
    expanded = optimizer.expand_query(
        "retrieval", ["vector", "similarity", "ranking", "extra"]
    )
    assert expanded.split() == ["retrieval", "vector", "similarity", "ranking"]


def test_relevance_analyzer_precision_and_recall() -> None:
    analyzer = RetrievalRelevanceAnalyzer()
    query = [1.0, 0.0]
    retrieved = [[1.0, 0.0], [0.8, 0.2], [0.1, 0.9]]
    ground_truth = [0, 1]
    metrics = analyzer.analyze_retrieval_quality(query, retrieved, ground_truth)
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["f1_score"] == pytest.approx(1.0)
    assert metrics["similarity_distribution"]["high"] >= 1


def test_relevance_analyzer_mrr_top_result_relevant() -> None:
    analyzer = RetrievalRelevanceAnalyzer()
    query = [1.0, 0.0]
    retrieved = [[1.0, 0.0], [0.2, 0.9], [0.5, 0.5]]
    score = analyzer.calculate_mrr(query, retrieved, relevant_indices=[0])
    assert score == pytest.approx(1.0)


def test_relevance_analyzer_ndcg_with_partial_relevance() -> None:
    analyzer = RetrievalRelevanceAnalyzer()
    query = [1.0, 0.0]
    retrieved = [[1.0, 0.0], [0.8, 0.2], [0.2, 0.8]]
    relevance_scores = [3.0, 2.0, 0.5]
    ndcg = analyzer.calculate_ndcg(query, retrieved, relevance_scores, k=3)
    assert 0.0 < ndcg <= 1.0
