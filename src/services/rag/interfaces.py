"""
RAG Service Interfaces

Abstract interfaces for RAG service components following SOLID principles.
These interfaces enable dependency injection, testing, and modular architecture.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from pathlib import Path
import asyncio

from src.database.models import DocumentModel


class IRAGIndexBuilder(ABC):
    """Interface for RAG index building operations."""
    
    @abstractmethod
    async def build_index(self, document: DocumentModel, **kwargs) -> Dict[str, Any]:
        """Build vector index for a document."""
        pass
    
    @abstractmethod
    async def rebuild_index(self, document_id: int, **kwargs) -> Dict[str, Any]:
        """Rebuild vector index for existing document."""
        pass
    
    @abstractmethod
    async def verify_index(self, document_id: int) -> bool:
        """Verify index integrity for a document."""
        pass
    
    @abstractmethod
    async def optimize_index(self, document_id: int) -> Dict[str, Any]:
        """Optimize vector index for better performance."""
        pass
    
    @abstractmethod
    async def get_index_stats(self, document_id: int) -> Dict[str, Any]:
        """Get statistics about document index."""
        pass


class IRAGQueryEngine(ABC):
    """Interface for RAG query processing operations."""
    
    @abstractmethod
    async def query(self, document_id: int, query: str, **kwargs) -> Dict[str, Any]:
        """Execute RAG query against document index."""
        pass
    
    @abstractmethod
    async def multi_document_query(self, document_ids: List[int], query: str, **kwargs) -> Dict[str, Any]:
        """Execute query across multiple documents."""
        pass
    
    @abstractmethod
    async def get_query_history(self, document_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent query history for a document."""
        pass
    
    @abstractmethod
    async def explain_query(self, document_id: int, query: str) -> Dict[str, Any]:
        """Provide explanation of how query was processed."""
        pass
    
    @abstractmethod
    async def suggest_queries(self, document_id: int, limit: int = 5) -> List[str]:
        """Suggest relevant queries for a document."""
        pass


class IRAGRecoveryService(ABC):
    """Interface for RAG system recovery and health monitoring."""
    
    @abstractmethod
    async def detect_corruption(self, document_id: int) -> bool:
        """Detect index corruption for a document."""
        pass
    
    @abstractmethod
    async def repair_index(self, document_id: int, **kwargs) -> Dict[str, Any]:
        """Repair corrupted index."""
        pass
    
    @abstractmethod
    async def health_check(self, **kwargs) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        pass
    
    @abstractmethod
    async def backup_index(self, document_id: int, backup_path: Path) -> Dict[str, Any]:
        """Create backup of document index."""
        pass
    
    @abstractmethod
    async def restore_index(self, document_id: int, backup_path: Path) -> Dict[str, Any]:
        """Restore index from backup."""
        pass
    
    @abstractmethod
    async def get_recovery_status(self, document_id: int) -> Dict[str, Any]:
        """Get recovery operation status."""
        pass


class IRAGFileManager(ABC):
    """Interface for RAG file management operations."""
    
    @abstractmethod
    async def cleanup_temp_files(self, document_id: Optional[int] = None, **kwargs) -> int:
        """Clean up temporary files."""
        pass
    
    @abstractmethod
    async def cleanup_orphaned_files(self, **kwargs) -> int:
        """Clean up orphaned files without parent documents."""
        pass
    
    @abstractmethod
    def get_storage_stats(self, document_id: Optional[int] = None) -> Dict[str, Any]:
        """Get storage usage statistics."""
        pass
    
    @abstractmethod
    async def move_files(self, file_moves: List[tuple]) -> Dict[str, Any]:
        """Move files between locations."""
        pass
    
    @abstractmethod
    async def copy_file_with_verification(self, source: Path, target: Path) -> Dict[str, Any]:
        """Copy file with integrity verification."""
        pass
    
    @abstractmethod
    async def batch_delete_files(self, file_paths: List[Path]) -> Dict[str, Any]:
        """Delete multiple files in batch."""
        pass
    
    @abstractmethod
    async def optimize_storage(self, **kwargs) -> Dict[str, Any]:
        """Optimize storage usage."""
        pass
    
    @abstractmethod
    def verify_file_integrity(self, file_path: Path, expected_checksum: Optional[str] = None) -> Dict[str, Any]:
        """Verify file integrity."""
        pass


