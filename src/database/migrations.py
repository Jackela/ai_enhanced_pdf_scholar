"""
Database Migration System - Legacy Module

DEPRECATED: This monolithic migration file has been replaced by the modular
migration system in the `migrations/` package. This file now serves as a
backward compatibility layer.

For new migrations, use the modular system:
- Create individual migration files in `migrations/versions/`
- Use ModularDatabaseMigrator for new code
- See migrations/README.md for complete documentation
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from .connection import DatabaseConnection

# Import modular system for backward compatibility
try:
    from .modular_migrator import ModularDatabaseMigrator

    # Backward compatibility alias - this ensures existing code continues to work
    DatabaseMigrator = ModularDatabaseMigrator

    logger = logging.getLogger(__name__)
    logger.info("Using modular database migrator for backward compatibility")

except ImportError:
    # Fallback to legacy implementation if modular system is not available
    logger = logging.getLogger(__name__)
    logger.warning("Modular migrator not available, using legacy implementation")


class MigrationError(Exception):
    """Raised when database migration fails."""

    pass


# If modular migrator is not available, define a fallback class
if "DatabaseMigrator" not in globals():

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

    CURRENT_VERSION = 7

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
            4: self._migration_004_performance_optimization,
            5: self._migration_005_advanced_performance_analysis,
            6: self._migration_006_add_authentication_tables,
            7: self._migration_007_add_tags_column,
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
            version: Version number to set[str]
        """
        try:
            self.db.execute(f"PRAGMA user_version = {version}")
            logger.info(f"Database version set[str] to {version}")
        except Exception as e:
            logger.error(f"Failed to set[str] database version: {e}")
            raise MigrationError(f"Cannot set[str] database version: {e}") from e

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
            ("CREATE INDEX idx_citations_confidence ON citations(confidence_score)"),
            (
                "CREATE INDEX idx_citation_relations_source "
                "ON citation_relations(source_document_id)"
            ),
            (
                "CREATE INDEX idx_citation_relations_target "
                "ON citation_relations(target_document_id)"
            ),
            (
                "CREATE INDEX idx_citation_relations_type "
                "ON citation_relations(relation_type)"
            ),
        ]

        for index_sql in citation_indexes:
            self.db.execute(index_sql)
        logger.info("Created citation table indexes")

        logger.info("Migration 003 completed successfully")

    def _migration_004_performance_optimization(self) -> None:
        """
        Migration 004: Performance optimization with strategic indexes.
        Adds comprehensive indexing strategy for high-performance queries.
        """
        logger.info("Applying migration 004: Performance optimization with indexes")

        # Performance indexes for documents table
        document_performance_indexes = [
            # High-priority indexes for duplicate detection and lookups
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_file_hash_unique ON documents(file_hash)",
            "CREATE INDEX IF NOT EXISTS idx_documents_content_hash_perf ON documents(content_hash) WHERE content_hash IS NOT NULL",
            # Temporal indexes for sorting and date range queries
            "CREATE INDEX IF NOT EXISTS idx_documents_created_desc_perf ON documents(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_documents_updated_desc_perf ON documents(updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_documents_accessed_desc_perf ON documents(last_accessed DESC) WHERE last_accessed IS NOT NULL",
            # Text search optimization
            "CREATE INDEX IF NOT EXISTS idx_documents_title_search ON documents(title COLLATE NOCASE)",
            # File size for analytics and filtering
            "CREATE INDEX IF NOT EXISTS idx_documents_file_size ON documents(file_size)",
            # Page count for document analysis
            "CREATE INDEX IF NOT EXISTS idx_documents_page_count ON documents(page_count) WHERE page_count IS NOT NULL",
        ]

        # Composite indexes for common query patterns
        document_composite_indexes = [
            # Most common query: recent documents by creation date with title
            "CREATE INDEX IF NOT EXISTS idx_documents_created_title_comp ON documents(created_at DESC, title)",
            # Usage analytics: access patterns with file size
            "CREATE INDEX IF NOT EXISTS idx_documents_access_size_comp ON documents(last_accessed DESC, file_size) WHERE last_accessed IS NOT NULL",
            # Duplicate detection: hash with creation date
            "CREATE INDEX IF NOT EXISTS idx_documents_hash_created_comp ON documents(file_hash, created_at DESC)",
            # Content analysis: content hash with page count
            "CREATE INDEX IF NOT EXISTS idx_documents_content_pages_comp ON documents(content_hash, page_count) WHERE content_hash IS NOT NULL AND page_count IS NOT NULL",
        ]

        # Performance indexes for vector_indexes table
        vector_performance_indexes = [
            # Foreign key optimization (already exists, ensure it's optimized)
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_document_perf ON vector_indexes(document_id)",
            # Hash-based lookups for index management
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_indexes_hash_unique ON vector_indexes(index_hash)",
            # Index creation time for maintenance
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_created_desc ON vector_indexes(created_at DESC)",
            # Index analysis: document with chunk count
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_doc_chunks ON vector_indexes(document_id, chunk_count) WHERE chunk_count IS NOT NULL",
        ]

        # Performance indexes for citations table
        citation_performance_indexes = [
            # Foreign key optimization
            "CREATE INDEX IF NOT EXISTS idx_citations_document_perf ON citations(document_id)",
            # Author search optimization
            "CREATE INDEX IF NOT EXISTS idx_citations_authors_search ON citations(authors COLLATE NOCASE) WHERE authors IS NOT NULL",
            # Title search optimization
            "CREATE INDEX IF NOT EXISTS idx_citations_title_search ON citations(title COLLATE NOCASE) WHERE title IS NOT NULL",
            # Year-based filtering and sorting
            "CREATE INDEX IF NOT EXISTS idx_citations_year_desc ON citations(publication_year DESC) WHERE publication_year IS NOT NULL",
            # DOI-based lookups for academic integrity
            "CREATE INDEX IF NOT EXISTS idx_citations_doi_lookup ON citations(doi) WHERE doi IS NOT NULL",
            # Citation type filtering
            "CREATE INDEX IF NOT EXISTS idx_citations_type_filter ON citations(citation_type) WHERE citation_type IS NOT NULL",
            # Confidence-based quality filtering
            "CREATE INDEX IF NOT EXISTS idx_citations_confidence_desc ON citations(confidence_score DESC) WHERE confidence_score IS NOT NULL",
            # Temporal analysis
            "CREATE INDEX IF NOT EXISTS idx_citations_created_desc ON citations(created_at DESC)",
        ]

        # Composite indexes for citations
        citation_composite_indexes = [
            # Document citations by confidence
            "CREATE INDEX IF NOT EXISTS idx_citations_doc_confidence ON citations(document_id, confidence_score DESC) WHERE confidence_score IS NOT NULL",
            # Academic search: author and year
            "CREATE INDEX IF NOT EXISTS idx_citations_author_year ON citations(authors, publication_year DESC) WHERE authors IS NOT NULL AND publication_year IS NOT NULL",
            # Citation analysis: type and confidence
            "CREATE INDEX IF NOT EXISTS idx_citations_type_confidence ON citations(citation_type, confidence_score DESC) WHERE citation_type IS NOT NULL AND confidence_score IS NOT NULL",
        ]

        # Performance indexes for citation_relations table
        relation_performance_indexes = [
            # Source document optimization
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_perf ON citation_relations(source_document_id)",
            # Target document optimization
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_target_perf ON citation_relations(target_document_id) WHERE target_document_id IS NOT NULL",
            # Source citation lookup
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_citation ON citation_relations(source_citation_id)",
            # Target citation lookup
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_target_citation ON citation_relations(target_citation_id) WHERE target_citation_id IS NOT NULL",
            # Relation type filtering
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_type_perf ON citation_relations(relation_type)",
            # Confidence filtering
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_confidence ON citation_relations(confidence_score DESC) WHERE confidence_score IS NOT NULL",
        ]

        # Composite indexes for citation relations
        relation_composite_indexes = [
            # Citation network analysis
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_target ON citation_relations(source_document_id, target_document_id) WHERE target_document_id IS NOT NULL",
            # Relation analysis with confidence
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_type_confidence ON citation_relations(relation_type, confidence_score DESC) WHERE confidence_score IS NOT NULL",
        ]

        # Tag performance indexes
        tag_performance_indexes = [
            # Tag name lookups (already exists, ensure case-insensitive)
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name_unique ON tags(name COLLATE NOCASE)",
            # Document-tag relationships optimization
            "CREATE INDEX IF NOT EXISTS idx_document_tags_document_perf ON document_tags(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_tags_tag_perf ON document_tags(tag_id)",
        ]

        # Apply all indexes
        all_indexes = (
            document_performance_indexes
            + document_composite_indexes
            + vector_performance_indexes
            + citation_performance_indexes
            + citation_composite_indexes
            + relation_performance_indexes
            + relation_composite_indexes
            + tag_performance_indexes
        )

        logger.info(f"Creating {len(all_indexes)} performance indexes...")

        for i, index_sql in enumerate(all_indexes, 1):
            try:
                self.db.execute(index_sql)
                logger.debug(
                    f"Created index {i}/{len(all_indexes)}: {index_sql[:50]}..."
                )
            except Exception as e:
                logger.warning(f"Index creation warning for index {i}: {e}")
                # Continue with other indexes even if one fails

        logger.info("Performance indexes created successfully")

        # Update database statistics for query optimizer
        try:
            self.db.execute("ANALYZE")
            logger.info("Database statistics updated")
        except Exception as e:
            logger.warning(f"Failed to update database statistics: {e}")

        logger.info("Migration 004 completed successfully")

    def _migration_005_advanced_performance_analysis(self) -> None:
        """
        Migration 005: Advanced performance analysis and optimization.
        Adds specialized indexes, query performance monitoring, and database analytics.
        """
        logger.info(
            "Applying migration 005: Advanced performance analysis and monitoring"
        )

        # Advanced covering indexes for complex queries
        covering_indexes = [
            # Document listing with metadata - covers common SELECT patterns
            "CREATE INDEX IF NOT EXISTS idx_documents_listing_cover ON documents(created_at DESC, title, file_size, page_count, last_accessed)",
            # Document search with size filter - covers advanced search patterns
            "CREATE INDEX IF NOT EXISTS idx_documents_search_cover ON documents(title COLLATE NOCASE, file_size, created_at DESC, id)",
            # Recent documents with usage analytics
            "CREATE INDEX IF NOT EXISTS idx_documents_recent_cover ON documents(last_accessed DESC, created_at DESC, title, file_size) WHERE last_accessed IS NOT NULL",
            # Citation analysis covering index
            "CREATE INDEX IF NOT EXISTS idx_citations_analysis_cover ON citations(document_id, confidence_score DESC, citation_type, publication_year, authors)",
            # Vector index management covering
            "CREATE INDEX IF NOT EXISTS idx_vector_management_cover ON vector_indexes(document_id, created_at DESC, chunk_count, index_path)",
        ]

        # Specialized partial indexes for filtered queries
        partial_indexes = [
            # High-confidence citations only
            "CREATE INDEX IF NOT EXISTS idx_citations_high_confidence ON citations(document_id, publication_year DESC, authors) WHERE confidence_score >= 0.8",
            # Large documents (performance-sensitive operations)
            "CREATE INDEX IF NOT EXISTS idx_documents_large_files ON documents(file_size DESC, page_count, created_at DESC) WHERE file_size > 10485760",  # > 10MB
            # Recent documents only (hot data)
            "CREATE INDEX IF NOT EXISTS idx_documents_recent_hot ON documents(last_accessed DESC, title)",
            # Documents with content hash (duplicate detection)
            "CREATE INDEX IF NOT EXISTS idx_documents_content_dedup ON documents(content_hash, file_hash, created_at DESC) WHERE content_hash IS NOT NULL AND content_hash != ''",
            # Multi-page documents (academic focus)
            "CREATE INDEX IF NOT EXISTS idx_documents_multi_page ON documents(page_count DESC, created_at DESC, title) WHERE page_count > 1",
        ]

        # Expression-based indexes for computed queries
        expression_indexes = [
            # Document age calculation (frequently used for cleanup) - FIXED: Removed non-deterministic julianday('now')
            "CREATE INDEX IF NOT EXISTS idx_documents_created_date ON documents(created_at DESC, document_id)",
            # File size categories for analytics
            "CREATE INDEX IF NOT EXISTS idx_documents_size_category ON documents(CASE WHEN file_size < 1048576 THEN 'small' WHEN file_size < 10485760 THEN 'medium' ELSE 'large' END, file_size)",
            # Citation density (citations per document)
            "CREATE INDEX IF NOT EXISTS idx_citation_density_calc ON citations(document_id, created_at DESC)",
        ]

        # Full-text search optimization indexes
        fts_support_indexes = [
            # Title trigrams for fuzzy search support
            "CREATE INDEX IF NOT EXISTS idx_documents_title_trigram ON documents(SUBSTR(title, 1, 3), title) WHERE LENGTH(title) >= 3",
            # Author name optimization for citations
            "CREATE INDEX IF NOT EXISTS idx_citations_author_search ON citations(SUBSTR(authors, 1, 10), authors) WHERE authors IS NOT NULL AND LENGTH(authors) >= 3",
        ]

        # Apply all advanced indexes
        all_advanced_indexes = (
            covering_indexes
            + partial_indexes
            + expression_indexes
            + fts_support_indexes
        )

        logger.info(
            f"Creating {len(all_advanced_indexes)} advanced performance indexes..."
        )

        created_count = 0
        for i, index_sql in enumerate(all_advanced_indexes, 1):
            try:
                self.db.execute(index_sql)
                created_count += 1
                logger.debug(
                    f"Created advanced index {i}/{len(all_advanced_indexes)}: {index_sql[:60]}..."
                )
            except Exception as e:
                logger.warning(f"Advanced index creation warning for index {i}: {e}")
                # Continue with other indexes even if one fails

        logger.info(
            f"Successfully created {created_count}/{len(all_advanced_indexes)} advanced indexes"
        )

        # Create query performance monitoring tables
        self._create_performance_monitoring_tables()

        # Initialize database performance baselines
        self._initialize_performance_baselines()

        # Update database statistics and optimize settings
        try:
            # Comprehensive statistics update
            self.db.execute("ANALYZE")

            # Optimize SQLite settings for performance
            performance_settings = [
                "PRAGMA optimize",  # Let SQLite optimize the database
                "PRAGMA wal_autocheckpoint=1000",  # Checkpoint every 1000 pages
                "PRAGMA journal_size_limit=67108864",  # 64MB journal size limit
            ]

            for setting in performance_settings:
                try:
                    self.db.execute(setting)
                    logger.debug(f"Applied performance setting: {setting}")
                except Exception as e:
                    logger.warning(f"Could not apply setting {setting}: {e}")

            logger.info("Database performance settings optimized")

        except Exception as e:
            logger.warning(f"Failed to update database performance settings: {e}")

        logger.info("Migration 005 completed successfully")

    def _create_performance_monitoring_tables(self) -> None:
        """
        Create tables for performance monitoring and query analysis.
        """
        logger.debug("Creating performance monitoring tables")

        # Query performance log table
        query_log_sql = """
        CREATE TABLE IF NOT EXISTS query_performance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_hash TEXT NOT NULL,
            query_pattern TEXT NOT NULL,
            execution_time_ms REAL NOT NULL,
            rows_examined INTEGER,
            rows_returned INTEGER,
            index_used TEXT,
            optimization_suggestions TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db.execute(query_log_sql)

        # Index usage statistics table
        index_stats_sql = """
        CREATE TABLE IF NOT EXISTS index_usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            last_used DATETIME,
            selectivity_estimate REAL,
            effectiveness_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db.execute(index_stats_sql)

        # Performance baselines table
        baselines_sql = """
        CREATE TABLE IF NOT EXISTS performance_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            baseline_value REAL NOT NULL,
            measurement_unit TEXT,
            measured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            context_info TEXT
        )
        """
        self.db.execute(baselines_sql)

        # Create indexes for monitoring tables
        monitoring_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_query_log_pattern ON query_performance_log(query_pattern, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_query_log_performance ON query_performance_log(execution_time_ms DESC, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_index_stats_usage ON index_usage_stats(usage_count DESC, effectiveness_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_baselines_metric ON performance_baselines(metric_name, measured_at DESC)",
        ]

        for index_sql in monitoring_indexes:
            try:
                self.db.execute(index_sql)
            except Exception as e:
                logger.warning(f"Could not create monitoring index: {e}")

        logger.debug("Performance monitoring tables created successfully")

    def _initialize_performance_baselines(self) -> None:
        """
        Initialize performance baselines for future comparison.
        """
        logger.debug("Initializing performance baselines")

        baselines = []

        try:
            # Table row counts
            tables = [
                "documents",
                "vector_indexes",
                "citations",
                "citation_relations",
                "tags",
                "document_tags",
            ]
            for table in tables:
                try:
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as count FROM {table}"
                    )
                    count = count_result["count"] if count_result else 0
                    baselines.append(
                        (
                            f"table_row_count_{table}",
                            count,
                            "rows",
                            "Table size baseline",
                        )
                    )
                except Exception as e:
                    logger.warning(f"Could not get row count for table {table}: {e}")

            # Index counts and sizes
            try:
                index_result = self.db.fetch_all(
                    "SELECT COUNT(*) as count FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
                )
                if index_result:
                    index_count = index_result[0]["count"]
                    baselines.append(
                        (
                            "total_indexes",
                            index_count,
                            "count",
                            "Total user-defined indexes",
                        )
                    )
            except Exception as e:
                logger.warning(f"Could not get index count: {e}")

            # Database file size
            try:
                size_result = self.db.fetch_one(
                    "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                )
                if size_result and size_result["size"]:
                    db_size = size_result["size"]
                    baselines.append(
                        ("database_size_bytes", db_size, "bytes", "Database file size")
                    )
            except Exception as e:
                logger.warning(f"Could not get database size: {e}")

            # Sample query performance baselines
            sample_queries = [
                ("SELECT COUNT(*) FROM documents", "simple_count_documents"),
                (
                    "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10",
                    "recent_documents_query",
                ),
                (
                    "SELECT d.*, COUNT(c.id) FROM documents d LEFT JOIN citations c ON d.id = c.document_id GROUP BY d.id LIMIT 10",
                    "document_citation_join",
                ),
            ]

            for query, query_name in sample_queries:
                try:
                    start_time = time.time()
                    self.db.fetch_all(query)
                    execution_time = (
                        time.time() - start_time
                    ) * 1000  # Convert to milliseconds
                    baselines.append(
                        (
                            f"query_time_{query_name}",
                            execution_time,
                            "milliseconds",
                            f"Baseline for: {query[:50]}...",
                        )
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not measure baseline for query {query_name}: {e}"
                    )

            # Insert all baselines
            if baselines:
                baseline_insert_sql = """
                INSERT INTO performance_baselines (metric_name, baseline_value, measurement_unit, context_info)
                VALUES (?, ?, ?, ?)
                """
                for baseline in baselines:
                    try:
                        self.db.execute(baseline_insert_sql, baseline)
                    except Exception as e:
                        logger.warning(f"Could not insert baseline {baseline[0]}: {e}")

                logger.info(f"Initialized {len(baselines)} performance baselines")

        except Exception as e:
            logger.warning(f"Failed to initialize performance baselines: {e}")

        logger.debug("Performance baseline initialization completed")

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

    def get_performance_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive database performance statistics.
        Returns:
            Dictionary with performance metrics and analysis
        """
        try:
            stats: dict[str, Any] = {
                "database_info": self._get_database_info(),
                "table_statistics": self._get_table_statistics(),
                "index_usage": self._get_index_usage_statistics(),
                "query_performance": self._get_query_performance_hints(),
                "maintenance_recommendations": self._get_maintenance_recommendations(),
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get performance statistics: {e}")
            return {"error": str(e)}

    def _get_database_info(self) -> dict[str, Any]:
        """Get basic database information."""
        info = {}
        try:
            # Database file size
            size_result = self.db.fetch_one(
                "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
            )
            info["database_size_bytes"] = size_result[0] if size_result else 0

            # Page information
            page_count = self.db.fetch_one("PRAGMA page_count")
            page_size = self.db.fetch_one("PRAGMA page_size")
            info["page_count"] = page_count[0] if page_count else 0
            info["page_size"] = page_size[0] if page_size else 0

            # Cache information
            cache_size = self.db.fetch_one("PRAGMA cache_size")
            info["cache_size_pages"] = cache_size[0] if cache_size else 0

            # Journal mode
            journal_mode = self.db.fetch_one("PRAGMA journal_mode")
            info["journal_mode"] = journal_mode[0] if journal_mode else "unknown"

            # Synchronous setting
            sync_mode = self.db.fetch_one("PRAGMA synchronous")
            info["synchronous_mode"] = sync_mode[0] if sync_mode else 0

        except Exception as e:
            logger.warning(f"Could not fetch database info: {e}")

        return info

    def _get_table_statistics(self) -> list[dict[str, Any]]:
        """Get statistics for each table."""
        table_stats = []
        try:
            tables = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )

            for table_row in tables:
                table_name = table_row["name"]
                try:
                    # Row count
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    )
                    row_count = count_result["count"] if count_result else 0

                    # Table size estimation
                    dbstat_result = self.db.fetch_one(
                        f"SELECT SUM(pgsize) as size FROM dbstat WHERE name = '{table_name}'"
                    )
                    table_size = (
                        dbstat_result["size"]
                        if dbstat_result and dbstat_result["size"]
                        else 0
                    )

                    table_stats.append(
                        {
                            "table_name": table_name,
                            "row_count": row_count,
                            "estimated_size_bytes": table_size,
                            "avg_row_size_bytes": (
                                table_size / row_count if row_count > 0 else 0
                            ),
                        }
                    )

                except Exception as e:
                    logger.warning(
                        f"Could not get statistics for table {table_name}: {e}"
                    )
                    table_stats.append({"table_name": table_name, "error": str(e)})

        except Exception as e:
            logger.warning(f"Could not fetch table statistics: {e}")

        return table_stats

    def _get_index_usage_statistics(self) -> list[dict[str, Any]]:
        """Get index usage and effectiveness statistics."""
        index_stats = []
        try:
            # Get all indexes
            indexes = self.db.fetch_all(
                "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )

            for index_row in indexes:
                index_name = index_row["name"]
                table_name = index_row["tbl_name"]

                try:
                    # Index size and page count (if dbstat is available)
                    try:
                        size_result = self.db.fetch_one(
                            f"SELECT COUNT(*) as pages, SUM(pgsize) as size FROM dbstat WHERE name = '{index_name}'"
                        )
                        pages = size_result["pages"] if size_result else 0
                        size_bytes = size_result["size"] if size_result else 0
                    except Exception:
                        pages = 0
                        size_bytes = 0

                    index_stats.append(
                        {
                            "index_name": index_name,
                            "table_name": table_name,
                            "pages": pages,
                            "size_bytes": size_bytes,
                            "sql": index_row["sql"],
                        }
                    )

                except Exception as e:
                    logger.warning(
                        f"Could not get statistics for index {index_name}: {e}"
                    )

        except Exception as e:
            logger.warning(f"Could not fetch index statistics: {e}")

        return index_stats

    def _get_query_performance_hints(self) -> dict[str, Any]:
        """Get query performance analysis and hints."""
        hints: Any = {
            "recommendations": [],
            "slow_query_patterns": [],
            "optimization_opportunities": [],
        }

        try:
            # Check for missing indexes on foreign keys
            tables_with_fks = [
                ("vector_indexes", "document_id", "documents"),
                ("document_tags", "document_id", "documents"),
                ("document_tags", "tag_id", "tags"),
                ("citations", "document_id", "documents"),
                ("citation_relations", "source_document_id", "documents"),
                ("citation_relations", "target_document_id", "documents"),
                ("citation_relations", "source_citation_id", "citations"),
                ("citation_relations", "target_citation_id", "citations"),
            ]

            for table, column, ref_table in tables_with_fks:
                try:
                    # Check if index exists for this foreign key
                    index_check = self.db.fetch_all(
                        f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table}' AND sql LIKE '%{column}%'"
                    )

                    if not index_check:
                        hints["recommendations"].append(
                            f"Consider adding index on {table}.{column} for foreign key performance"
                        )

                except Exception:
                    pass

            # Analyze table sizes for potential partitioning
            try:
                large_tables = self.db.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )

                for table_row in large_tables:
                    table_name = table_row["name"]
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    )
                    row_count = count_result["count"] if count_result else 0

                    if row_count > 10000:
                        hints["optimization_opportunities"].append(
                            f"Table {table_name} has {row_count} rows - consider archiving old data"
                        )

            except Exception:
                pass

            # Check for potential full table scans
            common_queries = [
                (
                    "documents",
                    "title",
                    "Text search on title without LIKE optimization",
                ),
                ("citations", "authors", "Author search without proper indexing"),
                ("citations", "publication_year", "Year range queries"),
            ]

            for table, column, description in common_queries:
                hints["slow_query_patterns"].append(
                    {
                        "table": table,
                        "column": column,
                        "description": description,
                        "recommendation": f"Use indexed queries on {table}.{column}",
                    }
                )

        except Exception as e:
            logger.warning(f"Could not generate performance hints: {e}")

        return hints

    def _get_maintenance_recommendations(self) -> list[str]:
        """Get database maintenance recommendations."""
        recommendations = []

        try:
            # Check if ANALYZE has been run recently
            recommendations.append(
                "Run ANALYZE periodically to update query optimizer statistics"
            )

            # Check journal mode
            journal_mode = self.db.fetch_one("PRAGMA journal_mode")
            if journal_mode and journal_mode[0] != "WAL":
                recommendations.append(
                    "Consider using WAL mode (PRAGMA journal_mode=WAL) for better concurrent access"
                )

            # Check cache size
            cache_size = self.db.fetch_one("PRAGMA cache_size")
            if cache_size and abs(cache_size[0]) < 2000:  # Less than 2MB cache
                recommendations.append(
                    "Consider increasing cache size (PRAGMA cache_size) for better performance"
                )

            # Check for unused indexes
            recommendations.append(
                "Monitor index usage and remove unused indexes to save space"
            )

            # Vacuum recommendation
            recommendations.append(
                "Run VACUUM periodically to reclaim unused space and optimize file layout"
            )

        except Exception as e:
            logger.warning(f"Could not generate maintenance recommendations: {e}")

        return recommendations

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
                    f"Schema mismatch: {current_version} != {self.CURRENT_VERSION}"
                )
                return False
            # Check required tables exist
            required_tables = [
                "documents",
                "vector_indexes",
                "tags",
                "document_tags",
                "citations",
                "citation_relations",
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

    def optimize_database_performance(self) -> dict[str, Any]:
        """
        Run database optimization procedures.
        Returns:
            Dictionary with optimization results
        """
        results = {"operations_performed": [], "warnings": [], "success": False}

        try:
            # Update statistics for query optimizer
            logger.info("Updating database statistics...")
            self.db.execute("ANALYZE")
            results["operations_performed"].append("Updated query optimizer statistics")

            # Check and optimize cache settings
            cache_size = self.db.fetch_one("PRAGMA cache_size")
            current_cache = cache_size[0] if cache_size else 0

            if abs(current_cache) < 4000:  # Less than 4MB
                self.db.execute("PRAGMA cache_size = -4096")  # Set to 4MB
                results["operations_performed"].append("Increased cache size to 4MB")

            # Enable WAL mode if not already enabled
            journal_mode = self.db.fetch_one("PRAGMA journal_mode")
            if journal_mode and journal_mode[0] != "WAL":
                try:
                    self.db.execute("PRAGMA journal_mode=WAL")
                    results["operations_performed"].append(
                        "Enabled WAL mode for better concurrency"
                    )
                except Exception as e:
                    results["warnings"].append(f"Could not enable WAL mode: {e}")

            # Optimize synchronous setting for performance
            sync_mode = self.db.fetch_one("PRAGMA synchronous")
            if sync_mode and sync_mode[0] > 1:  # FULL=2, NORMAL=1, OFF=0
                self.db.execute("PRAGMA synchronous = NORMAL")
                results["operations_performed"].append("Optimized synchronous setting")

            # Enable foreign key constraints if not enabled
            fk_check = self.db.fetch_one("PRAGMA foreign_keys")
            if not fk_check or fk_check[0] != 1:
                self.db.execute("PRAGMA foreign_keys = ON")
                results["operations_performed"].append(
                    "Enabled foreign key constraints"
                )

            results["success"] = True
            logger.info("Database optimization completed successfully")

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            results["error"] = str(e)

        return results

    def get_query_execution_plan(self, query: str) -> list[dict[str, Any]]:
        """
        Get the execution plan for a query to analyze performance.
        Args:
            query: SQL query to analyze
        Returns:
            List of execution plan steps
        """
        try:
            # Use EXPLAIN QUERY PLAN to get the execution strategy
            plan_query = f"EXPLAIN QUERY PLAN {query}"
            plan_rows = self.db.fetch_all(plan_query)

            execution_plan = []
            for row in plan_rows:
                step = {
                    "id": row.get("id", 0),
                    "parent": row.get("parent", 0),
                    "detail": row.get("detail", "No detail available"),
                }
                execution_plan.append(step)

            return execution_plan

        except Exception as e:
            logger.error(f"Failed to get execution plan for query: {e}")
            return [{"error": str(e)}]

    def analyze_slow_queries(self) -> dict[str, Any]:
        """
        Analyze potential slow query patterns based on current schema.
        Returns:
            Dictionary with slow query analysis and recommendations
        """
        analysis: Any = {
            "potential_slow_queries": [],
            "optimization_suggestions": [],
            "index_recommendations": [],
        }

        try:
            # Common slow query patterns to check for
            slow_patterns = [
                {
                    "query": "SELECT * FROM documents WHERE title LIKE '%search%'",
                    "issue": "Full-text search without FTS index",
                    "recommendation": "Consider implementing FTS5 virtual table for text search",
                },
                {
                    "query": "SELECT * FROM citations WHERE authors LIKE '%author%'",
                    "issue": "Pattern matching on large text field",
                    "recommendation": "Use proper text indexing or consider exact match queries",
                },
                {
                    "query": "SELECT d.*, COUNT(c.id) FROM documents d LEFT JOIN citations c ON d.id = c.document_id GROUP BY d.id",
                    "issue": "Large aggregation without proper indexes",
                    "recommendation": "Ensure foreign key indexes are present and consider materialized views",
                },
                {
                    "query": "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10",
                    "issue": "Sorting large table without covering index",
                    "recommendation": "Use covering index with (created_at DESC, frequently_selected_columns)",
                },
            ]

            analysis["potential_slow_queries"] = slow_patterns

            # Index recommendations based on schema analysis
            index_recommendations = [
                "CREATE INDEX IF NOT EXISTS idx_documents_title_fts ON documents(title) -- For text search",
                "CREATE INDEX IF NOT EXISTS idx_citations_composite_search ON citations(authors, publication_year DESC) -- For author+year queries",
                "CREATE INDEX IF NOT EXISTS idx_documents_covering_list ON documents(created_at DESC, title, file_size) -- Covering index for listing",
            ]

            analysis["index_recommendations"] = index_recommendations

            # General optimization suggestions
            optimization_suggestions = [
                "Use LIMIT clauses in queries to avoid fetching large result sets",
                "Prefer exact matches over LIKE patterns when possible",
                "Use EXISTS instead of IN for subqueries when checking existence",
                "Consider pagination for large result sets",
                "Use prepared statements to improve query parsing performance",
                "Monitor and log slow queries in application code",
            ]

            analysis["optimization_suggestions"] = optimization_suggestions

        except Exception as e:
            logger.error(f"Failed to analyze slow queries: {e}")
            analysis["error"] = str(e)

        return analysis

    def get_advanced_query_analysis(
        self, query: str, params: tuple = ()
    ) -> dict[str, Any]:
        """
        Perform advanced analysis of a specific query including execution plan,
        index usage, and optimization recommendations.
        Args:
            query: SQL query to analyze
            params: Query parameters
        Returns:
            Dictionary with comprehensive query analysis
        """
        analysis = {
            "query": query,
            "execution_plan": [],
            "index_usage": [],
            "performance_metrics": {},
            "optimization_recommendations": [],
            "cost_analysis": {},
        }

        try:
            # Get execution plan
            analysis["execution_plan"] = self.get_query_execution_plan(query)

            # Measure execution time
            import time

            start_time = time.time()

            # Execute query to measure performance
            if params:
                results = self.db.fetch_all(query, params)
            else:
                results = self.db.fetch_all(query)

            execution_time = (time.time() - start_time) * 1000  # milliseconds

            analysis["performance_metrics"] = {
                "execution_time_ms": execution_time,
                "rows_returned": len(results),
                "query_complexity": self._assess_query_complexity(query),
            }

            # Analyze execution plan for index usage
            plan_text = " ".join(
                [step.get("detail", "") for step in analysis["execution_plan"]]
            )
            analysis["index_usage"] = self._extract_index_usage_from_plan(plan_text)

            # Generate optimization recommendations
            analysis["optimization_recommendations"] = (
                self._generate_query_optimization_recommendations(
                    query, analysis["execution_plan"], execution_time
                )
            )

            # Cost analysis
            analysis["cost_analysis"] = self._analyze_query_cost(
                query, analysis["execution_plan"], len(results)
            )

        except Exception as e:
            logger.error(f"Failed to perform advanced query analysis: {e}")
            analysis["error"] = str(e)

        return analysis

    def _assess_query_complexity(self, query: str) -> str:
        """Assess the complexity of a SQL query."""
        query_lower = query.lower()
        complexity_indicators = {"simple": 0, "moderate": 0, "complex": 0}

        # Simple indicators
        if "select" in query_lower and "from" in query_lower:
            complexity_indicators["simple"] += 1

        # Moderate indicators
        moderate_keywords = ["join", "group by", "order by", "having", "union", "case"]
        for keyword in moderate_keywords:
            if keyword in query_lower:
                complexity_indicators["moderate"] += 1

        # Complex indicators
        complex_keywords = ["subquery", "exists", "window", "recursive", "cte"]
        for keyword in complex_keywords:
            if keyword in query_lower:
                complexity_indicators["complex"] += 1

        # Determine overall complexity
        if (
            complexity_indicators["complex"] > 0
            or complexity_indicators["moderate"] > 2
        ):
            return "complex"
        elif complexity_indicators["moderate"] > 0:
            return "moderate"
        else:
            return "simple"

    def _extract_index_usage_from_plan(self, plan_text: str) -> list[str]:
        """Extract index names used from execution plan text."""
        indexes_used = []

        # Look for index usage patterns in SQLite execution plans
        import re

        # Pattern for "USING INDEX index_name"
        index_patterns = [
            r"USING INDEX (\w+)",
            r"INDEX (\w+)",
            r"idx_\w+",  # Our index naming convention
        ]

        for pattern in index_patterns:
            matches = re.findall(pattern, plan_text, re.IGNORECASE)
            indexes_used.extend(matches)

        return list[Any](set[str](indexes_used))  # Remove duplicates

    def _generate_query_optimization_recommendations(
        self, query: str, execution_plan: list[Any], execution_time: float
    ) -> list[str]:
        """Generate optimization recommendations based on query analysis."""
        recommendations = []

        plan_text = " ".join([step.get("detail", "") for step in execution_plan])
        query_lower = query.lower()

        # Slow query threshold
        if execution_time > 100:  # > 100ms
            recommendations.append(
                f"Query is slow ({execution_time:.2f}ms). Consider optimization."
            )

        # Table scan detection
        if "scan table" in plan_text.lower():
            recommendations.append(
                "Table scan detected. Consider adding appropriate indexes."
            )

        # LIKE pattern optimization
        if "like" in query_lower and "%" in query:
            if query.count("%") >= 2:  # Leading and trailing wildcards
                recommendations.append(
                    "LIKE with leading wildcards can't use indexes efficiently. Consider FTS if full-text search is needed."
                )

        # ORDER BY without index
        if "order by" in query_lower and "using index" not in plan_text.lower():
            recommendations.append("ORDER BY clause may benefit from a covering index.")

        # GROUP BY optimization
        if "group by" in query_lower:
            recommendations.append(
                "GROUP BY queries can benefit from indexes on grouping columns."
            )

        # Large LIMIT without index
        if "limit" in query_lower and "using index" not in plan_text.lower():
            recommendations.append(
                "LIMIT queries should use indexes for optimal performance."
            )

        # JOIN optimization
        if "join" in query_lower and "nested loop" in plan_text.lower():
            recommendations.append(
                "JOIN operations should have indexes on join columns for better performance."
            )

        return recommendations

    def _analyze_query_cost(
        self, query: str, execution_plan: list[Any], rows_returned: int
    ) -> dict[str, Any]:
        """Analyze the cost characteristics of a query."""
        cost_analysis = {
            "estimated_cost": "unknown",
            "io_operations": "unknown",
            "memory_usage": "low",
            "scalability_concerns": [],
        }

        plan_text = " ".join([step.get("detail", "") for step in execution_plan])

        # Estimate cost based on operations
        cost_score = 0

        if "scan table" in plan_text.lower():
            cost_score += 5
        if "sort" in plan_text.lower():
            cost_score += 3
        if "nested loop" in plan_text.lower():
            cost_score += 4
        if "hash join" in plan_text.lower():
            cost_score += 2

        # Cost categorization
        if cost_score <= 2:
            cost_analysis["estimated_cost"] = "low"
        elif cost_score <= 6:
            cost_analysis["estimated_cost"] = "medium"
        else:
            cost_analysis["estimated_cost"] = "high"

        # Memory usage estimation
        if "sort" in plan_text.lower() or "hash" in plan_text.lower():
            cost_analysis["memory_usage"] = "medium"
        if "group by" in query.lower() and rows_returned > 1000:
            cost_analysis["memory_usage"] = "high"

        # Scalability concerns
        if "scan table" in plan_text.lower():
            cost_analysis["scalability_concerns"].append(
                "Full table scans don't scale with data size"
            )
        if rows_returned > 10000:
            cost_analysis["scalability_concerns"].append(
                "Large result sets may cause memory issues"
            )

        return cost_analysis

    def benchmark_query_performance(
        self, queries: list[tuple[str, str, tuple]]
    ) -> dict[str, Any]:
        """
        Benchmark multiple queries and compare their performance.
        Args:
            queries: List of (query_name, query_sql, params) tuples
        Returns:
            Dictionary with benchmark results and comparisons
        """
        benchmark_results: Any = {
            "benchmarks": [],
            "fastest_query": None,
            "slowest_query": None,
            "average_time": 0,
            "performance_summary": {},
        }

        try:
            import time

            for query_name, query_sql, params in queries:
                # Run query multiple times for accurate measurement
                execution_times = []

                for _ in range(3):  # Run 3 times
                    start_time = time.time()
                    try:
                        if params:
                            results = self.db.fetch_all(query_sql, params)
                        else:
                            results = self.db.fetch_all(query_sql)

                        execution_time = (time.time() - start_time) * 1000
                        execution_times.append(execution_time)

                    except Exception as e:
                        logger.error(f"Benchmark query {query_name} failed: {e}")
                        break

                if execution_times:
                    avg_time = sum(execution_times) / len(execution_times)
                    min_time = min(execution_times)
                    max_time = max(execution_times)

                    benchmark_result = {
                        "query_name": query_name,
                        "average_time_ms": avg_time,
                        "min_time_ms": min_time,
                        "max_time_ms": max_time,
                        "rows_returned": len(results) if "results" in locals() else 0,
                        "consistency": (
                            "high" if (max_time - min_time) < avg_time * 0.2 else "low"
                        ),
                    }

                    benchmark_results["benchmarks"].append(benchmark_result)

            # Calculate summary statistics
            if benchmark_results["benchmarks"]:
                times = [b["average_time_ms"] for b in benchmark_results["benchmarks"]]
                benchmark_results["average_time"] = sum(times) / len(times)

                # Find fastest and slowest
                fastest = min(
                    benchmark_results["benchmarks"], key=lambda x: x["average_time_ms"]
                )
                slowest = max(
                    benchmark_results["benchmarks"], key=lambda x: x["average_time_ms"]
                )

                benchmark_results["fastest_query"] = fastest["query_name"]
                benchmark_results["slowest_query"] = slowest["query_name"]

                # Performance summary
                benchmark_results["performance_summary"] = {
                    "total_queries_tested": len(benchmark_results["benchmarks"]),
                    "performance_range_ms": f"{fastest['average_time_ms']:.2f} - {slowest['average_time_ms']:.2f}",
                    "performance_variance": (
                        slowest["average_time_ms"] / fastest["average_time_ms"]
                        if fastest["average_time_ms"] > 0
                        else 0
                    ),
                }

        except Exception as e:
            logger.error(f"Query benchmark failed: {e}")
            benchmark_results["error"] = str(e)

        return benchmark_results

    def analyze_index_effectiveness(self) -> dict[str, Any]:
        """
        Analyze the effectiveness of all indexes in the database.
        Returns:
            Dictionary with index effectiveness analysis
        """
        analysis = {
            "indexes": [],
            "recommendations": [],
            "total_indexes": 0,
            "potentially_unused": [],
            "high_impact": [],
            "summary": {},
        }

        try:
            # Get all user-defined indexes
            indexes = self.db.fetch_all(
                "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )

            analysis["total_indexes"] = len(indexes)

            for index_row in indexes:
                index_name = index_row["name"]
                table_name = index_row["tbl_name"]

                index_analysis = {
                    "name": index_name,
                    "table": table_name,
                    "type": "unknown",
                    "size_estimate": 0,
                    "selectivity_estimate": 0.0,
                    "usage_pattern": "unknown",
                    "effectiveness": "unknown",
                }

                try:
                    # Get index size if dbstat is available
                    try:
                        size_result = self.db.fetch_one(
                            f"SELECT COUNT(*) as pages, SUM(pgsize) as size FROM dbstat WHERE name = '{index_name}'"
                        )
                        if size_result and size_result["size"]:
                            index_analysis["size_estimate"] = size_result["size"]
                    except Exception:
                        pass

                    # Estimate selectivity by checking if index is on unique or near-unique columns
                    try:
                        # Check if it's a unique index
                        if "UNIQUE" in (index_row["sql"] or "").upper():
                            index_analysis["type"] = "unique"
                            index_analysis["selectivity_estimate"] = 1.0
                            index_analysis["effectiveness"] = "high"
                        else:
                            index_analysis["type"] = "non-unique"
                            # For non-unique indexes, we can't easily determine selectivity without more analysis
                            index_analysis["selectivity_estimate"] = (
                                0.5  # Conservative estimate
                            )
                            index_analysis["effectiveness"] = "medium"
                    except Exception:
                        pass

                    # Analyze index usage patterns based on name
                    if "file_hash" in index_name or "content_hash" in index_name:
                        index_analysis["usage_pattern"] = "duplicate_detection"
                        index_analysis["effectiveness"] = "high"
                    elif "created_at" in index_name or "updated_at" in index_name:
                        index_analysis["usage_pattern"] = "temporal_queries"
                        index_analysis["effectiveness"] = "high"
                    elif "document_id" in index_name:
                        index_analysis["usage_pattern"] = "foreign_key_joins"
                        index_analysis["effectiveness"] = "high"
                    elif "title" in index_name:
                        index_analysis["usage_pattern"] = "text_search"
                        index_analysis["effectiveness"] = "medium"

                except Exception as e:
                    logger.warning(f"Could not analyze index {index_name}: {e}")

                analysis["indexes"].append(index_analysis)

            # Categorize indexes
            for index_info in analysis["indexes"]:
                if index_info["effectiveness"] == "high":
                    analysis["high_impact"].append(index_info["name"])
                elif (
                    index_info["effectiveness"] == "unknown"
                    and index_info["size_estimate"] > 0
                ):
                    analysis["potentially_unused"].append(index_info["name"])

            # Generate recommendations
            if analysis["potentially_unused"]:
                analysis["recommendations"].append(
                    f"Consider monitoring usage of {len(analysis['potentially_unused'])} potentially unused indexes"
                )

            if len(analysis["high_impact"]) / analysis["total_indexes"] < 0.5:
                analysis["recommendations"].append(
                    "Consider adding more targeted indexes for frequently used query patterns"
                )

            analysis["summary"] = {
                "total_indexes": analysis["total_indexes"],
                "high_impact_indexes": len(analysis["high_impact"]),
                "potentially_unused_indexes": len(analysis["potentially_unused"]),
                "index_effectiveness_ratio": (
                    len(analysis["high_impact"]) / analysis["total_indexes"]
                    if analysis["total_indexes"] > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to analyze index effectiveness: {e}")
            analysis["error"] = str(e)

        return analysis

    def _migration_006_add_authentication_tables(self) -> None:
        """
        Migration 006: Add authentication and user management tables.
        Creates tables for JWT-based authentication system.
        """
        logger.info("Applying migration 006: Add authentication tables")

        # Create users table
        users_sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            role VARCHAR(20) DEFAULT 'user' NOT NULL,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            is_verified BOOLEAN DEFAULT 0 NOT NULL,
            account_status VARCHAR(30) DEFAULT 'pending_verification' NOT NULL,
            failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
            last_failed_login DATETIME,
            account_locked_until DATETIME,
            password_changed_at DATETIME,
            password_reset_token VARCHAR(255),
            password_reset_expires DATETIME,
            email_verification_token VARCHAR(255),
            email_verified_at DATETIME,
            refresh_token_version INTEGER DEFAULT 0 NOT NULL,
            last_login DATETIME,
            last_activity DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            security_metadata TEXT
        )
        """
        self.db.execute(users_sql)
        logger.info("Created users table")

        # Create refresh_tokens table for token management
        refresh_tokens_sql = """
        CREATE TABLE refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_jti VARCHAR(255) UNIQUE NOT NULL,
            token_family VARCHAR(255) NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            revoked_at DATETIME,
            revoked_reason VARCHAR(255),
            device_info VARCHAR(500),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
        self.db.execute(refresh_tokens_sql)
        logger.info("Created refresh_tokens table")

        # Create user_sessions table for session tracking
        user_sessions_sql = """
        CREATE TABLE user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ended_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
        self.db.execute(user_sessions_sql)
        logger.info("Created user_sessions table")

        # Create login_attempts table for security monitoring
        login_attempts_sql = """
        CREATE TABLE login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(255) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            success BOOLEAN NOT NULL,
            failure_reason VARCHAR(255),
            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
        self.db.execute(login_attempts_sql)
        logger.info("Created login_attempts table")

        # Create audit_log table for security auditing
        audit_log_sql = """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id INTEGER,
            details TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
        self.db.execute(audit_log_sql)
        logger.info("Created audit_log table")

        # Create indexes for authentication tables
        auth_indexes = [
            # Users table indexes
            "CREATE INDEX idx_users_username ON users(username)",
            "CREATE INDEX idx_users_email ON users(email)",
            "CREATE INDEX idx_users_role ON users(role)",
            "CREATE INDEX idx_users_is_active ON users(is_active)",
            "CREATE INDEX idx_users_last_login ON users(last_login DESC)",
            "CREATE INDEX idx_users_created_at ON users(created_at DESC)",
            # Refresh tokens indexes
            "CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
            "CREATE INDEX idx_refresh_tokens_jti ON refresh_tokens(token_jti)",
            "CREATE INDEX idx_refresh_tokens_family ON refresh_tokens(token_family)",
            "CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at)",
            "CREATE INDEX idx_refresh_tokens_revoked ON refresh_tokens(revoked_at)",
            # User sessions indexes
            "CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id)",
            "CREATE INDEX idx_user_sessions_token ON user_sessions(session_token)",
            "CREATE INDEX idx_user_sessions_active ON user_sessions(ended_at) WHERE ended_at IS NULL",
            # Login attempts indexes
            "CREATE INDEX idx_login_attempts_username ON login_attempts(username)",
            "CREATE INDEX idx_login_attempts_ip ON login_attempts(ip_address)",
            "CREATE INDEX idx_login_attempts_time ON login_attempts(attempted_at DESC)",
            "CREATE INDEX idx_login_attempts_success ON login_attempts(success)",
            # Audit log indexes
            "CREATE INDEX idx_audit_log_user_id ON audit_log(user_id)",
            "CREATE INDEX idx_audit_log_action ON audit_log(action)",
            "CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id)",
            "CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC)",
        ]

        for index_sql in auth_indexes:
            try:
                self.db.execute(index_sql)
            except Exception as e:
                logger.warning(f"Could not create auth index: {e}")

        logger.info("Created authentication indexes")

        # Create default admin user (password from environment or generated)
        # Password is hashed with bcrypt
        import os
        import secrets
        import string

        import bcrypt

        # Get default admin password from environment variable or generate a secure one
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
        if not default_password:
            # Generate a secure random password if not provided
            alphabet = string.ascii_letters + string.digits + string.punctuation
            default_password = "".join(secrets.choice(alphabet) for _ in range(16))
            logger.warning(
                "No DEFAULT_ADMIN_PASSWORD environment variable set[str]. "
                f"Generated temporary password: {default_password}"
            )
            logger.warning(
                "IMPORTANT: Please change this password immediately after first login!"
            )

        password_hash = bcrypt.hashpw(
            default_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        admin_user_sql = """
        INSERT INTO users (
            username, email, password_hash, full_name, role,
            is_active, is_verified, account_status, email_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """

        try:
            self.db.execute(
                admin_user_sql,
                (
                    "admin",
                    "admin@localhost",
                    password_hash,
                    "System Administrator",
                    "admin",
                    1,  # is_active
                    1,  # is_verified
                    "active",
                ),
            )
            logger.info(
                "Created default admin user (username: admin, password: admin123!)"
            )
            logger.warning(
                "⚠️ IMPORTANT: Change the default admin password immediately!"
            )
        except Exception as e:
            logger.warning(
                f"Could not create default admin user (may already exist): {e}"
            )

        logger.info("Migration 006 completed successfully")

    def _migration_007_add_tags_column(self) -> None:
        """
        Migration 007: Add tags column to documents table.
        Adds a tags column to store comma-separated tag strings.
        """
        logger.info("Applying migration 007: Add tags column to documents table")

        # Add tags column to documents table
        alter_sql = "ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT ''"
        self.db.execute(alter_sql)
        logger.info("Added tags column to documents table")

        logger.info("Migration 007 completed successfully")
