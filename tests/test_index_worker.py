"""
Tests for Index Worker
Following TDD principles - tests written before implementation
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest

# Import the classes we need to test (will be implemented later)
from src.index_worker import IndexWorker


class TestIndexWorkerInitialization:
    """Test IndexWorker initialization"""
    
    def test_index_worker_requires_pdf_path(self):
        """IndexWorker should require a valid PDF path"""
        with pytest.raises(ValueError, match="PDF path is required"):
            IndexWorker("", Mock())
            
        with pytest.raises(ValueError, match="PDF path is required"):
            IndexWorker(None, Mock())
    
    def test_index_worker_requires_rag_service(self):
        """IndexWorker should require a valid RAG service"""
        with pytest.raises(ValueError, match="RAG service is required"):
            IndexWorker("test.pdf", None)
    
    def test_index_worker_initialization_success(self):
        """IndexWorker should initialize successfully with valid parameters"""
        mock_rag_service = Mock()
        worker = IndexWorker("test.pdf", mock_rag_service)
        
        assert worker is not None
        assert worker.pdf_path == "test.pdf"
        assert worker.rag_service == mock_rag_service


class TestIndexWorkerSignals:
    """Test IndexWorker signals"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_rag_service = Mock()
        self.worker = IndexWorker("test.pdf", self.mock_rag_service)
    
    def test_signals_exist(self):
        """IndexWorker should have all required signals"""
        # Check if signals exist (they should be defined in the class)
        assert hasattr(self.worker, 'indexing_completed')
        assert hasattr(self.worker, 'indexing_failed')
        assert hasattr(self.worker, 'progress_update')
    
    def test_signals_are_callable(self):
        """Signals should be callable (can emit)"""
        # These should not raise exceptions
        self.worker.indexing_completed.emit("test_path")  # Signal expects path argument
        self.worker.indexing_failed.emit("test error")
        self.worker.progress_update.emit("test progress")


class TestIndexWorkerExecution:
    """Test IndexWorker execution logic"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_pdf_path = os.path.join(self.temp_dir, "test.pdf")
        
        # Create a mock PDF file
        with open(self.test_pdf_path, 'wb') as f:
            f.write(b"Mock PDF content")
        
        self.mock_rag_service = Mock()
        self.worker = IndexWorker(self.test_pdf_path, self.mock_rag_service)
    
    def teardown_method(self):
        """Cleanup after each test method"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('PyQt6.QtCore.QThread.run')
    def test_run_successful_indexing(self, mock_thread_run):
        """Should emit success signal when indexing succeeds"""
        # Mock successful indexing
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # Create signal spies
        completed_spy = QSignalSpy(self.worker.indexing_completed)
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        progress_spy = QSignalSpy(self.worker.progress_update)
        
        # Run the worker
        self.worker.run()
        
        # Verify the RAG service was called
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with(self.test_pdf_path)
        
        # Verify success signal was emitted (using len() as signal was emitted)
        assert len(completed_spy) == 1
        assert len(failed_spy) == 0  # No failure signal
        
        # Should have progress updates
        assert len(progress_spy) > 0
    
    @patch('PyQt6.QtCore.QThread.run')
    def test_run_failed_indexing(self, mock_thread_run):
        """Should emit failure signal when indexing fails"""
        # Mock failed indexing
        error_msg = "Indexing failed"
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception(error_msg)
        
        # Create signal spies
        completed_spy = QSignalSpy(self.worker.indexing_completed)
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        
        # Run the worker
        self.worker.run()
        
        # Verify the RAG service was called
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with(self.test_pdf_path)
        
        # Verify failure signal was emitted
        assert len(completed_spy) == 0  # No success signal
        assert len(failed_spy) == 1
        
        # Check that the error message was passed
        emitted_args = failed_spy[0]  # Get first emission arguments
        assert error_msg in str(emitted_args[0])  # Error message should be in the signal
    
    def test_progress_updates_during_indexing(self):
        """Should emit progress updates during indexing process"""
        # Mock successful indexing
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # Create signal spy for progress
        progress_spy = QSignalSpy(self.worker.progress_update)
        
        # Run the worker
        self.worker.run()
        
        # Should have multiple progress updates
        assert len(progress_spy) >= 2  # At least start and end
        
        # Check typical progress messages exist
        progress_messages = [call[0] for call in progress_spy]
        
        # Should have starting message
        start_messages = [msg for msg in progress_messages if "开始" in str(msg) or "Starting" in str(msg)]
        assert len(start_messages) > 0
        
        # Should have completion or processing message
        process_messages = [msg for msg in progress_messages if 
                          "完成" in str(msg) or "处理" in str(msg) or 
                          "Complete" in str(msg) or "Processing" in str(msg)]
        assert len(process_messages) > 0


