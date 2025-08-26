"""
RAG Service Interface
Interface definitions for RAG (Retrieval Augmented Generation) services.
"""

from abc import ABC, abstractmethod
from typing import Any


class IRAGService(ABC):
    """Interface for RAG services."""

    @abstractmethod
    async def process_document(self, document_path: str, document_id: int) -> dict[str, Any]:
        """Process a document for RAG functionality."""
        pass

    @abstractmethod
    async def query_document(self, document_id: int, query: str, **kwargs) -> dict[str, Any]:
        """Query a document with RAG functionality."""
        pass

    @abstractmethod
    async def get_document_chunks(self, document_id: int) -> list[dict[str, Any]]:
        """Get document chunks for a document."""
        pass

    @abstractmethod
    async def update_document_index(self, document_id: int) -> bool:
        """Update document index."""
        pass

    @abstractmethod
    async def delete_document_index(self, document_id: int) -> bool:
        """Delete document index."""
        pass
