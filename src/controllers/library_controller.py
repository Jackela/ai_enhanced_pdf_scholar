import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.core.state_manager import StateManager
from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.exceptions import DocumentImportError, DuplicateDocumentError
from src.services.document_library_service import DocumentLibraryService
from src.services.enhanced_rag_service import EnhancedRAGService
from src.services.service_factory import ServiceFactory, get_service_factory

logger = logging.getLogger(__name__)


class ILibraryController(ABC):
    """Abstract interface for library controllers."""

    @abstractmethod
    def get_all_documents(self, search_query: str | None = None) -> list[DocumentModel]:
        """Get all documents, optionally filtered by search query."""
        pass

    @abstractmethod
    def get_documents(
        self,
        search_query: str | None = None,
        limit: int | None = None,
        sort_by: str = "created_at",
    ) -> list[DocumentModel]:
        """Get documents with filtering and sorting options."""
        pass

    @abstractmethod
    def delete_document(self, document_id: int) -> bool:
        """Delete a document from the library."""
        pass

    @abstractmethod
    def get_document_by_id(self, document_id: int) -> DocumentModel | None:
        """Get a document by its ID."""
        pass

    @abstractmethod
    def get_library_statistics(self) -> dict[str, Any]:
        """Get library statistics."""
        pass


class BaseLibraryController(ILibraryController):
    """Base controller with common functionality."""

    def __init__(self, library_service: DocumentLibraryService):
        """Initialize with library service."""
        if not library_service:
            raise ValueError("library_service is required")
        self.library_service = library_service
        logger.debug(
            f"BaseLibraryController initialized with {type(library_service).__name__}"
        )

    def get_all_documents(self, search_query: str | None = None) -> list[DocumentModel]:
        """Get all documents, optionally filtered by search query."""
        return self.library_service.get_documents(search_query=search_query)

    def get_documents(
        self,
        search_query: str | None = None,
        limit: int | None = None,
        sort_by: str = "created_at",
    ) -> list[DocumentModel]:
        """Get documents with filtering and sorting options."""
        return self.library_service.get_documents(
            search_query=search_query, limit=limit, sort_by=sort_by
        )

    def delete_document(self, document_id: int) -> bool:
        """Delete a document from the library."""
        return self.library_service.delete_document(document_id)

    def get_document_by_id(self, document_id: int) -> DocumentModel | None:
        """Get a document by its ID."""
        return self.library_service.get_document_by_id(document_id)

    def get_library_statistics(self) -> dict[str, Any]:
        """Get library statistics."""
        return self.library_service.get_library_statistics()

    def find_duplicate_documents(self) -> list[tuple]:
        """Find duplicate documents."""
        return self.library_service.find_duplicate_documents()

    def cleanup_library(self) -> dict[str, int]:
        """Clean up the library."""
        return self.library_service.cleanup_library()

    def verify_document_integrity(self, document_id: int) -> dict[str, Any]:
        """Verify document integrity."""
        return self.library_service.verify_document_integrity(document_id)


