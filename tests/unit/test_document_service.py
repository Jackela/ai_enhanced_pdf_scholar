"""
Unit tests for DocumentService - Document management business logic.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from src.database.models import DocumentModel
from src.exceptions.document import DocumentNotFoundError, DuplicateDocumentError
from src.repositories.document_repository import DocumentRepository
from src.services.content_hash_service import ContentHashService
from src.services.document_service import DocumentService


class TestDocumentService:
    """Test suite for DocumentService."""

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.find_all.return_value = []
        repo.find_by_id.return_value = None
        repo.save.return_value = DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test.pdf",
            content="Test content",
            content_hash="testhash123"
        )
        repo.update.return_value = True
        repo.delete.return_value = True
        return repo

    @pytest.fixture
    def mock_hash_service(self):
        """Create a mock content hash service."""
        service = Mock(spec=ContentHashService)
        service.calculate_content_hash.return_value = "contenthash123"
        service.calculate_file_hash.return_value = "filehash123"
        service.verify_file_integrity.return_value = True
        return service

    @pytest.fixture
    def document_service(self, mock_document_repo, mock_hash_service):
        """Create a DocumentService instance with mocked dependencies."""
        return DocumentService(
            document_repository=mock_document_repo,
            hash_service=mock_hash_service
        )

    def test_service_initialization(self, document_service):
        """Test DocumentService initialization."""
        assert document_service is not None
        assert document_service.document_repository is not None
        assert document_service.hash_service is not None

    def test_create_document(self, document_service, mock_document_repo, mock_hash_service):
        """Test creating a new document."""
        # Arrange
        document_data = {
            "title": "New Document",
            "file_path": "/path/to/new.pdf",
            "content": "Document content"
        }

        # Act
        result = document_service.create_document(document_data)

        # Assert
        mock_hash_service.calculate_content_hash.assert_called_once_with("Document content")
        mock_document_repo.save.assert_called_once()
        saved_doc = mock_document_repo.save.call_args[0][0]
        assert saved_doc.title == "New Document"
        assert saved_doc.content_hash == "contenthash123"
        assert result.id == 1

    def test_get_document_by_id(self, document_service, mock_document_repo):
        """Test retrieving a document by ID."""
        # Arrange
        document_id = 1
        mock_document = DocumentModel(
            id=document_id,
            title="Found Document",
            file_path="/found.pdf",
            content="Content",
            content_hash="hash123"
        )
        mock_document_repo.find_by_id.return_value = mock_document

        # Act
        result = document_service.get_document(document_id)

        # Assert
        mock_document_repo.find_by_id.assert_called_once_with(document_id)
        assert result.id == document_id
        assert result.title == "Found Document"

    def test_get_document_not_found(self, document_service, mock_document_repo):
        """Test retrieving non-existent document raises error."""
        # Arrange
        mock_document_repo.find_by_id.return_value = None

        # Act & Assert
        with pytest.raises(DocumentNotFoundError):
            document_service.get_document(999)

    def test_update_document(self, document_service, mock_document_repo, mock_hash_service):
        """Test updating an existing document."""
        # Arrange
        document_id = 1
        existing_doc = DocumentModel(
            id=document_id,
            title="Old Title",
            file_path="/old.pdf",
            content="Old content",
            content_hash="oldhash"
        )
        mock_document_repo.find_by_id.return_value = existing_doc

        update_data = {
            "title": "Updated Title",
            "content": "Updated content"
        }

        # Act
        result = document_service.update_document(document_id, update_data)

        # Assert
        mock_document_repo.find_by_id.assert_called_once_with(document_id)
        mock_hash_service.calculate_content_hash.assert_called_with("Updated content")
        mock_document_repo.update.assert_called_once()
        updated_doc = mock_document_repo.update.call_args[0][0]
        assert updated_doc.title == "Updated Title"
        assert updated_doc.content == "Updated content"

    def test_delete_document(self, document_service, mock_document_repo):
        """Test deleting a document."""
        # Arrange
        document_id = 1
        mock_document = DocumentModel(
            id=document_id,
            title="To Delete",
            file_path="/delete.pdf",
            content="Content",
            content_hash="hash"
        )
        mock_document_repo.find_by_id.return_value = mock_document

        # Act
        result = document_service.delete_document(document_id)

        # Assert
        mock_document_repo.find_by_id.assert_called_once_with(document_id)
        mock_document_repo.delete.assert_called_once_with(document_id)
        assert result is True

    def test_get_all_documents(self, document_service, mock_document_repo):
        """Test retrieving all documents."""
        # Arrange
        mock_documents = [
            DocumentModel(id=1, title="Doc 1", file_path="/1.pdf", content="", content_hash="h1"),
            DocumentModel(id=2, title="Doc 2", file_path="/2.pdf", content="", content_hash="h2"),
            DocumentModel(id=3, title="Doc 3", file_path="/3.pdf", content="", content_hash="h3")
        ]
        mock_document_repo.find_all.return_value = mock_documents

        # Act
        result = document_service.get_all_documents()

        # Assert
        mock_document_repo.find_all.assert_called_once()
        assert len(result) == 3
        assert result[0].title == "Doc 1"
        assert result[2].title == "Doc 3"

    def test_search_documents(self, document_service, mock_document_repo):
        """Test searching documents."""
        # Arrange
        query = "machine learning"
        mock_results = [
            DocumentModel(
                id=1,
                title="Machine Learning Guide",
                file_path="/ml.pdf",
                content="ML content",
                content_hash="mlhash"
            )
        ]
        mock_document_repo.search.return_value = mock_results

        # Act
        result = document_service.search_documents(query)

        # Assert
        mock_document_repo.search.assert_called_once_with(query)
        assert len(result) == 1
        assert "Machine Learning" in result[0].title

    def test_check_duplicate_document(self, document_service, mock_document_repo, mock_hash_service):
        """Test checking for duplicate documents."""
        # Arrange
        content = "Document content"
        content_hash = "hash123"
        mock_hash_service.calculate_content_hash.return_value = content_hash

        existing_doc = DocumentModel(
            id=1,
            title="Existing",
            file_path="/existing.pdf",
            content=content,
            content_hash=content_hash
        )
        mock_document_repo.find_by_content_hash.return_value = existing_doc

        # Act
        is_duplicate = document_service.check_duplicate(content)

        # Assert
        mock_hash_service.calculate_content_hash.assert_called_once_with(content)
        mock_document_repo.find_by_content_hash.assert_called_once_with(content_hash)
        assert is_duplicate is True

    def test_verify_document_integrity(self, document_service, mock_document_repo, mock_hash_service):
        """Test verifying document integrity."""
        # Arrange
        document_id = 1
        document = DocumentModel(
            id=document_id,
            title="Test",
            file_path="/test.pdf",
            content="Content",
            content_hash="originalhash"
        )
        mock_document_repo.find_by_id.return_value = document
        mock_hash_service.calculate_content_hash.return_value = "originalhash"

        # Act
        is_valid = document_service.verify_integrity(document_id)

        # Assert
        mock_document_repo.find_by_id.assert_called_once_with(document_id)
        mock_hash_service.calculate_content_hash.assert_called_once_with("Content")
        assert is_valid is True

    def test_verify_document_integrity_failed(self, document_service, mock_document_repo, mock_hash_service):
        """Test failed document integrity verification."""
        # Arrange
        document_id = 1
        document = DocumentModel(
            id=document_id,
            title="Test",
            file_path="/test.pdf",
            content="Content",
            content_hash="originalhash"
        )
        mock_document_repo.find_by_id.return_value = document
        mock_hash_service.calculate_content_hash.return_value = "differenthash"

        # Act
        is_valid = document_service.verify_integrity(document_id)

        # Assert
        assert is_valid is False

    def test_batch_create_documents(self, document_service, mock_document_repo, mock_hash_service):
        """Test batch creating multiple documents."""
        # Arrange
        documents_data = [
            {"title": "Doc 1", "content": "Content 1", "file_path": "/1.pdf"},
            {"title": "Doc 2", "content": "Content 2", "file_path": "/2.pdf"},
            {"title": "Doc 3", "content": "Content 3", "file_path": "/3.pdf"}
        ]

        mock_document_repo.save.side_effect = [
            DocumentModel(id=i+1, title=f"Doc {i+1}", file_path=f"/{i+1}.pdf",
                         content=f"Content {i+1}", content_hash=f"hash{i+1}")
            for i in range(3)
        ]

        # Act
        result = document_service.batch_create(documents_data)

        # Assert
        assert mock_document_repo.save.call_count == 3
        assert len(result) == 3
        assert result[0].id == 1
        assert result[2].title == "Doc 3"

    def test_get_document_statistics(self, document_service, mock_document_repo):
        """Test getting document statistics."""
        # Arrange
        mock_documents = [
            DocumentModel(id=1, title="PDF 1", file_path="/1.pdf", content="", content_hash="h1"),
            DocumentModel(id=2, title="PDF 2", file_path="/2.pdf", content="", content_hash="h2"),
            DocumentModel(id=3, title="TXT 1", file_path="/1.txt", content="", content_hash="h3")
        ]
        mock_document_repo.find_all.return_value = mock_documents

        # Act
        stats = document_service.get_statistics()

        # Assert
        assert stats["total_documents"] == 3
        assert stats["document_types"]["pdf"] == 2
        assert stats["document_types"]["txt"] == 1

    def test_export_document(self, document_service, mock_document_repo):
        """Test exporting a document."""
        # Arrange
        document_id = 1
        document = DocumentModel(
            id=document_id,
            title="Export Test",
            file_path="/export.pdf",
            content="Export content",
            content_hash="exporthash",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 2)
        )
        mock_document_repo.find_by_id.return_value = document

        # Act
        exported = document_service.export_document(document_id)

        # Assert
        assert exported["id"] == document_id
        assert exported["title"] == "Export Test"
        assert exported["content"] == "Export content"
        assert "metadata" in exported
        assert exported["metadata"]["content_hash"] == "exporthash"

    def test_import_document(self, document_service, mock_document_repo, mock_hash_service):
        """Test importing a document."""
        # Arrange
        import_data = {
            "title": "Imported Document",
            "content": "Imported content",
            "file_path": "/imported.pdf",
            "metadata": {
                "original_hash": "importhash",
                "source": "external_system"
            }
        }

        # Act
        result = document_service.import_document(import_data)

        # Assert
        mock_hash_service.calculate_content_hash.assert_called_once_with("Imported content")
        mock_document_repo.save.assert_called_once()
        saved_doc = mock_document_repo.save.call_args[0][0]
        assert saved_doc.title == "Imported Document"

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.unlink')
    def test_delete_document_with_file(self, mock_unlink, mock_exists,
                                       document_service, mock_document_repo):
        """Test deleting a document also deletes the file."""
        # Arrange
        document_id = 1
        document = DocumentModel(
            id=document_id,
            title="Delete with file",
            file_path="/delete_me.pdf",
            content="Content",
            content_hash="hash"
        )
        mock_document_repo.find_by_id.return_value = document
        mock_exists.return_value = True

        # Act
        result = document_service.delete_document(document_id, delete_file=True)

        # Assert
        mock_document_repo.delete.assert_called_once_with(document_id)
        mock_exists.assert_called_once()
        mock_unlink.assert_called_once()
        assert result is True
