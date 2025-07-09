"""
Unit tests for ChatManager component.

Tests the chat message lifecycle management including adding, removing,
and organizing chat messages in the chat panel.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import QObject

from src.chat_manager import ChatManager
from src.chat_message import ChatMessage


class TestChatManager:
    """Test suite for ChatManager component."""
    
    @pytest.fixture
    def mock_messages_layout(self):
        """Create a mock QVBoxLayout for messages."""
        layout = Mock(spec=QVBoxLayout)
        layout.addWidget = Mock()
        layout.removeWidget = Mock()
        return layout
    
    @pytest.fixture
    def mock_empty_message_widget(self):
        """Create a mock empty message widget."""
        widget = Mock(spec=QWidget)
        widget.hide = Mock()
        widget.show = Mock()
        return widget
    
    @pytest.fixture
    def chat_manager(self, mock_messages_layout, mock_empty_message_widget):
        """Create a ChatManager instance for testing."""
        return ChatManager(mock_messages_layout, mock_empty_message_widget)
    
    @pytest.fixture
    def sample_user_text(self):
        """Sample user message text."""
        return "Hello AI, how are you today?"
    
    @pytest.fixture
    def sample_ai_text(self):
        """Sample AI response text."""
        return "I'm doing well, thank you for asking! How can I help you?"

    def test_chat_manager_initialization(self, mock_messages_layout, mock_empty_message_widget):
        """Test ChatManager initialization."""
        manager = ChatManager(mock_messages_layout, mock_empty_message_widget)
        
        assert manager.messages_layout == mock_messages_layout
        assert manager.empty_message_widget == mock_empty_message_widget
        assert manager.messages == []
        assert manager.get_message_count() == 0

    @patch('src.chat_manager.ChatMessage')
    def test_add_user_message(self, mock_chat_message_class, chat_manager, sample_user_text):
        """Test adding a user message."""
        mock_message = Mock()
        mock_chat_message_class.return_value = mock_message
        
        result = chat_manager.add_user_message(sample_user_text)
        
        # Verify ChatMessage was created with correct parameters
        mock_chat_message_class.assert_called_once()
        call_args = mock_chat_message_class.call_args
        assert call_args[1]['message_text'] == sample_user_text
        assert call_args[1]['is_user'] == True
        assert 'timestamp' in call_args[1]
        
        # Verify message was added to layout and list
        chat_manager.messages_layout.addWidget.assert_called_once_with(mock_message)
        assert mock_message in chat_manager.messages
        assert chat_manager.get_message_count() == 1
        
        # Verify empty message was hidden
        chat_manager.empty_message_widget.hide.assert_called_once()
        
        assert result == mock_message

    @patch('src.chat_manager.ChatMessage')
    def test_add_ai_message(self, mock_chat_message_class, chat_manager, sample_ai_text):
        """Test adding an AI message."""
        mock_message = Mock()
        mock_chat_message_class.return_value = mock_message
        
        result = chat_manager.add_ai_message(sample_ai_text)
        
        # Verify ChatMessage was created with correct parameters
        mock_chat_message_class.assert_called_once()
        call_args = mock_chat_message_class.call_args
        assert call_args[1]['message_text'] == sample_ai_text
        assert call_args[1]['is_user'] == False
        assert 'timestamp' in call_args[1]
        
        # Verify message was added to layout and list
        chat_manager.messages_layout.addWidget.assert_called_once_with(mock_message)
        assert mock_message in chat_manager.messages
        assert chat_manager.get_message_count() == 1
        
        assert result == mock_message

    @patch('src.chat_manager.ChatMessage')
    def test_add_message_with_custom_timestamp(self, mock_chat_message_class, chat_manager, sample_user_text):
        """Test adding a message with custom timestamp."""
        custom_timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_message = Mock()
        mock_chat_message_class.return_value = mock_message
        
        chat_manager.add_user_message(sample_user_text, timestamp=custom_timestamp)
        
        call_args = mock_chat_message_class.call_args
        assert call_args[1]['timestamp'] == custom_timestamp

    @patch('src.chat_manager.ChatMessage')
    def test_add_empty_message_returns_none(self, mock_chat_message_class, chat_manager):
        """Test that adding empty message returns None."""
        result = chat_manager.add_user_message("")
        assert result is None
        mock_chat_message_class.assert_not_called()
        
        result = chat_manager.add_user_message("   \n\t   ")
        assert result is None
        mock_chat_message_class.assert_not_called()

    @patch('src.chat_manager.ChatMessage')
    def test_message_signals_connected(self, mock_chat_message_class, chat_manager, sample_user_text):
        """Test that message signals are properly connected."""
        mock_message = Mock()
        mock_message.delete_requested = Mock()
        mock_message.delete_requested.connect = Mock()
        mock_chat_message_class.return_value = mock_message
        
        chat_manager.add_user_message(sample_user_text)
        
        # Verify delete signal was connected
        mock_message.delete_requested.connect.assert_called_once_with(chat_manager.remove_message)

    @patch('src.chat_manager.ChatMessage')
    def test_remove_message(self, mock_chat_message_class, chat_manager, sample_user_text):
        """Test removing a message."""
        mock_message = Mock()
        mock_message.delete_requested = Mock()
        mock_message.delete_requested.connect = Mock()
        mock_message.deleteLater = Mock()
        mock_chat_message_class.return_value = mock_message
        
        # Add a message first
        chat_manager.add_user_message(sample_user_text)
        assert chat_manager.get_message_count() == 1
        
        # Remove the message
        chat_manager.remove_message(mock_message)
        
        # Verify message was removed from layout and list
        chat_manager.messages_layout.removeWidget.assert_called_once_with(mock_message)
        mock_message.deleteLater.assert_called_once()
        assert mock_message not in chat_manager.messages
        assert chat_manager.get_message_count() == 0
        
        # Verify empty message is shown when no messages left
        chat_manager.empty_message_widget.show.assert_called_once()

    @patch('src.chat_manager.ChatMessage')
    def test_clear_all_messages(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test clearing all messages."""
        # Add multiple messages
        mock_user_message = Mock()
        mock_ai_message = Mock()
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
            mock_msg.deleteLater = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        chat_manager.add_user_message(sample_user_text)
        chat_manager.add_ai_message(sample_ai_text)
        assert chat_manager.get_message_count() == 2
        
        # Clear all messages
        chat_manager.clear_all_messages()
        
        # Verify all messages were removed
        assert chat_manager.get_message_count() == 0
        assert chat_manager.messages == []
        mock_user_message.deleteLater.assert_called_once()
        mock_ai_message.deleteLater.assert_called_once()
        
        # Verify empty message is shown
        chat_manager.empty_message_widget.show.assert_called()

    @patch('src.chat_manager.ChatMessage')
    def test_get_message_counts(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test getting various message counts."""
        # Mock message objects
        mock_user_message = Mock()
        mock_user_message.is_user_message.return_value = True
        mock_ai_message = Mock()  
        mock_ai_message.is_user_message.return_value = False
        
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        # Add messages
        chat_manager.add_user_message(sample_user_text)
        chat_manager.add_ai_message(sample_ai_text)
        
        # Test counts
        assert chat_manager.get_message_count() == 2
        assert chat_manager.get_user_message_count() == 1
        assert chat_manager.get_ai_message_count() == 1

    @patch('src.chat_manager.ChatMessage')
    def test_get_last_message(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test getting the last message."""
        # Initially no messages
        assert chat_manager.get_last_message() is None
        
        # Add messages
        mock_user_message = Mock()
        mock_ai_message = Mock()
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        chat_manager.add_user_message(sample_user_text)
        assert chat_manager.get_last_message() == mock_user_message
        
        chat_manager.add_ai_message(sample_ai_text)
        assert chat_manager.get_last_message() == mock_ai_message

    @patch('src.chat_manager.ChatMessage')
    def test_get_conversation_history(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test getting conversation history."""
        timestamp1 = datetime(2024, 1, 15, 10, 0, 0)
        timestamp2 = datetime(2024, 1, 15, 10, 1, 0)
        
        # Mock message objects
        mock_user_message = Mock()
        mock_user_message.get_message_text.return_value = sample_user_text
        mock_user_message.is_user_message.return_value = True
        mock_user_message.get_timestamp.return_value = timestamp1
        
        mock_ai_message = Mock()
        mock_ai_message.get_message_text.return_value = sample_ai_text
        mock_ai_message.is_user_message.return_value = False
        mock_ai_message.get_timestamp.return_value = timestamp2
        
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        # Add messages
        chat_manager.add_user_message(sample_user_text, timestamp=timestamp1)
        chat_manager.add_ai_message(sample_ai_text, timestamp=timestamp2)
        
        # Get history
        history = chat_manager.get_conversation_history()
        
        assert len(history) == 2
        assert history[0] == {
            'text': sample_user_text,
            'is_user': True,
            'timestamp': timestamp1
        }
        assert history[1] == {
            'text': sample_ai_text,
            'is_user': False,
            'timestamp': timestamp2
        }

    @patch('src.chat_manager.ChatMessage')
    def test_export_conversation(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test exporting conversation as text."""
        timestamp1 = datetime(2024, 1, 15, 10, 0, 0)
        timestamp2 = datetime(2024, 1, 15, 10, 1, 0)
        
        # Test empty conversation
        exported = chat_manager.export_conversation()
        assert exported == "No messages in conversation."
        
        # Mock message objects
        mock_user_message = Mock()
        mock_user_message.is_user_message.return_value = True
        mock_user_message.get_message_text.return_value = sample_user_text
        mock_user_message.get_timestamp.return_value = timestamp1
        
        mock_ai_message = Mock()
        mock_ai_message.is_user_message.return_value = False
        mock_ai_message.get_message_text.return_value = sample_ai_text
        mock_ai_message.get_timestamp.return_value = timestamp2
        
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        # Add messages
        chat_manager.add_user_message(sample_user_text, timestamp=timestamp1)
        chat_manager.add_ai_message(sample_ai_text, timestamp=timestamp2)
        
        # Export conversation
        exported = chat_manager.export_conversation()
        
        assert "=== Chat Conversation Export ===" in exported
        assert "[2024-01-15 10:00:00] You:" in exported
        assert sample_user_text in exported
        assert "[2024-01-15 10:01:00] AI Assistant:" in exported
        assert sample_ai_text in exported

    @patch('src.chat_manager.ChatMessage')
    def test_update_message_widths(self, mock_chat_message_class, chat_manager, sample_user_text):
        """Test updating message widths."""
        mock_message = Mock()
        mock_message.delete_requested = Mock()
        mock_message.delete_requested.connect = Mock()
        mock_message.update_max_width = Mock()
        mock_chat_message_class.return_value = mock_message
        
        # Add a message
        chat_manager.add_user_message(sample_user_text)
        
        # Update widths
        chat_manager.update_message_widths(400)
        
        # Verify update_max_width was called
        mock_message.update_max_width.assert_called_once_with(400)

    @patch('src.chat_manager.ChatMessage')
    def test_find_message_by_text(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test finding a message by text content."""
        # Mock message objects
        mock_user_message = Mock()
        mock_user_message.get_message_text.return_value = sample_user_text
        mock_ai_message = Mock()
        mock_ai_message.get_message_text.return_value = sample_ai_text
        
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        # Add messages
        chat_manager.add_user_message(sample_user_text)
        chat_manager.add_ai_message(sample_ai_text)
        
        # Find messages
        found_user = chat_manager.find_message_by_text(sample_user_text)
        found_ai = chat_manager.find_message_by_text(sample_ai_text)
        not_found = chat_manager.find_message_by_text("Nonexistent message")
        
        assert found_user == mock_user_message
        assert found_ai == mock_ai_message
        assert not_found is None

    @patch('src.chat_manager.ChatMessage')
    def test_get_messages_since(self, mock_chat_message_class, chat_manager, sample_user_text, sample_ai_text):
        """Test getting messages since a specific timestamp."""
        timestamp1 = datetime(2024, 1, 15, 10, 0, 0)
        timestamp2 = datetime(2024, 1, 15, 10, 1, 0)
        cutoff_time = datetime(2024, 1, 15, 10, 0, 30)
        
        # Mock message objects
        mock_user_message = Mock()
        mock_user_message.get_timestamp.return_value = timestamp1
        mock_ai_message = Mock()
        mock_ai_message.get_timestamp.return_value = timestamp2
        
        for mock_msg in [mock_user_message, mock_ai_message]:
            mock_msg.delete_requested = Mock()
            mock_msg.delete_requested.connect = Mock()
        
        mock_chat_message_class.side_effect = [mock_user_message, mock_ai_message]
        
        # Add messages
        chat_manager.add_user_message(sample_user_text, timestamp=timestamp1)
        chat_manager.add_ai_message(sample_ai_text, timestamp=timestamp2)
        
        # Get messages since cutoff
        recent_messages = chat_manager.get_messages_since(cutoff_time)
        
        # Only AI message should be returned (timestamp2 > cutoff_time)
        assert len(recent_messages) == 1
        assert recent_messages[0] == mock_ai_message

    def test_signal_emissions(self, chat_manager):
        """Test that manager emits appropriate signals."""
        # Verify signals exist
        assert hasattr(chat_manager, 'message_added')
        assert hasattr(chat_manager, 'message_removed')
        assert hasattr(chat_manager, 'messages_cleared')

    @patch('src.chat_manager.ChatMessage')
    @patch('src.chat_manager.QApplication')
    def test_scroll_to_bottom_called(self, mock_qapp, mock_chat_message_class, chat_manager, sample_user_text):
        """Test that QApplication.processEvents is called after adding messages."""
        mock_message = Mock()
        mock_message.delete_requested = Mock()
        mock_message.delete_requested.connect = Mock()
        mock_chat_message_class.return_value = mock_message
        
        chat_manager.add_user_message(sample_user_text)
        
        # Verify processEvents was called for UI updates
        mock_qapp.processEvents.assert_called_once()

    def test_empty_widget_visibility_management(self, chat_manager, mock_messages_layout, mock_empty_message_widget):
        """Test proper management of empty widget visibility."""
        # Initially, empty widget should be visible (no messages)
        assert chat_manager.get_message_count() == 0
        
        # After adding first message, empty widget should be hidden
        with patch('src.chat_manager.ChatMessage') as mock_chat_message_class:
            mock_message = Mock()
            mock_message.delete_requested = Mock()
            mock_message.delete_requested.connect = Mock()
            mock_chat_message_class.return_value = mock_message
            
            chat_manager.add_user_message("Test message")
            mock_empty_message_widget.hide.assert_called_once()
            
            # After removing all messages, empty widget should be shown again
            chat_manager.remove_message(mock_message)
            mock_empty_message_widget.show.assert_called_once() 