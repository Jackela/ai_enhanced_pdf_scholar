"""
Migration 002: Add Content Hash Column

Adds content_hash column to documents table for improved duplicate detection
and content-based document identification.
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


class AddContentHashMigration(BaseMigration):
    """
    Adds content_hash column to documents table.

    This migration enhances duplicate detection by adding a content-based
    hash that complements the existing file-based hash.
    """

    @property
    def version(self) -> int:
        return 2

    @property
    def description(self) -> str:
        return "Add content_hash column to documents table for improved duplicate detection"

    @property
    def dependencies(self) -> list[int]:
        return [1]  # Requires initial schema

    @property
    def rollback_supported(self) -> bool:
        return True

    def up(self) -> None:
        """Apply the content hash migration."""
        logger.info("Adding content_hash column to documents table")

        # Add content_hash column
        add_column_sql = "ALTER TABLE documents ADD COLUMN content_hash TEXT"
        self.execute_sql(add_column_sql)
        logger.info("Added content_hash column to documents table")

        # Create index for content_hash
        create_index_sql = (
            "CREATE INDEX idx_documents_content_hash ON documents(content_hash)"
        )
        self.execute_sql(create_index_sql)
        logger.info("Created index on content_hash column")

        logger.info("Content hash migration completed successfully")

    def down(self) -> None:
        """Rollback the content hash migration."""
        logger.info("Rolling back content hash migration")

        try:
            # Drop the index first
            self.execute_sql("DROP INDEX IF EXISTS idx_documents_content_hash")
            logger.info("Dropped content_hash index")

            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            # This is a more complex rollback, but we'll implement it for completeness
            self._rollback_content_hash_column()

            logger.info("Content hash rollback completed")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

    def _rollback_content_hash_column(self) -> None:
        """
        Remove content_hash column by recreating table without it.

        SQLite doesn't support DROP COLUMN, so we use the standard pattern:
        1. Create new table without the column
        2. Copy data from old table to new table
        3. Drop old table and rename new table
        """
        logger.info("Removing content_hash column via table recreation")

        # Create new table without content_hash column (original schema from migration 001)
        create_new_table_sql = """
        CREATE TABLE documents_new (
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
        self.execute_sql(create_new_table_sql)

        # Copy data from old table to new table (excluding content_hash)
        copy_data_sql = """
        INSERT INTO documents_new 
        (id, title, file_path, file_hash, file_size, page_count, 
         created_at, updated_at, last_accessed, metadata)
        SELECT id, title, file_path, file_hash, file_size, page_count,
               created_at, updated_at, last_accessed, metadata
        FROM documents
        """
        self.execute_sql(copy_data_sql)

        # Drop old table
        self.execute_sql("DROP TABLE documents")

        # Rename new table
        self.execute_sql("ALTER TABLE documents_new RENAME TO documents")

        # Recreate the original indexes (from migration 001)
        original_indexes = [
            "CREATE INDEX idx_documents_hash ON documents(file_hash)",
            "CREATE INDEX idx_documents_title ON documents(title)",
            "CREATE INDEX idx_documents_created ON documents(created_at DESC)",
            "CREATE INDEX idx_documents_accessed ON documents(last_accessed DESC)",
        ]

        for index_sql in original_indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not recreate index during rollback: {e}")

        logger.info("Successfully removed content_hash column")

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

        # Check if content_hash column already exists
        try:
            columns = self.db.fetch_all("PRAGMA table_info(documents)")
            column_names = [col["name"] for col in columns]

            if "content_hash" in column_names:
                logger.warning("content_hash column already exists")
                return False  # Skip if already applied

        except Exception as e:
            logger.warning(f"Could not check existing columns: {e}")

        return True

    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        try:
            # Check that content_hash column exists
            columns = self.db.fetch_all("PRAGMA table_info(documents)")
            column_names = [col["name"] for col in columns]

            if "content_hash" not in column_names:
                logger.error("content_hash column was not added")
                return False

            # Check that index was created
            indexes = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_documents_content_hash'"
            )

            if not indexes:
                logger.error("content_hash index was not created")
                return False

            logger.info("Post-migration validation passed")
            return True

        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
