"""
Document Repository
Implements data access layer for documents with advanced querying capabilities.
Provides methods for document search, filtering, and duplicate detection.
"""

import logging
from datetime import datetime
from typing import Any

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
        "description": "Repository for document data access with search.",
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

    def to_model(self, row: dict[str, Any]) -> DocumentModel:
        """Convert database row to DocumentModel."""
        return DocumentModel.from_database_row(row)

    def to_database_dict(self, model: DocumentModel) -> dict[str, Any]:
        """Convert DocumentModel to database dictionary."""
        return model.to_database_dict()

    def get_by_id(self, entity_id: int) -> DocumentModel | None:
        """Interface method - alias for find_by_id."""
        return self.find_by_id(entity_id)
        
    def get_by_ids(self, entity_ids: list[int]) -> list[DocumentModel]:
        """Get multiple documents by their IDs."""
        if not entity_ids:
            return []
            
        try:
            # Create placeholders for SQL IN clause
            placeholders = ",".join("?" * len(entity_ids))
            query = f"SELECT * FROM documents WHERE id IN ({placeholders})"
            rows = self.db.fetch_all(query, tuple(entity_ids))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get documents by IDs {entity_ids}: {e}")
            raise

    def find_by_hash(self, file_hash: str) -> DocumentModel | None:
        """Interface method - alias for find_by_file_hash."""
        return self.find_by_file_hash(file_hash)

    def find_by_file_hash(self, file_hash: str) -> DocumentModel | None:
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

    def find_by_file_path(self, file_path: str) -> DocumentModel | None:
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

    def find_by_content_hash(self, content_hash: str) -> DocumentModel | None:
        """
        Find documents by content hash (for duplicate detection).
        Args:
            content_hash: Content-based hash
        Returns:
            Document model or None if not found
        """
        try:
            query = "SELECT * FROM documents WHERE content_hash = ?"
            row = self.db.fetch_one(query, (content_hash,))
            if row:
                return self.to_model(dict(row))
            return None
        except Exception as e:
            logger.error(f"Failed to find document by content hash {content_hash}: {e}")
            raise

    def search_by_title(
        self, search_query: str, limit: int = 50
    ) -> list[DocumentModel]:
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
    ) -> list[DocumentModel]:
        """Interface method - search documents by query."""
        return self.search_by_title(query, limit)

    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[DocumentModel]:
        """Interface method - get all documents with pagination and sorting."""
        try:
            # Secure whitelist-based validation for sort_by parameter
            valid_sort_fields = {
                "created_at": "created_at",
                "updated_at": "updated_at",
                "last_accessed": "last_accessed",
                "title": "title",
                "file_size": "file_size",
            }

            # Use whitelist lookup to prevent injection
            safe_sort_by = valid_sort_fields.get(sort_by.lower(), "created_at")

            # Secure validation for sort_order using whitelist
            valid_sort_orders = {"asc": "ASC", "desc": "DESC"}
            safe_sort_order = valid_sort_orders.get(sort_order.lower(), "DESC")

            # Use parameterized query - build safe SQL using whitelisted values
            query = f"""
            SELECT * FROM documents
            ORDER BY {safe_sort_by} {safe_sort_order}
            LIMIT ? OFFSET ?
            """

            # Log the safe query for security auditing
            logger.debug(
                f"Executing secure query with sort_by='{safe_sort_by}', sort_order='{safe_sort_order}'"
            )

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

    def find_recent_documents(self, limit: int = 20) -> list[DocumentModel]:
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
                CASE WHEN last_accessed IS NOT NULL
                     THEN last_accessed ELSE created_at END DESC,
                created_at DESC
            LIMIT ?
            """
            rows = self.db.fetch_all(query, (limit,))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find recent documents: {e}")
            raise

    def find_by_size_range(
        self, min_size: int | None = None, max_size: int | None = None
    ) -> list[DocumentModel]:
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
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[DocumentModel]:
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

    def get_statistics(self) -> dict[str, Any]:
        """
        Get document repository statistics.
        Returns:
            Dictionary with various statistics
        """
        try:
            stats: dict[str, Any] = {}
            # Total count
            stats["total_documents"] = self.count()

            # Size and page statistics in one query
            main_query = """
            SELECT
                COUNT(*) as count,
                COALESCE(SUM(file_size), 0) as total_size,
                COALESCE(AVG(file_size), 0) as avg_size,
                COALESCE(SUM(page_count), 0) as total_pages,
                COALESCE(AVG(page_count), 0) as avg_pages,
                MIN(created_at) as oldest_date,
                MAX(created_at) as newest_date
            FROM documents
            """
            result = self.db.fetch_one(main_query)
            if result:
                result_dict = dict(result)
                stats["total_size_bytes"] = result_dict.get("total_size", 0) or 0
                stats["average_size_bytes"] = result_dict.get("avg_size", 0) or 0
                stats["total_pages"] = result_dict.get("total_pages", 0) or 0
                stats["average_pages"] = result_dict.get("avg_pages", 0) or 0
                stats["oldest_document_date"] = result_dict.get("oldest_date")
                stats["newest_document_date"] = result_dict.get("newest_date")
            else:
                # Empty database
                stats["total_size_bytes"] = 0
                stats["average_size_bytes"] = 0
                stats["total_pages"] = 0
                stats["average_pages"] = 0
                stats["oldest_document_date"] = None
                stats["newest_document_date"] = None

            return stats
        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            raise

    def find_duplicates_by_size_and_name(self) -> list[tuple[int, list[DocumentModel]]]:
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

    def find_duplicates_by_content_hash(self) -> list[tuple[str, list[DocumentModel]]]:
        """
        Find exact content duplicates based on content hash.
        Returns:
            List of tuples (content_hash, list_of_documents)
        """
        try:
            # Find documents with same content hash (excluding NULL values)
            query = """
            SELECT content_hash, COUNT(*) as count
            FROM documents
            WHERE content_hash IS NOT NULL AND content_hash != ''
            GROUP BY content_hash
            HAVING count > 1
            ORDER BY content_hash
            """
            hash_groups = self.db.fetch_all(query)
            duplicates = []
            for group in hash_groups:
                content_hash = group["content_hash"]
                docs = self.find_by_field("content_hash", content_hash)
                if len(docs) > 1:
                    duplicates.append((content_hash, docs))
            return duplicates
        except Exception as e:
            logger.error(f"Failed to find content-based duplicate documents: {e}")
            raise

    def find_similar_documents_by_title(
        self, similarity_threshold: float = 0.8
    ) -> list[tuple[str, list[DocumentModel]]]:
        """
        Find documents with similar titles using simple similarity matching.
        Args:
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
        Returns:
            List of tuples (similarity_reason, list_of_documents)
        """
        try:
            # Get all documents
            all_docs = self.find_all()
            similar_groups = []
            processed_ids = set()

            for i, doc1 in enumerate(all_docs):
                if doc1.id in processed_ids:
                    continue

                similar_docs = [doc1]
                for j, doc2 in enumerate(all_docs[i + 1 :], i + 1):
                    if doc2.id in processed_ids:
                        continue

                    # Simple title similarity check
                    similarity = self._calculate_title_similarity(
                        doc1.title, doc2.title
                    )
                    if similarity >= similarity_threshold:
                        similar_docs.append(doc2)
                        processed_ids.add(doc2.id)

                if len(similar_docs) > 1:
                    processed_ids.add(doc1.id)
                    similar_groups.append(
                        (
                            f"Similar titles (>{similarity_threshold * 100}% match)",
                            similar_docs,
                        )
                    )

            return similar_groups
        except Exception as e:
            logger.error(f"Failed to find similar documents by title: {e}")
            raise

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate simple similarity between two titles.
        Uses basic string similarity metrics.
        Args:
            title1: First title
            title2: Second title
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize titles (lowercase, strip whitespace)
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        if t1 == t2:
            return 1.0
        if not t1 or not t2:
            return 0.0

        # Simple Jaccard similarity using word sets
        words1 = set(t1.split())
        words2 = set(t2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def advanced_search(
        self,
        title_contains: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        min_pages: int | None = None,
        max_pages: int | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        has_vector_index: bool | None = None,
        limit: int = 50,
        # Keep old parameter names for backward compatibility
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DocumentModel]:
        """
        Advanced search with multiple criteria.
        Args:
            title_contains: Search term for title
            min_size: Minimum file size
            max_size: Maximum file size
            min_pages: Minimum page count
            max_pages: Maximum page count
            start_date: Start date filter
            end_date: End date filter
            has_vector_index: Filter by vector index existence
            limit: Maximum results
        Returns:
            List of matching documents
        """
        try:
            conditions: list[str] = []
            params: list[Any] = []
            # Title search
            if title_contains:
                conditions.append("d.title LIKE ?")
                params.append(f"%{title_contains}%")
            # Size range
            if min_size is not None:
                conditions.append("d.file_size >= ?")
                params.append(min_size)
            if max_size is not None:
                conditions.append("d.file_size <= ?")
                params.append(max_size)
            # Page range
            if min_pages is not None:
                conditions.append("d.page_count >= ?")
                params.append(min_pages)
            if max_pages is not None:
                conditions.append("d.page_count <= ?")
                params.append(max_pages)
            # Date range - prioritize new parameter names
            start_date_to_use = created_after or start_date
            end_date_to_use = created_before or end_date
            if start_date_to_use is not None:
                conditions.append("d.created_at >= ?")
                params.append(start_date_to_use.isoformat())
            if end_date_to_use is not None:
                conditions.append("d.created_at <= ?")
                params.append(end_date_to_use.isoformat())
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
