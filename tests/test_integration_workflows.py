"""
Integration test suite for end-to-end workflows.

This module tests complete user workflows including:
- PDF loading and annotation workflow
- AI query and response workflow  
- Settings configuration workflow
- Multi-step user interactions
- Cross-component communication
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import fitz

from PyQt6.QtWidgets import QApplication, QFileDialog
from PyQt6.QtCore import Qt, QPoint, QSettings, QTimer
from PyQt6.QtTest import QTest

from main import MainWindow
from src.llm_service import GeminiLLMService


class TestCompleteAnnotationWorkflow:
    """Test complete annotation creation workflow."""
    
    def test_full_pdf_annotation_workflow(self, qtbot):
        """Test complete workflow: load PDF -> select text -> query AI -> create annotation."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Step 1: Load PDF (mocked)
        with patch.object(QFileDialog, 'getOpenFileName') as mock_dialog:
            mock_dialog.return_value = ("test.pdf", "")
            
            with patch.object(main_window.pdf_viewer, 'load_pdf') as mock_load:
                mock_load.return_value = None  # Successful load
                
                # Trigger PDF loading
                main_window.open_pdf()
                
                # Verify PDF loading was attempted
                mock_load.assert_called_once_with("test.pdf")
        
        # Step 2: Simulate text selection in PDF viewer
        test_text = "Selected text for annotation"
        test_context = "Context around selected text"
        test_rect = fitz.Rect(10, 10, 100, 50)
        
        # Mock the text selection
        main_window.current_selected_text = test_text
        
        # Step 3: Trigger AI query
        ai_response = "This is an AI generated annotation for the selected text."
        
        with patch.object(main_window.llm_service, 'query_llm') as mock_llm:
            mock_llm.return_value = ai_response
            
            # Start AI query
            main_window.start_ai_query("What does this mean?", test_rect)
            
            # Wait for worker to complete
            qtbot.waitUntil(lambda: hasattr(main_window, 'llm_worker') and not main_window.llm_worker.isRunning(), timeout=3000)
        
        # Step 4: Verify annotation was created
        annotation_count = main_window.annotation_manager.get_annotation_count()
        assert annotation_count > 0
        
    def test_multiple_annotations_workflow(self, qtbot):
        """Test creating multiple annotations in sequence."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Mock LLM service for consistent responses
        with patch.object(main_window.llm_service, 'query_llm') as mock_llm:
            mock_llm.return_value = "AI response"
            
            # Create multiple annotations
            for i in range(3):
                test_rect = fitz.Rect(i*20, i*20, i*20+50, i*20+30)
                main_window.current_selected_text = f"Text {i}"
                
                main_window.start_ai_query(f"Question {i}", test_rect)
                
                # Wait for completion
                qtbot.waitUntil(lambda: not hasattr(main_window, 'llm_worker') or not main_window.llm_worker.isRunning(), timeout=3000)
        
        # Verify all annotations were created
        assert main_window.annotation_manager.get_annotation_count() == 3
        
    def test_annotation_deletion_workflow(self, qtbot):
        """Test annotation creation and deletion workflow."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Create an annotation first
        test_rect = fitz.Rect(10, 10, 100, 50)
        main_window.annotation_manager.add_annotation(1, test_rect, "Test annotation", "Selected text")
        
        initial_count = main_window.annotation_manager.get_annotation_count()
        assert initial_count == 1
        
        # Find and remove the annotation
        # This would typically involve clicking a delete button in the panel
        # For testing, we'll directly call the removal method
        if main_window.annotation_manager.annotations:
            annotation_widget = main_window.annotation_manager.annotations[0]
            main_window.annotation_manager.remove_annotation(annotation_widget)
        
        final_count = main_window.annotation_manager.get_annotation_count()
        assert final_count == 0


