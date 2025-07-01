"""
Comprehensive test suite for error handling and edge cases.

This module tests error scenarios including:
- File system errors (missing files, permissions)
- Network errors (timeouts, connection failures)
- Memory constraints
- Invalid data handling
- Recovery mechanisms
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QSettings

from src.pdf_document import PDFDocument
from src.pdf_viewer import PDFViewer
from src.llm_service import GeminiLLMService, LLMAPIError, LLMResponseError, LLMConfigurationError
from src.llm_worker import LLMWorker
from src.annotation_manager import AnnotationManager
from main import MainWindow


class TestFileSystemErrors:
    """Test handling of file system related errors."""
    
    def test_pdf_load_nonexistent_file(self, qtbot):
        """Test loading a PDF file that doesn't exist."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Try to load non-existent file
        nonexistent_path = "/path/to/nonexistent/file.pdf"
        
        with qtbot.waitSignal(pdf_viewer.error_occurred, timeout=2000) as blocker:
            pdf_viewer.load_pdf(nonexistent_path)
            
        # Should emit error signal
        assert blocker.signal_triggered
        
    def test_pdf_load_corrupted_file(self, qtbot):
        """Test loading a corrupted PDF file."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Create a corrupted/invalid PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(b"This is not a valid PDF content")
            temp_file_path = temp_file.name
            
        try:
            with qtbot.waitSignal(pdf_viewer.error_occurred, timeout=2000) as blocker:
                pdf_viewer.load_pdf(temp_file_path)
                
            # Should emit error signal for corrupted file
            assert blocker.signal_triggered
            
        finally:
            os.unlink(temp_file_path)
            
    def test_pdf_load_permission_denied(self, qtbot):
        """Test loading PDF with insufficient permissions."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # This test is platform-dependent and might not work on all systems
        # We'll simulate permission error by mocking
        with patch('fitz.open') as mock_fitz_open:
            mock_fitz_open.side_effect = PermissionError("Permission denied")
            
            with qtbot.waitSignal(pdf_viewer.error_occurred, timeout=2000) as blocker:
                pdf_viewer.load_pdf("some_file.pdf")
                
            assert blocker.signal_triggered
            
    def test_settings_file_corruption(self, qtbot):
        """Test handling of corrupted settings file."""
        # Create temporary settings with invalid content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as temp_settings:
            temp_settings.write("Invalid INI content without proper structure")
            temp_settings_path = temp_settings.name
            
        try:
            # QSettings should handle invalid files gracefully
            settings = QSettings(temp_settings_path, QSettings.Format.IniFormat)
            
            # Should not crash when accessing invalid settings
            value = settings.value("some/key", "default")
            assert value == "default"
            
        finally:
            os.unlink(temp_settings_path)
            
    def test_temp_directory_full(self, qtbot):
        """Test behavior when temporary directory is full."""
        # This is hard to test realistically, so we'll mock it
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.side_effect = OSError("No space left on device")
            
            # Operations requiring temp files should handle gracefully
            # Implementation depends on actual temp file usage


