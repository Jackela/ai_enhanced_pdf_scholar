"""
Comprehensive tests for Document Chunking Strategies.

Tests cover:
- ChunkConfig dataclass
- SentenceChunker (basic sentence-based chunking)
- ParagraphChunker (paragraph-based with large paragraph splitting)
- SemanticChunker (semantic coherence-based)
- HybridChunker (fallback strategy chain)
- AdaptiveChunking (complexity-based adaptive sizing)
- CitationAwareChunking (citation context preservation)

Target Coverage: src/services/rag/chunking_strategies.py (25% → 75%)
"""

from __future__ import annotations

import pytest

from src.services.rag.chunking_strategies import (
    AdaptiveChunking,
    ChunkConfig,
    CitationAwareChunking,
    HybridChunker,
    ParagraphChunker,
    SemanticChunker,
    SentenceChunker,
)

# ============================================================================
# Configuration Tests
# ============================================================================


def test_chunk_config_defaults():
    """Test ChunkConfig default values."""
    config = ChunkConfig()

    assert config.chunk_size == 1000
    assert config.chunk_overlap == 200
    assert config.separator == "\n\n"
    assert config.min_chunk_size == 100
    assert config.max_chunk_size == 2000


def test_chunk_config_custom_values():
    """Test ChunkConfig with custom values."""
    config = ChunkConfig(
        chunk_size=500,
        chunk_overlap=100,
        separator="\n",
        min_chunk_size=50,
        max_chunk_size=1000,
    )

    assert config.chunk_size == 500
    assert config.chunk_overlap == 100
    assert config.separator == "\n"
    assert config.min_chunk_size == 50
    assert config.max_chunk_size == 1000


# ============================================================================
# SentenceChunker Tests
# ============================================================================


def test_sentence_chunker_initialization():
    """Test SentenceChunker initializes with default config."""
    chunker = SentenceChunker()
    assert chunker.config is not None
    assert chunker.config.chunk_size == 1000


def test_sentence_chunker_simple_text():
    """Test sentence chunking with simple text."""
    chunker = SentenceChunker(ChunkConfig(chunk_size=100))
    text = "First sentence. Second sentence. Third sentence."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all("metadata" in chunk for chunk in chunks)
    assert all(chunk["metadata"]["type"] == "sentence" for chunk in chunks)


def test_sentence_chunker_respects_chunk_size():
    """Test sentence chunker respects chunk size limits."""
    chunker = SentenceChunker(ChunkConfig(chunk_size=50))
    text = (
        "This is a very long sentence that should be split into multiple chunks. " * 3
    )

    chunks = chunker.chunk(text)

    # Each chunk should be roughly within size limit
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk["text"]) <= 200  # Allow some overflow


# ============================================================================
# ParagraphChunker Tests
# ============================================================================


def test_paragraph_chunker_basic_split():
    """Test paragraph chunker with basic paragraphs."""
    chunker = ParagraphChunker()
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

    chunks = chunker.chunk(text)

    assert len(chunks) == 3
    assert chunks[0]["text"] == "Paragraph one."
    assert chunks[1]["text"] == "Paragraph two."
    assert chunks[2]["text"] == "Paragraph three."


def test_paragraph_chunker_splits_large_paragraphs():
    """Test paragraph chunker splits oversized paragraphs."""
    config = ChunkConfig(chunk_size=50, max_chunk_size=100)
    chunker = ParagraphChunker(config)

    # Create paragraph > max_chunk_size
    large_para = "word " * 50  # 250 characters

    chunks = chunker.chunk(large_para)

    assert len(chunks) > 1  # Should be split
    for chunk in chunks:
        assert chunk["metadata"]["type"] in ["paragraph_split"]


def test_paragraph_chunker_empty_paragraphs():
    """Test paragraph chunker handles empty paragraphs."""
    chunker = ParagraphChunker()
    text = "Content\n\n\n\nMore content"

    chunks = chunker.chunk(text)

    # Should skip empty paragraphs
    assert all(len(chunk["text"]) > 0 for chunk in chunks)


# ============================================================================
# SemanticChunker Tests
# ============================================================================


def test_semantic_chunker_initialization():
    """Test SemanticChunker initializes correctly."""
    chunker = SemanticChunker()
    assert chunker.config is not None


def test_semantic_chunker_section_detection():
    """Test semantic chunker detects sections."""
    chunker = SemanticChunker(ChunkConfig(chunk_size=100))
    text = "Introduction\nFirst section content.\nMethod\nSecond section content."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all(chunk["metadata"]["type"] == "semantic" for chunk in chunks)


def test_semantic_chunker_large_sections():
    """Test semantic chunker handles large sections."""
    config = ChunkConfig(chunk_size=50, max_chunk_size=100)
    chunker = SemanticChunker(config)

    # Create large section
    text = "Section\n" + ("word " * 50)

    chunks = chunker.chunk(text)

    # Should fall back to paragraph chunking for large sections
    assert len(chunks) > 1


# ============================================================================
# HybridChunker Tests
# ============================================================================


def test_hybrid_chunker_initialization():
    """Test HybridChunker initializes with multiple strategies."""
    chunker = HybridChunker()

    assert len(chunker.strategies) == 3
    assert isinstance(chunker.strategies[0], SemanticChunker)
    assert isinstance(chunker.strategies[1], ParagraphChunker)
    assert isinstance(chunker.strategies[2], SentenceChunker)


def test_hybrid_chunker_successful_strategy():
    """Test hybrid chunker uses first successful strategy."""
    chunker = HybridChunker()
    text = "Simple text. Multiple sentences. Should work."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)


