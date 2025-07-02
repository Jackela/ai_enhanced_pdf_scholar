"""
Chat Panel Component

This module provides the main ChatPanel widget that integrates all chat functionality
including message display, input handling, and AI interaction.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, 
    QFrame, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import logging

from src.chat_manager import ChatManager
from src.chat_input import ChatInput
from src.responsive_utils import responsive_calc

logger = logging.getLogger(__name__)


class ChatPanel(QWidget):
    """
    {
        "name": "ChatPanel",
        "version": "1.0.0",
        "description": "Main chat panel widget integrating message display, input, and AI interaction.",
        "dependencies": ["ChatManager", "ChatInput", "responsive_utils"],
        "interface": {
            "inputs": [],
            "outputs": "Complete chat panel widget with AI conversation capabilities"
        }
    }
    
    The main chat panel widget that provides a complete chat interface.
    Features message display, input handling, responsive design, and AI integration.
    """
    
    # Signal emitted when user sends a message
    user_message_sent = pyqtSignal(str)  # Passes the message text
    
    # Signal emitted when AI response is needed
    ai_response_requested = pyqtSignal(str)  # Passes the user message
    
    # Signal emitted when chat is cleared
    chat_cleared = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the chat panel."""
        super().__init__(parent)
        
        # Get responsive configuration
        self.colors = responsive_calc.get_chat_colors()
        self.spacing = responsive_calc.get_chat_spacing_config()
        self.fonts = responsive_calc.get_font_config()
        
        # State management
        self.is_ai_responding = False
        
        self._setup_ui()
        self._apply_styling()
        self._connect_signals()
        
        logger.info("ChatPanel initialized")

    def _setup_ui(self):
        """Setup the UI components of the chat panel."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Header Section ---
        header_widget = self._create_header()
        main_layout.addWidget(header_widget)
        
        # --- Messages Section ---
        messages_widget = self._create_messages_section()
        main_layout.addWidget(messages_widget, 1)  # Take most space
        
        # --- Input Section ---
        input_widget = self._create_input_section()
        main_layout.addWidget(input_widget)

    def _create_header(self) -> QWidget:
        """Create the chat panel header with title and controls."""
        header_frame = QFrame()
        header_frame.setObjectName("chat_header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(
            self.spacing["padding"],
            self.spacing["padding"] // 2,
            self.spacing["padding"],
            self.spacing["padding"] // 2
        )
        header_layout.setSpacing(self.spacing["item_spacing"])
        
        # Title label
        title_text = responsive_calc.get_chat_panel_title()
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("chat_title")
        title_font = QFont()
        title_font.setPointSize(self.fonts["title"])
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        
        # Clear button
        self.clear_button = QPushButton("🗑️")
        self.clear_button.setObjectName("clear_button")
        self.clear_button.setToolTip("Clear all messages")
        self.clear_button.setFixedSize(32, 32)
        clear_font = QFont()
        clear_font.setPointSize(self.fonts["body"])
        self.clear_button.setFont(clear_font)
        
        # Layout
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_button)
        
        return header_frame

    def _create_messages_section(self) -> QWidget:
        """Create the scrollable messages display section."""
        # Container widget
        messages_container = QWidget()
        messages_container.setObjectName("messages_container")
        container_layout = QVBoxLayout(messages_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Scroll area for messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("messages_scroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Messages widget (scrollable content)
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("messages_widget")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(
            self.spacing["margin"],
            self.spacing["margin"],
            self.spacing["margin"],
            self.spacing["margin"]
        )
        self.messages_layout.setSpacing(self.spacing["item_spacing"])
        self.messages_layout.addStretch()  # Push messages to top
        
        # Empty state message
        self.empty_message = self._create_empty_state()
        self.messages_layout.addWidget(self.empty_message)
        
        # Set the messages widget as the scroll area content
        self.scroll_area.setWidget(self.messages_widget)
        
        # Add scroll area to container
        container_layout.addWidget(self.scroll_area)
        
        return messages_container

    def _create_empty_state(self) -> QWidget:
        """Create the empty state widget shown when no messages exist."""
        empty_config = responsive_calc.get_chat_empty_state_config()
        
        empty_frame = QFrame()
        empty_frame.setObjectName("empty_state")
        empty_layout = QVBoxLayout(empty_frame)
        empty_layout.setContentsMargins(
            self.spacing["padding"],
            self.spacing["padding"] * 2,
            self.spacing["padding"],
            self.spacing["padding"] * 2
        )
        empty_layout.setSpacing(self.spacing["item_spacing"])
        
        # Icon label
        icon_label = QLabel(empty_config["icon"])
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(self.fonts["title"] * 2)
        icon_label.setFont(icon_font)
        
        # Title label
        title_label = QLabel(empty_config["title"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_font = QFont()
        title_font.setPointSize(self.fonts["title"])
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        # Description label
        description_label = QLabel(empty_config["description"])
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(self.fonts["body"])
        description_label.setFont(desc_font)
        
        # Add to layout
        empty_layout.addWidget(icon_label)
        empty_layout.addWidget(title_label)
        empty_layout.addWidget(description_label)
        
        return empty_frame

    def _create_input_section(self) -> QWidget:
        """Create the message input section."""
        input_container = QWidget()
        input_container.setObjectName("input_container")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)
        
        # Chat input widget
        self.chat_input = ChatInput()
        input_layout.addWidget(self.chat_input)
        
        return input_container

    def _apply_styling(self):
        """Apply styling to the chat panel components."""
        # Get responsive style templates
        panel_style = responsive_calc.create_responsive_style(
            responsive_calc.get_chat_panel_style_template()
        )
        
        primary_color = self.colors["primary"]
        secondary_color = self.colors["secondary"]
        
        additional_styles = f"""
            QFrame#chat_header {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {primary_color}, stop:1 {secondary_color});
                border: none;
                border-radius: 0px;
                margin: 0px;
                padding: 0px;
            }}
            
            QLabel#chat_title {{
                color: white;
                background-color: transparent;
                border: none;
                font-weight: bold;
            }}
            
            QPushButton#clear_button {{
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: {self.spacing["margin"] // 2}px;
                font-weight: bold;
            }}
            
            QPushButton#clear_button:hover {{
                background-color: rgba(255, 255, 255, 0.3);
                border-color: white;
            }}
            
            QPushButton#clear_button:pressed {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            
            QWidget#messages_container {{
                background-color: transparent;
                border: none;
            }}
            
            QScrollArea#messages_scroll {{
                background-color: transparent;
                border: none;
            }}
            
            QWidget#messages_widget {{
                background-color: transparent;
            }}
            
            QFrame#empty_state {{
                background-color: rgba(0, 120, 212, 0.05);
                border: 2px dashed rgba(0, 120, 212, 0.3);
                border-radius: {self.spacing["margin"]}px;
                margin: {self.spacing["margin"]}px;
            }}
            
            QFrame#empty_state QLabel {{
                color: {primary_color};
                background-color: transparent;
                border: none;
            }}
            
            QWidget#input_container {{
                background-color: transparent;
                border: none;
            }}
        """
        
        complete_style = panel_style + additional_styles
        self.setStyleSheet(complete_style)

    def _connect_signals(self):
        """Connect internal signals."""
        # Chat input signals
        self.chat_input.message_sent.connect(self._handle_user_message)
        
        # Clear button
        self.clear_button.clicked.connect(self.clear_chat)
        
        # Initialize chat manager after UI setup
        self.chat_manager = ChatManager(
            self.messages_layout,
            self.empty_message,
            parent=self
        )
        
        # Connect chat manager signals
        self.chat_manager.message_added.connect(self._on_message_added)
        self.chat_manager.message_removed.connect(self._on_message_removed)
        self.chat_manager.messages_cleared.connect(self._on_messages_cleared)

    def _handle_user_message(self, message_text: str):
        """Handle a new user message."""
        if not message_text.strip() or self.is_ai_responding:
            return
        
        # Add user message to chat
        user_message = self.chat_manager.add_user_message(message_text)
        
        # Disable input while AI is responding
        self.chat_input.set_enabled(False)
        self.is_ai_responding = True
        
        # Emit signal for AI processing
        self.user_message_sent.emit(message_text)
        self.ai_response_requested.emit(message_text)
        
        logger.info(f"User message handled: {len(message_text)} characters")

    def add_ai_response(self, response_text: str):
        """Add an AI response to the chat."""
        if not response_text.strip():
            logger.warning("Attempted to add empty AI response")
            return
        
        # Add AI message to chat
        ai_message = self.chat_manager.add_ai_message(response_text)
        
        # Re-enable input
        self.chat_input.set_enabled(True)
        self.is_ai_responding = False
        
        # Focus back to input
        self.chat_input.focus_input()
        
        logger.info(f"AI response added: {len(response_text)} characters")

    def handle_ai_error(self, error_message: str):
        """Handle an AI error by showing an error message."""
        error_response = f"❌ **Error**: {error_message}\n\nPlease try again or check your settings."
        self.add_ai_response(error_response)

    def clear_chat(self):
        """Clear all messages from the chat."""
        self.chat_manager.clear_all_messages()
        self.chat_input.clear_input()
        self.chat_input.focus_input()
        self.chat_cleared.emit()
        logger.info("Chat cleared by user")

    def _on_message_added(self, message):
        """Handle when a message is added."""
        # Scroll to bottom to show new message
        QTimer.singleShot(100, self._scroll_to_bottom)

    def _on_message_removed(self, message):
        """Handle when a message is removed."""
        pass

    def _on_messages_cleared(self):
        """Handle when all messages are cleared."""
        pass

    def _scroll_to_bottom(self):
        """Scroll the messages area to the bottom."""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def get_message_count(self) -> int:
        """Get the total number of messages in the chat."""
        return self.chat_manager.get_message_count()

    def get_conversation_history(self) -> list:
        """Get the conversation history."""
        return self.chat_manager.get_conversation_history()

    def export_conversation(self) -> str:
        """Export the conversation as text."""
        return self.chat_manager.export_conversation()

    def set_enabled(self, enabled: bool):
        """Enable or disable the chat panel."""
        self.chat_input.set_enabled(enabled and not self.is_ai_responding)
        self.clear_button.setEnabled(enabled)

    def focus_input(self):
        """Set focus to the chat input."""
        self.chat_input.focus_input()

    def resizeEvent(self, event):
        """Handle resize events to update message widths."""
        super().resizeEvent(event)
        if hasattr(self, 'chat_manager'):
            # Update message widths based on new panel width
            self.chat_manager.update_message_widths(self.width())

    def is_responding(self) -> bool:
        """Check if AI is currently responding."""
        return self.is_ai_responding

    def get_last_user_message(self) -> str:
        """Get the text of the last user message."""
        last_message = self.chat_manager.get_last_message()
        if last_message and last_message.is_user_message():
            return last_message.get_message_text()
        return "" 