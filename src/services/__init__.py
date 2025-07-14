"""
Business Logic Services

This package contains all business logic services that implement
core application functionality for the Web-based PDF Scholar platform.
Services are designed to be framework-agnostic and testable.

Key Services:
- DocumentLibraryService: Document management and library operations
- EnhancedRAGService: RAG-based document query and analysis
- ContentHashService: File content hashing and duplicate detection
- VectorIndexManager: Vector index management for RAG
- RAGCacheService: Caching for RAG query results
"""

from .document_library_service import DocumentLibraryService
from .enhanced_rag_service import EnhancedRAGService
from .content_hash_service import ContentHashService
from .vector_index_manager import VectorIndexManager
from .rag_cache_service import RAGCacheService

__all__ = [
    'DocumentLibraryService', 
    'EnhancedRAGService', 
    'ContentHashService',
    'VectorIndexManager',
    'RAGCacheService'
]