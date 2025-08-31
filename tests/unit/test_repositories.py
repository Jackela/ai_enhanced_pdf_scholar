"""
Unit tests for Repository Layer - Database abstraction and data access.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import CitationModel, CitationRelationModel, DocumentModel
from src.repositories.base_repository import BaseRepository
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.repositories.document_repository import DocumentRepository


class TestBaseRepository:
    """Test suite for BaseRepository functionality."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        conn = Mock(spec=DatabaseConnection)
        conn.execute.return_value = Mock()
        conn.fetch_one.return_value = None
        conn.fetch_all.return_value = []
        conn.commit.return_value = None
        return conn

    @pytest.fixture
    def base_repository(self, mock_db_connection):
        """Create a BaseRepository instance."""
        repo = BaseRepository(mock_db_connection)
        repo.table_name = "test_table"
        repo.model_class = Mock
        return repo

    def test_base_repository_initialization(self, base_repository):
        """Test BaseRepository initialization."""
        assert base_repository is not None
        assert base_repository.table_name == "test_table"
        assert base_repository.db_connection is not None

    def test_execute_query(self, base_repository, mock_db_connection):
        """Test executing a query through base repository."""
        # Arrange
        query = "SELECT * FROM test_table WHERE id = ?"
        params = (1,)

        # Act
        base_repository._execute_query(query, params)

        # Assert
        mock_db_connection.execute.assert_called_once_with(query, params)

    def test_fetch_one(self, base_repository, mock_db_connection):
        """Test fetching single result."""
        # Arrange
        mock_db_connection.fetch_one.return_value = {"id": 1, "name": "Test"}
        query = "SELECT * FROM test_table WHERE id = ?"

        # Act
        result = base_repository._fetch_one(query, (1,))

        # Assert
        assert result == {"id": 1, "name": "Test"}
        mock_db_connection.execute.assert_called_once_with(query, (1,))
        mock_db_connection.fetch_one.assert_called_once()

    def test_fetch_all(self, base_repository, mock_db_connection):
        """Test fetching multiple results."""
        # Arrange
        mock_db_connection.fetch_all.return_value = [
            {"id": 1, "name": "Test1"},
            {"id": 2, "name": "Test2"}
        ]
        query = "SELECT * FROM test_table"

        # Act
        result = base_repository._fetch_all(query)

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "Test1"
        mock_db_connection.execute.assert_called_once_with(query, ())
        mock_db_connection.fetch_all.assert_called_once()


