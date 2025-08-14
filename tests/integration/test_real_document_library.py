"""
Real Document Library Integration Tests

This module replaces mock-based tests with actual PDF processing to validate
document library operations. Tests use real PDFs with actual file operations,
hash calculations, and metadata extraction.

Key differences from mock tests:
- Uses real PDF files and text extraction
- Performs actual hash calculations and comparisons
- Tests real file system operations and error conditions
- Validates actual metadata extraction and storage
- Tests performance with real processing times
"""

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pytest
import fitz  # PyMuPDF for PDF validation

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.services.document_library_service import (
    DocumentLibraryService,
    DocumentImportError,
    DuplicateDocumentError,
)
from tests.fixtures.pdf_fixtures import PDFFixtureGenerator
from tests.fixtures.academic_pdf_generator import AcademicPDFGenerator


class TestRealDocumentLibrary:
    """Integration tests for document library with real PDF processing."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures and database."""
        # Create PDF fixtures
        cls.pdf_generator = PDFFixtureGenerator()
        cls.academic_generator = AcademicPDFGenerator()

        # Generate real PDF fixtures
        cls.basic_fixtures = cls.pdf_generator.create_all_fixtures()
        cls.academic_fixtures = cls.academic_generator.create_all_academic_fixtures()

        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name

        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test fixtures and database."""
        cls.pdf_generator.cleanup_fixtures()
        if hasattr(cls.academic_generator, 'cleanup_fixtures'):
            cls.academic_generator.cleanup_fixtures()
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        cls.db.execute("""
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
        """)

    def setup_method(self):
        """Set up for each test method."""
        # Create temporary documents directory
        self.temp_docs_dir = tempfile.mkdtemp()

        # Create service instance
        self.service = DocumentLibraryService(
            db_connection=self.db,
            documents_dir=self.temp_docs_dir
        )

        # Clear database for fresh test
        self.db.execute("DELETE FROM documents")

    def teardown_method(self):
        """Clean up after each test method."""
        if Path(self.temp_docs_dir).exists():
            shutil.rmtree(self.temp_docs_dir)

    def get_fixture_path(self, fixture_name: str) -> str:
        """Get path to a test fixture."""
        return str(self.pdf_generator.get_fixture_path(fixture_name))

    def get_academic_fixture_path(self, fixture_name: str) -> str:
        """Get path to an academic test fixture."""
        return str(self.academic_generator.get_fixture_path(fixture_name))

    # ===== Real PDF Import Tests =====

    def test_import_real_academic_papers(self):
        """Test importing actual academic papers with real content extraction."""
        academic_papers = [
            ("ai_research_sample.pdf", "AI Research Paper"),
            ("cv_research_sample.pdf", "Computer Vision Paper"),
            ("data_science_sample.pdf", "Data Science Paper")
        ]

        imported_docs = []

        for filename, title in academic_papers:
            pdf_path = self.get_academic_fixture_path(filename)
            if not Path(pdf_path).exists():
                continue

            start_time = time.time()
            document = self.service.import_document(pdf_path, title=title)
            import_time = time.time() - start_time

            # Validate real import
            assert document is not None
            assert document.id is not None
            assert document.title == title
            assert document.file_size > 0
            assert document.page_count > 0

            # Verify actual file was copied
            managed_path = Path(document.file_path)
            assert managed_path.exists()
            assert managed_path.stat().st_size == document.file_size

            # Validate PDF content is accessible
            actual_text = self._extract_pdf_text(managed_path)
            assert len(actual_text) > 500  # Academic papers should have substantial content

            imported_docs.append({
                'document': document,
                'filename': filename,
                'import_time': import_time,
                'text_length': len(actual_text)
            })

        assert len(imported_docs) > 0, "Should import at least one academic paper"

        # Validate import performance
        avg_import_time = sum(d['import_time'] for d in imported_docs) / len(imported_docs)
        assert avg_import_time < 5, f"Import too slow: {avg_import_time:.2f}s average"

        # Print summary
        print(f"Imported {len(imported_docs)} academic papers:")
        for doc_info in imported_docs:
            doc = doc_info['document']
            print(f"  {doc_info['filename']}: {doc.file_size} bytes, {doc.page_count} pages")
            print(f"    Import time: {doc_info['import_time']:.2f}s")
            print(f"    Text content: {doc_info['text_length']} chars")

    def test_real_duplicate_detection_by_content_hash(self):
        """Test duplicate detection using actual PDF content hashes."""
        # Use identical content PDFs generated by fixture generator
        identical_pdfs = self.pdf_generator.create_identical_content_pdfs()

        # Import first PDF
        first_path = str(identical_pdfs[0])
        doc1 = self.service.import_document(first_path, title="First Import")

        # Verify content hash was calculated
        assert doc1.content_hash is not None
        assert len(doc1.content_hash) > 0

        # Extract and verify actual content
        text1 = self._extract_pdf_text(Path(doc1.file_path))
        assert len(text1) > 0

        # Try to import second PDF with identical content
        second_path = str(identical_pdfs[1])

        with pytest.raises(DuplicateDocumentError) as exc_info:
            self.service.import_document(second_path, title="Second Import")

        assert "already exists" in str(exc_info.value)

        # Verify only one document in database
        all_docs = self.service.get_documents()
        assert len(all_docs) == 1

        print(f"Content-based duplicate detection working correctly")
        print(f"Original content hash: {doc1.content_hash[:16]}...")
        print(f"Content length: {len(text1)} characters")

    def test_real_file_hash_vs_content_hash_difference(self):
        """Test that file hash and content hash are different but both valid."""
        # Use binary identical PDFs (same file, different names)
        binary_identical_path = self.get_fixture_path("binary_identical.pdf")
        copy1_path = self.get_fixture_path("binary_identical_copy_1.pdf")

        # Import both files
        doc1 = self.service.import_document(binary_identical_path, title="Original")

        # Should be able to import copy because it has different file path
        # but same content, so duplicate detection should trigger
        with pytest.raises(DuplicateDocumentError):
            self.service.import_document(copy1_path, title="Copy", check_duplicates=True)

        # But can import if we disable duplicate checking
        doc2 = self.service.import_document(copy1_path, title="Copy", check_duplicates=False)

        # Both documents should have same file hash and content hash
        assert doc1.file_hash == doc2.file_hash  # Binary identical
        assert doc1.content_hash == doc2.content_hash  # Same content

        print(f"File hash validation:")
        print(f"  Doc1 file hash: {doc1.file_hash[:16]}...")
        print(f"  Doc2 file hash: {doc2.file_hash[:16]}...")
        print(f"  Hashes match: {doc1.file_hash == doc2.file_hash}")

    def test_real_pdf_metadata_extraction(self):
        """Test metadata extraction from real PDF files."""
        # Test with academic paper that has rich metadata
        ai_paper_path = self.get_academic_fixture_path("ai_research_sample.pdf")

        document = self.service.import_document(ai_paper_path, title="AI Research Test")

        # Validate basic metadata
        assert document.file_size > 0
        assert document.page_count >= 3  # AI paper has 3 pages

        # Parse stored metadata
        if document.metadata:
            if isinstance(document.metadata, str):
                metadata = json.loads(document.metadata)
            else:
                metadata = document.metadata

            # Should contain extracted metadata
            assert isinstance(metadata, dict)

            # Check for expected metadata fields
            expected_fields = ['file_extension', 'original_filename']
            for field in expected_fields:
                if field in metadata:
                    print(f"Found metadata field '{field}': {metadata[field]}")

        # Verify actual PDF properties using PyMuPDF
        actual_metadata = self._get_real_pdf_metadata(Path(document.file_path))

        assert actual_metadata['page_count'] == document.page_count
        assert actual_metadata['file_size'] == document.file_size

        print(f"PDF metadata validation:")
        print(f"  Stored page count: {document.page_count}")
        print(f"  Actual page count: {actual_metadata['page_count']}")
        print(f"  File size: {document.file_size} bytes")

    def test_real_library_statistics_calculation(self):
        """Test library statistics with real documents and calculations."""
        # Import several different sized academic papers
        papers_to_import = [
            ("ai_research_sample.pdf", "AI Research"),
            ("cv_research_sample.pdf", "Computer Vision"),
            ("data_science_sample.pdf", "Data Science")
        ]

        imported_sizes = []
        imported_pages = []

        for filename, title in papers_to_import:
            pdf_path = self.get_academic_fixture_path(filename)
            if not Path(pdf_path).exists():
                continue

            document = self.service.import_document(pdf_path, title=title)
            imported_sizes.append(document.file_size)
            imported_pages.append(document.page_count)

        # Get library statistics
        stats = self.service.get_library_statistics()

        # Validate statistics match reality
        expected_total_docs = len(imported_sizes)
        expected_total_size = sum(imported_sizes)
        expected_total_pages = sum(imported_pages)
        expected_avg_size = expected_total_size / max(expected_total_docs, 1) / (1024 * 1024)  # MB

        assert stats["total_documents"] == expected_total_docs
        assert stats["total_pages"] == expected_total_pages
        assert abs(stats["total_size_mb"] - expected_total_size / (1024 * 1024)) < 0.1
        assert abs(stats["average_size_mb"] - expected_avg_size) < 0.1

        # All academic papers should have unique content
        assert stats["unique_content_count"] == expected_total_docs
        assert stats["duplicate_groups"] == 0

        print(f"Library statistics validation:")
        print(f"  Documents: {stats['total_documents']} (expected {expected_total_docs})")
        print(f"  Total size: {stats['total_size_mb']:.2f} MB")
        print(f"  Total pages: {stats['total_pages']}")
        print(f"  Average size: {stats['average_size_mb']:.2f} MB")

    def test_real_document_integrity_verification(self):
        """Test document integrity with real file operations."""
        # Import a document
        pdf_path = self.get_academic_fixture_path("ai_research_sample.pdf")
        document = self.service.import_document(pdf_path, title="Integrity Test")

        # Verify initial integrity
        integrity = self.service.verify_document_integrity(document.id)
        assert integrity["file_exists"] is True
        assert integrity["file_hash_matches"] is True
        assert integrity["is_valid_pdf"] is True
        assert len(integrity["errors"]) == 0

        # Corrupt the file by truncating it
        managed_path = Path(document.file_path)
        original_size = managed_path.stat().st_size

        # Write partial content to simulate corruption
        with open(managed_path, 'r+b') as f:
            f.truncate(original_size // 2)

        # Verify integrity detection
        integrity = self.service.verify_document_integrity(document.id)
        assert integrity["file_exists"] is True
        assert integrity["file_hash_matches"] is False  # Hash should not match
        assert len(integrity["errors"]) > 0

        # Check specific error messages
        error_messages = " ".join(integrity["errors"]).lower()
        assert "hash mismatch" in error_messages

        print(f"Integrity verification test:")
        print(f"  Original size: {original_size} bytes")
        print(f"  Corrupted size: {managed_path.stat().st_size} bytes")
        print(f"  Detected integrity issues: {len(integrity['errors'])}")

    def test_real_library_cleanup_operations(self):
        """Test library cleanup with real file operations."""
        # Import a document
        pdf_path = self.get_academic_fixture_path("cv_research_sample.pdf")
        document = self.service.import_document(pdf_path, title="Cleanup Test")

        managed_path = Path(document.file_path)
        assert managed_path.exists()

        # Create an orphaned file in the documents directory
        orphaned_file = Path(self.temp_docs_dir) / "orphaned_file.pdf"
        orphaned_file.write_text("fake pdf content")

        # Create invalid document record (file doesn't exist)
        self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Invalid Doc", "/nonexistent/path.pdf", "fake_hash")
        )

        # Perform cleanup
        cleanup_results = self.service.cleanup_library()

        # Verify cleanup results
        assert cleanup_results["total_documents_checked"] == 2  # Valid + invalid
        assert cleanup_results["invalid_documents_removed"] == 1
        assert cleanup_results["orphaned_files_removed"] == 1

        # Verify valid document is still there
        remaining_docs = self.service.get_documents()
        assert len(remaining_docs) == 1
        assert remaining_docs[0].id == document.id
        assert managed_path.exists()

        # Verify orphaned file was removed
        assert not orphaned_file.exists()

        print(f"Cleanup operation results:")
        print(f"  Documents checked: {cleanup_results['total_documents_checked']}")
        print(f"  Invalid documents removed: {cleanup_results['invalid_documents_removed']}")
        print(f"  Orphaned files removed: {cleanup_results['orphaned_files_removed']}")

    def test_real_search_functionality(self):
        """Test document search with real content."""
        # Import papers with different content
        papers_and_keywords = [
            ("ai_research_sample.pdf", "AI NLP Research", ["bert", "transformer", "nlp"]),
            ("cv_research_sample.pdf", "Computer Vision", ["cnn", "image", "convolution"]),
            ("data_science_sample.pdf", "Healthcare ML", ["healthcare", "patient", "medical"])
        ]

        imported_docs = []

        for filename, title, keywords in papers_and_keywords:
            pdf_path = self.get_academic_fixture_path(filename)
            if not Path(pdf_path).exists():
                continue

            document = self.service.import_document(pdf_path, title=title)
            imported_docs.append((document, keywords))

        # Test title-based search
        bert_search = self.service.advanced_search(title_contains="AI")
        assert len(bert_search) == 1
        assert "AI" in bert_search[0].title

        # Test date-based search
        recent_search = self.service.advanced_search(
            created_after=datetime.now() - timedelta(minutes=5)
        )
        assert len(recent_search) == len(imported_docs)

        # Test size-based search
        for doc, _ in imported_docs:
            size_search = self.service.advanced_search(
                min_size=doc.file_size - 1000,
                max_size=doc.file_size + 1000
            )
            assert any(d.id == doc.id for d in size_search)

        print(f"Search functionality validation:")
        print(f"  Total documents: {len(imported_docs)}")
        print(f"  Title search results: {len(bert_search)}")
        print(f"  Recent documents: {len(recent_search)}")

    def test_performance_benchmarks_real_processing(self):
        """Benchmark real PDF processing performance."""
        # Test with different sized documents
        test_files = [
            ("ai_research_sample.pdf", "Small academic paper (3 pages)"),
            ("cv_research_sample.pdf", "Medium academic paper (2 pages)"),
            ("data_science_sample.pdf", "Large academic paper (2 pages)")
        ]

        performance_results = []

        for filename, description in test_files:
            pdf_path = self.get_academic_fixture_path(filename)
            if not Path(pdf_path).exists():
                continue

            # Measure import performance
            start_time = time.time()
            document = self.service.import_document(pdf_path, title=f"Perf Test {filename}")
            import_time = time.time() - start_time

            # Measure text extraction time
            start_time = time.time()
            text = self._extract_pdf_text(Path(document.file_path))
            extract_time = time.time() - start_time

            # Measure integrity check time
            start_time = time.time()
            integrity = self.service.verify_document_integrity(document.id)
            integrity_time = time.time() - start_time

            performance_results.append({
                'description': description,
                'file_size': document.file_size,
                'page_count': document.page_count,
                'text_length': len(text),
                'import_time': import_time,
                'extract_time': extract_time,
                'integrity_time': integrity_time,
                'total_time': import_time + extract_time + integrity_time
            })

        # Validate performance is reasonable
        for result in performance_results:
            assert result['import_time'] < 3, f"Import too slow: {result['import_time']:.2f}s"
            assert result['extract_time'] < 1, f"Extraction too slow: {result['extract_time']:.2f}s"
            assert result['integrity_time'] < 2, f"Integrity check too slow: {result['integrity_time']:.2f}s"

        # Calculate averages
        avg_import_time = sum(r['import_time'] for r in performance_results) / len(performance_results)
        avg_extract_time = sum(r['extract_time'] for r in performance_results) / len(performance_results)

        print("Performance benchmark results:")
        for result in performance_results:
            print(f"  {result['description']}:")
            print(f"    File: {result['file_size']} bytes, {result['page_count']} pages")
            print(f"    Text: {result['text_length']} chars")
            print(f"    Import: {result['import_time']:.3f}s")
            print(f"    Extract: {result['extract_time']:.3f}s")
            print(f"    Integrity: {result['integrity_time']:.3f}s")
            print(f"    Total: {result['total_time']:.3f}s")

        print(f"Average times:")
        print(f"  Import: {avg_import_time:.3f}s")
        print(f"  Extract: {avg_extract_time:.3f}s")

    # ===== Helper Methods =====

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            doc = fitz.open(str(pdf_path))
            text = ""
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            print(f"Warning: Could not extract text from {pdf_path}: {e}")
            return ""

    def _get_real_pdf_metadata(self, pdf_path: Path) -> Dict:
        """Get actual PDF metadata using PyMuPDF."""
        try:
            doc = fitz.open(str(pdf_path))
            metadata = {
                'page_count': doc.page_count,
                'file_size': pdf_path.stat().st_size,
                'metadata': doc.metadata
            }
            doc.close()
            return metadata
        except Exception as e:
            return {'page_count': 0, 'file_size': 0, 'metadata': {}, 'error': str(e)}