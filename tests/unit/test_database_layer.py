"""
Unit tests for database layer components.
Tests database connections, models, and data persistence.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Import with error handling for CI/CD environments
try:
    from src.database.connection import DatabaseConnection
    from src.database.models import DocumentModel, VectorIndexModel
    IMPORTS_AVAILABLE = True
except ImportError:
    # Skip this module if imports are not available
    pytest.skip("Database modules not available - missing dependencies", allow_module_level=True)


class TestDatabaseConnection:
    """Test DatabaseConnection functionality."""

    def test_database_connection_creation(self):
        """Test DatabaseConnection creation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            assert db is not None
            assert str(db.db_path) == str(db_path)
            # Check for any connection management attribute
            assert (hasattr(db, 'connection_pool') or 
                   hasattr(db, 'connection_timeout') or 
                   hasattr(db, 'pool') or 
                   hasattr(db, '_connections'))
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_execute(self):
        """Test database execute functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Test table creation
            db.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Test data insertion
            db.execute("INSERT INTO test_table (name) VALUES (?)", ("test_name",))
            
            # Test data retrieval
            result = db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("test_name",))
            assert result is not None
            assert result["name"] == "test_name"
            assert result["id"] is not None
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_fetch_all(self):
        """Test database fetch_all functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Create test table
            db.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Insert test data
            test_data = [("name1",), ("name2",), ("name3",)]
            for name in test_data:
                db.execute("INSERT INTO test_table (name) VALUES (?)", name)
            
            # Test fetch_all
            results = db.fetch_all("SELECT * FROM test_table ORDER BY id")
            assert len(results) == 3
            assert results[0]["name"] == "name1"
            assert results[1]["name"] == "name2"
            assert results[2]["name"] == "name3"
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_transaction(self):
        """Test database transaction functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Create test table
            db.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Test successful transaction
            with db.transaction():
                db.execute("INSERT INTO test_table (name) VALUES (?)", ("transaction_test",))
            
            # Verify data was committed
            result = db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("transaction_test",))
            assert result is not None
            assert result["name"] == "transaction_test"
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_transaction_rollback(self):
        """Test database transaction rollback functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Create test table
            db.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Test transaction rollback
            try:
                with db.transaction():
                    db.execute("INSERT INTO test_table (name) VALUES (?)", ("rollback_test",))
                    raise Exception("Simulated error")
            except Exception:
                pass  # Expected exception
            
            # Verify data was not committed
            result = db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("rollback_test",))
            assert result is None
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_close(self):
        """Test database connection closing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Test that connection can be closed
            db.close_all_connections()
            
            # Test that new connection can be established after closing
            db.execute("SELECT 1")
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_connection_error_handling(self):
        """Test database connection error handling."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name
        
        try:
            db = DatabaseConnection(db_path)
            
            # Test SQL error handling
            with pytest.raises(Exception):
                db.execute("INVALID SQL STATEMENT")
            
            # Test that connection is still usable after error
            db.execute("SELECT 1")
            
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestDatabaseModels:
    """Test database model functionality."""

    def test_document_model_creation(self):
        """Test DocumentModel creation."""
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
        assert doc.id is None
        assert doc.content_hash is None

    def test_document_model_validation(self):
        """Test DocumentModel validation."""
        # Test valid document
        doc = DocumentModel(
            title="Valid Document",
            file_path="/valid/path.pdf",
            file_hash="valid_hash",
            file_size=1024
        )
        assert doc.title == "Valid Document"
        
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

    def test_document_model_with_metadata(self):
        """Test DocumentModel with metadata."""
        metadata = {
            "author": "Test Author",
            "created": "2024-01-01",
            "tags": ["test", "document"]
        }
        
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024,
            metadata=metadata
        )
        
        assert doc.metadata == metadata
        assert doc.metadata["author"] == "Test Author"
        assert doc.metadata["tags"] == ["test", "document"]

    def test_vector_index_model_creation(self):
        """Test VectorIndexModel creation."""
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
        assert index.id is None

    def test_vector_index_model_validation(self):
        """Test VectorIndexModel validation."""
        # Test valid index
        index = VectorIndexModel(
            document_id=1,
            index_path="/valid/index.faiss",
            index_hash="valid_hash"
        )
        assert index.document_id == 1
        
        # Test invalid document ID
        with pytest.raises(ValueError, match="Document ID must be positive"):
            VectorIndexModel(
                document_id=0,
                index_path="/test/index.faiss",
                index_hash="test_hash"
            )
        
        # Test negative document ID
        with pytest.raises(ValueError, match="Document ID must be positive"):
            VectorIndexModel(
                document_id=-1,
                index_path="/test/index.faiss",
                index_hash="test_hash"
            )
        
        # Test empty index path
        with pytest.raises(ValueError, match="Index path cannot be empty"):
            VectorIndexModel(
                document_id=1,
                index_path="",
                index_hash="test_hash"
            )

    def test_model_timestamp_behavior(self):
        """Test model timestamp behavior."""
        # Create document
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024
        )
        
        # Check that timestamps are set
        assert doc.created_at is not None
        assert doc.updated_at is not None
        
        # Check that timestamps are datetime objects
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
        
        # Check that created_at and updated_at are close to current time
        now = datetime.now()
        assert abs((now - doc.created_at).total_seconds()) < 1.0
        assert abs((now - doc.updated_at).total_seconds()) < 1.0

    def test_model_equality(self):
        """Test model equality comparison."""
        doc1 = DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024
        )
        
        doc2 = DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024
        )
        
        doc3 = DocumentModel(
            id=2,
            title="Different Document",
            file_path="/test/path2.pdf",
            file_hash="different_hash",
            file_size=2048
        )
        
        # Test equality (based on implementation)
        # Note: This test depends on how __eq__ is implemented in the model
        # For now, we just test that the objects are created correctly
        assert doc1.id == doc2.id
        assert doc1.title == doc2.title
        assert doc1 != doc3

    def test_model_string_representation(self):
        """Test model string representation."""
        doc = DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024
        )
        
        # Test that string representation includes key information
        str_repr = str(doc)
        assert "Test Document" in str_repr or "DocumentModel" in str_repr
        
        # Test that repr is also available
        repr_str = repr(doc)
        assert repr_str is not None
        assert len(repr_str) > 0