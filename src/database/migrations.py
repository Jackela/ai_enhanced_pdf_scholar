"""
Database Migration System
Handles database schema creation, versioning, and migrations.
Ensures database schema is up-to-date and supports gradual upgrades.
"""

import logging
from collections.abc import Callable
from typing import Any

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Raised when database migration fails."""

    pass


class DatabaseMigrator:
    """
    {
        "name": "DatabaseMigrator",
        "version": "1.0.0",
        "description": "Database schema migration manager with version control.",
        "dependencies": ["DatabaseConnection"],
        "interface": {
            "inputs": ["database_connection: DatabaseConnection"],
            "outputs": "Database schema management and migration utilities"
        }
    }
    Manages database schema creation and migrations.
    Tracks schema version and applies incremental updates.
    """

    CURRENT_VERSION = 3

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize database migrator.
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
        self.migrations = self._get_migrations()

    def _get_migrations(self) -> dict[int, Callable[[], None]]:
        """
        Get all available migrations.
        Returns:
            Dictionary mapping version numbers to migration functions
        """
        return {
            1: self._migration_001_initial_schema,
            2: self._migration_002_add_content_hash,
            3: self._migration_003_add_citation_tables,
        }

    def get_current_version(self) -> int:
        """
        Get current database schema version.
        Returns:
            Current schema version number
        """
        try:
            result = self.db.fetch_one("PRAGMA user_version")
            return result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not determine database version: {e}")
            return 0

    def set_version(self, version: int) -> None:
        """
        Set database schema version.
        Args:
            version: Version number to set
        """
        try:
            self.db.execute(f"PRAGMA user_version = {version}")
            logger.info(f"Database version set to {version}")
        except Exception as e:
            logger.error(f"Failed to set database version: {e}")
            raise MigrationError(f"Cannot set database version: {e}") from e

    def needs_migration(self) -> bool:
        """
        Check if database needs migration.
        Returns:
            True if migration is needed
        """
        current_version = self.get_current_version()
        return current_version < self.CURRENT_VERSION

    def migrate(self) -> bool:
        """
        Perform database migration to latest version.
        Returns:
            True if migration succeeded
        Raises:
            MigrationError: If migration fails
        """
        current_version = self.get_current_version()
        target_version = self.CURRENT_VERSION
        if current_version >= target_version:
            logger.info(
                f"Database is already at version {current_version}, no migration needed"
            )
            return True
        logger.info(
            f"Migrating database from version {current_version} to {target_version}"
        )
        try:
            with self.db.transaction():
                # Apply each migration in sequence
                for version in range(current_version + 1, target_version + 1):
                    if version not in self.migrations:
                        raise MigrationError(
                            f"No migration available for version {version}"
                        )
                    logger.info(f"Applying migration {version}")
                    migration_func = self.migrations[version]
                    migration_func()
                    self.set_version(version)
                    logger.info(f"Migration {version} completed successfully")
                logger.info("Database migration completed successfully")
                return True
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            raise MigrationError(f"Migration failed: {e}") from e

    def create_tables_if_not_exist(self) -> bool:
        """
        Create database tables if they don't exist.
        This is used for fresh installations.
        Returns:
            True if tables were created successfully
        """
        try:
            current_version = self.get_current_version()
            if current_version == 0:
                logger.info("Creating database schema for fresh installation")
                return self.migrate()
            else:
                logger.info(f"Database already exists at version {current_version}")
                return True
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise MigrationError(f"Table creation failed: {e}") from e

    def _migration_001_initial_schema(self) -> None:
        """
        Migration 001: Create initial database schema.
        Creates:
        - documents table
        - vector_indexes table
        - tags table
        - document_tags table
        - indexes for performance
        """
        logger.info("Creating initial database schema")
        # Create documents table
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
        self.db.execute(documents_sql)
        logger.info("Created documents table")
        # Create vector_indexes table
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
        self.db.execute(vector_indexes_sql)
        logger.info("Created vector_indexes table")
        # Create tags table
        tags_sql = """
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#0078d4'
        )
        """
        self.db.execute(tags_sql)
        logger.info("Created tags table")
        # Create document_tags junction table
        document_tags_sql = """
        CREATE TABLE document_tags (
            document_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (document_id, tag_id),
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
        """
        self.db.execute(document_tags_sql)
        logger.info("Created document_tags table")
        # Create indexes for performance
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
            self.db.execute(index_sql)
        logger.info("Created database indexes")
        # Insert default tags
        default_tags = [
            ("academic", "#0078d4"),
            ("research", "#107c10"),
            ("reference", "#ff8c00"),
            ("important", "#d13438"),
        ]
        tag_insert_sql = "INSERT INTO tags (name, color) VALUES (?, ?)"
        for tag_name, tag_color in default_tags:
            try:
                self.db.execute(tag_insert_sql, (tag_name, tag_color))
            except Exception as e:
                # Ignore duplicate tag errors
                logger.debug(f"Could not insert default tag {tag_name}: {e}")
        logger.info("Inserted default tags")
        logger.info("Initial schema migration completed")

    def _migration_002_add_content_hash(self) -> None:
        """
        Migration 002: Add content_hash to documents table.
        """
        logger.info("Applying migration 002: Add content_hash")
        # Add content_hash column
        add_column_sql = "ALTER TABLE documents ADD COLUMN content_hash TEXT"
        self.db.execute(add_column_sql)
        logger.info("Added content_hash column to documents table")
        # Create index for content_hash
        create_index_sql = (
            "CREATE INDEX idx_documents_content_hash ON documents(content_hash)"
        )
        self.db.execute(create_index_sql)
        logger.info("Created index on content_hash")
        logger.info("Migration 002 completed successfully")

    def _migration_003_add_citation_tables(self) -> None:
        """
        Migration 003: Add citation and citation_relations tables.
        Creates tables for advanced citation extraction and analysis features.
        """
        logger.info("Applying migration 003: Add citation tables")

        # Create citations table
        citations_sql = """
        CREATE TABLE citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            authors TEXT,
            title TEXT,
            publication_year INTEGER,
            journal_or_venue TEXT,
            doi TEXT,
            page_range TEXT,
            citation_type TEXT,
            confidence_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
        """
        self.db.execute(citations_sql)
        logger.info("Created citations table")

        # Create citation_relations table
        citation_relations_sql = """
        CREATE TABLE citation_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_document_id INTEGER NOT NULL,
            source_citation_id INTEGER NOT NULL,
            target_document_id INTEGER,
            target_citation_id INTEGER,
            relation_type TEXT NOT NULL DEFAULT 'cites',
            confidence_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_document_id)
                REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (source_citation_id)
                REFERENCES citations (id) ON DELETE CASCADE,
            FOREIGN KEY (target_document_id)
                REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (target_citation_id)
                REFERENCES citations (id) ON DELETE CASCADE
        )
        """
        self.db.execute(citation_relations_sql)
        logger.info("Created citation_relations table")

        # Create indexes for performance
        citation_indexes = [
            "CREATE INDEX idx_citations_document ON citations(document_id)",
            "CREATE INDEX idx_citations_authors ON citations(authors)",
            "CREATE INDEX idx_citations_title ON citations(title)",
            "CREATE INDEX idx_citations_year ON citations(publication_year)",
            "CREATE INDEX idx_citations_doi ON citations(doi)",
            "CREATE INDEX idx_citations_type ON citations(citation_type)",
            ("CREATE INDEX idx_citations_confidence "
             "ON citations(confidence_score)"),
            ("CREATE INDEX idx_citation_relations_source "
             "ON citation_relations(source_document_id)"),
            ("CREATE INDEX idx_citation_relations_target "
             "ON citation_relations(target_document_id)"),
            ("CREATE INDEX idx_citation_relations_type "
             "ON citation_relations(relation_type)"),
        ]

        for index_sql in citation_indexes:
            self.db.execute(index_sql)
        logger.info("Created citation table indexes")

        logger.info("Migration 003 completed successfully")

    def get_schema_info(self) -> dict[str, Any]:
        """
        Get information about current database schema.
        Returns:
            Dictionary with schema information
        """
        try:
            info: dict[str, Any] = {
                "current_version": self.get_current_version(),
                "target_version": self.CURRENT_VERSION,
                "needs_migration": self.needs_migration(),
                "tables": [],
            }
            # Get table information
            tables = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            for table in tables:
                table_name = table["name"]
                # Get table info
                table_info = self.db.fetch_all(f"PRAGMA table_info({table_name})")
                columns = [
                    {
                        "name": col["name"],
                        "type": col["type"],
                        "notnull": bool(col["notnull"]),
                    }
                    for col in table_info
                ]
                # Get row count
                count_result = self.db.fetch_one(
                    f"SELECT COUNT(*) as count FROM {table_name}"
                )
                row_count = count_result["count"] if count_result else 0
                info["tables"].append(
                    {"name": table_name, "columns": columns, "row_count": row_count}
                )
            return info
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return {"error": str(e)}

    def validate_schema(self) -> bool:
        """
        Validate that database schema is correct and complete.
        Returns:
            True if schema is valid
        """
        try:
            # Check version
            current_version = self.get_current_version()
            if current_version != self.CURRENT_VERSION:
                logger.warning(
                    f"Schema mismatch: {current_version} != "
                    f"{self.CURRENT_VERSION}"
                )
                return False
            # Check required tables exist
            required_tables = [
                "documents", "vector_indexes", "tags",
                "document_tags", "citations", "citation_relations"
            ]
            existing_tables = [
                row["name"]
                for row in self.db.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ]
            for table in required_tables:
                if table not in existing_tables:
                    logger.error(f"Required table missing: {table}")
                    return False
            # Check foreign key constraints are enabled
            fk_result = self.db.fetch_one("PRAGMA foreign_keys")
            if not fk_result or fk_result[0] != 1:
                logger.warning("Foreign key constraints are not enabled")
                return False
            logger.info("Database schema validation passed")
            return True
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False