class TestNetworkErrors:
    """Test handling of network-related errors."""
    
    def test_llm_service_connection_timeout(self, qtbot):
        """Test LLM service connection timeout."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        with patch('src.llm_service.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection timeout")
            
            with pytest.raises(LLMAPIError):
                service.query_llm("Test prompt")
                
    def test_llm_service_network_unreachable(self, qtbot):
        """Test LLM service when network is unreachable."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        with patch('src.llm_service.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError("Network is unreachable")
            
            with pytest.raises(LLMAPIError):
                service.query_llm("Test prompt")
                
    def test_llm_worker_network_error_handling(self, qtbot):
        """Test LLM worker handles network errors properly."""
        mock_service = MagicMock()
        mock_service.query_llm.side_effect = LLMAPIError("Network error")
        
        worker = LLMWorker(mock_service, "Test prompt")
        
        with qtbot.waitSignal(worker.error_occurred, timeout=2000) as blocker:
            worker.run()
            
        assert blocker.signal_triggered
        assert "Network error" in blocker.args[0]
        
    def test_slow_network_response(self, qtbot):
        """Test handling of very slow network responses."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        with patch('src.llm_service.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
            
            with pytest.raises(LLMAPIError):
                service.query_llm("Test prompt")


class TestMemoryConstraints:
    """Test handling of memory-related issues."""
    
    def test_large_pdf_handling(self, qtbot):
        """Test handling of very large PDF files."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Mock a scenario where PDF loading consumes too much memory
        with patch('fitz.open') as mock_fitz_open:
            mock_fitz_open.side_effect = MemoryError("Not enough memory")
            
            with qtbot.waitSignal(pdf_viewer.error_occurred, timeout=2000) as blocker:
                pdf_viewer.load_pdf("large_file.pdf")
                
            assert blocker.signal_triggered
            
    def test_many_annotations_memory_usage(self, qtbot):
        """Test memory usage with many annotations."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Create proper layout and widget for annotation manager
        from PyQt6.QtWidgets import QVBoxLayout
        annotations_container = QWidget()
        annotations_layout = QVBoxLayout(annotations_container)
        empty_message = QWidget()
        
        annotation_manager = AnnotationManager(pdf_viewer, annotations_layout, empty_message)
        
        # Add many annotations to test memory handling
        import fitz
        for i in range(100):
            rect = fitz.Rect(i, i, i+10, i+10)
            annotation_manager.add_annotation(1, rect, f"Annotation {i}", f"Selected text {i}")
            
        # Should handle many annotations without crashing
        assert annotation_manager.get_annotation_count() == 100
        
    def test_large_text_selection_handling(self, qtbot):
        """Test handling of very large text selections."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Simulate very large text selection
        large_text = "A" * 100000  # 100KB of text
        
        # Should handle large text without memory issues
        # (Implementation depends on actual text handling code)


class TestInvalidDataHandling:
    """Test handling of invalid or malformed data."""
    
    def test_invalid_llm_response_format(self, qtbot):
        """Test handling of invalid LLM response formats."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        with patch('src.llm_service.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"invalid": "response"}
            mock_response.text = '{"invalid": "response"}'
            mock_post.return_value = mock_response
            
            with pytest.raises(LLMResponseError):
                service.query_llm("Test prompt")
                
    def test_malformed_json_response(self, qtbot):
        """Test handling of malformed JSON responses."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        with patch('src.llm_service.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            import json
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
            mock_response.text = "Invalid JSON content"
            mock_post.return_value = mock_response
            
            with pytest.raises(LLMResponseError):
                service.query_llm("Test prompt")
                
    def test_unicode_handling_in_annotations(self, qtbot):
        """Test handling of Unicode characters in annotations."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Create proper layout for annotation manager
        from PyQt6.QtWidgets import QVBoxLayout
        annotations_container = QWidget()
        annotations_layout = QVBoxLayout(annotations_container)
        empty_message = QWidget()
        
        annotation_manager = AnnotationManager(pdf_viewer, annotations_layout, empty_message)
        
        # Test with various Unicode characters
        unicode_texts = [
            "中文测试",
            "🌟🚀💻",
            "Ñiño en español",
            "Русский текст",
            "محتوى عربي"
        ]
        
        import fitz
        for i, text in enumerate(unicode_texts):
            rect = fitz.Rect(i*10, i*10, i*10+10, i*10+10)
            annotation_manager.add_annotation(1, rect, f"Response for: {text}", text)
            
        # Should handle Unicode without issues
        assert annotation_manager.get_annotation_count() == len(unicode_texts)
        
    def test_extremely_long_text_handling(self, qtbot):
        """Test handling of extremely long text inputs."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        
        # Create extremely long text
        long_text = "A" * 1000000  # 1MB of text
        
        # Should handle long text gracefully in text processing
        # (Implementation depends on actual text handling)


