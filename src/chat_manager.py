"""
Chat Manager Component

This module provides the ChatManager class for managing the lifecycle of chat messages
in the chat panel. It handles adding, removing, and organizing chat messages.
"""

from typing import List, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QApplication
from datetime import datetime
import logging

from src.chat_message import ChatMessage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


class ChatManager(QObject):
    """
    {
        "name": "ChatManager", 
        "version": "1.0.0",
        "description": "Manages chat messages lifecycle in the chat panel with efficient message handling.",
        "dependencies": ["ChatMessage"],
        "interface": {
            "inputs": [
                {"name": "messages_layout", "type": "QVBoxLayout"},
                {"name": "empty_message_widget", "type": "QWidget"}
            ],
            "outputs": "Managed chat message collection"
        }
    }
    
    Manages the lifecycle of chat message widgets within the chat panel.
    Provides functionality to add, remove, and organize chat messages.
    """
    
    # Signal emitted when a new message is added
    message_added = pyqtSignal(object)  # Passes ChatMessage object
    
    # Signal emitted when a message is removed
    message_removed = pyqtSignal(object)  # Passes ChatMessage object
    
    # Signal emitted when all messages are cleared
    messages_cleared = pyqtSignal()

    def __init__(self, messages_layout: QVBoxLayout, empty_message_widget: 'QWidget', parent=None):
        """
        Initialize the chat manager.
        
        Args:
            messages_layout: The layout for chat messages
            empty_message_widget: Widget to show when no messages exist
            parent: The parent QObject
        """
        super().__init__(parent)
        
        self.messages_layout = messages_layout
        self.empty_message_widget = empty_message_widget
        # List to maintain message order (newest at bottom)
        self.messages: List[ChatMessage] = []
        
        logger.info("ChatManager initialized")

    def add_user_message(self, message_text: str, timestamp: datetime = None) -> ChatMessage:
        """
        Add a user message to the chat.
        
        Args:
            message_text: The user's message content
            timestamp: When the message was created (defaults to now)
            
        Returns:
            The created ChatMessage widget
        """
        return self._add_message(message_text, is_user=True, timestamp=timestamp)

    def add_ai_message(self, message_text: str, timestamp: datetime = None) -> ChatMessage:
        """
        Add an AI response message to the chat.
        
        Args:
            message_text: The AI's response content
            timestamp: When the message was created (defaults to now)
            
        Returns:
            The created ChatMessage widget
        """
        return self._add_message(message_text, is_user=False, timestamp=timestamp)

    def _add_message(self, message_text: str, is_user: bool, timestamp: datetime = None) -> ChatMessage:
        """
        Internal method to add a message to the chat.
        
        Args:
            message_text: The message content
            is_user: True if this is a user message, False for AI message
            timestamp: When the message was created (defaults to now)
            
        Returns:
            The created ChatMessage widget
        """
        # Validate input
        if not message_text or not message_text.strip():
            logger.warning("Attempted to add empty message, skipping")
            return None
        
        # Create the message widget
        message_widget = ChatMessage(
            message_text=message_text.strip(),
            is_user=is_user,
            timestamp=timestamp or datetime.now()
        )
        
        # Connect delete signal
        message_widget.delete_requested.connect(self.remove_message)
        
        # Add to layout (newest at bottom)
        self.messages_layout.addWidget(message_widget)
        
        # Store message reference
        self.messages.append(message_widget)
        
        # Hide empty message if this is the first message
        if len(self.messages) == 1:
            self.empty_message_widget.hide()
        
        # Emit signal
        self.message_added.emit(message_widget)
        
        logger.info(f"Added {'user' if is_user else 'AI'} message with {len(message_text)} characters. Total messages: {len(self.messages)}")
        
        # Process layout changes and scroll to bottom
        QApplication.processEvents()
        self._scroll_to_bottom()
        
        return message_widget

    def remove_message(self, message: ChatMessage):
        """
        Remove a specific message from the chat.
        
        Args:
            message: The ChatMessage widget to remove
        """
        if message in self.messages:
            self.messages.remove(message)
            self.messages_layout.removeWidget(message)
            message.deleteLater()
            
            # Show empty message if no messages left
            if not self.messages:
                self.empty_message_widget.show()
            
            # Emit signal
            self.message_removed.emit(message)
            
            logger.info(f"Removed chat message. Remaining messages: {len(self.messages)}")

    def clear_all_messages(self):
        """Remove all messages from the chat and clear the records."""
        logger.info(f"Clearing all chat messages ({len(self.messages)} total)")
        
        # Remove all messages
        for message in self.messages[:]:  # Copy list to avoid modification during iteration
            self.remove_message(message)
        
        self.messages.clear()
        self.empty_message_widget.show()
        
        # Emit signal
        self.messages_cleared.emit()

    def get_message_count(self) -> int:
        """Get the total number of messages."""
        return len(self.messages)

    def get_user_message_count(self) -> int:
        """Get the number of user messages."""
        return sum(1 for msg in self.messages if msg.is_user_message())

    def get_ai_message_count(self) -> int:
        """Get the number of AI messages."""
        return sum(1 for msg in self.messages if not msg.is_user_message())

    def get_last_message(self) -> ChatMessage:
        """Get the most recent message."""
        return self.messages[-1] if self.messages else None

    def get_conversation_history(self) -> List[dict]:
        """
        Get the conversation history as a list of dictionaries.
        
        Returns:
            List of message dictionaries with 'text', 'is_user', and 'timestamp' keys
        """
        history = []
        for message in self.messages:
            history.append({
                'text': message.get_message_text(),
                'is_user': message.is_user_message(),
                'timestamp': message.get_timestamp()
            })
        return history

    def export_conversation(self) -> str:
        """
        Export the conversation as a formatted text string.
        
        Returns:
            Formatted conversation text
        """
        if not self.messages:
            return "No messages in conversation."
        
        lines = []
        lines.append("=== Chat Conversation Export ===\n")
        
        for message in self.messages:
            sender = "You" if message.is_user_message() else "AI Assistant"
            timestamp = message.get_timestamp().strftime("%Y-%m-%d %H:%M:%S")
            text = message.get_message_text()
            
            lines.append(f"[{timestamp}] {sender}:")
            lines.append(f"{text}\n")
        
        return "\n".join(lines)

    def _scroll_to_bottom(self):
        """Scroll the chat to the bottom to show the newest message."""
        # This will be handled by the parent scroll area
        # We emit a signal that the parent can connect to
        pass

    def update_message_widths(self, panel_width: int):
        """
        Update the maximum width of all messages based on panel width.
        
        Args:
            panel_width: Current width of the chat panel
        """
        for message in self.messages:
            message.update_max_width(panel_width)

    def find_message_by_text(self, text: str) -> ChatMessage:
        """
        Find a message by its text content.
        
        Args:
            text: The text to search for
            
        Returns:
            The first ChatMessage with matching text, or None if not found
        """
        for message in self.messages:
            if message.get_message_text() == text:
                return message
        return None

    def get_messages_since(self, timestamp: datetime) -> List[ChatMessage]:
        """
        Get all messages created after the specified timestamp.
        
        Args:
            timestamp: The cutoff timestamp
            
        Returns:
            List of ChatMessage widgets created after the timestamp
        """
        return [
            message for message in self.messages 
            if message.get_timestamp() > timestamp
        ] 