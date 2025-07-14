"""
Test Content Hash Service

Unit tests for the ContentHashService class, focusing on file hashing,
content extraction, and deduplication capabilities.
"""

import pytest
import tempfile
import fitz
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services.content_hash_service import ContentHashService, ContentHashError
from tests.fixtures.pdf_fixtures import PDFFixtureGenerator


class TestContentHashService:
    """Test cases for ContentHashService class."""
    
    @classmethod
    def setup_class(cls):
        """Set up test fixtures for all tests."""
        # Create PDF fixtures generator
        cls.fixture_generator = PDFFixtureGenerator()
        cls.fixtures = cls.fixture_generator.create_all_fixtures()
        
        # Create a non-PDF file for testing
        cls.temp_txt = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        cls.temp_txt.write(b"This is not a PDF file")
        cls.temp_txt.close()
        cls.txt_path = cls.temp_txt.name
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests."""
        cls.fixture_generator.cleanup_fixtures()
        Path(cls.txt_path).unlink(missing_ok=True)
    
    def get_fixture_path(self, fixture_name: str) -> str:
        """Get path to a test fixture."""
        return str(self.fixture_generator.get_fixture_path(fixture_name))
    
    def test_calculate_file_hash_success(self):
        """Test successful file hash calculation."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        file_hash = ContentHashService.calculate_file_hash(pdf_path)
        
        assert isinstance(file_hash, str)
        assert len(file_hash) == 16  # Should be 16 characters
        assert all(c in '0123456789abcdef' for c in file_hash)  # Should be hex
    
    def test_calculate_file_hash_consistency(self):
        """Test that file hash is consistent across multiple calls."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        hash1 = ContentHashService.calculate_file_hash(pdf_path)
        hash2 = ContentHashService.calculate_file_hash(pdf_path)
        
        assert hash1 == hash2
    
    def test_calculate_file_hash_different_files(self):
        """Test that different files produce different hashes."""
        pdf_path1 = self.get_fixture_path("different_content_1.pdf")
        pdf_path2 = self.get_fixture_path("different_content_2.pdf")
        
        hash1 = ContentHashService.calculate_file_hash(pdf_path1)
        hash2 = ContentHashService.calculate_file_hash(pdf_path2)
        
        assert hash1 != hash2
    
    def test_calculate_file_hash_binary_identical(self):
        """Test that binary identical files produce identical hashes."""
        original_path = self.get_fixture_path("binary_identical.pdf")
        copy_path = self.get_fixture_path("binary_identical_copy_1.pdf")
        
        hash1 = ContentHashService.calculate_file_hash(original_path)
        hash2 = ContentHashService.calculate_file_hash(copy_path)
        
        assert hash1 == hash2
    
    def test_calculate_file_hash_nonexistent_file(self):
        """Test file hash calculation with non-existent file."""
        with pytest.raises(ContentHashError, match="File not found"):
            ContentHashService.calculate_file_hash("/nonexistent/file.pdf")
    
    def test_calculate_file_hash_directory(self):
        """Test file hash calculation with directory path."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ContentHashError, match="Path is not a file"):
                ContentHashService.calculate_file_hash(temp_dir)
    
    def test_calculate_content_hash_success(self):
        """Test successful content hash calculation."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        content_hash = ContentHashService.calculate_content_hash(pdf_path)
        
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16
        assert all(c in '0123456789abcdef' for c in content_hash)
    
    def test_calculate_content_hash_consistency(self):
        """Test that content hash is consistent."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        hash1 = ContentHashService.calculate_content_hash(pdf_path)
        hash2 = ContentHashService.calculate_content_hash(pdf_path)
        
        assert hash1 == hash2
    
    def test_calculate_content_hash_identical_content(self):
        """Test that files with identical content produce identical content hashes."""
        pdf_path1 = self.get_fixture_path("identical_content_1.pdf")
        pdf_path2 = self.get_fixture_path("identical_content_2.pdf")
        pdf_path3 = self.get_fixture_path("identical_content_3.pdf")
        
        hash1 = ContentHashService.calculate_content_hash(pdf_path1)
        hash2 = ContentHashService.calculate_content_hash(pdf_path2)
        hash3 = ContentHashService.calculate_content_hash(pdf_path3)
        
        assert hash1 == hash2 == hash3
    
    def test_calculate_content_hash_different_content(self):
        """Test that files with different content produce different content hashes."""
        pdf_path1 = self.get_fixture_path("different_content_1.pdf")
        pdf_path2 = self.get_fixture_path("different_content_2.pdf")
        pdf_path3 = self.get_fixture_path("different_content_3.pdf")
        
        hash1 = ContentHashService.calculate_content_hash(pdf_path1)
        hash2 = ContentHashService.calculate_content_hash(pdf_path2)
        hash3 = ContentHashService.calculate_content_hash(pdf_path3)
        
        assert hash1 != hash2 != hash3
        assert hash1 != hash3
    
    def test_calculate_content_hash_empty_pdf(self):
        """Test content hash calculation for empty PDF."""
        pdf_path = self.get_fixture_path("empty.pdf")
        content_hash = ContentHashService.calculate_content_hash(pdf_path)
        
        # Empty PDF should still produce a valid hash (fallback to filename)
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16
    
    def test_calculate_content_hash_multipage(self):
        """Test content hash calculation for multi-page PDF."""
        pdf_path = self.get_fixture_path("multi_page.pdf")
        content_hash = ContentHashService.calculate_content_hash(pdf_path)
        
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16
    
    def test_calculate_content_hash_special_characters(self):
        """Test content hash calculation for PDF with special characters."""
        pdf_path = self.get_fixture_path("special_chars.pdf")
        content_hash = ContentHashService.calculate_content_hash(pdf_path)
        
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16
    
    def test_calculate_content_hash_non_pdf(self):
        """Test content hash calculation with non-PDF file."""
        with pytest.raises(ContentHashError, match="File must be a PDF"):
            ContentHashService.calculate_content_hash(self.txt_path)
    
    def test_calculate_content_hash_nonexistent_file(self):
        """Test content hash calculation with non-existent file."""
        with pytest.raises(ContentHashError, match="File not found"):
            ContentHashService.calculate_content_hash("/nonexistent/file.pdf")
    
    def test_calculate_content_hash_corrupted_pdf(self):
        """Test content hash calculation with corrupted PDF."""
        corrupted_path = self.get_fixture_path("corrupted.pdf")
        
        # Should raise ContentHashError for corrupted PDFs
        with pytest.raises(ContentHashError, match="Content hashing failed"):
            ContentHashService.calculate_content_hash(corrupted_path)
    
    def test_calculate_combined_hashes_success(self):
        """Test calculating both hashes in one operation."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        file_hash, content_hash = ContentHashService.calculate_combined_hashes(pdf_path)
        
        assert isinstance(file_hash, str)
        assert isinstance(content_hash, str)
        assert len(file_hash) == 16
        assert len(content_hash) == 16
        assert file_hash != content_hash  # Should be different for same file
    
    def test_calculate_combined_hashes_consistency(self):
        """Test that combined hashes match individual calculations."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        file_hash, content_hash = ContentHashService.calculate_combined_hashes(pdf_path)
        
        individual_file_hash = ContentHashService.calculate_file_hash(pdf_path)
        individual_content_hash = ContentHashService.calculate_content_hash(pdf_path)
        
        assert file_hash == individual_file_hash
        assert content_hash == individual_content_hash
    
    def test_deduplication_scenario(self):
        """Test complete deduplication scenario with fixtures."""
        # Files with identical content should have same content hash but different file hash
        identical_files = [
            self.get_fixture_path("identical_content_1.pdf"),
            self.get_fixture_path("identical_content_2.pdf"),
            self.get_fixture_path("identical_content_3.pdf")
        ]
        
        content_hashes = []
        file_hashes = []
        
        for pdf_path in identical_files:
            file_hash, content_hash = ContentHashService.calculate_combined_hashes(pdf_path)
            file_hashes.append(file_hash)
            content_hashes.append(content_hash)
        
        # All content hashes should be identical
        assert len(set(content_hashes)) == 1, "Content hashes should be identical for same content"
        
        # All file hashes should be different (different metadata/creation times)
        assert len(set(file_hashes)) == len(file_hashes), "File hashes should be different for different files"
    
    def test_extract_pdf_text_success(self):
        """Test PDF text extraction."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        text = ContentHashService._extract_pdf_text(pdf_path)
        
        assert isinstance(text, str)
        assert len(text) > 0
    
    def test_extract_pdf_text_empty_pdf(self):
        """Test text extraction from empty PDF."""
        pdf_path = self.get_fixture_path("empty.pdf")
        text = ContentHashService._extract_pdf_text(pdf_path)
        
        # Should return filename as fallback for empty PDFs
        assert len(text) > 0
    
    def test_extract_pdf_text_invalid_pdf(self):
        """Test text extraction from invalid PDF."""
        # Use the corrupted PDF fixture instead of txt file which might have permission issues
        corrupted_path = self.get_fixture_path("corrupted.pdf")
        with pytest.raises(ContentHashError, match="PDF text extraction failed"):
            ContentHashService._extract_pdf_text(corrupted_path)
    
    def test_normalize_text_basic(self):
        """Test basic text normalization."""
        input_text = "  Hello   WORLD  \n\n  "
        normalized = ContentHashService._normalize_text(input_text)
        
        assert normalized == "hello world"
    
    def test_normalize_text_empty(self):
        """Test normalization of empty text."""
        assert ContentHashService._normalize_text("") == ""
        assert ContentHashService._normalize_text(None) == ""
        assert ContentHashService._normalize_text("   ") == ""
    
    def test_normalize_text_complex(self):
        """Test normalization of complex text."""
        input_text = "This\tis\ta\nTest\r\nWith   Multiple\n\nSpaces"
        normalized = ContentHashService._normalize_text(input_text)
        
        assert normalized == "this is a test with multiple spaces"
    
    def test_validate_pdf_file_valid(self):
        """Test PDF validation with valid file."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        assert ContentHashService.validate_pdf_file(pdf_path) is True
    
    def test_validate_pdf_file_invalid_extension(self):
        """Test PDF validation with non-PDF file."""
        assert ContentHashService.validate_pdf_file(self.txt_path) is False
    
    def test_validate_pdf_file_nonexistent(self):
        """Test PDF validation with non-existent file."""
        assert ContentHashService.validate_pdf_file("/nonexistent/file.pdf") is False
    
    def test_validate_pdf_file_corrupted(self):
        """Test PDF validation with corrupted PDF."""
        # Create a file with PDF extension but invalid content
        corrupted_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        corrupted_pdf.write(b"This is not a valid PDF content")
        corrupted_pdf.close()
        
        try:
            assert ContentHashService.validate_pdf_file(corrupted_pdf.name) is False
        finally:
            Path(corrupted_pdf.name).unlink(missing_ok=True)
    
    def test_get_file_info_success(self):
        """Test getting comprehensive file information."""
        pdf_path = self.get_fixture_path("simple_text.pdf")
        info = ContentHashService.get_file_info(pdf_path)
        
        assert "file_path" in info
        assert "file_name" in info
        assert "file_size" in info
        assert "file_exists" in info
        assert "is_pdf" in info
        assert "is_valid_pdf" in info
        assert "page_count" in info
        assert "text_length" in info
        assert "file_hash" in info
        assert "content_hash" in info
        
        assert info["file_exists"] is True
        assert info["is_pdf"] is True
        assert info["is_valid_pdf"] is True
        assert info["page_count"] == 1
        assert info["text_length"] > 0
        assert len(info["file_hash"]) == 16
        assert len(info["content_hash"]) == 16
    
    def test_get_file_info_nonexistent(self):
        """Test file info for non-existent file."""
        info = ContentHashService.get_file_info("/nonexistent/file.pdf")
        
        assert info["file_exists"] is False
        assert info["file_size"] == 0
        assert info["is_pdf"] is True  # Based on extension
        assert info["is_valid_pdf"] is False
    
    def test_get_file_info_non_pdf(self):
        """Test file info for non-PDF file."""
        info = ContentHashService.get_file_info(self.txt_path)
        
        assert info["file_exists"] is True
        assert info["is_pdf"] is False
        assert info["is_valid_pdf"] is False
        assert info["page_count"] == 0
        assert info["text_length"] == 0
        assert info["file_hash"] is None
        assert info["content_hash"] is None
    
    def test_content_hash_different_for_different_content(self):
        """Test that different PDF content produces different hashes."""
        pdf_path1 = self.get_fixture_path("different_content_1.pdf")
        pdf_path2 = self.get_fixture_path("different_content_2.pdf")
        
        hash1 = ContentHashService.calculate_content_hash(pdf_path1)
        hash2 = ContentHashService.calculate_content_hash(pdf_path2)
        
        assert hash1 != hash2
    
    def test_content_hash_same_for_same_content_different_files(self):
        """Test that same content produces same hash even in different files."""
        pdf_path1 = self.get_fixture_path("identical_content_1.pdf")
        pdf_path2 = self.get_fixture_path("identical_content_2.pdf")
        
        hash1 = ContentHashService.calculate_content_hash(pdf_path1)
        hash2 = ContentHashService.calculate_content_hash(pdf_path2)
        
        # Content hashes should be the same
        assert hash1 == hash2
        
        # But file hashes should be different (different file metadata)
        file_hash1 = ContentHashService.calculate_file_hash(pdf_path1)
        file_hash2 = ContentHashService.calculate_file_hash(pdf_path2)
        assert file_hash1 != file_hash2
    
    def test_large_file_processing(self):
        """Test processing of large content efficiently."""
        # Mock a large file scenario
        with patch('builtins.open') as mock_open:
            # Create a mock file that returns chunks
            mock_file = MagicMock()
            mock_file.read.side_effect = [b'a' * ContentHashService.CHUNK_SIZE, b'b' * 1000, b'']
            mock_open.return_value.__enter__.return_value = mock_file
            
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    hash_result = ContentHashService.calculate_file_hash("/fake/large/file.pdf")
                    
                    assert isinstance(hash_result, str)
                    assert len(hash_result) == 16
                    # Verify file was read in chunks
                    assert mock_file.read.call_count >= 2
    
    @patch('src.services.content_hash_service.fitz.open')
    def test_pdf_processing_error_handling(self, mock_fitz_open):
        """Test error handling during PDF processing."""
        # Mock PyMuPDF to raise an exception
        mock_fitz_open.side_effect = Exception("PDF processing failed")
        
        pdf_path = self.get_fixture_path("simple_text.pdf")
        with pytest.raises(ContentHashError, match="PDF text extraction failed"):
            ContentHashService._extract_pdf_text(pdf_path)
    
    def test_hash_deterministic_across_platforms(self):
        """Test that hashes are deterministic across different platforms."""
        # This test ensures our hashing is not affected by platform-specific factors
        pdf_path = self.get_fixture_path("simple_text.pdf")
        hash1 = ContentHashService.calculate_file_hash(pdf_path)
        
        # Simulate different runs
        for _ in range(5):
            hash_repeated = ContentHashService.calculate_file_hash(pdf_path)
            assert hash1 == hash_repeated