class TestDocumentRepository:
    """Test suite for DocumentRepository."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        conn = Mock(spec=DatabaseConnection)
        conn.execute.return_value = Mock()
        conn.fetch_one.return_value = None
        conn.fetch_all.return_value = []
        conn.commit.return_value = None
        conn.lastrowid = 1
        return conn

    @pytest.fixture
    def document_repository(self, mock_db_connection):
        """Create a DocumentRepository instance."""
        return DocumentRepository(mock_db_connection)

    def test_save_document(self, document_repository, mock_db_connection):
        """Test saving a document."""
        # Arrange
        document = DocumentModel(
            title="Test Document",
            file_path="/path/to/doc.pdf",
            content="Test content",
            content_hash="abc123"
        )
        mock_db_connection.lastrowid = 10

        # Act
        result = document_repository.save(document)

        # Assert
        mock_db_connection.execute.assert_called()
        assert result.id == 10
        query = mock_db_connection.execute.call_args[0][0]
        assert "INSERT INTO documents" in query

    def test_find_document_by_id(self, document_repository, mock_db_connection):
        """Test finding a document by ID."""
        # Arrange
        mock_db_connection.fetch_one.return_value = {
            "id": 1,
            "title": "Found Document",
            "file_path": "/path/to/found.pdf",
            "content": "Content",
            "content_hash": "hash123",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        }

        # Act
        result = document_repository.find_by_id(1)

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.title == "Found Document"
        query = mock_db_connection.execute.call_args[0][0]
        assert "SELECT * FROM documents WHERE id = ?" in query

    def test_find_all_documents(self, document_repository, mock_db_connection):
        """Test finding all documents."""
        # Arrange
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "title": "Doc 1",
                "file_path": "/path1.pdf",
                "content": "Content 1",
                "content_hash": "hash1",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01"
            },
            {
                "id": 2,
                "title": "Doc 2",
                "file_path": "/path2.pdf",
                "content": "Content 2",
                "content_hash": "hash2",
                "created_at": "2024-01-02",
                "updated_at": "2024-01-02"
            }
        ]

        # Act
        result = document_repository.find_all()

        # Assert
        assert len(result) == 2
        assert result[0].title == "Doc 1"
        assert result[1].title == "Doc 2"

    def test_update_document(self, document_repository, mock_db_connection):
        """Test updating a document."""
        # Arrange
        document = DocumentModel(
            id=1,
            title="Updated Document",
            file_path="/updated/path.pdf",
            content="Updated content",
            content_hash="newhash"
        )

        # Act
        result = document_repository.update(document)

        # Assert
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "UPDATE documents SET" in query
        assert result is True

    def test_delete_document(self, document_repository, mock_db_connection):
        """Test deleting a document."""
        # Arrange
        document_id = 1

        # Act
        result = document_repository.delete(document_id)

        # Assert
        mock_db_connection.execute.assert_called_once()
        query = mock_db_connection.execute.call_args[0][0]
        assert "DELETE FROM documents WHERE id = ?" in query
        assert result is True

    def test_find_by_content_hash(self, document_repository, mock_db_connection):
        """Test finding document by content hash."""
        # Arrange
        content_hash = "unique_hash_123"
        mock_db_connection.fetch_one.return_value = {
            "id": 5,
            "title": "Document with hash",
            "file_path": "/path.pdf",
            "content": "Content",
            "content_hash": content_hash,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        }

        # Act
        result = document_repository.find_by_content_hash(content_hash)

        # Assert
        assert result is not None
        assert result.content_hash == content_hash
        query = mock_db_connection.execute.call_args[0][0]
        assert "WHERE content_hash = ?" in query

    def test_search_documents(self, document_repository, mock_db_connection):
        """Test searching documents by query."""
        # Arrange
        search_query = "machine learning"
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "title": "Machine Learning Basics",
                "file_path": "/ml.pdf",
                "content": "Introduction to machine learning",
                "content_hash": "mlhash",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01"
            }
        ]

        # Act
        result = document_repository.search(search_query)

        # Assert
        assert len(result) == 1
        assert "Machine Learning" in result[0].title
        query = mock_db_connection.execute.call_args[0][0]
        assert "LIKE" in query


class TestCitationRepository:
    """Test suite for CitationRepository."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        conn = Mock(spec=DatabaseConnection)
        conn.execute.return_value = Mock()
        conn.fetch_one.return_value = None
        conn.fetch_all.return_value = []
        conn.commit.return_value = None
        conn.lastrowid = 1
        return conn

    @pytest.fixture
    def citation_repository(self, mock_db_connection):
        """Create a CitationRepository instance."""
        return CitationRepository(mock_db_connection)

    def test_save_citation(self, citation_repository, mock_db_connection):
        """Test saving a citation."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            citation_text="Smith et al. (2024)",
            authors="Smith, J., Doe, J.",
            year=2024,
            title="Test Paper"
        )
        mock_db_connection.lastrowid = 5

        # Act
        result = citation_repository.save(citation)

        # Assert
        assert result.id == 5
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "INSERT INTO citations" in query

    def test_find_citations_by_document(self, citation_repository, mock_db_connection):
        """Test finding citations by document ID."""
        # Arrange
        document_id = 1
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "document_id": 1,
                "citation_text": "Citation 1",
                "authors": "Author A",
                "year": 2023,
                "title": "Paper 1",
                "created_at": "2024-01-01"
            },
            {
                "id": 2,
                "document_id": 1,
                "citation_text": "Citation 2",
                "authors": "Author B",
                "year": 2024,
                "title": "Paper 2",
                "created_at": "2024-01-02"
            }
        ]

        # Act
        result = citation_repository.find_by_document_id(document_id)

        # Assert
        assert len(result) == 2
        assert result[0].citation_text == "Citation 1"
        assert result[1].year == 2024

    def test_find_citation_by_id(self, citation_repository, mock_db_connection):
        """Test finding a citation by ID."""
        # Arrange
        citation_id = 1
        mock_db_connection.fetch_one.return_value = {
            "id": citation_id,
            "document_id": 1,
            "citation_text": "Found Citation",
            "authors": "Found Author",
            "year": 2024,
            "title": "Found Title",
            "created_at": "2024-01-01"
        }

        # Act
        result = citation_repository.find_by_id(citation_id)

        # Assert
        assert result is not None
        assert result.id == citation_id
        assert result.citation_text == "Found Citation"

    def test_update_citation(self, citation_repository, mock_db_connection):
        """Test updating a citation."""
        # Arrange
        citation = CitationModel(
            id=1,
            document_id=1,
            citation_text="Updated Citation",
            authors="Updated Author",
            year=2025,
            title="Updated Title"
        )

        # Act
        result = citation_repository.update(citation)

        # Assert
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "UPDATE citations SET" in query
        assert result is True

    def test_delete_citation(self, citation_repository, mock_db_connection):
        """Test deleting a citation."""
        # Arrange
        citation_id = 1

        # Act
        result = citation_repository.delete(citation_id)

        # Assert
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "DELETE FROM citations WHERE id = ?" in query
        assert result is True

    def test_search_citations(self, citation_repository, mock_db_connection):
        """Test searching citations."""
        # Arrange
        search_query = "neural networks"
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "document_id": 1,
                "citation_text": "Neural Networks Paper",
                "authors": "AI Researcher",
                "year": 2024,
                "title": "Deep Neural Networks",
                "created_at": "2024-01-01"
            }
        ]

        # Act
        result = citation_repository.search(search_query)

        # Assert
        assert len(result) == 1
        assert "Neural Networks" in result[0].citation_text
        query = mock_db_connection.execute.call_args[0][0]
        assert "LIKE" in query

    def test_find_duplicate_citation(self, citation_repository, mock_db_connection):
        """Test finding duplicate citations."""
        # Arrange
        citation = CitationModel(
            document_id=1,
            citation_text="Duplicate Citation",
            authors="Same Author",
            year=2024
        )
        mock_db_connection.fetch_one.return_value = {
            "id": 10,
            "document_id": 1,
            "citation_text": "Duplicate Citation",
            "authors": "Same Author",
            "year": 2024,
            "title": None,
            "created_at": "2024-01-01"
        }

        # Act
        result = citation_repository.find_duplicate(citation)

        # Assert
        assert result is not None
        assert result.id == 10
        query = mock_db_connection.execute.call_args[0][0]
        assert "citation_text = ?" in query
        assert "authors = ?" in query


class TestCitationRelationRepository:
    """Test suite for CitationRelationRepository."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        conn = Mock(spec=DatabaseConnection)
        conn.execute.return_value = Mock()
        conn.fetch_one.return_value = None
        conn.fetch_all.return_value = []
        conn.commit.return_value = None
        conn.lastrowid = 1
        return conn

    @pytest.fixture
    def relation_repository(self, mock_db_connection):
        """Create a CitationRelationRepository instance."""
        return CitationRelationRepository(mock_db_connection)

    def test_save_relation(self, relation_repository, mock_db_connection):
        """Test saving a citation relation."""
        # Arrange
        relation = CitationRelationModel(
            source_citation_id=1,
            target_citation_id=2,
            relation_type="cites"
        )
        mock_db_connection.lastrowid = 3

        # Act
        result = relation_repository.save(relation)

        # Assert
        assert result.id == 3
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "INSERT INTO citation_relations" in query

    def test_find_relations_by_citation(self, relation_repository, mock_db_connection):
        """Test finding relations by citation ID."""
        # Arrange
        citation_id = 1
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "source_citation_id": 1,
                "target_citation_id": 2,
                "relation_type": "cites",
                "created_at": "2024-01-01"
            },
            {
                "id": 2,
                "source_citation_id": 3,
                "target_citation_id": 1,
                "relation_type": "cited_by",
                "created_at": "2024-01-02"
            }
        ]

        # Act
        result = relation_repository.find_by_citation_id(citation_id)

        # Assert
        assert len(result) == 2
        assert result[0].relation_type == "cites"
        assert result[1].relation_type == "cited_by"

    def test_delete_relations_by_citation(self, relation_repository, mock_db_connection):
        """Test deleting all relations for a citation."""
        # Arrange
        citation_id = 1

        # Act
        result = relation_repository.delete_by_citation_id(citation_id)

        # Assert
        mock_db_connection.execute.assert_called()
        query = mock_db_connection.execute.call_args[0][0]
        assert "DELETE FROM citation_relations WHERE" in query
        assert "source_citation_id = ? OR target_citation_id = ?" in query
        assert result is True

    def test_find_relation_by_id(self, relation_repository, mock_db_connection):
        """Test finding a relation by ID."""
        # Arrange
        relation_id = 1
        mock_db_connection.fetch_one.return_value = {
            "id": relation_id,
            "source_citation_id": 1,
            "target_citation_id": 2,
            "relation_type": "cites",
            "created_at": "2024-01-01"
        }

        # Act
        result = relation_repository.find_by_id(relation_id)

        # Assert
        assert result is not None
        assert result.id == relation_id
        assert result.relation_type == "cites"

    def test_find_relations_by_type(self, relation_repository, mock_db_connection):
        """Test finding relations by type."""
        # Arrange
        relation_type = "cites"
        mock_db_connection.fetch_all.return_value = [
            {
                "id": 1,
                "source_citation_id": 1,
                "target_citation_id": 2,
                "relation_type": "cites",
                "created_at": "2024-01-01"
            },
            {
                "id": 2,
                "source_citation_id": 3,
                "target_citation_id": 4,
                "relation_type": "cites",
                "created_at": "2024-01-02"
            }
        ]

        # Act
        result = relation_repository.find_by_type(relation_type)

        # Assert
        assert len(result) == 2
        assert all(r.relation_type == "cites" for r in result)
        query = mock_db_connection.execute.call_args[0][0]
        assert "WHERE relation_type = ?" in query
