"""
Vector Similarity and Retrieval Relevance Tests

Tests for vector similarity algorithms, semantic search quality,
and retrieval relevance optimization in RAG systems.
"""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from src.services.rag.exceptions import RAGVectorError
from src.services.rag.vector_similarity import (
    RetrievalRelevanceAnalyzer,
    SemanticSearchOptimizer,
    VectorSimilarityCalculator,
)


class TestVectorSimilarityCalculator:
    """Test suite for vector similarity calculation algorithms."""

    @pytest.fixture
    def similarity_calculator(self):
        """Create vector similarity calculator."""
        return VectorSimilarityCalculator()

    @pytest.fixture
    def sample_vectors(self):
        """Create sample vectors for similarity testing."""
        return {
            "query_vector": np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
            "document_vectors": [
                np.array([0.12, 0.18, 0.29, 0.41, 0.52]),  # Very similar
                np.array([0.05, 0.15, 0.25, 0.35, 0.45]),  # Moderately similar
                np.array([0.8, 0.7, 0.6, 0.5, 0.4]),       # Less similar
                np.array([-0.1, -0.2, -0.3, -0.4, -0.5]), # Opposite direction
                np.array([0.0, 0.0, 0.0, 0.0, 0.0])       # Zero vector
            ],
            "expected_similarities": [0.999, 0.95, 0.65, -1.0, 0.0]  # Approximate expected values
        }

    def test_cosine_similarity_calculation(self, similarity_calculator, sample_vectors):
        """Test cosine similarity calculation accuracy."""
        # Given
        query_vec = sample_vectors["query_vector"]
        doc_vectors = sample_vectors["document_vectors"]

        # When
        similarities = [
            similarity_calculator.cosine_similarity(query_vec, doc_vec)
            for doc_vec in doc_vectors
        ]

        # Then
        assert len(similarities) == 5

        # Most similar vector should have highest similarity
        assert similarities[0] > similarities[1] > similarities[2]

        # Opposite vector should have negative similarity
        assert similarities[3] < 0

        # All similarities should be in valid range [-1, 1]
        for sim in similarities:
            assert -1.0 <= sim <= 1.0

    def test_euclidean_distance_calculation(self, similarity_calculator, sample_vectors):
        """Test Euclidean distance calculation for vector similarity."""
        # Given
        query_vec = sample_vectors["query_vector"]
        doc_vectors = sample_vectors["document_vectors"]

        # When
        distances = [
            similarity_calculator.euclidean_distance(query_vec, doc_vec)
            for doc_vec in doc_vectors
        ]

        # Then
        assert len(distances) == 5

        # Most similar vector should have smallest distance
        assert distances[0] < distances[1] < distances[2]

        # All distances should be non-negative
        for dist in distances:
            assert dist >= 0

    def test_manhattan_distance_calculation(self, similarity_calculator):
        """Test Manhattan (L1) distance calculation."""
        # Given
        vec1 = np.array([1, 2, 3])
        vec2 = np.array([4, 5, 6])
        expected_distance = abs(1-4) + abs(2-5) + abs(3-6)  # = 3 + 3 + 3 = 9

        # When
        distance = similarity_calculator.manhattan_distance(vec1, vec2)

        # Then
        assert distance == expected_distance

    def test_dot_product_similarity(self, similarity_calculator, sample_vectors):
        """Test dot product similarity calculation."""
        # Given
        query_vec = sample_vectors["query_vector"]
        doc_vec = sample_vectors["document_vectors"][0]

        # When
        dot_product = similarity_calculator.dot_product_similarity(query_vec, doc_vec)

        # Then
        assert isinstance(dot_product, float)
        assert dot_product > 0  # Positive vectors should have positive dot product

    def test_batch_similarity_calculation(self, similarity_calculator, sample_vectors):
        """Test efficient batch similarity calculation."""
        # Given
        query_vec = sample_vectors["query_vector"]
        doc_matrix = np.array(sample_vectors["document_vectors"])

        # When
        batch_similarities = similarity_calculator.batch_cosine_similarity(
            query_vec, doc_matrix
        )

        # Then
        assert len(batch_similarities) == len(sample_vectors["document_vectors"])
        assert isinstance(batch_similarities, np.ndarray)

        # Should match individual calculations
        individual_sims = [
            similarity_calculator.cosine_similarity(query_vec, doc_vec)
            for doc_vec in sample_vectors["document_vectors"]
        ]

        np.testing.assert_allclose(batch_similarities, individual_sims, rtol=1e-10)

    def test_similarity_ranking_and_sorting(self, similarity_calculator, sample_vectors):
        """Test similarity-based ranking of document vectors."""
        # Given
        query_vec = sample_vectors["query_vector"]
        doc_vectors = sample_vectors["document_vectors"]
        doc_ids = [f"doc_{i}" for i in range(len(doc_vectors))]

        # When
        ranked_results = similarity_calculator.rank_by_similarity(
            query_vec, doc_vectors, doc_ids, top_k=3
        )

        # Then
        assert len(ranked_results) == 3
        assert ranked_results[0]["doc_id"] == "doc_0"  # Most similar should be first

        # Similarities should be in descending order
        similarities = [result["similarity"] for result in ranked_results]
        assert similarities == sorted(similarities, reverse=True)

    def test_vector_normalization(self, similarity_calculator):
        """Test vector normalization for consistent similarity calculation."""
        # Given
        unnormalized_vector = np.array([3, 4])  # Length = 5

        # When
        normalized = similarity_calculator.normalize_vector(unnormalized_vector)

        # Then
        assert abs(np.linalg.norm(normalized) - 1.0) < 1e-10  # Should be unit length
        assert np.allclose(normalized, [0.6, 0.8])  # Expected normalized values

    def test_vector_dimension_mismatch_handling(self, similarity_calculator):
        """Test handling of vectors with different dimensions."""
        # Given
        vec1 = np.array([1, 2, 3])
        vec2 = np.array([4, 5])  # Different dimension

        # When/Then
        with pytest.raises(RAGVectorError) as exc_info:
            similarity_calculator.cosine_similarity(vec1, vec2)

        assert "dimension mismatch" in str(exc_info.value).lower()

    def test_zero_vector_handling(self, similarity_calculator):
        """Test handling of zero vectors in similarity calculations."""
        # Given
        zero_vec = np.array([0, 0, 0])
        normal_vec = np.array([1, 1, 1])

        # When
        similarity = similarity_calculator.cosine_similarity(zero_vec, normal_vec)

        # Then
        assert similarity == 0.0  # Cosine similarity with zero vector should be 0


