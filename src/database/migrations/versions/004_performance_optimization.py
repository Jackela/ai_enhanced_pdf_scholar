"""
Migration 004: Performance Optimization

Adds comprehensive indexing strategy for high-performance queries including:
- Strategic indexes for documents, citations, and vector_indexes tables
- Composite indexes for common query patterns
- Partial indexes for filtered queries
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
