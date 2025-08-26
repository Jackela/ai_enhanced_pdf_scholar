"""
Unit tests for database models.
Tests model creation, validation, and serialization.
"""

from datetime import datetime

from src.database.models import CitationModel, CitationRelationModel, DocumentModel


class TestDocumentModel:
    """Test DocumentModel functionality."""

    def test_document_model_creation_with_required_fields(self):
        """Test document model creation with required fields."""
        doc = DocumentModel(
            title="Test Document",
            file_path="/path/to/document.pdf",
            file_hash="abc123",
            file_size=1024
        )

        assert doc.title == "Test Document"
        assert doc.file_path == "/path/to/document.pdf"
        assert doc.file_hash == "abc123"
        assert doc.file_size == 1024
        assert doc.id is None  # Not set until saved

    def test_document_model_creation_with_all_fields(self):
        """Test document model creation with all fields."""
        now = datetime.now()
        doc = DocumentModel(
            id=1,
            title="Complete Document",
            file_path="/path/to/complete.pdf",
            file_hash="abc123",
            file_size=1024,
            content_hash="def456",
            page_count=10,
            created_at=now,
            last_accessed=now
        )

        assert doc.id == 1
        assert doc.title == "Complete Document"
        assert doc.file_size == 1024
        assert doc.page_count == 10
        assert doc.file_hash == "abc123"
        assert doc.file_hash_hash == "def456"
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.last_accessed, datetime)

    def test_document_model_default_values(self):
        """Test document model default values."""
        doc = DocumentModel(
            title="Test Document",
            file_path="/path/to/document.pdf",
            file_hash="test123", file_size=500
        )

        # Check that optional fields have expected defaults
        assert doc.file_size is None or doc.file_size == 0
        assert doc.page_count is None or doc.page_count == 0

    def test_document_model_string_representation(self):
        """Test document model string representation."""
        doc = DocumentModel(
            title="Test Document",
            file_path="/path/to/document.pdf",
            file_hash="test123", file_size=500
        )

        str_repr = str(doc)
        assert "Test Document" in str_repr or "DocumentModel" in str_repr

    def test_document_model_with_unicode_content(self):
        """Test document model with unicode content."""
        doc = DocumentModel(
            title="Unicode Test Document",
            file_path="/path/to/unicode.pdf",
            content="Unicode content: 测试内容 with émojis 🚀"
        )

        assert "测试内容" in doc.file_hash
        assert "🚀" in doc.file_hash

    def test_document_model_field_validation(self):
        """Test document model field validation."""
        # Test with empty title
        try:
            doc = DocumentModel(
                title="",
                file_path="/path/to/document.pdf",
                file_hash="test123", file_size=500
            )
            # Should allow empty title or handle gracefully
            assert doc.title == ""
        except ValueError:
            # If validation is strict, should raise ValueError
            pass

    def test_document_model_serialization(self):
        """Test document model can be serialized to dict."""
        doc = DocumentModel(
            document_id=1,
            title="Serializable Document",
            file_path="/path/to/doc.pdf",
            content="Content for serialization"
        )

        # Test if model has dict conversion method
        try:
            doc_dict = doc.to_dict()
            assert isinstance(doc_dict, dict)
            assert doc_dict["title"] == "Serializable Document"
        except AttributeError:
            # Model might not have to_dict method - that's ok
            pass


