"""
RAG Services Module

This module provides focused RAG services that replace the monolithic EnhancedRAGService
with a set of single-responsibility components following SOLID principles.

Components:
- RAGIndexBuilder: Handles PDF processing and vector index creation
- RAGQueryEngine: Manages index loading and query execution
- RAGRecoveryService: Handles corruption detection and repair
- RAGFileManager: Manages file operations and cleanup
- RAGCoordinator: Orchestrates service interactions

This architecture provides:
- Single Responsibility Principle compliance
- Improved testability with focused interfaces
- Better maintainability and debugging
- Clear separation of concerns
- Enhanced code reusability
"""

from .coordinator import RAGCoordinator
from .index_builder import RAGIndexBuilder
from .query_engine import RAGQueryEngine
from .recovery_service import RAGRecoveryService
from .file_manager import RAGFileManager

__all__ = [
    'RAGCoordinator',
    'RAGIndexBuilder', 
    'RAGQueryEngine',
    'RAGRecoveryService',
    'RAGFileManager'
]