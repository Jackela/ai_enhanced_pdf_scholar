"""
Large Document Processing for RAG
==================================

This module handles processing of large documents for the RAG pipeline,
including splitting, chunking, and optimizing for efficient retrieval.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.rag.chunking_strategies import (
    ChunkConfig,
    HybridChunker,
)
from src.services.rag.performance_monitor import get_monitor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingConfig:
    """Configuration for large document processing"""

    max_file_size_mb: int = 100
    chunk_size: int = 1000
    chunk_overlap: int = 200
    parallel_processing: bool = True
    cache_processed: bool = True
    optimize_memory: bool = True


class LargeDocumentProcessor:
    """Handles processing of large documents for RAG"""

    def __init__(self, config: ProcessingConfig | None = None):
        """
        Initialize large document processor

        Args:
            config: Processing configuration
        """
        self.config = config or ProcessingConfig()
        self.monitor = get_monitor()

        # Initialize chunking strategy
        chunk_config = ChunkConfig(
            chunk_size=self.config.chunk_size, chunk_overlap=self.config.chunk_overlap
        )
        self.chunker = HybridChunker(chunk_config)

        # Cache for processed documents
        self.cache: dict[str, list[dict[str, Any]]] = {}

    def process_document(
        self, file_path: str, content: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Process a large document into chunks

        Args:
            file_path: Path to the document
            content: Optional pre-loaded content

        Returns:
            List of document chunks with metadata
        """
        op_id = self.monitor.start_operation(
            "process_large_document", {"file": file_path}
        )

        try:
            # Check cache first
            doc_hash = self._get_document_hash(file_path, content)
            if self.config.cache_processed and doc_hash in self.cache:
                logger.info(f"Using cached chunks for {file_path}")
                self.monitor.end_operation(op_id, success=True)
                return self.cache[doc_hash]

            # Load content if not provided
            if content is None:
                content = self._load_document(file_path)

            # Check document size
            size_mb = len(content.encode("utf-8")) / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                raise ValueError(
                    f"Document size ({size_mb:.2f}MB) exceeds maximum ({self.config.max_file_size_mb}MB)"
                )

            # Process document
            chunks = self._process_content(content, file_path)

            # Cache if enabled
            if self.config.cache_processed:
                self.cache[doc_hash] = chunks

            self.monitor.end_operation(op_id, success=True)
            logger.info(f"Successfully processed {file_path}: {len(chunks)} chunks")

            return chunks

        except Exception as e:
            self.monitor.end_operation(op_id, success=False, error_message=str(e))
            logger.error(f"Failed to process document {file_path}: {e}")
            raise

    def _get_document_hash(self, file_path: str, content: str | None = None) -> str:
        """Generate hash for document caching"""
        if content:
            return hashlib.sha256(content.encode()).hexdigest()

        # Hash file path and modification time
        path = Path(file_path)
        if path.exists():
            stat = path.stat()
            hash_str = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
            return hashlib.sha256(hash_str.encode()).hexdigest()

        return hashlib.sha256(file_path.encode()).hexdigest()

    def _load_document(self, file_path: str) -> str:
        """Load document content from file"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        # Check file size before loading
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(
                f"File size ({size_mb:.2f}MB) exceeds maximum ({self.config.max_file_size_mb}MB)"
            )

        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, encoding="latin-1") as f:
                return f.read()

    def _process_content(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Process document content into chunks"""
        # Use chunking strategy
        chunks = self.chunker.chunk(content)

        # Add document metadata to each chunk
        doc_metadata = {
            "source": file_path,
            "document_name": Path(file_path).name,
            "total_chunks": len(chunks),
        }

        # Enhance chunks with metadata
        enhanced_chunks = []
        for i, chunk in enumerate(chunks):
            enhanced_chunk = {
                **chunk,
                "chunk_index": i,
                "document_metadata": doc_metadata,
            }
            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks

    def process_batch(self, file_paths: list[str]) -> dict[str, list[dict[str, Any]]]:
        """
        Process multiple documents in batch

        Args:
            file_paths: List of document paths

        Returns:
            Dictionary mapping file paths to their chunks
        """
        op_id = self.monitor.start_operation(
            "process_batch", {"count": len(file_paths)}
        )
        results = {}

        try:
            for file_path in file_paths:
                try:
                    chunks = self.process_document(file_path)
                    results[file_path] = chunks
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    results[file_path] = []

            self.monitor.end_operation(op_id, success=True)
            return results

        except Exception as e:
            self.monitor.end_operation(op_id, success=False, error_message=str(e))
            raise

    def optimize_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Optimize chunks for better retrieval

        Args:
            chunks: List of document chunks

        Returns:
            Optimized chunks
        """
        optimized = []

        for chunk in chunks:
            # Remove very small chunks
            if len(chunk.get("text", "")) < 50:
                continue

            # Merge consecutive small chunks
            if optimized and len(chunk.get("text", "")) < 200:
                last_chunk = optimized[-1]
                if len(last_chunk.get("text", "")) < 500:
                    # Merge with previous chunk
                    last_chunk["text"] += "\n" + chunk.get("text", "")
                    last_chunk["metadata"]["merged"] = True
                    continue

            optimized.append(chunk)

        return optimized

    def get_processing_stats(self) -> dict[str, Any]:
        """Get processing statistics"""
        stats = self.monitor.get_statistics()

        # Add cache statistics
        stats["cache_stats"] = {
            "cached_documents": len(self.cache),
            "total_cached_chunks": sum(len(chunks) for chunks in self.cache.values()),
        }

        return stats

    def clear_cache(self):
        """Clear the document cache"""
        self.cache.clear()
        logger.info("Document cache cleared")


# Utility functions
def estimate_processing_time(file_size_mb: float, chunk_size: int = 1000) -> float:
    """
    Estimate processing time for a document

    Args:
        file_size_mb: File size in megabytes
        chunk_size: Target chunk size

    Returns:
        Estimated time in seconds
    """
    # Rough estimation: 10MB/second processing speed
    base_time = file_size_mb / 10.0

    # Add overhead for chunking
    estimated_chunks = (file_size_mb * 1024 * 1024) / chunk_size
    chunking_overhead = estimated_chunks * 0.001  # 1ms per chunk

    return base_time + chunking_overhead


def validate_document(file_path: str) -> tuple[bool, str | None]:
    """
    Validate if a document can be processed

    Args:
        file_path: Path to document

    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(file_path)

    if not path.exists():
        return False, "File does not exist"

    if not path.is_file():
        return False, "Path is not a file"

    # Check file extension
    valid_extensions = {".txt", ".pdf", ".md", ".json", ".csv"}
    if path.suffix.lower() not in valid_extensions:
        return False, f"Unsupported file type: {path.suffix}"

    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > 100:  # 100MB limit
        return False, f"File too large: {size_mb:.2f}MB"

    return True, None


# Export main classes
__all__ = [
    "ProcessingConfig",
    "LargeDocumentProcessor",
    "estimate_processing_time",
    "validate_document",
]