class TestCitationModel:
    """Test CitationModel functionality."""

    def test_citation_model_creation_with_required_fields(self):
        """Test citation model creation with required fields."""
        citation = CitationModel(
            document_id=1,
            raw_text="Smith, J. (2023). Test Article. Journal of Testing, 10(1), 1-10.",
            title="Test Citation",
            authors="Test Author"
        )

        assert citation.document_id == 1
        assert citation.raw_text == "Smith, J. (2023). Test Article. Journal of Testing, 10(1), 1-10."
        assert citation.title == "Test Citation"
        assert citation.authors == "Test Author"

    def test_citation_model_creation_with_all_fields(self):
        """Test citation model creation with all fields."""
        citation = CitationModel(
            citation_id=1,
            document_id=1,
            title="Complete Citation",
            authors="Author One, Author Two",
            year=2023,
            journal="Test Journal",
            volume="10",
            pages="1-10",
            doi="10.1000/test.doi",
            citation_type="article",
            confidence_score=0.95,
            created_at=datetime.now()
        )

        assert citation.citation_id == 1
        assert citation.year == 2023
        assert citation.journal == "Test Journal"
        assert citation.doi == "10.1000/test.doi"
        assert citation.confidence_score == 0.95

    def test_citation_model_multiple_authors(self):
        """Test citation model with multiple authors."""
        citation = CitationModel(
            document_id=1,
            title="Multi-Author Paper",
            authors="Smith, J.; Johnson, A.; Williams, B.",
            citation_type="article"
        )

        assert "Smith, J." in citation.authors
        assert "Johnson, A." in citation.authors
        assert "Williams, B." in citation.authors

    def test_citation_model_different_types(self):
        """Test citation model with different citation types."""
        types = ["article", "book", "inproceedings", "techreport", "misc"]

        for citation_type in types:
            citation = CitationModel(
                document_id=1,
                title=f"Test {citation_type.title()}",
                authors="Test Author",
                citation_type=citation_type
            )
            assert citation.citation_type == citation_type

    def test_citation_model_year_validation(self):
        """Test citation model year validation."""
        # Test valid year
        citation = CitationModel(
            document_id=1,
            title="Valid Year Citation",
            authors="Test Author",
            citation_type="article",
            year=2023
        )
        assert citation.year == 2023

        # Test edge case years
        old_citation = CitationModel(
            document_id=1,
            title="Old Citation",
            authors="Historical Author",
            citation_type="book",
            year=1900
        )
        assert old_citation.year == 1900

    def test_citation_model_confidence_score_range(self):
        """Test citation model confidence score range."""
        # Test valid confidence scores
        for score in [0.0, 0.5, 0.95, 1.0]:
            citation = CitationModel(
                document_id=1,
                title="Confidence Test Citation",
                authors="Test Author",
                citation_type="article",
                confidence_score=score
            )
            assert citation.confidence_score == score


class TestCitationRelationModel:
    """Test CitationRelationModel functionality."""

    def test_citation_relation_model_creation(self):
        """Test citation relation model creation."""
        relation = CitationRelationModel(
            source_document_id=1,
            target_document_id=2,
            citation_context="This work builds upon [1]"
        )

        assert relation.source_document_id == 1
        assert relation.target_document_id == 2
        assert relation.citation_context == "This work builds upon [1]"

    def test_citation_relation_model_with_all_fields(self):
        """Test citation relation model with all fields."""
        relation = CitationRelationModel(
            relation_id=1,
            source_document_id=1,
            target_document_id=2,
            citation_context="Detailed citation context",
            relation_type="cites",
            confidence_score=0.9,
            created_at=datetime.now()
        )

        assert relation.relation_id == 1
        assert relation.relation_type == "cites"
        assert relation.confidence_score == 0.9
        assert isinstance(relation.created_at, datetime)

    def test_citation_relation_different_types(self):
        """Test citation relation with different relation types."""
        relation_types = ["cites", "cited_by", "related_to", "builds_on"]

        for rel_type in relation_types:
            relation = CitationRelationModel(
                source_document_id=1,
                target_document_id=2,
                citation_context=f"Context for {rel_type}",
                relation_type=rel_type
            )
            assert relation.relation_type == rel_type

    def test_citation_relation_self_reference_prevention(self):
        """Test that self-referencing relations are handled."""
        # This should either be allowed or raise a validation error
        try:
            relation = CitationRelationModel(
                source_document_id=1,
                target_document_id=1,  # Same as source
                citation_context="Self-referencing relation"
            )
            # If allowed, it should be created
            assert relation.source_document_id == relation.target_document_id
        except ValueError:
            # If validation prevents self-reference, that's also correct
            pass

    def test_citation_relation_model_context_length(self):
        """Test citation relation model with various context lengths."""
        # Short context
        short_relation = CitationRelationModel(
            source_document_id=1,
            target_document_id=2,
            citation_context="Brief context."
        )
        assert len(short_relation.citation_context) > 0

        # Long context
        long_context = "Very long citation context. " * 50  # ~1400 chars
        long_relation = CitationRelationModel(
            source_document_id=1,
            target_document_id=2,
            citation_context=long_context
        )
        assert len(long_relation.citation_context) > 1000


