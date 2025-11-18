"""
Migration 008: Add Multi-Document Tables

Creates the multi_document_collections and multi_document_indexes tables
required for multi-document analysis and cross-document querying functionality.
"""

import logging

try:
    from ..base import BaseMigration
except ImportError:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).parent.parent))
    from base import BaseMigration

logger = logging.getLogger(__name__)


class AddMultiDocumentTablesMigration(BaseMigration):
    """
    Creates multi-document analysis tables.

    This migration creates the tables needed for:
    - Multi-document collections (grouping documents)
    - Multi-document indexes (vector indexes for cross-document search)
    """

    @property
    def version(self) -> int:
        return 8

    @property
    def description(self) -> str:
        return "Add multi_document_collections and multi_document_indexes tables"

    @property
    def dependencies(self) -> list[int]:
        return []  # No dependencies - tables are self-contained

    @property
    def rollback_supported(self) -> bool:
        return True

    def up(self) -> None:
        """Apply the multi-document tables migration."""
        logger.info("Creating multi-document analysis tables")

        # Create multi_document_collections table
        collections_sql = """
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
        self.execute_sql(collections_sql)
        logger.info("Created multi_document_collections table")

        # Create multi_document_indexes table
        indexes_sql = """
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
        self.execute_sql(indexes_sql)
        logger.info("Created multi_document_indexes table")

        # Create indexes for performance
        performance_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_multi_doc_collections_name ON multi_document_collections(name)",
            "CREATE INDEX IF NOT EXISTS idx_multi_doc_collections_created ON multi_document_collections(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_multi_doc_indexes_collection ON multi_document_indexes(collection_id)",
            "CREATE INDEX IF NOT EXISTS idx_multi_doc_indexes_hash ON multi_document_indexes(index_hash)",
            "CREATE INDEX IF NOT EXISTS idx_multi_doc_indexes_created ON multi_document_indexes(created_at DESC)",
        ]

        for index_sql in performance_indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        logger.info("Multi-document tables migration completed successfully")

    def down(self) -> None:
        """Rollback the multi-document tables migration."""
        logger.info("Rolling back multi-document tables migration")

        try:
            # Drop tables in reverse order (indexes first due to foreign key)
            self.execute_sql("DROP TABLE IF EXISTS multi_document_indexes")
            logger.info("Dropped multi_document_indexes table")

            self.execute_sql("DROP TABLE IF EXISTS multi_document_collections")
            logger.info("Dropped multi_document_collections table")

            logger.info("Multi-document tables rollback completed")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

    def pre_migrate_checks(self) -> bool:
        """Perform pre-migration validation."""
        if not super().pre_migrate_checks():
            return False

        # Check that documents table exists
        result = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        if not result:
            logger.error(
                "Documents table does not exist - migration 001 must be applied first"
            )
            return False

        # Check if multi_document_collections table already exists
        try:
            result = self.db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='multi_document_collections'"
            )
            if result:
                logger.warning("multi_document_collections table already exists")
                return False  # Skip if already applied

        except Exception as e:
            logger.warning(f"Could not check existing tables: {e}")

        return True

    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        try:
            # Check that both tables exist
            collections_result = self.db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='multi_document_collections'"
            )
            indexes_result = self.db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='multi_document_indexes'"
            )

            if not collections_result:
                logger.error("multi_document_collections table was not created")
                return False

            if not indexes_result:
                logger.error("multi_document_indexes table was not created")
                return False

            # Verify foreign key constraint exists
            indexes_info = self.db.fetch_all(
                "PRAGMA foreign_key_list(multi_document_indexes)"
            )
            fk_found = any(
                fk["table"] == "multi_document_collections" for fk in indexes_info
            )

            if not fk_found:
                logger.warning("Foreign key constraint may not be properly created")

            logger.info("Post-migration validation passed")
            return True

        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