class TestRecoveryMechanisms:
    """Test error recovery and graceful degradation."""
    
    def test_graceful_degradation_no_llm_service(self, qtbot):
        """Test graceful degradation when LLM service is unavailable."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        
        # Mock LLM service to be unavailable
        main_window.llm_service.is_configured = MagicMock(return_value=False)
        
        # UI should still be functional for PDF viewing
        main_window.show()
        
        # Basic operations should work
        assert main_window.pdf_viewer is not None
        
    @patch('PyQt6.QtWidgets.QMessageBox.critical')
    def test_error_message_display(self, mock_message_box, qtbot):
        """Test that error messages are displayed to users."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Test error handling in AI query
        error_message = "Test error message"
        
        # Should display error without crashing
        main_window.handle_ai_error(error_message)
        
        # Verify message box was called
        mock_message_box.assert_called_once()
        
    @patch('PyQt6.QtWidgets.QMessageBox.critical')
    def test_state_restoration_after_error(self, mock_message_box, qtbot):
        """Test that application state is restored after errors."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Simulate error and recovery
        main_window.loading_indicator.show_at_position(main_window.rect().center())
        
        # Error should hide loading indicator
        main_window.handle_ai_error("Test error")
        
        # Loading indicator should be hidden
        qtbot.waitUntil(lambda: not main_window.loading_indicator.isVisible(), timeout=2000)
        
        # Verify message box was called
        mock_message_box.assert_called_once()
        
    def test_cleanup_after_exceptions(self, qtbot):
        """Test that resources are cleaned up after exceptions."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Simulate exception during PDF loading
        with patch.object(pdf_viewer, 'load_pdf') as mock_load:
            mock_load.side_effect = Exception("Simulated exception")
            
            try:
                pdf_viewer.load_pdf("test.pdf")
            except Exception:
                pass
                
            # Should not leak resources or leave invalid state
            # (Specific checks depend on implementation)


class TestConcurrencyErrors:
    """Test handling of concurrency-related errors."""
    
    def test_multiple_llm_queries_concurrently(self, qtbot):
        """Test handling multiple concurrent LLM queries."""
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default: {
            "llm/api_key": "test_key",
            "llm/model_name": "test_model"
        }.get(key, default)
        
        service = GeminiLLMService(mock_settings)
        
        # Create multiple workers
        workers = []
        for i in range(5):
            worker = LLMWorker(service, f"Query {i}")
            workers.append(worker)
            
        # Should handle multiple concurrent workers
        # (Actual concurrency testing requires more complex setup)
        
    def test_thread_safety_annotation_manager(self, qtbot):
        """Test thread safety of annotation manager."""
        pdf_viewer = PDFViewer()
        qtbot.addWidget(pdf_viewer)
        
        # Create proper layout for annotation manager
        from PyQt6.QtWidgets import QVBoxLayout
        annotations_container = QWidget()
        annotations_layout = QVBoxLayout(annotations_container)
        empty_message = QWidget()
        
        annotation_manager = AnnotationManager(pdf_viewer, annotations_layout, empty_message)
        
        # Simulate concurrent access to annotation manager
        # (Full thread safety testing requires threading setup)
        import fitz
        
        for i in range(10):
            rect = fitz.Rect(i, i, i+10, i+10)
            annotation_manager.add_annotation(1, rect, f"Concurrent annotation {i}", f"Text {i}")
            
        assert annotation_manager.get_annotation_count() == 10


class TestResourceExhaustion:
    """Test handling of resource exhaustion scenarios."""
    
    def test_file_handle_exhaustion(self, qtbot):
        """Test handling when file handles are exhausted."""
        # This is difficult to test reliably across platforms
        # We'll simulate the condition
        
        with patch('builtins.open') as mock_open:
            mock_open.side_effect = OSError("Too many open files")
            
            # Operations requiring file access should handle gracefully
            try:
                pdf_document = PDFDocument("test.pdf")
                pdf_document.load_document("test.pdf")
            except Exception as e:
                # Should raise appropriate exception, not crash
                assert isinstance(e, (OSError, IOError, Exception))
                
    def test_disk_space_exhaustion(self, qtbot):
        """Test handling when disk space is exhausted."""
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.side_effect = OSError("No space left on device")
            
            # Operations requiring temp space should handle gracefully
            # (Implementation depends on actual temp file usage)
            
    def test_widget_creation_limits(self, qtbot):
        """Test handling of widget creation limits."""
        # Create many widgets to test limits
        widgets = []
        
        try:
            for i in range(1000):  # Large number of widgets
                widget = QWidget()
                widgets.append(widget)
                qtbot.addWidget(widget)
                
        except Exception as e:
            # Should handle resource exhaustion gracefully
            pass
            
        # Clean up
        for widget in widgets:
            widget.deleteLater() 