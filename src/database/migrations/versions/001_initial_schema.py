"""
Migration 001: Initial Database Schema

Creates the foundational database schema including:
- documents table for PDF file metadata
- vector_indexes table for RAG indexing
- tags system for document organization
- Performance indexes for optimal queries
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


class InitialSchemaMigration(BaseMigration):
    """
    Creates the initial database schema for the AI Enhanced PDF Scholar system.

    This migration establishes the core tables and indexes needed for:
    - Document storage and metadata management
    - Vector indexing for RAG functionality
    - Tag-based document organization
    - Performance optimization
    """

    @property
    def version(self) -> int:
        return 1

    @property
    def description(self) -> str:
        return "Create initial database schema with documents, vector_indexes, and tags tables"

    @property
    def rollback_supported(self) -> bool:
        return True

    def up(self) -> None:
        """Apply the initial schema migration."""
        logger.info("Creating initial database schema")

        # Create documents table
        self._create_documents_table()

        # Create vector_indexes table
        self._create_vector_indexes_table()

        # Create tags system
        self._create_tags_tables()

        # Create performance indexes
        self._create_performance_indexes()

        # Insert default tags
        self._insert_default_tags()

        logger.info("Initial schema migration completed successfully")

    def down(self) -> None:
        """Rollback the initial schema migration."""
        logger.info("Rolling back initial schema migration")

        # Drop tables in reverse order (respecting foreign keys)
        tables_to_drop = ["document_tags", "tags", "vector_indexes", "documents"]

        for table in tables_to_drop:
            try:
                self.execute_sql(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")

        logger.info("Initial schema rollback completed")

    def _create_documents_table(self) -> None:
        """Create the documents table."""
        documents_sql = """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT,
            file_hash TEXT UNIQUE NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_accessed DATETIME,
            metadata TEXT DEFAULT '{}'
        )
        """
        self.execute_sql(documents_sql)
        logger.info("Created documents table")

    def _create_vector_indexes_table(self) -> None:
        """Create the vector_indexes table."""
        vector_indexes_sql = """
        CREATE TABLE vector_indexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            index_path TEXT NOT NULL,
            index_hash TEXT UNIQUE NOT NULL,
            chunk_count INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
        """
        self.execute_sql(vector_indexes_sql)
        logger.info("Created vector_indexes table")

    def _create_tags_tables(self) -> None:
        """Create the tags and document_tags tables."""
        # Tags table
        tags_sql = """
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#0078d4'
        )
        """
        self.execute_sql(tags_sql)
        logger.info("Created tags table")

        # Document-tags junction table
        document_tags_sql = """
        CREATE TABLE document_tags (
            document_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (document_id, tag_id),
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
        """
        self.execute_sql(document_tags_sql)
        logger.info("Created document_tags table")

    def _create_performance_indexes(self) -> None:
        """Create indexes for optimal query performance."""
        indexes = [
            "CREATE INDEX idx_documents_hash ON documents(file_hash)",
            "CREATE INDEX idx_documents_title ON documents(title)",
            "CREATE INDEX idx_documents_created ON documents(created_at DESC)",
            "CREATE INDEX idx_documents_accessed ON documents(last_accessed DESC)",
            "CREATE INDEX idx_vector_indexes_document ON vector_indexes(document_id)",
            "CREATE INDEX idx_vector_indexes_hash ON vector_indexes(index_hash)",
            "CREATE INDEX idx_tags_name ON tags(name)",
        ]

        for index_sql in indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        logger.info("Created database indexes")

    def _insert_default_tags(self) -> None:
        """Insert default tags for document organization."""
        default_tags = [
            ("academic", "#0078d4"),
            ("research", "#107c10"),
            ("reference", "#ff8c00"),
            ("important", "#d13438"),
        ]

        tag_insert_sql = "INSERT INTO tags (name, color) VALUES (?, ?)"

        for tag_name, tag_color in default_tags:
            try:
                self.execute_sql(tag_insert_sql, (tag_name, tag_color))
            except Exception as e:
                # Ignore duplicate tag errors
                logger.debug(f"Could not insert default tag {tag_name}: {e}")

        logger.info("Inserted default tags")

    def pre_migrate_checks(self) -> bool:
        """Perform pre-migration validation."""
        if not super().pre_migrate_checks():
            return False

        # Check if any tables already exist
        existing_tables = []
        try:
            results = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('documents', 'vector_indexes', 'tags')"
            )
            existing_tables = [row["name"] for row in results]
        except Exception as e:
            logger.warning(f"Could not check existing tables: {e}")

        if existing_tables:
            logger.warning(f"Some tables already exist: {existing_tables}")
            # Could choose to skip or fail here depending on requirements

        return True

    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        required_tables = ["documents", "vector_indexes", "tags", "document_tags"]

        try:
            for table in required_tables:
                result = self.db.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                )
                if not result:
                    logger.error(f"Required table {table} was not created")
                    return False

            # Check that default tags were inserted
            tag_count = self.db.fetch_one("SELECT COUNT(*) as count FROM tags")
            if not tag_count or tag_count["count"] == 0:
                logger.warning("No default tags were inserted")

            logger.info("Post-migration validation passed")
            return True

        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
