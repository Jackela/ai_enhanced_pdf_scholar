"""
Migration 005: Advanced Performance Analysis

Adds specialized indexes, query performance monitoring, and database analytics:
- Covering indexes for complex queries
- Partial indexes for filtered queries
- Performance monitoring tables
- Database performance baselines
"""

import logging
import time

try:
    from ..base import BaseMigration
except ImportError:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).parent.parent))
    from base import BaseMigration

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
            "query_performance_log",
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
            "idx_documents_listing_cover",
            "idx_documents_search_cover",
            "idx_documents_recent_cover",
            "idx_citations_analysis_cover",
            "idx_vector_management_cover",
            # Partial indexes
            "idx_citations_high_confidence",
            "idx_documents_large_files",
            "idx_documents_recent_hot",
            "idx_documents_content_dedup",
            "idx_documents_multi_page",
            # Expression indexes
            "idx_documents_created_date",
            "idx_documents_size_category",
            "idx_citation_density_calc",
            # FTS support indexes
            "idx_documents_title_trigram",
            "idx_citations_author_search",
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

            # Sample query performance baselines
            sample_queries = [
                ("SELECT COUNT(*) FROM documents", "simple_count_documents"),
                (
                    "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10",
                    "recent_documents_query",
                ),
            ]

            for query, query_name in sample_queries:
                try:
                    start_time = time.time()
                    self.db.fetch_all(query)
                    execution_time = (time.time() - start_time) * 1000
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
