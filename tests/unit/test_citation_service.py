"""
Unit tests for CitationService - Main business logic for citation management.
"""

from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from src.database.models import CitationModel, CitationRelationModel
from src.interfaces.repository_interfaces import (
    ICitationRelationRepository,
    ICitationRepository,
)
from src.services.citation_parsing_service import CitationParsingService
from src.services.citation_service import CitationService


class TestCitationService:
    """Test suite for CitationService business logic."""

    @pytest.fixture
    def mock_citation_repo(self):
        """Create a mock citation repository."""
        repo = Mock(spec=ICitationRepository)
        repo.find_by_document_id.return_value = []
        repo.find_by_id.return_value = None
        repo.save.return_value = CitationModel(
            id=1,
            document_id=1,
            citation_text="Test citation",
            authors="Test Author",
            year=2024,
            title="Test Title"
        )
        return repo

    @pytest.fixture
    def mock_relation_repo(self):
        """Create a mock citation relation repository."""
        repo = Mock(spec=ICitationRelationRepository)
        repo.find_by_citation_id.return_value = []
        repo.save.return_value = CitationRelationModel(
            id=1,
            source_citation_id=1,
            target_citation_id=2,
            relation_type="cites"
        )
        return repo

    @pytest.fixture
    def mock_parsing_service(self):
        """Create a mock citation parsing service."""
        service = Mock(spec=CitationParsingService)
        service.parse_citations.return_value = [
            {
                "text": "Smith et al. (2024)",
                "authors": "Smith, J., Doe, J.",
                "year": 2024,
                "title": "Sample Paper",
                "journal": "Test Journal"
            }
        ]
        service.extract_relations.return_value = [
            {
                "source_id": 1,
                "target_id": 2,
                "relation_type": "cites"
            }
        ]
        return service

    @pytest.fixture
    def citation_service(self, mock_citation_repo, mock_relation_repo, mock_parsing_service):
        """Create a CitationService instance with mocked dependencies."""
        return CitationService(
            citation_repository=mock_citation_repo,
            relation_repository=mock_relation_repo,
            parsing_service=mock_parsing_service
        )

    def test_service_initialization(self, citation_service):
        """Test that CitationService initializes correctly."""
        assert citation_service is not None
        assert citation_service.citation_repository is not None
        assert citation_service.relation_repository is not None
        assert citation_service.parsing_service is not None

    def test_extract_citations_from_text(self, citation_service, mock_parsing_service):
        """Test extracting citations from text."""
        # Arrange
        text = "This paper cites Smith et al. (2024) and Jones (2023)."
        document_id = 1

        # Act
        result = citation_service.extract_citations(text, document_id)

        # Assert
        mock_parsing_service.parse_citations.assert_called_once_with(text)
        assert len(result) == 1
        assert result[0]["authors"] == "Smith, J., Doe, J."
        assert result[0]["year"] == 2024

    def test_save_citation(self, citation_service, mock_citation_repo):
        """Test saving a citation to the repository."""
        # Arrange
        citation_data = {
            "document_id": 1,
            "citation_text": "Test Citation",
            "authors": "Author, A.",
            "year": 2024,
            "title": "Test Title",
            "journal": "Test Journal"
        }

        # Act
        result = citation_service.save_citation(citation_data)

        # Assert
        mock_citation_repo.save.assert_called_once()
        saved_citation = mock_citation_repo.save.call_args[0][0]
        assert saved_citation.document_id == 1
        assert saved_citation.citation_text == "Test Citation"
        assert saved_citation.authors == "Author, A."
        assert result.id == 1

    def test_get_citations_by_document(self, citation_service, mock_citation_repo):
        """Test retrieving citations for a document."""
        # Arrange
        document_id = 1
        mock_citations = [
            CitationModel(id=1, document_id=1, citation_text="Citation 1"),
            CitationModel(id=2, document_id=1, citation_text="Citation 2")
        ]
        mock_citation_repo.find_by_document_id.return_value = mock_citations

        # Act
        result = citation_service.get_citations_by_document(document_id)

        # Assert
        mock_citation_repo.find_by_document_id.assert_called_once_with(document_id)
        assert len(result) == 2
        assert result[0].citation_text == "Citation 1"
        assert result[1].citation_text == "Citation 2"

    def test_create_citation_relation(self, citation_service, mock_relation_repo):
        """Test creating a relation between citations."""
        # Arrange
        source_id = 1
        target_id = 2
        relation_type = "cites"

        # Act
        result = citation_service.create_relation(source_id, target_id, relation_type)

        # Assert
        mock_relation_repo.save.assert_called_once()
        saved_relation = mock_relation_repo.save.call_args[0][0]
        assert saved_relation.source_citation_id == source_id
        assert saved_relation.target_citation_id == target_id
        assert saved_relation.relation_type == relation_type
        assert result.id == 1

    def test_get_citation_relations(self, citation_service, mock_relation_repo):
        """Test retrieving relations for a citation."""
        # Arrange
        citation_id = 1
        mock_relations = [
            CitationRelationModel(
                id=1,
                source_citation_id=1,
                target_citation_id=2,
                relation_type="cites"
            ),
            CitationRelationModel(
                id=2,
                source_citation_id=1,
                target_citation_id=3,
                relation_type="cited_by"
            )
        ]
        mock_relation_repo.find_by_citation_id.return_value = mock_relations

        # Act
        result = citation_service.get_relations(citation_id)

        # Assert
        mock_relation_repo.find_by_citation_id.assert_called_once_with(citation_id)
        assert len(result) == 2
        assert result[0].relation_type == "cites"
        assert result[1].relation_type == "cited_by"

    def test_update_citation(self, citation_service, mock_citation_repo):
        """Test updating an existing citation."""
        # Arrange
        citation_id = 1
        existing_citation = CitationModel(
            id=citation_id,
            document_id=1,
            citation_text="Old Text",
            authors="Old Author",
            year=2023
        )
        mock_citation_repo.find_by_id.return_value = existing_citation

        update_data = {
            "citation_text": "New Text",
            "authors": "New Author",
            "year": 2024
        }

        # Act
        result = citation_service.update_citation(citation_id, update_data)

        # Assert
        mock_citation_repo.find_by_id.assert_called_once_with(citation_id)
        mock_citation_repo.update.assert_called_once()
        updated_citation = mock_citation_repo.update.call_args[0][0]
        assert updated_citation.citation_text == "New Text"
        assert updated_citation.authors == "New Author"
        assert updated_citation.year == 2024

    def test_delete_citation(self, citation_service, mock_citation_repo, mock_relation_repo):
        """Test deleting a citation and its relations."""
        # Arrange
        citation_id = 1

        # Act
        result = citation_service.delete_citation(citation_id)

        # Assert
        mock_relation_repo.delete_by_citation_id.assert_called_once_with(citation_id)
        mock_citation_repo.delete.assert_called_once_with(citation_id)
        assert result is True

    def test_search_citations(self, citation_service, mock_citation_repo):
        """Test searching citations by query."""
        # Arrange
        query = "machine learning"
        mock_results = [
            CitationModel(
                id=1,
                document_id=1,
                citation_text="Machine Learning Paper",
                title="ML Research"
            )
        ]
        mock_citation_repo.search.return_value = mock_results

        # Act
        result = citation_service.search_citations(query)

        # Assert
        mock_citation_repo.search.assert_called_once_with(query)
        assert len(result) == 1
        assert "Machine Learning" in result[0].citation_text

    def test_get_citation_statistics(self, citation_service, mock_citation_repo):
        """Test getting citation statistics."""
        # Arrange
        document_id = 1
        mock_citations = [
            CitationModel(id=1, document_id=1, year=2022),
            CitationModel(id=2, document_id=1, year=2023),
            CitationModel(id=3, document_id=1, year=2023),
            CitationModel(id=4, document_id=1, year=2024)
        ]
        mock_citation_repo.find_by_document_id.return_value = mock_citations

        # Act
        stats = citation_service.get_statistics(document_id)

        # Assert
        assert stats["total_citations"] == 4
        assert stats["citations_by_year"]["2023"] == 2
        assert stats["citations_by_year"]["2022"] == 1
        assert stats["citations_by_year"]["2024"] == 1

    def test_batch_save_citations(self, citation_service, mock_citation_repo):
        """Test batch saving multiple citations."""
        # Arrange
        citations_data = [
            {"document_id": 1, "citation_text": "Citation 1", "year": 2023},
            {"document_id": 1, "citation_text": "Citation 2", "year": 2024},
            {"document_id": 1, "citation_text": "Citation 3", "year": 2024}
        ]

        # Act
        result = citation_service.batch_save_citations(citations_data)

        # Assert
        assert mock_citation_repo.save.call_count == 3
        assert len(result) == 3

    def test_handle_empty_citation_list(self, citation_service, mock_citation_repo):
        """Test handling empty citation list."""
        # Arrange
        mock_citation_repo.find_by_document_id.return_value = []

        # Act
        result = citation_service.get_citations_by_document(999)

        # Assert
        assert result == []
        mock_citation_repo.find_by_document_id.assert_called_once_with(999)

    def test_citation_validation_error(self, citation_service):
        """Test citation validation with invalid data."""
        # Arrange
        invalid_citation = {
            "document_id": None,  # Invalid: missing document_id
            "citation_text": "",   # Invalid: empty text
            "year": "invalid"      # Invalid: non-numeric year
        }

        # Act & Assert
        with pytest.raises(ValueError):
            citation_service.validate_citation_data(invalid_citation)

    def test_duplicate_citation_handling(self, citation_service, mock_citation_repo):
        """Test handling duplicate citations."""
        # Arrange
        citation_data = {
            "document_id": 1,
            "citation_text": "Duplicate Citation",
            "authors": "Author A",
            "year": 2024
        }

        # Simulate existing citation
        existing_citation = CitationModel(
            id=1,
            document_id=1,
            citation_text="Duplicate Citation",
            authors="Author A",
            year=2024
        )
        mock_citation_repo.find_duplicate.return_value = existing_citation

        # Act
        result = citation_service.save_citation(citation_data, allow_duplicates=False)

        # Assert
        mock_citation_repo.find_duplicate.assert_called_once()
        assert result.id == 1  # Returns existing citation

    def test_citation_with_metadata(self, citation_service, mock_citation_repo):
        """Test saving citation with full metadata."""
        # Arrange
        citation_data = {
            "document_id": 1,
            "citation_text": "Complete Citation",
            "authors": "Smith, J., Doe, J.",
            "year": 2024,
            "title": "Complete Research Paper",
            "journal": "Journal of Testing",
            "volume": "10",
            "issue": "2",
            "pages": "100-120",
            "doi": "10.1234/test.2024",
            "url": "https://example.com/paper"
        }

        # Act
        result = citation_service.save_citation(citation_data)

        # Assert
        mock_citation_repo.save.assert_called_once()
        saved_citation = mock_citation_repo.save.call_args[0][0]
        assert saved_citation.doi == "10.1234/test.2024"
        assert saved_citation.url == "https://example.com/paper"
        assert saved_citation.volume == "10"
