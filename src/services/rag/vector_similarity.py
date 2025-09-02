"""
Vector Similarity and Retrieval Module

This module provides vector similarity calculations, semantic search optimization,
and retrieval relevance analysis for RAG systems.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class VectorSimilarityCalculator:
    """Calculator for vector similarity metrics."""

    def __init__(self):
        """Initialize the vector similarity calculator."""
        self.supported_metrics = ['cosine', 'euclidean', 'manhattan', 'dot_product']

    def calculate_cosine_similarity(self, vector1: list[float], vector2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        if not vector1 or not vector2:
            return 0.0

        # Convert to numpy arrays
        v1 = np.array(vector1)
        v2 = np.array(vector2)

        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def calculate_euclidean_distance(self, vector1: list[float], vector2: list[float]) -> float:
        """
        Calculate Euclidean distance between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Euclidean distance
        """
        if not vector1 or not vector2:
            return float('inf')

        v1 = np.array(vector1)
        v2 = np.array(vector2)

        return float(np.linalg.norm(v1 - v2))

    def calculate_dot_product(self, vector1: list[float], vector2: list[float]) -> float:
        """
        Calculate dot product between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Dot product value
        """
        if not vector1 or not vector2:
            return 0.0

        v1 = np.array(vector1)
        v2 = np.array(vector2)

        return float(np.dot(v1, v2))

    def batch_similarity(self, query_vector: list[float],
                        candidate_vectors: list[list[float]],
                        metric: str = 'cosine') -> list[float]:
        """
        Calculate similarity between query vector and multiple candidates.
        
        Args:
            query_vector: Query vector
            candidate_vectors: List of candidate vectors
            metric: Similarity metric to use
            
        Returns:
            List of similarity scores
        """
        similarities = []

        for candidate in candidate_vectors:
            if metric == 'cosine':
                sim = self.calculate_cosine_similarity(query_vector, candidate)
            elif metric == 'euclidean':
                # Convert distance to similarity (lower distance = higher similarity)
                distance = self.calculate_euclidean_distance(query_vector, candidate)
                sim = 1.0 / (1.0 + distance) if distance != float('inf') else 0.0
            elif metric == 'dot_product':
                sim = self.calculate_dot_product(query_vector, candidate)
            else:
                sim = 0.0

            similarities.append(sim)

        return similarities


class SemanticSearchOptimizer:
    """Optimizer for semantic search performance."""

    def __init__(self):
        """Initialize the semantic search optimizer."""
        self.similarity_calculator = VectorSimilarityCalculator()
        self.optimization_strategies = ['threshold_tuning', 'reranking', 'query_expansion']

    def optimize_retrieval_threshold(self, query_vector: list[float],
                                   candidate_vectors: list[list[float]],
                                   relevance_scores: list[float]) -> float:
        """
        Optimize similarity threshold for retrieval.
        
        Args:
            query_vector: Query vector
            candidate_vectors: Candidate vectors
            relevance_scores: Known relevance scores
            
        Returns:
            Optimal threshold value
        """
        # Calculate similarities
        similarities = self.similarity_calculator.batch_similarity(
            query_vector, candidate_vectors, 'cosine'
        )

        # Find optimal threshold by maximizing precision/recall balance
        thresholds = np.linspace(0.1, 0.9, 9)
        best_threshold = 0.5
        best_f1 = 0.0

        for threshold in thresholds:
            # Calculate precision and recall at this threshold
            retrieved = [1 if sim >= threshold else 0 for sim in similarities]
            relevant = [1 if score >= 0.7 else 0 for score in relevance_scores]

            if sum(retrieved) == 0:
                continue

            # Calculate precision, recall, and F1
            tp = sum(r and rel for r, rel in zip(retrieved, relevant, strict=False))
            precision = tp / sum(retrieved) if sum(retrieved) > 0 else 0
            recall = tp / sum(relevant) if sum(relevant) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        return best_threshold

    def rerank_results(self, query_vector: list[float],
                      candidate_vectors: list[list[float]],
                      initial_scores: list[float],
                      contexts: Optional[list[str]] = None) -> list[int]:
        """
        Rerank search results using multiple signals.
        
        Args:
            query_vector: Query vector
            candidate_vectors: Candidate vectors
            initial_scores: Initial similarity scores
            contexts: Optional context information
            
        Returns:
            List of reranked indices
        """
        # Calculate additional similarity metrics
        cosine_scores = self.similarity_calculator.batch_similarity(
            query_vector, candidate_vectors, 'cosine'
        )

        # Combine scores (weighted average)
        combined_scores = []
        for i, (initial, cosine) in enumerate(zip(initial_scores, cosine_scores, strict=False)):
            # Weight: 60% initial, 40% cosine similarity
            combined = 0.6 * initial + 0.4 * cosine
            combined_scores.append((combined, i))

        # Sort by combined score (descending)
        combined_scores.sort(key=lambda x: x[0], reverse=True)

        # Return reranked indices
        return [idx for _, idx in combined_scores]

    def expand_query(self, original_query: str, similar_terms: list[str]) -> str:
        """
        Expand query with similar terms for better retrieval.
        
        Args:
            original_query: Original query text
            similar_terms: List of similar terms
            
        Returns:
            Expanded query
        """
        # Simple query expansion by adding related terms
        expanded_terms = [original_query] + similar_terms[:3]  # Limit to top 3
        return " ".join(expanded_terms)


class RetrievalRelevanceAnalyzer:
    """Analyzer for retrieval relevance and quality metrics."""

    def __init__(self):
        """Initialize the retrieval relevance analyzer."""
        self.similarity_calculator = VectorSimilarityCalculator()

    def analyze_retrieval_quality(self, query_vector: list[float],
                                 retrieved_vectors: list[list[float]],
                                 ground_truth_relevant: list[int]) -> dict[str, Any]:
        """
        Analyze quality of retrieval results.
        
        Args:
            query_vector: Query vector
            retrieved_vectors: Retrieved document vectors
            ground_truth_relevant: Indices of truly relevant documents
            
        Returns:
            Quality metrics
        """
        # Calculate similarities
        similarities = self.similarity_calculator.batch_similarity(
            query_vector, retrieved_vectors, 'cosine'
        )

        # Calculate metrics
        total_retrieved = len(retrieved_vectors)
        total_relevant = len(ground_truth_relevant)

        # Assume documents with similarity > 0.7 are considered retrieved as relevant
        threshold = 0.7
        predicted_relevant = [i for i, sim in enumerate(similarities) if sim >= threshold]

        # Calculate precision, recall, F1
        true_positives = len(set(predicted_relevant) & set(ground_truth_relevant))
        precision = true_positives / len(predicted_relevant) if predicted_relevant else 0
        recall = true_positives / total_relevant if total_relevant > 0 else 0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # Calculate average similarity
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0

        # Calculate similarity distribution
        high_sim = sum(1 for s in similarities if s >= 0.8)
        medium_sim = sum(1 for s in similarities if 0.5 <= s < 0.8)
        low_sim = sum(1 for s in similarities if s < 0.5)

        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'average_similarity': avg_similarity,
            'total_retrieved': total_retrieved,
            'total_relevant': total_relevant,
            'true_positives': true_positives,
            'similarity_distribution': {
                'high': high_sim,
                'medium': medium_sim,
                'low': low_sim
            }
        }

    def calculate_mrr(self, query_vector: list[float],
                     retrieved_vectors: list[list[float]],
                     relevant_indices: list[int]) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR).
        
        Args:
            query_vector: Query vector
            retrieved_vectors: Retrieved document vectors in rank order
            relevant_indices: Indices of relevant documents
            
        Returns:
            MRR score
        """
        similarities = self.similarity_calculator.batch_similarity(
            query_vector, retrieved_vectors, 'cosine'
        )

        # Sort by similarity (descending) to get ranking
        ranked_indices = sorted(range(len(similarities)),
                              key=lambda i: similarities[i], reverse=True)

        # Find first relevant document rank
        for rank, doc_idx in enumerate(ranked_indices, 1):
            if doc_idx in relevant_indices:
                return 1.0 / rank

        return 0.0  # No relevant documents found

    def calculate_ndcg(self, query_vector: list[float],
                      retrieved_vectors: list[list[float]],
                      relevance_scores: list[float],
                      k: int = 10) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain (NDCG@k).
        
        Args:
            query_vector: Query vector
            retrieved_vectors: Retrieved document vectors
            relevance_scores: Ground truth relevance scores
            k: Number of top documents to consider
            
        Returns:
            NDCG@k score
        """
        similarities = self.similarity_calculator.batch_similarity(
            query_vector, retrieved_vectors, 'cosine'
        )

        # Sort by similarity (descending) to get ranking
        ranked_items = sorted(zip(similarities, relevance_scores, strict=False), reverse=True)[:k]

        # Calculate DCG
        dcg = 0.0
        for i, (_, relevance) in enumerate(ranked_items):
            dcg += relevance / np.log2(i + 2)  # i+2 because log2(1) = 0

        # Calculate IDCG (perfect ranking)
        ideal_relevances = sorted(relevance_scores, reverse=True)[:k]
        idcg = 0.0
        for i, relevance in enumerate(ideal_relevances):
            idcg += relevance / np.log2(i + 2)

        # Calculate NDCG
        if idcg == 0:
            return 0.0
        return dcg / idcg
