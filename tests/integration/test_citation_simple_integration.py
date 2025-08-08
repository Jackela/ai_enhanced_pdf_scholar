"""
Simplified Citation Integration Tests
Core integration testing focused on essential workflows.
"""

import pytest
import tempfile
import os
from typing import Any

from src.database.connection import DatabaseConnection
from src.database import DatabaseMigrator
from src.database.models import DocumentModel, CitationModel
from src.repositories.citation_repository import CitationRepository
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.services.citation_service import CitationService
from src.services.citation_parsing_service import CitationParsingService


class TestSimpleCitationIntegration:
    """Simplified integration tests for citation system."""

    @pytest.fixture(scope="function")
    def test_db(self):
        """Create temporary test database."""
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        try:
            db_connection = DatabaseConnection(temp_db.name)
            migrator = DatabaseMigrator(db_connection)
            migrator.migrate()
            yield db_connection
        finally:
            # Cleanup with better error handling
            try:
                if os.path.exists(temp_db.name):
                    os.unlink(temp_db.name)
            except PermissionError:
                pass  # File in use, will be cleaned up later

    def test_citation_parsing_and_storage(self, test_db: DatabaseConnection):
        """Test basic citation parsing and storage workflow."""
        # Initialize components
        citation_repo = CitationRepository(test_db)
        parsing_service = CitationParsingService()
        
        # First create a valid document to satisfy foreign key constraint
        doc_sql = """
            INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        test_db.execute(doc_sql, (
            "Test Document", "/test/doc.pdf", "test_hash", 1024, "content_hash", 5
        ))
        
        # Get the document ID
        doc_row = test_db.fetch_one("SELECT id FROM documents WHERE file_hash = ?", ("test_hash",))
        document_id = doc_row[0]
        
        # Test data
        academic_text = """
        Smith, J. (2023). Machine Learning Fundamentals. Journal of AI, 15(3), 123-145.
        Jones, M. et al. (2022). Deep Learning Applications. Conference Proceedings.
        """
        
        # Parse citations
        parsed_citations = parsing_service.parse_citations_from_text(academic_text)
        
        # Validate parsing
        assert isinstance(parsed_citations, list)
        assert len(parsed_citations) >= 1
        
        # Create and store citations
        for citation_data in parsed_citations:
            citation_model = CitationModel(
                document_id=document_id,  # Use valid document ID
                raw_text=citation_data["raw_text"],
                authors=citation_data.get("authors"),
                title=citation_data.get("title"),
                publication_year=citation_data.get("publication_year"),
                confidence_score=citation_data["confidence_score"]
            )
            
            # Store citation
            created_citation = citation_repo.create(citation_model)
            
            # Validate storage
            assert created_citation.id is not None
            assert created_citation.raw_text == citation_data["raw_text"]
            assert created_citation.confidence_score > 0.0

    def test_citation_service_integration(self, test_db: DatabaseConnection):
        """Test citation service with real components."""
        # Initialize all components
        citation_repo = CitationRepository(test_db)
        relation_repo = CitationRelationRepository(test_db)
        citation_service = CitationService(citation_repo, relation_repo)
        
        # Test statistics (should work even with empty database)
        stats = citation_service.get_citation_statistics()
        assert isinstance(stats, dict)
        assert "total_citations" in stats
        assert stats["total_citations"] >= 0
        
        # Test search (should return empty list for non-existent author)
        search_results = citation_service.search_citations_by_author("NonExistent")
        assert isinstance(search_results, list)
        assert len(search_results) == 0
        
        # Test citation retrieval for non-existent document
        citations = citation_service.get_citations_for_document(99999)
        assert isinstance(citations, list)
        assert len(citations) == 0

    def test_parsing_quality_validation(self, test_db: DatabaseConnection):
        """Test parsing quality with realistic academic text."""
        parsing_service = CitationParsingService()
        
        # Real academic text with clear citations
        test_text = """
        The transformer architecture (Vaswani, A. et al. (2017). Attention is all you need. 
        In Advances in neural information processing systems.) has revolutionized NLP.
        
        Building on this work, Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2018) 
        introduced BERT in their paper "BERT: Pre-training of Deep Bidirectional Transformers 
        for Language Understanding" published as arXiv preprint arXiv:1810.04805.
        """
        
        parsed_citations = parsing_service.parse_citations_from_text(test_text)
        
        # Quality assertions
        assert len(parsed_citations) >= 1, "Should extract at least one citation"
        
        # Check confidence scores
        high_confidence_count = sum(1 for c in parsed_citations if c["confidence_score"] >= 0.5)
        assert high_confidence_count >= 1, "Should have at least one high-confidence citation"
        
        # Check essential fields extraction
        for citation in parsed_citations:
            assert len(citation["raw_text"]) > 10, "Raw text should be substantial"
            assert 0.0 <= citation["confidence_score"] <= 1.0, "Invalid confidence score"

    def test_error_handling_integration(self, test_db: DatabaseConnection):
        """Test error handling across integrated components."""
        citation_service = CitationService(
            CitationRepository(test_db),
            CitationRelationRepository(test_db)
        )
        parsing_service = CitationParsingService()
        
        # Test with malformed input
        try:
            malformed_result = parsing_service.parse_citations_from_text("Invalid text @@##$$")
            assert isinstance(malformed_result, list)  # Should handle gracefully
        except Exception as e:
            pytest.fail(f"Should handle malformed text gracefully: {e}")
        
        # Test with empty input
        empty_result = parsing_service.parse_citations_from_text("")
        assert isinstance(empty_result, list)
        assert len(empty_result) == 0
        
        # Test service error handling
        invalid_citations = citation_service.get_citations_for_document(-1)
        assert isinstance(invalid_citations, list)
        assert len(invalid_citations) == 0

    def test_component_modularity(self, test_db: DatabaseConnection):
        """Test that components can be swapped independently."""
        # Create a valid document first
        doc_sql = """
            INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        test_db.execute(doc_sql, (
            "Modularity Test Document", "/test/mod.pdf", "mod_hash", 512, "mod_content", 3
        ))
        
        # Get the document ID
        doc_row = test_db.fetch_one("SELECT id FROM documents WHERE file_hash = ?", ("mod_hash",))
        document_id = doc_row[0]
        
        # Original components
        original_repo = CitationRepository(test_db)
        original_service = CitationService(original_repo, CitationRelationRepository(test_db))
        
        # Test component interface compliance
        test_citation = CitationModel(
            document_id=document_id,
            raw_text="Test citation for modularity",
            confidence_score=0.8
        )
        
        # Repository should handle CRUD operations
        created = original_repo.create(test_citation)
        assert created.id is not None
        
        retrieved = original_repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.raw_text == test_citation.raw_text
        
        # Service should work with repository
        search_results = original_service.search_citations_by_author("Test")
        assert isinstance(search_results, list)
        
        # This demonstrates modular architecture for LLM development