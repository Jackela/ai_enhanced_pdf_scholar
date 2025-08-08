"""
Migration 003: Add Citation Tables

Creates citation and citation_relations tables for advanced citation
extraction and analysis features.
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


class AddCitationTablesMigration(BaseMigration):
    """
    Creates citation management tables for academic paper analysis.
    
    This migration adds:
    - citations table for extracted citation data
    - citation_relations table for citation network analysis
    - Performance indexes for citation queries
    """
    
    @property
    def version(self) -> int:
        return 3
        
    @property
    def description(self) -> str:
        return "Add citation and citation_relations tables for advanced citation analysis"
        
    @property
    def dependencies(self) -> list[int]:
        return [1]  # Requires documents table from initial schema
        
    @property
    def rollback_supported(self) -> bool:
        return True
        
    def up(self) -> None:
        """Apply the citation tables migration."""
        logger.info("Creating citation analysis tables")
        
        # Create citations table
        self._create_citations_table()
        
        # Create citation_relations table
        self._create_citation_relations_table()
        
        # Create performance indexes
        self._create_citation_indexes()
        
        logger.info("Citation tables migration completed successfully")
        
    def down(self) -> None:
        """Rollback the citation tables migration."""
        logger.info("Rolling back citation tables migration")
        
        # Drop tables in reverse order (respecting foreign keys)
        tables_to_drop = ["citation_relations", "citations"]
        
        for table in tables_to_drop:
            try:
                self.execute_sql(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")
                
        logger.info("Citation tables rollback completed")
        
    def _create_citations_table(self) -> None:
        """Create the citations table."""
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
        self.execute_sql(citations_sql)
        logger.info("Created citations table")
        
    def _create_citation_relations_table(self) -> None:
        """Create the citation_relations table."""
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
        self.execute_sql(citation_relations_sql)
        logger.info("Created citation_relations table")
        
    def _create_citation_indexes(self) -> None:
        """Create indexes for citation table performance."""
        citation_indexes = [
            "CREATE INDEX idx_citations_document ON citations(document_id)",
            "CREATE INDEX idx_citations_authors ON citations(authors)",
            "CREATE INDEX idx_citations_title ON citations(title)",
            "CREATE INDEX idx_citations_year ON citations(publication_year)",
            "CREATE INDEX idx_citations_doi ON citations(doi)",
            "CREATE INDEX idx_citations_type ON citations(citation_type)",
            "CREATE INDEX idx_citations_confidence ON citations(confidence_score)",
            "CREATE INDEX idx_citation_relations_source ON citation_relations(source_document_id)",
            "CREATE INDEX idx_citation_relations_target ON citation_relations(target_document_id)",
            "CREATE INDEX idx_citation_relations_type ON citation_relations(relation_type)",
        ]
        
        for index_sql in citation_indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not create citation index: {e}")
                
        logger.info("Created citation table indexes")
        
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
            
        # Check if citation tables already exist
        existing_tables = []
        try:
            results = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('citations', 'citation_relations')"
            )
            existing_tables = [row["name"] for row in results]
        except Exception as e:
            logger.warning(f"Could not check existing tables: {e}")
            
        if existing_tables:
            logger.warning(f"Some citation tables already exist: {existing_tables}")
            return False  # Skip if already applied
            
        return True
        
    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        required_tables = ["citations", "citation_relations"]
        
        try:
            for table in required_tables:
                result = self.db.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if not result:
                    logger.error(f"Required table {table} was not created")
                    return False
                    
            # Check that foreign key constraints are properly set up
            # We can do this by checking the schema
            citations_schema = self.db.fetch_one(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='citations'"
            )
            
            if citations_schema and "FOREIGN KEY" not in citations_schema["sql"]:
                logger.warning("Citations table may not have proper foreign key constraints")
                
            logger.info("Post-migration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False