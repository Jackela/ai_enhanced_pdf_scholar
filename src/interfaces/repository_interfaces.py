"""
Repository Interfaces
Defines abstract base classes for repository pattern implementation
following the Interface Segregation Principle (ISP).
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from src.database.models import DocumentModel, VectorIndexModel, CitationModel, CitationRelationModel

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
    def get_statistics(self) -> dict:
        """Get citation statistics."""
        pass


class ICitationRelationRepository(IRepository[CitationRelationModel]):
    """
    Citation relation repository interface.
    Provides citation relationship operations following ISP.
    """

    @abstractmethod
    def find_by_source_document(self, source_document_id: int) -> list[CitationRelationModel]:
        """Find all relations where document is the source."""
        pass

    @abstractmethod
    def find_by_target_document(self, target_document_id: int) -> list[CitationRelationModel]:
        """Find all relations where document is the target."""
        pass

    @abstractmethod
    def find_by_citation(self, citation_id: int) -> list[CitationRelationModel]:
        """Find all relations involving a specific citation."""
        pass

    @abstractmethod
    def get_citation_network(self, document_id: int, depth: int = 1) -> dict:
        """Get citation network for a document up to specified depth."""
        pass

    @abstractmethod
    def get_most_cited_documents(self, limit: int = 10) -> list[dict]:
        """Get most cited documents in the library."""
        pass

    @abstractmethod
    def get_relations_by_source(self, source_document_id: int) -> list[CitationRelationModel]:
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
