"""
Document Repository
Implements data access layer for documents with advanced querying capabilities.
Provides methods for document search, filtering, and duplicate detection.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.interfaces.repository_interfaces import IDocumentRepository

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository[DocumentModel], IDocumentRepository):
    """
    {
        "name": "DocumentRepository",
        "version": "1.0.0",
        "description": "Repository for document data access with advanced search and filtering.",
        "dependencies": ["BaseRepository", "DocumentModel", "DatabaseConnection"],
        "interface": {
            "inputs": ["database_connection: DatabaseConnection"],
            "outputs": "Advanced document CRUD operations with search capabilities"
        }
    }
    Repository for document entities with advanced query capabilities.
    Supports search, filtering, duplicate detection, and statistics.
    """

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize document repository.
        Args:
            db_connection: Database connection instance
        """
        super().__init__(db_connection)

    def get_table_name(self) -> str:
        """Get the database table name."""
        return "documents"

    def to_model(self, row: Dict[str, Any]) -> DocumentModel:
        """Convert database row to DocumentModel."""
        return DocumentModel.from_database_row(row)

    def to_database_dict(self, model: DocumentModel) -> Dict[str, Any]:
        """Convert DocumentModel to database dictionary."""
        return model.to_database_dict()

    def get_by_id(self, entity_id: int) -> Optional[DocumentModel]:
        """Interface method - alias for find_by_id."""
        return self.find_by_id(entity_id)

    def find_by_hash(self, file_hash: str) -> Optional[DocumentModel]:
        """Interface method - alias for find_by_file_hash."""
        return self.find_by_file_hash(file_hash)

    def find_by_file_hash(self, file_hash: str) -> Optional[DocumentModel]:
        """
        Find document by file hash.
        Args:
            file_hash: File content hash
        Returns:
            Document model or None if not found
        """
        try:
            query = "SELECT * FROM documents WHERE file_hash = ?"
            row = self.db.fetch_one(query, (file_hash,))
            if row:
                return self.to_model(dict(row))
            return None
        except Exception as e:
            logger.error(f"Failed to find document by file hash {file_hash}: {e}")
            raise

    def find_by_file_path(self, file_path: str) -> Optional[DocumentModel]:
        """
        Find document by its absolute file path.
        Args:
            file_path: Absolute path to the document file
        Returns:
            Document model or None if not found
        """
        try:
            query = "SELECT * FROM documents WHERE file_path = ?"
            row = self.db.fetch_one(query, (file_path,))
            if row:
                return self.to_model(dict(row))
            return None
        except Exception as e:
            logger.error(f"Failed to find document by file path {file_path}: {e}")
            raise

    def find_by_content_hash(self, content_hash: str) -> Optional[DocumentModel]:
        """
        Find documents by content hash (for duplicate detection).
        Note: This requires adding content_hash column to database.
        Args:
            content_hash: Content-based hash
        Returns:
            List of documents with matching content
        """
        try:
            # For now, return None since content_hash column doesn't exist yet
            # TODO: Add content_hash column in future migration
            logger.warning(
                "Content hash search not implemented yet - requires database migration"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to find document by content hash {content_hash}: {e}")
            raise

    def search_by_title(
        self, search_query: str, limit: int = 50
    ) -> List[DocumentModel]:
        """
        Search documents by title.
        Args:
            search_query: Search term for title
            limit: Maximum number of results
        Returns:
            List of matching documents
        """
        try:
            query = """
            SELECT * FROM documents
            WHERE title LIKE ?
            ORDER BY title
            LIMIT ?
            """
            search_pattern = f"%{search_query}%"
            rows = self.db.fetch_all(query, (search_pattern, limit))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to search documents by title '{search_query}': {e}")
            raise

    def search(
        self, query: str, limit: int = 50, offset: int = 0
    ) -> List[DocumentModel]:
        """Interface method - search documents by query."""
        return self.search_by_title(query, limit)

    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[DocumentModel]:
        """Interface method - get all documents with pagination and sorting."""
        try:
            # Validate sort_by parameter
            valid_sort_fields = [
                "created_at",
                "updated_at",
                "last_accessed",
                "title",
                "file_size",
            ]
            if sort_by not in valid_sort_fields:
                sort_by = "created_at"
            # Validate sort_order
            if sort_order.lower() not in ["asc", "desc"]:
                sort_order = "desc"
            query = f"""
            SELECT * FROM documents
            ORDER BY {sort_by} {sort_order.upper()}
            LIMIT ? OFFSET ?
            """
            rows = self.db.fetch_all(query, (limit, offset))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all documents: {e}")
            raise

    def create(self, entity: DocumentModel) -> DocumentModel:
        """Interface method - create new document."""
        return super().create(entity)

    def update(self, entity: DocumentModel) -> DocumentModel:
        """Interface method - update existing document."""
        return super().update(entity)

    def delete(self, entity_id: int) -> bool:
        """Interface method - delete document by ID."""
        return super().delete(entity_id)

    def find_recent_documents(self, limit: int = 20) -> List[DocumentModel]:
        """
        Find recently accessed documents.
        Args:
            limit: Maximum number of documents to return
        Returns:
            List of recently accessed documents
        """
        try:
            query = """
            SELECT * FROM documents
            ORDER BY
                CASE WHEN last_accessed IS NOT NULL THEN last_accessed ELSE created_at END DESC,
                created_at DESC
            LIMIT ?
            """
            rows = self.db.fetch_all(query, (limit,))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find recent documents: {e}")
            raise

    def find_by_size_range(
        self, min_size: Optional[int] = None, max_size: Optional[int] = None
    ) -> List[DocumentModel]:
        """
        Find documents by file size range.
        Args:
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
        Returns:
            List of documents in size range
        """
        try:
            conditions = []
            params = []
            if min_size is not None:
                conditions.append("file_size >= ?")
                params.append(min_size)
            if max_size is not None:
                conditions.append("file_size <= ?")
                params.append(max_size)
            if not conditions:
                return self.find_all()
            where_clause = " AND ".join(conditions)
            query = f"SELECT * FROM documents WHERE {where_clause} ORDER BY file_size"
            rows = self.db.fetch_all(query, tuple(params))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find documents by size range: {e}")
            raise

    def find_by_date_range(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[DocumentModel]:
        """
        Find documents by creation date range.
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        Returns:
            List of documents in date range
        """
        try:
            conditions = []
            params = []
            if start_date is not None:
                conditions.append("created_at >= ?")
                params.append(start_date.isoformat())
            if end_date is not None:
                conditions.append("created_at <= ?")
                params.append(end_date.isoformat())
            if not conditions:
                return self.find_all()
            where_clause = " AND ".join(conditions)
            query = (
                f"SELECT * FROM documents WHERE {where_clause} ORDER BY created_at DESC"
            )
            rows = self.db.fetch_all(query, tuple(params))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find documents by date range: {e}")
            raise

    def update_access_time(self, document_id: int) -> bool:
        """
        Update the last accessed time for a document.
        Args:
            document_id: Document ID
        Returns:
            True if updated successfully
        """
        try:
            query = "UPDATE documents SET last_accessed = ? WHERE id = ?"
            current_time = datetime.now().isoformat()
            result = self.db.execute(query, (current_time, document_id))
            if result.rowcount > 0:
                logger.debug(f"Updated access time for document {document_id}")
                return True
            else:
                logger.warning(
                    f"No document found with ID {document_id} for access time update"
                )
                return False
        except Exception as e:
            logger.error(
                f"Failed to update access time for document {document_id}: {e}"
            )
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get document repository statistics.
        Returns:
            Dictionary with various statistics
        """
        try:
            stats: Dict[str, Any] = {}
            # Total count
            stats["total_documents"] = self.count()
            # Size statistics
            size_query = """
            SELECT
                COUNT(*) as count,
                AVG(file_size) as avg_size,
                MIN(file_size) as min_size,
                MAX(file_size) as max_size,
                SUM(file_size) as total_size
            FROM documents
            """
            size_result = self.db.fetch_one(size_query)
            if size_result:
                stats["size_stats"] = dict(size_result)
            # Page count statistics (if available)
            page_query = """
            SELECT
                COUNT(*) as count,
                AVG(page_count) as avg_pages,
                MIN(page_count) as min_pages,
                MAX(page_count) as max_pages
            FROM documents
            WHERE page_count IS NOT NULL
            """
            page_result = self.db.fetch_one(page_query)
            if page_result:
                stats["page_stats"] = dict(page_result)
            # Recent activity
            recent_query = """
            SELECT COUNT(*) as recent_count
            FROM documents
            WHERE last_accessed > datetime('now', '-7 days')
            """
            recent_result = self.db.fetch_one(recent_query)
            if recent_result:
                stats["recent_activity"] = dict(recent_result)
            return stats
        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            raise

    def find_duplicates_by_size_and_name(self) -> List[Tuple[int, List[DocumentModel]]]:
        """
        Find potential duplicates based on file size and similar names.
        Returns:
            List of tuples (file_size, list_of_documents)
        """
        try:
            # Find documents with same file size
            query = """
            SELECT file_size, COUNT(*) as count
            FROM documents
            GROUP BY file_size
            HAVING count > 1
            ORDER BY file_size
            """
            size_groups = self.db.fetch_all(query)
            duplicates = []
            for group in size_groups:
                file_size = group["file_size"]
                docs = self.find_by_field("file_size", file_size)
                if len(docs) > 1:
                    duplicates.append((file_size, docs))
            return duplicates
        except Exception as e:
            logger.error(f"Failed to find duplicate documents: {e}")
            raise

    def advanced_search(
        self,
        title_query: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        has_vector_index: Optional[bool] = None,
        limit: int = 50,
    ) -> List[DocumentModel]:
        """
        Advanced search with multiple criteria.
        Args:
            title_query: Search term for title
            min_size: Minimum file size
            max_size: Maximum file size
            start_date: Start date filter
            end_date: End date filter
            has_vector_index: Filter by vector index existence
            limit: Maximum results
        Returns:
            List of matching documents
        """
        try:
            conditions: List[str] = []
            params: List[Any] = []
            # Title search
            if title_query:
                conditions.append("d.title LIKE ?")
                params.append(f"%{title_query}%")
            # Size range
            if min_size is not None:
                conditions.append("d.file_size >= ?")
                params.append(min_size)
            if max_size is not None:
                conditions.append("d.file_size <= ?")
                params.append(max_size)
            # Date range
            if start_date is not None:
                conditions.append("d.created_at >= ?")
                params.append(start_date.isoformat())
            if end_date is not None:
                conditions.append("d.created_at <= ?")
                params.append(end_date.isoformat())
            # Vector index filter
            base_query = "SELECT d.* FROM documents d"
            if has_vector_index is not None:
                base_query += " LEFT JOIN vector_indexes vi ON d.id = vi.document_id"
                if has_vector_index:
                    conditions.append("vi.id IS NOT NULL")
                else:
                    conditions.append("vi.id IS NULL")
            # Build final query
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
                query = base_query + where_clause
            else:
                query = base_query
            query += " ORDER BY d.created_at DESC LIMIT ?"
            params.append(limit)
            rows = self.db.fetch_all(query, tuple(params))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to perform advanced search: {e}")
            raise
