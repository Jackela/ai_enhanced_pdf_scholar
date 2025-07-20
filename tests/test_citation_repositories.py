"""
Test Citation Repositories - TDD Implementation
Tests for CitationRepository and CitationRelationRepository.
Follows SOLID principles and Repository pattern testing.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.database.models import CitationModel, CitationRelationModel, DocumentModel
from src.database.connection import DatabaseConnection
from src.interfaces.repository_interfaces import ICitationRepository, ICitationRelationRepository


class TestCitationRepositoryInterface:
    """Test suite for CitationRepository interface compliance using TDD."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection for testing."""
        mock_db = Mock()
        mock_db.get_last_change_count.return_value = 1
        return mock_db

    @pytest.fixture
    def sample_citations(self):
        """Sample citations for testing."""
        return [
            CitationModel(
                id=1,
                document_id=1,
                raw_text="Smith, J. (2023). Test Paper. Journal of Testing.",
                authors="Smith, J.",
                title="Test Paper",
                publication_year=2023,
                journal_or_venue="Journal of Testing",
                citation_type="journal",
                confidence_score=0.9,
                _from_database=True
            ),
            CitationModel(
                id=2,
                document_id=1,
                raw_text="Jones, M. (2022). Another Paper. Conference Proceedings.",
                authors="Jones, M.",
                title="Another Paper",
                publication_year=2022,
                journal_or_venue="Conference Proceedings",
                citation_type="conference",
                confidence_score=0.85,
                _from_database=True
            )
        ]

    def test_citation_repository_create_new_citation(self, mock_db_connection):
        """Test creating a new citation through repository."""
        # This test will fail until we implement CitationRepository
        # Following TDD red-green-refactor cycle
        
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        new_citation = CitationModel(
            document_id=1,
            raw_text="New citation text",
            authors="New Author",
            title="New Title",
            publication_year=2023
        )
        
        # Mock database response
        mock_db_connection.execute.return_value = None
        mock_db_connection.fetch_one.return_value = {"id": 1}
        
        # Act
        result = repo.create(new_citation)
        
        # Assert
        assert isinstance(result, CitationModel)
        assert result.id == 1
        assert result.document_id == 1
        assert result.raw_text == "New citation text"
        mock_db_connection.execute.assert_called_once()

    def test_citation_repository_get_by_id_existing(self, mock_db_connection):
        """Test getting citation by ID when it exists."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_row = {
            "id": 1,
            "document_id": 1,
            "raw_text": "Test citation",
            "authors": "Test Author",
            "title": "Test Title",
            "publication_year": 2023,
            "journal_or_venue": "Test Journal",
            "doi": None,
            "page_range": None,
            "citation_type": "journal",
            "confidence_score": 0.9,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00"
        }
        mock_db_connection.fetch_one.return_value = mock_row
        
        # Act
        result = repo.get_by_id(1)
        
        # Assert
        assert isinstance(result, CitationModel)
        assert result.id == 1
        assert result.document_id == 1
        assert result.raw_text == "Test citation"
        mock_db_connection.fetch_one.assert_called_once()

    def test_citation_repository_get_by_id_nonexistent(self, mock_db_connection):
        """Test getting citation by ID when it doesn't exist."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_db_connection.fetch_one.return_value = None
        
        # Act
        result = repo.get_by_id(999)
        
        # Assert
        assert result is None
        mock_db_connection.fetch_one.assert_called_once()

    def test_citation_repository_update_existing_citation(self, mock_db_connection):
        """Test updating an existing citation."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        citation = CitationModel(
            id=1,
            document_id=1,
            raw_text="Updated citation text",
            authors="Updated Author",
            title="Updated Title",
            publication_year=2023,
            _from_database=True
        )
        
        # Mock database response
        mock_db_connection.execute.return_value = None
        
        # Act
        result = repo.update(citation)
        
        # Assert
        assert isinstance(result, CitationModel)
        assert result.raw_text == "Updated citation text"
        mock_db_connection.execute.assert_called_once()

    def test_citation_repository_delete_existing_citation(self, mock_db_connection):
        """Test deleting an existing citation."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_db_connection.execute.return_value = None
        mock_db_connection.get_last_change_count.return_value = 1
        
        # Act
        result = repo.delete(1)
        
        # Assert
        assert result is True
        mock_db_connection.execute.assert_called_once()

    def test_citation_repository_find_by_document_id(self, mock_db_connection, sample_citations):
        """Test finding citations by document ID."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [citation.to_database_dict() for citation in sample_citations]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.find_by_document_id(1)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(citation, CitationModel) for citation in result)
        assert all(citation.document_id == 1 for citation in result)
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_repository_search_by_author(self, mock_db_connection):
        """Test searching citations by author."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "id": 1,
            "document_id": 1,
            "raw_text": "Smith citation",
            "authors": "Smith, J.",
            "title": "Smith Paper",
            "publication_year": 2023,
            "journal_or_venue": None,
            "doi": None,
            "page_range": None,
            "citation_type": None,
            "confidence_score": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.search_by_author("Smith")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].authors == "Smith, J."
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_repository_search_by_title(self, mock_db_connection):
        """Test searching citations by title."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "id": 1,
            "document_id": 1,
            "raw_text": "Machine Learning citation",
            "authors": "Author, A.",
            "title": "Machine Learning Paper",
            "publication_year": 2023,
            "journal_or_venue": None,
            "doi": None,
            "page_range": None,
            "citation_type": None,
            "confidence_score": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.search_by_title("Machine Learning")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Machine Learning" in result[0].title
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_repository_find_by_doi(self, mock_db_connection):
        """Test finding citation by DOI."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_row = {
            "id": 1,
            "document_id": 1,
            "raw_text": "DOI citation",
            "authors": "DOI Author",
            "title": "DOI Paper",
            "publication_year": 2023,
            "journal_or_venue": "DOI Journal",
            "doi": "10.1000/test.doi",
            "page_range": None,
            "citation_type": "journal",
            "confidence_score": 0.95,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00"
        }
        mock_db_connection.fetch_one.return_value = mock_row
        
        # Act
        result = repo.find_by_doi("10.1000/test.doi")
        
        # Assert
        assert isinstance(result, CitationModel)
        assert result.doi == "10.1000/test.doi"
        mock_db_connection.fetch_one.assert_called_once()

    def test_citation_repository_find_by_year_range(self, mock_db_connection):
        """Test finding citations by year range."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [
            {
                "id": 1,
                "document_id": 1,
                "raw_text": "2020 citation",
                "authors": "Author 2020",
                "title": "2020 Paper",
                "publication_year": 2020,
                "journal_or_venue": None,
                "doi": None,
                "page_range": None,
                "citation_type": None,
                "confidence_score": None,
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:00:00"
            },
            {
                "id": 2,
                "document_id": 1,
                "raw_text": "2022 citation",
                "authors": "Author 2022",
                "title": "2022 Paper",
                "publication_year": 2022,
                "journal_or_venue": None,
                "doi": None,
                "page_range": None,
                "citation_type": None,
                "confidence_score": None,
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:00:00"
            }
        ]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.find_by_year_range(2020, 2022)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(2020 <= citation.publication_year <= 2022 for citation in result)
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_repository_get_by_type(self, mock_db_connection):
        """Test getting citations by type."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "id": 1,
            "document_id": 1,
            "raw_text": "Journal citation",
            "authors": "Journal Author",
            "title": "Journal Paper",
            "publication_year": 2023,
            "journal_or_venue": "Test Journal",
            "doi": None,
            "page_range": None,
            "citation_type": "journal",
            "confidence_score": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.get_by_type("journal")
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].citation_type == "journal"
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_repository_get_statistics(self, mock_db_connection):
        """Test getting citation statistics."""
        # Arrange
        from src.repositories.citation_repository import CitationRepository
        repo = CitationRepository(mock_db_connection)
        
        # Mock database response
        mock_db_connection.fetch_one.side_effect = [
            {"count": 100},  # total_citations
            {"count": 60},   # complete_citations
            {"avg_confidence": 0.85},  # avg_confidence_score
            {"docs_with_citations": 20}  # documents_with_citations
        ]
        mock_db_connection.fetch_all.side_effect = [
            [{"citation_type": "journal", "count": 40}],  # citation_types
            [{"publication_year": 2023, "count": 15}],  # years_breakdown
        ]
        
        # Act
        result = repo.get_statistics()
        
        # Assert
        assert isinstance(result, dict)
        assert "total_citations" in result
        assert "complete_citations" in result
        assert "avg_confidence_score" in result
        assert "citation_types" in result


