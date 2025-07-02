"""
Unit tests for ChatInput component.

Tests the chat input widget functionality including text input handling,
keyboard shortcuts, auto-resizing, and state management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QTextEdit, QPushButton
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent

from src.chat_input import ChatInput, ChatInputTextEdit


class TestChatInputTextEdit:
    """Test suite for ChatInputTextEdit component."""
    
    @pytest.fixture
    def text_edit(self, qtbot):
        """Create a ChatInputTextEdit instance for testing."""
        edit = ChatInputTextEdit()
        qtbot.addWidget(edit)
        return edit
    
    def test_text_edit_initialization(self, text_edit):
        """Test ChatInputTextEdit initialization."""
        assert text_edit is not None
        assert text_edit.acceptRichText() == False


class TestChatInput:
    """Test suite for ChatInput component."""
    
    @pytest.fixture
    def chat_input(self, qtbot):
        """Create a ChatInput instance for testing."""
        with patch('src.chat_input.responsive_calc') as mock_responsive_calc:
            # Mock responsive calculator
            mock_responsive_calc.get_chat_colors.return_value = {
                "primary": "#0078d4",
                "secondary": "#106ebe",
                "send_button": {"background": "#0078d4", "text": "#ffffff"}
            }
            mock_responsive_calc.get_chat_spacing_config.return_value = {
                "margin": 12, "padding": 16, "item_spacing": 12
            }
            mock_responsive_calc.get_font_config.return_value = {
                "body": 13, "caption": 10
            }
            mock_responsive_calc.get_chat_input_placeholder.return_value = "Type a message..."
            mock_responsive_calc.create_responsive_style.return_value = "/* test style */"
            mock_responsive_calc.get_chat_input_style_template.return_value = "/* template */"
            
            input_widget = ChatInput()
            qtbot.addWidget(input_widget)
            return input_widget

    def test_chat_input_initialization(self, chat_input):
        """Test ChatInput initialization."""
        assert chat_input is not None
        assert hasattr(chat_input, 'text_input')
        assert hasattr(chat_input, 'send_button')
        assert chat_input.is_sending == False

    def test_send_message_with_text(self, chat_input):
        """Test sending message with valid text."""
        test_message = "Hello AI!"
        
        # Set text in input
        chat_input.text_input.setPlainText(test_message)
        
        # Mock signal
        chat_input.message_sent = Mock()
        
        # Send message
        chat_input._send_message()
        
        # Verify signal was emitted
        chat_input.message_sent.emit.assert_called_once_with(test_message)
        
        # Verify input was cleared
        assert chat_input.text_input.toPlainText() == ""

    def test_clear_input(self, chat_input):
        """Test clearing input text."""
        # Set some text
        chat_input.text_input.setPlainText("Some text to clear")
        
        # Clear input
        chat_input.clear_input()
        
        # Verify text was cleared
        assert chat_input.text_input.toPlainText() == ""

    def test_set_enabled_true(self, chat_input):
        """Test enabling chat input."""
        # Add some text to enable send button
        chat_input.text_input.setPlainText("test message")
        chat_input.set_enabled(True)
        
        assert chat_input.text_input.isEnabled() == True
        assert chat_input.send_button.isEnabled() == True
        assert chat_input.is_sending == False

    def test_set_enabled_false(self, chat_input):
        """Test disabling chat input."""
        chat_input.set_enabled(False)
        
        assert chat_input.text_input.isEnabled() == False
        assert chat_input.send_button.isEnabled() == False
        # is_sending state is not changed by set_enabled
        assert chat_input.is_sending == False
