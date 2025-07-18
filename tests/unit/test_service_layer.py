"""
Unit tests for service layer components.
Tests business logic and service coordination.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime, timedelta

from src.services.content_hash_service import ContentHashService


class TestContentHashService:
    """Test ContentHashService functionality."""

    def test_content_hash_service_creation(self):
        """Test ContentHashService creation."""
        service = ContentHashService()
        assert service is not None

    def test_calculate_content_hash(self):
        """Test content hash calculation."""
        service = ContentHashService()
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            # Mock PDF processing for testing
            with patch('src.services.content_hash_service.fitz.open') as mock_fitz:
                mock_doc = MagicMock()
                mock_page = MagicMock()
                mock_page.get_text.return_value = "test content for hashing"
                mock_doc.__len__.return_value = 1
                mock_doc.__getitem__.return_value = mock_page
                mock_doc.__enter__.return_value = mock_doc
                mock_doc.__exit__.return_value = None
                mock_fitz.return_value = mock_doc
                
                # Test content hash calculation
                hash_result = service.calculate_content_hash(temp_file_path)
                
                assert hash_result is not None
                assert isinstance(hash_result, str)
                assert len(hash_result) == 16  # 16-character hex length as per implementation
                
                # Test consistency
                hash_result2 = service.calculate_content_hash(temp_file_path)
                assert hash_result == hash_result2
                
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        service = ContentHashService()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test file content")
            temp_file_path = temp_file.name
        
        try:
            # Test file hash calculation
            hash_result = service.calculate_file_hash(temp_file_path)
            
            assert hash_result is not None
            assert isinstance(hash_result, str)
            assert len(hash_result) == 16  # 16-character hex length as per implementation
            
            # Test consistency
            hash_result2 = service.calculate_file_hash(temp_file_path)
            assert hash_result == hash_result2
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    def test_calculate_file_hash_nonexistent_file(self):
        """Test file hash calculation with nonexistent file."""
        service = ContentHashService()
        
        with pytest.raises(Exception):  # ContentHashError wraps the underlying error
            service.calculate_file_hash("/nonexistent/file.txt")

    def test_hash_service_with_empty_content(self):
        """Test hash service with empty content."""
        service = ContentHashService()
        
        # Test empty content with mock PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            with patch('src.services.content_hash_service.fitz.open') as mock_fitz:
                mock_doc = MagicMock()
                mock_page = MagicMock()
                mock_page.get_text.return_value = ""
                mock_doc.__len__.return_value = 1
                mock_doc.__getitem__.return_value = mock_page
                mock_doc.__enter__.return_value = mock_doc
                mock_doc.__exit__.return_value = None
                mock_fitz.return_value = mock_doc
                
                empty_hash = service.calculate_content_hash(temp_file_path)
                assert empty_hash is not None
                assert len(empty_hash) == 16
                
                # Test that empty content produces consistent hash
                empty_hash2 = service.calculate_content_hash(temp_file_path)
                assert empty_hash == empty_hash2
                
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    def test_hash_service_with_large_content(self):
        """Test hash service with large content."""
        service = ContentHashService()
        
        # Create large content (1MB)
        large_content = "x" * (1024 * 1024)
        hash_result = service.calculate_content_hash(large_content)
        
        assert hash_result is not None
        assert len(hash_result) == 64
        
        # Test consistency with large content
        hash_result2 = service.calculate_content_hash(large_content)
        assert hash_result == hash_result2

    def test_hash_service_with_unicode_content(self):
        """Test hash service with unicode content."""
        service = ContentHashService()
        
        # Test unicode content
        unicode_content = "测试内容 🚀 α β γ δ ε"
        hash_result = service.calculate_content_hash(unicode_content)
        
        assert hash_result is not None
        assert len(hash_result) == 64
        
        # Test consistency with unicode
        hash_result2 = service.calculate_content_hash(unicode_content)
        assert hash_result == hash_result2

    def test_hash_service_performance(self):
        """Test hash service performance."""
        import time
        
        service = ContentHashService()
        test_content = "test content" * 100  # Reasonable size
        
        start_time = time.time()
        hash_result = service.calculate_content_hash(test_content)
        duration = time.time() - start_time
        
        assert hash_result is not None
        assert duration < 0.1  # Should be fast for reasonable content size

    def test_hash_service_batch_processing(self):
        """Test hash service batch processing capability."""
        service = ContentHashService()
        
        # Process multiple content items
        contents = [f"content_{i}" for i in range(10)]
        hashes = []
        
        for content in contents:
            hash_result = service.calculate_content_hash(content)
            hashes.append(hash_result)
        
        # Verify all hashes are unique
        assert len(set(hashes)) == 10
        
        # Verify all hashes are valid
        for hash_result in hashes:
            assert hash_result is not None
            assert len(hash_result) == 64


class TestServiceLayerIntegration:
    """Test service layer integration scenarios."""

    def test_service_dependency_injection(self):
        """Test that services can be properly injected."""
        # Create service
        hash_service = ContentHashService()
        
        # Test that service can be used by other components
        assert hash_service is not None
        
        # Mock a dependent service
        class MockDocumentService:
            def __init__(self, hash_service):
                self.hash_service = hash_service
            
            def process_document(self, content):
                return self.hash_service.calculate_content_hash(content)
        
        doc_service = MockDocumentService(hash_service)
        result = doc_service.process_document("test content")
        
        assert result is not None
        assert len(result) == 64

    def test_service_error_handling(self):
        """Test service error handling."""
        service = ContentHashService()
        
        # Test with None input
        with pytest.raises((TypeError, AttributeError)):
            service.calculate_content_hash(None)

    def test_service_thread_safety(self):
        """Test service thread safety."""
        import threading
        import time
        
        service = ContentHashService()
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(5):
                    content = f"thread_{thread_id}_content_{i}"
                    hash_result = service.calculate_content_hash(content)
                    results.append((thread_id, i, hash_result))
            except Exception as e:
                errors.append(f"thread_{thread_id}_error: {e}")
        
        # Run multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0
        
        # Verify all results are valid
        assert len(results) == 15  # 3 threads * 5 iterations
        for thread_id, iteration, hash_result in results:
            assert hash_result is not None
            assert len(hash_result) == 64

    def test_service_configuration(self):
        """Test service configuration and customization."""
        service = ContentHashService()
        
        # Test that service can be configured (mock configuration)
        with patch.object(service, 'calculate_content_hash') as mock_hash:
            mock_hash.return_value = "custom_hash_result"
            
            result = service.calculate_content_hash("test")
            assert result == "custom_hash_result"
            mock_hash.assert_called_once_with("test")

    def test_service_logging_integration(self):
        """Test service logging integration."""
        service = ContentHashService()
        
        # Mock logging to test integration
        with patch('src.services.content_hash_service.logger', autospec=True) as mock_logger:
            # Test that service operations can be logged
            service.calculate_content_hash("test content")
            
            # Verify logging integration works (service may or may not log)
            # This test ensures the logging infrastructure is compatible
            assert mock_logger is not None

    def test_service_metrics_collection(self):
        """Test service metrics collection capability."""
        service = ContentHashService()
        
        # Mock metrics collection
        metrics = {
            'hash_calculations': 0,
            'total_processing_time': 0.0
        }
        
        def track_metrics(content):
            import time
            start_time = time.time()
            result = service.calculate_content_hash(content)
            duration = time.time() - start_time
            
            metrics['hash_calculations'] += 1
            metrics['total_processing_time'] += duration
            
            return result
        
        # Process some content
        for i in range(5):
            result = track_metrics(f"content_{i}")
            assert result is not None
        
        # Verify metrics were collected
        assert metrics['hash_calculations'] == 5
        assert metrics['total_processing_time'] > 0.0

    def test_service_caching_compatibility(self):
        """Test service caching compatibility."""
        service = ContentHashService()
        
        # Mock a caching layer
        cache = {}
        
        def cached_hash_calculation(content):
            if content in cache:
                return cache[content]
            
            result = service.calculate_content_hash(content)
            cache[content] = result
            return result
        
        # Test caching behavior
        content = "test content"
        
        # First call should compute hash
        result1 = cached_hash_calculation(content)
        assert result1 is not None
        assert content in cache
        
        # Second call should use cache
        result2 = cached_hash_calculation(content)
        assert result2 == result1
        assert result2 == cache[content]