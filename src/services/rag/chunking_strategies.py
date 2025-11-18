"""
Document Chunking Strategies for RAG
=====================================

This module provides various chunking strategies for document processing
in the RAG pipeline.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkConfig:
    """Configuration for chunking strategies"""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: str = "\n\n"
    min_chunk_size: int = 100
    max_chunk_size: int = 2000


class ChunkingStrategy:
    """Base class for document chunking strategies"""

    def __init__(self, config: ChunkConfig | None = None):
        self.config = config or ChunkConfig()

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into chunks"""
        raise NotImplementedError


class SentenceChunker(ChunkingStrategy):
    """Chunks documents by sentences"""

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into sentence-based chunks"""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.config.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "text": current_chunk.strip(),
                            "metadata": {
                                "type": "sentence",
                                "size": len(current_chunk),
                            },
                        }
                    )
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(
                {
                    "text": current_chunk.strip(),
                    "metadata": {"type": "sentence", "size": len(current_chunk)},
                }
            )

        return chunks


class ParagraphChunker(ChunkingStrategy):
    """Chunks documents by paragraphs"""

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into paragraph-based chunks"""
        paragraphs = text.split(self.config.separator)
        chunks = []

        for para in paragraphs:
            if len(para) > self.config.max_chunk_size:
                # Split large paragraphs
                sub_chunks = self._split_large_paragraph(para)
                chunks.extend(sub_chunks)
            elif para.strip():
                chunks.append(
                    {
                        "text": para.strip(),
                        "metadata": {"type": "paragraph", "size": len(para)},
                    }
                )

        return chunks

    def _split_large_paragraph(self, text: str) -> list[dict[str, Any]]:
        """Split a large paragraph into smaller chunks"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0

        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size <= self.config.chunk_size:
                current_chunk.append(word)
                current_size += word_size
            else:
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(
                        {
                            "text": chunk_text,
                            "metadata": {
                                "type": "paragraph_split",
                                "size": len(chunk_text),
                            },
                        }
                    )
                current_chunk = [word]
                current_size = word_size

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {"type": "paragraph_split", "size": len(chunk_text)},
                }
            )

        return chunks


class SemanticChunker(ChunkingStrategy):
    """Chunks documents based on semantic similarity"""

    def __init__(self, config: ChunkConfig | None = None):
        super().__init__(config)
        # In production, this would use embeddings for semantic similarity

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into semantically coherent chunks"""
        # Simplified implementation - in production would use embeddings
        sections = re.split(r"\n(?=[A-Z])", text)
        chunks = []

        for section in sections:
            if len(section) > self.config.max_chunk_size:
                # Use paragraph chunker for large sections
                para_chunker = ParagraphChunker(self.config)
                sub_chunks = para_chunker.chunk(section)
                chunks.extend(sub_chunks)
            elif section.strip():
                chunks.append(
                    {
                        "text": section.strip(),
                        "metadata": {"type": "semantic", "size": len(section)},
                    }
                )

        return chunks


