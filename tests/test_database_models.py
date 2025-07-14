"""
Test Database Models

Unit tests for database model classes, focusing on data validation,
serialization, and factory methods.
"""

import pytest
import tempfile
import json
from datetime import datetime
from pathlib import Path

from src.database.models import DocumentModel, VectorIndexModel, TagModel


class TestDocumentModel:
    """Test cases for DocumentModel class."""
    
    def setup_method(self):
        """Set up test data for each test."""
        self.test_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        self.test_file.write(b"dummy PDF content")
        self.test_file.close()
        self.test_path = self.test_file.name
    
    def teardown_method(self):
        """Clean up after each test."""
        Path(self.test_path).unlink(missing_ok=True)
    
    def test_document_model_creation_minimal(self):
        """Test creating DocumentModel with minimal required fields."""
        doc = DocumentModel(
            title="Test Document",
            file_path=self.test_path,
            file_hash="abc123def456",
            file_size=1024
        )
        
        assert doc.title == "Test Document"
        assert doc.file_path == self.test_path
        assert doc.file_hash == "abc123def456"
        assert doc.file_size == 1024
        assert doc.id is None
        assert doc.page_count is None
        assert doc.created_at is not None
        assert doc.updated_at is not None
        assert doc.last_accessed is None
        assert doc.metadata == {}
    
    def test_document_model_creation_complete(self):
        """Test creating DocumentModel with all fields."""
        now = datetime.now()
        metadata = {"author": "Test Author", "subject": "Test Subject"}
        
        doc = DocumentModel(
            id=1,
            title="Complete Document",
            file_path=self.test_path,
            file_hash="xyz789abc123",
            file_size=2048,
            page_count=10,
            created_at=now,
            updated_at=now,
            last_accessed=now,
            metadata=metadata
        )
        
        assert doc.id == 1
        assert doc.title == "Complete Document"
        assert doc.page_count == 10
        assert doc.created_at == now
        assert doc.metadata == metadata
    
    def test_document_model_allows_empty_title(self):
        """Test that empty title is allowed with fallback logic."""
        # Empty title should be allowed
        doc = DocumentModel(
            title="",
            file_path=self.test_path,
            file_hash="abc123",
            file_size=1024
        )
        assert doc.title == ""
        
        # Whitespace-only title should be allowed
        doc = DocumentModel(
            title="   ",
            file_path=self.test_path,
            file_hash="abc123",
            file_size=1024
        )
        assert doc.title == "   "
    
    def test_document_model_validation_empty_hash(self):
        """Test validation fails for empty file hash."""
        with pytest.raises(ValueError, match="File hash cannot be empty"):
            DocumentModel(
                title="Test",
                file_path=self.test_path,
                file_hash="",
                file_size=1024
            )
    
    def test_document_model_validation_negative_size(self):
        """Test validation fails for negative file size."""
        with pytest.raises(ValueError, match="File size cannot be negative"):
            DocumentModel(
                title="Test",
                file_path=self.test_path,
                file_hash="abc123",
                file_size=-1
            )
    
    def test_from_file_factory_method(self):
        """Test creating DocumentModel from file using factory method."""
        doc = DocumentModel.from_file(
            file_path=self.test_path,
            file_hash="test_hash",
            title="Custom Title"
        )
        
        assert doc.title == "Custom Title"
        assert doc.file_path == str(Path(self.test_path).absolute())
        assert doc.file_hash == "test_hash"
        assert doc.file_size > 0
        assert "file_extension" in doc.metadata
        assert "original_filename" in doc.metadata
        assert "file_modified_at" in doc.metadata
    
    def test_from_file_factory_auto_title(self):
        """Test from_file with automatic title extraction."""
        doc = DocumentModel.from_file(
            file_path=self.test_path,
            file_hash="test_hash"
        )
        
        # Title should be extracted from filename (without extension)
        expected_title = Path(self.test_path).stem
        assert doc.title == expected_title
    
    def test_from_file_factory_nonexistent_file(self):
        """Test from_file with non-existent file."""
        with pytest.raises(FileNotFoundError):
            DocumentModel.from_file(
                file_path="/nonexistent/file.pdf",
                file_hash="test_hash"
            )
    
    def test_from_database_row_factory(self):
        """Test creating DocumentModel from database row."""
        now = datetime.now()
        row = {
            "id": 1,
            "title": "Database Document",
            "file_path": self.test_path,
            "file_hash": "db_hash",
            "file_size": 1024,
            "page_count": 5,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "metadata": json.dumps({"key": "value"})
        }
        
        doc = DocumentModel.from_database_row(row)
        
        assert doc.id == 1
        assert doc.title == "Database Document"
        assert doc.file_hash == "db_hash"
        assert doc.page_count == 5
        assert isinstance(doc.created_at, datetime)
        assert doc.metadata == {"key": "value"}
    
    def test_from_database_row_null_values(self):
        """Test from_database_row with null values."""
        row = {
            "id": 1,
            "title": "Minimal Document",
            "file_path": None,
            "file_hash": "hash123",
            "file_size": 1024,
            "page_count": None,
            "created_at": None,
            "updated_at": None,
            "last_accessed": None,
            "metadata": None
        }
        
        doc = DocumentModel.from_database_row(row)
        
        assert doc.file_path is None
        assert doc.page_count is None
        assert doc.created_at is None
        assert doc.metadata == {}
    
    def test_to_database_dict(self):
        """Test converting DocumentModel to database dictionary."""
        now = datetime.now()
        doc = DocumentModel(
            title="Test Document",
            file_path=self.test_path,
            file_hash="test_hash",
            file_size=1024,
            page_count=10,
            created_at=now,
            metadata={"key": "value"}
        )
        
        db_dict = doc.to_database_dict()
        
        assert db_dict["title"] == "Test Document"
        assert db_dict["file_hash"] == "test_hash"
        assert db_dict["file_size"] == 1024
        assert db_dict["page_count"] == 10
        assert db_dict["created_at"] == now.isoformat()
        assert json.loads(db_dict["metadata"]) == {"key": "value"}
    
    def test_update_access_time(self):
        """Test updating last accessed time."""
        doc = DocumentModel(
            title="Test",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024
        )
        
        assert doc.last_accessed is None
        
        # Update access time
        doc.update_access_time()
        
        assert doc.last_accessed is not None
        assert isinstance(doc.last_accessed, datetime)
    
    def test_get_display_name(self):
        """Test getting display name."""
        # Test with title
        doc = DocumentModel(
            title="My Document",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024
        )
        assert doc.get_display_name() == "My Document"
        
        # Test with empty title - should fall back to filename in metadata
        doc = DocumentModel(
            title="",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024,
            metadata={"original_filename": "test.pdf"}
        )
        assert doc.get_display_name() == "test.pdf"
        
        # Test with empty title and no filename metadata - should fall back to default
        doc = DocumentModel(
            title="",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024
        )
        assert doc.get_display_name() == "Unknown Document"
    
    def test_get_file_extension(self):
        """Test getting file extension."""
        doc = DocumentModel(
            title="Test",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024,
            metadata={"file_extension": ".pdf"}
        )
        
        assert doc.get_file_extension() == ".pdf"
        
        # Test default when no extension in metadata
        doc.metadata = {}
        assert doc.get_file_extension() == ".pdf"  # Default
    
    def test_is_file_available(self):
        """Test checking file availability."""
        doc = DocumentModel(
            title="Test",
            file_path=self.test_path,
            file_hash="hash",
            file_size=1024
        )
        
        assert doc.is_file_available() is True
        
        # Test with non-existent file
        doc.file_path = "/nonexistent/file.pdf"
        assert doc.is_file_available() is False
        
        # Test with None file path
        doc.file_path = None
        assert doc.is_file_available() is False


