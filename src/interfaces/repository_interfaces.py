"""
Repository Interfaces
Defines abstract base classes for repository pattern implementation
following the Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from src.database.models import (
    CitationModel,
    CitationRelationModel,
    DocumentModel,
    VectorIndexModel,
)
from src.database.multi_document_models import (
    CrossDocumentQueryModel,
    MultiDocumentCollectionModel,
    MultiDocumentIndexModel,
)

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
    def get_by_ids(self, entity_ids: list[int]) -> list[T]:
        """Get multiple entities by IDs."""
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
    ) -> tuple[list[DocumentModel], int]:
        """Search documents by query and return results with a total count."""
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


class ICitationRepository(IRepository[CitationModel]):
    """
    Citation repository interface.
    Provides citation-specific operations following ISP.
    """

    @abstractmethod
    def find_by_document_id(self, document_id: int) -> list[CitationModel]:
        """Find all citations for a document."""
        pass

    @abstractmethod
    def search_by_author(self, author: str, limit: int = 50) -> list[CitationModel]:
        """Search citations by author name."""
        pass

    @abstractmethod
    def search_by_title(self, title: str, limit: int = 50) -> list[CitationModel]:
        """Search citations by title."""
        pass

    @abstractmethod
    def find_by_doi(self, doi: str) -> CitationModel | None:
        """Find citation by DOI."""
        pass

    @abstractmethod
    def find_by_year_range(self, start_year: int, end_year: int) -> list[CitationModel]:
        """Find citations within year range."""
        pass

    @abstractmethod
    def get_by_type(self, citation_type: str) -> list[CitationModel]:
        """Get citations by type (journal, conference, book, etc.)."""
        pass

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """Get citation statistics."""
        pass


class ICitationRelationRepository(IRepository[CitationRelationModel]):
    """
    Citation relation repository interface.
    Provides citation relationship operations following ISP.
    """

    @abstractmethod
    def find_by_source_document(
        self, source_document_id: int
    ) -> list[CitationRelationModel]:
        """Find all relations where document is the source."""
        pass

    @abstractmethod
    def find_by_target_document(
        self, target_document_id: int
    ) -> list[CitationRelationModel]:
        """Find all relations where document is the target."""
        pass

    @abstractmethod
    def find_by_citation(self, citation_id: int) -> list[CitationRelationModel]:
        """Find all relations involving a specific citation."""
        pass

    @abstractmethod
    def get_citation_network(self, document_id: int, depth: int = 1) -> dict[str, Any]:
        """Get citation network for a document up to specified depth."""
        pass

    @abstractmethod
    def get_most_cited_documents(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most cited documents in the library."""
        pass

    @abstractmethod
    def get_relations_by_source(
        self, source_document_id: int
    ) -> list[CitationRelationModel]:
        """Get all relations by source document."""
        pass

    @abstractmethod
    def get_all_relations(self) -> list[CitationRelationModel]:
        """Get all citation relations in the system."""
        pass

    @abstractmethod
    def cleanup_orphaned_relations(self) -> int:
        """Remove relations pointing to non-existent documents/citations."""
        pass


class IMultiDocumentCollectionRepository(IRepository[MultiDocumentCollectionModel]):
    """
    Multi-document collection repository interface.
    Provides operations for managing document collections.
    """

    @abstractmethod
    def get_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[MultiDocumentCollectionModel]:
        """Get all collections with pagination."""
        pass

    @abstractmethod
    def find_by_name(self, name: str) -> MultiDocumentCollectionModel | None:
        """Find collection by name."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 50) -> list[MultiDocumentCollectionModel]:
        """Search collections by name or description."""
        pass

    @abstractmethod
    def get_collections_containing_document(
        self, document_id: int
    ) -> list[MultiDocumentCollectionModel]:
        """Get all collections that contain a specific document."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get total collection count."""
        pass


class IMultiDocumentIndexRepository(IRepository[MultiDocumentIndexModel]):
    """
    Multi-document index repository interface.
    Provides operations for managing collection indexes.
    """

    @abstractmethod
    def get_by_collection_id(
        self, collection_id: int
    ) -> MultiDocumentIndexModel | None:
        """Get index by collection ID."""
        pass

    @abstractmethod
    def find_by_hash(self, index_hash: str) -> MultiDocumentIndexModel | None:
        """Find index by hash."""
        pass

    @abstractmethod
    def get_orphaned_indexes(self) -> list[MultiDocumentIndexModel]:
        """Get indexes without corresponding collections."""
        pass

    @abstractmethod
    def cleanup_orphaned(self) -> int:
        """Remove orphaned indexes."""
        pass


class ICrossDocumentQueryRepository(IRepository[CrossDocumentQueryModel]):
    """
    Cross-document query repository interface.
    Provides operations for managing cross-document queries and results.
    """

    @abstractmethod
    def find_by_collection_id(
        self, collection_id: int, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by collection ID."""
        pass

    @abstractmethod
    def find_by_user_id(
        self, user_id: str, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by user ID."""
        pass

    @abstractmethod
    def find_by_status(
        self, status: str, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by status."""
        pass

    @abstractmethod
    def get_recent_queries(
        self, days: int = 7, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Get recent queries within specified days."""
        pass

    @abstractmethod
    def get_query_statistics(self) -> dict[str, Any]:
        """Get query performance statistics."""
        pass

    @abstractmethod
    def cleanup_old_queries(self, days_old: int = 30) -> int:
        """Remove old query records."""
        pass
