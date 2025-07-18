"""
Repository Interfaces
Defines abstract base classes for repository pattern implementation
following the Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from src.database.models import DocumentModel, VectorIndexModel

T = TypeVar("T")


class IRepository(ABC, Generic[T]):
    """
    Generic repository interface.
    Follows the Interface Segregation Principle by providing
    minimal, focused interface that all repositories must implement.
    """

    @abstractmethod
    def create(self, entity: T) -> T:
        """Create a new entity."""
        pass

    @abstractmethod
    def get_by_id(self, entity_id: int) -> T | None:
        """Get entity by ID."""
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Update an existing entity."""
        pass

    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        """Delete an entity by ID."""
        pass


class IDocumentRepository(IRepository[DocumentModel]):
    """
    Document-specific repository interface.
    Extends the base repository with document-specific operations
    following the Interface Segregation Principle.
    """

    @abstractmethod
    def find_by_hash(self, file_hash: str) -> DocumentModel | None:
        """Find document by file hash."""
        pass

    @abstractmethod
    def find_by_content_hash(self, content_hash: str) -> DocumentModel | None:
        """Find document by content hash."""
        pass

    @abstractmethod
    def search(
        self, query: str, limit: int = 50, offset: int = 0
    ) -> list[DocumentModel]:
        """Search documents by query."""
        pass

    @abstractmethod
    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[DocumentModel]:
        """Get all documents with pagination and sorting."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get total document count."""
        pass


class IVectorIndexRepository(IRepository[VectorIndexModel]):
    """
    Vector index repository interface.
    Provides vector index-specific operations following ISP.
    """

    @abstractmethod
    def find_by_document_id(self, document_id: int) -> VectorIndexModel | None:
        """Find vector index by document ID."""
        pass

    @abstractmethod
    def find_by_hash(self, index_hash: str) -> VectorIndexModel | None:
        """Find vector index by hash."""
        pass

    @abstractmethod
    def get_orphaned_indexes(self) -> list[VectorIndexModel]:
        """Get vector indexes without corresponding documents."""
        pass

    @abstractmethod
    def cleanup_orphaned(self) -> int:
        """Remove orphaned vector indexes."""
        pass
