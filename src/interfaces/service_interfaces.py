"""
Service Interfaces

Defines abstract interfaces for business logic services
following the Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.database.models import DocumentModel, VectorIndexModel


class IContentHashService(ABC):
    """
    Content hashing service interface.

    Abstracts content hashing operations to allow different implementations
    following the Dependency Inversion Principle.
    """

    @abstractmethod
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate file content hash."""
        pass

    @abstractmethod
    def calculate_content_hash(self, file_path: str) -> str:
        """Calculate document content hash."""
        pass

    @abstractmethod
    def calculate_combined_hashes(self, file_path: str) -> tuple[str, str]:
        """Calculate both file and content hashes."""
        pass

    @abstractmethod
    def validate_pdf_file(self, file_path: str) -> bool:
        """Validate if file is a valid PDF."""
        pass


class IRAGService(ABC):
    """
    RAG (Retrieval-Augmented Generation) service interface.

    Abstracts RAG operations to support different implementations
    and models while following the Open/Closed Principle.
    """

    @abstractmethod
    def build_index(self, file_path: str, index_path: str) -> bool:
        """Build vector index from document."""
        pass

    @abstractmethod
    def load_index(self, index_path: str) -> bool:
        """Load existing vector index."""
        pass

    @abstractmethod
    def query(self, query: str) -> str:
        """Query the loaded index."""
        pass

    @abstractmethod
    def is_index_loaded(self) -> bool:
        """Check if index is loaded."""
        pass

    @abstractmethod
    def get_index_info(self) -> Dict[str, Any]:
        """Get information about loaded index."""
        pass


class IDocumentLibraryService(ABC):
    """
    Document library service interface.

    Defines the contract for document library management operations
    following the Interface Segregation Principle.
    """

    @abstractmethod
    def import_document(
        self,
        file_path: str,
        title: Optional[str] = None,
        check_duplicates: bool = True,
        overwrite_duplicates: bool = False,
    ) -> DocumentModel:
        """Import a document into the library."""
        pass

    @abstractmethod
    def get_document_by_id(self, document_id: int) -> Optional[DocumentModel]:
        """Get document by ID."""
        pass

    @abstractmethod
    def get_documents(
        self,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[DocumentModel]:
        """Get documents with optional search and pagination."""
        pass

    @abstractmethod
    def delete_document(
        self, document_id: int, remove_vector_index: bool = True
    ) -> bool:
        """Delete a document."""
        pass

    @abstractmethod
    def find_duplicate_documents(self) -> List[tuple]:
        """Find potential duplicate documents."""
        pass

    @abstractmethod
    def get_library_statistics(self) -> Dict[str, Any]:
        """Get library statistics."""
        pass

    @abstractmethod
    def cleanup_library(self) -> Dict[str, int]:
        """Clean up orphaned data."""
        pass

    @abstractmethod
    def verify_document_integrity(self, document_id: int) -> Dict[str, Any]:
        """Verify document integrity."""
        pass


class IVectorIndexService(ABC):
    """
    Vector index management service interface.

    Abstracts vector index operations following the Single Responsibility Principle.
    """

    @abstractmethod
    def create_index(self, document: DocumentModel) -> Optional[VectorIndexModel]:
        """Create vector index for document."""
        pass

    @abstractmethod
    def get_index_by_document_id(self, document_id: int) -> Optional[VectorIndexModel]:
        """Get vector index by document ID."""
        pass

    @abstractmethod
    def delete_index(self, index_id: int) -> bool:
        """Delete vector index."""
        pass

    @abstractmethod
    def verify_index_integrity(self, index_id: int) -> Dict[str, Any]:
        """Verify index file integrity."""
        pass

    @abstractmethod
    def cleanup_orphaned_indexes(self) -> int:
        """Clean up orphaned index files."""
        pass
