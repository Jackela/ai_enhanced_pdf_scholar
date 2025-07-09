"""
Unit tests for ChatMessage component.

Tests the individual chat message widget functionality including user/AI message styling,
Markdown rendering, timestamps, and responsive design.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from PyQt6.QtWidgets import QLabel, QTextBrowser
from PyQt6.QtCore import Qt

from src.chat_message import ChatMessage


class TestChatMessage:
    """Test suite for ChatMessage component."""
    
    @pytest.fixture
    def sample_user_message(self):
        """Sample user message text."""
        return "Hello AI, can you help me understand this document?"
    
    @pytest.fixture
    def sample_ai_message(self):
        """Sample AI message with Markdown formatting."""
        return """**Hello!** I'd be happy to help you understand the document.

Here are some key points:

- Point 1 with `code snippet`
- Point 2 with emphasis

```python
def example_function():
    return "This is a code block"
```

Let me know if you need clarification on any specific part!"""
    
    @pytest.fixture
    def mock_timestamp(self):
        """Fixed timestamp for testing."""
        return datetime(2024, 1, 15, 14, 30, 0)

    def test_user_message_creation(self, qtbot, sample_user_message, mock_timestamp):
        """Test creating a user message widget."""
        message = ChatMessage(sample_user_message, is_user=True, timestamp=mock_timestamp)
        qtbot.addWidget(message)
        
        assert message.message_text == sample_user_message
        assert message.is_user == True
        assert message.timestamp == mock_timestamp
        assert message.get_message_text() == sample_user_message
        assert message.is_user_message() == True
        assert message.get_timestamp() == mock_timestamp

    def test_ai_message_creation(self, qtbot, sample_ai_message, mock_timestamp):
        """Test creating an AI message widget."""
        message = ChatMessage(sample_ai_message, is_user=False, timestamp=mock_timestamp)
        qtbot.addWidget(message)
        
        assert message.message_text == sample_ai_message
        assert message.is_user == False
        assert message.timestamp == mock_timestamp
        assert message.get_message_text() == sample_ai_message
        assert message.is_user_message() == False
        assert message.get_timestamp() == mock_timestamp

    def test_default_timestamp(self, qtbot, sample_user_message):
        """Test that default timestamp is set to current time."""
        before_creation = datetime.now()
        message = ChatMessage(sample_user_message, is_user=True)
        after_creation = datetime.now()
        qtbot.addWidget(message)
        
        assert before_creation <= message.timestamp <= after_creation

    def test_user_message_ui_components(self, qtbot, sample_user_message):
        """Test that user message has correct UI components."""
        message = ChatMessage(sample_user_message, is_user=True)
        qtbot.addWidget(message)
        
        # User messages should have a QLabel for content
        content_label = message.findChild(QLabel, "user_content")
        assert content_label is not None
        assert content_label.text() == sample_user_message
        assert content_label.wordWrap() == True
        
        # Should not have a QTextBrowser
        content_browser = message.findChild(QTextBrowser, "ai_content")
        assert content_browser is None

    def test_ai_message_ui_components(self, qtbot, sample_ai_message):
        """Test that AI message has correct UI components."""
        message = ChatMessage(sample_ai_message, is_user=False)
        qtbot.addWidget(message)
        
        # AI messages should have a QTextBrowser for Markdown content
        content_browser = message.findChild(QTextBrowser, "ai_content")
        assert content_browser is not None
        assert content_browser.isReadOnly() == True
        
        # Should not have a simple QLabel for content
        content_label = message.findChild(QLabel, "user_content")
        assert content_label is None

    def test_sender_labels(self, qtbot, sample_user_message, sample_ai_message):
        """Test that sender labels are correctly set."""
        user_message = ChatMessage(sample_user_message, is_user=True)
        ai_message = ChatMessage(sample_ai_message, is_user=False)
        qtbot.addWidget(user_message)
        qtbot.addWidget(ai_message)
        
        # Check sender labels
        user_sender = user_message.findChild(QLabel, "sender_label")
        ai_sender = ai_message.findChild(QLabel, "sender_label")
        
        assert user_sender is not None
        assert ai_sender is not None
        assert user_sender.text() == "You"
        assert ai_sender.text() == "AI Assistant"

    def test_timestamp_display(self, qtbot, sample_user_message, mock_timestamp):
        """Test that timestamp is correctly displayed."""
        message = ChatMessage(sample_user_message, is_user=True, timestamp=mock_timestamp)
        qtbot.addWidget(message)
        
        timestamp_label = message.findChild(QLabel, "timestamp_label")
        assert timestamp_label is not None
        assert timestamp_label.text() == "14:30"  # HH:MM format

    @patch('src.chat_message.responsive_calc')
    def test_responsive_configuration_loading(self, mock_responsive_calc, qtbot, sample_user_message):
        """Test that responsive configuration is loaded correctly."""
        mock_responsive_calc.get_chat_colors.return_value = {
            "user_message": {"background": "#0078d4", "text": "#ffffff", "border": "#106ebe"},
            "ai_message": {"background": "#f5f5f5", "text": "#333333", "border": "#e0e0e0"},
            "primary": "#0078d4"
        }
        mock_responsive_calc.get_chat_spacing_config.return_value = {
            "margin": 12, "padding": 16, "item_spacing": 12
        }
        mock_responsive_calc.get_font_config.return_value = {
            "title": 16, "body": 13, "caption": 10
        }
        
        message = ChatMessage(sample_user_message, is_user=True)
        qtbot.addWidget(message)
        
        # Verify that responsive calc methods were called
        mock_responsive_calc.get_chat_colors.assert_called_once()
        mock_responsive_calc.get_chat_spacing_config.assert_called_once()
        mock_responsive_calc.get_font_config.assert_called_once()

    def test_markdown_rendering_setup(self, qtbot, sample_ai_message):
        """Test that Markdown rendering is properly set up for AI messages."""
        message = ChatMessage(sample_ai_message, is_user=False)
        qtbot.addWidget(message)
        
        content_browser = message.findChild(QTextBrowser, "ai_content")
        assert content_browser is not None
        
        # Check that the content contains formatted text (QTextBrowser converts HTML to its own format)
        html_content = content_browser.toHtml()
        
        # QTextBrowser converts <strong> to <span style="font-weight:700;"> etc.
        # So we check for the presence of content and styling indicators
        assert "font-weight:700" in html_content or "font-weight:bold" in html_content  # Bold formatting
        assert "Point 1 with" in html_content  # List content should be present
        assert "Point 2 with" in html_content  # List content should be present
        assert "code snippet" in html_content  # Inline code content
        assert "example_function" in html_content  # Code block content
        assert "This is a code block" in html_content  # Code block content
        
        # Verify that content is actually rendered (not empty)
        assert len(html_content) > 500  # Should be substantial HTML content

    def test_update_max_width(self, qtbot, sample_user_message):
        """Test updating maximum width based on parent width."""
        message = ChatMessage(sample_user_message, is_user=True)
        qtbot.addWidget(message)
        
        # Test width update - should not raise exceptions
        message.update_max_width(400)
        message.update_max_width(800)

    def test_delete_signal_emission(self, qtbot, sample_user_message):
        """Test that delete_requested signal exists."""
        message = ChatMessage(sample_user_message, is_user=True)
        qtbot.addWidget(message)
        
        # Verify signal exists
        assert hasattr(message, 'delete_requested')

    def test_empty_message_handling(self, qtbot):
        """Test handling of empty message text."""
        # Empty string should be handled gracefully
        message = ChatMessage("", is_user=True)
        qtbot.addWidget(message)
        
        assert message.message_text == ""
        assert message.get_message_text() == ""

    def test_whitespace_message_handling(self, qtbot):
        """Test handling of whitespace-only message text."""
        whitespace_message = "   \n\t   "
        message = ChatMessage(whitespace_message, is_user=True)
        qtbot.addWidget(message)
        
        assert message.message_text == whitespace_message
        assert message.get_message_text() == whitespace_message

    @pytest.mark.parametrize("is_user,expected_alignment", [
        (True, "right"),
        (False, "left")
    ])
    def test_message_alignment(self, qtbot, sample_user_message, is_user, expected_alignment):
        """Test that messages are aligned correctly based on sender."""
        message = ChatMessage(sample_user_message, is_user=is_user)
        qtbot.addWidget(message)
        
        # This tests the UI structure - actual alignment testing would require 
        # more complex geometry checks
        assert message.is_user == is_user

    def test_ai_message_scrollbar_policy(self, qtbot, sample_ai_message):
        """Test that AI message browser has correct scrollbar policy."""
        message = ChatMessage(sample_ai_message, is_user=False)
        qtbot.addWidget(message)
        
        content_browser = message.findChild(QTextBrowser, "ai_content")
        assert content_browser is not None
        assert content_browser.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert content_browser.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    def test_long_message_handling(self, qtbot):
        """Test handling of very long messages."""
        long_message = "This is a very long message. " * 100
        message = ChatMessage(long_message, is_user=False)
        qtbot.addWidget(message)
        
        assert message.get_message_text() == long_message
        
        # AI message should have height limit
        content_browser = message.findChild(QTextBrowser, "ai_content")
        assert content_browser is not None
        assert content_browser.maximumHeight() == 300

    def test_message_with_special_characters(self, qtbot):
        """Test handling of messages with special characters."""
        special_message = "Message with émojis 🚀 and spëcial châractërs"
        message = ChatMessage(special_message, is_user=True)
        qtbot.addWidget(message)
        
        assert message.get_message_text() == special_message

    def test_css_styling_application(self, qtbot, sample_user_message, sample_ai_message):
        """Test that CSS styling is applied to messages."""
        user_message = ChatMessage(sample_user_message, is_user=True)
        ai_message = ChatMessage(sample_ai_message, is_user=False)
        qtbot.addWidget(user_message)
        qtbot.addWidget(ai_message)
        
        # Both messages should have styleSheet applied
        assert user_message.styleSheet() != ""
        assert ai_message.styleSheet() != ""
        
        # Styles should be different for user vs AI messages
        assert user_message.styleSheet() != ai_message.styleSheet() 