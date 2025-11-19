"""
Multi-Document RAG Repository Implementations
Concrete implementations of multi-document repository interfaces.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.multi_document_models import (
    CrossDocumentQueryModel,
    MultiDocumentCollectionModel,
    MultiDocumentIndexModel,
)
from src.interfaces.repository_interfaces import (
    ICrossDocumentQueryRepository,
    IMultiDocumentCollectionRepository,
    IMultiDocumentIndexRepository,
)

logger = logging.getLogger(__name__)


class MultiDocumentCollectionRepository(IMultiDocumentCollectionRepository):
    """Repository for multi-document collections."""

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure the collections table exists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS multi_document_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        document_ids TEXT NOT NULL,  -- JSON array
                        document_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to create collections table: {e}")
            raise

    def create(
        self, entity: MultiDocumentCollectionModel
    ) -> MultiDocumentCollectionModel:
        """Create a new collection."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    INSERT INTO multi_document_collections
                    (name, description, document_ids, document_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["name"],
                        data["description"],
                        data["document_ids"],
                        data["document_count"],
                        data["created_at"],
                        data["updated_at"],
                    ),
                )

                entity.id = cursor.lastrowid
                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def get_by_id(self, entity_id: int) -> MultiDocumentCollectionModel | None:
        """Get collection by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections WHERE id = ?
                """,
                    (entity_id,),
                )

                row = cursor.fetchone()
                if row:
                    return MultiDocumentCollectionModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get collection {entity_id}: {e}")
            raise

    def get_by_ids(self, entity_ids: list[int]) -> list[MultiDocumentCollectionModel]:
        """Get multiple collections by IDs."""
        if not entity_ids:
            return []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(entity_ids))
                cursor.execute(
                    f"""
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections WHERE id IN ({placeholders})
                """,  # noqa: S608 - safe SQL construction
                    entity_ids,
                )

                rows = cursor.fetchall()
                return [
                    MultiDocumentCollectionModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get collections {entity_ids}: {e}")
            raise

    def update(
        self, entity: MultiDocumentCollectionModel
    ) -> MultiDocumentCollectionModel:
        """Update an existing collection."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    UPDATE multi_document_collections
                    SET name = ?, description = ?, document_ids = ?, document_count = ?, updated_at = ?
                    WHERE id = ?
                """,
                    (
                        data["name"],
                        data["description"],
                        data["document_ids"],
                        data["document_count"],
                        data["updated_at"],
                        entity.id,
                    ),
                )

                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to update collection {entity.id}: {e}")
            raise

    def delete(self, entity_id: int) -> bool:
        """Delete a collection by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM multi_document_collections WHERE id = ?", (entity_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete collection {entity_id}: {e}")
            raise

    def get_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[MultiDocumentCollectionModel]:
        """Get all collections with pagination."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

                rows = cursor.fetchall()
                return [
                    MultiDocumentCollectionModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get all collections: {e}")
            raise

    def find_by_name(self, name: str) -> MultiDocumentCollectionModel | None:
        """Find collection by name."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections WHERE name = ?
                """,
                    (name,),
                )

                row = cursor.fetchone()
                if row:
                    return MultiDocumentCollectionModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to find collection by name {name}: {e}")
            raise

    def search(self, query: str, limit: int = 50) -> list[MultiDocumentCollectionModel]:
        """Search collections by name or description."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                search_pattern = f"%{query}%"
                cursor.execute(
                    """
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections
                    WHERE name LIKE ? OR description LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (search_pattern, search_pattern, limit),
                )

                rows = cursor.fetchall()
                return [
                    MultiDocumentCollectionModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to search collections: {e}")
            raise

    def get_collections_containing_document(
        self, document_id: int
    ) -> list[MultiDocumentCollectionModel]:
        """Get all collections that contain a specific document."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, description, document_ids, document_count, created_at, updated_at
                    FROM multi_document_collections
                """
                )

                rows = cursor.fetchall()
                collections = []
                for row in rows:
                    collection = MultiDocumentCollectionModel.from_database_row(
                        dict[str, Any](row)
                    )
                    if document_id in collection.document_ids:
                        collections.append(collection)

                return collections
        except Exception as e:
            logger.error(
                f"Failed to get collections containing document {document_id}: {e}"
            )
            raise

    def count(self) -> int:
        """Get total collection count."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM multi_document_collections")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count collections: {e}")
            raise


class MultiDocumentIndexRepository(IMultiDocumentIndexRepository):
    """Repository for multi-document indexes."""

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure the indexes table exists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS multi_document_indexes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id INTEGER NOT NULL,
                        index_path TEXT NOT NULL,
                        index_hash TEXT NOT NULL,
                        embedding_model TEXT NOT NULL DEFAULT 'text-embedding-ada-002',
                        chunk_count INTEGER,
                        created_at TEXT NOT NULL,
                        metadata TEXT,  -- JSON
                        FOREIGN KEY (collection_id) REFERENCES multi_document_collections (id)
                    )
                """
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to create indexes table: {e}")
            raise

    def create(self, entity: MultiDocumentIndexModel) -> MultiDocumentIndexModel:
        """Create a new index."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    INSERT INTO multi_document_indexes
                    (collection_id, index_path, index_hash, embedding_model, chunk_count, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["collection_id"],
                        data["index_path"],
                        data["index_hash"],
                        data["embedding_model"],
                        data["chunk_count"],
                        data["created_at"],
                        data["metadata"],
                    ),
                )

                entity.id = cursor.lastrowid
                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise

    def get_by_id(self, entity_id: int) -> MultiDocumentIndexModel | None:
        """Get index by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, index_path, index_hash, embedding_model,
                           chunk_count, created_at, metadata
                    FROM multi_document_indexes WHERE id = ?
                """,
                    (entity_id,),
                )

                row = cursor.fetchone()
                if row:
                    return MultiDocumentIndexModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get index {entity_id}: {e}")
            raise

    def get_by_ids(self, entity_ids: list[int]) -> list[MultiDocumentIndexModel]:
        """Get multiple indexes by IDs."""
        if not entity_ids:
            return []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(entity_ids))
                cursor.execute(
                    f"""
                    SELECT id, collection_id, index_path, index_hash, embedding_model,
                           chunk_count, created_at, metadata
                    FROM multi_document_indexes WHERE id IN ({placeholders})
                """,  # noqa: S608 - safe SQL construction
                    entity_ids,
                )

                rows = cursor.fetchall()
                return [
                    MultiDocumentIndexModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get indexes {entity_ids}: {e}")
            raise

    def update(self, entity: MultiDocumentIndexModel) -> MultiDocumentIndexModel:
        """Update an existing index."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    UPDATE multi_document_indexes
                    SET collection_id = ?, index_path = ?, index_hash = ?, embedding_model = ?,
                        chunk_count = ?, metadata = ?
                    WHERE id = ?
                """,
                    (
                        data["collection_id"],
                        data["index_path"],
                        data["index_hash"],
                        data["embedding_model"],
                        data["chunk_count"],
                        data["metadata"],
                        entity.id,
                    ),
                )

                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to update index {entity.id}: {e}")
            raise

    def delete(self, entity_id: int) -> bool:
        """Delete an index by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM multi_document_indexes WHERE id = ?", (entity_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete index {entity_id}: {e}")
            raise

    def get_by_collection_id(
        self, collection_id: int
    ) -> MultiDocumentIndexModel | None:
        """Get index by collection ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, index_path, index_hash, embedding_model,
                           chunk_count, created_at, metadata
                    FROM multi_document_indexes WHERE collection_id = ?
                """,
                    (collection_id,),
                )

                row = cursor.fetchone()
                if row:
                    return MultiDocumentIndexModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get index for collection {collection_id}: {e}")
            raise

    def find_by_hash(self, index_hash: str) -> MultiDocumentIndexModel | None:
        """Find index by hash."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, index_path, index_hash, embedding_model,
                           chunk_count, created_at, metadata
                    FROM multi_document_indexes WHERE index_hash = ?
                """,
                    (index_hash,),
                )

                row = cursor.fetchone()
                if row:
                    return MultiDocumentIndexModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to find index by hash {index_hash}: {e}")
            raise

    def get_orphaned_indexes(self) -> list[MultiDocumentIndexModel]:
        """Get indexes without corresponding collections."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT i.id, i.collection_id, i.index_path, i.index_hash, i.embedding_model,
                           i.chunk_count, i.created_at, i.metadata
                    FROM multi_document_indexes i
                    LEFT JOIN multi_document_collections c ON i.collection_id = c.id
                    WHERE c.id IS NULL
                """
                )

                rows = cursor.fetchall()
                return [
                    MultiDocumentIndexModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get orphaned indexes: {e}")
            raise

    def cleanup_orphaned(self) -> int:
        """Remove orphaned indexes."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM multi_document_indexes
                    WHERE collection_id NOT IN (
                        SELECT id FROM multi_document_collections
                    )
                """
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned indexes: {e}")
            raise


class CrossDocumentQueryRepository(ICrossDocumentQueryRepository):
    """Repository for cross-document queries."""

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure the queries table exists."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cross_document_queries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id INTEGER NOT NULL,
                        query_text TEXT NOT NULL,
                        user_id TEXT,
                        response_text TEXT,
                        confidence_score REAL,
                        sources TEXT,  -- JSON
                        cross_references TEXT,  -- JSON
                        status TEXT NOT NULL DEFAULT 'pending',
                        error_message TEXT,
                        processing_time_ms INTEGER,
                        tokens_used INTEGER,
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        FOREIGN KEY (collection_id) REFERENCES multi_document_collections (id)
                    )
                """
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to create queries table: {e}")
            raise

    def create(self, entity: CrossDocumentQueryModel) -> CrossDocumentQueryModel:
        """Create a new query."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    INSERT INTO cross_document_queries
                    (collection_id, query_text, user_id, response_text, confidence_score,
                     sources, cross_references, status, error_message, processing_time_ms,
                     tokens_used, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["collection_id"],
                        data["query_text"],
                        data["user_id"],
                        data["response_text"],
                        data["confidence_score"],
                        data["sources"],
                        data["cross_references"],
                        data["status"],
                        data["error_message"],
                        data["processing_time_ms"],
                        data["tokens_used"],
                        data["created_at"],
                        data["completed_at"],
                    ),
                )

                entity.id = cursor.lastrowid
                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to create query: {e}")
            raise

    def get_by_id(self, entity_id: int) -> CrossDocumentQueryModel | None:
        """Get query by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries WHERE id = ?
                """,
                    (entity_id,),
                )

                row = cursor.fetchone()
                if row:
                    return CrossDocumentQueryModel.from_database_row(
                        dict[str, Any](row)
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get query {entity_id}: {e}")
            raise

    def get_by_ids(self, entity_ids: list[int]) -> list[CrossDocumentQueryModel]:
        """Get multiple queries by IDs."""
        if not entity_ids:
            return []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(entity_ids))
                cursor.execute(
                    f"""
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries WHERE id IN ({placeholders})
                """,  # noqa: S608 - safe SQL construction
                    entity_ids,
                )

                rows = cursor.fetchall()
                return [
                    CrossDocumentQueryModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get queries {entity_ids}: {e}")
            raise

    def update(self, entity: CrossDocumentQueryModel) -> CrossDocumentQueryModel:
        """Update an existing query."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                data = entity.to_database_dict()

                cursor.execute(
                    """
                    UPDATE cross_document_queries
                    SET collection_id = ?, query_text = ?, user_id = ?, response_text = ?,
                        confidence_score = ?, sources = ?, cross_references = ?, status = ?,
                        error_message = ?, processing_time_ms = ?, tokens_used = ?, completed_at = ?
                    WHERE id = ?
                """,
                    (
                        data["collection_id"],
                        data["query_text"],
                        data["user_id"],
                        data["response_text"],
                        data["confidence_score"],
                        data["sources"],
                        data["cross_references"],
                        data["status"],
                        data["error_message"],
                        data["processing_time_ms"],
                        data["tokens_used"],
                        data["completed_at"],
                        entity.id,
                    ),
                )

                conn.commit()
                return entity
        except Exception as e:
            logger.error(f"Failed to update query {entity.id}: {e}")
            raise

    def delete(self, entity_id: int) -> bool:
        """Delete a query by ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM cross_document_queries WHERE id = ?", (entity_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete query {entity_id}: {e}")
            raise

    def find_by_collection_id(
        self, collection_id: int, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by collection ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries
                    WHERE collection_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (collection_id, limit),
                )

                rows = cursor.fetchall()
                return [
                    CrossDocumentQueryModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to find queries for collection {collection_id}: {e}")
            raise

    def find_by_user_id(
        self, user_id: str, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by user ID."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (user_id, limit),
                )

                rows = cursor.fetchall()
                return [
                    CrossDocumentQueryModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to find queries for user {user_id}: {e}")
            raise

    def find_by_status(
        self, status: str, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Find queries by status."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (status, limit),
                )

                rows = cursor.fetchall()
                return [
                    CrossDocumentQueryModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to find queries by status {status}: {e}")
            raise

    def get_recent_queries(
        self, days: int = 7, limit: int = 50
    ) -> list[CrossDocumentQueryModel]:
        """Get recent queries within specified days."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, collection_id, query_text, user_id, response_text, confidence_score,
                           sources, cross_references, status, error_message, processing_time_ms,
                           tokens_used, created_at, completed_at
                    FROM cross_document_queries
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (cutoff_date, limit),
                )

                rows = cursor.fetchall()
                return [
                    CrossDocumentQueryModel.from_database_row(dict[str, Any](row))
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get recent queries: {e}")
            raise

    def get_query_statistics(self) -> dict[str, Any]:
        """Get query performance statistics."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Basic statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_queries,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_queries,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_queries,
                        AVG(CASE WHEN processing_time_ms IS NOT NULL THEN processing_time_ms END) as avg_processing_time,
                        AVG(CASE WHEN confidence_score IS NOT NULL THEN confidence_score END) as avg_confidence
                    FROM cross_document_queries
                """
                )

                stats = dict[str, Any](cursor.fetchone())
                return stats
        except Exception as e:
            logger.error(f"Failed to get query statistics: {e}")
            raise

    def cleanup_old_queries(self, days_old: int = 30) -> int:
        """Remove old query records."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM cross_document_queries
                    WHERE created_at < ?
                """,
                    (cutoff_date,),
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup old queries: {e}")
            raise
