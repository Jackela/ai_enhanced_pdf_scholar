"""
Test Citation Models - TDD Implementation
Tests for CitationModel and CitationRelationModel data classes.
Ensures proper validation, creation, and data handling.
"""

from datetime import datetime

import pytest

from src.database.models import CitationModel, CitationRelationModel


class TestCitationModel:
    """Test suite for CitationModel using TDD approach."""

    def test_citation_model_creation_with_required_fields(self):
        """Test creating citation with only required fields."""
        # Arrange
        document_id = 1
        raw_text = "Smith, J. (2023). Test Paper. Journal of Testing, 1(1), 1-10."

        # Act
        citation = CitationModel(
            document_id=document_id,
            raw_text=raw_text
        )

        # Assert
        assert citation.document_id == document_id
        assert citation.raw_text == raw_text
        assert citation.id is None  # Not set until saved to DB
        assert citation.created_at is not None
        assert citation.updated_at is not None
        assert citation.created_at == citation.updated_at
        assert not citation._from_database

    def test_citation_model_creation_with_all_fields(self):
        """Test creating citation with all fields populated."""
        # Arrange
        test_data = {
            "document_id": 1,
            "raw_text": "Smith, J. (2023). Test Paper. Journal of Testing, 1(1), 1-10.",
            "authors": "Smith, J.",
            "title": "Test Paper",
            "publication_year": 2023,
            "journal_or_venue": "Journal of Testing",
            "doi": "10.1000/test.doi",
            "page_range": "1-10",
            "citation_type": "journal",
            "confidence_score": 0.95
        }

        # Act
        citation = CitationModel(**test_data)

        # Assert
        assert citation.document_id == test_data["document_id"]
        assert citation.raw_text == test_data["raw_text"]
        assert citation.authors == test_data["authors"]
        assert citation.title == test_data["title"]
        assert citation.publication_year == test_data["publication_year"]
        assert citation.journal_or_venue == test_data["journal_or_venue"]
        assert citation.doi == test_data["doi"]
        assert citation.page_range == test_data["page_range"]
        assert citation.citation_type == test_data["citation_type"]
        assert citation.confidence_score == test_data["confidence_score"]

    def test_citation_model_validation_invalid_document_id(self):
        """Test validation fails for invalid document_id."""
        # Arrange
        invalid_ids = [0, -1, -999]

        for invalid_id in invalid_ids:
            # Act & Assert
            with pytest.raises(ValueError, match="Document ID must be positive"):
                CitationModel(
                    document_id=invalid_id,
                    raw_text="Valid citation text"
                )

    def test_citation_model_validation_empty_raw_text(self):
        """Test validation fails for empty raw_text."""
        # Arrange
        empty_texts = ["", "   ", "\t\n"]

        for empty_text in empty_texts:
            # Act & Assert
            with pytest.raises(ValueError, match="Raw citation text cannot be empty"):
                CitationModel(
                    document_id=1,
                    raw_text=empty_text
                )

    def test_citation_model_validation_invalid_publication_year(self):
        """Test validation fails for invalid publication_year."""
        # Arrange
        invalid_years = [999, datetime.now().year + 2, -2023]

        for invalid_year in invalid_years:
            # Act & Assert
            with pytest.raises(ValueError, match="Invalid publication year"):
                CitationModel(
                    document_id=1,
                    raw_text="Valid citation",
                    publication_year=invalid_year
                )

    def test_citation_model_validation_invalid_confidence_score(self):
        """Test validation fails for invalid confidence_score."""
        # Arrange
        invalid_scores = [-0.1, 1.1, 2.0, -1.0]

        for invalid_score in invalid_scores:
            # Act & Assert
            with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
                CitationModel(
                    document_id=1,
                    raw_text="Valid citation",
                    confidence_score=invalid_score
                )

    def test_citation_model_from_database_row(self):
        """Test creating citation from database row."""
        # Arrange
        db_row = {
            "id": 1,
            "document_id": 2,
            "raw_text": "Database citation",
            "authors": "DB Author",
            "title": "DB Title",
            "publication_year": 2023,
            "journal_or_venue": "DB Journal",
            "doi": "10.1000/db.doi",
            "page_range": "10-20",
            "citation_type": "journal",
            "confidence_score": 0.8,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-02T12:00:00"
        }

        # Act
        citation = CitationModel.from_database_row(db_row)

        # Assert
        assert citation.id == 1
        assert citation.document_id == 2
        assert citation.raw_text == "Database citation"
        assert citation.authors == "DB Author"
        assert citation.title == "DB Title"
        assert citation.publication_year == 2023
        assert citation.journal_or_venue == "DB Journal"
        assert citation.doi == "10.1000/db.doi"
        assert citation.page_range == "10-20"
        assert citation.citation_type == "journal"
        assert citation.confidence_score == 0.8
        assert citation.created_at == datetime(2023, 1, 1, 12, 0, 0)
        assert citation.updated_at == datetime(2023, 1, 2, 12, 0, 0)
        assert citation._from_database is True

    def test_citation_model_to_database_dict(self):
        """Test converting citation to database dictionary."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Test citation",
            authors="Test Author",
            title="Test Title",
            publication_year=2023,
            confidence_score=0.9
        )
        citation.id = 1

        # Act
        db_dict = citation.to_database_dict()

        # Assert
        expected_keys = [
            "id", "document_id", "raw_text", "authors", "title",
            "publication_year", "journal_or_venue", "doi", "page_range",
            "citation_type", "confidence_score", "created_at", "updated_at"
        ]
        assert all(key in db_dict for key in expected_keys)
        assert db_dict["id"] == 1
        assert db_dict["document_id"] == 1
        assert db_dict["raw_text"] == "Test citation"
        assert db_dict["authors"] == "Test Author"
        assert db_dict["title"] == "Test Title"
        assert db_dict["publication_year"] == 2023
        assert db_dict["confidence_score"] == 0.9

    def test_citation_model_to_api_dict(self):
        """Test converting citation to API dictionary."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="API citation",
            authors="API Author",
            confidence_score=0.85
        )
        citation.id = 2

        # Act
        api_dict = citation.to_api_dict()

        # Assert
        expected_keys = [
            "id", "document_id", "raw_text", "authors", "title",
            "publication_year", "journal_or_venue", "doi", "page_range",
            "citation_type", "confidence_score", "created_at", "updated_at"
        ]
        assert all(key in api_dict for key in expected_keys)
        assert api_dict["id"] == 2
        assert api_dict["document_id"] == 1
        assert api_dict["raw_text"] == "API citation"
        assert api_dict["authors"] == "API Author"

    def test_citation_model_format_apa_style(self):
        """Test APA citation formatting."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Raw citation",
            authors="Smith, J., & Jones, M.",
            title="Test Paper on Citation Formatting",
            publication_year=2023,
            journal_or_venue="Journal of Test Citations"
        )

        # Act
        formatted = citation.get_formatted_citation("apa")

        # Assert
        expected = "Smith, J., & Jones, M.. (2023). Test Paper on Citation Formatting. *Journal of Test Citations*."
        assert formatted == expected

    def test_citation_model_format_mla_style(self):
        """Test MLA citation formatting."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Raw citation",
            authors="Smith, John",
            title="Test Paper on Citation Formatting",
            publication_year=2023,
            journal_or_venue="Journal of Test Citations"
        )

        # Act
        formatted = citation.get_formatted_citation("mla")

        # Assert
        expected = 'Smith, John, "Test Paper on Citation Formatting", *Journal of Test Citations*, 2023.'
        assert formatted == expected

    def test_citation_model_format_chicago_style(self):
        """Test Chicago citation formatting."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Raw citation",
            authors="Smith, John",
            title="Test Paper on Citation Formatting",
            publication_year=2023,
            journal_or_venue="Journal of Test Citations"
        )

        # Act
        formatted = citation.get_formatted_citation("chicago")

        # Assert
        expected = 'Smith, John. "Test Paper on Citation Formatting". Journal of Test Citations. (2023).'
        assert formatted == expected

    def test_citation_model_format_unknown_style_returns_raw(self):
        """Test that unknown citation style returns raw text."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Raw citation text",
            authors="Test Author"
        )

        # Act
        formatted = citation.get_formatted_citation("unknown")

        # Assert
        assert formatted == "Raw citation text"

    def test_citation_model_is_complete_with_required_fields(self):
        """Test is_complete returns True when all required fields present."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            raw_text="Complete citation",
            authors="Complete Author",
            title="Complete Title",
            publication_year=2023
        )

        # Act & Assert
        assert citation.is_complete() is True

    def test_citation_model_is_complete_with_missing_fields(self):
        """Test is_complete returns False when required fields missing."""
        # Arrange
        incomplete_citations = [
            CitationModel(document_id=1, raw_text="No author", title="Title", publication_year=2023),
            CitationModel(document_id=1, raw_text="No title", authors="Author"),
            CitationModel(document_id=1, raw_text="No year", authors="Author", title="Title"),
        ]

        for citation in incomplete_citations:
            # Act & Assert
            assert citation.is_complete() is False


class TestCitationRelationModel:
    """Test suite for CitationRelationModel using TDD approach."""

    def test_citation_relation_creation_with_required_fields(self):
        """Test creating citation relation with required fields."""
        # Arrange
        source_doc_id = 1
        source_citation_id = 2

        # Act
        relation = CitationRelationModel(
            source_document_id=source_doc_id,
            source_citation_id=source_citation_id
        )

        # Assert
        assert relation.source_document_id == source_doc_id
        assert relation.source_citation_id == source_citation_id
        assert relation.target_document_id is None
        assert relation.target_citation_id is None
        assert relation.relation_type == "cites"
        assert relation.confidence_score is None
        assert relation.created_at is not None
        assert relation.id is None

    def test_citation_relation_creation_with_all_fields(self):
        """Test creating citation relation with all fields."""
        # Arrange
        test_data = {
            "source_document_id": 1,
            "source_citation_id": 2,
            "target_document_id": 3,
            "target_citation_id": 4,
            "relation_type": "references",
            "confidence_score": 0.88
        }

        # Act
        relation = CitationRelationModel(**test_data)

        # Assert
        assert relation.source_document_id == 1
        assert relation.source_citation_id == 2
        assert relation.target_document_id == 3
        assert relation.target_citation_id == 4
        assert relation.relation_type == "references"
        assert relation.confidence_score == 0.88

    def test_citation_relation_validation_invalid_source_document_id(self):
        """Test validation fails for invalid source_document_id."""
        # Arrange
        invalid_ids = [0, -1, -999]

        for invalid_id in invalid_ids:
            # Act & Assert
            with pytest.raises(ValueError, match="Source document ID must be positive"):
                CitationRelationModel(
                    source_document_id=invalid_id,
                    source_citation_id=1
                )

    def test_citation_relation_validation_invalid_source_citation_id(self):
        """Test validation fails for invalid source_citation_id."""
        # Arrange
        invalid_ids = [0, -1, -999]

        for invalid_id in invalid_ids:
            # Act & Assert
            with pytest.raises(ValueError, match="Source citation ID must be positive"):
                CitationRelationModel(
                    source_document_id=1,
                    source_citation_id=invalid_id
                )

    def test_citation_relation_validation_invalid_target_document_id(self):
        """Test validation fails for invalid target_document_id when provided."""
        # Arrange
        invalid_ids = [0, -1, -999]

        for invalid_id in invalid_ids:
            # Act & Assert
            with pytest.raises(ValueError, match="Target document ID must be positive"):
                CitationRelationModel(
                    source_document_id=1,
                    source_citation_id=2,
                    target_document_id=invalid_id
                )

    def test_citation_relation_validation_invalid_confidence_score(self):
        """Test validation fails for invalid confidence_score."""
        # Arrange
        invalid_scores = [-0.1, 1.1, 2.0, -1.0]

        for invalid_score in invalid_scores:
            # Act & Assert
            with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
                CitationRelationModel(
                    source_document_id=1,
                    source_citation_id=2,
                    confidence_score=invalid_score
                )

    def test_citation_relation_from_database_row(self):
        """Test creating citation relation from database row."""
        # Arrange
        db_row = {
            "id": 1,
            "source_document_id": 2,
            "source_citation_id": 3,
            "target_document_id": 4,
            "target_citation_id": 5,
            "relation_type": "cited_by",
            "confidence_score": 0.75,
            "created_at": "2023-01-01T12:00:00"
        }

        # Act
        relation = CitationRelationModel.from_database_row(db_row)

        # Assert
        assert relation.id == 1
        assert relation.source_document_id == 2
        assert relation.source_citation_id == 3
        assert relation.target_document_id == 4
        assert relation.target_citation_id == 5
        assert relation.relation_type == "cited_by"
        assert relation.confidence_score == 0.75
        assert relation.created_at == datetime(2023, 1, 1, 12, 0, 0)

    def test_citation_relation_to_database_dict(self):
        """Test converting citation relation to database dictionary."""
        # Arrange
        relation = CitationRelationModel(
            source_document_id=1,
            source_citation_id=2,
            target_document_id=3,
            relation_type="cites",
            confidence_score=0.9
        )
        relation.id = 1

        # Act
        db_dict = relation.to_database_dict()

        # Assert
        expected_keys = [
            "id", "source_document_id", "source_citation_id",
            "target_document_id", "target_citation_id", "relation_type",
            "confidence_score", "created_at"
        ]
        assert all(key in db_dict for key in expected_keys)
        assert db_dict["id"] == 1
        assert db_dict["source_document_id"] == 1
        assert db_dict["source_citation_id"] == 2
        assert db_dict["target_document_id"] == 3
        assert db_dict["relation_type"] == "cites"
        assert db_dict["confidence_score"] == 0.9

    def test_citation_relation_database_row_with_defaults(self):
        """Test database row parsing with default values."""
        # Arrange
        minimal_row = {
            "id": 1,
            "source_document_id": 2,
            "source_citation_id": 3,
            "created_at": "2023-01-01T12:00:00"
        }

        # Act
        relation = CitationRelationModel.from_database_row(minimal_row)

        # Assert
        assert relation.id == 1
        assert relation.source_document_id == 2
        assert relation.source_citation_id == 3
        assert relation.target_document_id is None
        assert relation.target_citation_id is None
        assert relation.relation_type == "cites"  # Default value
        assert relation.confidence_score is None
        assert relation.created_at == datetime(2023, 1, 1, 12, 0, 0)