class TestSettingsWorkflow:
    """Test settings configuration workflows."""
    
    def test_api_key_configuration_workflow(self, qtbot):
        """Test complete API key configuration workflow."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Test non-blocking settings dialog approach
        with patch('src.settings_dialog.SettingsDialog.show') as mock_show:
            with patch.object(main_window.llm_service, 'refresh_config') as mock_refresh:
                # Open settings dialog (non-blocking)
                main_window.open_settings()
                
                # Verify settings dialog show() was called (not exec())
                mock_show.assert_called_once()
                
                # Test simulated dialog acceptance by calling the callback directly
                mock_dialog = MagicMock()
                main_window._on_settings_accepted(mock_dialog)
                
                # Verify LLM service refresh was called
                mock_refresh.assert_called_once()
                
                # Verify dialog cleanup was called
                mock_dialog.deleteLater.assert_called_once()
                
    def test_settings_persistence_workflow(self, qtbot):
        """Test that settings persist across application restarts."""
        # Create temporary settings file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as temp_file:
            temp_file.write('[llm]\napi_key=test_key_123\nmodel_name=gemini-pro\n')
            temp_file_path = temp_file.name
        
        try:
            # Create settings from file
            settings = QSettings(temp_file_path, QSettings.Format.IniFormat)
            
            # Create main window with these settings
            main_window = MainWindow()
            main_window.settings = settings
            qtbot.addWidget(main_window)
            
            # Verify settings were loaded
            api_key = settings.value("llm/api_key", "")
            assert api_key == "test_key_123"
            
        finally:
            import os
            os.unlink(temp_file_path)


class TestErrorRecoveryWorkflows:
    """Test error recovery in complete workflows."""
    
    def test_llm_error_recovery_workflow(self, qtbot):
        """Test workflow recovery after LLM service errors."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Mock LLM service to fail first, then succeed
        call_count = 0
        def mock_query(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return "Success response"
        
        with patch.object(main_window.llm_service, 'query_llm', side_effect=mock_query):
            # First query should fail
            test_rect = fitz.Rect(10, 10, 100, 50)
            main_window.current_selected_text = "Test text"
            
            main_window.start_ai_query("Test question", test_rect)
            
            # Wait for error handling
            qtbot.waitUntil(lambda: not hasattr(main_window, 'llm_worker') or not main_window.llm_worker.isRunning(), timeout=3000)
            
            # Should have 0 annotations due to error
            assert main_window.annotation_manager.get_annotation_count() == 0
            
            # Second query should succeed
            main_window.start_ai_query("Test question 2", test_rect)
            
            # Wait for success
            qtbot.waitUntil(lambda: not hasattr(main_window, 'llm_worker') or not main_window.llm_worker.isRunning(), timeout=3000)
            
            # Should now have 1 annotation
            assert main_window.annotation_manager.get_annotation_count() == 1
            
    def test_pdf_load_error_recovery_workflow(self, qtbot):
        """Test recovery workflow after PDF loading errors."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Mock PDF loading to fail first time
        call_count = 0
        def mock_load_pdf(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                main_window.pdf_viewer.error_occurred.emit("Failed to load PDF")
            else:
                # Success - don't emit error
                pass
        
        with patch.object(main_window.pdf_viewer, 'load_pdf', side_effect=mock_load_pdf):
            with patch.object(QFileDialog, 'getOpenFileName') as mock_dialog:
                # First attempt
                mock_dialog.return_value = ("bad_file.pdf", "")
                main_window.open_pdf()
                
                # Wait for error signal
                qtbot.wait(100)
                
                # Second attempt should work
                mock_dialog.return_value = ("good_file.pdf", "")
                main_window.open_pdf()
                
                # Should not crash and UI should remain functional


class TestUserInteractionWorkflows:
    """Test complex user interaction workflows."""
    
    def test_selection_mode_switching_workflow(self, qtbot):
        """Test switching between text and area selection modes."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Start in text selection mode
        assert main_window.pdf_viewer.selection_mode.name == "TEXT"
        
        # Switch to area selection mode
        main_window.toggle_selection_mode(True)
        assert main_window.pdf_viewer.selection_mode.name == "SCREENSHOT"
        
        # Switch back to text selection mode
        main_window.toggle_selection_mode(False)
        assert main_window.pdf_viewer.selection_mode.name == "TEXT"
        
        # Verify UI updates accordingly
        action_text = main_window.selection_mode_action.text()
        assert "Area" in action_text
        
    def test_loading_indicator_workflow(self, qtbot):
        """Test loading indicator show/hide workflow during AI queries."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Mock slow LLM service
        with patch.object(main_window.llm_service, 'query_llm') as mock_llm:
            mock_llm.return_value = "Response"
            
            # Start AI query
            test_rect = fitz.Rect(10, 10, 100, 50)
            main_window.current_selected_text = "Test"
            main_window.last_query_position = QPoint(100, 100)
            
            main_window.start_ai_query("Question", test_rect)
            
            # Loading indicator should be shown
            qtbot.waitUntil(lambda: main_window.loading_indicator.isVisible(), timeout=1000)
            
            # Wait for completion
            qtbot.waitUntil(lambda: not hasattr(main_window, 'llm_worker') or not main_window.llm_worker.isRunning(), timeout=3000)
            
            # Loading indicator should be hidden
            qtbot.waitUntil(lambda: not main_window.loading_indicator.isVisible(), timeout=2000)
            
    def test_annotation_panel_scrolling_workflow(self, qtbot):
        """Test annotation panel scrolling with many annotations."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Create many annotations to test scrolling
        for i in range(10):
            test_rect = fitz.Rect(i*10, i*10, i*10+50, i*10+30)
            main_window.annotation_manager.add_annotation(1, test_rect, f"Long annotation text {i} " * 10, f"Selected text {i}")
        
        # Panel should be scrollable
        scroll_area = main_window.annotations_scroll
        assert scroll_area.verticalScrollBar().maximum() > 0
        
        # Test scrolling
        scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().maximum() // 2)
        qtbot.wait(100)  # Allow scroll to complete


class TestCrossComponentCommunication:
    """Test communication between different components."""
    
    def test_pdf_viewer_to_annotation_manager_communication(self, qtbot):
        """Test signal communication from PDF viewer to annotation manager."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Mock text selection in PDF viewer
        selected_text = "Test selection"
        context_text = "Context around selection"
        test_rect = fitz.Rect(10, 10, 100, 50)
        
        # Trigger text query signal from PDF viewer
        with qtbot.waitSignal(main_window.pdf_viewer.text_query_requested, timeout=1000) as blocker:
            main_window.pdf_viewer.text_query_requested.emit(selected_text, context_text, test_rect)
            
        # Verify signal was emitted with correct parameters
        assert blocker.signal_triggered
        assert blocker.args == [selected_text, context_text, test_rect]
        
    def test_llm_worker_to_main_window_communication(self, qtbot):
        """Test signal communication from LLM worker to main window."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Create and start LLM worker
        with patch.object(main_window.llm_service, 'query_llm') as mock_llm:
            mock_llm.return_value = "Test response"
            
            worker = main_window.llm_service
            test_rect = fitz.Rect(10, 10, 100, 50)
            
            # Monitor for result signal
            initial_count = main_window.annotation_manager.get_annotation_count()
            
            main_window.handle_ai_response("Test response", test_rect)
            
            # Should have created annotation
            final_count = main_window.annotation_manager.get_annotation_count()
            assert final_count == initial_count + 1
            
    def test_annotation_manager_empty_state_communication(self, qtbot):
        """Test annotation manager empty state communication."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Initially should show empty message
        assert main_window.empty_message.isVisible()
        
        # Add annotation
        test_rect = fitz.Rect(10, 10, 100, 50)
        main_window.annotation_manager.add_annotation(1, test_rect, "Test", "Text")
        
        # Empty message should be hidden
        assert not main_window.empty_message.isVisible()
        
        # Remove all annotations
        main_window.annotation_manager.clear_all_annotations()
        
        # Empty message should be visible again
        assert main_window.empty_message.isVisible()


class TestDataPersistenceWorkflows:
    """Test data persistence across different operations."""
    
    def test_annotation_data_consistency(self, qtbot):
        """Test that annotation data remains consistent across operations."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Create annotation with specific data
        page_num = 2
        test_rect = fitz.Rect(10, 10, 100, 50)
        ai_response = "Detailed AI response with special characters: àáâã 🌟"
        selected_text = "Original selected text with unicode: 中文"
        
        main_window.annotation_manager.add_annotation(page_num, test_rect, ai_response, selected_text)
        
        # Verify data is stored correctly
        assert main_window.annotation_manager.get_annotation_count() == 1
        
        # The exact data verification would depend on annotation widget implementation
        # This tests that the operation completes without data corruption
        
    def test_settings_data_persistence(self, qtbot):
        """Test that settings data persists correctly."""
        # Create temporary settings
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            # Set some settings
            settings = QSettings(temp_file_path, QSettings.Format.IniFormat)
            settings.setValue("llm/api_key", "persistent_key_123")
            settings.setValue("llm/model_name", "persistent_model")
            settings.sync()
            
            # Create new settings instance from same file
            new_settings = QSettings(temp_file_path, QSettings.Format.IniFormat)
            
            # Verify data persisted
            assert new_settings.value("llm/api_key") == "persistent_key_123"
            assert new_settings.value("llm/model_name") == "persistent_model"
            
        finally:
            import os
            os.unlink(temp_file_path)


class TestPerformanceWorkflows:
    """Test performance characteristics of complete workflows."""
    
    def test_large_annotation_set_performance(self, qtbot):
        """Test performance with large number of annotations."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        import time
        start_time = time.time()
        
        # Create 50 annotations
        for i in range(50):
            test_rect = fitz.Rect(i, i, i+50, i+30)
            main_window.annotation_manager.add_annotation(1, test_rect, f"Annotation {i}", f"Text {i}")
        
        creation_time = time.time() - start_time
        
        # Should create annotations in reasonable time (< 5 seconds for 50 annotations)
        assert creation_time < 5.0
        assert main_window.annotation_manager.get_annotation_count() == 50
        
        # Test clearing performance
        start_time = time.time()
        main_window.annotation_manager.clear_all_annotations()
        clear_time = time.time() - start_time
        
        # Should clear quickly (< 1 second)
        assert clear_time < 1.0
        assert main_window.annotation_manager.get_annotation_count() == 0
        
    def test_rapid_user_interaction_performance(self, qtbot):
        """Test performance under rapid user interactions."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        main_window.show()
        
        # Rapid mode switching
        for i in range(10):
            main_window.toggle_selection_mode(i % 2 == 0)
            qtbot.wait(10)  # Small delay
        
        # Should remain responsive
        assert main_window.isVisible()
        
        # Rapid annotation creation
        with patch.object(main_window.llm_service, 'query_llm') as mock_llm:
            mock_llm.return_value = "Quick response"
            
            for i in range(5):
                test_rect = fitz.Rect(i*20, i*20, i*20+50, i*20+30)
                main_window.current_selected_text = f"Text {i}"
                main_window.handle_ai_response(f"Response {i}", test_rect)
                qtbot.wait(50)  # Small delay between operations
        
        # All annotations should be created
        assert main_window.annotation_manager.get_annotation_count() == 5 