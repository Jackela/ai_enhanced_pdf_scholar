"""
Migration Conversion Script

This script converts the remaining monolithic migrations (004, 005, 007)
into individual modular migration files.

Run this script to complete the migration system refactoring.
"""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_migration_004_performance_optimization():
    """Create migration 004 for performance optimization."""

    migration_content = '''"""
Migration 004: Performance Optimization

Adds comprehensive indexing strategy for high-performance queries including:
- Strategic indexes for documents, citations, and vector_indexes tables
- Composite indexes for common query patterns
- Partial indexes for filtered queries
"""

import logging
from typing import Any
from ..base import BaseMigration

logger = logging.getLogger(__name__)


class PerformanceOptimizationMigration(BaseMigration):
    """
    Performance optimization with strategic indexes.

    Adds comprehensive indexing strategy for high-performance queries
    with focus on query patterns used by the application.
    """

    @property
    def version(self) -> int:
        return 4

    @property
    def description(self) -> str:
        return "Performance optimization with strategic indexes for high-performance queries"

    @property
    def dependencies(self) -> list[int]:
        return [1, 3]  # Requires initial schema and citation tables

    @property
    def rollback_supported(self) -> bool:
        return True  # Can drop indexes safely

    def up(self) -> None:
        """Apply performance optimization indexes."""
        logger.info("Applying performance optimization indexes")

        # Performance indexes for documents table
        self._create_document_performance_indexes()

        # Performance indexes for vector_indexes table
        self._create_vector_performance_indexes()

        # Performance indexes for citations table
        self._create_citation_performance_indexes()

        # Performance indexes for citation_relations table
        self._create_relation_performance_indexes()

        # Tag performance indexes
        self._create_tag_performance_indexes()

        # Update database statistics
        self._update_database_statistics()

        logger.info("Performance optimization completed successfully")

    def down(self) -> None:
        """Remove performance optimization indexes."""
        logger.info("Removing performance optimization indexes")

        # Get all indexes created by this migration
        performance_indexes = [
            # Document indexes
            "idx_documents_file_hash_unique", "idx_documents_content_hash_perf",
            "idx_documents_created_desc_perf", "idx_documents_updated_desc_perf",
            "idx_documents_accessed_desc_perf", "idx_documents_title_search",
            "idx_documents_file_size", "idx_documents_page_count",

            # Composite document indexes
            "idx_documents_created_title_comp", "idx_documents_access_size_comp",
            "idx_documents_hash_created_comp", "idx_documents_content_pages_comp",

            # Vector indexes
            "idx_vector_indexes_document_perf", "idx_vector_indexes_hash_unique",
            "idx_vector_indexes_created_desc", "idx_vector_indexes_doc_chunks",

            # Citation indexes
            "idx_citations_document_perf", "idx_citations_authors_search",
            "idx_citations_title_search", "idx_citations_year_desc",
            "idx_citations_doi_lookup", "idx_citations_type_filter",
            "idx_citations_confidence_desc", "idx_citations_created_desc",

            # Citation composite indexes
            "idx_citations_doc_confidence", "idx_citations_author_year",
            "idx_citations_type_confidence",

            # Citation relation indexes
            "idx_citation_relations_source_perf", "idx_citation_relations_target_perf",
            "idx_citation_relations_source_citation", "idx_citation_relations_target_citation",
            "idx_citation_relations_type_perf", "idx_citation_relations_confidence",
            "idx_citation_relations_source_target", "idx_citation_relations_type_confidence",

            # Tag indexes
            "idx_tags_name_unique", "idx_document_tags_document_perf", "idx_document_tags_tag_perf"
        ]

        for index_name in performance_indexes:
            try:
                self.execute_sql(f"DROP INDEX IF EXISTS {index_name}")
                logger.debug(f"Dropped index: {index_name}")
            except Exception as e:
                logger.warning(f"Could not drop index {index_name}: {e}")

        logger.info("Performance optimization rollback completed")

    def _create_document_performance_indexes(self) -> None:
        """Create performance indexes for documents table."""
        document_indexes = [
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
        composite_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_documents_created_title_comp ON documents(created_at DESC, title)",
            "CREATE INDEX IF NOT EXISTS idx_documents_access_size_comp ON documents(last_accessed DESC, file_size) WHERE last_accessed IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_documents_hash_created_comp ON documents(file_hash, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_documents_content_pages_comp ON documents(content_hash, page_count) WHERE content_hash IS NOT NULL AND page_count IS NOT NULL",
        ]

        all_indexes = document_indexes + composite_indexes
        self._create_indexes(all_indexes, "document performance")

    def _create_vector_performance_indexes(self) -> None:
        """Create performance indexes for vector_indexes table."""
        vector_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_document_perf ON vector_indexes(document_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_indexes_hash_unique ON vector_indexes(index_hash)",
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_created_desc ON vector_indexes(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_vector_indexes_doc_chunks ON vector_indexes(document_id, chunk_count) WHERE chunk_count IS NOT NULL",
        ]

        self._create_indexes(vector_indexes, "vector performance")

    def _create_citation_performance_indexes(self) -> None:
        """Create performance indexes for citations table."""
        citation_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_citations_document_perf ON citations(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_citations_authors_search ON citations(authors COLLATE NOCASE) WHERE authors IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_title_search ON citations(title COLLATE NOCASE) WHERE title IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_year_desc ON citations(publication_year DESC) WHERE publication_year IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_doi_lookup ON citations(doi) WHERE doi IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_type_filter ON citations(citation_type) WHERE citation_type IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_confidence_desc ON citations(confidence_score DESC) WHERE confidence_score IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_created_desc ON citations(created_at DESC)",
        ]

        # Composite indexes for citations
        citation_composite = [
            "CREATE INDEX IF NOT EXISTS idx_citations_doc_confidence ON citations(document_id, confidence_score DESC) WHERE confidence_score IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_author_year ON citations(authors, publication_year DESC) WHERE authors IS NOT NULL AND publication_year IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citations_type_confidence ON citations(citation_type, confidence_score DESC) WHERE citation_type IS NOT NULL AND confidence_score IS NOT NULL",
        ]

        all_indexes = citation_indexes + citation_composite
        self._create_indexes(all_indexes, "citation performance")

    def _create_relation_performance_indexes(self) -> None:
        """Create performance indexes for citation_relations table."""
        relation_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_perf ON citation_relations(source_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_target_perf ON citation_relations(target_document_id) WHERE target_document_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_citation ON citation_relations(source_citation_id)",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_target_citation ON citation_relations(target_citation_id) WHERE target_citation_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_type_perf ON citation_relations(relation_type)",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_confidence ON citation_relations(confidence_score DESC) WHERE confidence_score IS NOT NULL",
        ]

        # Composite indexes for relations
        relation_composite = [
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_source_target ON citation_relations(source_document_id, target_document_id) WHERE target_document_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_citation_relations_type_confidence ON citation_relations(relation_type, confidence_score DESC) WHERE confidence_score IS NOT NULL",
        ]

        all_indexes = relation_indexes + relation_composite
        self._create_indexes(all_indexes, "citation relation performance")

    def _create_tag_performance_indexes(self) -> None:
        """Create performance indexes for tag tables."""
        tag_indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name_unique ON tags(name COLLATE NOCASE)",
            "CREATE INDEX IF NOT EXISTS idx_document_tags_document_perf ON document_tags(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_tags_tag_perf ON document_tags(tag_id)",
        ]

        self._create_indexes(tag_indexes, "tag performance")

    def _create_indexes(self, index_list: list[str], category: str) -> None:
        """Helper method to create a list of indexes."""
        created_count = 0
        for index_sql in index_list:
            try:
                self.execute_sql(index_sql)
                created_count += 1
            except Exception as e:
                logger.warning(f"Could not create {category} index: {e}")

        logger.info(f"Created {created_count}/{len(index_list)} {category} indexes")

    def _update_database_statistics(self) -> None:
        """Update database statistics for query optimizer."""
        try:
            self.execute_sql("ANALYZE")
            logger.info("Database statistics updated")
        except Exception as e:
            logger.warning(f"Failed to update database statistics: {e}")

    def post_migrate_checks(self) -> bool:
        """Validate that indexes were created successfully."""
        try:
            # Check that some key indexes exist
            key_indexes = [
                "idx_documents_file_hash_unique",
                "idx_citations_document_perf",
                "idx_vector_indexes_document_perf"
            ]

            for index_name in key_indexes:
                result = self.db.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                )
                if not result:
                    logger.error(f"Key index {index_name} was not created")
                    return False

            logger.info("Post-migration validation passed")
            return True

        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
'''

    return migration_content


