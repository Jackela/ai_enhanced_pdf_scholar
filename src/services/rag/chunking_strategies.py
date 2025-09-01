"""
Document Chunking Strategies for RAG
=====================================

This module provides various chunking strategies for document processing
in the RAG pipeline.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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

    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into chunks"""
        raise NotImplementedError


class SentenceChunker(ChunkingStrategy):
    """Chunks documents by sentences"""

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into sentence-based chunks"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.config.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "metadata": {"type": "sentence", "size": len(current_chunk)}
                    })
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {"type": "sentence", "size": len(current_chunk)}
            })

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
                chunks.append({
                    "text": para.strip(),
                    "metadata": {"type": "paragraph", "size": len(para)}
                })

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
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {"type": "paragraph_split", "size": len(chunk_text)}
                    })
                current_chunk = [word]
                current_size = word_size

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "metadata": {"type": "paragraph_split", "size": len(chunk_text)}
            })

        return chunks


class SemanticChunker(ChunkingStrategy):
    """Chunks documents based on semantic similarity"""

    def __init__(self, config: Optional[ChunkConfig] = None):
        super().__init__(config)
        # In production, this would use embeddings for semantic similarity

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Split text into semantically coherent chunks"""
        # Simplified implementation - in production would use embeddings
        sections = re.split(r'\n(?=[A-Z])', text)
        chunks = []

        for section in sections:
            if len(section) > self.config.max_chunk_size:
                # Use paragraph chunker for large sections
                para_chunker = ParagraphChunker(self.config)
                sub_chunks = para_chunker.chunk(section)
                chunks.extend(sub_chunks)
            elif section.strip():
                chunks.append({
                    "text": section.strip(),
                    "metadata": {"type": "semantic", "size": len(section)}
                })

        return chunks


class HybridChunker(ChunkingStrategy):
    """Combines multiple chunking strategies"""

    def __init__(self, config: Optional[ChunkConfig] = None):
        super().__init__(config)
        self.strategies = [
            SemanticChunker(config),
            ParagraphChunker(config),
            SentenceChunker(config)
        ]

    def chunk(self, text: str) -> list[dict[str, Any]]:
        """Apply hybrid chunking strategy"""
        # Try semantic first, fall back to paragraph, then sentence
        for strategy in self.strategies:
            try:
                chunks = strategy.chunk(text)
                if chunks:
                    return chunks
            except Exception:
                continue

        # Fallback to simple splitting
        return [{
            "text": text[:self.config.chunk_size],
            "metadata": {"type": "fallback", "size": len(text[:self.config.chunk_size])}
        }]


# Export main classes
__all__ = [
    'ChunkConfig',
    'ChunkingStrategy',
    'SentenceChunker',
    'ParagraphChunker',
    'SemanticChunker',
    'HybridChunker'
]