class TestIndexWorkerThreading:
    """Test IndexWorker threading behavior"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_rag_service = Mock()
        self.worker = IndexWorker("test.pdf", self.mock_rag_service)
    
    def test_is_qthread_subclass(self):
        """IndexWorker should be a QThread subclass"""
        from PyQt6.QtCore import QThread
        assert isinstance(self.worker, QThread)
    
    def test_can_start_and_wait(self):
        """IndexWorker should be startable and waitable like a QThread"""
        # Mock successful indexing to avoid actual work
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # This should not raise exceptions
        self.worker.start()
        
        # Wait for completion (with timeout)
        finished = self.worker.wait(5000)  # 5 second timeout
        assert finished is True  # Should complete within timeout
    
    def test_thread_cleanup(self):
        """IndexWorker should clean up properly after completion"""
        # Mock successful indexing
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # Run and wait for completion
        self.worker.start()
        self.worker.wait(5000)
        
        # Thread should be finished
        assert self.worker.isFinished()
        assert not self.worker.isRunning()


class TestIndexWorkerErrorHandling:
    """Test comprehensive error handling in IndexWorker"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_rag_service = Mock()
        self.worker = IndexWorker("test.pdf", self.mock_rag_service)
    
    def test_handles_file_not_found_error(self):
        """Should handle file not found errors gracefully"""
        from src.rag_service import RAGIndexError
        
        self.mock_rag_service.build_index_from_pdf.side_effect = RAGIndexError("PDF file not found")
        
        # Create signal spy
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        
        # Run the worker
        self.worker.run()
        
        # Should emit failure signal
        assert len(failed_spy) == 1
        error_msg = str(failed_spy[0][0])
        assert "PDF file not found" in error_msg
    
    def test_handles_generic_exceptions(self):
        """Should handle any unexpected exceptions gracefully"""
        self.mock_rag_service.build_index_from_pdf.side_effect = RuntimeError("Unexpected error")
        
        # Create signal spy
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        
        # Run the worker
        self.worker.run()
        
        # Should emit failure signal
        assert len(failed_spy) == 1
        error_msg = str(failed_spy[0][0])
        assert "Unexpected error" in error_msg
    
    def test_continues_execution_after_error(self):
        """Worker should handle errors without crashing the thread"""
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception("Test error")
        
        # This should not raise exceptions or crash
        self.worker.run()
        
        # Worker should still be in a valid state
        assert self.worker is not None


class TestIndexWorkerIntegration:
    """Integration tests for IndexWorker with real-like scenarios"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_pdf_path = os.path.join(self.temp_dir, "test.pdf")
        
        # Create a mock PDF file
        with open(self.test_pdf_path, 'wb') as f:
            f.write(b"Mock PDF content")
        
        self.mock_rag_service = Mock()
        self.worker = IndexWorker(self.test_pdf_path, self.mock_rag_service)
    
    def teardown_method(self):
        """Cleanup after each test method"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow_success(self):
        """Test complete successful workflow"""
        # Mock successful indexing
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # Create signal spies
        completed_spy = QSignalSpy(self.worker.indexing_completed)
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        progress_spy = QSignalSpy(self.worker.progress_update)
        
        # Start the worker
        self.worker.start()
        
        # Wait for completion
        finished = self.worker.wait(5000)
        assert finished is True
        
        # Verify signals
        assert len(completed_spy) == 1
        assert len(failed_spy) == 0
        assert len(progress_spy) > 0
        
        # Verify RAG service was called correctly
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with(self.test_pdf_path)
    
    def test_full_workflow_failure(self):
        """Test complete failure workflow"""
        # Mock failed indexing
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception("Test failure")
        
        # Create signal spies
        completed_spy = QSignalSpy(self.worker.indexing_completed)
        failed_spy = QSignalSpy(self.worker.indexing_failed)
        
        # Start the worker
        self.worker.start()
        
        # Wait for completion
        finished = self.worker.wait(5000)
        assert finished is True
        
        # Verify signals
        assert len(completed_spy) == 0
        assert len(failed_spy) == 1
        
        # Verify RAG service was called
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with(self.test_pdf_path)


if __name__ == "__main__":
    pytest.main([__file__]) 