def create_migration_005_advanced_performance():
    """Create migration 005 for advanced performance analysis."""

    migration_content = '''"""
Migration 005: Advanced Performance Analysis

Adds specialized indexes, query performance monitoring, and database analytics:
- Covering indexes for complex queries
- Partial indexes for filtered queries
- Performance monitoring tables
- Database performance baselines
"""

import logging
import time
from typing import Any
from ..base import BaseMigration

logger = logging.getLogger(__name__)


class AdvancedPerformanceAnalysisMigration(BaseMigration):
    """
    Advanced performance analysis and optimization.

    Adds specialized indexes, query performance monitoring,
    and database analytics capabilities.
    """

    @property
    def version(self) -> int:
        return 5

    @property
    def description(self) -> str:
        return "Advanced performance analysis with specialized indexes and monitoring"

    @property
    def dependencies(self) -> list[int]:
        return [4]  # Requires basic performance optimization

    @property
    def rollback_supported(self) -> bool:
        return True

    def up(self) -> None:
        """Apply advanced performance optimizations."""
        logger.info("Applying advanced performance analysis and monitoring")

        # Advanced covering indexes
        self._create_covering_indexes()

        # Specialized partial indexes
        self._create_partial_indexes()

        # Expression-based indexes
        self._create_expression_indexes()

        # Full-text search support indexes
        self._create_fts_support_indexes()

        # Create performance monitoring tables
        self._create_performance_monitoring_tables()

        # Initialize performance baselines
        self._initialize_performance_baselines()

        # Optimize database settings
        self._optimize_database_settings()

        logger.info("Advanced performance analysis completed successfully")

    def down(self) -> None:
        """Remove advanced performance optimizations."""
        logger.info("Rolling back advanced performance analysis")

        # Drop monitoring tables
        monitoring_tables = [
            "performance_baselines",
            "index_usage_stats",
            "query_performance_log"
        ]

        for table in monitoring_tables:
            try:
                self.execute_sql(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped monitoring table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")

        # Drop advanced indexes
        advanced_indexes = [
            # Covering indexes
            "idx_documents_listing_cover", "idx_documents_search_cover",
            "idx_documents_recent_cover", "idx_citations_analysis_cover",
            "idx_vector_management_cover",

            # Partial indexes
            "idx_citations_high_confidence", "idx_documents_large_files",
            "idx_documents_recent_hot", "idx_documents_content_dedup",
            "idx_documents_multi_page",

            # Expression indexes
            "idx_documents_created_date", "idx_documents_size_category",
            "idx_citation_density_calc",

            # FTS support indexes
            "idx_documents_title_trigram", "idx_citations_author_search"
        ]

        for index_name in advanced_indexes:
            try:
                self.execute_sql(f"DROP INDEX IF EXISTS {index_name}")
            except Exception as e:
                logger.warning(f"Could not drop advanced index {index_name}: {e}")

        logger.info("Advanced performance analysis rollback completed")

    def _create_covering_indexes(self) -> None:
        """Create covering indexes for complex queries."""
        covering_indexes = [
            # Document listing with metadata
            "CREATE INDEX IF NOT EXISTS idx_documents_listing_cover ON documents(created_at DESC, title, file_size, page_count, last_accessed)",

            # Document search with size filter
            "CREATE INDEX IF NOT EXISTS idx_documents_search_cover ON documents(title COLLATE NOCASE, file_size, created_at DESC, id)",

            # Recent documents with usage analytics
            "CREATE INDEX IF NOT EXISTS idx_documents_recent_cover ON documents(last_accessed DESC, created_at DESC, title, file_size) WHERE last_accessed IS NOT NULL",

            # Citation analysis covering index
            "CREATE INDEX IF NOT EXISTS idx_citations_analysis_cover ON citations(document_id, confidence_score DESC, citation_type, publication_year, authors)",

            # Vector index management covering
            "CREATE INDEX IF NOT EXISTS idx_vector_management_cover ON vector_indexes(document_id, created_at DESC, chunk_count, index_path)",
        ]

        self._create_indexes(covering_indexes, "covering")

    def _create_partial_indexes(self) -> None:
        """Create partial indexes for filtered queries."""
        partial_indexes = [
            # High-confidence citations only
            "CREATE INDEX IF NOT EXISTS idx_citations_high_confidence ON citations(document_id, publication_year DESC, authors) WHERE confidence_score >= 0.8",

            # Large documents (performance-sensitive operations)
            "CREATE INDEX IF NOT EXISTS idx_documents_large_files ON documents(file_size DESC, page_count, created_at DESC) WHERE file_size > 10485760",

            # Recent documents only (hot data)
            "CREATE INDEX IF NOT EXISTS idx_documents_recent_hot ON documents(last_accessed DESC, title)",

            # Documents with content hash (duplicate detection)
            "CREATE INDEX IF NOT EXISTS idx_documents_content_dedup ON documents(content_hash, file_hash, created_at DESC) WHERE content_hash IS NOT NULL AND content_hash != ''",

            # Multi-page documents (academic focus)
            "CREATE INDEX IF NOT EXISTS idx_documents_multi_page ON documents(page_count DESC, created_at DESC, title) WHERE page_count > 1",
        ]

        self._create_indexes(partial_indexes, "partial")

    def _create_expression_indexes(self) -> None:
        """Create expression-based indexes for computed queries."""
        expression_indexes = [
            # Document age calculation (fixed to avoid non-deterministic functions)
            "CREATE INDEX IF NOT EXISTS idx_documents_created_date ON documents(created_at DESC, id)",

            # File size categories for analytics
            "CREATE INDEX IF NOT EXISTS idx_documents_size_category ON documents(CASE WHEN file_size < 1048576 THEN 'small' WHEN file_size < 10485760 THEN 'medium' ELSE 'large' END, file_size)",

            # Citation density (citations per document)
            "CREATE INDEX IF NOT EXISTS idx_citation_density_calc ON citations(document_id, created_at DESC)",
        ]

        self._create_indexes(expression_indexes, "expression")

    def _create_fts_support_indexes(self) -> None:
        """Create indexes to support full-text search."""
        fts_indexes = [
            # Title trigrams for fuzzy search support
            "CREATE INDEX IF NOT EXISTS idx_documents_title_trigram ON documents(SUBSTR(title, 1, 3), title) WHERE LENGTH(title) >= 3",

            # Author name optimization for citations
            "CREATE INDEX IF NOT EXISTS idx_citations_author_search ON citations(SUBSTR(authors, 1, 10), authors) WHERE authors IS NOT NULL AND LENGTH(authors) >= 3",
        ]

        self._create_indexes(fts_indexes, "FTS support")

    def _create_performance_monitoring_tables(self) -> None:
        """Create tables for performance monitoring and query analysis."""
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
        self.execute_sql(query_log_sql)

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
        self.execute_sql(index_stats_sql)

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
        self.execute_sql(baselines_sql)

        # Create indexes for monitoring tables
        monitoring_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_query_log_pattern ON query_performance_log(query_pattern, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_query_log_performance ON query_performance_log(execution_time_ms DESC, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_index_stats_usage ON index_usage_stats(usage_count DESC, effectiveness_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_baselines_metric ON performance_baselines(metric_name, measured_at DESC)",
        ]

        self._create_indexes(monitoring_indexes, "monitoring")
        logger.debug("Performance monitoring tables created successfully")

    def _initialize_performance_baselines(self) -> None:
        """Initialize performance baselines for future comparison."""
        logger.debug("Initializing performance baselines")

        baselines = []

        try:
            # Table row counts
            tables = ['documents', 'vector_indexes', 'citations', 'citation_relations', 'tags', 'document_tags']
            for table in tables:
                try:
                    count_result = self.db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                    count = count_result['count'] if count_result else 0
                    baselines.append((f"table_row_count_{table}", count, "rows", "Table size baseline"))
                except Exception as e:
                    logger.warning(f"Could not get row count for table {table}: {e}")

            # Sample query performance baselines
            sample_queries = [
                ("SELECT COUNT(*) FROM documents", "simple_count_documents"),
                ("SELECT * FROM documents ORDER BY created_at DESC LIMIT 10", "recent_documents_query"),
            ]

            for query, query_name in sample_queries:
                try:
                    start_time = time.time()
                    self.db.fetch_all(query)
                    execution_time = (time.time() - start_time) * 1000
                    baselines.append((f"query_time_{query_name}", execution_time, "milliseconds", f"Baseline for: {query[:50]}..."))
                except Exception as e:
                    logger.warning(f"Could not measure baseline for query {query_name}: {e}")

            # Insert all baselines
            if baselines:
                baseline_insert_sql = """
                INSERT INTO performance_baselines (metric_name, baseline_value, measurement_unit, context_info)
                VALUES (?, ?, ?, ?)
                """
                for baseline in baselines:
                    try:
                        self.execute_sql(baseline_insert_sql, baseline)
                    except Exception as e:
                        logger.warning(f"Could not insert baseline {baseline[0]}: {e}")

                logger.info(f"Initialized {len(baselines)} performance baselines")

        except Exception as e:
            logger.warning(f"Failed to initialize performance baselines: {e}")

    def _optimize_database_settings(self) -> None:
        """Optimize SQLite settings for performance."""
        try:
            performance_settings = [
                "PRAGMA optimize",
                "PRAGMA wal_autocheckpoint=1000",
                "PRAGMA journal_size_limit=67108864",  # 64MB journal size limit
            ]

            for setting in performance_settings:
                try:
                    self.execute_sql(setting)
                    logger.debug(f"Applied performance setting: {setting}")
                except Exception as e:
                    logger.warning(f"Could not apply setting {setting}: {e}")

            logger.info("Database performance settings optimized")

        except Exception as e:
            logger.warning(f"Failed to update database performance settings: {e}")

    def _create_indexes(self, index_list: list[str], category: str) -> None:
        """Helper method to create a list of indexes."""
        created_count = 0
        for index_sql in index_list:
            try:
                self.execute_sql(index_sql)
                created_count += 1
            except Exception as e:
                logger.warning(f"Could not create {category} index: {e}")

        logger.info(f"Created {created_count}/{len(index_list)} {category} indexes")
'''

    return migration_content