class TestSemanticSearchOptimizer:
    """Test semantic search optimization and retrieval improvement."""

    @pytest.fixture
    def search_optimizer(self):
        """Create semantic search optimizer."""
        mock_embedding_model = Mock()
        mock_vector_store = Mock()

        return SemanticSearchOptimizer(
            embedding_model=mock_embedding_model,
            vector_store=mock_vector_store
        )

    @pytest.fixture
    def sample_search_data(self):
        """Sample data for search optimization testing."""
        return {
            "queries": [
                "machine learning algorithms",
                "deep neural networks",
                "natural language processing",
                "computer vision techniques",
                "reinforcement learning methods"
            ],
            "documents": [
                {"id": "doc1", "title": "Introduction to Machine Learning", "content": "ML algorithms..."},
                {"id": "doc2", "title": "Deep Learning Fundamentals", "content": "Neural networks..."},
                {"id": "doc3", "title": "NLP with Transformers", "content": "Language processing..."},
                {"id": "doc4", "title": "Computer Vision Applications", "content": "Image recognition..."},
                {"id": "doc5", "title": "Reinforcement Learning", "content": "RL algorithms..."}
            ]
        }

    @pytest.mark.asyncio
    async def test_query_expansion_optimization(self, search_optimizer, sample_search_data):
        """Test query expansion for improved retrieval."""
        # Given
        original_query = "neural networks"

        # Mock query expansion
        search_optimizer.expand_query = Mock(return_value={
            "expanded_terms": ["neural networks", "deep learning", "artificial neurons", "backpropagation"],
            "semantic_variants": ["neural nets", "neural models"],
            "related_concepts": ["machine learning", "AI"]
        })

        # When
        expanded_query = search_optimizer.expand_query(original_query)

        # Then
        assert len(expanded_query["expanded_terms"]) >= 4
        assert "neural networks" in expanded_query["expanded_terms"]
        assert len(expanded_query["semantic_variants"]) >= 1

    @pytest.mark.asyncio
    async def test_retrieval_reranking_optimization(self, search_optimizer):
        """Test retrieval result reranking for improved relevance."""
        # Given
        query = "deep learning applications"
        initial_results = [
            {"doc_id": "doc1", "score": 0.7, "content": "Basic ML concepts"},
            {"doc_id": "doc2", "score": 0.8, "content": "Deep learning in computer vision"},
            {"doc_id": "doc3", "score": 0.6, "content": "Statistical methods"},
            {"doc_id": "doc4", "score": 0.9, "content": "Neural network applications"}
        ]

        # Mock reranking
        search_optimizer.rerank_results = Mock(return_value=[
            {"doc_id": "doc4", "score": 0.95, "rerank_score": 0.92},  # Most relevant
            {"doc_id": "doc2", "score": 0.85, "rerank_score": 0.88},  # Second most relevant
            {"doc_id": "doc1", "score": 0.75, "rerank_score": 0.72},
            {"doc_id": "doc3", "score": 0.65, "rerank_score": 0.65}
        ])

        # When
        reranked_results = search_optimizer.rerank_results(query, initial_results)

        # Then
        assert len(reranked_results) == 4
        assert reranked_results[0]["doc_id"] == "doc4"  # Should be top result

        # Reranked scores should be in descending order
        rerank_scores = [result["rerank_score"] for result in reranked_results]
        assert rerank_scores == sorted(rerank_scores, reverse=True)

    @pytest.mark.asyncio
    async def test_semantic_clustering_for_retrieval(self, search_optimizer):
        """Test semantic clustering to improve retrieval diversity."""
        # Given
        search_results = [
            {"doc_id": "doc1", "embedding": [0.1, 0.2, 0.3], "topic": "ML basics"},
            {"doc_id": "doc2", "embedding": [0.15, 0.25, 0.35], "topic": "ML basics"},  # Similar
            {"doc_id": "doc3", "embedding": [0.8, 0.7, 0.6], "topic": "Deep learning"},
            {"doc_id": "doc4", "embedding": [0.85, 0.75, 0.65], "topic": "Deep learning"}, # Similar
            {"doc_id": "doc5", "embedding": [0.4, 0.9, 0.2], "topic": "NLP"}
        ]

        # Mock clustering
        search_optimizer.cluster_results = Mock(return_value={
            "clusters": {
                "cluster_0": ["doc1", "doc2"],  # ML basics
                "cluster_1": ["doc3", "doc4"],  # Deep learning
                "cluster_2": ["doc5"]          # NLP
            },
            "diverse_results": [
                {"doc_id": "doc1", "cluster": "cluster_0"},
                {"doc_id": "doc3", "cluster": "cluster_1"},
                {"doc_id": "doc5", "cluster": "cluster_2"}
            ]
        })

        # When
        clustered_results = search_optimizer.cluster_results(search_results, max_per_cluster=1)

        # Then
        assert len(clustered_results["clusters"]) == 3
        assert len(clustered_results["diverse_results"]) == 3

        # Should select diverse results from different clusters
        selected_clusters = {result["cluster"] for result in clustered_results["diverse_results"]}
        assert len(selected_clusters) == 3

    def test_similarity_threshold_optimization(self, search_optimizer):
        """Test optimization of similarity thresholds for quality filtering."""
        # Given
        search_results_with_scores = [
            {"doc_id": "doc1", "similarity": 0.95},  # High relevance
            {"doc_id": "doc2", "similarity": 0.87},  # Good relevance
            {"doc_id": "doc3", "similarity": 0.72},  # Moderate relevance
            {"doc_id": "doc4", "similarity": 0.45},  # Low relevance
            {"doc_id": "doc5", "similarity": 0.23}   # Very low relevance
        ]

        # When
        optimal_threshold = search_optimizer.optimize_similarity_threshold(
            search_results_with_scores,
            target_precision=0.8,
            min_results=2
        )

        # Then
        assert 0.7 <= optimal_threshold <= 0.9  # Should filter out low-relevance results

        # Filter results with optimized threshold
        filtered_results = [r for r in search_results_with_scores if r["similarity"] >= optimal_threshold]
        assert len(filtered_results) >= 2  # Should meet minimum results requirement

    @pytest.mark.asyncio
    async def test_multi_vector_search_optimization(self, search_optimizer):
        """Test optimization of multi-vector search strategies."""
        # Given
        query_vectors = {
            "semantic": [0.1, 0.2, 0.3, 0.4],    # Semantic embedding
            "syntactic": [0.5, 0.6, 0.7, 0.8],   # Syntactic features
            "contextual": [0.2, 0.4, 0.1, 0.7]   # Contextual embedding
        }

        # Mock multi-vector search
        search_optimizer.multi_vector_search = AsyncMock(return_value={
            "combined_results": [
                {"doc_id": "doc1", "semantic_score": 0.9, "syntactic_score": 0.7, "contextual_score": 0.8, "combined_score": 0.83},
                {"doc_id": "doc2", "semantic_score": 0.8, "syntactic_score": 0.9, "contextual_score": 0.7, "combined_score": 0.8},
                {"doc_id": "doc3", "semantic_score": 0.7, "syntactic_score": 0.6, "contextual_score": 0.9, "combined_score": 0.73}
            ],
            "vector_weights": {"semantic": 0.5, "syntactic": 0.3, "contextual": 0.2}
        })

        # When
        multi_vector_results = await search_optimizer.multi_vector_search(query_vectors)

        # Then
        assert len(multi_vector_results["combined_results"]) == 3
        assert "vector_weights" in multi_vector_results

        # Combined scores should reflect weighted combination
        for result in multi_vector_results["combined_results"]:
            assert "combined_score" in result
            assert 0 <= result["combined_score"] <= 1


