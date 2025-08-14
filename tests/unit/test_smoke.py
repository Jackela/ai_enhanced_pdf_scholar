"""
Smoke tests for basic functionality.
Ensures core modules can be imported and basic functionality works.
"""

import pytest
from pathlib import Path


def test_imports():
    """Test that core modules can be imported."""
    # Test database models
    from src.database.models import DocumentModel, VectorIndexModel
    assert DocumentModel is not None
    assert VectorIndexModel is not None

    # Test database connection
    from src.database.connection import DatabaseConnection
    assert DatabaseConnection is not None

    # Test repositories
    from src.repositories.document_repository import DocumentRepository
    from src.repositories.vector_repository import VectorIndexRepository
    assert DocumentRepository is not None
    assert VectorIndexRepository is not None


def test_document_model_creation():
    """Test basic DocumentModel creation."""
    from src.database.models import DocumentModel

    doc = DocumentModel(
        title="Test Document",
        file_path="/test/path.pdf",
        file_hash="test_hash_123",
        file_size=1024
    )

    assert doc.title == "Test Document"
    assert doc.file_hash == "test_hash_123"
    assert doc.file_size == 1024


def test_vector_index_model_creation():
    """Test basic VectorIndexModel creation."""
    from src.database.models import VectorIndexModel

    index = VectorIndexModel(
        document_id=1,
        index_path="/test/index.faiss",
        index_hash="index_hash_123"
    )

    assert index.document_id == 1
    assert index.index_path == "/test/index.faiss"
    assert index.index_hash == "index_hash_123"


def test_model_validation():
    """Test model validation logic."""
    from src.database.models import DocumentModel, VectorIndexModel

    # Test DocumentModel validation
    with pytest.raises(ValueError, match="File hash cannot be empty"):
        DocumentModel(
            title="Test",
            file_path="/test/path.pdf",
            file_hash="",  # Empty hash should raise error
            file_size=1024
        )

    with pytest.raises(ValueError, match="File size cannot be negative"):
        DocumentModel(
            title="Test",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=-1  # Negative size should raise error
        )

    # Test VectorIndexModel validation
    with pytest.raises(ValueError, match="Document ID must be positive"):
        VectorIndexModel(
            document_id=0,  # Invalid ID
            index_path="/test/index.faiss",
            index_hash="index_hash"
        )

    with pytest.raises(ValueError, match="Index path cannot be empty"):
        VectorIndexModel(
            document_id=1,
            index_path="",  # Empty path should raise error
            index_hash="index_hash"
        )


def test_model_defaults():
    """Test model default values and post-init behavior."""
    from src.database.models import DocumentModel

    doc = DocumentModel(
        title="Test Document",
        file_path="/test/path.pdf",
        file_hash="test_hash",
        file_size=1024
    )

    # Check that defaults are set
    assert doc.metadata == {}
    assert doc.created_at is not None
    assert doc.updated_at is not None
    assert doc.content_hash is None
    assert doc.id is None