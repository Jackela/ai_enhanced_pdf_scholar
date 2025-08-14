"""
Comprehensive Tests for VectorIndexRepository
Tests all aspects of vector index data access including:
- Basic CRUD operations
- Document relationship management
- Index cleanup and maintenance
- Integrity verification and validation
- Statistics and reporting
- Error handling and edge cases
"""

import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.repositories.vector_repository import VectorIndexRepository


class TestVectorIndexRepository:
    """Comprehensive test suite for VectorIndexRepository."""

    @classmethod
    def setup_class(cls):
        """Set up test database."""
        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        # Initialize database schema
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test database."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        # Create documents table
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT ''
            )
        """
        )
        # Create vector_indexes table
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                index_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """
        )

    def setup_method(self):
        """Set up for each test method."""
        self.repository = VectorIndexRepository(self.db)
        self.temp_index_dir = tempfile.mkdtemp()
        # Clear tables for fresh test
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")

    def teardown_method(self):
        """Clean up after each test method."""
        if Path(self.temp_index_dir).exists():
            shutil.rmtree(self.temp_index_dir)

    def _create_test_document(self, **kwargs) -> int:
        """Create a test document and return its ID."""
        defaults = {
            "title": "Test Document",
            "file_path": "/test/path/document.pdf",
            "file_hash": "abc123def456",
            "content_hash": "content123hash456",
            "file_size": 1024,
            "page_count": 5,
        }
        defaults.update(kwargs)
        result = self.db.execute(
            """INSERT INTO documents (title, file_path, file_hash, content_hash, file_size, page_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                defaults["title"],
                defaults["file_path"],
                defaults["file_hash"],
                defaults["content_hash"],
                defaults["file_size"],
                defaults["page_count"],
            ),
        )
        return self.db.get_last_insert_id()

    def _create_test_vector_index(
        self, document_id: int = None, **kwargs
    ) -> VectorIndexModel:
        """Create a test vector index with default values."""
        if document_id is None:
            document_id = self._create_test_document()
        defaults = {
            "document_id": document_id,
            "index_path": str(Path(self.temp_index_dir) / "test_index"),
            "chunk_count": 10,
            "index_hash": "index_hash_123",
            "metadata": {},
        }
        defaults.update(kwargs)
        return VectorIndexModel(**defaults)

    def _create_index_files(self, index_path: str):
        """Create fake index files for testing."""
        index_dir = Path(index_path)
        index_dir.mkdir(parents=True, exist_ok=True)
        (index_dir / "index.faiss").write_text("fake index")
        (index_dir / "docstore.pkl").write_text("fake docstore")

    # ===== Repository Pattern Tests =====
    def test_repository_inheritance(self):
        """Test that VectorIndexRepository properly inherits from BaseRepository."""
        from src.repositories.base_repository import BaseRepository

        assert isinstance(self.repository, BaseRepository)

    def test_get_table_name(self):
        """Test getting the table name."""
        assert self.repository.get_table_name() == "vector_indexes"

    def test_to_model_conversion(self):
        """Test conversion from database row to model."""
        row_data = {
            "id": 1,
            "document_id": 123,
            "index_path": "/test/index/path",
            "chunk_count": 25,
            "index_hash": "hash123",
            "created_at": "2023-01-01 10:00:00",
            "updated_at": "2023-01-01 10:00:00",
            "metadata": "{}",
        }
        model = self.repository.to_model(row_data)
        assert isinstance(model, VectorIndexModel)
        assert model.id == 1
        assert model.document_id == 123
        assert model.index_path == "/test/index/path"
        assert model.chunk_count == 25
        assert model.index_hash == "hash123"

    def test_to_database_dict_conversion(self):
        """Test conversion from model to database dictionary."""
        vector_index = self._create_test_vector_index()
        vector_index.id = 1
        db_dict = self.repository.to_database_dict(vector_index)
        assert isinstance(db_dict, dict)
        assert db_dict["document_id"] == vector_index.document_id
        assert db_dict["index_path"] == vector_index.index_path
        assert db_dict["chunk_count"] == vector_index.chunk_count
        assert "id" in db_dict

    # ===== CRUD Operations Tests =====
    def test_create_vector_index(self):
        """Test creating a new vector index."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(
            document_id=document_id, index_path="/new/index/path", chunk_count=15
        )
        created_index = self.repository.create(vector_index)
        assert created_index is not None
        assert created_index.id is not None
        assert created_index.document_id == document_id
        assert created_index.index_path == "/new/index/path"
        assert created_index.chunk_count == 15

    def test_find_by_id_success(self):
        """Test finding vector index by ID."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        found_index = self.repository.find_by_id(created_index.id)
        assert found_index is not None
        assert found_index.id == created_index.id
        assert found_index.document_id == document_id

    def test_find_by_id_not_found(self):
        """Test finding vector index by nonexistent ID."""
        found_index = self.repository.find_by_id(99999)
        assert found_index is None

    def test_update_vector_index(self):
        """Test updating an existing vector index."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        # Update the index
        created_index.chunk_count = 25
        created_index.index_hash = "updated_hash"
        updated_index = self.repository.update(created_index)
        assert updated_index is not None
        assert updated_index.chunk_count == 25
        assert updated_index.index_hash == "updated_hash"

    def test_delete_vector_index(self):
        """Test deleting a vector index."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        success = self.repository.delete(created_index.id)
        assert success is True
        # Verify deletion
        found_index = self.repository.find_by_id(created_index.id)
        assert found_index is None

    def test_delete_nonexistent_vector_index(self):
        """Test deleting a nonexistent vector index."""
        success = self.repository.delete(99999)
        assert success is False

    # ===== Document Relationship Tests =====
    def test_find_by_document_id_success(self):
        """Test finding vector index by document ID."""
        document_id = self._create_test_document(title="Test Document")
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        found_index = self.repository.find_by_document_id(document_id)
        assert found_index is not None
        assert found_index.id == created_index.id
        assert found_index.document_id == document_id

    def test_find_by_document_id_not_found(self):
        """Test finding vector index by nonexistent document ID."""
        found_index = self.repository.find_by_document_id(99999)
        assert found_index is None

    def test_find_by_index_hash_success(self):
        """Test finding vector index by index hash."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(
            document_id=document_id, index_hash="unique_hash_123"
        )
        created_index = self.repository.create(vector_index)
        found_index = self.repository.find_by_index_hash("unique_hash_123")
        assert found_index is not None
        assert found_index.id == created_index.id
        assert found_index.index_hash == "unique_hash_123"

    def test_find_by_index_hash_not_found(self):
        """Test finding vector index by nonexistent hash."""
        found_index = self.repository.find_by_index_hash("nonexistent_hash")
        assert found_index is None

    def test_find_all_with_documents(self):
        """Test finding all vector indexes with document information."""
        # Create multiple documents with indexes
        doc1_id = self._create_test_document(title="Document 1", file_path="/test/path/document1.pdf", file_size=1000)
        doc2_id = self._create_test_document(title="Document 2", file_path="/test/path/document2.pdf", file_size=2000)
        index1 = self._create_test_vector_index(document_id=doc1_id, chunk_count=10)
        index2 = self._create_test_vector_index(document_id=doc2_id, chunk_count=20)
        self.repository.create(index1)
        self.repository.create(index2)
        results = self.repository.find_all_with_documents()
        assert len(results) == 2
        # Check that document information is included
        for result in results:
            assert "document_title" in result
            assert "document_path" in result
            assert "document_size" in result
            assert result["document_title"] in ["Document 1", "Document 2"]

    def test_delete_by_document_id_success(self):
        """Test deleting vector index by document ID."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        success = self.repository.delete_by_document_id(document_id)
        assert success is True
        # Verify deletion
        found_index = self.repository.find_by_document_id(document_id)
        assert found_index is None

    def test_delete_by_document_id_not_found(self):
        """Test deleting vector index by nonexistent document ID."""
        success = self.repository.delete_by_document_id(99999)
        assert success is False

    # ===== Orphaned Index Tests =====
    def test_find_orphaned_indexes_none(self):
        """Test finding orphaned indexes when none exist."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        self.repository.create(vector_index)
        orphaned = self.repository.find_orphaned_indexes()
        assert orphaned == []

    def test_find_orphaned_indexes_with_orphans(self):
        """Test finding orphaned indexes."""
        # Temporarily disable foreign keys to create orphaned index
        self.db.execute("PRAGMA foreign_keys = OFF")
        try:
            # Create vector index with nonexistent document
            vector_index = self._create_test_vector_index(document_id=99999)
            created_index = self.repository.create(vector_index)
            orphaned = self.repository.find_orphaned_indexes()
            assert len(orphaned) == 1
            assert orphaned[0].id == created_index.id
            assert orphaned[0].document_id == 99999
        finally:
            # Re-enable foreign keys
            self.db.execute("PRAGMA foreign_keys = ON")

    def test_cleanup_orphaned_indexes_none(self):
        """Test cleanup when no orphaned indexes exist."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        self.repository.create(vector_index)
        cleaned_count = self.repository.cleanup_orphaned_indexes()
        assert cleaned_count == 0

    def test_cleanup_orphaned_indexes_with_orphans(self):
        """Test cleanup of orphaned indexes."""
        # Create valid index
        valid_doc_id = self._create_test_document()
        valid_index = self._create_test_vector_index(document_id=valid_doc_id)
        self.repository.create(valid_index)
        # Temporarily disable foreign keys to create orphaned indexes
        self.db.execute("PRAGMA foreign_keys = OFF")
        try:
            # Create orphaned indexes
            orphaned1 = self._create_test_vector_index(document_id=99998)
            orphaned2 = self._create_test_vector_index(document_id=99999)
            self.repository.create(orphaned1)
            self.repository.create(orphaned2)
        finally:
            # Re-enable foreign keys
            self.db.execute("PRAGMA foreign_keys = ON")
        cleaned_count = self.repository.cleanup_orphaned_indexes()
        assert cleaned_count == 2
        # Verify valid index remains
        valid_found = self.repository.find_by_document_id(valid_doc_id)
        assert valid_found is not None
        # Verify orphaned indexes are gone
        remaining = self.repository.find_all()
        assert len(remaining) == 1

    # ===== Invalid Index Tests =====
    @patch.object(VectorIndexModel, "is_index_available")
    def test_find_invalid_indexes_none(self, mock_is_available):
        """Test finding invalid indexes when none exist."""
        mock_is_available.return_value = True
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        self.repository.create(vector_index)
        invalid = self.repository.find_invalid_indexes()
        assert invalid == []

    @patch.object(VectorIndexModel, "is_index_available")
    def test_find_invalid_indexes_with_invalid(self, mock_is_available):
        """Test finding invalid indexes."""
        mock_is_available.return_value = False
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        invalid = self.repository.find_invalid_indexes()
        assert len(invalid) == 1
        assert invalid[0].id == created_index.id

    @patch.object(VectorIndexModel, "is_index_available")
    def test_cleanup_invalid_indexes_none(self, mock_is_available):
        """Test cleanup when no invalid indexes exist."""
        mock_is_available.return_value = True
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        self.repository.create(vector_index)
        cleaned_count = self.repository.cleanup_invalid_indexes()
        assert cleaned_count == 0

    def test_cleanup_invalid_indexes_with_invalid(self):
        """Test cleanup of invalid indexes."""
        # Create valid index
        valid_doc_id = self._create_test_document()
        valid_index = self._create_test_vector_index(document_id=valid_doc_id)
        valid_created = self.repository.create(valid_index)

        # Create invalid index
        invalid_doc_id = self._create_test_document(title="Invalid Doc", file_path="/test/path/invalid_document.pdf")
        invalid_index = self._create_test_vector_index(document_id=invalid_doc_id)
        invalid_created = self.repository.create(invalid_index)

        # Create a custom mock that checks the actual instance ID
        original_method = VectorIndexModel.is_index_available

        def custom_mock(instance_self):
            if instance_self.id == valid_created.id:
                return True  # Valid index
            else:
                return False  # Invalid index

        # Apply the mock
        with patch.object(VectorIndexModel, 'is_index_available', custom_mock):
            cleaned_count = self.repository.cleanup_invalid_indexes()

        assert cleaned_count == 1
        # Verify valid index remains
        valid_found = self.repository.find_by_id(valid_created.id)
        assert valid_found is not None
        # Verify invalid index is gone
        invalid_found = self.repository.find_by_id(invalid_created.id)
        assert invalid_found is None

    @patch.object(VectorIndexModel, "is_index_available")
    @patch("shutil.rmtree")
    def test_cleanup_invalid_indexes_with_file_removal(
        self, mock_rmtree, mock_is_available
    ):
        """Test cleanup of invalid indexes with file removal."""
        mock_is_available.return_value = False
        # Create index with files
        index_path = str(Path(self.temp_index_dir) / "invalid_index")
        self._create_index_files(index_path)
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(
            document_id=document_id, index_path=index_path
        )
        created_index = self.repository.create(vector_index)
        cleaned_count = self.repository.cleanup_invalid_indexes(remove_files=True)
        assert cleaned_count == 1
        mock_rmtree.assert_called_once_with(index_path, ignore_errors=True)

    # ===== Statistics Tests =====
    def test_get_index_statistics_empty(self):
        """Test getting statistics for empty repository."""
        stats = self.repository.get_index_statistics()
        assert stats["total_indexes"] == 0
        assert "chunk_stats" in stats
        assert "coverage" in stats
        assert stats["orphaned_count"] == 0
        assert stats["invalid_count"] == 0

    def test_get_index_statistics_with_data(self):
        """Test getting statistics with data."""
        # Create documents and indexes
        doc1_id = self._create_test_document(title="Doc 1", file_path="/test/path/doc1.pdf")
        doc2_id = self._create_test_document(title="Doc 2", file_path="/test/path/doc2.pdf")
        doc3_id = self._create_test_document(title="Doc 3", file_path="/test/path/doc3.pdf")  # No index
        index1 = self._create_test_vector_index(document_id=doc1_id, chunk_count=10)
        index2 = self._create_test_vector_index(document_id=doc2_id, chunk_count=20)
        self.repository.create(index1)
        self.repository.create(index2)
        stats = self.repository.get_index_statistics()
        assert stats["total_indexes"] == 2
        assert stats["chunk_stats"]["total_chunks"] == 30
        assert stats["chunk_stats"]["avg_chunks"] == 15.0
        assert stats["coverage"]["documents_with_index"] == 2
        assert stats["coverage"]["total_documents"] == 3
        assert stats["coverage"]["coverage_percentage"] == 66.66666666666666

    # ===== Integrity Verification Tests =====
    def test_verify_index_integrity_not_found(self):
        """Test integrity verification for nonexistent index."""
        result = self.repository.verify_index_integrity(99999)
        assert result["exists"] is False
        assert "Index not found" in result["error"]

    def test_verify_index_integrity_valid(self):
        """Test integrity verification for valid index."""
        # Create index with files
        index_path = str(Path(self.temp_index_dir) / "valid_index")
        self._create_index_files(index_path)
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(
            document_id=document_id, index_path=index_path
        )
        created_index = self.repository.create(vector_index)
        with patch.object(VectorIndexModel, "is_index_available", return_value=True):
            result = self.repository.verify_index_integrity(created_index.id)
        assert result["exists"] is True
        assert result["document_exists"] is True
        assert result["files_exist"] is True
        assert result["path_accessible"] is True
        assert result["is_valid"] is True
        assert result["errors"] == []

    def test_verify_index_integrity_missing_document(self):
        """Test integrity verification when document is missing."""
        # Temporarily disable foreign keys to create index for nonexistent document
        self.db.execute("PRAGMA foreign_keys = OFF")
        try:
            # Create index for nonexistent document
            vector_index = self._create_test_vector_index(document_id=99999)
            created_index = self.repository.create(vector_index)
        finally:
            # Re-enable foreign keys
            self.db.execute("PRAGMA foreign_keys = ON")
        with patch.object(VectorIndexModel, "is_index_available", return_value=True):
            result = self.repository.verify_index_integrity(created_index.id)
        assert result["exists"] is True
        assert result["document_exists"] is False
        assert result["is_valid"] is False
        assert "Associated document no longer exists" in result["errors"]

    def test_verify_index_integrity_missing_files(self):
        """Test integrity verification when index files are missing."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        with patch.object(VectorIndexModel, "is_index_available", return_value=False):
            result = self.repository.verify_index_integrity(created_index.id)
        assert result["exists"] is True
        assert result["document_exists"] is True
        assert result["files_exist"] is False
        assert result["is_valid"] is False
        assert "Index files are missing or incomplete" in result["errors"]

    def test_verify_index_integrity_inaccessible_path(self):
        """Test integrity verification when path is inaccessible."""
        document_id = self._create_test_document()
        vector_index = self._create_test_vector_index(
            document_id=document_id, index_path="/nonexistent/path"
        )
        created_index = self.repository.create(vector_index)
        with patch.object(VectorIndexModel, "is_index_available", return_value=True):
            result = self.repository.verify_index_integrity(created_index.id)
        assert result["exists"] is True
        assert result["path_accessible"] is False
        assert result["is_valid"] is False

    # ===== Error Handling Tests =====
    @patch("src.repositories.vector_repository.logger")
    def test_find_by_document_id_database_error(self, mock_logger):
        """Test error handling in find_by_document_id."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_document_id(123)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.vector_repository.logger")
    def test_find_by_index_hash_database_error(self, mock_logger):
        """Test error handling in find_by_index_hash."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_index_hash("test_hash")
            mock_logger.error.assert_called_once()

    @patch("src.repositories.vector_repository.logger")
    def test_find_all_with_documents_database_error(self, mock_logger):
        """Test error handling in find_all_with_documents."""
        with patch.object(
            self.db, "fetch_all", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_all_with_documents()
            mock_logger.error.assert_called_once()

    def test_cleanup_invalid_indexes_individual_failure(self):
        """Test cleanup continues when individual index cleanup fails."""
        with patch.object(VectorIndexModel, "is_index_available", return_value=False):
            # Create multiple invalid indexes
            doc1_id = self._create_test_document(title="Doc 1", file_path="/test/path/doc1.pdf")
            doc2_id = self._create_test_document(title="Doc 2", file_path="/test/path/doc2.pdf")
            index1 = self._create_test_vector_index(document_id=doc1_id)
            index2 = self._create_test_vector_index(document_id=doc2_id)
            created1 = self.repository.create(index1)
            created2 = self.repository.create(index2)
            # Mock delete to fail for first index only
            original_delete = self.repository.delete
            call_count = 0

            def mock_delete(index_id):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Delete failed")
                return original_delete(index_id)

            with patch.object(self.repository, "delete", side_effect=mock_delete):
                cleaned_count = self.repository.cleanup_invalid_indexes()
            # Should continue and clean up the second index
            assert cleaned_count == 1

    # ===== Integration Tests =====
    def test_full_index_lifecycle(self):
        """Test complete index lifecycle: create, read, update, delete."""
        # Create
        document_id = self._create_test_document(title="Lifecycle Test")
        vector_index = self._create_test_vector_index(
            document_id=document_id, chunk_count=15, index_hash="lifecycle_hash"
        )
        created_index = self.repository.create(vector_index)
        assert created_index.id is not None
        # Read
        found_index = self.repository.find_by_id(created_index.id)
        assert found_index.chunk_count == 15
        # Update
        found_index.chunk_count = 25
        updated_index = self.repository.update(found_index)
        assert updated_index.chunk_count == 25
        # Delete
        delete_success = self.repository.delete(created_index.id)
        assert delete_success is True
        # Verify deletion
        deleted_index = self.repository.find_by_id(created_index.id)
        assert deleted_index is None

    def test_document_index_relationship_integrity(self):
        """Test that document-index relationships are properly maintained."""
        # Create document and index
        document_id = self._create_test_document(title="Relationship Test")
        vector_index = self._create_test_vector_index(document_id=document_id)
        created_index = self.repository.create(vector_index)
        # Verify relationship
        found_by_doc = self.repository.find_by_document_id(document_id)
        assert found_by_doc.id == created_index.id
        # Verify in joined query
        with_docs = self.repository.find_all_with_documents()
        assert len(with_docs) == 1
        assert with_docs[0]["document_title"] == "Relationship Test"
        assert with_docs[0]["document_id"] == document_id

    def test_multiple_indexes_operations(self):
        """Test operations with multiple indexes."""
        # Create multiple documents and indexes
        docs_and_indexes = []
        for i in range(3):
            doc_id = self._create_test_document(title=f"Document {i}", file_path=f"/test/path/document{i}.pdf")
            index = self._create_test_vector_index(
                document_id=doc_id, chunk_count=10 * (i + 1), index_hash=f"hash_{i}"
            )
            created_index = self.repository.create(index)
            docs_and_indexes.append((doc_id, created_index))
        # Test find_all
        all_indexes = self.repository.find_all()
        assert len(all_indexes) == 3
        # Test find_all_with_documents
        with_docs = self.repository.find_all_with_documents()
        assert len(with_docs) == 3
        # Test statistics
        stats = self.repository.get_index_statistics()
        assert stats["total_indexes"] == 3
        assert stats["chunk_stats"]["total_chunks"] == 60  # 10 + 20 + 30
        assert stats["coverage"]["coverage_percentage"] == 100.0
        # Test cleanup operations don't affect valid indexes
        orphaned_count = self.repository.cleanup_orphaned_indexes()
        assert orphaned_count == 0
        # All indexes should still exist
        remaining = self.repository.find_all()
        assert len(remaining) == 3
