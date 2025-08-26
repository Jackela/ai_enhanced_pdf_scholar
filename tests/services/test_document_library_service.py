"""
Comprehensive Tests for DocumentLibraryService
Tests all aspects of document library management including:
- Document importing with duplicate detection
- File management and storage
- Search and retrieval operations
- Library maintenance and integrity verification
- Error handling and edge cases
"""

import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import VectorIndexModel
from src.services.content_hash_service import ContentHashError
from src.services.document_library_service import (
    DocumentImportError,
    DocumentLibraryService,
    DuplicateDocumentError,
)
from tests.fixtures.pdf_fixtures import PDFFixtureGenerator


class TestDocumentLibraryService:
    """Comprehensive test suite for DocumentLibraryService."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures and database."""
        # Create PDF fixtures
        cls.fixture_generator = PDFFixtureGenerator()
        cls.fixtures = cls.fixture_generator.create_all_fixtures()
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
        """Clean up test fixtures and database."""
        cls.fixture_generator.cleanup_fixtures()
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
        # Create temporary documents directory
        self.temp_docs_dir = tempfile.mkdtemp()
        # Create service instance
        self.service = DocumentLibraryService(
            db_connection=self.db, documents_dir=self.temp_docs_dir
        )
        # Clear database for fresh test
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")

    def teardown_method(self):
        """Clean up after each test method."""
        # Clean up temporary documents directory
        if Path(self.temp_docs_dir).exists():
            shutil.rmtree(self.temp_docs_dir)

    def get_fixture_path(self, fixture_name: str) -> str:
        """Get path to a test fixture."""
        return str(self.fixture_generator.get_fixture_path(fixture_name))

    # ===== Initialization Tests =====
    def test_initialization_default_directory(self):
        """Test service initialization with default documents directory."""
        service = DocumentLibraryService(self.db)
        expected_dir = Path.home() / ".ai_pdf_scholar" / "documents"
        assert service.documents_dir == expected_dir
        assert service.documents_dir.exists()

    def test_initialization_custom_directory(self):
        """Test service initialization with custom documents directory."""
        custom_dir = tempfile.mkdtemp()
        try:
            service = DocumentLibraryService(self.db, custom_dir)
            assert service.documents_dir == Path(custom_dir)
            assert service.documents_dir.exists()
        finally:
            shutil.rmtree(custom_dir)

    # ===== Import Document Tests =====
    def test_import_document_success(self):
        """Test successful document import."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        assert document is not None
        assert document.id is not None
        assert document.title == "Test Document"
        assert document.file_hash is not None
        assert document.content_hash is not None
        assert Path(document.file_path).exists()
        assert Path(document.file_path).parent == self.service.documents_dir

    def test_import_document_default_title(self):
        """Test document import with default title from filename."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path)
        assert document.title == "simple_text"

    def test_import_document_nonexistent_file(self):
        """Test import with nonexistent file."""
        with pytest.raises(DocumentImportError, match="File not found"):
            self.service.import_document("/nonexistent/file.pdf")

    def test_import_document_invalid_pdf(self):
        """Test import with invalid PDF file."""
        corrupted_path = self.get_fixture_path("corrupted.pdf")
        with pytest.raises(DocumentImportError, match="Invalid PDF file"):
            self.service.import_document(corrupted_path)

    @patch(
        "src.services.content_hash_service.ContentHashService.calculate_combined_hashes"
    )
    def test_import_document_hash_calculation_error(self, mock_hash):
        """Test import when hash calculation fails."""
        mock_hash.side_effect = ContentHashError("Hash calculation failed")
        pdf_path = self.get_fixture_path("simple_text.pdf")
        with pytest.raises(DocumentImportError, match="Failed to calculate file hash"):
            self.service.import_document(pdf_path)

    def test_import_document_duplicate_detection(self):
        """Test duplicate detection during import."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Import first time
        doc1 = self.service.import_document(pdf_path, title="First Import")
        # Try to import same file again
        with pytest.raises(DuplicateDocumentError, match="Document already exists"):
            self.service.import_document(pdf_path, title="Second Import")

    def test_import_document_duplicate_overwrite(self):
        """Test overwriting duplicate documents."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Import first time
        doc1 = self.service.import_document(pdf_path, title="First Import")
        original_id = doc1.id
        # Import again with overwrite
        doc2 = self.service.import_document(
            pdf_path, title="Updated Import", overwrite_duplicates=True
        )
        assert doc2.id == original_id
        assert doc2.title == "Updated Import"
        assert doc2.updated_at > doc1.created_at

    def test_import_document_skip_duplicate_check(self):
        """Test importing with duplicate checking disabled."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Import first time
        doc1 = self.service.import_document(pdf_path, title="First Import")
        # Import again with duplicate checking disabled
        doc2 = self.service.import_document(
            pdf_path, title="Second Import", check_duplicates=False
        )
        assert doc2.id != doc1.id
        assert doc2.title == "Second Import"

    @patch("shutil.copy2")
    def test_import_document_copy_failure(self, mock_copy):
        """Test import when file copy fails."""
        mock_copy.side_effect = OSError("Permission denied")
        pdf_path = self.get_fixture_path("simple_text.pdf")
        with pytest.raises(
            DocumentImportError, match="Failed to copy file to managed storage"
        ):
            self.service.import_document(pdf_path)

    # ===== Document Retrieval Tests =====
    def test_get_documents_empty_library(self):
        """Test getting documents from empty library."""
        documents = self.service.get_documents()
        assert documents == []

    def test_get_documents_with_results(self):
        """Test getting documents with results."""
        # Import test documents
        pdf1 = self.get_fixture_path("simple_text.pdf")
        pdf2 = self.get_fixture_path("multi_page.pdf")
        doc1 = self.service.import_document(pdf1, title="Document 1")
        doc2 = self.service.import_document(pdf2, title="Document 2")
        documents = self.service.get_documents()
        assert len(documents) == 2
        document_ids = [d.id for d in documents]
        assert doc1.id in document_ids
        assert doc2.id in document_ids

    def test_get_documents_with_limit(self):
        """Test getting documents with limit."""
        # Import multiple documents
        for i in range(5):
            pdf_path = self.get_fixture_path("simple_text.pdf")
            self.service.import_document(
                pdf_path, title=f"Document {i}", check_duplicates=False
            )
        documents = self.service.get_documents(limit=3)
        assert len(documents) == 3

    def test_get_recent_documents(self):
        """Test getting recent documents."""
        # Import documents with different timestamps
        pdf_path = self.get_fixture_path("simple_text.pdf")
        doc1 = self.service.import_document(
            pdf_path, title="Older Document", check_duplicates=False
        )
        # Simulate older document
        self.db.execute(
            "UPDATE documents SET created_at = ? WHERE id = ?",
            (datetime.now() - timedelta(days=1), doc1.id),
        )
        doc2 = self.service.import_document(
            pdf_path, title="Newer Document", check_duplicates=False
        )
        recent_docs = self.service.get_recent_documents(limit=1)
        assert len(recent_docs) == 1
        assert recent_docs[0].id == doc2.id

    def test_get_document_by_path_success(self):
        """Test finding document by file path."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        imported_doc = self.service.import_document(pdf_path, title="Test Document")
        found_doc = self.service.get_document_by_path(imported_doc.file_path)
        assert found_doc is not None
        assert found_doc.id == imported_doc.id

    def test_get_document_by_path_not_found(self):
        """Test finding document by nonexistent path."""
        found_doc = self.service.get_document_by_path("/nonexistent/path.pdf")
        assert found_doc is None

    def test_get_document_by_id_success(self):
        """Test finding document by ID."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        imported_doc = self.service.import_document(pdf_path, title="Test Document")
        found_doc = self.service.get_document_by_id(imported_doc.id)
        assert found_doc is not None
        assert found_doc.id == imported_doc.id
        assert found_doc.title == "Test Document"

    def test_get_document_by_id_not_found(self):
        """Test finding document by nonexistent ID."""
        found_doc = self.service.get_document_by_id(99999)
        assert found_doc is None

    # ===== Document Deletion Tests =====
    def test_delete_document_success(self):
        """Test successful document deletion."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        managed_file_path = Path(document.file_path)
        assert managed_file_path.exists()
        success = self.service.delete_document(document.id)
        assert success is True
        assert not managed_file_path.exists()
        # Verify document removed from database
        found_doc = self.service.get_document_by_id(document.id)
        assert found_doc is None

    def test_delete_document_not_found(self):
        """Test deleting nonexistent document."""
        success = self.service.delete_document(99999)
        assert success is False

    def test_delete_document_with_vector_index(self):
        """Test deleting document with associated vector index."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        # Create mock vector index
        vector_index = VectorIndexModel(
            document_id=document.id,
            index_path="/fake/vector/path",
            chunk_count=10,
            index_hash="fake_hash",
        )
        # Simulate vector index in database
        self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count, index_hash) VALUES (?, ?, ?, ?)",
            (
                document.id,
                vector_index.index_path,
                vector_index.chunk_count,
                vector_index.index_hash,
            ),
        )
        success = self.service.delete_document(document.id, remove_vector_index=True)
        assert success is True
        # Verify vector index removed
        vector_count = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM vector_indexes WHERE document_id = ?",
            (document.id,),
        )
        assert vector_count["count"] == 0

    @patch("os.unlink")
    def test_delete_document_file_removal_error(self, mock_unlink):
        """Test document deletion when file removal fails."""
        mock_unlink.side_effect = OSError("Permission denied")
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        # Should still succeed even if file removal fails
        success = self.service.delete_document(document.id)
        assert success is True
        # Document should be removed from database
        found_doc = self.service.get_document_by_id(document.id)
        assert found_doc is None

    # ===== Duplicate Detection Tests =====
    def test_find_duplicate_documents_none(self):
        """Test finding duplicates when none exist."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        self.service.import_document(pdf_path, title="Unique Document")
        duplicates = self.service.find_duplicate_documents()
        assert duplicates == []

    def test_find_duplicate_documents_by_content(self):
        """Test finding duplicates by content hash."""
        # Import identical content documents
        pdf1 = self.get_fixture_path("identical_content_1.pdf")
        pdf2 = self.get_fixture_path("identical_content_2.pdf")
        doc1 = self.service.import_document(
            pdf1, title="Document 1", check_duplicates=False
        )
        doc2 = self.service.import_document(
            pdf2, title="Document 2", check_duplicates=False
        )
        duplicates = self.service.find_duplicate_documents()
        assert len(duplicates) == 1
        content_hash, docs = duplicates[0]
        assert len(docs) == 2
        doc_ids = [d.id for d in docs]
        assert doc1.id in doc_ids
        assert doc2.id in doc_ids

    # ===== Library Statistics Tests =====
    def test_get_library_statistics_empty(self):
        """Test getting statistics for empty library."""
        stats = self.service.get_library_statistics()
        assert stats["total_documents"] == 0
        assert stats["total_size_mb"] == 0.0
        assert stats["total_pages"] == 0
        assert stats["unique_content_count"] == 0
        assert stats["duplicate_groups"] == 0
        assert stats["average_size_mb"] == 0.0

    def test_get_library_statistics_with_documents(self):
        """Test getting statistics with documents."""
        pdf1 = self.get_fixture_path("simple_text.pdf")
        pdf2 = self.get_fixture_path("multi_page.pdf")
        self.service.import_document(pdf1, title="Document 1")
        self.service.import_document(pdf2, title="Document 2")
        stats = self.service.get_library_statistics()
        assert stats["total_documents"] == 2
        assert stats["total_size_mb"] > 0
        assert stats["unique_content_count"] == 2
        assert stats["duplicate_groups"] == 0

    # ===== Library Cleanup Tests =====
    def test_cleanup_library_no_orphans(self):
        """Test library cleanup when no orphaned files exist."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        self.service.import_document(pdf_path, title="Valid Document")
        cleanup_results = self.service.cleanup_library()
        assert cleanup_results["orphaned_files_removed"] == 0
        assert cleanup_results["invalid_documents_removed"] == 0
        assert cleanup_results["total_documents_checked"] == 1

    def test_cleanup_library_with_orphaned_files(self):
        """Test library cleanup with orphaned files."""
        # Create orphaned file in documents directory
        orphaned_file = self.service.documents_dir / "orphaned.pdf"
        orphaned_file.write_text("fake pdf content")
        cleanup_results = self.service.cleanup_library()
        assert cleanup_results["orphaned_files_removed"] == 1
        assert not orphaned_file.exists()

    def test_cleanup_library_with_invalid_documents(self):
        """Test library cleanup with invalid document references."""
        # Create document with invalid file path
        self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Invalid Document", "/nonexistent/path.pdf", "fake_hash"),
        )
        cleanup_results = self.service.cleanup_library()
        assert cleanup_results["invalid_documents_removed"] == 1
        # Verify invalid document was removed
        remaining_docs = self.service.get_documents()
        assert len(remaining_docs) == 0

    # ===== Document Integrity Tests =====
    def test_verify_document_integrity_valid(self):
        """Test integrity verification for valid document."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Valid Document")
        integrity_result = self.service.verify_document_integrity(document.id)
        assert integrity_result["file_exists"] is True
        assert integrity_result["file_hash_matches"] is True
        assert integrity_result["is_valid_pdf"] is True
        assert integrity_result["errors"] == []

    def test_verify_document_integrity_missing_file(self):
        """Test integrity verification when file is missing."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        # Remove the managed file
        Path(document.file_path).unlink()
        integrity_result = self.service.verify_document_integrity(document.id)
        assert integrity_result["file_exists"] is False
        assert "File not found" in integrity_result["errors"]

    def test_verify_document_integrity_nonexistent_document(self):
        """Test integrity verification for nonexistent document."""
        integrity_result = self.service.verify_document_integrity(99999)
        assert integrity_result["errors"] == ["Document not found"]

    @patch("src.services.content_hash_service.ContentHashService.calculate_file_hash")
    def test_verify_document_integrity_hash_mismatch(self, mock_hash):
        """Test integrity verification when hash doesn't match."""
        mock_hash.return_value = "different_hash"
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        integrity_result = self.service.verify_document_integrity(document.id)
        assert integrity_result["file_hash_matches"] is False
        assert any(
            "File hash mismatch" in error for error in integrity_result["errors"]
        )

    # ===== Advanced Search Tests =====
    def test_advanced_search_by_title(self):
        """Test advanced search by title."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        doc1 = self.service.import_document(
            pdf_path, title="Python Programming", check_duplicates=False
        )
        doc2 = self.service.import_document(
            pdf_path, title="Java Programming", check_duplicates=False
        )
        doc3 = self.service.import_document(
            pdf_path, title="Data Science", check_duplicates=False
        )
        results = self.service.advanced_search(title_contains="Programming")
        assert len(results) == 2
        titles = [doc.title for doc in results]
        assert "Python Programming" in titles
        assert "Java Programming" in titles
        assert "Data Science" not in titles

    def test_advanced_search_by_date_range(self):
        """Test advanced search by date range."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Create document and modify its date
        doc1 = self.service.import_document(
            pdf_path, title="Old Document", check_duplicates=False
        )
        old_date = datetime.now() - timedelta(days=30)
        self.db.execute(
            "UPDATE documents SET created_at = ? WHERE id = ?", (old_date, doc1.id)
        )
        doc2 = self.service.import_document(
            pdf_path, title="New Document", check_duplicates=False
        )
        # Search for documents from last 7 days
        from_date = datetime.now() - timedelta(days=7)
        results = self.service.advanced_search(created_after=from_date)
        assert len(results) == 1
        assert results[0].id == doc2.id

    def test_advanced_search_by_file_size(self):
        """Test advanced search by file size."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        document = self.service.import_document(pdf_path, title="Test Document")
        # Get the actual file size
        file_size = Path(document.file_path).stat().st_size
        # Search for files smaller than file_size + 1000 bytes
        results = self.service.advanced_search(max_size=file_size + 1000)
        assert len(results) == 1
        assert results[0].id == document.id
        # Search for files larger than file_size + 1000 bytes
        results = self.service.advanced_search(min_size=file_size + 1000)
        assert len(results) == 0

    def test_advanced_search_multiple_criteria(self):
        """Test advanced search with multiple criteria."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        doc1 = self.service.import_document(
            pdf_path, title="Python Guide", check_duplicates=False
        )
        doc2 = self.service.import_document(
            pdf_path, title="Python Advanced", check_duplicates=False
        )
        doc3 = self.service.import_document(
            pdf_path, title="Java Guide", check_duplicates=False
        )
        results = self.service.advanced_search(title_contains="Python", limit=1)
        assert len(results) == 1
        assert "Python" in results[0].title

    # ===== Edge Cases and Error Handling =====
    def test_managed_file_path_creation(self):
        """Test managed file path creation logic."""
        file_hash = "abcdef1234567890"
        filename = "test_document.pdf"
        managed_path = self.service._create_managed_file_path(file_hash, filename)
        expected_filename = "abcdef12.pdf"
        assert managed_path.name == expected_filename
        assert managed_path.parent == self.service.documents_dir

    def test_managed_file_path_no_extension(self):
        """Test managed file path creation without extension."""
        file_hash = "abcdef1234567890"
        filename = "test_document"
        managed_path = self.service._create_managed_file_path(file_hash, filename)
        expected_filename = "abcdef12"
        assert managed_path.name == expected_filename

    @patch("src.services.content_hash_service.ContentHashService.get_file_info")
    def test_import_document_metadata_extraction_error(self, mock_get_info):
        """Test import when metadata extraction fails."""
        mock_get_info.side_effect = Exception("Metadata extraction failed")
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Should still succeed despite metadata extraction failure
        document = self.service.import_document(pdf_path, title="Test Document")
        assert document is not None
        assert document.title == "Test Document"

    def test_service_database_integration(self):
        """Test that service properly integrates with database layer."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        # Import document
        document = self.service.import_document(pdf_path, title="Integration Test")
        # Verify document was saved to database
        db_document = self.db.fetch_one(
            "SELECT * FROM documents WHERE id = ?", (document.id,)
        )
        assert db_document is not None
        assert db_document["title"] == "Integration Test"
        assert db_document["file_path"] == document.file_path
        assert db_document["file_hash"] == document.file_hash
