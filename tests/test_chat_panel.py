"""
Unit tests for ChatPanel component.

Tests the main chat panel widget functionality including UI components,
signal connections, message handling, AI interaction, and RAG mode functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QVBoxLayout, QScrollArea, QLabel, QFrame, QPushButton
from PyQt6.QtCore import Qt, QTimer

from src.chat_panel import ChatPanel
from src.chat_manager import ChatManager
from src.chat_input import ChatInput


class TestChatPanel:
    """Test suite for ChatPanel component."""
    
    @pytest.fixture
    def chat_panel(self, qtbot):
        """Create a ChatPanel instance for testing."""
        with patch('src.chat_panel.responsive_calc') as mock_responsive_calc:
            # Mock responsive calculator
            mock_responsive_calc.get_chat_colors.return_value = {
                "primary": "#0078d4",
                "secondary": "#106ebe",
                "user_message": {"background": "#0078d4", "text": "#ffffff", "border": "#106ebe"},
                "ai_message": {"background": "#f5f5f5", "text": "#333333", "border": "#e0e0e0"}
            }
            mock_responsive_calc.get_chat_spacing_config.return_value = {
                "margin": 12, "padding": 16, "item_spacing": 12
            }
            mock_responsive_calc.get_font_config.return_value = {
                "title": 16, "body": 13, "caption": 10
            }
            mock_responsive_calc.get_chat_panel_title.return_value = "AI Chat"
            mock_responsive_calc.get_chat_empty_state_config.return_value = {
                "icon": "💬", "title": "Start Chatting", "description": "Send a message to begin"
            }
            mock_responsive_calc.create_responsive_style.return_value = "/* test style */"
            mock_responsive_calc.get_chat_panel_style_template.return_value = "/* template */"
            mock_responsive_calc.get_chat_input_placeholder.return_value = "Type a message..."
            
            panel = ChatPanel()
            qtbot.addWidget(panel)
            return panel

    def test_chat_panel_initialization(self, chat_panel):
        """Test ChatPanel initialization."""
        assert chat_panel is not None
        assert chat_panel.is_ai_responding == False
        assert chat_panel.rag_mode == False
        assert chat_panel.pdf_document_name == ""
        assert hasattr(chat_panel, 'colors')
        assert hasattr(chat_panel, 'spacing')
        assert hasattr(chat_panel, 'fonts')
        assert hasattr(chat_panel, 'chat_manager')
        assert hasattr(chat_panel, 'chat_input')

    def test_ui_components_creation(self, chat_panel):
        """Test that all UI components are created correctly."""
        # Header components
        assert chat_panel.title_label is not None
        assert chat_panel.clear_button is not None
        assert chat_panel.title_label.text() == "AI Chat"
        
        # Messages section
        assert chat_panel.scroll_area is not None
        assert chat_panel.messages_widget is not None
        assert chat_panel.messages_layout is not None
        assert chat_panel.empty_message is not None
        
        # Input section
        assert chat_panel.chat_input is not None
        assert isinstance(chat_panel.chat_input, ChatInput)
        
        # Chat manager
        assert chat_panel.chat_manager is not None
        assert isinstance(chat_panel.chat_manager, ChatManager)

    def test_signals_exist(self, chat_panel):
        """Test that all required signals exist."""
        assert hasattr(chat_panel, 'user_message_sent')
        assert hasattr(chat_panel, 'ai_response_requested')
        assert hasattr(chat_panel, 'rag_query_requested')
        assert hasattr(chat_panel, 'chat_cleared')

    def test_rag_mode_toggle_enable(self, chat_panel):
        """Test enabling RAG mode."""
        test_doc_name = "test_document.pdf"
        
        # Enable RAG mode
        chat_panel.set_rag_mode(True, test_doc_name)
        
        # Verify state changes
        assert chat_panel.rag_mode == True
        assert chat_panel.pdf_document_name == test_doc_name
        assert f"文档对话 - {test_doc_name}" in chat_panel.title_label.text()

    def test_rag_mode_toggle_disable(self, chat_panel):
        """Test disabling RAG mode."""
        # First enable it
        chat_panel.set_rag_mode(True, "test.pdf")
        
        # Then disable it
        chat_panel.set_rag_mode(False)
        
        # Verify state changes
        assert chat_panel.rag_mode == False
        assert chat_panel.pdf_document_name == ""
        assert "AI Chat" in chat_panel.title_label.text()

    def test_handle_user_message_rag_mode(self, chat_panel):
        """Test handling user message in RAG mode."""
        test_message = "What is this document about?"
        
        # Enable RAG mode
        chat_panel.set_rag_mode(True, "test.pdf")
        
        # Mock chat manager and signals
        chat_panel.chat_manager.add_user_message = Mock(return_value=Mock())
        chat_panel.user_message_sent = Mock()
        chat_panel.rag_query_requested = Mock()
        
        # Call handler
        chat_panel._handle_user_message(test_message)
        
        # Verify RAG query signal is emitted instead of ai_response_requested
        chat_panel.rag_query_requested.emit.assert_called_once_with(test_message)
        chat_panel.user_message_sent.emit.assert_called_once_with(test_message)

    def test_handle_user_message_normal_mode(self, chat_panel):
        """Test handling user message in normal mode."""
        test_message = "Hello AI!"
        
        # Ensure normal mode
        chat_panel.set_rag_mode(False)
        
        # Mock chat manager and signals
        chat_panel.chat_manager.add_user_message = Mock(return_value=Mock())
        chat_panel.user_message_sent = Mock()
        chat_panel.ai_response_requested = Mock()
        
        # Call handler
        chat_panel._handle_user_message(test_message)
        
        # Verify normal AI response signal is emitted
        chat_panel.ai_response_requested.emit.assert_called_once_with(test_message)
        chat_panel.user_message_sent.emit.assert_called_once_with(test_message)

    def test_handle_user_message_valid(self, chat_panel):
        """Test handling valid user message."""
        test_message = "Hello AI!"
        
        # Mock chat manager
        chat_panel.chat_manager.add_user_message = Mock(return_value=Mock())
        
        # Mock signals
        chat_panel.user_message_sent = Mock()
        chat_panel.ai_response_requested = Mock()
        
        # Call handler
        chat_panel._handle_user_message(test_message)
        
        # Verify state changes
        assert chat_panel.is_ai_responding == True
        
        # Verify chat manager called
        chat_panel.chat_manager.add_user_message.assert_called_once_with(test_message)
        
        # Verify signals emitted
        chat_panel.user_message_sent.emit.assert_called_once_with(test_message)
        chat_panel.ai_response_requested.emit.assert_called_once_with(test_message)

    def test_handle_user_message_empty(self, chat_panel):
        """Test handling empty user message."""
        # Mock dependencies
        chat_panel.chat_manager.add_user_message = Mock()
        chat_panel.user_message_sent = Mock()
        chat_panel.ai_response_requested = Mock()
        
        # Test empty message
        chat_panel._handle_user_message("")
        
        # Verify nothing happens
        chat_panel.chat_manager.add_user_message.assert_not_called()
        chat_panel.user_message_sent.emit.assert_not_called()
        chat_panel.ai_response_requested.emit.assert_not_called()

    def test_handle_user_message_while_ai_responding(self, chat_panel):
        """Test handling user message while AI is responding."""
        # Set AI responding state
        chat_panel.is_ai_responding = True
        
        # Mock dependencies
        chat_panel.chat_manager.add_user_message = Mock()
        chat_panel.user_message_sent = Mock()
        chat_panel.ai_response_requested = Mock()
        
        # Try to send message
        chat_panel._handle_user_message("Test message")
        
        # Verify nothing happens
        chat_panel.chat_manager.add_user_message.assert_not_called()
        chat_panel.user_message_sent.emit.assert_not_called()
        chat_panel.ai_response_requested.emit.assert_not_called()

    def test_add_ai_response(self, chat_panel):
        """Test adding AI response."""
        test_response = "This is an AI response."
        
        # Mock dependencies
        chat_panel.chat_manager.add_ai_message = Mock(return_value=Mock())
        chat_panel.chat_input.set_enabled = Mock()
        
        # Add AI response
        chat_panel.add_ai_response(test_response)
        
        # Verify state changes
        assert chat_panel.is_ai_responding == False
        
        # Verify chat manager called
        chat_panel.chat_manager.add_ai_message.assert_called_once_with(test_response)
        
        # Verify input re-enabled
        chat_panel.chat_input.set_enabled.assert_called_once_with(True)

    def test_handle_ai_error(self, chat_panel):
        """Test handling AI error."""
        test_error = "API Error"
        
        # Mock dependencies
        chat_panel.chat_manager.add_ai_message = Mock(return_value=Mock())
        chat_panel.chat_input.set_enabled = Mock()
        
        # Handle error
        chat_panel.handle_ai_error(test_error)
        
        # Verify state changes
        assert chat_panel.is_ai_responding == False
        
        # Verify error message added
        chat_panel.chat_manager.add_ai_message.assert_called_once()
        error_message = chat_panel.chat_manager.add_ai_message.call_args[0][0]
        assert "Error" in error_message
        assert test_error in error_message
        
        # Verify input re-enabled
        chat_panel.chat_input.set_enabled.assert_called_once_with(True)

    def test_clear_chat(self, chat_panel):
        """Test clearing chat."""
        # Mock dependencies
        chat_panel.chat_manager.clear_all_messages = Mock()
        chat_panel.chat_input.clear_input = Mock()
        chat_panel.chat_input.focus_input = Mock()
        chat_panel.chat_cleared = Mock()
        
        chat_panel.clear_chat()
        
        # Verify all clear operations
        chat_panel.chat_manager.clear_all_messages.assert_called_once()
        chat_panel.chat_input.clear_input.assert_called_once()
        chat_panel.chat_input.focus_input.assert_called_once()
        chat_panel.chat_cleared.emit.assert_called_once()


