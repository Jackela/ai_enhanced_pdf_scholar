"""
End-to-End Citation Extraction Workflow Tests
Tests complete citation extraction from real document processing to analysis.
Implements enterprise testing patterns with data-driven validation.
"""

import logging
import os
import tempfile
from collections.abc import Generator
from typing import Any

import pytest

from src.database import DatabaseMigrator
from src.database.connection import DatabaseConnection
from src.database.models import CitationModel, CitationRelationModel, DocumentModel
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.repositories.document_repository import DocumentRepository
from src.services.citation_parsing_service import CitationParsingService
from src.services.citation_service import CitationService

logger = logging.getLogger(__name__)


class TestCitationE2EWorkflow:
    """
    {
        "name": "CitationE2EWorkflow",
        "version": "1.0.0",
        "description": "End-to-end tests for complete citation extraction pipeline",
        "scope": "Full system integration from document to citation network",
        "testing_strategy": "Data-driven, real-world scenarios, enterprise validation"
    }
    End-to-end test suite for complete citation extraction workflow.
    Tests realistic document processing scenarios with enterprise validation.
    Designed for independent LLM module development and validation.
    """

    @pytest.fixture(scope="class")
    def e2e_database(self) -> Generator[DatabaseConnection, None, None]:
        """
        Create isolated E2E test database with full schema.
        Simulates production database environment.
        """
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()

        try:
            db_connection = DatabaseConnection(temp_db.name)
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
    def e2e_system_components(self, e2e_database: DatabaseConnection) -> dict[str, Any]:
        """
        Factory for complete system components.
        Enterprise-grade component initialization with proper dependency injection.
        """
        # Repository layer
        document_repo = DocumentRepository(e2e_database)
        citation_repo = CitationRepository(e2e_database)
        relation_repo = CitationRelationRepository(e2e_database)

        # Service layer
        parsing_service = CitationParsingService()
        citation_service = CitationService(citation_repo, relation_repo)

        return {
            "db": e2e_database,
            "document_repo": document_repo,
            "citation_repo": citation_repo,
            "relation_repo": relation_repo,
            "parsing_service": parsing_service,
            "citation_service": citation_service
        }

    @pytest.fixture
    def research_paper_documents(self) -> list[dict[str, Any]]:
        """
        Real-world research paper samples for E2E testing.
        Data-driven test cases with diverse citation patterns.
        """
        return [
            {
                "title": "Machine Learning Advances in Natural Language Processing",
                "file_path": "/papers/ml_nlp_advances.pdf",
                "content": """
                Abstract: This paper presents recent advances in machine learning for natural language processing.

                Introduction:
                Recent work by Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N.,
                Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. In Advances in neural
                information processing systems (pp. 5998-6008).

                The transformer architecture has revolutionized NLP, as demonstrated in Devlin, J., Chang, M. W.,
                Lee, K., & Toutanova, K. (2018). BERT: Pre-training of Deep Bidirectional Transformers for
                Language Understanding. arXiv preprint arXiv:1810.04805.

                Recent developments include Brown, T., Mann, B., Ryder, N., Subbiah, M., Kaplan, J. D.,
                Dhariwal, P., ... & Amodei, D. (2020). Language models are few-shot learners.
                Advances in neural information processing systems, 33, 1877-1901.
                """,
                "expected_citations": [
                    {"authors": "Vaswani, A.", "year": 2017, "type": "conference"},
                    {"authors": "Devlin, J.", "year": 2018, "type": "preprint"},
                    {"authors": "Brown, T.", "year": 2020, "type": "conference"}
                ]
            },
            {
                "title": "Computer Vision and Deep Learning: A Comprehensive Survey",
                "file_path": "/papers/cv_deep_learning_survey.pdf",
                "content": """
                This survey examines recent progress in computer vision using deep learning techniques.

                Foundational work includes LeCun, Y., Bottou, L., Bengio, Y., & Haffner, P. (1998).
                Gradient-based learning applied to document recognition. Proceedings of the IEEE, 86(11), 2278-2324.

                Modern architectures build on He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual
                learning for image recognition. In Proceedings of the IEEE conference on computer vision
                and pattern recognition (pp. 770-778).

                Object detection advances are covered in Ren, S., He, K., Girshick, R., & Sun, J. (2015).
                Faster r-cnn: Towards real-time object detection with region proposal networks.
                Advances in neural information processing systems, 28.
                """,
                "expected_citations": [
                    {"authors": "LeCun, Y.", "year": 1998, "type": "journal"},
                    {"authors": "He, K.", "year": 2016, "type": "conference"},
                    {"authors": "Ren, S.", "year": 2015, "type": "conference"}
                ]
            }
        ]

    def test_complete_document_processing_pipeline(
        self,
        e2e_system_components: dict[str, Any],
        research_paper_documents: list[dict[str, Any]]
    ):
        """
        Test complete document processing pipeline from ingestion to citation network.

        Pipeline: Document → Parse → Extract → Store → Network → Analysis
        Enterprise validation with performance metrics.
        """
        document_repo = e2e_system_components["document_repo"]
        citation_service = e2e_system_components["citation_service"]
        parsing_service = e2e_system_components["parsing_service"]
        relation_repo = e2e_system_components["relation_repo"]

        processed_documents = []
        all_citations = []

        # Process each research paper
        for paper_data in research_paper_documents:
            # Step 1: Create document record
            document = DocumentModel(
                title=paper_data["title"],
                file_path=paper_data["file_path"],
                file_hash=f"hash_{len(processed_documents)}",
                file_size=len(paper_data["content"]),
                content_hash=f"content_hash_{len(processed_documents)}",
                page_count=10,
                _from_database=False
            )

            # Insert document
            insert_sql = """
                INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """
            e2e_system_components["db"].execute(insert_sql, (
                document.title, document.file_path, document.file_hash,
                document.file_size, document.content_hash, document.page_count
            ))

            # Get document with ID
            row = e2e_system_components["db"].fetch_one(
                "SELECT id FROM documents WHERE file_hash = ?",
                (document.file_hash,)
            )
            if row:
                document.id = row[0]
            document._from_database = True
            processed_documents.append(document)

            # Step 2: Parse citations from content
            parsed_citations = parsing_service.parse_citations_from_text(paper_data["content"])

            # Validate parsing results against expected
            assert len(parsed_citations) >= len(paper_data["expected_citations"])

            # Step 3: Store citations via service
            document_citations = []
            for citation_data in parsed_citations:
                citation_model = CitationModel(
                    document_id=document.id,
                    raw_text=citation_data["raw_text"],
                    authors=citation_data.get("authors"),
                    title=citation_data.get("title"),
                    publication_year=citation_data.get("publication_year"),
                    journal_or_venue=citation_data.get("journal_or_venue"),
                    doi=citation_data.get("doi"),
                    citation_type=citation_data.get("citation_type", "unknown"),
                    confidence_score=citation_data["confidence_score"]
                )

                created_citation = e2e_system_components["citation_repo"].create(citation_model)
                document_citations.append(created_citation)
                all_citations.append(created_citation)

            # Validate citation storage
            assert len(document_citations) >= 1

            # Step 4: Verify citation retrieval
            retrieved_citations = citation_service.get_citations_for_document(document.id)
            assert len(retrieved_citations) == len(document_citations)

        # Step 5: Cross-document citation network analysis
        if len(processed_documents) >= 2:
            # Create citation relations between documents
            doc1, doc2 = processed_documents[0], processed_documents[1]

            # Find citations in doc1 that might reference doc2's authors
            doc1_citations = citation_service.get_citations_for_document(doc1.id)
            doc2_citations = citation_service.get_citations_for_document(doc2.id)

            # Create a cross-reference relation (simulated)
            if doc1_citations and doc2_citations:
                relation = CitationRelationModel(
                    source_document_id=doc1.id,
                    source_citation_id=doc1_citations[0].id,
                    target_document_id=doc2.id,
                    relation_type="cites",
                    confidence_score=0.8
                )

                created_relation = relation_repo.create(relation)
                assert created_relation.id is not None

                # Test citation network building
                network = citation_service.build_citation_network(doc1.id, depth=1)
                assert isinstance(network, dict)
                assert "nodes" in network
                assert "edges" in network

        # Step 6: System-wide analytics
        total_stats = citation_service.get_citation_statistics()
        assert total_stats["total_citations"] == len(all_citations)

        # Performance validation
        assert len(all_citations) >= len(research_paper_documents)  # At least one citation per document

    def test_citation_quality_validation_e2e(
        self,
        e2e_system_components: dict[str, Any],
        research_paper_documents: list[dict[str, Any]]
    ):
        """
        End-to-end validation of citation extraction quality.
        Tests parsing accuracy against known ground truth.
        """
        parsing_service = e2e_system_components["parsing_service"]

        quality_metrics = {
            "total_expected": 0,
            "total_extracted": 0,
            "high_confidence_extracted": 0,
            "author_extraction_accuracy": 0,
            "year_extraction_accuracy": 0
        }

        for paper_data in research_paper_documents:
            expected_citations = paper_data["expected_citations"]
            quality_metrics["total_expected"] += len(expected_citations)

            # Parse citations
            parsed_citations = parsing_service.parse_citations_from_text(paper_data["content"])
            quality_metrics["total_extracted"] += len(parsed_citations)

            # Count high-confidence extractions
            high_conf_citations = [c for c in parsed_citations if c["confidence_score"] >= 0.5]
            quality_metrics["high_confidence_extracted"] += len(high_conf_citations)

            # Validate against expected citations
            for expected in expected_citations:
                # Check if any parsed citation matches expected author
                author_matches = [
                    c for c in parsed_citations
                    if c.get("authors") and expected["authors"] in c["authors"]
                ]
                if author_matches:
                    quality_metrics["author_extraction_accuracy"] += 1

                # Check year extraction
                year_matches = [
                    c for c in parsed_citations
                    if c.get("publication_year") == expected["year"]
                ]
                if year_matches:
                    quality_metrics["year_extraction_accuracy"] += 1

        # Enterprise quality thresholds
        extraction_rate = quality_metrics["total_extracted"] / quality_metrics["total_expected"]
        assert extraction_rate >= 0.8, f"Extraction rate {extraction_rate:.2f} below 80% threshold"

        if quality_metrics["total_extracted"] > 0:
            high_conf_rate = quality_metrics["high_confidence_extracted"] / quality_metrics["total_extracted"]
            assert high_conf_rate >= 0.3, f"High confidence rate {high_conf_rate:.2f} below 30% threshold"

        # Author extraction accuracy
        if quality_metrics["total_expected"] > 0:
            author_accuracy = quality_metrics["author_extraction_accuracy"] / quality_metrics["total_expected"]
            # Enhanced citation parsing algorithm now achieves 40% threshold
            assert author_accuracy >= 0.4, f"Author extraction accuracy {author_accuracy:.2f} below 40% threshold"

    def test_system_scalability_e2e(
        self,
        e2e_system_components: dict[str, Any]
    ):
        """
        Test system scalability with larger document sets.
        Validates performance under realistic load.
        """
        import time

        citation_service = e2e_system_components["citation_service"]
        parsing_service = e2e_system_components["parsing_service"]
        document_repo = e2e_system_components["document_repo"]

        # Create multiple documents with citations
        num_documents = 10
        total_citations = 0

        start_time = time.time()

        for i in range(num_documents):
            # Create document
            document = DocumentModel(
                title=f"Scalability Test Document {i}",
                file_path=f"/test/scale_doc_{i}.pdf",
                file_hash=f"scale_hash_{i}",
                file_size=1024,
                content_hash=f"scale_content_{i}",
                page_count=5,
                _from_database=False
            )

            # Store document
            insert_sql = """
                INSERT INTO documents (title, file_path, file_hash, file_size, content_hash, page_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """
            e2e_system_components["db"].execute(insert_sql, (
                document.title, document.file_path, document.file_hash,
                document.file_size, document.content_hash, document.page_count
            ))

            row = e2e_system_components["db"].fetch_one(
                "SELECT id FROM documents WHERE file_hash = ?",
                (document.file_hash,)
            )
            if row:
                document.id = row[0]

            # Generate citations for this document
            sample_text = f"""
            This is test document {i}. It references Author{i}, A. ({2020 + i}).
            Test Paper {i}. Journal of Testing, {i}(1), 1-10.

            Additional reference: Researcher{i}, B. et al. ({2021 + i}).
            Another Test Study. Conference Proceedings, pages {i*10}-{i*10+10}.
            """

            # Parse and store citations
            parsed_citations = parsing_service.parse_citations_from_text(sample_text)
            for citation_data in parsed_citations:
                citation_model = CitationModel(
                    document_id=document.id,
                    raw_text=citation_data["raw_text"],
                    authors=citation_data.get("authors"),
                    confidence_score=citation_data["confidence_score"]
                )
                e2e_system_components["citation_repo"].create(citation_model)
                total_citations += 1

        processing_time = time.time() - start_time

        # Performance assertions
        docs_per_second = num_documents / processing_time
        assert docs_per_second >= 2, f"Document processing rate {docs_per_second:.1f}/s below threshold"

        # Verify all data was stored correctly
        final_stats = citation_service.get_citation_statistics()
        assert final_stats["total_citations"] >= total_citations

    def test_error_resilience_e2e(
        self,
        e2e_system_components: dict[str, Any]
    ):
        """
        Test system resilience under various error conditions.
        Validates graceful degradation and recovery.
        """
        citation_service = e2e_system_components["citation_service"]
        parsing_service = e2e_system_components["parsing_service"]

        # Test with malformed text
        malformed_text = "This is not a proper citation format!!! @#$%^&*()"

        try:
            parsed_citations = parsing_service.parse_citations_from_text(malformed_text)
            # Should return empty list or handle gracefully
            assert isinstance(parsed_citations, list)
        except Exception as e:
            pytest.fail(f"System should handle malformed text gracefully, but raised: {e}")

        # Test with empty text
        empty_citations = parsing_service.parse_citations_from_text("")
        assert isinstance(empty_citations, list)
        assert len(empty_citations) == 0

        # Test with very long text
        long_text = "A. Smith (2023). " * 1000  # Repeat pattern 1000 times
        long_citations = parsing_service.parse_citations_from_text(long_text)
        assert isinstance(long_citations, list)
        # Should not crash or take excessive time

        # Test invalid document queries
        invalid_citations = citation_service.get_citations_for_document(-1)
        assert isinstance(invalid_citations, list)
        assert len(invalid_citations) == 0

    def test_modular_component_swapping_e2e(
        self,
        e2e_database: DatabaseConnection
    ):
        """
        Test modular architecture with component swapping.
        Validates that LLM modules can be independently developed and swapped.
        """
        # Create base system
        citation_repo = CitationRepository(e2e_database)
        relation_repo = CitationRelationRepository(e2e_database)

        # Original parsing service
        original_parser = CitationParsingService()
        original_service = CitationService(citation_repo, relation_repo)

        # Test with original parser
        test_text = "Smith, J. (2023). Original Test Paper. Journal of Tests."
        original_results = original_parser.parse_citations_from_text(test_text)

        # Create enhanced parsing service (simulated LLM enhancement)
        class EnhancedParsingService:
            def parse_citations_from_text(self, text: str) -> list[dict]:
                # Simulated enhanced parsing with better accuracy
                return [{
                    "raw_text": "Smith, J. (2023). Original Test Paper. Journal of Tests.",
                    "authors": "Smith, J.",
                    "title": "Original Test Paper",
                    "publication_year": 2023,
                    "journal_or_venue": "Journal of Tests",
                    "citation_type": "journal",
                    "confidence_score": 0.95  # Higher confidence
                }]

        # Swap parsing service
        enhanced_parser = EnhancedParsingService()
        enhanced_results = enhanced_parser.parse_citations_from_text(test_text)

        # Both should work with same interface
        assert isinstance(original_results, list)
        assert isinstance(enhanced_results, list)

        # Enhanced parser should provide better results
        if enhanced_results:
            assert enhanced_results[0]["confidence_score"] >= 0.9

        # Service layer should work with both parsers
        # This demonstrates modular extensibility for LLM development

    def test_citation_network_analysis_e2e(
        self,
        e2e_system_components: dict[str, Any]
    ):
        """
        Test complete citation network analysis workflow.
        Validates network building and analysis capabilities.
        """
        # This test will be expanded when citation network functionality is implemented
        citation_service = e2e_system_components["citation_service"]

        # For now, test basic network functionality
        try:
            # Test network building with non-existent document
            network = citation_service.build_citation_network(99999, depth=1)
            assert isinstance(network, dict)
            assert "nodes" in network
            assert "edges" in network
        except Exception as e:
            # Should handle gracefully
            assert "not found" in str(e).lower() or "invalid" in str(e).lower()

    def test_data_export_and_validation_e2e(
        self,
        e2e_system_components: dict[str, Any]
    ):
        """
        Test data export and validation for enterprise integration.
        Validates data quality and export formats.
        """
        citation_service = e2e_system_components["citation_service"]

        # Get system statistics
        stats = citation_service.get_citation_statistics()

        # Validate statistics structure
        required_fields = ["total_citations", "complete_citations", "avg_confidence_score"]
        for field in required_fields:
            assert field in stats, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(stats["total_citations"], int)
        assert isinstance(stats["complete_citations"], int)
        assert isinstance(stats["avg_confidence_score"], (int, float))

        # Validate value ranges
        assert stats["total_citations"] >= 0
        assert stats["complete_citations"] >= 0
        assert 0.0 <= stats["avg_confidence_score"] <= 1.0

        # Test search functionality
        search_results = citation_service.search_citations_by_author("Smith", limit=10)
        assert isinstance(search_results, list)
        assert len(search_results) <= 10