def create_migration_007_add_tags_column():
    """Create migration 007 for adding tags column."""

    migration_content = '''"""
Migration 007: Add Tags Column

Adds a tags column to the documents table for storing comma-separated tag strings.
This provides a simple alternative to the normalized tags system.
"""

import logging
from typing import Any
from ..base import BaseMigration

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
'''

    return migration_content


def main():
    """Main conversion function."""
    # Get the project root directory
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    versions_dir = project_root / "src" / "database" / "migrations" / "versions"

    # Ensure versions directory exists
    versions_dir.mkdir(parents=True, exist_ok=True)

    # Create migration files
    migrations = [
        (4, "004_performance_optimization.py", create_migration_004_performance_optimization),
        (5, "005_advanced_performance_analysis.py", create_migration_005_advanced_performance),
        (7, "007_add_tags_column.py", create_migration_007_add_tags_column),
    ]

    for version, filename, creator_func in migrations:
        file_path = versions_dir / filename

        if file_path.exists():
            logger.info(f"Migration {filename} already exists, skipping")
            continue

        logger.info(f"Creating migration {filename}")

        try:
            content = creator_func()
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Successfully created {filename}")
        except Exception as e:
            logger.error(f"Failed to create {filename}: {e}")

    logger.info("Migration conversion completed!")
    logger.info(f"Created migration files in: {versions_dir}")

    # Provide usage instructions
    print("""
Migration Conversion Complete!

Next Steps:
1. Review the generated migration files in src/database/migrations/versions/
2. Test the new modular migration system:

   from database.connection import DatabaseConnection
   from database.modular_migrator import ModularDatabaseMigrator

   db = DatabaseConnection("test.db")
   migrator = ModularDatabaseMigrator(db)

   # Check status
   print(f"Current version: {migrator.get_current_version()}")
   print(f"Needs migration: {migrator.needs_migration()}")

   # Apply migrations
   if migrator.needs_migration():
       migrator.migrate()

3. Run the test suite: python -m pytest tests/migrations/
4. Update any remaining code to use ModularDatabaseMigrator
5. Refer to src/database/migrations/README.md for full documentation

The old migrations.py file is now a compatibility layer that uses the modular system.
""")


if __name__ == "__main__":
    main()