def test_hybrid_chunker_fallback():
    """Test hybrid chunker fallback when all strategies fail."""
    chunker = HybridChunker(ChunkConfig(chunk_size=100))

    # Mock all strategies to fail
    for strategy in chunker.strategies:
        strategy.chunk = lambda text: []  # Return empty to trigger fallback

    text = "Test text"
    chunks = chunker.chunk(text)

    # Should use fallback strategy
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["type"] == "fallback"


# ============================================================================
# AdaptiveChunking Tests
# ============================================================================


def test_adaptive_chunking_initialization():
    """Test AdaptiveChunking initializes with correct sizes."""
    config = ChunkConfig(chunk_size=1000, min_chunk_size=100, max_chunk_size=2000)
    chunker = AdaptiveChunking(config)

    assert chunker.base_chunk_size == 1000
    assert chunker.min_chunk_size == 100
    assert chunker.max_chunk_size == 2000


def test_adaptive_chunking_complexity_calculation():
    """Test complexity score calculation."""
    chunker = AdaptiveChunking()

    # Low complexity text
    simple_text = "This is simple text. Easy to read."
    simple_complexity = chunker._calculate_complexity(simple_text)

    # High complexity text (with acronyms and numbers)
    complex_text = "The API uses REST architecture. HTTP status code 200 indicates success. JSON data format."
    complex_complexity = chunker._calculate_complexity(complex_text)

    assert 0 <= simple_complexity <= 1
    assert 0 <= complex_complexity <= 1
    assert complex_complexity > simple_complexity


def test_adaptive_chunking_adaptive_size():
    """Test adaptive chunk size based on complexity."""
    chunker = AdaptiveChunking(
        ChunkConfig(chunk_size=1000, min_chunk_size=100, max_chunk_size=2000)
    )

    # High complexity should give smaller chunks
    high_complexity_size = chunker._get_adaptive_chunk_size(0.8)
    assert high_complexity_size <= 1000

    # Low complexity should give larger chunks
    low_complexity_size = chunker._get_adaptive_chunk_size(0.2)
    assert low_complexity_size >= 1000


def test_adaptive_chunking_basic_text():
    """Test adaptive chunking on basic text."""
    chunker = AdaptiveChunking(ChunkConfig(chunk_size=100))
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all("complexity_score" in chunk for chunk in chunks)
    assert all("adaptive_size" in chunk for chunk in chunks)


# ============================================================================
# CitationAwareChunking Tests
# ============================================================================


def test_citation_aware_chunking_initialization():
    """Test CitationAwareChunking initializes with patterns."""
    chunker = CitationAwareChunking()

    assert len(chunker.citation_patterns) > 0


def test_citation_aware_find_citations():
    """Test citation position detection."""
    chunker = CitationAwareChunking()
    text = "According to research [1], the method works. See Figure 1 for details."

    positions = chunker._find_citation_positions(text)

    assert len(positions) > 0


def test_citation_aware_extract_citations():
    """Test citation extraction with types."""
    chunker = CitationAwareChunking()
    text = "Research [1] shows. Smith et al. (2020) demonstrated. See Figure 2."

    citations = chunker._extract_citations(text)

    assert len(citations) >= 2
    assert all("text" in cite for cite in citations)
    assert all("type" in cite for cite in citations)


def test_citation_aware_chunking_preserves_context():
    """Test citation-aware chunking preserves citation context."""
    chunker = CitationAwareChunking(ChunkConfig(chunk_size=100))
    text = "Introduction text [1]. More content. References (Smith, 2020) are important. See Figure 1."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all("citations" in chunk for chunk in chunks)
    assert all("citation_count" in chunk for chunk in chunks)


def test_citation_aware_chunk_metadata():
    """Test citation-aware chunk includes rich metadata."""
    chunker = CitationAwareChunking()
    text = "Study [1] shows results. See Figure 1 and Table 2. Equation 3 demonstrates."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    chunk = chunks[0]

    assert "has_figures" in chunk
    assert "has_equations" in chunk
    assert "citation_density" in chunk["metadata"]


def test_citation_aware_section_boundaries():
    """Test section boundary detection."""
    chunker = CitationAwareChunking()
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    boundaries = chunker._find_section_boundaries(text)

    assert len(boundaries) > 0  # Should find paragraph breaks


# ============================================================================
# Edge Cases & Integration
# ============================================================================


def test_chunker_empty_text():
    """Test all chunkers handle empty text gracefully."""
    chunkers = [
        SentenceChunker(),
        ParagraphChunker(),
        SemanticChunker(),
        HybridChunker(),
        AdaptiveChunking(),
        CitationAwareChunking(),
    ]

    for chunker in chunkers:
        chunks = chunker.chunk("")
        # Should return empty or minimal chunks, not crash
        assert isinstance(chunks, list)


def test_chunker_very_long_text():
    """Test chunkers handle very long text."""
    config = ChunkConfig(chunk_size=100)
    chunker = SentenceChunker(config)

    # Create very long text
    long_text = "This is a sentence. " * 100

    chunks = chunker.chunk(long_text)

    assert len(chunks) > 1
    assert all("text" in chunk for chunk in chunks)


def test_all_chunkers_return_consistent_format():
    """Test all chunkers return consistent chunk format."""
    text = "Sample text for testing. Multiple sentences here. End of sample."
    chunkers = [
        SentenceChunker(),
        ParagraphChunker(),
        SemanticChunker(),
        HybridChunker(),
        AdaptiveChunking(),
        CitationAwareChunking(),
    ]

    for chunker in chunkers:
        chunks = chunker.chunk(text)
        for chunk in chunks:
            # All chunks must have text and metadata
            assert "text" in chunk
            assert "metadata" in chunk
            assert "type" in chunk["metadata"]
