"""
RAG Service Interfaces

Abstract interfaces for RAG service components following SOLID principles.
These interfaces enable dependency injection, testing, and modular architecture.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.database.models import DocumentModel


class IRAGIndexBuilder(ABC):
    """Interface for RAG index building operations."""

    @abstractmethod
    async def build_index(
        self, document: DocumentModel, **kwargs: Any
    ) -> dict[str, Any]:
        """Build vector index for a document."""
        pass

    @abstractmethod
    async def rebuild_index(self, document_id: int, **kwargs: Any) -> dict[str, Any]:
        """Rebuild vector index for existing document."""
        pass

    @abstractmethod
    async def verify_index(self, document_id: int) -> bool:
        """Verify index integrity for a document."""
        pass

    @abstractmethod
    async def optimize_index(self, document_id: int) -> dict[str, Any]:
        """Optimize vector index for better performance."""
        pass

    @abstractmethod
    async def get_index_stats(self, document_id: int) -> dict[str, Any]:
        """Get statistics about document index."""
        pass


class IRAGQueryEngine(ABC):
    """Interface for RAG query processing operations."""

    @abstractmethod
    async def query(
        self, document_id: int, query: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute RAG query against document index."""
        pass

    @abstractmethod
    async def multi_document_query(
        self, document_ids: list[int], query: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute query across multiple documents."""
        pass

    @abstractmethod
    async def get_query_history(
        self, document_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent query history for a document."""
        pass

    @abstractmethod
    async def explain_query(self, document_id: int, query: str) -> dict[str, Any]:
        """Provide explanation of how query was processed."""
        pass

    @abstractmethod
    async def suggest_queries(self, document_id: int, limit: int = 5) -> list[str]:
        """Suggest relevant queries for a document."""
        pass


class IRAGRecoveryService(ABC):
    """Interface for RAG system recovery and health monitoring."""

    @abstractmethod
    async def detect_corruption(self, document_id: int) -> bool:
        """Detect index corruption for a document."""
        pass

    @abstractmethod
    async def repair_index(self, document_id: int, **kwargs: Any) -> dict[str, Any]:
        """Repair corrupted index."""
        pass

    @abstractmethod
    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Perform comprehensive health check."""
        pass

    @abstractmethod
    async def backup_index(self, document_id: int, backup_path: Path) -> dict[str, Any]:
        """Create backup of document index."""
        pass

    @abstractmethod
    async def restore_index(
        self, document_id: int, backup_path: Path
    ) -> dict[str, Any]:
        """Restore index from backup."""
        pass

    @abstractmethod
    async def get_recovery_status(self, document_id: int) -> dict[str, Any]:
        """Get recovery operation status."""
        pass


class IRAGFileManager(ABC):
    """Interface for RAG file management operations."""

    @abstractmethod
    async def cleanup_temp_files(
        self, document_id: int | None = None, **kwargs: Any
    ) -> int:
        """Clean up temporary files."""
        pass

    @abstractmethod
    async def cleanup_orphaned_files(self, **kwargs: Any) -> int:
        """Clean up orphaned files without parent documents."""
        pass

    @abstractmethod
    def get_storage_stats(self, document_id: int | None = None) -> dict[str, Any]:
        """Get storage usage statistics."""
        pass

    @abstractmethod
    async def move_files(self, file_moves: list[tuple]) -> dict[str, Any]:
        """Move files between locations."""
        pass

    @abstractmethod
    async def copy_file_with_verification(
        self, source: Path, target: Path
    ) -> dict[str, Any]:
        """Copy file with integrity verification."""
        pass

    @abstractmethod
    async def batch_delete_files(self, file_paths: list[Path]) -> dict[str, Any]:
        """Delete multiple files in batch."""
        pass

    @abstractmethod
    async def optimize_storage(self, **kwargs: Any) -> dict[str, Any]:
        """Optimize storage usage."""
        pass

    @abstractmethod
    def verify_file_integrity(
        self, file_path: Path, expected_checksum: str | None = None
    ) -> dict[str, Any]:
        """Verify file integrity."""
        pass


class IRAGCoordinator(ABC):
    """Interface for RAG system coordination and orchestration."""

    @abstractmethod
    async def process_document_complete(
        self, document: DocumentModel, **kwargs: Any
    ) -> dict[str, Any]:
        """Complete document processing workflow."""
        pass

    @abstractmethod
    async def query_document(
        self, document_id: int, query: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Query document with full workflow."""
        pass

    @abstractmethod
    async def batch_process_documents(
        self, document_ids: list[int], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Process multiple documents in batch."""
        pass

    @abstractmethod
    async def cleanup_resources(
        self, document_id: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Clean up system resources."""
        pass

    @abstractmethod
    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """System-wide health check."""
        pass

    @abstractmethod
    def get_performance_metrics(self, **kwargs: Any) -> dict[str, Any]:
        """Get system performance metrics."""
        pass


# Additional specialized interfaces for advanced RAG functionality


class IRAGVectorStore(ABC):
    """Interface for vector storage operations."""

    @abstractmethod
    async def add_documents(
        self, documents: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        """Add documents to vector store."""
        pass

    @abstractmethod
    async def similarity_search_with_score(
        self, query: str, k: int = 5, **kwargs: Any
    ) -> list[tuple]:
        """Perform similarity search with relevance scores."""
        pass

    @abstractmethod
    async def delete_documents(
        self, document_ids: list[str], **kwargs: Any
    ) -> dict[str, Any]:
        """Delete documents from vector store."""
        pass

    @abstractmethod
    async def save_local(self, path: Path) -> bool:
        """Save vector store to local path."""
        pass

    @abstractmethod
    async def load_local(self, path: Path) -> bool:
        """Load vector store from local path."""
        pass


class IRAGTextSplitter(ABC):
    """Interface for text splitting strategies."""

    @abstractmethod
    def split_text(self, text: str, **kwargs: Any) -> list[str]:
        """Split text into chunks."""
        pass

    @abstractmethod
    def split_documents(
        self, documents: list[dict[str, Any]], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Split multiple documents."""
        pass

    @abstractmethod
    def get_chunk_metadata(
        self, chunk: str, source_document: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate metadata for text chunk."""
        pass


class IRAGLLMClient(ABC):
    """Interface for Language Model interactions."""

    @abstractmethod
    async def generate_response(
        self, prompt: str, context: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Generate response using LLM."""
        pass

    @abstractmethod
    async def generate_embeddings(
        self, texts: list[str], **kwargs: Any
    ) -> list[list[float]]:
        """Generate embeddings for texts."""
        pass

    @abstractmethod
    async def assess_response_quality(
        self, query: str, response: str, context: str
    ) -> dict[str, Any]:
        """Assess quality of generated response."""
        pass


class IRAGContextBuilder(ABC):
    """Interface for building query context."""

    @abstractmethod
    def build_context(
        self, query: str, retrieved_documents: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        """Build context for LLM query."""
        pass

    @abstractmethod
    def optimize_context_length(self, context: str, max_length: int) -> str:
        """Optimize context to fit within length limits."""
        pass

    @abstractmethod
    def extract_key_information(
        self, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Extract key information from documents."""
        pass


# Quality assessment interfaces


class IRAGQualityAssessment(ABC):
    """Interface for RAG response quality assessment."""

    @abstractmethod
    async def evaluate_response_relevance(
        self, query: str, answer: str, source_texts: list[str]
    ) -> float:
        """Evaluate response relevance to query."""
        pass

    @abstractmethod
    async def evaluate_citation_accuracy(
        self, response_text: str, source_citations: list[str]
    ) -> dict[str, Any]:
        """Evaluate citation accuracy."""
        pass

    @abstractmethod
    async def detect_hallucination(
        self, response_text: str, source_content: str
    ) -> dict[str, Any]:
        """Detect potential hallucination in response."""
        pass

    @abstractmethod
    async def comprehensive_assessment(
        self,
        query: str,
        answer: str,
        sources: list[dict[str, Any]],
        document_content: str,
    ) -> dict[str, Any]:
        """Comprehensive quality assessment."""
        pass


# Performance monitoring interfaces


class IRAGPerformanceMonitor(ABC):
    """Interface for RAG performance monitoring."""

    @abstractmethod
    async def track_query_performance(
        self, query_id: str, metrics: dict[str, Any]
    ) -> None:
        """Track query performance metrics."""
        pass

    @abstractmethod
    async def track_indexing_performance(
        self, document_id: int, metrics: dict[str, Any]
    ) -> None:
        """Track indexing performance metrics."""
        pass

    @abstractmethod
    def get_performance_summary(self, time_range: str) -> dict[str, Any]:
        """Get performance summary for time range."""
        pass

    @abstractmethod
    async def detect_performance_degradation(self) -> dict[str, Any]:
        """Detect performance degradation patterns."""
        pass


# Export all interfaces
__all__ = [
    "IRAGIndexBuilder",
    "IRAGQueryEngine",
    "IRAGRecoveryService",
    "IRAGFileManager",
    "IRAGCoordinator",
    "IRAGVectorStore",
    "IRAGTextSplitter",
    "IRAGLLMClient",
    "IRAGContextBuilder",
    "IRAGQualityAssessment",
    "IRAGPerformanceMonitor",
]