class TestCitationRelationRepositoryInterface:
    """Test suite for CitationRelationRepository interface compliance using TDD."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection for testing."""
        mock_db = Mock()
        mock_db.get_last_change_count.return_value = 1
        return mock_db

    @pytest.fixture
    def sample_relations(self):
        """Sample citation relations for testing."""
        return [
            CitationRelationModel(
                id=1,
                source_document_id=1,
                source_citation_id=1,
                target_document_id=2,
                target_citation_id=2,
                relation_type="cites",
                confidence_score=0.9
            ),
            CitationRelationModel(
                id=2,
                source_document_id=2,
                source_citation_id=3,
                target_document_id=1,
                target_citation_id=1,
                relation_type="cited_by",
                confidence_score=0.85
            )
        ]

    def test_citation_relation_repository_create_new_relation(self, mock_db_connection):
        """Test creating a new citation relation."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        new_relation = CitationRelationModel(
            source_document_id=1,
            source_citation_id=1,
            target_document_id=2,
            relation_type="cites",
            confidence_score=0.88
        )
        
        # Mock database response
        mock_db_connection.execute.return_value = None
        mock_db_connection.fetch_one.return_value = {"id": 1}
        
        # Act
        result = repo.create(new_relation)
        
        # Assert
        assert isinstance(result, CitationRelationModel)
        assert result.id == 1
        assert result.source_document_id == 1
        assert result.target_document_id == 2
        mock_db_connection.execute.assert_called_once()

    def test_citation_relation_repository_find_by_source_document(self, mock_db_connection):
        """Test finding relations by source document."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "id": 1,
            "source_document_id": 1,
            "source_citation_id": 1,
            "target_document_id": 2,
            "target_citation_id": 2,
            "relation_type": "cites",
            "confidence_score": 0.9,
            "created_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.find_by_source_document(1)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].source_document_id == 1
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_relation_repository_find_by_target_document(self, mock_db_connection):
        """Test finding relations by target document."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "id": 1,
            "source_document_id": 2,
            "source_citation_id": 3,
            "target_document_id": 1,
            "target_citation_id": 1,
            "relation_type": "cites",
            "confidence_score": 0.85,
            "created_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.find_by_target_document(1)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].target_document_id == 1
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_relation_repository_get_citation_network(self, mock_db_connection):
        """Test getting citation network for a document."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        # Mock database response - return empty relations for simplicity
        mock_db_connection.fetch_all.return_value = []
        
        # Act
        result = repo.get_citation_network(1, depth=1)
        
        # Assert
        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result
        assert "center_document" in result
        assert result["center_document"] == 1
        assert result["depth"] == 1
        # With empty relations, should still have the center document as a node
        assert len(result["nodes"]) >= 1

    def test_citation_relation_repository_get_most_cited_documents(self, mock_db_connection):
        """Test getting most cited documents."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        # Mock database response
        mock_rows = [{
            "document_id": 1,
            "title": "Popular Paper",
            "citation_count": 10,
            "created_at": "2023-01-01T12:00:00"
        }]
        mock_db_connection.fetch_all.return_value = mock_rows
        
        # Act
        result = repo.get_most_cited_documents(limit=5)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert "document_id" in result[0]
        assert "citation_count" in result[0]
        mock_db_connection.fetch_all.assert_called_once()

    def test_citation_relation_repository_cleanup_orphaned_relations(self, mock_db_connection):
        """Test cleaning up orphaned relations."""
        # Arrange
        from src.repositories.citation_relation_repository import CitationRelationRepository
        repo = CitationRelationRepository(mock_db_connection)
        
        # Mock database response
        mock_db_connection.execute.return_value = None
        mock_db_connection.get_last_change_count.side_effect = [1, 1, 1, 0]  # 4 SQL operations
        
        # Act
        result = repo.cleanup_orphaned_relations()
        
        # Assert
        assert result == 3  # 1 + 1 + 1 + 0 = 3
        mock_db_connection.execute.assert_called()


class TestCitationRepositorySOLIDCompliance:
    """Test SOLID principles compliance in citation repositories."""
    
    def test_single_responsibility_principle(self):
        """Test that each repository has a single responsibility."""
        # CitationRepository should only handle citation data operations
        # CitationRelationRepository should only handle relation operations
        from src.interfaces.repository_interfaces import ICitationRepository, ICitationRelationRepository
        
        # Check that interfaces are properly segregated
        citation_methods = [method for method in dir(ICitationRepository) if not method.startswith('_')]
        relation_methods = [method for method in dir(ICitationRelationRepository) if not method.startswith('_')]
        
        # Assert no overlap in responsibilities (method names should be distinct)
        assert "find_by_document_id" in citation_methods
        assert "get_citation_network" in relation_methods
        
        # Both should inherit from base IRepository interface
        from src.interfaces.repository_interfaces import IRepository
        assert issubclass(ICitationRepository, IRepository)
        assert issubclass(ICitationRelationRepository, IRepository)

    def test_interface_segregation_principle(self):
        """Test that interfaces are properly segregated."""
        from src.interfaces.repository_interfaces import (
            IRepository, ICitationRepository, ICitationRelationRepository
        )
        
        # Check that clients only depend on methods they need
        base_methods = {"create", "get_by_id", "update", "delete"}
        citation_specific = {"find_by_document_id", "search_by_author", "search_by_title"}
        relation_specific = {"find_by_source_document", "get_citation_network"}
        
        # Verify method separation
        citation_interface_methods = {
            method for method in dir(ICitationRepository) 
            if not method.startswith('_') and callable(getattr(ICitationRepository, method))
        }
        
        assert base_methods.issubset(citation_interface_methods)
        assert citation_specific.issubset(citation_interface_methods)
        assert not relation_specific.intersection(citation_interface_methods)

    def test_dependency_inversion_principle(self):
        """Test that repositories depend on abstractions, not concretions."""
        # This test will verify that repositories depend on DatabaseConnection interface
        # rather than concrete database implementations
        
        # Repositories should accept DatabaseConnection (abstraction) in constructor
        # This will be verified when we implement the actual repositories
        
        # For now, verify that interfaces exist and are properly abstract
        from src.interfaces.repository_interfaces import ICitationRepository
        
        # Check that interface methods are abstract
        assert hasattr(ICitationRepository, '__abstractmethods__')
        assert len(ICitationRepository.__abstractmethods__) > 0