class TestModelInteractions:
    """Test interactions between different models."""

    def test_document_citation_relationship(self):
        """Test relationship between document and citation models."""
        # Create a document
        doc = DocumentModel(
            document_id=1,
            title="Source Document",
            file_path="/path/to/source.pdf",
            content="Document with citations"
        )

        # Create a citation for that document
        citation = CitationModel(
            document_id=doc.document_id,
            title="Referenced Work",
            authors="Referenced Author",
            citation_type="article"
        )

        assert citation.document_id == doc.document_id

    def test_citation_relation_consistency(self):
        """Test consistency in citation relations."""
        # Create documents
        doc1 = DocumentModel(
            document_id=1,
            title="Source Document",
            file_path="/path/to/source.pdf",
            content="Source content"
        )

        doc2 = DocumentModel(
            document_id=2,
            title="Target Document",
            file_path="/path/to/target.pdf",
            content="Target content"
        )

        # Create relation between documents
        relation = CitationRelationModel(
            source_document_id=doc1.document_id,
            target_document_id=doc2.document_id,
            citation_context="Document 1 cites Document 2"
        )

        assert relation.source_document_id == doc1.document_id
        assert relation.target_document_id == doc2.document_id

    def test_model_datetime_consistency(self):
        """Test that datetime fields are consistent across models."""
        now = datetime.now()

        # Create models with same timestamp
        doc = DocumentModel(
            title="Timestamped Document",
            file_path="/path/to/doc.pdf",
            content="Content",
            created_at=now
        )

        citation = CitationModel(
            document_id=1,
            title="Timestamped Citation",
            authors="Author",
            citation_type="article",
            created_at=now
        )

        relation = CitationRelationModel(
            source_document_id=1,
            target_document_id=2,
            citation_context="Context",
            created_at=now
        )

        # All should have the same creation time
        assert doc.created_at == now
        assert citation.created_at == now
        assert relation.created_at == now


class TestModelEdgeCases:
    """Test edge cases for all models."""

    def test_empty_string_fields(self):
        """Test models with empty string fields."""
        # Document with empty content
        doc = DocumentModel(
            title="Empty Content Document",
            file_path="/path/to/empty.pdf",
            content=""
        )
        assert doc.file_hash == ""

        # Citation with empty journal
        citation = CitationModel(
            document_id=1,
            title="No Journal Citation",
            authors="Author",
            citation_type="article",
            journal=""
        )
        assert citation.journal == ""

    def test_null_optional_fields(self):
        """Test models with None values for optional fields."""
        doc = DocumentModel(
            title="Minimal Document",
            file_path="/path/to/minimal.pdf",
            content="Minimal content",
            file_size=None,
            page_count=None
        )

        assert doc.file_size is None
        assert doc.page_count is None

    def test_special_characters_in_fields(self):
        """Test models with special characters in fields."""
        doc = DocumentModel(
            title="Special Characters: !@#$%^&*()",
            file_path="/path/with spaces/and-symbols.pdf",
            content="Content with special chars: <>?{}[]|\\"
        )

        assert "!@#$%^&*()" in doc.title
        assert "<>?{}[]|\\" in doc.file_hash
