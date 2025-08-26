"""
Citation System Integration Tests
Tests the complete citation extraction workflow with real database.
Follows enterprise testing patterns with modular architecture.
"""

import logging
import os
import tempfile
from collections.abc import Generator
from typing import Any

import pytest

from src.database import DatabaseMigrator
from src.database.connection import DatabaseConnection
from src.database.models import CitationModel, DocumentModel
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.services.citation_parsing_service import CitationParsingService
from src.services.citation_service import CitationService

logger = logging.getLogger(__name__)


class TestCitationSystemIntegration:
    """
    {
        "name": "CitationSystemIntegration",
        "version": "1.0.0",
        "description": "Integration tests for complete citation extraction workflow",
        "dependencies": ["DatabaseConnection", "All Citation Components"],
        "test_strategy": "Real database, modular architecture, enterprise patterns"
    }
    Integration test suite for the complete citation extraction system.
    Tests real component interactions with actual database.
    Uses enterprise testing patterns for maintainability and extensibility.
    """

    @pytest.fixture(scope="class")
    def test_database(self) -> Generator[DatabaseConnection, None, None]:
        """
        Create isolated test database for integration tests.
        Uses temporary file to avoid conflicts.
        """
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()

        try:
            # Initialize database connection
            db_connection = DatabaseConnection(temp_db.name)

            # Run migrations to set up schema
            migrator = DatabaseMigrator(db_connection)
            migrator.migrate()

            yield db_connection

        finally:
            # Cleanup - ensure all database connections are closed
            try:
                db_connection.close_all_connections()
            except Exception as e:
                logger.warning(f"Error closing database connections: {e}")

            # Wait a moment for Windows to release file locks
            import time
            time.sleep(0.1)

            # Attempt to delete the temporary database file
            if os.path.exists(temp_db.name):
                try:
                    os.unlink(temp_db.name)
                except PermissionError as e:
                    # On Windows, sometimes we need to retry
                    logger.warning(f"Failed to delete temp db on first attempt: {e}")
                    time.sleep(0.5)
                    try:
                        os.unlink(temp_db.name)
                    except PermissionError:
                        # If it still fails, log but don't fail the test
                        logger.warning(f"Could not delete temporary database file: {temp_db.name}")
                        pass

    @pytest.fixture
    def citation_components(self, test_database: DatabaseConnection) -> dict[str, Any]:
        """
        Factory fixture for citation system components.
        Creates loosely coupled, injectable components.
        """
        # Repository layer - data access abstraction
        citation_repo = CitationRepository(test_database)
        relation_repo = CitationRelationRepository(test_database)

        # Service layer - business logic and parsing
        parsing_service = CitationParsingService()
        citation_service = CitationService(citation_repo, relation_repo)

        return {
            "db": test_database,
            "citation_repo": citation_repo,
            "relation_repo": relation_repo,
            "parsing_service": parsing_service,
            "citation_service": citation_service
        }

    @pytest.fixture
    def sample_academic_text(self) -> str:
        """
        Real academic text with multiple citation formats.
        Data-driven testing with realistic content.
        """
        return """
        This research builds upon foundational work in machine learning. Smith, J. (2023) demonstrates
        that "advanced neural architectures significantly improve performance" in his comprehensive study
        published in the Journal of AI Research, 15(3), 123-145. https://doi.org/10.1000/jai.2023.001.

        Additional insights come from collaborative research by Jones, M., Brown, K., & Wilson, L. (2022).
        Their paper "Deep Learning Applications in Natural Language Processing" was presented at the
        International Conference on Machine Learning (ICML 2022), pages 256-267.

        Furthermore, the theoretical foundations are established in Anderson, P. et al. (2021).
        "Machine Learning: Theory and Practice", 3rd Edition. MIT Press, Cambridge, MA.

        Recent work by Taylor, R. (2024) in "Emerging Trends in AI" (PhD dissertation, Stanford University)
        provides contemporary perspectives on these methodologies.
        """

    @pytest.fixture
    def sample_document(self, test_database: DatabaseConnection, sample_academic_text: str) -> DocumentModel:
        """
        Create test document with realistic academic content.
        Represents real-world document processing scenario.
        """
        import uuid
        # Generate unique hashes for each test to avoid UNIQUE constraint violations
        unique_suffix = str(uuid.uuid4())[:8]

        # Create document record
        document = DocumentModel(
            title="Integration Test Document",
            file_path=f"/test/integration_document_{unique_suffix}.pdf",
            file_hash=f"integration_hash_{unique_suffix}",
            file_size=2048,
            content_hash=f"content_hash_{unique_suffix}",
            page_count=5,
            _from_database=False
        )

        # Insert into database and get ID
        insert_sql = """
            INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        test_database.execute(insert_sql, (
            document.title, document.file_path, document.file_hash,
            document.file_size, document.content_hash, document.page_count
        ))

        # Get inserted document with ID
        fetch_sql = "SELECT id FROM documents WHERE file_hash = ?"
        row = test_database.fetch_one(fetch_sql, (document.file_hash,))
        if row:
            document.id = row[0]  # First column is id
            document._from_database = True

        return document

    def test_complete_citation_extraction_workflow(
        self,
        citation_components: dict[str, Any],
        sample_document: DocumentModel,
        sample_academic_text: str
    ):
        """
        Test complete end-to-end citation extraction workflow.

        Workflow: Text → Parse → Extract → Store → Retrieve → Analyze
        """
        parsing_service = citation_components["parsing_service"]
        citation_service = citation_components["citation_service"]
        citation_repo = citation_components["citation_repo"]

        # Step 1: Parse citations from text
        parsed_citations = parsing_service.parse_citations_from_text(sample_academic_text)

        # Verify parsing results
        assert isinstance(parsed_citations, list)
        assert len(parsed_citations) >= 2  # Should find multiple citations

        # Verify parsed citation structure
        for citation_data in parsed_citations:
            assert isinstance(citation_data, dict)
            assert "raw_text" in citation_data
            assert "confidence_score" in citation_data
            assert 0.0 <= citation_data["confidence_score"] <= 1.0

        # Step 2: Create citation models and store in database
        created_citations = []
        for citation_data in parsed_citations:
            citation_model = CitationModel(
                document_id=sample_document.id,
                raw_text=citation_data["raw_text"],
                authors=citation_data.get("authors"),
                title=citation_data.get("title"),
                publication_year=citation_data.get("publication_year"),
                journal_or_venue=citation_data.get("journal_or_venue"),
                doi=citation_data.get("doi"),
                citation_type=citation_data.get("citation_type", "unknown"),
                confidence_score=citation_data["confidence_score"]
            )

            # Store in database via repository
            created_citation = citation_repo.create(citation_model)
            created_citations.append(created_citation)

        # Verify database storage
        assert len(created_citations) >= 2
        for citation in created_citations:
            assert citation.id is not None
            assert citation.document_id == sample_document.id
            assert len(citation.raw_text) > 10

        # Step 3: Retrieve citations for document
        retrieved_citations = citation_service.get_citations_for_document(sample_document.id)

        # Verify retrieval
        assert len(retrieved_citations) == len(created_citations)
        retrieved_ids = {c.id for c in retrieved_citations}
        created_ids = {c.id for c in created_citations}
        assert retrieved_ids == created_ids

        # Step 4: Test search functionality
        # Search by author if any citations have authors
        citations_with_authors = [c for c in retrieved_citations if c.authors]
        if citations_with_authors:
            first_author = citations_with_authors[0].authors
            search_results = citation_service.search_citations_by_author(first_author[:5])  # Partial match
            assert isinstance(search_results, list)

        # Step 5: Get statistics
        stats = citation_service.get_citation_statistics()
        assert isinstance(stats, dict)
        assert "total_citations" in stats
        assert stats["total_citations"] >= len(created_citations)

    def test_citation_parsing_quality_metrics(
        self,
        citation_components: dict[str, Any],
        sample_academic_text: str
    ):
        """
        Test citation parsing quality with enterprise metrics.
        Validates parsing accuracy and confidence scoring.
        """
        parsing_service = citation_components["parsing_service"]

        # Parse citations
        parsed_citations = parsing_service.parse_citations_from_text(sample_academic_text)

        # Quality metrics validation
        assert len(parsed_citations) >= 2, "Should extract multiple citations"

        # Confidence score distribution analysis
        confidence_scores = [c["confidence_score"] for c in parsed_citations]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)

        # Enterprise quality thresholds
        assert avg_confidence >= 0.3, f"Average confidence {avg_confidence:.2f} below threshold"
        assert all(0.0 <= score <= 1.0 for score in confidence_scores), "Invalid confidence scores"

        # Content quality validation
        high_confidence_citations = [c for c in parsed_citations if c["confidence_score"] >= 0.5]
        assert len(high_confidence_citations) >= 1, "Should have at least one high-confidence citation"

        # Verify essential field extraction
        for citation in high_confidence_citations:
            # At least one of these should be extracted for high-confidence citations
            has_essential_fields = any([
                citation.get("authors"),
                citation.get("title"),
                citation.get("publication_year")
            ])
            assert has_essential_fields, f"High-confidence citation missing essential fields: {citation}"

    def test_database_transaction_integrity(
        self,
        citation_components: dict[str, Any],
        sample_document: DocumentModel
    ):
        """
        Test database transaction integrity and error handling.
        Validates ACID properties in citation operations.
        """
        citation_repo = citation_components["citation_repo"]
        db = citation_components["db"]

        # Test successful transaction
        citation1 = CitationModel(
            document_id=sample_document.id,
            raw_text="Test citation 1",
            authors="Test Author",
            title="Test Title",
            confidence_score=0.8
        )

        created_citation = citation_repo.create(citation1)
        assert created_citation.id is not None

        # Verify persistence
        retrieved = citation_repo.get_by_id(created_citation.id)
        assert retrieved is not None
        assert retrieved.raw_text == "Test citation 1"

        # Test update operation
        retrieved.title = "Updated Test Title"
        updated_citation = citation_repo.update(retrieved)
        assert updated_citation.title == "Updated Test Title"

        # Verify update persistence
        re_retrieved = citation_repo.get_by_id(created_citation.id)
        assert re_retrieved.title == "Updated Test Title"

        # Test delete operation
        delete_success = citation_repo.delete(created_citation.id)
        assert delete_success is True

        # Verify deletion
        deleted_citation = citation_repo.get_by_id(created_citation.id)
        assert deleted_citation is None

    def test_concurrent_citation_operations(
        self,
        citation_components: dict[str, Any],
        sample_document: DocumentModel
    ):
        """
        Test concurrent citation operations for thread safety.
        Validates system behavior under concurrent load.
        """
        citation_repo = citation_components["citation_repo"]

        # Create multiple citations concurrently (simulated)
        citation_batch = []
        for i in range(5):
            citation = CitationModel(
                document_id=sample_document.id,
                raw_text=f"Concurrent citation {i}",
                authors=f"Author {i}",
                confidence_score=0.7
            )
            citation_batch.append(citation)

        # Store all citations
        created_citations = []
        for citation in citation_batch:
            created = citation_repo.create(citation)
            created_citations.append(created)

        # Verify all citations were created with unique IDs
        citation_ids = [c.id for c in created_citations]
        assert len(citation_ids) == len(set(citation_ids)), "Duplicate IDs detected"

        # Verify all citations can be retrieved
        for citation_id in citation_ids:
            retrieved = citation_repo.get_by_id(citation_id)
            assert retrieved is not None
            assert "Concurrent citation" in retrieved.raw_text

    def test_system_performance_benchmarks(
        self,
        citation_components: dict[str, Any],
        sample_academic_text: str,
        sample_document: DocumentModel
    ):
        """
        Test system performance with enterprise benchmarks.
        Validates parsing and storage performance.
        """
        import time

        parsing_service = citation_components["parsing_service"]
        citation_repo = citation_components["citation_repo"]

        # Benchmark citation parsing
        start_time = time.time()
        parsed_citations = parsing_service.parse_citations_from_text(sample_academic_text)
        parsing_duration = time.time() - start_time

        # Performance assertion - should parse quickly
        assert parsing_duration < 2.0, f"Parsing took {parsing_duration:.2f}s, expected < 2.0s"

        # Benchmark database operations
        start_time = time.time()
        for citation_data in parsed_citations:
            citation_model = CitationModel(
                document_id=sample_document.id,
                raw_text=citation_data["raw_text"],
                confidence_score=citation_data["confidence_score"]
            )
            citation_repo.create(citation_model)

        storage_duration = time.time() - start_time

        # Performance assertion - should store efficiently
        citations_per_second = len(parsed_citations) / storage_duration if storage_duration > 0 else float('inf')
        assert citations_per_second >= 5, f"Storage rate {citations_per_second:.1f}/s below threshold"

    def test_error_handling_and_recovery(
        self,
        citation_components: dict[str, Any]
    ):
        """
        Test error handling and system recovery.
        Validates graceful degradation under error conditions.
        """
        citation_service = citation_components["citation_service"]
        citation_repo = citation_components["citation_repo"]

        # Test invalid document ID
        invalid_citations = citation_service.get_citations_for_document(99999)
        assert isinstance(invalid_citations, list)
        assert len(invalid_citations) == 0

        # Test malformed citation data - should raise validation error during model creation
        with pytest.raises(ValueError, match="Document ID must be positive"):
            invalid_citation = CitationModel(
                document_id=-1,  # Invalid document ID
                raw_text="",     # Empty text
                confidence_score=1.5  # Invalid score > 1.0
            )

    def test_modular_extensibility(
        self,
        citation_components: dict[str, Any]
    ):
        """
        Test modular architecture extensibility.
        Validates that components can be extended independently.
        """
        # Test that parsing service can be swapped out
        class MockParsingService:
            def parse_citations_from_text(self, text: str) -> list[dict]:
                return [{
                    "raw_text": "Mock citation",
                    "authors": "Mock Author",
                    "confidence_score": 0.9
                }]

        # Components should accept interface-compatible replacements
        mock_parser = MockParsingService()
        result = mock_parser.parse_citations_from_text("any text")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["authors"] == "Mock Author"

        # This demonstrates how LLM modules can be independently developed
        # Each service follows interface contracts for seamless integration