class HybridChunker(ChunkingStrategy):
    """Combines multiple chunking strategies"""

    def __init__(self, config: ChunkConfig | None = None):
        super().__init__(config)
        self.strategies = [
            SemanticChunker(config),
            ParagraphChunker(config),
            SentenceChunker(config),
        ]

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Apply hybrid chunking strategy"""
        # Try semantic first, fall back to paragraph, then sentence
        for strategy in self.strategies:
            try:
                chunks = strategy.chunk(text)
                if chunks:
                    return chunks
            except Exception as exc:
                logger.warning(
                    "Chunker %s failed, falling back to next strategy: %s",
                    strategy.__class__.__name__,
                    exc,
                )
                continue

        # Fallback to simple splitting
        return [
            {
                "text": text[: self.config.chunk_size],
                "metadata": {
                    "type": "fallback",
                    "size": len(text[: self.config.chunk_size]),
                },
            }
        ]


class AdaptiveChunking(ChunkingStrategy):
    """Adaptive chunking strategy that dynamically adjusts chunk size based on content complexity"""

    def __init__(self, config: ChunkConfig | None = None):
        super().__init__(config)
        self.base_chunk_size = config.chunk_size if config else 1000
        self.max_chunk_size = config.max_chunk_size if config else 2000
        self.min_chunk_size = config.min_chunk_size if config else 100

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Adaptively chunk text based on content complexity"""
        chunks = []
        position = 0

        # Split text into paragraphs for analysis
        paragraphs = text.split("\n\n")
        current_chunk = ""
        current_size = 0

        for para_idx, paragraph in enumerate(paragraphs):
            para_complexity = self._calculate_complexity(paragraph)
            adaptive_size = self._get_adaptive_chunk_size(para_complexity)

            # Check if adding this paragraph would exceed the adaptive size
            if current_size + len(paragraph) > adaptive_size and current_chunk:
                # Finalize current chunk
                chunks.append(
                    {
                        "text": current_chunk.strip(),
                        "start_position": position - len(current_chunk),
                        "end_position": position,
                        "chunk_size": len(current_chunk),
                        "complexity_score": self._calculate_complexity(current_chunk),
                        "adaptive_size": adaptive_size,
                        "metadata": {"type": "adaptive", "size": len(current_chunk)},
                    }
                )

                # Start new chunk
                current_chunk = paragraph + "\n\n"
                current_size = len(paragraph) + 2
                position += len(paragraph) + 2
            else:
                # Add to current chunk
                current_chunk += paragraph + "\n\n"
                current_size += len(paragraph) + 2
                position += len(paragraph) + 2

        # Add final chunk if exists
        if current_chunk.strip():
            chunks.append(
                {
                    "text": current_chunk.strip(),
                    "start_position": position - len(current_chunk),
                    "end_position": position,
                    "chunk_size": len(current_chunk),
                    "complexity_score": self._calculate_complexity(current_chunk),
                    "adaptive_size": self.base_chunk_size,
                    "metadata": {"type": "adaptive", "size": len(current_chunk)},
                }
            )

        return chunks

    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score (0-1)"""
        if not text:
            return 0.0

        # Factors for complexity
        sentence_count = len(re.split(r"[.!?]+", text))
        word_count = len(text.split())
        avg_word_length = (
            sum(len(word) for word in text.split()) / word_count
            if word_count > 0
            else 0
        )

        # Technical terms (simple heuristic)
        technical_terms = len(re.findall(r"\b[A-Z]{2,}\b", text))  # Acronyms
        numbers = len(re.findall(r"\d+", text))

        # Normalize factors
        sentence_density = sentence_count / word_count if word_count > 0 else 0
        technical_density = (
            (technical_terms + numbers) / word_count if word_count > 0 else 0
        )

        # Combine factors (0-1 scale)
        complexity = min(
            1.0,
            (
                sentence_density * 0.3
                + min(avg_word_length / 10, 1.0) * 0.3
                + technical_density * 0.4
            ),
        )

        return complexity

    def _get_adaptive_chunk_size(self, complexity: float) -> int:
        """Get adaptive chunk size based on complexity"""
        # Higher complexity = smaller chunks for better granularity
        # Lower complexity = larger chunks for efficiency

        if complexity > 0.7:  # High complexity
            return max(self.min_chunk_size, int(self.base_chunk_size * 0.6))
        elif complexity > 0.4:  # Medium complexity
            return int(self.base_chunk_size * 0.8)
        else:  # Low complexity
            return min(self.max_chunk_size, int(self.base_chunk_size * 1.2))


class CitationAwareChunking(ChunkingStrategy):
    """Citation-aware chunking that preserves citation contexts and reference integrity"""

    def __init__(self, config: ChunkConfig | None = None):
        super().__init__(config)
        # Citation patterns for detection
        self.citation_patterns = [
            r"\[[0-9,\-\s]+\]",  # [1], [1-3], [1, 2, 3]
            r"\([A-Za-z]+(?:\s+et\s+al\.)?,?\s+\d{4}\)",  # (Smith, 2020), (Smith et al., 2020)
            r"(?:Fig|Figure|Table|Eq|Equation)\.?\s*\d+",  # Figure 1, Table 2, etc.
        ]

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Chunk text while preserving citation contexts"""
        chunks = []
        position = 0

        # First pass: identify citation boundaries and important references
        citation_positions = self._find_citation_positions(text)
        section_boundaries = self._find_section_boundaries(text)

        # Combine boundaries and sort
        all_boundaries = sorted(citation_positions + section_boundaries)

        # Create chunks that respect citation contexts
        current_chunk = ""
        current_start = 0

        for boundary in all_boundaries:
            # Check if adding up to this boundary would exceed chunk size
            potential_chunk = text[current_start:boundary]

            if (
                len(current_chunk) + len(potential_chunk) > self.config.chunk_size
                and current_chunk
            ):
                # Finalize current chunk
                chunks.append(
                    self._create_citation_chunk(current_chunk, current_start, position)
                )

                # Start new chunk
                current_chunk = potential_chunk
                current_start = boundary
                position = boundary
            else:
                # Add to current chunk
                current_chunk += potential_chunk
                position = boundary

        # Add remaining text
        if position < len(text):
            remaining_text = text[position:]
            if (
                len(current_chunk) + len(remaining_text) > self.config.chunk_size
                and current_chunk
            ):
                # Finalize current chunk and start new one
                chunks.append(
                    self._create_citation_chunk(current_chunk, current_start, position)
                )
                chunks.append(
                    self._create_citation_chunk(remaining_text, position, len(text))
                )
            else:
                # Add to current chunk
                current_chunk += remaining_text
                chunks.append(
                    self._create_citation_chunk(current_chunk, current_start, len(text))
                )
        elif current_chunk:
            chunks.append(
                self._create_citation_chunk(current_chunk, current_start, position)
            )

        return chunks

    def _find_citation_positions(self, text: str) -> list[int]:
        """Find positions where citations occur for boundary detection"""
        positions = []

        for pattern in self.citation_patterns:
            for match in re.finditer(pattern, text):
                # Add position after citation for potential break point
                positions.append(match.end())

        return positions

    def _find_section_boundaries(self, text: str) -> list[int]:
        """Find section boundaries (headers, paragraph breaks)"""
        positions = []

        # Find paragraph boundaries
        for match in re.finditer(r"\n\n+", text):
            positions.append(match.end())

        # Find potential headers (lines with few words, capitalized)
        for match in re.finditer(r"\n([A-Z][A-Za-z\s]{5,50})\n", text):
            positions.append(match.start())

        return positions

    def _create_citation_chunk(
        self, text: str, start_pos: int, end_pos: int
    ) -> dict[str, Any]:
        """Create a chunk with citation metadata"""
        citations = self._extract_citations(text)

        return {
            "text": text.strip(),
            "start_position": start_pos,
            "end_position": end_pos,
            "chunk_size": len(text),
            "citations": citations,
            "citation_count": len(citations),
            "has_figures": bool(re.search(r"(?:Fig|Figure|Table)\.?\s*\d+", text)),
            "has_equations": bool(re.search(r"(?:Eq|Equation)\.?\s*\d+", text)),
            "metadata": {
                "type": "citation_aware",
                "size": len(text),
                "citation_density": len(citations) / len(text.split())
                if text.split()
                else 0,
            },
        }

    def _extract_citations(self, text: str) -> list[dict[str, str]]:
        """Extract citations from text with their types and positions"""
        citations = []

        for pattern_idx, pattern in enumerate(self.citation_patterns):
            for match in re.finditer(pattern, text):
                citation_type = ["numeric", "author_year", "figure_table"][pattern_idx]
                citations.append(
                    {
                        "text": match.group(),
                        "type": citation_type,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        return sorted(citations, key=lambda x: x["start"])


# Export main classes
__all__ = [
    "ChunkConfig",
    "ChunkingStrategy",
    "SentenceChunker",
    "ParagraphChunker",
    "SemanticChunker",
    "HybridChunker",
    "AdaptiveChunking",
    "CitationAwareChunking",
]
logger = logging.getLogger(__name__)
