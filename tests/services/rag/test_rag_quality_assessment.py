"""
RAG Query Quality Assessment Tests

Comprehensive tests for evaluating RAG query accuracy, response quality,
and citation reliability to ensure high-quality AI-powered responses.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.services.rag.quality_assessment import (
    CitationAccuracyValidator,
    RAGQualityAssessment,
    SemanticRelevanceScorer,
)


class TestRAGQualityAssessment:
    """Test suite for RAG response quality assessment and validation."""

    @pytest.fixture
    def sample_document_content(self):
        """Sample document content for quality testing."""
        return {
            "title": "Advances in Machine Learning",
            "content": """
            Machine learning has revolutionized artificial intelligence by enabling
            computers to learn from data without explicit programming. Deep learning,
            a subset of machine learning, uses neural networks with multiple layers
            to model and understand complex patterns.

            Key findings include:
            1. Transformer architectures have significantly improved natural language processing
            2. Convolutional neural networks excel at image recognition tasks
            3. Reinforcement learning has achieved superhuman performance in games

            The implications for future research are substantial, particularly in
            areas such as autonomous vehicles, medical diagnosis, and scientific discovery.
            """,
            "citations": [
                "Vaswani et al. (2017). Attention is All You Need. NIPS.",
                "LeCun et al. (1998). Gradient-based learning applied to document recognition. Proceedings of IEEE.",
                "Silver et al. (2016). Mastering the game of Go with deep neural networks. Nature."
            ]
        }

    @pytest.fixture
    def quality_assessment_service(self):
        """Create RAG quality assessment service."""
        mock_semantic_scorer = Mock()
        mock_citation_validator = Mock()
        mock_relevance_analyzer = Mock()

        return RAGQualityAssessment(
            semantic_scorer=mock_semantic_scorer,
            citation_validator=mock_citation_validator,
            relevance_analyzer=mock_relevance_analyzer
        )

    @pytest.fixture
    def sample_rag_responses(self):
        """Sample RAG responses for quality evaluation."""
        return [
            {
                "query": "What are the key advances in machine learning?",
                "answer": """Machine learning has seen significant advances, particularly in deep learning
                architectures. Transformer models have revolutionized natural language processing,
                while convolutional neural networks excel at image recognition. Reinforcement learning
                has achieved superhuman performance in complex games like Go.""",
                "sources": [
                    {"page": 1, "confidence": 0.95, "text": "Transformer architectures have significantly improved..."},
                    {"page": 1, "confidence": 0.88, "text": "Convolutional neural networks excel at image recognition..."},
                    {"page": 2, "confidence": 0.92, "text": "Reinforcement learning has achieved superhuman performance..."}
                ],
                "expected_quality": "high"
            },
            {
                "query": "What is deep learning?",
                "answer": """Deep learning is a subset of machine learning that uses neural networks
                with multiple layers to model complex patterns in data.""",
                "sources": [
                    {"page": 1, "confidence": 0.93, "text": "Deep learning, a subset of machine learning..."}
                ],
                "expected_quality": "medium"
            },
            {
                "query": "What color is the sky?",
                "answer": """I cannot find relevant information about sky color in the provided
                machine learning document.""",
                "sources": [],
                "expected_quality": "appropriate_rejection"
            }
        ]

    def test_response_quality_metrics_initialization(self, quality_assessment_service):
        """Test response quality metrics calculation setup."""
        assert quality_assessment_service.semantic_scorer is not None
        assert quality_assessment_service.citation_validator is not None
        assert quality_assessment_service.relevance_analyzer is not None

    @pytest.mark.asyncio
    async def test_evaluate_response_relevance(self, quality_assessment_service, sample_rag_responses):
        """Test evaluation of response relevance to query."""
        # Given
        response = sample_rag_responses[0]  # High-quality response

        # Mock semantic similarity scoring
        quality_assessment_service.semantic_scorer.calculate_similarity.return_value = 0.85

        # When
        relevance_score = await quality_assessment_service.evaluate_response_relevance(
            query=response["query"],
            answer=response["answer"],
            source_texts=[s["text"] for s in response["sources"]]
        )

        # Then
        assert 0.0 <= relevance_score <= 1.0
        assert relevance_score >= 0.8  # High-quality response should score well
        quality_assessment_service.semantic_scorer.calculate_similarity.assert_called()

    @pytest.mark.asyncio
    async def test_evaluate_citation_accuracy(self, quality_assessment_service, sample_document_content):
        """Test evaluation of citation accuracy and reliability."""
        # Given
        response_with_claims = """Transformer architectures were introduced in 2017 by Vaswani et al.
        and have revolutionized natural language processing. CNNs were developed by LeCun in 1998
        for document recognition."""

        expected_citations = sample_document_content["citations"]

        # Mock citation validation
        quality_assessment_service.citation_validator.validate_claims.return_value = {
            "accuracy_score": 0.9,
            "verified_claims": 2,
            "total_claims": 2,
            "citation_matches": [
                {"claim": "Transformer architectures...2017...Vaswani", "citation": expected_citations[0], "match": True},
                {"claim": "CNNs...LeCun...1998", "citation": expected_citations[1], "match": True}
            ]
        }

        # When
        citation_accuracy = await quality_assessment_service.evaluate_citation_accuracy(
            response_text=response_with_claims,
            source_citations=expected_citations
        )

        # Then
        assert citation_accuracy["accuracy_score"] == 0.9
        assert citation_accuracy["verified_claims"] == 2
        assert len(citation_accuracy["citation_matches"]) == 2

    @pytest.mark.asyncio
    async def test_evaluate_completeness_and_coverage(self, quality_assessment_service, sample_rag_responses):
        """Test evaluation of response completeness and topic coverage."""
        # Given
        response = sample_rag_responses[0]
        query_intent_keywords = ["advances", "machine learning", "key", "important"]

        # Mock completeness analysis
        quality_assessment_service.relevance_analyzer.analyze_coverage.return_value = {
            "coverage_score": 0.85,
            "covered_topics": ["deep learning", "transformers", "CNNs", "reinforcement learning"],
            "missing_topics": [],
            "keyword_coverage": 0.9
        }

        # When
        completeness_metrics = await quality_assessment_service.evaluate_completeness(
            query=response["query"],
            answer=response["answer"],
            source_content=" ".join([s["text"] for s in response["sources"]]),
            intent_keywords=query_intent_keywords
        )

        # Then
        assert completeness_metrics["coverage_score"] >= 0.8
        assert completeness_metrics["keyword_coverage"] >= 0.8
        assert len(completeness_metrics["covered_topics"]) >= 3

    @pytest.mark.asyncio
    async def test_detect_hallucination_and_fabrication(self, quality_assessment_service):
        """Test detection of AI hallucination and information fabrication."""
        # Given - response with fabricated information
        fabricated_response = """According to the document, machine learning was invented in 1955
        by John McCarthy at MIT, and the first neural network had 10,000 layers."""

        limited_source_content = """Machine learning has revolutionized artificial intelligence.
        Deep learning uses neural networks with multiple layers."""

        # Mock hallucination detection
        quality_assessment_service.relevance_analyzer.detect_fabrication.return_value = {
            "hallucination_detected": True,
            "fabricated_claims": [
                {"claim": "invented in 1955 by John McCarthy", "source_support": False},
                {"claim": "first neural network had 10,000 layers", "source_support": False}
            ],
            "confidence": 0.85
        }

        # When
        hallucination_analysis = await quality_assessment_service.detect_hallucination(
            response_text=fabricated_response,
            source_content=limited_source_content
        )

        # Then
        assert hallucination_analysis["hallucination_detected"] is True
        assert len(hallucination_analysis["fabricated_claims"]) == 2
        assert hallucination_analysis["confidence"] >= 0.8

    @pytest.mark.asyncio
    async def test_evaluate_response_consistency(self, quality_assessment_service):
        """Test evaluation of response consistency across multiple queries."""
        # Given - multiple related queries and responses
        query_response_pairs = [
            ("What is deep learning?", "Deep learning is a subset of machine learning using neural networks."),
            ("How does deep learning work?", "Deep learning uses neural networks with multiple layers to learn patterns."),
            ("What are neural networks?", "Neural networks are computational models inspired by biological neurons.")
        ]

        # Mock consistency analysis
        quality_assessment_service.semantic_scorer.calculate_consistency.return_value = {
            "consistency_score": 0.88,
            "contradictions": [],
            "semantic_coherence": 0.92
        }

        # When
        consistency_metrics = await quality_assessment_service.evaluate_consistency(
            query_response_pairs
        )

        # Then
        assert consistency_metrics["consistency_score"] >= 0.8
        assert len(consistency_metrics["contradictions"]) == 0
        assert consistency_metrics["semantic_coherence"] >= 0.85

    @pytest.mark.asyncio
    async def test_comprehensive_quality_assessment(self, quality_assessment_service, sample_rag_responses, sample_document_content):
        """Test comprehensive quality assessment combining all metrics."""
        # Given
        response = sample_rag_responses[0]
        document_content = sample_document_content["content"]

        # Mock comprehensive assessment
        quality_assessment_service.evaluate_response_relevance = AsyncMock(return_value=0.89)
        quality_assessment_service.evaluate_citation_accuracy = AsyncMock(return_value={"accuracy_score": 0.91})
        quality_assessment_service.evaluate_completeness = AsyncMock(return_value={"coverage_score": 0.87})
        quality_assessment_service.detect_hallucination = AsyncMock(return_value={"hallucination_detected": False})

        # When
        comprehensive_score = await quality_assessment_service.comprehensive_assessment(
            query=response["query"],
            answer=response["answer"],
            sources=response["sources"],
            document_content=document_content
        )

        # Then
        assert "overall_quality_score" in comprehensive_score
        assert "relevance_score" in comprehensive_score
        assert "citation_accuracy" in comprehensive_score
        assert "completeness_score" in comprehensive_score
        assert "hallucination_risk" in comprehensive_score

        # Overall score should be high for good response
        assert comprehensive_score["overall_quality_score"] >= 0.8

    def test_quality_threshold_validation(self, quality_assessment_service):
        """Test quality threshold validation for response acceptance."""
        # Given - different quality scores
        test_cases = [
            {"scores": {"relevance": 0.95, "accuracy": 0.92, "completeness": 0.88}, "should_accept": True},
            {"scores": {"relevance": 0.65, "accuracy": 0.70, "completeness": 0.60}, "should_accept": False},
            {"scores": {"relevance": 0.85, "accuracy": 0.30, "completeness": 0.80}, "should_accept": False}
        ]

        for case in test_cases:
            # When
            meets_threshold = quality_assessment_service.meets_quality_threshold(
                quality_scores=case["scores"],
                threshold_config={
                    "min_relevance": 0.75,
                    "min_accuracy": 0.80,
                    "min_completeness": 0.70
                }
            )

            # Then
            assert meets_threshold == case["should_accept"]

    @pytest.mark.asyncio
    async def test_quality_improvement_suggestions(self, quality_assessment_service):
        """Test generation of quality improvement suggestions."""
        # Given - response with specific quality issues
        low_quality_response = {
            "query": "What are the key advances in AI?",
            "answer": "AI is good.",  # Too brief, lacks detail
            "sources": [{"text": "Brief mention", "confidence": 0.3}]  # Low confidence
        }

        # Mock improvement analysis
        quality_assessment_service.analyze_improvement_opportunities.return_value = {
            "suggestions": [
                {"issue": "Response too brief", "suggestion": "Provide more detailed explanation"},
                {"issue": "Low source confidence", "suggestion": "Use higher-confidence sources"},
                {"issue": "Missing key concepts", "suggestion": "Include more relevant terms"}
            ],
            "priority_improvements": ["Add more detail", "Improve source quality"]
        }

        # When
        improvement_suggestions = await quality_assessment_service.generate_improvement_suggestions(
            low_quality_response
        )

        # Then
        assert len(improvement_suggestions["suggestions"]) >= 3
        assert len(improvement_suggestions["priority_improvements"]) >= 2

    @pytest.mark.asyncio
    async def test_domain_specific_quality_evaluation(self, quality_assessment_service):
        """Test domain-specific quality evaluation for technical content."""
        # Given - technical query and response
        technical_query = "Explain the attention mechanism in transformers"
        technical_response = """The attention mechanism allows the model to focus on relevant
        parts of the input sequence. It uses query, key, and value matrices to compute attention scores."""

        domain_context = "machine_learning"

        # Mock domain-specific evaluation
        quality_assessment_service.evaluate_domain_specificity.return_value = {
            "domain_accuracy": 0.92,
            "technical_precision": 0.88,
            "terminology_correctness": 0.95,
            "domain_completeness": 0.85
        }

        # When
        domain_quality = await quality_assessment_service.evaluate_domain_quality(
            query=technical_query,
            response=technical_response,
            domain=domain_context
        )

        # Then
        assert domain_quality["domain_accuracy"] >= 0.9
        assert domain_quality["technical_precision"] >= 0.85
        assert domain_quality["terminology_correctness"] >= 0.9

    def test_quality_benchmarking_and_comparison(self, quality_assessment_service):
        """Test quality benchmarking against reference standards."""
        # Given - responses to benchmark
        responses_to_evaluate = [
            {"id": "resp_1", "quality_scores": {"relevance": 0.89, "accuracy": 0.92}},
            {"id": "resp_2", "quality_scores": {"relevance": 0.76, "accuracy": 0.88}},
            {"id": "resp_3", "quality_scores": {"relevance": 0.94, "accuracy": 0.85}}
        ]

        benchmark_standards = {
            "excellent": {"min_relevance": 0.90, "min_accuracy": 0.90},
            "good": {"min_relevance": 0.80, "min_accuracy": 0.85},
            "acceptable": {"min_relevance": 0.70, "min_accuracy": 0.75}
        }

        # When
        benchmark_results = quality_assessment_service.benchmark_responses(
            responses_to_evaluate, benchmark_standards
        )

        # Then
        assert len(benchmark_results["rankings"]) == 3
        assert benchmark_results["rankings"][0]["id"] == "resp_1"  # Should rank highest
        assert "quality_distribution" in benchmark_results


class TestSemanticRelevanceScorer:
    """Test semantic relevance scoring for RAG responses."""

    @pytest.fixture
    def semantic_scorer(self):
        """Create semantic relevance scorer."""
        mock_embedding_model = Mock()
        mock_embedding_model.encode.return_value = [[0.1, 0.2, 0.3], [0.15, 0.25, 0.35]]

        return SemanticRelevanceScorer(embedding_model=mock_embedding_model)

    def test_calculate_semantic_similarity(self, semantic_scorer):
        """Test semantic similarity calculation between texts."""
        # Given
        text1 = "Machine learning is a subset of artificial intelligence"
        text2 = "AI includes machine learning as a key component"

        # When
        similarity = semantic_scorer.calculate_similarity(text1, text2)

        # Then
        assert 0.0 <= similarity <= 1.0
        semantic_scorer.embedding_model.encode.assert_called()

    def test_relevance_scoring_with_context(self, semantic_scorer):
        """Test relevance scoring with document context."""
        # Given
        query = "What is deep learning?"
        response = "Deep learning uses neural networks"
        context = "Machine learning and artificial intelligence research"

        # When
        relevance_score = semantic_scorer.score_with_context(query, response, context)

        # Then
        assert "query_response_similarity" in relevance_score
        assert "response_context_alignment" in relevance_score
        assert "overall_relevance" in relevance_score

    def test_multi_document_relevance_scoring(self, semantic_scorer):
        """Test relevance scoring across multiple document sources."""
        # Given
        query = "Advances in neural networks"
        sources = [
            {"text": "CNN architectures for image processing", "weight": 0.8},
            {"text": "RNN applications in sequence modeling", "weight": 0.7},
            {"text": "Transformer models for NLP", "weight": 0.9}
        ]

        # When
        multi_doc_score = semantic_scorer.score_multi_document_relevance(query, sources)

        # Then
        assert "weighted_relevance_score" in multi_doc_score
        assert "individual_scores" in multi_doc_score
        assert len(multi_doc_score["individual_scores"]) == 3


class TestCitationAccuracyValidator:
    """Test citation accuracy validation for RAG responses."""

    @pytest.fixture
    def citation_validator(self):
        """Create citation accuracy validator."""
        return CitationAccuracyValidator()

    def test_extract_factual_claims(self, citation_validator):
        """Test extraction of factual claims from response text."""
        # Given
        response_text = """Transformers were introduced by Vaswani et al. in 2017.
        The architecture achieved state-of-the-art results on machine translation tasks."""

        # When
        claims = citation_validator.extract_factual_claims(response_text)

        # Then
        assert len(claims) >= 2
        assert any("Vaswani" in claim for claim in claims)
        assert any("2017" in claim for claim in claims)

    def test_validate_claims_against_sources(self, citation_validator):
        """Test validation of claims against source documents."""
        # Given
        claims = [
            "Transformers were introduced in 2017",
            "The model uses attention mechanisms",
            "Results improved machine translation"
        ]

        source_documents = [
            "Vaswani et al. (2017) introduced the Transformer architecture with attention mechanisms.",
            "The model achieved significant improvements in translation quality."
        ]

        # When
        validation_results = citation_validator.validate_claims_against_sources(
            claims, source_documents
        )

        # Then
        assert len(validation_results) == 3
        assert validation_results[0]["supported"] is True  # 2017 claim
        assert validation_results[1]["supported"] is True  # attention claim
        assert validation_results[2]["supported"] is True  # improvement claim

    def test_detect_citation_fabrication(self, citation_validator):
        """Test detection of fabricated or incorrect citations."""
        # Given
        response_with_fake_citation = """According to Smith et al. (2025),
        quantum neural networks will replace all traditional models."""

        available_citations = [
            "Jones et al. (2023). Advances in Neural Architecture.",
            "Brown et al. (2022). Machine Learning Trends."
        ]

        # When
        fabrication_analysis = citation_validator.detect_fabrication(
            response_with_fake_citation, available_citations
        )

        # Then
        assert fabrication_analysis["fabrication_detected"] is True
        assert "Smith et al. (2025)" in fabrication_analysis["fabricated_citations"]

    def test_citation_format_validation(self, citation_validator):
        """Test validation of citation format consistency."""
        # Given
        citations_to_validate = [
            "Smith, J. (2023). Title of Paper. Journal Name.",
            "Brown et al. 2022. Another Paper. Conference.",  # Inconsistent format
            "Davis, M. (2021). Third Paper. Publisher."
        ]

        # When
        format_analysis = citation_validator.validate_citation_formats(citations_to_validate)

        # Then
        assert format_analysis["consistent_format"] is False
        assert len(format_analysis["format_issues"]) >= 1
