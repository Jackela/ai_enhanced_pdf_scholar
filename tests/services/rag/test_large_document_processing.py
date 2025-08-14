"""
Large Document Processing and Chunking Strategy Tests

Comprehensive tests for handling large academic documents, including
memory-efficient processing, intelligent chunking strategies, and
performance optimization for multi-page PDF documents.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import time
import psutil
from pathlib import Path
import tempfile
import numpy as np
from typing import List, Dict, Any, Generator
import json

from src.services.rag.large_document_processor import (
    LargeDocumentProcessor,
    ChunkingStrategy,
    MemoryEfficientProcessor,
    AcademicDocumentProcessor
)
from src.services.rag.chunking_strategies import (
    FixedSizeChunking,
    SemanticChunking,
    StructureAwareChunking,
    AdaptiveChunking,
    CitationAwareChunking
)
from src.services.rag.exceptions import RAGProcessingError, RAGMemoryError
from src.database.models import DocumentModel


class TestLargeDocumentProcessor:
    """Test suite for large document processing and memory management."""

    @pytest.fixture
    def mock_large_pdf_content(self):
        """Mock content for large PDF documents."""
        # Simulate large academic paper content
        return {
            "text": "Large document content " * 10000,  # ~250KB of text
            "metadata": {
                "page_count": 50,
                "word_count": 25000,
                "size_mb": 15.5,
                "has_references": True,
                "has_figures": True,
                "has_tables": True
            },
            "sections": [
                {"title": "Abstract", "content": "Abstract content " * 100, "page": 1},
                {"title": "Introduction", "content": "Introduction content " * 500, "page": 2},
                {"title": "Literature Review", "content": "Literature review " * 800, "page": 5},
                {"title": "Methodology", "content": "Methodology description " * 600, "page": 12},
                {"title": "Results", "content": "Results and analysis " * 1200, "page": 20},
                {"title": "Discussion", "content": "Discussion content " * 900, "page": 35},
                {"title": "Conclusion", "content": "Conclusion summary " * 300, "page": 45},
                {"title": "References", "content": "Reference list " * 400, "page": 47}
            ],
            "citations": [f"Author{i} et al. (202{i%4})" for i in range(1, 151)]  # 150 citations
        }

    @pytest.fixture
    def document_processor(self):
        """Create large document processor with mocked dependencies."""
        mock_pdf_extractor = Mock()
        mock_memory_manager = Mock()
        mock_chunk_optimizer = Mock()

        return LargeDocumentProcessor(
            pdf_extractor=mock_pdf_extractor,
            memory_manager=mock_memory_manager,
            chunk_optimizer=mock_chunk_optimizer,
            max_memory_mb=512,  # 512MB memory limit
            enable_streaming=True
        )

    @pytest.fixture
    def sample_large_document(self):
        """Create sample large document model."""
        return DocumentModel(
            id=1,
            title="Large Academic Paper: Advanced Machine Learning Techniques",
            file_path="/test/large_paper.pdf",
            content_hash="large_hash_123",
            mime_type="application/pdf",
            file_size=15 * 1024 * 1024  # 15MB
        )

    @pytest.mark.asyncio
    async def test_memory_efficient_processing_streaming(self, document_processor, mock_large_pdf_content):
        """Test memory-efficient streaming processing of large documents."""
        # Given
        document_processor.pdf_extractor.extract_text_streaming.return_value = self._create_text_stream(
            mock_large_pdf_content["text"]
        )

        # Monitor memory usage
        initial_memory = psutil.Process().memory_info().rss

        # When
        processing_result = await document_processor.process_document_streaming(
            document_path="/test/large_paper.pdf",
            chunk_size=2000,
            overlap=200,
            memory_threshold_mb=256
        )

        # Then
        peak_memory = psutil.Process().memory_info().rss
        memory_increase_mb = (peak_memory - initial_memory) / (1024 * 1024)

        assert processing_result["success"] is True
        assert processing_result["chunks_created"] > 0
        assert memory_increase_mb < 100  # Should not increase memory by more than 100MB
        assert processing_result["processing_mode"] == "streaming"
        assert "memory_stats" in processing_result

    @pytest.mark.asyncio
    async def test_adaptive_chunking_strategy(self, document_processor, mock_large_pdf_content):
        """Test adaptive chunking that adjusts based on document structure."""
        # Given
        adaptive_chunker = AdaptiveChunking(
            base_chunk_size=1500,
            min_chunk_size=500,
            max_chunk_size=3000,
            structure_awareness=True
        )

        # Mock chunking result
        document_processor.chunk_optimizer.adaptive_chunk.return_value = {
            "chunks": [
                {"text": "Abstract chunk", "size": 800, "type": "abstract", "metadata": {"section": "abstract"}},
                {"text": "Introduction chunk 1", "size": 1500, "type": "content", "metadata": {"section": "introduction"}},
                {"text": "Introduction chunk 2", "size": 1200, "type": "content", "metadata": {"section": "introduction"}},
                {"text": "Methodology chunk", "size": 2200, "type": "content", "metadata": {"section": "methodology"}},
                {"text": "Results chunk 1", "size": 2800, "type": "content", "metadata": {"section": "results"}},
                {"text": "References chunk", "size": 900, "type": "references", "metadata": {"section": "references"}}
            ],
            "chunk_statistics": {
                "total_chunks": 6,
                "avg_chunk_size": 1683,
                "size_variance": 0.35,
                "structure_preserved": True
            }
        }

        # When
        chunking_result = await document_processor.process_with_adaptive_chunking(
            content=mock_large_pdf_content["text"],
            sections=mock_large_pdf_content["sections"],
            chunking_strategy=adaptive_chunker
        )

        # Then
        assert len(chunking_result["chunks"]) == 6
        assert chunking_result["chunk_statistics"]["structure_preserved"] is True
        assert chunking_result["chunk_statistics"]["avg_chunk_size"] > 1000
        assert chunking_result["chunk_statistics"]["size_variance"] < 0.5

    @pytest.mark.asyncio
    async def test_semantic_chunking_with_embeddings(self, document_processor):
        """Test semantic chunking that preserves meaning across chunk boundaries."""
        # Given
        semantic_chunker = SemanticChunking(
            embedding_model=Mock(),
            similarity_threshold=0.75,
            min_chunk_size=800,
            max_chunk_size=2500
        )

        # Mock semantic similarity calculation
        semantic_chunker.embedding_model.encode.return_value = np.random.rand(10, 384)  # Mock embeddings

        document_processor.chunk_optimizer.semantic_chunk.return_value = {
            "chunks": [
                {
                    "text": "Machine learning fundamentals and core concepts in artificial intelligence research",
                    "semantic_score": 0.89,
                    "coherence_score": 0.92,
                    "size": 1800,
                    "topics": ["machine_learning", "ai_fundamentals"]
                },
                {
                    "text": "Neural network architectures including convolutional and recurrent networks",
                    "semantic_score": 0.85,
                    "coherence_score": 0.88,
                    "size": 2100,
                    "topics": ["neural_networks", "deep_learning"]
                },
                {
                    "text": "Evaluation metrics and performance assessment methods for ML models",
                    "semantic_score": 0.78,
                    "coherence_score": 0.84,
                    "size": 1650,
                    "topics": ["evaluation", "metrics", "performance"]
                }
            ],
            "semantic_coherence": 0.85,
            "topic_coverage": 0.92
        }

        # When
        semantic_result = await document_processor.process_with_semantic_chunking(
            content="Large document content for semantic analysis",
            chunking_strategy=semantic_chunker
        )

        # Then
        assert semantic_result["semantic_coherence"] >= 0.8
        assert semantic_result["topic_coverage"] >= 0.9
        assert all(chunk["semantic_score"] >= 0.75 for chunk in semantic_result["chunks"])
        assert all(chunk["coherence_score"] >= 0.8 for chunk in semantic_result["chunks"])

    @pytest.mark.asyncio
    async def test_citation_aware_chunking(self, document_processor, mock_large_pdf_content):
        """Test chunking strategy that preserves citation context."""
        # Given
        citation_chunker = CitationAwareChunking(
            preserve_citations=True,
            citation_context_window=100,
            reference_linking=True
        )

        # Mock citation-aware chunking
        document_processor.chunk_optimizer.citation_aware_chunk.return_value = {
            "chunks": [
                {
                    "text": "Research shows significant improvements (Smith et al., 2023; Jones, 2022).",
                    "citations": ["Smith et al., 2023", "Jones, 2022"],
                    "citation_positions": [{"start": 45, "end": 62}, {"start": 64, "end": 75}],
                    "reference_links": ["ref_1", "ref_2"],
                    "citation_density": 0.15
                },
                {
                    "text": "The methodology builds on previous work by Brown et al. (2021) and extends the framework.",
                    "citations": ["Brown et al., 2021"],
                    "citation_positions": [{"start": 47, "end": 64}],
                    "reference_links": ["ref_3"],
                    "citation_density": 0.08
                }
            ],
            "total_citations": 3,
            "citation_coverage": 1.0,
            "reference_completeness": 1.0
        }

        # When
        citation_result = await document_processor.process_with_citation_awareness(
            content=mock_large_pdf_content["text"],
            citations=mock_large_pdf_content["citations"],
            chunking_strategy=citation_chunker
        )

        # Then
        assert citation_result["total_citations"] == 3
        assert citation_result["citation_coverage"] == 1.0
        assert citation_result["reference_completeness"] == 1.0
        assert all("citations" in chunk for chunk in citation_result["chunks"])
        assert all(len(chunk["citations"]) > 0 for chunk in citation_result["chunks"])

    @pytest.mark.asyncio
    async def test_structure_aware_chunking_academic_papers(self, document_processor, mock_large_pdf_content):
        """Test structure-aware chunking for academic paper sections."""
        # Given
        structure_chunker = StructureAwareChunking(
            section_boundaries=True,
            preserve_headings=True,
            table_figure_handling=True,
            reference_section_separate=True
        )

        # Mock structure-aware processing
        document_processor.chunk_optimizer.structure_aware_chunk.return_value = {
            "chunks": [
                {
                    "text": "Abstract: This paper presents...",
                    "section": "abstract",
                    "heading": "Abstract",
                    "structural_type": "summary",
                    "importance_score": 0.95
                },
                {
                    "text": "1. Introduction\nMachine learning has revolutionized...",
                    "section": "introduction",
                    "heading": "1. Introduction",
                    "structural_type": "content",
                    "importance_score": 0.88
                },
                {
                    "text": "3. Methodology\n3.1 Experimental Design...",
                    "section": "methodology",
                    "heading": "3. Methodology",
                    "structural_type": "content",
                    "importance_score": 0.92
                },
                {
                    "text": "References\n[1] Author, A. (2023)...",
                    "section": "references",
                    "heading": "References",
                    "structural_type": "bibliography",
                    "importance_score": 0.70
                }
            ],
            "section_coverage": 8,
            "structure_preserved": True,
            "heading_extraction_success": 1.0
        }

        # When
        structure_result = await document_processor.process_with_structure_awareness(
            content=mock_large_pdf_content["text"],
            sections=mock_large_pdf_content["sections"],
            chunking_strategy=structure_chunker
        )

        # Then
        assert structure_result["structure_preserved"] is True
        assert structure_result["section_coverage"] == 8
        assert structure_result["heading_extraction_success"] == 1.0
        assert all("section" in chunk for chunk in structure_result["chunks"])
        assert all("structural_type" in chunk for chunk in structure_result["chunks"])

    @pytest.mark.asyncio
    async def test_performance_benchmarking_large_documents(self, document_processor):
        """Test performance benchmarks for different document sizes."""
        # Given - simulate documents of different sizes
        document_sizes = [
            {"size_mb": 1, "pages": 5, "word_count": 2500},
            {"size_mb": 5, "pages": 20, "word_count": 12500},
            {"size_mb": 10, "pages": 40, "word_count": 25000},
            {"size_mb": 25, "pages": 100, "word_count": 62500},
            {"size_mb": 50, "pages": 200, "word_count": 125000}
        ]

        performance_results = []

        for doc_size in document_sizes:
            # Mock processing for different sizes
            mock_content = "Document content " * (doc_size["word_count"] // 2)

            start_time = time.time()

            # When - process document
            result = await document_processor.process_document_benchmark(
                content=mock_content,
                size_mb=doc_size["size_mb"],
                chunk_size=2000
            )

            processing_time = time.time() - start_time

            performance_results.append({
                "size_mb": doc_size["size_mb"],
                "processing_time": processing_time,
                "chunks_created": result.get("chunks_created", 0),
                "throughput_mb_per_sec": doc_size["size_mb"] / processing_time if processing_time > 0 else 0,
                "memory_peak_mb": result.get("memory_peak_mb", 0)
            })

        # Then - verify performance scaling
        assert len(performance_results) == 5

        # Performance should scale reasonably (not exponentially worse)
        small_doc_throughput = performance_results[0]["throughput_mb_per_sec"]
        large_doc_throughput = performance_results[-1]["throughput_mb_per_sec"]

        # Throughput shouldn't degrade by more than 50% for 50x larger documents
        assert large_doc_throughput >= (small_doc_throughput * 0.5)

        # Memory usage should remain reasonable
        for result in performance_results:
            assert result["memory_peak_mb"] < 1000  # Less than 1GB peak memory

    @pytest.mark.asyncio
    async def test_concurrent_large_document_processing(self, document_processor):
        """Test concurrent processing of multiple large documents."""
        # Given - multiple large documents
        large_documents = [
            {"id": i, "size_mb": 10 + i, "content": f"Large document {i} " * 5000}
            for i in range(1, 6)  # 5 documents, 10-14MB each
        ]

        # Mock concurrent processing capability
        document_processor.enable_concurrent_processing = True
        document_processor.max_concurrent_documents = 3

        start_time = time.time()

        # When - process all documents concurrently
        processing_tasks = [
            document_processor.process_document_streaming(
                content=doc["content"],
                document_id=doc["id"]
            )
            for doc in large_documents
        ]

        results = await asyncio.gather(*processing_tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Then
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 3  # At least 3 should succeed concurrently

        # Concurrent processing should be faster than sequential
        estimated_sequential_time = sum(doc["size_mb"] * 0.5 for doc in large_documents)  # Estimate
        assert total_time < estimated_sequential_time

        # Verify all successful results have required fields
        for result in successful_results:
            assert result["success"] is True
            assert "processing_time" in result
            assert "chunks_created" in result

    def test_memory_pressure_handling(self, document_processor):
        """Test handling of memory pressure during large document processing."""
        # Given - simulate memory pressure
        document_processor.memory_manager.get_available_memory.return_value = 50 * 1024 * 1024  # 50MB available
        document_processor.memory_manager.is_memory_pressure.return_value = True

        # Mock memory pressure response
        document_processor.memory_manager.handle_memory_pressure.return_value = {
            "strategy": "streaming_mode",
            "chunk_size_reduction": 0.5,
            "enable_compression": True,
            "temporary_storage": True
        }

        # When
        pressure_response = document_processor.handle_memory_pressure()

        # Then
        assert pressure_response["strategy"] == "streaming_mode"
        assert pressure_response["chunk_size_reduction"] == 0.5
        assert pressure_response["enable_compression"] is True
        assert pressure_response["temporary_storage"] is True

    @pytest.mark.asyncio
    async def test_error_handling_corrupted_large_documents(self, document_processor):
        """Test error handling for corrupted or malformed large documents."""
        # Given - simulate various corruption scenarios
        corruption_scenarios = [
            {"type": "truncated_pdf", "error": "PDF truncated during processing"},
            {"type": "memory_corruption", "error": "Memory corruption detected"},
            {"type": "encoding_error", "error": "Character encoding issues"},
            {"type": "malformed_structure", "error": "Document structure malformed"}
        ]

        for scenario in corruption_scenarios:
            # Mock specific error
            document_processor.pdf_extractor.extract_text_streaming.side_effect = Exception(scenario["error"])

            # When/Then
            with pytest.raises(RAGProcessingError) as exc_info:
                await document_processor.process_document_streaming(
                    document_path="/test/corrupted.pdf"
                )

            assert scenario["error"] in str(exc_info.value)

            # Reset for next test
            document_processor.pdf_extractor.extract_text_streaming.side_effect = None

    @pytest.mark.asyncio
    async def test_chunk_overlap_optimization(self, document_processor):
        """Test optimization of chunk overlap for better context preservation."""
        # Given - different overlap strategies
        overlap_strategies = [
            {"strategy": "fixed", "overlap": 200, "expected_context_score": 0.75},
            {"strategy": "adaptive", "overlap": "auto", "expected_context_score": 0.85},
            {"strategy": "semantic", "overlap": "semantic_boundary", "expected_context_score": 0.90},
            {"strategy": "sentence_aware", "overlap": "sentence_boundary", "expected_context_score": 0.88}
        ]

        for strategy in overlap_strategies:
            # Mock overlap optimization
            document_processor.chunk_optimizer.optimize_overlap.return_value = {
                "optimal_overlap": strategy["overlap"],
                "context_preservation_score": strategy["expected_context_score"],
                "chunks_created": 25,
                "average_overlap_size": 180,
                "context_quality_metrics": {
                    "coherence": 0.89,
                    "continuity": 0.87,
                    "completeness": 0.92
                }
            }

            # When
            overlap_result = await document_processor.optimize_chunk_overlap(
                content="Test content for overlap optimization",
                strategy=strategy["strategy"]
            )

            # Then
            assert overlap_result["context_preservation_score"] >= strategy["expected_context_score"]
            assert overlap_result["chunks_created"] > 0
            assert overlap_result["context_quality_metrics"]["coherence"] >= 0.8

    def _create_text_stream(self, text: str) -> Generator[str, None, None]:
        """Create a text stream for testing streaming processing."""
        chunk_size = 1000
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]


class TestMemoryEfficientProcessor:
    """Test memory-efficient processing strategies."""

    @pytest.fixture
    def memory_processor(self):
        """Create memory-efficient processor."""
        return MemoryEfficientProcessor(
            memory_limit_mb=256,
            streaming_threshold_mb=10,
            compression_enabled=True,
            temporary_storage_enabled=True
        )

    def test_memory_monitoring_and_alerts(self, memory_processor):
        """Test memory monitoring and alert system."""
        # Given - simulate memory usage
        memory_processor.monitor_memory_usage(
            current_usage_mb=200,
            peak_usage_mb=220,
            limit_mb=256
        )

        # When
        memory_status = memory_processor.get_memory_status()

        # Then
        assert memory_status["current_usage_percent"] > 75  # Above 75%
        assert memory_status["alert_level"] == "warning"
        assert "recommendations" in memory_status
        assert memory_status["within_limits"] is True

    @pytest.mark.asyncio
    async def test_streaming_mode_activation(self, memory_processor):
        """Test automatic activation of streaming mode under memory pressure."""
        # Given - high memory pressure
        memory_processor.check_memory_pressure = Mock(return_value=True)
        memory_processor.activate_streaming_mode = AsyncMock(return_value={
            "streaming_activated": True,
            "chunk_size_adjusted": 1500,
            "compression_enabled": True,
            "memory_freed_mb": 50
        })

        # When
        streaming_result = await memory_processor.handle_memory_pressure()

        # Then
        assert streaming_result["streaming_activated"] is True
        assert streaming_result["chunk_size_adjusted"] == 1500
        assert streaming_result["memory_freed_mb"] > 0

    def test_compression_efficiency_for_large_chunks(self, memory_processor):
        """Test compression efficiency for large text chunks."""
        # Given - large text chunk
        large_chunk = "This is repeated content for compression testing. " * 1000  # ~50KB

        # When
        compression_result = memory_processor.compress_chunk(large_chunk)

        # Then
        assert compression_result["compressed_size"] < len(large_chunk)
        assert compression_result["compression_ratio"] > 0.5  # At least 50% reduction
        assert compression_result["compression_time"] < 1.0   # Less than 1 second
        assert compression_result["decompression_verified"] is True


class TestAcademicDocumentProcessor:
    """Test academic document specific processing features."""

    @pytest.fixture
    def academic_processor(self):
        """Create academic document processor."""
        return AcademicDocumentProcessor(
            citation_extraction=True,
            figure_table_detection=True,
            section_structure_analysis=True,
            reference_linking=True,
            metadata_enhancement=True
        )

    def test_academic_section_detection(self, academic_processor):
        """Test detection and processing of academic paper sections."""
        # Given
        academic_text = """
        Abstract
        This paper presents novel approaches to machine learning.

        1. Introduction
        Machine learning has become increasingly important...

        2. Literature Review
        Previous work by Smith et al. (2023) has shown...

        3. Methodology
        Our experimental design consists of...

        4. Results
        The results demonstrate significant improvements...

        5. Conclusion
        In conclusion, this research contributes...

        References
        [1] Smith, J. et al. (2023). Advanced ML Techniques.
        """

        # When
        section_analysis = academic_processor.analyze_section_structure(academic_text)

        # Then
        expected_sections = ["abstract", "introduction", "literature_review", "methodology", "results", "conclusion", "references"]
        assert len(section_analysis["detected_sections"]) >= 6
        assert section_analysis["structure_score"] >= 0.8
        assert section_analysis["academic_format_compliance"] >= 0.85

        detected_section_types = [section["type"] for section in section_analysis["detected_sections"]]
        assert "abstract" in detected_section_types
        assert "references" in detected_section_types

    def test_citation_extraction_and_linking(self, academic_processor):
        """Test citation extraction and reference linking."""
        # Given
        text_with_citations = """
        Recent advances in deep learning (LeCun et al., 2015; Goodfellow et al., 2016) have
        revolutionized computer vision. The transformer architecture (Vaswani et al., 2017)
        has become the standard for natural language processing tasks.
        """

        references = """
        References:
        LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436-444.
        Goodfellow, I., Bengio, Y., & Courville, A. (2016). Deep Learning. MIT Press.
        Vaswani, A., et al. (2017). Attention is all you need. NIPS.
        """

        # When
        citation_analysis = academic_processor.extract_and_link_citations(
            text_with_citations, references
        )

        # Then
        assert len(citation_analysis["citations"]) == 3
        assert citation_analysis["citation_coverage"] >= 0.9
        assert citation_analysis["reference_matching_success"] >= 0.9

        # Verify specific citations detected
        citation_texts = [cite["text"] for cite in citation_analysis["citations"]]
        assert any("LeCun et al., 2015" in cite for cite in citation_texts)
        assert any("Vaswani et al., 2017" in cite for cite in citation_texts)

    def test_figure_and_table_detection(self, academic_processor):
        """Test detection and handling of figures and tables in academic documents."""
        # Given
        document_with_figures = """
        The methodology is illustrated in Figure 1.

        [Figure 1: Neural Network Architecture - Shows the complete architecture]

        Table 1 summarizes the experimental results across different datasets.

        [Table 1: Performance Comparison
        Method | Accuracy | F1-Score
        CNN    | 0.85     | 0.83
        RNN    | 0.82     | 0.80
        Transformer | 0.91 | 0.89]

        As shown in Figure 2, the loss decreases consistently during training.
        """

        # When
        visual_element_analysis = academic_processor.detect_figures_and_tables(document_with_figures)

        # Then
        assert len(visual_element_analysis["figures"]) == 2
        assert len(visual_element_analysis["tables"]) == 1
        assert visual_element_analysis["figure_references_count"] == 2
        assert visual_element_analysis["table_references_count"] == 1
        assert visual_element_analysis["visual_content_ratio"] > 0.1

    def test_metadata_enhancement_for_academic_papers(self, academic_processor):
        """Test metadata enhancement for academic document processing."""
        # Given
        academic_document = {
            "title": "Advanced Machine Learning Techniques for Computer Vision",
            "authors": ["Dr. Jane Smith", "Prof. John Doe", "Sarah Wilson"],
            "abstract": "This paper presents novel approaches...",
            "keywords": ["machine learning", "computer vision", "neural networks"],
            "publication_year": 2023,
            "venue": "International Conference on Machine Learning"
        }

        # When
        enhanced_metadata = academic_processor.enhance_metadata(academic_document)

        # Then
        assert enhanced_metadata["academic_level"] in ["undergraduate", "graduate", "research"]
        assert enhanced_metadata["research_domain"] is not None
        assert enhanced_metadata["estimated_reading_time"] > 0
        assert enhanced_metadata["complexity_score"] >= 0.0
        assert "subject_classification" in enhanced_metadata
        assert enhanced_metadata["citation_style"] in ["APA", "IEEE", "ACM", "Chicago"]