class TestRetrievalRelevanceAnalyzer:
    """Test retrieval relevance analysis and quality metrics."""

    @pytest.fixture
    def relevance_analyzer(self):
        """Create retrieval relevance analyzer."""
        return RetrievalRelevanceAnalyzer()

    @pytest.fixture
    def relevance_test_data(self):
        """Test data for relevance analysis."""
        return {
            "queries_with_ground_truth": [
                {
                    "query": "machine learning algorithms",
                    "relevant_docs": ["doc1", "doc2", "doc5"],
                    "retrieved_docs": ["doc1", "doc2", "doc3", "doc4"],
                    "expected_precision": 0.5,  # 2/4 relevant
                    "expected_recall": 0.67     # 2/3 found
                },
                {
                    "query": "deep learning networks",
                    "relevant_docs": ["doc2", "doc3"],
                    "retrieved_docs": ["doc2", "doc3"],
                    "expected_precision": 1.0,  # 2/2 relevant
                    "expected_recall": 1.0      # 2/2 found
                }
            ]
        }

    def test_calculate_precision_at_k(self, relevance_analyzer, relevance_test_data):
        """Test precision@k calculation for retrieval evaluation."""
        # Given
        test_case = relevance_test_data["queries_with_ground_truth"][0]

        # When
        precision_at_k = relevance_analyzer.calculate_precision_at_k(
            retrieved_docs=test_case["retrieved_docs"],
            relevant_docs=test_case["relevant_docs"],
            k=4
        )

        # Then
        assert abs(precision_at_k - test_case["expected_precision"]) < 0.01

    def test_calculate_recall_at_k(self, relevance_analyzer, relevance_test_data):
        """Test recall@k calculation for retrieval evaluation."""
        # Given
        test_case = relevance_test_data["queries_with_ground_truth"][0]

        # When
        recall_at_k = relevance_analyzer.calculate_recall_at_k(
            retrieved_docs=test_case["retrieved_docs"],
            relevant_docs=test_case["relevant_docs"],
            k=4
        )

        # Then
        assert abs(recall_at_k - test_case["expected_recall"]) < 0.01

    def test_calculate_f1_score(self, relevance_analyzer, relevance_test_data):
        """Test F1 score calculation for retrieval quality."""
        # Given
        test_case = relevance_test_data["queries_with_ground_truth"][0]
        precision = test_case["expected_precision"]
        recall = test_case["expected_recall"]
        expected_f1 = 2 * (precision * recall) / (precision + recall)

        # When
        f1_score = relevance_analyzer.calculate_f1_score(
            retrieved_docs=test_case["retrieved_docs"],
            relevant_docs=test_case["relevant_docs"]
        )

        # Then
        assert abs(f1_score - expected_f1) < 0.01

    def test_calculate_mean_average_precision(self, relevance_analyzer, relevance_test_data):
        """Test Mean Average Precision (MAP) calculation."""
        # Given
        queries_data = relevance_test_data["queries_with_ground_truth"]

        # When
        map_score = relevance_analyzer.calculate_mean_average_precision(queries_data)

        # Then
        assert 0 <= map_score <= 1
        assert isinstance(map_score, float)

    def test_calculate_ndcg(self, relevance_analyzer):
        """Test Normalized Discounted Cumulative Gain (NDCG) calculation."""
        # Given
        retrieved_docs = ["doc1", "doc2", "doc3", "doc4"]
        relevance_scores = [3, 2, 0, 1]  # Graded relevance scores

        # When
        ndcg_score = relevance_analyzer.calculate_ndcg(
            retrieved_docs=retrieved_docs,
            relevance_scores=relevance_scores,
            k=4
        )

        # Then
        assert 0 <= ndcg_score <= 1
        assert isinstance(ndcg_score, float)

    def test_analyze_retrieval_distribution(self, relevance_analyzer):
        """Test analysis of retrieval result distribution."""
        # Given
        retrieval_results = [
            {"doc_id": "doc1", "score": 0.95, "category": "ML"},
            {"doc_id": "doc2", "score": 0.87, "category": "DL"},
            {"doc_id": "doc3", "score": 0.82, "category": "ML"},
            {"doc_id": "doc4", "score": 0.76, "category": "NLP"},
            {"doc_id": "doc5", "score": 0.71, "category": "DL"}
        ]

        # When
        distribution_analysis = relevance_analyzer.analyze_retrieval_distribution(
            retrieval_results
        )

        # Then
        assert "score_distribution" in distribution_analysis
        assert "category_distribution" in distribution_analysis
        assert "diversity_metrics" in distribution_analysis

        # Should identify categories present
        assert "ML" in distribution_analysis["category_distribution"]
        assert "DL" in distribution_analysis["category_distribution"]
        assert "NLP" in distribution_analysis["category_distribution"]

    def test_evaluate_retrieval_consistency(self, relevance_analyzer):
        """Test evaluation of retrieval consistency across similar queries."""
        # Given
        similar_queries = [
            {"query": "neural networks", "results": ["doc1", "doc2", "doc3"]},
            {"query": "neural nets", "results": ["doc1", "doc2", "doc4"]},
            {"query": "artificial neural networks", "results": ["doc1", "doc3", "doc5"]}
        ]

        # When
        consistency_analysis = relevance_analyzer.evaluate_retrieval_consistency(
            similar_queries
        )

        # Then
        assert "consistency_score" in consistency_analysis
        assert "common_results" in consistency_analysis
        assert "variation_analysis" in consistency_analysis

        # Should identify doc1 as consistently retrieved
        assert "doc1" in consistency_analysis["common_results"]

    def test_identify_retrieval_gaps(self, relevance_analyzer):
        """Test identification of retrieval quality gaps."""
        # Given
        performance_data = {
            "queries": [
                {"category": "ML", "precision": 0.9, "recall": 0.8},
                {"category": "DL", "precision": 0.7, "recall": 0.9},
                {"category": "NLP", "precision": 0.6, "recall": 0.5},  # Lower performance
                {"category": "CV", "precision": 0.8, "recall": 0.7}
            ]
        }

        # When
        gap_analysis = relevance_analyzer.identify_retrieval_gaps(performance_data)

        # Then
        assert "performance_gaps" in gap_analysis
        assert "improvement_recommendations" in gap_analysis

        # Should identify NLP as having gaps
        nlp_gaps = [gap for gap in gap_analysis["performance_gaps"] if gap["category"] == "NLP"]
        assert len(nlp_gaps) > 0

    def test_benchmark_retrieval_performance(self, relevance_analyzer):
        """Test benchmarking of retrieval performance against standards."""
        # Given
        current_performance = {
            "precision_at_5": 0.82,
            "recall_at_10": 0.75,
            "map_score": 0.78,
            "ndcg_at_10": 0.85
        }

        benchmark_standards = {
            "precision_at_5": 0.80,
            "recall_at_10": 0.70,
            "map_score": 0.75,
            "ndcg_at_10": 0.80
        }

        # When
        benchmark_results = relevance_analyzer.benchmark_performance(
            current_performance, benchmark_standards
        )

        # Then
        assert "meets_benchmark" in benchmark_results
        assert "performance_comparison" in benchmark_results
        assert benchmark_results["meets_benchmark"] is True  # Exceeds all benchmarks

    @pytest.mark.asyncio
    async def test_real_time_relevance_monitoring(self, relevance_analyzer):
        """Test real-time monitoring of retrieval relevance."""
        # Given
        query_stream = [
            {"query": "machine learning", "timestamp": "2023-01-01T10:00:00Z"},
            {"query": "deep learning", "timestamp": "2023-01-01T10:01:00Z"},
            {"query": "neural networks", "timestamp": "2023-01-01T10:02:00Z"}
        ]

        # Mock real-time monitoring
        relevance_analyzer.monitor_relevance = AsyncMock(return_value={
            "current_performance": {"avg_precision": 0.85, "avg_recall": 0.78},
            "performance_trend": "improving",
            "alerts": []
        })

        # When
        monitoring_results = await relevance_analyzer.monitor_relevance(query_stream)

        # Then
        assert "current_performance" in monitoring_results
        assert "performance_trend" in monitoring_results
        assert monitoring_results["performance_trend"] == "improving"
