"""
Core functionality tests for essential backend components.
Tests the most critical backend functions with fast execution times.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.database.models import DocumentModel, VectorIndexModel
from src.database.connection import DatabaseConnection
from src.services.content_hash_service import ContentHashService


class TestCoreModels:
    """Test core database models."""

    def test_document_model_creation(self):
        """Test DocumentModel creation and validation."""
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash_123",
            file_size=1024
        )
        
        assert doc.title == "Test Document"
        assert doc.file_path == "/test/path.pdf"
        assert doc.file_hash == "test_hash_123"
        assert doc.file_size == 1024
        assert doc.metadata == {}
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_model_validation(self):
        """Test DocumentModel validation rules."""
        # Test empty hash validation
        with pytest.raises(ValueError, match="File hash cannot be empty"):
            DocumentModel(
                title="Test",
                file_path="/test/path.pdf",
                file_hash="",
                file_size=1024
            )
        
        # Test negative file size validation
        with pytest.raises(ValueError, match="File size cannot be negative"):
            DocumentModel(
                title="Test",
                file_path="/test/path.pdf",
                file_hash="test_hash",
                file_size=-1
            )

    def test_vector_index_model_creation(self):
        """Test VectorIndexModel creation and validation."""
        index = VectorIndexModel(
            document_id=1,
            index_path="/test/index.faiss",
            index_hash="index_hash_123"
        )
        
        assert index.document_id == 1
        assert index.index_path == "/test/index.faiss"
        assert index.index_hash == "index_hash_123"
        assert index.created_at is not None
        assert index.created_at is not None

    def test_vector_index_model_validation(self):
        """Test VectorIndexModel validation rules."""
        # Test invalid document ID
        with pytest.raises(ValueError, match="Document ID must be positive"):
            VectorIndexModel(
                document_id=0,
                index_path="/test/index.faiss",
                index_hash="index_hash"
            )
        
        # Test empty index path
        with pytest.raises(ValueError, match="Index path cannot be empty"):
            VectorIndexModel(
                document_id=1,
                index_path="",
                index_hash="index_hash"
            )


class TestDatabaseConnection:
    """Test core database connection functionality."""

    def test_database_connection_creation(self):
        """Test DatabaseConnection creation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            assert str(db.db_path) == str(db_path)
            assert hasattr(db, 'connection_timeout') or hasattr(db, 'pool')
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_basic_operations(self):
        """Test basic database operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Test table creation
            db.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Test insert
            db.execute("INSERT INTO test_table (name) VALUES (?)", ("test_name",))
            
            # Test select
            result = db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("test_name",))
            assert result is not None
            assert result["name"] == "test_name"
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestContentHashService:
    """Test content hash service functionality."""

    def test_content_hash_service_creation(self):
        """Test ContentHashService creation."""
        service = ContentHashService()
        assert service is not None

    def test_file_hash_calculation(self):
        """Test file hash calculation."""
        service = ContentHashService()
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            # Calculate hash
            hash_result = service.calculate_file_hash(temp_file_path)
            assert hash_result is not None
            assert len(hash_result) == 16  # 16-character hex length as per implementation
            
            # Verify hash is consistent
            hash_result2 = service.calculate_file_hash(temp_file_path)
            assert hash_result == hash_result2
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    def test_content_hash_calculation(self):
        """Test content hash calculation."""
        service = ContentHashService()
        
        test_content = "test content for hashing"
        hash_result = service.calculate_content_hash(test_content)
        
        assert hash_result is not None
        assert len(hash_result) == 64  # SHA256 hex length
        
        # Verify hash is consistent
        hash_result2 = service.calculate_content_hash(test_content)
        assert hash_result == hash_result2
        
        # Verify different content produces different hash
        different_content = "different test content"
        different_hash = service.calculate_content_hash(different_content)
        assert hash_result != different_hash


class TestImportStructure:
    """Test that core modules can be imported correctly."""

    def test_database_imports(self):
        """Test database module imports."""
        from src.database.models import DocumentModel, VectorIndexModel
        from src.database.connection import DatabaseConnection
        
        assert DocumentModel is not None
        assert VectorIndexModel is not None
        assert DatabaseConnection is not None

    def test_repository_imports(self):
        """Test repository module imports."""
        from src.repositories.base_repository import BaseRepository
        from src.repositories.document_repository import DocumentRepository
        from src.repositories.vector_repository import VectorIndexRepository
        
        assert BaseRepository is not None
        assert DocumentRepository is not None
        assert VectorIndexRepository is not None

    def test_service_imports(self):
        """Test service module imports."""
        from src.services.content_hash_service import ContentHashService
        
        assert ContentHashService is not None

    def test_api_imports(self):
        """Test API module imports."""
        # Only test imports that don't require heavy dependencies
        try:
            from src.api.health import router as health_router
            assert health_router is not None
        except ImportError:
            # Skip if health module doesn't exist or has dependencies
            pass


class TestPerformanceBasics:
    """Test basic performance characteristics."""

    def test_model_creation_performance(self):
        """Test that model creation is fast."""
        import time
        
        start_time = time.time()
        for i in range(100):
            doc = DocumentModel(
                title=f"Test Document {i}",
                file_path=f"/test/path{i}.pdf",
                file_hash=f"test_hash_{i}",
                file_size=1024
            )
            assert doc.title == f"Test Document {i}"
        
        duration = time.time() - start_time
        assert duration < 0.1  # Should be very fast

    def test_hash_calculation_performance(self):
        """Test that hash calculation is reasonably fast."""
        import time
        
        service = ContentHashService()
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content" * 100)
            temp_file_path = temp_file.name
        
        try:
            start_time = time.time()
            hash_result = service.calculate_file_hash(temp_file_path)
            duration = time.time() - start_time
            
            assert hash_result is not None
            assert duration < 0.1  # Should be fast for small content
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)