class TestVectorIndexModel:
    """Test cases for VectorIndexModel class."""
    
    def test_vector_index_creation_minimal(self):
        """Test creating VectorIndexModel with minimal fields."""
        index = VectorIndexModel(
            document_id=1,
            index_path="/path/to/index",
            index_hash="index_hash_123"
        )
        
        assert index.document_id == 1
        assert index.index_path == "/path/to/index"
        assert index.index_hash == "index_hash_123"
        assert index.id is None
        assert index.chunk_count is None
        assert index.created_at is not None
    
    def test_vector_index_creation_complete(self):
        """Test creating VectorIndexModel with all fields."""
        now = datetime.now()
        
        index = VectorIndexModel(
            id=1,
            document_id=5,
            index_path="/complete/path",
            index_hash="complete_hash",
            chunk_count=25,
            created_at=now
        )
        
        assert index.id == 1
        assert index.document_id == 5
        assert index.chunk_count == 25
        assert index.created_at == now
    
    def test_vector_index_validation_document_id(self):
        """Test validation for document ID."""
        with pytest.raises(ValueError, match="Document ID must be positive"):
            VectorIndexModel(
                document_id=0,
                index_path="/path",
                index_hash="hash"
            )
        
        with pytest.raises(ValueError, match="Document ID must be positive"):
            VectorIndexModel(
                document_id=-1,
                index_path="/path",
                index_hash="hash"
            )
    
    def test_vector_index_validation_empty_path(self):
        """Test validation for empty index path."""
        with pytest.raises(ValueError, match="Index path cannot be empty"):
            VectorIndexModel(
                document_id=1,
                index_path="",
                index_hash="hash"
            )
    
    def test_vector_index_validation_empty_hash(self):
        """Test validation for empty index hash."""
        with pytest.raises(ValueError, match="Index hash cannot be empty"):
            VectorIndexModel(
                document_id=1,
                index_path="/path",
                index_hash=""
            )
    
    def test_from_database_row_factory(self):
        """Test creating VectorIndexModel from database row."""
        now = datetime.now()
        row = {
            "id": 1,
            "document_id": 5,
            "index_path": "/db/path",
            "index_hash": "db_hash",
            "chunk_count": 15,
            "created_at": now.isoformat()
        }
        
        index = VectorIndexModel.from_database_row(row)
        
        assert index.id == 1
        assert index.document_id == 5
        assert index.chunk_count == 15
        assert isinstance(index.created_at, datetime)
    
    def test_to_database_dict(self):
        """Test converting VectorIndexModel to database dictionary."""
        now = datetime.now()
        index = VectorIndexModel(
            document_id=3,
            index_path="/test/path",
            index_hash="test_hash",
            chunk_count=20,
            created_at=now
        )
        
        db_dict = index.to_database_dict()
        
        assert db_dict["document_id"] == 3
        assert db_dict["index_path"] == "/test/path"
        assert db_dict["index_hash"] == "test_hash"
        assert db_dict["chunk_count"] == 20
        assert db_dict["created_at"] == now.isoformat()
    
    def test_is_index_available_true(self):
        """Test index availability check with valid index."""
        # Create temporary directory structure
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir)
            
            # Create required index files
            (index_path / "default__vector_store.json").write_text("{}")
            (index_path / "graph_store.json").write_text("{}")
            (index_path / "index_store.json").write_text("{}")
            
            index = VectorIndexModel(
                document_id=1,
                index_path=str(index_path),
                index_hash="hash"
            )
            
            assert index.is_index_available() is True
    
    def test_is_index_available_false(self):
        """Test index availability check with invalid index."""
        # Non-existent path
        index = VectorIndexModel(
            document_id=1,
            index_path="/nonexistent/path",
            index_hash="hash"
        )
        
        assert index.is_index_available() is False
        
        # Existing path but missing files
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            index = VectorIndexModel(
                document_id=1,
                index_path=temp_dir,
                index_hash="hash"
            )
            
            assert index.is_index_available() is False


