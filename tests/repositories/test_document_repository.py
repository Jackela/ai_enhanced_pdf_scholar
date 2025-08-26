"""
Comprehensive Tests for DocumentRepository
Tests all aspects of document data access including:
- CRUD operations
- Advanced search and filtering
- Hash-based lookups
- Statistics and aggregations
- Error handling and edge cases
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.repositories.document_repository import DocumentRepository


class TestDocumentRepository:
    """Comprehensive test suite for DocumentRepository."""

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

    def setup_method(self):
        """Set up for each test method."""
        self.repository = DocumentRepository(self.db)
        # Clear documents table for fresh test
        self.db.execute("DELETE FROM documents")

    def _create_test_document(self, **kwargs) -> DocumentModel:
        """Create a test document with default values."""
        defaults = {
            "title": "Test Document",
            "file_path": "/test/path/document.pdf",
            "file_hash": "abc123def456",
            "content_hash": "content123hash456",
            "file_size": 1024,
            "page_count": 5,
            "metadata": {},
            "tags": "",
        }
        defaults.update(kwargs)
        return DocumentModel(**defaults)

    # ===== Repository Pattern Tests =====
    def test_repository_inheritance(self):
        """Test that DocumentRepository properly inherits from BaseRepository."""
        from src.repositories.base_repository import BaseRepository

        assert isinstance(self.repository, BaseRepository)

    def test_get_table_name(self):
        """Test getting the table name."""
        assert self.repository.get_table_name() == "documents"

    def test_to_model_conversion(self):
        """Test conversion from database row to model."""
        row_data = {
            "id": 1,
            "title": "Test Document",
            "file_path": "/test/path.pdf",
            "file_hash": "hash123",
            "content_hash": "content_hash123",
            "file_size": 2048,
            "page_count": 10,
            "created_at": "2023-01-01 10:00:00",
            "updated_at": "2023-01-01 10:00:00",
            "last_accessed": None,
            "metadata": "{}",
            "tags": "",
        }
        model = self.repository.to_model(row_data)
        assert isinstance(model, DocumentModel)
        assert model.id == 1
        assert model.title == "Test Document"
        assert model.file_path == "/test/path.pdf"
        assert model.file_hash == "hash123"
        assert model.content_hash == "content_hash123"

    def test_to_database_dict_conversion(self):
        """Test conversion from model to database dictionary."""
        document = self._create_test_document(
            id=1, title="Test Document", file_path="/test/path.pdf"
        )
        db_dict = self.repository.to_database_dict(document)
        assert isinstance(db_dict, dict)
        assert db_dict["title"] == "Test Document"
        assert db_dict["file_path"] == "/test/path.pdf"
        assert "id" in db_dict

    # ===== CRUD Operations Tests =====
    def test_create_document(self):
        """Test creating a new document."""
        document = self._create_test_document(
            title="New Document", file_path="/new/path.pdf", file_hash="new_hash_123"
        )
        created_doc = self.repository.create(document)
        assert created_doc is not None
        assert created_doc.id is not None
        assert created_doc.title == "New Document"
        assert created_doc.file_path == "/new/path.pdf"
        assert created_doc.file_hash == "new_hash_123"

    def test_find_by_id_success(self):
        """Test finding document by ID."""
        document = self._create_test_document(title="Find By ID Test")
        created_doc = self.repository.create(document)
        found_doc = self.repository.find_by_id(created_doc.id)
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        assert found_doc.title == "Find By ID Test"

    def test_find_by_id_not_found(self):
        """Test finding document by nonexistent ID."""
        found_doc = self.repository.find_by_id(99999)
        assert found_doc is None

    def test_get_by_id_interface_method(self):
        """Test the interface method get_by_id."""
        document = self._create_test_document(title="Interface Test")
        created_doc = self.repository.create(document)
        found_doc = self.repository.get_by_id(created_doc.id)
        assert found_doc is not None
        assert found_doc.id == created_doc.id

    def test_update_document(self):
        """Test updating an existing document."""
        document = self._create_test_document(title="Original Title")
        created_doc = self.repository.create(document)
        # Update the document
        created_doc.title = "Updated Title"
        created_doc.page_count = 15
        updated_doc = self.repository.update(created_doc)
        assert updated_doc is not None
        assert updated_doc.title == "Updated Title"
        assert updated_doc.page_count == 15
        # Verify the update persisted
        retrieved_doc = self.repository.find_by_id(created_doc.id)
        assert retrieved_doc.title == "Updated Title"
        assert retrieved_doc.page_count == 15

    def test_delete_document(self):
        """Test deleting a document."""
        document = self._create_test_document(title="To Be Deleted")
        created_doc = self.repository.create(document)
        success = self.repository.delete(created_doc.id)
        assert success is True
        # Verify deletion
        found_doc = self.repository.find_by_id(created_doc.id)
        assert found_doc is None

    def test_delete_nonexistent_document(self):
        """Test deleting a nonexistent document."""
        success = self.repository.delete(99999)
        assert success is False

    # ===== Hash-based Lookup Tests =====
    def test_find_by_file_hash_success(self):
        """Test finding document by file hash."""
        document = self._create_test_document(
            title="Hash Test", file_hash="unique_file_hash_123"
        )
        created_doc = self.repository.create(document)
        found_doc = self.repository.find_by_file_hash("unique_file_hash_123")
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        assert found_doc.file_hash == "unique_file_hash_123"

    def test_find_by_file_hash_not_found(self):
        """Test finding document by nonexistent file hash."""
        found_doc = self.repository.find_by_file_hash("nonexistent_hash")
        assert found_doc is None

    def test_find_by_hash_interface_method(self):
        """Test the interface method find_by_hash."""
        document = self._create_test_document(file_hash="interface_hash_123")
        created_doc = self.repository.create(document)
        found_doc = self.repository.find_by_hash("interface_hash_123")
        assert found_doc is not None
        assert found_doc.id == created_doc.id

    def test_find_by_content_hash_success(self):
        """Test finding document by content hash."""
        document = self._create_test_document(
            title="Content Hash Test", content_hash="unique_content_hash_123"
        )
        created_doc = self.repository.create(document)
        found_doc = self.repository.find_by_content_hash("unique_content_hash_123")
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        assert found_doc.content_hash == "unique_content_hash_123"

    def test_find_by_content_hash_not_found(self):
        """Test finding document by nonexistent content hash."""
        found_doc = self.repository.find_by_content_hash("nonexistent_content_hash")
        assert found_doc is None

    def test_find_by_file_path_success(self):
        """Test finding document by file path."""
        document = self._create_test_document(
            title="Path Test", file_path="/unique/file/path.pdf"
        )
        created_doc = self.repository.create(document)
        found_doc = self.repository.find_by_file_path("/unique/file/path.pdf")
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        assert found_doc.file_path == "/unique/file/path.pdf"

    def test_find_by_file_path_not_found(self):
        """Test finding document by nonexistent file path."""
        found_doc = self.repository.find_by_file_path("/nonexistent/path.pdf")
        assert found_doc is None

    # ===== Search and Filtering Tests =====
    def test_search_by_title_success(self):
        """Test searching documents by title."""
        docs = [
            self._create_test_document(
                title="Python Programming Guide",
                file_path="/path1.pdf",
                file_hash="hash1",
            ),
            self._create_test_document(
                title="Java Programming Manual",
                file_path="/path2.pdf",
                file_hash="hash2",
            ),
            self._create_test_document(
                title="Data Science Handbook", file_path="/path3.pdf", file_hash="hash3"
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        results = self.repository.search_by_title("Programming")
        assert len(results) == 2
        titles = [doc.title for doc in results]
        assert "Python Programming Guide" in titles
        assert "Java Programming Manual" in titles
        assert "Data Science Handbook" not in titles

    def test_search_by_title_case_insensitive(self):
        """Test that title search is case insensitive."""
        document = self._create_test_document(title="Python Programming")
        self.repository.create(document)
        results = self.repository.search_by_title("python")
        assert len(results) == 1
        assert results[0].title == "Python Programming"

    def test_search_by_title_with_limit(self):
        """Test title search with limit."""
        for i in range(5):
            doc = self._create_test_document(
                title=f"Test Document {i}",
                file_path=f"/path{i}.pdf",
                file_hash=f"hash{i}",
            )
            self.repository.create(doc)
        results = self.repository.search_by_title("Test", limit=3)
        assert len(results) == 3

    def test_search_general(self):
        """Test general search functionality."""
        docs = [
            self._create_test_document(
                title="Machine Learning", file_path="/ml.pdf", file_hash="hash1"
            ),
            self._create_test_document(
                title="Deep Learning", file_path="/dl.pdf", file_hash="hash2"
            ),
            self._create_test_document(
                title="Natural Language Processing",
                file_path="/nlp.pdf",
                file_hash="hash3",
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        results = self.repository.search("Learning")
        assert len(results) == 2
        titles = [doc.title for doc in results]
        assert "Machine Learning" in titles
        assert "Deep Learning" in titles

    def test_get_all_documents(self):
        """Test getting all documents with pagination."""
        # Create multiple documents
        for i in range(10):
            doc = self._create_test_document(
                title=f"Document {i}", file_path=f"/path{i}.pdf", file_hash=f"hash{i}"
            )
            self.repository.create(doc)
        # Test getting all without limit
        all_docs = self.repository.get_all(limit=100)
        assert len(all_docs) == 10
        # Test with limit
        limited_docs = self.repository.get_all(limit=5)
        assert len(limited_docs) == 5
        # Test with offset
        offset_docs = self.repository.get_all(limit=5, offset=5)
        assert len(offset_docs) == 5
        # Verify no overlap between limited and offset results
        limited_ids = {doc.id for doc in limited_docs}
        offset_ids = {doc.id for doc in offset_docs}
        assert limited_ids.isdisjoint(offset_ids)

    def test_get_all_with_sorting(self):
        """Test getting all documents with sorting options."""
        # Create documents with different creation times
        base_time = datetime.now()
        for i in range(3):
            doc = self._create_test_document(
                title=f"Document {i}", file_path=f"/path{i}.pdf", file_hash=f"hash{i}"
            )
            created_doc = self.repository.create(doc)
            # Manually update timestamp for testing
            adjusted_time = base_time - timedelta(days=i)
            self.db.execute(
                "UPDATE documents SET created_at = ? WHERE id = ?",
                (adjusted_time, created_doc.id),
            )
        # Test sorting by creation date (newest first)
        recent_docs = self.repository.get_all(sort_by="created_at", sort_order="DESC")
        assert len(recent_docs) == 3
        # Verify order (newest first)
        for i in range(len(recent_docs) - 1):
            assert recent_docs[i].created_at >= recent_docs[i + 1].created_at

    def test_find_recent_documents(self):
        """Test finding recent documents."""
        # Create documents with different timestamps
        base_time = datetime.now()
        doc_ids = []
        for i in range(5):
            doc = self._create_test_document(
                title=f"Document {i}", file_path=f"/path{i}.pdf", file_hash=f"hash{i}"
            )
            created_doc = self.repository.create(doc)
            doc_ids.append(created_doc.id)
            # Set different creation times
            time_offset = timedelta(days=i)
            adjusted_time = base_time - time_offset
            self.db.execute(
                "UPDATE documents SET created_at = ? WHERE id = ?",
                (adjusted_time, created_doc.id),
            )
        recent_docs = self.repository.find_recent_documents(limit=3)
        assert len(recent_docs) == 3
        # Should be in descending order of creation time (newest first)
        assert recent_docs[0].title == "Document 0"  # Most recent
        assert recent_docs[1].title == "Document 1"
        assert recent_docs[2].title == "Document 2"

    # ===== Advanced Filtering Tests =====
    def test_find_by_size_range(self):
        """Test finding documents by file size range."""
        docs = [
            self._create_test_document(
                title="Small Doc",
                file_path="/small.pdf",
                file_hash="hash1",
                file_size=500,
            ),
            self._create_test_document(
                title="Medium Doc",
                file_path="/medium.pdf",
                file_hash="hash2",
                file_size=1500,
            ),
            self._create_test_document(
                title="Large Doc",
                file_path="/large.pdf",
                file_hash="hash3",
                file_size=3000,
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        # Test minimum size filter
        large_docs = self.repository.find_by_size_range(min_size=2000)
        assert len(large_docs) == 1
        assert large_docs[0].title == "Large Doc"
        # Test maximum size filter
        small_docs = self.repository.find_by_size_range(max_size=1000)
        assert len(small_docs) == 1
        assert small_docs[0].title == "Small Doc"
        # Test size range
        medium_docs = self.repository.find_by_size_range(min_size=1000, max_size=2000)
        assert len(medium_docs) == 1
        assert medium_docs[0].title == "Medium Doc"

    def test_find_by_date_range(self):
        """Test finding documents by date range."""
        base_time = datetime.now()
        # Create documents with different dates
        docs = [
            self._create_test_document(
                title="Old Doc", file_path="/old.pdf", file_hash="hash1"
            ),
            self._create_test_document(
                title="Recent Doc", file_path="/recent.pdf", file_hash="hash2"
            ),
            self._create_test_document(
                title="New Doc", file_path="/new.pdf", file_hash="hash3"
            ),
        ]
        created_docs = []
        for i, doc in enumerate(docs):
            created_doc = self.repository.create(doc)
            created_docs.append(created_doc)
            # Set different creation dates
            adjusted_time = base_time - timedelta(days=10 - i * 5)  # 10, 5, 0 days ago
            self.db.execute(
                "UPDATE documents SET created_at = ? WHERE id = ?",
                (adjusted_time, created_doc.id),
            )
        # Test finding documents from last 7 days
        start_date = base_time - timedelta(days=7)
        recent_docs = self.repository.find_by_date_range(start_date=start_date)
        assert len(recent_docs) == 2  # "Recent Doc" and "New Doc"
        titles = [doc.title for doc in recent_docs]
        assert "Recent Doc" in titles
        assert "New Doc" in titles
        assert "Old Doc" not in titles
        # Test finding documents before a certain date
        end_date = base_time - timedelta(days=7)
        old_docs = self.repository.find_by_date_range(end_date=end_date)
        assert len(old_docs) == 1
        assert old_docs[0].title == "Old Doc"

    def test_update_access_time(self):
        """Test updating document access time."""
        document = self._create_test_document(title="Access Test")
        created_doc = self.repository.create(document)
        # Initially, last_accessed should be None
        assert created_doc.last_accessed is None
        # Update access time
        success = self.repository.update_access_time(created_doc.id)
        assert success is True
        # Verify access time was updated
        updated_doc = self.repository.find_by_id(created_doc.id)
        assert updated_doc.last_accessed is not None

    def test_update_access_time_nonexistent(self):
        """Test updating access time for nonexistent document."""
        success = self.repository.update_access_time(99999)
        assert success is False

    # ===== Statistics and Aggregation Tests =====
    def test_get_statistics_empty_library(self):
        """Test getting statistics for empty library."""
        stats = self.repository.get_statistics()
        assert stats["total_documents"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["average_size_bytes"] == 0
        assert stats["total_pages"] == 0
        assert stats["average_pages"] == 0
        assert stats["oldest_document_date"] is None
        assert stats["newest_document_date"] is None

    def test_get_statistics_with_documents(self):
        """Test getting statistics with documents."""
        docs = [
            self._create_test_document(
                title="Doc 1",
                file_path="/doc1.pdf",
                file_hash="hash1",
                file_size=1000,
                page_count=10,
            ),
            self._create_test_document(
                title="Doc 2",
                file_path="/doc2.pdf",
                file_hash="hash2",
                file_size=2000,
                page_count=20,
            ),
            self._create_test_document(
                title="Doc 3",
                file_path="/doc3.pdf",
                file_hash="hash3",
                file_size=3000,
                page_count=30,
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        stats = self.repository.get_statistics()
        assert stats["total_documents"] == 3
        assert stats["total_size_bytes"] == 6000
        assert stats["average_size_bytes"] == 2000
        assert stats["total_pages"] == 60
        assert stats["average_pages"] == 20
        assert stats["oldest_document_date"] is not None
        assert stats["newest_document_date"] is not None

    def test_find_duplicates_by_size_and_name(self):
        """Test finding potential duplicates by size and name similarity."""
        # Create documents with same size and similar names
        docs = [
            self._create_test_document(
                title="Python Guide",
                file_path="/guide1.pdf",
                file_hash="hash1",
                file_size=1500,
            ),
            self._create_test_document(
                title="Python Guide",
                file_path="/guide2.pdf",
                file_hash="hash2",
                file_size=1500,
            ),
            self._create_test_document(
                title="Java Manual",
                file_path="/manual.pdf",
                file_hash="hash3",
                file_size=2000,
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        duplicates = self.repository.find_duplicates_by_size_and_name()
        assert len(duplicates) == 1  # One group of duplicates
        size, duplicate_docs = duplicates[0]
        assert size == 1500
        assert len(duplicate_docs) == 2
        assert all(doc.title == "Python Guide" for doc in duplicate_docs)

    def test_advanced_search_multiple_criteria(self):
        """Test advanced search with multiple criteria."""
        docs = [
            self._create_test_document(
                title="Python Programming",
                file_path="/python.pdf",
                file_hash="hash1",
                file_size=1500,
                page_count=25,
            ),
            self._create_test_document(
                title="Java Programming",
                file_path="/java.pdf",
                file_hash="hash2",
                file_size=2500,
                page_count=35,
            ),
            self._create_test_document(
                title="Python Data Science",
                file_path="/datascience.pdf",
                file_hash="hash3",
                file_size=1800,
                page_count=40,
            ),
        ]
        for doc in docs:
            self.repository.create(doc)
        # Search for Python documents with moderate size
        results = self.repository.advanced_search(
            title_contains="Python",
            min_size=1000,
            max_size=2000,
            min_pages=20,
            max_pages=30,
        )
        assert len(results) == 1
        assert results[0].title == "Python Programming"

    def test_advanced_search_with_date_filters(self):
        """Test advanced search with date filters."""
        base_time = datetime.now()
        # Create documents with different dates
        old_doc = self._create_test_document(
            title="Old Document", file_path="/old.pdf", file_hash="hash1"
        )
        new_doc = self._create_test_document(
            title="New Document", file_path="/new.pdf", file_hash="hash2"
        )
        created_old = self.repository.create(old_doc)
        created_new = self.repository.create(new_doc)
        # Set different creation dates
        old_date = base_time - timedelta(days=30)
        self.db.execute(
            "UPDATE documents SET created_at = ? WHERE id = ?",
            (old_date, created_old.id),
        )
        # Search for documents created in last 15 days
        recent_date = base_time - timedelta(days=15)
        results = self.repository.advanced_search(created_after=recent_date)
        assert len(results) == 1
        assert results[0].title == "New Document"

    # ===== Error Handling Tests =====
    @patch("src.repositories.document_repository.logger")
    def test_find_by_file_hash_database_error(self, mock_logger):
        """Test error handling in find_by_file_hash."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_file_hash("test_hash")
            mock_logger.error.assert_called_once()

    @patch("src.repositories.document_repository.logger")
    def test_find_by_file_path_database_error(self, mock_logger):
        """Test error handling in find_by_file_path."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_file_path("/test/path.pdf")
            mock_logger.error.assert_called_once()

    def test_create_duplicate_file_path(self):
        """Test creating document with duplicate file path (should fail due to UNIQUE constraint)."""
        doc1 = self._create_test_document(
            title="First Document", file_path="/same/path.pdf", file_hash="hash1"
        )
        doc2 = self._create_test_document(
            title="Second Document",
            file_path="/same/path.pdf",  # Same path
            file_hash="hash2",
        )
        self.repository.create(doc1)
        # Second create should fail due to unique constraint on file_path
        with pytest.raises(Exception):  # SQLite constraint error
            self.repository.create(doc2)

    # ===== Integration Tests =====
    def test_full_document_lifecycle(self):
        """Test complete document lifecycle: create, read, update, delete."""
        # Create
        document = self._create_test_document(
            title="Lifecycle Test",
            file_path="/lifecycle.pdf",
            file_hash="lifecycle_hash",
        )
        created_doc = self.repository.create(document)
        assert created_doc.id is not None
        # Read
        found_doc = self.repository.find_by_id(created_doc.id)
        assert found_doc.title == "Lifecycle Test"
        # Update
        found_doc.title = "Updated Lifecycle Test"
        updated_doc = self.repository.update(found_doc)
        assert updated_doc is not None
        assert updated_doc.title == "Updated Lifecycle Test"
        # Verify update persisted
        retrieved_doc = self.repository.find_by_id(created_doc.id)
        assert retrieved_doc.title == "Updated Lifecycle Test"
        # Delete
        delete_success = self.repository.delete(created_doc.id)
        assert delete_success is True
        # Verify deletion
        deleted_doc = self.repository.find_by_id(created_doc.id)
        assert deleted_doc is None

    def test_transaction_rollback_simulation(self):
        """Test that repository operations work within database transactions."""
        document = self._create_test_document(title="Transaction Test")
        # This should work normally
        created_doc = self.repository.create(document)
        assert created_doc.id is not None
        # Verify it was saved
        found_doc = self.repository.find_by_id(created_doc.id)
        assert found_doc is not None
        assert found_doc.title == "Transaction Test"
