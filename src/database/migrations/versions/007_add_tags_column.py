"""
Migration 007: Add Tags Column

Adds a tags column to the documents table for storing comma-separated tag strings.
This provides a simple alternative to the normalized tags system.
"""

import logging
from typing import Any

try:
    from ..base import BaseMigration
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from base import BaseMigration

logger = logging.getLogger(__name__)


class AddTagsColumnMigration(BaseMigration):
    """
    Adds tags column to documents table.
    
    This migration adds a simple tags column to store comma-separated
    tag strings directly in the documents table, complementing the
    existing normalized tag system.
    """
    
    @property
    def version(self) -> int:
        return 7
        
    @property
    def description(self) -> str:
        return "Add tags column to documents table for comma-separated tag storage"
        
    @property
    def dependencies(self) -> list[int]:
        return [1]  # Requires documents table
        
    @property
    def rollback_supported(self) -> bool:
        return True
        
    def up(self) -> None:
        """Apply the tags column migration."""
        logger.info("Adding tags column to documents table")
        
        # Add tags column to documents table
        alter_sql = "ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT ''"
        self.execute_sql(alter_sql)
        logger.info("Added tags column to documents table")
        
        logger.info("Tags column migration completed successfully")
        
    def down(self) -> None:
        """Rollback the tags column migration."""
        logger.info("Rolling back tags column migration")
        
        try:
            # SQLite doesn't support DROP COLUMN directly, so we recreate the table
            self._rollback_tags_column()
            logger.info("Tags column rollback completed")
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
            
    def _rollback_tags_column(self) -> None:
        """
        Remove tags column by recreating table without it.
        """
        logger.info("Removing tags column via table recreation")
        
        # Create new table without tags column
        create_new_table_sql = """
        CREATE TABLE documents_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT,
            file_hash TEXT UNIQUE NOT NULL,
            file_size INTEGER NOT NULL,
            content_hash TEXT,
            page_count INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_accessed DATETIME,
            metadata TEXT DEFAULT '{}'
        )
        """
        self.execute_sql(create_new_table_sql)
        
        # Copy data from old table to new table (excluding tags)
        copy_data_sql = """
        INSERT INTO documents_new 
        (id, title, file_path, file_hash, file_size, content_hash, page_count, 
         created_at, updated_at, last_accessed, metadata)
        SELECT id, title, file_path, file_hash, file_size, content_hash, page_count,
               created_at, updated_at, last_accessed, metadata
        FROM documents
        """
        self.execute_sql(copy_data_sql)
        
        # Drop old table
        self.execute_sql("DROP TABLE documents")
        
        # Rename new table
        self.execute_sql("ALTER TABLE documents_new RENAME TO documents")
        
        # Recreate essential indexes
        essential_indexes = [
            "CREATE INDEX idx_documents_hash ON documents(file_hash)",
            "CREATE INDEX idx_documents_title ON documents(title)",
            "CREATE INDEX idx_documents_created ON documents(created_at DESC)",
        ]
        
        for index_sql in essential_indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not recreate index during rollback: {e}")
                
        logger.info("Successfully removed tags column")
        
    def pre_migrate_checks(self) -> bool:
        """Perform pre-migration validation."""
        if not super().pre_migrate_checks():
            return False
            
        # Check that documents table exists
        result = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        if not result:
            logger.error("Documents table does not exist - migration 001 must be applied first")
            return False
            
        # Check if tags column already exists
        try:
            columns = self.db.fetch_all("PRAGMA table_info(documents)")
            column_names = [col["name"] for col in columns]
            
            if "tags" in column_names:
                logger.warning("tags column already exists")
                return False  # Skip if already applied
                
        except Exception as e:
            logger.warning(f"Could not check existing columns: {e}")
            
        return True
        
    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        try:
            # Check that tags column exists
            columns = self.db.fetch_all("PRAGMA table_info(documents)")
            column_names = [col["name"] for col in columns]
            
            if "tags" not in column_names:
                logger.error("tags column was not added")
                return False
                
            logger.info("Post-migration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
