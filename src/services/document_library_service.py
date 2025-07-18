"""
Document Library Service
Business logic layer for document management. Provides high-level operations
for document importing, organization, and lifecycle management.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.content_hash_service import ContentHashError, ContentHashService

logger = logging.getLogger(__name__)


class DocumentImportError(Exception):
    """Raised when document import fails."""

    pass


class DuplicateDocumentError(DocumentImportError):
    """Raised when attempting to import a duplicate document."""

    pass


class DocumentLibraryService:
    """
    {
        "name": "DocumentLibraryService",
        "version": "1.0.0",
        "description": "High-level business logic for document library management.",
        "dependencies": [
            "DocumentRepository",
            "VectorIndexRepository",
            "ContentHashService"
        ],
        "interface": {
            "inputs": ["database_connection: DatabaseConnection"],
            "outputs": "Document management operations with business logic"
        }
    }
    Service layer for document library management.
    Provides intelligent import, duplicate detection, and organization features.
    """

    def __init__(
        self, db_connection: DatabaseConnection, documents_dir: str | None = None
    ) -> None:
        """
        Initialize document library service.
        Args:
            db_connection: Database connection instance
            documents_dir: Directory for permanent document storage
                (defaults to ~/.ai_pdf_scholar/documents)
        """
        self.db = db_connection
        self.document_repo = DocumentRepository(db_connection)
        self.vector_repo = VectorIndexRepository(db_connection)
        # Set up managed documents directory
        if documents_dir:
            self.documents_dir = Path(documents_dir)
        else:
            self.documents_dir = Path.home() / ".ai_pdf_scholar" / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def _create_managed_file_path(self, file_hash: str, original_filename: str) -> Path:
        """
        Create a managed file path for permanent storage.
        Args:
            file_hash: File hash for unique identification
            original_filename: Original filename for extension
        Returns:
            Path for managed file storage
        """
        # Use first 8 characters of hash for filename, preserve extension
        extension = Path(original_filename).suffix
        managed_filename = f"{file_hash[:8]}{extension}"
        return self.documents_dir / managed_filename

    def _copy_to_managed_storage(self, source_path: str, managed_path: Path) -> None:
        """
        Copy file to managed storage location.
        Args:
            source_path: Source file path
            managed_path: Destination managed path
        Raises:
            DocumentImportError: If copy fails
        """
        try:
            logger.debug(f"Copying file from {source_path} to {managed_path}")
            shutil.copy2(source_path, managed_path)
            logger.debug(f"File copied successfully to {managed_path}")
        except Exception as e:
            raise DocumentImportError(
                f"Failed to copy file to managed storage: {e}"
            ) from e

    def _validate_import_file(self, file_path: str) -> Path:
        """Validate file for import."""
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise DocumentImportError(f"File not found: {file_path}")
        if not ContentHashService.validate_pdf_file(file_path):
            raise DocumentImportError(f"Invalid PDF file: {file_path}")
        return file_path_obj

    def _calculate_file_hashes(self, file_path: str) -> tuple[str, str]:
        """Calculate file and content hashes."""
        try:
            file_hash, content_hash = ContentHashService.calculate_combined_hashes(
                file_path
            )
            logger.debug(
                f"Calculated hashes - file: {file_hash}, content: {content_hash}"
            )
            return file_hash, content_hash
        except ContentHashError as e:
            raise DocumentImportError(f"Failed to calculate file hash: {e}") from e

    def _handle_duplicate_document(
        self,
        existing_doc: DocumentModel,
        overwrite: bool,
        file_path: str,
        managed_file_path: Path,
        title: str | None,
    ) -> DocumentModel | None:
        """Handle duplicate document found during import."""
        if not overwrite:
            raise DuplicateDocumentError(
                f"Document already exists: {existing_doc.title} (ID: {existing_doc.id})"
            )
        logger.info(f"Overwriting existing document: {existing_doc.id}")
        self._copy_to_managed_storage(file_path, managed_file_path)
        existing_doc.file_path = str(managed_file_path)
        existing_doc.updated_at = datetime.now()
        if title:
            existing_doc.title = title
        return self.document_repo.update(existing_doc)

    def _enrich_document_metadata(
        self,
        document: DocumentModel,
        file_path: str,
        managed_file_path: Path,
        content_hash: str,
    ) -> None:
        """Enrich document with additional metadata."""
        try:
            file_info = ContentHashService.get_file_info(file_path)
            document.page_count = file_info.get("page_count", 0)
            if document.metadata is not None:
                document.metadata.update(
                    {
                        "content_hash": content_hash,
                        "import_timestamp": datetime.now().isoformat(),
                        "original_path": str(Path(file_path).absolute()),
                        "managed_path": str(managed_file_path),
                        "file_valid": file_info.get("is_valid_pdf", False),
                    }
                )
        except Exception as e:
            logger.warning(f"Could not extract additional metadata: {e}")

    def import_document(
        self,
        file_path: str,
        title: str | None = None,
        check_duplicates: bool = True,
        overwrite_duplicates: bool = False,
    ) -> DocumentModel:
        """
        Import a document into the library with intelligent duplicate detection.
        Args:
            file_path: Path to the PDF file
            title: Custom title (defaults to filename)
            check_duplicates: Whether to check for duplicates
            overwrite_duplicates: Whether to overwrite existing duplicates
        Returns:
            Imported document model
        Raises:
            DocumentImportError: If import fails
            DuplicateDocumentError: If duplicate found and not overwriting
        """
        try:
            logger.info(f"Starting document import: {file_path}")

            # Validate and calculate hashes
            file_path_obj = self._validate_import_file(file_path)
            file_hash, content_hash = self._calculate_file_hashes(file_path)
            managed_file_path = self._create_managed_file_path(
                file_hash, file_path_obj.name
            )

            # Handle duplicates
            if check_duplicates:
                existing_doc = self.document_repo.find_by_file_hash(file_hash)
                if existing_doc:
                    return self._handle_duplicate_document(
                        existing_doc,
                        overwrite_duplicates,
                        file_path,
                        managed_file_path,
                        title,
                    )

            # Create new document
            self._copy_to_managed_storage(file_path, managed_file_path)
            title = title or file_path_obj.stem
            document = DocumentModel.from_file(
                file_path=str(managed_file_path), file_hash=file_hash, title=title
            )
            document.content_hash = content_hash

            # Enrich with metadata and save
            self._enrich_document_metadata(
                document, file_path, managed_file_path, content_hash
            )
            saved_document = self.document_repo.create(document)

            logger.info(
                f"Document imported successfully: {saved_document.id} - "
                f"{saved_document.title}"
            )
            return saved_document

        except (DocumentImportError, DuplicateDocumentError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error during document import: {e}")
            raise DocumentImportError(f"Import failed: {e}") from e

    def get_documents(
        self,
        search_query: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[DocumentModel]:
        """
        Get documents with optional search and pagination.
        Args:
            search_query: Search term for title
            limit: Maximum number of documents
            offset: Number of documents to skip
            sort_by: Field to sort by
            sort_order: Sort direction (asc/desc)
        Returns:
            List of document models
        """
        try:
            if search_query:
                return self.document_repo.search_by_title(search_query, limit)
            else:
                # For now, use simple pagination
                # TODO: Implement proper sorting in repository
                return self.document_repo.find_all(limit, offset)
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            raise

    def get_recent_documents(self, limit: int = 20) -> list[DocumentModel]:
        """
        Get recently accessed documents.
        Args:
            limit: Maximum number of documents
        Returns:
            List of recent documents
        """
        try:
            return self.document_repo.find_recent_documents(limit)
        except Exception as e:
            logger.error(f"Failed to get recent documents: {e}")
            raise

    def get_document_by_path(self, file_path: str) -> DocumentModel | None:
        """
        Get document by its file path.
        Args:
            file_path: Absolute path to the document file
        Returns:
            Document model or None if not found
        """
        try:
            return self.document_repo.find_by_file_path(file_path)
        except Exception as e:
            logger.error(f"Failed to get document by path {file_path}: {e}")
            raise

    def get_document_by_id(self, document_id: int) -> DocumentModel | None:
        """
        Get document by ID and update access time.
        Args:
            document_id: Document primary key
        Returns:
            Document model or None if not found
        """
        try:
            document = self.document_repo.find_by_id(document_id)
            if document:
                # Update access time
                self.document_repo.update_access_time(document_id)
            return document
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            raise

    def delete_document(
        self, document_id: int, remove_vector_index: bool = True
    ) -> bool:
        """
        Delete document and optionally its vector index.
        Args:
            document_id: Document primary key
            remove_vector_index: Whether to also remove vector index
        Returns:
            True if deleted successfully
        """
        try:
            with self.db.transaction():
                # Remove vector index if requested
                if remove_vector_index:
                    vector_index = self.vector_repo.find_by_document_id(document_id)
                    if vector_index:
                        # Remove index files
                        try:
                            index_path = Path(vector_index.index_path)
                            if index_path.exists():
                                import shutil

                                shutil.rmtree(index_path, ignore_errors=True)
                                logger.debug(
                                    f"Removed vector index files: {index_path}"
                                )
                        except Exception as e:
                            logger.warning(f"Could not remove vector index files: {e}")
                        # Remove from database
                        self.vector_repo.delete_by_document_id(document_id)
                # Remove document
                deleted = self.document_repo.delete(document_id)
                if deleted:
                    logger.info(f"Document {document_id} deleted successfully")
                return deleted
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise

    def find_duplicate_documents(self) -> list[tuple[str, list[DocumentModel]]]:
        """
        Find potential duplicate documents.
        Returns:
            List of tuples (criteria, list_of_duplicates)
        """
        try:
            duplicates = []
            # Find duplicates by file size and similar names
            size_duplicates = self.document_repo.find_duplicates_by_size_and_name()
            for file_size, docs in size_duplicates:
                duplicates.append((f"File size: {file_size} bytes", docs))
            # TODO: Add content-based duplicate detection when content_hash
            # field is available
            return duplicates
        except Exception as e:
            logger.error(f"Failed to find duplicate documents: {e}")
            raise

    def get_library_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive library statistics.
        Returns:
            Dictionary with various statistics
        """
        try:
            stats = {}
            # Document statistics
            doc_stats = self.document_repo.get_statistics()
            stats["documents"] = doc_stats
            # Vector index statistics
            vector_stats = self.vector_repo.get_index_statistics()
            stats["vector_indexes"] = vector_stats
            # Library health
            stats["health"] = {
                "orphaned_indexes": vector_stats.get("orphaned_count", 0),
                "invalid_indexes": vector_stats.get("invalid_count", 0),
                "index_coverage": vector_stats.get("coverage", {}).get(
                    "coverage_percentage", 0
                ),
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get library statistics: {e}")
            raise

    def cleanup_library(self) -> dict[str, int]:
        """
        Perform library cleanup operations.
        Returns:
            Dictionary with cleanup results
        """
        try:
            results = {}
            # Cleanup orphaned vector indexes
            orphaned_cleaned = self.vector_repo.cleanup_orphaned_indexes()
            results["orphaned_indexes_cleaned"] = orphaned_cleaned
            # Cleanup invalid vector indexes
            invalid_cleaned = self.vector_repo.cleanup_invalid_indexes(
                remove_files=True
            )
            results["invalid_indexes_cleaned"] = invalid_cleaned
            # TODO: Add more cleanup operations
            # - Remove documents with missing files
            # - Clean up unused tags
            # - Optimize database
            logger.info(f"Library cleanup completed: {results}")
            return results
        except Exception as e:
            logger.error(f"Failed to cleanup library: {e}")
            raise

    def verify_document_integrity(self, document_id: int) -> dict[str, Any]:
        """
        Verify the integrity of a document and its associated data.
        Args:
            document_id: Document primary key
        Returns:
            Dictionary with integrity check results
        """
        try:
            result: dict[str, Any] = {
                "document_id": document_id,
                "exists": False,
                "file_exists": False,
                "file_accessible": False,
                "hash_matches": False,
                "vector_index_exists": False,
                "vector_index_valid": False,
                "errors": [],
            }
            # Check document existence
            document = self.document_repo.find_by_id(document_id)
            if not document:
                result["errors"].append("Document not found in database")
                return result
            result["exists"] = True
            result["title"] = document.title
            result["file_path"] = document.file_path
            # Check file existence
            if document.file_path:
                file_path = Path(document.file_path)
                result["file_exists"] = file_path.exists()
                if result["file_exists"]:
                    result["file_accessible"] = file_path.is_file()
                    # Verify file hash
                    try:
                        current_hash = ContentHashService.calculate_file_hash(
                            document.file_path
                        )
                        result["hash_matches"] = current_hash == document.file_hash
                        result["current_hash"] = current_hash
                        result["stored_hash"] = document.file_hash
                        if not result["hash_matches"]:
                            result["errors"].append(
                                "File hash mismatch - file may have been modified"
                            )
                    except Exception as e:
                        result["errors"].append(f"Could not calculate file hash: {e}")
                else:
                    result["errors"].append("File path is not accessible")
            else:
                result["errors"].append("No file path stored")
            # Check vector index
            vector_index = self.vector_repo.find_by_document_id(document_id)
            if vector_index:
                result["vector_index_exists"] = True
                # Verify vector index integrity
                index_check = self.vector_repo.verify_index_integrity(vector_index.id)
                result["vector_index_valid"] = index_check.get("is_valid", False)
                result["vector_index_details"] = index_check
                if not result["vector_index_valid"]:
                    result["errors"].extend(index_check.get("errors", []))
            # Overall health
            result["is_healthy"] = (
                result["exists"]
                and result["file_exists"]
                and result["file_accessible"]
                and result["hash_matches"]
            )
            return result
        except Exception as e:
            logger.error(f"Failed to verify document integrity for {document_id}: {e}")
            return {"document_id": document_id, "error": str(e)}

    def advanced_search(self, **kwargs: Any) -> list[DocumentModel]:
        """
        Perform advanced search with multiple criteria.
        Args:
            **kwargs: Search criteria (passed to repository)
        Returns:
            List of matching documents
        """
        try:
            return self.document_repo.advanced_search(**kwargs)
        except Exception as e:
            logger.error(f"Failed to perform advanced search: {e}")
            raise