class IRAGCoordinator(ABC):
    """Interface for RAG system coordination and orchestration."""
    
    @abstractmethod
    async def process_document_complete(self, document: DocumentModel, **kwargs) -> Dict[str, Any]:
        """Complete document processing workflow."""
        pass
    
    @abstractmethod
    async def query_document(self, document_id: int, query: str, **kwargs) -> Dict[str, Any]:
        """Query document with full workflow."""
        pass
    
    @abstractmethod
    async def batch_process_documents(self, document_ids: List[int], **kwargs) -> List[Dict[str, Any]]:
        """Process multiple documents in batch."""
        pass
    
    @abstractmethod
    async def cleanup_resources(self, document_id: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Clean up system resources."""
        pass
    
    @abstractmethod
    async def health_check(self, **kwargs) -> Dict[str, Any]:
        """System-wide health check."""
        pass
    
    @abstractmethod
    def get_performance_metrics(self, **kwargs) -> Dict[str, Any]:
        """Get system performance metrics."""
        pass


# Additional specialized interfaces for advanced RAG functionality

class IRAGVectorStore(ABC):
    """Interface for vector storage operations."""
    
    @abstractmethod
    async def add_documents(self, documents: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Add documents to vector store."""
        pass
    
    @abstractmethod
    async def similarity_search_with_score(self, query: str, k: int = 5, **kwargs) -> List[tuple]:
        """Perform similarity search with relevance scores."""
        pass
    
    @abstractmethod
    async def delete_documents(self, document_ids: List[str], **kwargs) -> Dict[str, Any]:
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
    def split_text(self, text: str, **kwargs) -> List[str]:
        """Split text into chunks."""
        pass
    
    @abstractmethod
    def split_documents(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """Split multiple documents."""
        pass
    
    @abstractmethod
    def get_chunk_metadata(self, chunk: str, source_document: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata for text chunk."""
        pass


class IRAGLLMClient(ABC):
    """Interface for Language Model interactions."""
    
    @abstractmethod
    async def generate_response(self, prompt: str, context: str, **kwargs) -> Dict[str, Any]:
        """Generate response using LLM."""
        pass
    
    @abstractmethod
    async def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generate embeddings for texts."""
        pass
    
    @abstractmethod
    async def assess_response_quality(self, query: str, response: str, context: str) -> Dict[str, Any]:
        """Assess quality of generated response."""
        pass


class IRAGContextBuilder(ABC):
    """Interface for building query context."""
    
    @abstractmethod
    def build_context(self, query: str, retrieved_documents: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Build context for LLM query."""
        pass
    
    @abstractmethod
    def optimize_context_length(self, context: str, max_length: int) -> str:
        """Optimize context to fit within length limits."""
        pass
    
    @abstractmethod
    def extract_key_information(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key information from documents."""
        pass


# Quality assessment interfaces

class IRAGQualityAssessment(ABC):
    """Interface for RAG response quality assessment."""
    
    @abstractmethod
    async def evaluate_response_relevance(self, query: str, answer: str, source_texts: List[str]) -> float:
        """Evaluate response relevance to query."""
        pass
    
    @abstractmethod
    async def evaluate_citation_accuracy(self, response_text: str, source_citations: List[str]) -> Dict[str, Any]:
        """Evaluate citation accuracy."""
        pass
    
    @abstractmethod
    async def detect_hallucination(self, response_text: str, source_content: str) -> Dict[str, Any]:
        """Detect potential hallucination in response."""
        pass
    
    @abstractmethod
    async def comprehensive_assessment(self, query: str, answer: str, sources: List[Dict[str, Any]], document_content: str) -> Dict[str, Any]:
        """Comprehensive quality assessment."""
        pass


# Performance monitoring interfaces

class IRAGPerformanceMonitor(ABC):
    """Interface for RAG performance monitoring."""
    
    @abstractmethod
    async def track_query_performance(self, query_id: str, metrics: Dict[str, Any]) -> None:
        """Track query performance metrics."""
        pass
    
    @abstractmethod
    async def track_indexing_performance(self, document_id: int, metrics: Dict[str, Any]) -> None:
        """Track indexing performance metrics."""
        pass
    
    @abstractmethod
    def get_performance_summary(self, time_range: str) -> Dict[str, Any]:
        """Get performance summary for time range."""
        pass
    
    @abstractmethod
    async def detect_performance_degradation(self) -> Dict[str, Any]:
        """Detect performance degradation patterns."""
        pass


# Export all interfaces
__all__ = [
    'IRAGIndexBuilder',
    'IRAGQueryEngine', 
    'IRAGRecoveryService',
    'IRAGFileManager',
    'IRAGCoordinator',
    'IRAGVectorStore',
    'IRAGTextSplitter',
    'IRAGLLMClient',
    'IRAGContextBuilder',
    'IRAGQualityAssessment',
    'IRAGPerformanceMonitor'
]