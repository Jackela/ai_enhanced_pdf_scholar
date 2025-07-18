import logging
from typing import Any

from src.core.state_manager import StateManager
from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.services.document_library_service import (
    DocumentImportError,
    DocumentLibraryService,
    DuplicateDocumentError,
)
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)


class LibraryController:
    def __init__(
        self,
        library_service: DocumentLibraryService = None,
        db_connection: DatabaseConnection = None,
        enhanced_rag_service: EnhancedRAGService = None,
        state_manager: StateManager = None,
    ):
        """
        Initialize LibraryController with flexible dependency injection.
        Supports both old style (desktop app) and new style (web API) initialization.
        """
        if library_service is not None:
            # Legacy desktop app style initialization (deprecated)
            self.library_service = library_service
            self.state_manager = state_manager
            self.enhanced_rag_service = None
        else:
            # Web API style initialization
            if db_connection is None:
                raise ValueError("db_connection is required for web API initialization")
            # Initialize library service with managed documents directory
            from pathlib import Path

            documents_dir = Path.home() / ".ai_pdf_scholar" / "documents"
            self.library_service = DocumentLibraryService(
                db_connection, str(documents_dir)
            )
            self.enhanced_rag_service = enhanced_rag_service
            self.state_manager = state_manager
        logger.info("LibraryController initialized")

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
        Returns True if successful, False otherwise.
        """
        try:
            document = self.library_service.import_document(
                file_path, title, overwrite_duplicates=not check_duplicates
            )
            return document is not None
        except (DocumentImportError, DuplicateDocumentError):
            raise  # Re-raise for API error handling
        except Exception as e:
            logger.error(f"Document import failed: {e}")
            return False

    def import_document_legacy(
        self,
        file_path: str,
        title: str | None = None,
        overwrite_duplicates: bool = False,
    ) -> DocumentModel:
        """
        Import a document into the library (legacy method returning DocumentModel).
        """
        return self.library_service.import_document(
            file_path, title, overwrite_duplicates=overwrite_duplicates
        )

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
        """
        if not self.enhanced_rag_service:
            raise ValueError("Enhanced RAG service not available")
        # Get document from library
        document = self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        # Load index for the document
        success = self.enhanced_rag_service.load_index_for_document(document_id)
        if not success:
            # Try to build index if it doesn't exist
            success = self.enhanced_rag_service.build_index_from_document(document)
            if not success:
                raise ValueError(
                    f"Failed to build or load index for document {document_id}"
                )
        # Perform query
        return self.enhanced_rag_service.query(query)