class WebAPILibraryController(BaseLibraryController):
    """Web API-specific library controller with enhanced functionality."""

    def __init__(
        self,
        db_connection: DatabaseConnection,
        enhanced_rag_service: EnhancedRAGService | None = None,
        state_manager: StateManager | None = None,
        documents_dir: str | None = None,
        service_factory: ServiceFactory | None = None,
    ):
        """Initialize web API controller with managed dependencies."""
        if not db_connection:
            raise ValueError("db_connection is required for web API initialization")

        # Set up managed documents directory
        if documents_dir:
            managed_documents_dir = documents_dir
        else:
            managed_documents_dir = str(Path.home() / ".ai_pdf_scholar" / "documents")

        # Initialize library service using factory if available
        if service_factory:
            library_service = service_factory.create_service(
                DocumentLibraryService, documents_dir=managed_documents_dir
            )
            logger.debug("Library service created via ServiceFactory")
        else:
            # Fallback to direct instantiation with DI pattern
            from src.repositories.document_repository import DocumentRepository
            from src.services.content_hash_service import ContentHashService

            doc_repo = DocumentRepository(db_connection)
            hash_service = ContentHashService()
            library_service = DocumentLibraryService(
                document_repository=doc_repo,
                hash_service=hash_service,
                documents_dir=managed_documents_dir
            )
            logger.debug("Library service created directly with DI pattern (fallback)")

        super().__init__(library_service)

        self.enhanced_rag_service = enhanced_rag_service
        self.state_manager = state_manager
        logger.info(
            f"WebAPILibraryController initialized with documents dir: "
            f"{managed_documents_dir}"
        )

    @classmethod
    def create_with_factory(
        cls,
        service_factory: ServiceFactory | None = None,
        enhanced_rag_service: EnhancedRAGService | None = None,
        state_manager: StateManager | None = None,
        documents_dir: str | None = None,
    ) -> "WebAPILibraryController":
        """
        Create controller using the global or provided service factory.

        Args:
            service_factory: Optional service factory (uses global if None)
            enhanced_rag_service: Optional RAG service instance
            state_manager: Optional state manager instance
            documents_dir: Optional documents directory path

        Returns:
            Configured WebAPILibraryController instance
        """
        factory = service_factory or get_service_factory()

        # Get database connection from factory
        db_connection = factory.db_connection

        # Create enhanced services via factory if not provided
        if not enhanced_rag_service:
            try:
                enhanced_rag_service = factory.create_service(EnhancedRAGService)
            except Exception as e:
                logger.warning(f"Could not create EnhancedRAGService via factory: {e}")
                enhanced_rag_service = None

        return cls(
            db_connection=db_connection,
            enhanced_rag_service=enhanced_rag_service,
            state_manager=state_manager,
            documents_dir=documents_dir,
            service_factory=factory,
        )

    def get_all_documents(self, search_query: str | None = None) -> list[DocumentModel]:
        """
        Get all documents, optionally filtered by search query.
        """
        return self.library_service.get_documents(search_query=search_query)

    def get_documents(
        self,
        search_query: str | None = None,
        limit: int | None = None,
        sort_by: str = "created_at",
    ) -> list[DocumentModel]:
        """
        Get documents with filtering and sorting options for API endpoints.
        """
        return self.library_service.get_documents(
            search_query=search_query, limit=limit, sort_by=sort_by
        )

    def import_document(
        self,
        file_path: str,
        title: str | None = None,
        check_duplicates: bool = True,
        auto_build_index: bool = False,
    ) -> bool:
        """
        Import a document into the library for API endpoints.
        Args:
            file_path: Path to the PDF file to import
            title: Optional custom title for the document
            check_duplicates: Whether to check for duplicate files
            auto_build_index: Whether to automatically build vector index (future use)
        Returns:
            True if successful, False otherwise
        Raises:
            DocumentImportError: If import fails due to validation or processing error
            DuplicateDocumentError: If duplicate found and check_duplicates=True
        """
        try:
            document = self.library_service.import_document(
                file_path,
                title,
                check_duplicates=check_duplicates,
                overwrite_duplicates=not check_duplicates,
            )

            # TODO: Implement auto_build_index when requested
            if auto_build_index and self.enhanced_rag_service and document:
                logger.debug(f"Auto-building index for document {document.id}")
                # Future enhancement: Build vector index automatically

            return document is not None
        except (DocumentImportError, DuplicateDocumentError):
            raise  # Re-raise for proper API error handling
        except Exception as e:
            logger.error(f"Unexpected error during document import: {e}")
            return False

    def delete_document(self, document_id: int) -> bool:
        """
        Delete a document from the library.
        """
        return self.library_service.delete_document(document_id)

    def get_document_by_id(self, document_id: int) -> DocumentModel | None:
        """
        Get a document by its ID.
        """
        return self.library_service.get_document_by_id(document_id)

    def get_library_statistics(self) -> dict[str, Any]:
        """
        Get library statistics.
        """
        return self.library_service.get_library_statistics()

    def find_duplicate_documents(self) -> list[tuple]:
        """
        Find duplicate documents.
        """
        return self.library_service.find_duplicate_documents()

    def cleanup_library(self) -> dict[str, int]:
        """
        Clean up the library.
        """
        return self.library_service.cleanup_library()

    def verify_document_integrity(self, document_id: int) -> dict[str, Any]:
        """
        Verify document integrity.
        """
        return self.library_service.verify_document_integrity(document_id)

    def query_document(self, document_id: int, query: str) -> str:
        """
        Query a document using RAG service.
        Args:
            document_id: ID of the document to query
            query: Search query to execute against the document
        Returns:
            Query response from the RAG service
        Raises:
            ValueError: If RAG service unavailable or document not found
        """
        if not self.enhanced_rag_service:
            raise ValueError("Enhanced RAG service not available for document querying")

        # Validate document exists
        document = self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"Document with ID {document_id} not found")

        # Load or build document index
        success = self.enhanced_rag_service.load_index_for_document(document_id)
        if not success:
            logger.info(f"Building new index for document {document_id}")
            success = self.enhanced_rag_service.build_index_from_document(document)
            if not success:
                raise ValueError(
                    f"Failed to build or load vector index for document {document_id}. "
                    "Check document file accessibility and vector service config."
                )

        # Execute query
        try:
            return self.enhanced_rag_service.query(query)
        except Exception as e:
            logger.error(f"Query execution failed for document {document_id}: {e}")
            raise ValueError(f"Query execution failed: {e}") from e


class DesktopLibraryController(BaseLibraryController):
    """Desktop application-specific library controller (legacy support)."""

    def __init__(
        self,
        library_service: DocumentLibraryService,
        state_manager: StateManager | None = None,
    ):
        """Initialize desktop controller with existing library service."""
        super().__init__(library_service)
        self.state_manager = state_manager
        logger.info("DesktopLibraryController initialized (legacy mode)")

    def import_document_legacy(
        self,
        file_path: str,
        title: str | None = None,
        overwrite_duplicates: bool = False,
    ) -> DocumentModel:
        """
        Import a document into the library (legacy method returning DocumentModel).
        Args:
            file_path: Path to the PDF file to import
            title: Optional custom title for the document
            overwrite_duplicates: Whether to overwrite existing duplicates
        Returns:
            Imported DocumentModel instance
        Raises:
            DocumentImportError: If import fails
            DuplicateDocumentError: If duplicate found and overwrite_duplicates=False
        """
        return self.library_service.import_document(
            file_path,
            title,
            check_duplicates=not overwrite_duplicates,
            overwrite_duplicates=overwrite_duplicates,
        )


# Backwards compatibility alias - will be deprecated
LibraryController = WebAPILibraryController
