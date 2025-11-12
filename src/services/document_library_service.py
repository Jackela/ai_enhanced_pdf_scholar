"""
Document Library Service
Business logic layer for document management. Provides high-level operations
for document importing, organization, and lifecycle management.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.exceptions import (
    ContentHashError,
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)
from src.interfaces.repository_interfaces import IDocumentRepository
from src.interfaces.service_interfaces import IContentHashService
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.content_hash_service import ContentHashService

logger = logging.getLogger(__name__)


# Exception classes now imported from src.exceptions


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
        self,
        document_repository: IDocumentRepository,
        hash_service: IContentHashService,
        documents_dir: str | None = None,
    ) -> None:
        """
        Initialize document library service with dependency injection.

        Args:
            document_repository: Document repository implementation
            hash_service: Content hash service implementation
            documents_dir: Directory for permanent document storage
                (defaults to ~/.ai_pdf_scholar/documents)
        """
        self.document_repo: IDocumentRepository = document_repository
        self.hash_service: IContentHashService = hash_service

        # Get database connection from repository for vector repo (legacy compatibility)
        # TODO: Refactor to inject VectorIndexRepository in v2.2
        self.db: DatabaseConnection = document_repository.db
        self.vector_repo: VectorIndexRepository = VectorIndexRepository(self.db)

        # Set up managed documents directory
        if documents_dir:
            self.documents_dir: Path = Path(documents_dir)
        else:
            self.documents_dir: Path = Path.home() / ".ai_pdf_scholar" / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def _create_managed_file_path(self, file_hash: str, original_filename: str, force_unique: bool = False) -> Path:
        """
        Create a managed file path for permanent storage.
        Args:
            file_hash: File hash for unique identification
            original_filename: Original filename for extension
            force_unique: Force unique path even with same hash
        Returns:
            Path for managed file storage
        """
        # Use first 8 characters of hash for filename, preserve extension
        extension = Path(original_filename).suffix
        if force_unique:
            import time
            timestamp = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
            managed_filename = f"{file_hash[:8]}_{timestamp}{extension}"
        else:
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
            raise DocumentImportError(
                f"File not found: {file_path}",
                file_path=file_path,
                reason="File does not exist",
            )
        if not self.hash_service.validate_pdf_file(file_path):
            raise DocumentValidationError(
                f"Invalid PDF file: {file_path}",
                file_path=file_path,
                validation_issue="Not a valid PDF format",
            )
        return file_path_obj

    def _calculate_file_hashes(self, file_path: str) -> tuple[str, str]:
        """Calculate file and content hashes."""
        try:
            file_hash, content_hash = self.hash_service.calculate_combined_hashes(
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
            file_info = self.hash_service.get_file_info(file_path)
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
                file_hash, file_path_obj.name, force_unique=not check_duplicates
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
            sort_by: Field to sort by (created_at, updated_at, last_accessed, title, file_size)
            sort_order: Sort direction (asc/desc)
        Returns:
            List of document models
        """
        try:
            if search_query:
                return self.document_repo.search_by_title(search_query, limit)
            else:
                # Use repository-level sorting with secure validation
                return self.document_repo.get_all(limit, offset, sort_by, sort_order)
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
                # Get document info before deletion for file cleanup
                document = self.document_repo.find_by_id(document_id)
                if not document:
                    logger.warning(f"Document {document_id} not found for deletion")
                    return False

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

                # Remove document from database
                deleted = self.document_repo.delete(document_id)
                if deleted:
                    # Remove document file from managed storage
                    if document.file_path:
                        try:
                            file_path = Path(document.file_path)
                            if file_path.exists():
                                file_path.unlink()
                                logger.debug(f"Removed document file: {file_path}")
                            else:
                                logger.debug(f"Document file not found: {file_path}")
                        except Exception as e:
                            logger.warning(f"Could not remove document file {document.file_path}: {e}")
                            # Don't fail the deletion if file removal fails

                    logger.info(f"Document {document_id} deleted successfully")
                return deleted
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise

    def find_duplicate_documents(
        self,
        include_content_hash: bool = True,
        include_title_similarity: bool = True,
        title_similarity_threshold: float = 0.8,
    ) -> list[tuple[str, list[DocumentModel]]]:
        """
        Find potential duplicate documents using multiple detection methods.
        Args:
            include_content_hash: Check for exact content duplicates
            include_title_similarity: Check for similar titles
            title_similarity_threshold: Minimum similarity score for title matching
        Returns:
            List of tuples (criteria, list_of_duplicates)
        """
        try:
            duplicates = []

            # 1. Exact content duplicates (highest priority)
            if include_content_hash:
                content_duplicates = (
                    self.document_repo.find_duplicates_by_content_hash()
                )
                for content_hash, docs in content_duplicates:
                    criteria = f"Exact content match (hash: {content_hash[:16]}...)"
                    duplicates.append((criteria, docs))
                    logger.info(f"Found {len(docs)} documents with exact content match")

            # 2. File size and similar names (medium priority)
            size_duplicates = self.document_repo.find_duplicates_by_size_and_name()
            for file_size, docs in size_duplicates:
                # Only include if not already found as content duplicates
                if not self._already_in_duplicates(docs, duplicates):
                    duplicates.append((f"File size: {file_size} bytes", docs))

            # 3. Similar titles (lower priority)
            if include_title_similarity:
                title_duplicates = self.document_repo.find_similar_documents_by_title(
                    title_similarity_threshold
                )
                for criteria, docs in title_duplicates:
                    # Only include if not already found
                    if not self._already_in_duplicates(docs, duplicates):
                        duplicates.append((criteria, docs))

            logger.info(
                f"Found {len(duplicates)} groups of potential duplicate documents"
            )
            return duplicates

        except Exception as e:
            logger.error(f"Failed to find duplicate documents: {e}")
            raise

    def _already_in_duplicates(
        self,
        docs: list[DocumentModel],
        existing_duplicates: list[tuple[str, list[DocumentModel]]],
    ) -> bool:
        """
        Check if documents are already included in existing duplicate groups.
        Args:
            docs: Documents to check
            existing_duplicates: Existing duplicate groups
        Returns:
            True if any document is already in a duplicate group
        """
        doc_ids = {doc.id for doc in docs}
        for _, existing_docs in existing_duplicates:
            existing_ids = {doc.id for doc in existing_docs}
            if doc_ids.intersection(existing_ids):
                return True
        return False

    def resolve_duplicate_documents(
        self,
        duplicate_group: list[DocumentModel],
        keep_document_id: int,
        remove_files: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve a group of duplicate documents by keeping one and removing others.
        Args:
            duplicate_group: List of duplicate documents
            keep_document_id: ID of document to keep
            remove_files: Whether to remove managed files of duplicates
        Returns:
            Dictionary with resolution results
        """
        try:
            result = {
                "kept_document_id": keep_document_id,
                "removed_documents": [],
                "errors": [],
            }

            # Validate that keep_document_id is in the group
            keep_doc = None
            for doc in duplicate_group:
                if doc.id == keep_document_id:
                    keep_doc = doc
                    break

            if not keep_doc:
                raise ValueError(
                    f"Document ID {keep_document_id} not found in duplicate group"
                )

            # Remove other documents
            for doc in duplicate_group:
                if doc.id != keep_document_id:
                    try:
                        success = self.delete_document(doc.id, remove_vector_index=True)
                        if success:
                            result["removed_documents"].append(
                                {
                                    "id": doc.id,
                                    "title": doc.title,
                                    "file_path": doc.file_path,
                                }
                            )
                        else:
                            result["errors"].append(
                                f"Failed to delete document {doc.id}"
                            )
                    except Exception as e:
                        result["errors"].append(
                            f"Error deleting document {doc.id}: {e}"
                        )
                        logger.error(f"Error deleting duplicate document {doc.id}: {e}")

            logger.info(
                f"Resolved duplicate group: kept document {keep_document_id}, "
                f"removed {len(result['removed_documents'])} duplicates"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to resolve duplicate documents: {e}")
            raise

    def get_library_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive library statistics.
        Returns:
            Dictionary with various statistics
        """
        try:
            stats = {}
            # Document statistics - flatten to top level for backward compatibility
            doc_stats = self.document_repo.get_statistics()
            stats.update(doc_stats)

            # Convert bytes to MB for user-friendly display
            # Use higher precision for small files to avoid 0.0 display issues
            if "total_size_bytes" in stats and stats["total_size_bytes"]:
                total_bytes = stats["total_size_bytes"]
                # Use 4 decimal places to handle small files better, then round to 2 for display
                total_mb = total_bytes / (1024 * 1024)
                stats["total_size_mb"] = round(total_mb, 4) if total_mb < 0.01 else round(total_mb, 2)
            else:
                stats["total_size_mb"] = 0.0

            if "average_size_bytes" in stats and stats["average_size_bytes"]:
                avg_bytes = stats["average_size_bytes"]
                # Use 4 decimal places to handle small files better, then round to 2 for display
                avg_mb = avg_bytes / (1024 * 1024)
                stats["average_size_mb"] = round(avg_mb, 4) if avg_mb < 0.01 else round(avg_mb, 2)
            else:
                stats["average_size_mb"] = 0.0

            # Calculate unique content and duplicate statistics
            try:
                # Count unique content hashes
                unique_content_query = """
                SELECT COUNT(DISTINCT content_hash) as unique_count
                FROM documents
                WHERE content_hash IS NOT NULL AND content_hash != ''
                """
                unique_result = self.document_repo.db.fetch_one(unique_content_query)
                stats["unique_content_count"] = unique_result["unique_count"] if unique_result else 0

                # Count duplicate groups (groups with more than 1 document sharing same content_hash)
                duplicate_groups_query = """
                SELECT COUNT(*) as group_count
                FROM (
                    SELECT content_hash
                    FROM documents
                    WHERE content_hash IS NOT NULL AND content_hash != ''
                    GROUP BY content_hash
                    HAVING COUNT(*) > 1
                ) duplicate_groups
                """
                duplicate_result = self.document_repo.db.fetch_one(duplicate_groups_query)
                stats["duplicate_groups"] = duplicate_result["group_count"] if duplicate_result else 0
            except Exception as e:
                logger.warning(f"Failed to calculate content statistics: {e}")
                stats["unique_content_count"] = 0
                stats["duplicate_groups"] = 0

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

    def cleanup_library(
        self,
        remove_missing_files: bool = True,
        remove_orphaned_files: bool = True,
        optimize_database: bool = True,
        cleanup_temp_files: bool = True,
        verify_integrity: bool = False,
    ) -> dict[str, Any]:
        """
        Perform comprehensive library cleanup operations.

        This method orchestrates various cleanup operations to maintain library health.
        Each operation is performed independently and failures in one operation do not
        prevent others from completing.

        Args:
            remove_missing_files: Remove document records for missing files
            remove_orphaned_files: Remove files in documents directory not in database
            optimize_database: Run database optimization (VACUUM/ANALYZE)
            cleanup_temp_files: Clean up temporary files in various locations
            verify_integrity: Verify and report integrity issues

        Returns:
            Dictionary with cleanup results and error summary

        Raises:
            Exception: If critical cleanup coordination fails
        """
        try:
            results = self._initialize_cleanup_results()

            # Execute cleanup operations in order of importance
            self._cleanup_vector_indexes(results)

            if remove_missing_files:
                self._cleanup_missing_documents(results)

            if remove_orphaned_files:
                self._cleanup_orphaned_files_operation(results)

            if cleanup_temp_files:
                self._cleanup_temporary_files_operation(results)

            if optimize_database:
                self._perform_database_optimization(results)

            if verify_integrity:
                self._perform_integrity_verification(results)

            return self._finalize_cleanup_results(results)

        except Exception as e:
            logger.error(f"Critical failure during library cleanup coordination: {e}")
            raise

    def _cleanup_documents_with_missing_files(self) -> int:
        """
        Remove document records where the referenced file no longer exists.
        Returns:
            Number of documents removed
        """
        count = 0
        try:
            # Get all documents
            documents = self.document_repo.find_all()
            for doc in documents:
                if doc.file_path and not Path(doc.file_path).exists():
                    try:
                        if self.document_repo.delete(doc.id):
                            count += 1
                            logger.debug(
                                f"Removed document {doc.id} with missing file: {doc.file_path}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to remove document {doc.id}: {e}")
        except Exception as e:
            logger.error(f"Error during missing file cleanup: {e}")
            raise
        return count

    def _cleanup_orphaned_files(self) -> int:
        """
        Remove files in documents directory that are not referenced in database.
        Returns:
            Number of files removed
        """
        count = 0
        try:
            if not self.documents_dir.exists():
                return 0

            # Get all file paths from database
            db_files = set()
            documents = self.document_repo.find_all()
            for doc in documents:
                if doc.file_path:
                    db_files.add(Path(doc.file_path).name)

            # Check files in documents directory
            for file_path in self.documents_dir.iterdir():
                if file_path.is_file() and file_path.name not in db_files:
                    try:
                        file_path.unlink()
                        count += 1
                        logger.debug(f"Removed orphaned file: {file_path}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to remove orphaned file {file_path}: {e}"
                        )
        except Exception as e:
            logger.error(f"Error during orphaned file cleanup: {e}")
            raise
        return count

    def _cleanup_temp_files(self) -> int:
        """
        Clean up temporary files in various locations.
        Returns:
            Number of temporary files cleaned
        """
        count = 0
        temp_patterns = [
            "*.tmp",
            "*.temp",
            "*~",
            ".DS_Store",
            "Thumbs.db",
            "*.bak",
            "*.swp",
            "*.swo",
        ]

        try:
            # Clean temp files from documents directory
            if self.documents_dir.exists():
                for pattern in temp_patterns:
                    for temp_file in self.documents_dir.glob(pattern):
                        try:
                            temp_file.unlink()
                            count += 1
                            logger.debug(f"Removed temp file: {temp_file}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove temp file {temp_file}: {e}"
                            )

            # Clean temp files from system temp directory
            import tempfile

            temp_dir = Path(tempfile.gettempdir())
            ai_temp_pattern = "ai_pdf_scholar_*"
            for temp_item in temp_dir.glob(ai_temp_pattern):
                try:
                    if temp_item.is_file():
                        temp_item.unlink()
                        count += 1
                    elif temp_item.is_dir():
                        shutil.rmtree(temp_item)
                        count += 1
                    logger.debug(f"Removed temp item: {temp_item}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp item {temp_item}: {e}")

        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            raise
        return count

    def _optimize_database(self) -> None:
        """
        Perform database optimization operations.
        """
        try:
            # Run VACUUM to reclaim space and defragment
            self.db.execute("VACUUM")
            logger.debug("Database VACUUM completed")

            # Run ANALYZE to update query planner statistics
            self.db.execute("ANALYZE")
            logger.debug("Database ANALYZE completed")

            # Optionally rebuild indexes if needed
            # This is usually not necessary unless corruption is suspected

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            raise

    def _verify_library_integrity(self) -> int:
        """
        Verify overall library integrity and return issue count.
        Returns:
            Number of integrity issues found
        """
        issue_count = 0
        try:
            documents = self.document_repo.find_all()
            for doc in documents:
                integrity_result = self.verify_document_integrity(doc.id)
                if not integrity_result.get("is_healthy", False):
                    issue_count += 1
                    logger.warning(
                        f"Integrity issue found for document {doc.id}: {integrity_result.get('errors', [])}"
                    )
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            raise
        return issue_count

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
                        current_hash = self.hash_service.calculate_file_hash(
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

    # Additional cleanup helper methods added for better code organization

    def _initialize_cleanup_results(self) -> dict[str, Any]:
        """Initialize cleanup results dictionary with default values."""
        return {
            "orphaned_indexes_cleaned": 0,
            "invalid_indexes_cleaned": 0,
            "missing_file_documents_removed": 0,
            "orphaned_files_removed": 0,
            "temp_files_cleaned": 0,
            "database_optimized": False,
            "integrity_issues_found": 0,
            "errors": [],
            "operation_start_time": datetime.now().isoformat(),
        }

    def _cleanup_vector_indexes(self, results: dict[str, Any]) -> None:
        """
        Clean up orphaned and invalid vector indexes.

        Args:
            results: Results dictionary to update with cleanup statistics
        """
        # Clean orphaned vector indexes (indexes without corresponding documents)
        try:
            orphaned_cleaned = self.vector_repo.cleanup_orphaned_indexes()
            results["orphaned_indexes_cleaned"] = orphaned_cleaned
            logger.debug(f"Cleaned {orphaned_cleaned} orphaned vector indexes")
        except Exception as e:
            error_msg = f"Vector index orphan cleanup error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to cleanup orphaned vector indexes: {e}")

        # Clean invalid vector indexes (corrupted or inaccessible indexes)
        try:
            invalid_cleaned = self.vector_repo.cleanup_invalid_indexes(
                remove_files=True
            )
            results["invalid_indexes_cleaned"] = invalid_cleaned
            logger.debug(f"Cleaned {invalid_cleaned} invalid vector indexes")
        except Exception as e:
            error_msg = f"Invalid vector index cleanup error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to cleanup invalid vector indexes: {e}")

    def _cleanup_missing_documents(self, results: dict[str, Any]) -> None:
        """
        Remove database records for documents whose files no longer exist.

        Args:
            results: Results dictionary to update with cleanup statistics
        """
        try:
            missing_removed = self._cleanup_documents_with_missing_files()
            results["missing_file_documents_removed"] = missing_removed
            logger.debug(f"Removed {missing_removed} documents with missing files")
        except Exception as e:
            error_msg = f"Missing file document cleanup error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to cleanup documents with missing files: {e}")

    def _cleanup_orphaned_files_operation(self, results: dict[str, Any]) -> None:
        """
        Remove files in documents directory that are not referenced in database.

        Args:
            results: Results dictionary to update with cleanup statistics
        """
        try:
            orphaned_removed = self._cleanup_orphaned_files()
            results["orphaned_files_removed"] = orphaned_removed
            logger.debug(f"Removed {orphaned_removed} orphaned files")
        except Exception as e:
            error_msg = f"Orphaned file cleanup error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to cleanup orphaned files: {e}")

    def _cleanup_temporary_files_operation(self, results: dict[str, Any]) -> None:
        """
        Clean up temporary files from various system locations.

        Args:
            results: Results dictionary to update with cleanup statistics
        """
        try:
            temp_cleaned = self._cleanup_temp_files()
            results["temp_files_cleaned"] = temp_cleaned
            logger.debug(f"Cleaned {temp_cleaned} temporary files")
        except Exception as e:
            error_msg = f"Temporary file cleanup error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to cleanup temporary files: {e}")

    def _perform_database_optimization(self, results: dict[str, Any]) -> None:
        """
        Perform database optimization operations (VACUUM, ANALYZE).

        Args:
            results: Results dictionary to update with optimization status
        """
        try:
            self._optimize_database()
            results["database_optimized"] = True
            logger.debug("Database optimization completed successfully")
        except Exception as e:
            error_msg = f"Database optimization error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to optimize database: {e}")

    def _perform_integrity_verification(self, results: dict[str, Any]) -> None:
        """
        Perform comprehensive library integrity verification.

        Args:
            results: Results dictionary to update with integrity check results
        """
        try:
            integrity_issues = self._verify_library_integrity()
            results["integrity_issues_found"] = integrity_issues
            if integrity_issues > 0:
                logger.warning(
                    f"Found {integrity_issues} integrity issues during cleanup verification"
                )
            else:
                logger.debug(
                    "Library integrity verification completed - no issues found"
                )
        except Exception as e:
            error_msg = f"Integrity verification error: {e}"
            results["errors"].append(error_msg)
            logger.warning(f"Failed to verify library integrity: {e}")

    def _finalize_cleanup_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        Finalize cleanup results with summary statistics and completion timestamp.

        Args:
            results: Populated results dictionary

        Returns:
            Finalized results dictionary with summary information
        """
        # Calculate total items cleaned
        total_items_cleaned = (
            results["orphaned_indexes_cleaned"]
            + results["invalid_indexes_cleaned"]
            + results["missing_file_documents_removed"]
            + results["orphaned_files_removed"]
            + results["temp_files_cleaned"]
        )

        # Add summary information
        results["total_items_cleaned"] = total_items_cleaned
        results["error_count"] = len(results["errors"])
        results["operation_end_time"] = datetime.now().isoformat()
        results["success"] = results["error_count"] == 0

        # Log completion summary
        if results["success"]:
            logger.info(
                f"Library cleanup completed successfully: {total_items_cleaned} items cleaned, "
                f"database optimization: {results['database_optimized']}"
            )
        else:
            logger.warning(
                f"Library cleanup completed with issues: {total_items_cleaned} items cleaned, "
                f"{results['error_count']} errors encountered"
            )

        return results
