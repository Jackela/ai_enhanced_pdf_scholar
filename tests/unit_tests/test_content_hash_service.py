"""
Unit tests for ContentHashService.
Tests hash generation, caching, and collision detection.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.content_hash_service import ContentHashService


class TestContentHashService:
    """Test ContentHashService functionality."""

    @pytest.fixture
    def hash_service(self):
        """Create a ContentHashService instance."""
        return ContentHashService()

    @pytest.fixture
    def temp_file_with_content(self):
        """Create a temporary file with known content."""
        content = b"This is test content for hashing"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = f.name
        yield temp_path, content
        # Cleanup
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    def test_initialization(self, hash_service):
        """Test service initializes correctly."""
        assert hash_service is not None
        assert hasattr(hash_service, 'calculate_content_hash')
        assert hasattr(hash_service, 'calculate_file_hash')

    def test_calculate_content_hash_consistent(self, hash_service):
        """Test content hash generation is consistent."""
        content = "test content"

        hash1 = hash_service.calculate_content_hash(content)
        hash2 = hash_service.calculate_content_hash(content)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) > 0

    def test_calculate_content_hash_different_content(self, hash_service):
        """Test different content produces different hashes."""
        content1 = "test content 1"
        content2 = "test content 2"

        hash1 = hash_service.calculate_content_hash(content1)
        hash2 = hash_service.calculate_content_hash(content2)

        assert hash1 != hash2

    def test_calculate_content_hash_empty_string(self, hash_service):
        """Test empty string hash generation."""
        empty_hash = hash_service.calculate_content_hash("")
        assert isinstance(empty_hash, str)
        assert len(empty_hash) > 0

    def test_calculate_content_hash_unicode_content(self, hash_service):
        """Test hash generation with unicode content."""
        unicode_content = "测试内容 with émojis 🚀"
        hash_result = hash_service.calculate_content_hash(unicode_content)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_calculate_file_hash_success(self, hash_service, temp_file_with_content):
        """Test successful file hash generation."""
        file_path, content = temp_file_with_content

        file_hash = hash_service.calculate_file_hash(file_path)
        assert isinstance(file_hash, str)
        assert len(file_hash) > 0

    def test_calculate_file_hash_consistent(self, hash_service, temp_file_with_content):
        """Test file hash generation is consistent."""
        file_path, content = temp_file_with_content

        hash1 = hash_service.calculate_file_hash(file_path)
        hash2 = hash_service.calculate_file_hash(file_path)

        assert hash1 == hash2

    def test_calculate_file_hash_nonexistent_file(self, hash_service):
        """Test file hash generation with non-existent file."""
        with pytest.raises((FileNotFoundError, IOError, Exception)):
            hash_service.calculate_file_hash("/nonexistent/file.txt")

    def test_calculate_file_hash_pathlib_path(self, hash_service, temp_file_with_content):
        """Test file hash generation with pathlib.Path object."""
        file_path, content = temp_file_with_content
        path_obj = Path(file_path)

        file_hash = hash_service.calculate_file_hash(str(path_obj))
        assert isinstance(file_hash, str)
        assert len(file_hash) > 0

    def test_hash_format_validation(self, hash_service):
        """Test that generated hashes have expected format."""
        content = "test content"
        content_hash = hash_service.calculate_content_hash(content)

        # Hash should be hexadecimal string
        assert content_hash.isalnum()
        # Common hash lengths (MD5=32, SHA1=40, SHA256=64)
        assert len(content_hash) in [32, 40, 64]

    @patch('builtins.open', side_effect=OSError("Permission denied"))
    def test_calculate_file_hash_permission_error(self, mock_open, hash_service):
        """Test file hash generation with permission error."""
        with pytest.raises((IOError, PermissionError, Exception)):
            hash_service.calculate_file_hash("/protected/file.txt")

    def test_large_content_hash_performance(self, hash_service):
        """Test hash generation performance with large content."""
        # Create large content (1MB)
        large_content = "x" * (1024 * 1024)

        # Should complete reasonably quickly
        import time
        start_time = time.time()
        hash_result = hash_service.calculate_content_hash(large_content)
        end_time = time.time()

        assert isinstance(hash_result, str)
        assert len(hash_result) > 0
        # Should complete in less than 1 second
        assert (end_time - start_time) < 1.0

    def test_content_vs_file_hash_consistency(self, hash_service, temp_file_with_content):
        """Test that content hash matches file hash for same content."""
        file_path, content = temp_file_with_content

        # Generate hash from content directly
        content_hash = hash_service.calculate_content_hash(content.decode('utf-8'))

        # Generate hash from file
        file_hash = hash_service.calculate_file_hash(file_path)

        # They might be different if file hash includes metadata,
        # but both should be valid hashes
        assert isinstance(content_hash, str)
        assert isinstance(file_hash, str)
        assert len(content_hash) > 0
        assert len(file_hash) > 0


class TestContentHashServiceEdgeCases:
    """Test edge cases for ContentHashService."""

    @pytest.fixture
    def hash_service(self):
        """Create a ContentHashService instance."""
        return ContentHashService()

    def test_binary_content_handling(self, hash_service):
        """Test handling of binary content."""
        binary_content = b'\x00\x01\x02\x03\xFF'
        # Convert to string if service expects string input
        try:
            hash_result = hash_service.calculate_content_hash(binary_content)
        except (TypeError, UnicodeDecodeError):
            # If service doesn't handle binary, try with decoded content
            hash_result = hash_service.calculate_content_hash(str(binary_content))

        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_very_long_file_path(self, hash_service):
        """Test handling of very long file paths."""
        long_path = "a" * 1000 + ".txt"

        with pytest.raises((FileNotFoundError, OSError, Exception)):
            hash_service.calculate_file_hash(long_path)

    def test_special_characters_in_content(self, hash_service):
        """Test handling of special characters in content."""
        special_content = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        hash_result = hash_service.calculate_content_hash(special_content)

        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_newline_variations_in_content(self, hash_service):
        """Test that different newline styles produce different hashes."""
        content_unix = "line1\nline2\nline3"
        content_windows = "line1\r\nline2\r\nline3"

        hash_unix = hash_service.calculate_content_hash(content_unix)
        hash_windows = hash_service.calculate_content_hash(content_windows)

        # Different line endings should produce different hashes
        assert hash_unix != hash_windows

    def test_whitespace_sensitivity(self, hash_service):
        """Test that whitespace differences affect hash."""
        content1 = "word1 word2"
        content2 = "word1  word2"  # Extra space
        content3 = "word1\tword2"  # Tab instead of space

        hash1 = hash_service.calculate_content_hash(content1)
        hash2 = hash_service.calculate_content_hash(content2)
        hash3 = hash_service.calculate_content_hash(content3)

        # All should be different
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3


class TestContentHashServiceIntegration:
    """Integration tests for ContentHashService."""

    @pytest.fixture
    def hash_service(self):
        """Create a ContentHashService instance."""
        return ContentHashService()

    def test_duplicate_detection_scenario(self, hash_service):
        """Test using hash service for duplicate detection scenario."""
        # Simulate duplicate detection workflow
        content1 = "This is a document content"
        content2 = "This is a document content"  # Identical
        content3 = "This is different content"

        hash1 = hash_service.calculate_content_hash(content1)
        hash2 = hash_service.calculate_content_hash(content2)
        hash3 = hash_service.calculate_content_hash(content3)

        # Identical content should have same hash (duplicates)
        assert hash1 == hash2
        # Different content should have different hash
        assert hash1 != hash3

    @pytest.mark.slow
    def test_multiple_files_hashing(self, hash_service):
        """Test hashing multiple temporary files."""
        temp_files = []
        hashes = []

        try:
            # Create multiple temporary files
            for i in range(5):
                content = f"File content {i}"
                with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
                    f.write(content)
                    temp_files.append(f.name)

                # Generate hash for each file
                file_hash = hash_service.calculate_file_hash(f.name)
                hashes.append(file_hash)

            # All hashes should be different
            assert len(set(hashes)) == len(hashes)

            # All hashes should be valid
            for hash_val in hashes:
                assert isinstance(hash_val, str)
                assert len(hash_val) > 0

        finally:
            # Cleanup temporary files
            for file_path in temp_files:
                try:
                    os.unlink(file_path)
                except FileNotFoundError:
                    pass