class TestTagModel:
    """Test cases for TagModel class."""
    
    def test_tag_model_creation_minimal(self):
        """Test creating TagModel with minimal fields."""
        tag = TagModel(name="academic")
        
        assert tag.name == "academic"  # Should be normalized to lowercase
        assert tag.color == "#0078d4"  # Default color
        assert tag.id is None
    
    def test_tag_model_creation_complete(self):
        """Test creating TagModel with all fields."""
        tag = TagModel(
            id=1,
            name="Research",
            color="#ff0000"
        )
        
        assert tag.id == 1
        assert tag.name == "research"  # Should be normalized
        assert tag.color == "#ff0000"
    
    def test_tag_model_validation_empty_name(self):
        """Test validation for empty tag name."""
        with pytest.raises(ValueError, match="Tag name cannot be empty"):
            TagModel(name="")
        
        with pytest.raises(ValueError, match="Tag name cannot be empty"):
            TagModel(name="   ")  # Only whitespace
    
    def test_tag_name_normalization(self):
        """Test tag name normalization."""
        tag = TagModel(name="  IMPORTANT  ")
        
        assert tag.name == "important"  # Trimmed and lowercase
    
    def test_from_database_row_factory(self):
        """Test creating TagModel from database row."""
        row = {
            "id": 1,
            "name": "database_tag",
            "color": "#00ff00"
        }
        
        tag = TagModel.from_database_row(row)
        
        assert tag.id == 1
        assert tag.name == "database_tag"
        assert tag.color == "#00ff00"
    
    def test_from_database_row_null_color(self):
        """Test from_database_row with null color."""
        row = {
            "id": 1,
            "name": "test",
            "color": None
        }
        
        tag = TagModel.from_database_row(row)
        
        assert tag.color is None  # Should preserve None from database
    
    def test_to_database_dict(self):
        """Test converting TagModel to database dictionary."""
        tag = TagModel(
            name="Test Tag",
            color="#123456"
        )
        
        db_dict = tag.to_database_dict()
        
        assert db_dict["name"] == "test tag"  # Normalized
        assert db_dict["color"] == "#123456"