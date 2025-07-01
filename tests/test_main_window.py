import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
import fitz

# Configure pytest to suppress PyQt6 warnings during testing
logging.getLogger('PyQt6').setLevel(logging.WARNING)

from main import MainWindow


class TestMainWindow:
    """Test suite for the MainWindow class using pytest-qt for headless GUI testing."""

    @pytest.fixture
    def main_window(self, qtbot):
        """Create a MainWindow instance for testing."""
        with patch('config.APP_NAME', 'TestApp'):
            with patch('src.llm_service.GeminiLLMService') as mock_llm:
                mock_llm.return_value.is_configured.return_value = True
                window = MainWindow()
                qtbot.addWidget(window)
                return window

    def test_main_window_initialization(self, main_window):
        """Test that MainWindow initializes correctly."""
        assert main_window.windowTitle() == "AI-Enhanced PDF Scholar"
        # Window size now depends on screen size (responsive)
        assert main_window.width() >= 800  # At least minimum width
        assert main_window.height() >= 600  # At least minimum height
        assert main_window.width() <= 1400  # Not exceeding max reasonable size
        assert main_window.height() <= 900  # Not exceeding max reasonable size
        assert hasattr(main_window, 'pdf_viewer')
        assert hasattr(main_window, 'annotation_manager')
        assert hasattr(main_window, 'annotations_panel')

    def test_ui_components_exist(self, main_window):
        """Test that all UI components are properly created."""
        # Check toolbar exists
        assert main_window.toolbar is not None
        
        # Check PDF viewer exists
        assert main_window.pdf_viewer is not None
        
        # Check annotations panel components exist
        assert hasattr(main_window, 'annotations_panel')
        assert hasattr(main_window, 'annotations_scroll')
        assert hasattr(main_window, 'annotations_container')
        assert hasattr(main_window, 'annotations_layout')
        assert hasattr(main_window, 'empty_message')

    def test_annotations_panel_layout(self, main_window):
        """Test the annotations panel layout and styling."""
        panel = main_window.annotations_panel
        assert panel is not None
        
        # Panel width is now responsive based on window size
        assert panel.minimumWidth() >= 280  # At least minimum from config
        assert panel.maximumWidth() <= 500  # Not exceeding maximum from config
        
        # Ensure panel width is reasonable relative to window width
        window_width = main_window.width()
        panel_width = panel.width()
        panel_ratio = panel_width / window_width
        assert 0.2 <= panel_ratio <= 0.4  # Between 20% and 40% of window width
        
        # Check that style sheet is applied (responsive styling)
        assert panel.styleSheet() != ""  # Some styling should be applied

    def test_selection_mode_toggle(self, main_window, qtbot):
        """Test the selection mode toggle functionality."""
        action = main_window.selection_mode_action
        assert action is not None
        assert action.isCheckable() is True
        
        # Initially should be in text mode
        assert "Area" in action.text()
        
        # Toggle to area mode
        action.trigger()
        assert "Text" in action.text()

    @patch('main.QFileDialog.getOpenFileName')
    def test_open_pdf_dialog(self, mock_dialog, main_window, qtbot):
        """Test the PDF opening dialog."""
        mock_dialog.return_value = ('test.pdf', 'PDF Files (*.pdf)')
        
        with patch.object(main_window.pdf_viewer, 'load_pdf') as mock_load:
            with patch.object(main_window.annotation_manager, 'clear_all_annotations') as mock_clear:
                main_window.open_pdf()
                
                mock_clear.assert_called_once()
                mock_load.assert_called_once_with('test.pdf')

    @patch('main.SettingsDialog')
    def test_open_settings_dialog(self, mock_dialog_class, main_window, qtbot):
        """Test the settings dialog opening."""
        mock_dialog = Mock()
        mock_dialog.exec.return_value = True
        mock_dialog_class.return_value = mock_dialog
        
        with patch.object(main_window.llm_service, 'refresh_config') as mock_refresh:
            main_window.open_settings()
            
            mock_dialog_class.assert_called_once_with(main_window)
            mock_dialog.exec.assert_called_once()
            mock_refresh.assert_called_once()

    def test_handle_text_query(self, main_window):
        """Test handling of text query requests."""
        selected_text = "Test selected text"
        context_text = "Test context"
        pdf_rect = fitz.Rect(0, 0, 100, 100)
        
        with patch('main.InquiryPopup') as mock_popup_class:
            mock_popup = Mock()
            mock_popup_class.return_value = mock_popup
            
            # Set selection end position for popup positioning
            main_window.pdf_viewer.selection_end_pos = Mock()
            main_window.pdf_viewer.selection_end_pos.toPoint.return_value = Mock()
            
            with patch.object(main_window.pdf_viewer, 'mapToGlobal', return_value=Mock()):
                main_window.handle_text_query(selected_text, context_text, pdf_rect)
                
                # Check that selected text is stored
                assert main_window.current_selected_text == selected_text
                
                # Check popup creation
                mock_popup_class.assert_called_once_with(
                    parent=main_window.pdf_viewer,
                    selected_text=selected_text,
                    context_text=context_text
                )

    def test_start_ai_query(self, main_window):
        """Test AI query initiation."""
        prompt = "Test prompt"
        pdf_rect = fitz.Rect(0, 0, 100, 100)
        
        with patch('main.LLMWorker') as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker
            
            with patch.object(main_window.pdf_viewer, 'clear_selection') as mock_clear:
                with patch.object(main_window.loading_indicator, 'show_at_position') as mock_show:
                    main_window.last_query_position = Mock()
                    
                    main_window.start_ai_query(prompt, pdf_rect)
                    
                    # Check that selection is cleared
                    mock_clear.assert_called_once()
                    
                    # Check loading indicator is shown
                    mock_show.assert_called_once_with(main_window.last_query_position)
                    
                    # Check worker is created and started
                    mock_worker_class.assert_called_once_with(main_window.llm_service, prompt)
                    mock_worker.start.assert_called_once()

    def test_handle_ai_response(self, main_window):
        """Test handling of AI response."""
        ai_response = "Test AI response"
        pdf_rect = fitz.Rect(0, 0, 100, 100)
        page_num = 0
        
        # Set up stored selected text
        main_window.current_selected_text = "Test selected text"
        
        with patch.object(main_window.loading_indicator, 'hide_with_fade') as mock_hide:
            with patch.object(main_window.pdf_viewer, 'get_current_page_number', return_value=page_num):
                with patch.object(main_window.annotation_manager, 'add_annotation') as mock_add:
                    main_window.handle_ai_response(ai_response, pdf_rect)
                    
                    # Check loading indicator is hidden
                    mock_hide.assert_called_once()
                    
                    # Check annotation is added with selected text
                    mock_add.assert_called_once_with(
                        page_num, 
                        pdf_rect, 
                        ai_response, 
                        "Test selected text"
                    )
                    
                    # Check selected text is cleared
                    assert main_window.current_selected_text == ""

    def test_handle_ai_error(self, main_window, qtbot):
        """Test handling of AI errors."""
        error_msg = "LLMConfigurationError: Test error"
        
        with patch.object(main_window.loading_indicator, 'hide_with_fade') as mock_hide:
            with patch('main.QMessageBox.critical') as mock_msgbox:
                main_window.handle_ai_error(error_msg)
                
                mock_hide.assert_called_once()
                mock_msgbox.assert_called_once()
                
                # Check that configuration error is detected
                call_args = mock_msgbox.call_args[0]
                assert "LLM Not Configured" in call_args[1]

    def test_signal_connections(self, main_window):
        """Test that all signals are properly connected."""
        # This is a basic check that the connection methods exist
        assert hasattr(main_window.pdf_viewer, 'view_changed')
        assert hasattr(main_window.pdf_viewer, 'text_query_requested')
        assert hasattr(main_window.pdf_viewer, 'image_query_requested')
        assert hasattr(main_window.pdf_viewer, 'open_pdf_requested')
        assert hasattr(main_window.pdf_viewer, 'error_occurred')

    def test_empty_annotations_state(self, main_window):
        """Test the empty annotations state."""
        # Check that empty message exists and has responsive content
        assert main_window.empty_message is not None
        assert "🚀" in main_window.empty_message.text()  # Should contain the emoji
        assert "AI" in main_window.empty_message.text()  # Should contain AI reference
        
        # Test that the message has responsive styling applied
        assert main_window.empty_message.styleSheet() != ""  # Should have some styling
        
        # Check word wrap is enabled for responsive text
        assert main_window.empty_message.wordWrap() is True
        
        # Verify the message is part of the annotations layout
        assert main_window.empty_message.parent() == main_window.annotations_container


class TestMainWindowIntegration:
    """Integration tests for MainWindow with real components."""

    @pytest.fixture
    def app(self):
        """Create QApplication instance for integration tests."""
        return QApplication.instance() or QApplication([])

    def test_window_displays(self, app, qtbot):
        """Test that the window can be displayed without errors."""
        with patch('config.APP_NAME', 'TestApp'):
            with patch('src.llm_service.GeminiLLMService') as mock_llm:
                mock_llm.return_value.is_configured.return_value = True
                window = MainWindow()
                qtbot.addWidget(window)
                
                # Show the window
                window.show()
                qtbot.waitForWindowShown(window)
                
                # Basic checks
                assert window.isVisible()
                assert window.pdf_viewer.isVisible()
                assert window.annotations_panel.isVisible() 