"""
Unit tests for ChatPanel component.

Tests the main chat panel widget functionality including UI components,
signal connections, message handling, and AI interaction.
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
        assert hasattr(chat_panel, 'chat_cleared')

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
