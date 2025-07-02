"""
Chat Input Component

This module provides the ChatInput widget for user message input in the chat panel.
It supports multi-line text input, keyboard shortcuts, and responsive design.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QFont, QTextCursor
import logging

from src.responsive_utils import responsive_calc
from config import AI_CHAT

logger = logging.getLogger(__name__)


class ChatInputTextEdit(QTextEdit):
    """
    Custom QTextEdit that handles Enter key for sending messages and Shift+Enter for new lines.
    """
    
    # Signal emitted when user wants to send message (Enter pressed)
    send_requested = pyqtSignal(str)  # Passes the message text
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)  # Only plain text
        
        # Set up keyboard shortcuts
        self._setup_shortcuts()
        
        # Configure text edit behavior
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Auto-resize behavior
        self.textChanged.connect(self._adjust_height)
        
        # Set size policies
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for the text edit."""
        # Enter key to send (without modifiers)
        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.enter_shortcut.activated.connect(self._handle_enter)
        
        # Shift+Enter for new line (handled automatically by QTextEdit)
        # Ctrl+Enter as alternative send method
        self.ctrl_enter_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.ctrl_enter_shortcut.activated.connect(self._handle_enter)

    def _handle_enter(self):
        """Handle Enter key press to send message."""
        text = self.toPlainText().strip()
        if text:
            self.send_requested.emit(text)
            self.clear()
            self._reset_height()

    def _adjust_height(self):
        """Adjust the height of the text edit based on content."""
        # Get document height
        doc_height = self.document().size().height()
        
        # Calculate new height with padding - use config value
        font_height = self.fontMetrics().height()
        max_lines = AI_CHAT["input_settings"]["max_lines"]
        min_height = font_height + 20  # Minimum height (1 line + padding)
        max_height = font_height * max_lines + 20  # Maximum height (config lines + padding)
        
        new_height = max(min_height, min(max_height, int(doc_height) + 20))
        self.setFixedHeight(new_height)

    def _reset_height(self):
        """Reset height to minimum after clearing text."""
        font_height = self.fontMetrics().height()
        min_height = font_height + 20
        self.setFixedHeight(min_height)

    def keyPressEvent(self, event):
        """Handle key press events."""
        # Handle Shift+Enter for new line
        if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # Insert a new line
            cursor = self.textCursor()
            cursor.insertText("\n")
            return
        
        # Handle regular Enter (without Shift) for sending
        if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._handle_enter()
            return
        
        # For all other keys, use default behavior
        super().keyPressEvent(event)


class ChatInput(QWidget):
    """
    {
        "name": "ChatInput",
        "version": "1.0.0",
        "description": "Chat input widget with text area, send button, and responsive design.",
        "dependencies": ["ChatInputTextEdit", "responsive_utils", "config"],
        "interface": {
            "inputs": [],
            "outputs": "Chat input widget with send functionality"
        }
    }
    
    A complete chat input widget with text area and send button.
    Features keyboard shortcuts, auto-resize, and responsive design.
    """
    
    # Signal emitted when user sends a message
    message_sent = pyqtSignal(str)  # Passes the message text
    
    # Signal emitted when input focus changes
    focus_changed = pyqtSignal(bool)  # True when focused, False when lost focus

    def __init__(self, parent=None):
        """Initialize the chat input widget."""
        super().__init__(parent)
        
        # Get responsive configuration
        self.colors = responsive_calc.get_chat_colors()
        self.spacing = responsive_calc.get_chat_spacing_config()
        self.fonts = responsive_calc.get_font_config()
        
        # Get UI text and settings from config
        self.ui_text = AI_CHAT["ui_text"]
        self.input_settings = AI_CHAT["input_settings"]
        
        # State management
        self.is_sending = False
        
        self._setup_ui()
        self._apply_styling()
        self._connect_signals()
        
        logger.info("ChatInput widget initialized")

    def _setup_ui(self):
        """Setup the UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            self.spacing["padding"],
            self.spacing["padding"] // 2,
            self.spacing["padding"],
            self.spacing["padding"] // 2
        )
        main_layout.setSpacing(self.spacing["item_spacing"] // 2)
        
        # Input container frame
        input_frame = QFrame()
        input_frame.setObjectName("input_frame")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(
            self.spacing["padding"] // 2,
            self.spacing["padding"] // 2,
            self.spacing["padding"] // 2,
            self.spacing["padding"] // 2
        )
        input_layout.setSpacing(self.spacing["item_spacing"] // 2)
        
        # Input area layout
        input_area_layout = QHBoxLayout()
        input_area_layout.setContentsMargins(0, 0, 0, 0)
        input_area_layout.setSpacing(self.spacing["item_spacing"])
        
        # Text input
        self.text_input = ChatInputTextEdit()
        self.text_input.setObjectName("text_input")
        
        # Get responsive placeholder text
        placeholder = self._get_responsive_placeholder()
        self.text_input.setPlaceholderText(placeholder)
        
        # Set font from config
        input_font = QFont()
        input_font.setPointSize(self.fonts["body"])
        input_font.setFamily(self.input_settings["font_family"])
        self.text_input.setFont(input_font)
        
        # Send button - use config text
        self.send_button = QPushButton(self.ui_text["send_button"])
        self.send_button.setObjectName("send_button")
        send_font = QFont()
        send_font.setPointSize(self.fonts["body"])
        send_font.setBold(True)
        self.send_button.setFont(send_font)
        
        # Configure send button size from config
        button_size = self.input_settings["button_size"]
        self.send_button.setFixedSize(button_size["width"], button_size["height"])
        self.send_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Add to input area layout
        input_area_layout.addWidget(self.text_input, 1)
        input_area_layout.addWidget(self.send_button)
        
        # Add to input layout
        input_layout.addLayout(input_area_layout)
        
        # Add to main layout
        main_layout.addWidget(input_frame)
        
        # Initially disable send button
        self.send_button.setEnabled(False)

    def _get_responsive_placeholder(self):
        """Get responsive placeholder text from config."""
        # Get current breakpoint
        breakpoint = responsive_calc.get_current_breakpoint()
        
        # Get responsive placeholder and add instruction
        base_placeholder = AI_CHAT["input_placeholder"]["responsive_content"].get(
            breakpoint, 
            AI_CHAT["input_placeholder"]["responsive_content"]["medium"]
        )
        
        instruction = self.ui_text["input_instruction"]
        return f"{base_placeholder} {instruction}"

    def _apply_styling(self):
        """Apply styling to the chat input components."""
        # Color configuration
        primary_color = self.colors["primary"]
        secondary_color = self.colors["secondary"]
        
        # Use only PyQt6-supported CSS properties
        style = f"""
            QFrame#input_frame {{
                background-color: white;
                border: 2px solid {primary_color};
                border-radius: {self.spacing["margin"]}px;
                margin: 0px;
            }}
            
            QTextEdit#text_input {{
                background-color: transparent;
                border: 1px solid #e0e0e0;
                border-radius: {self.spacing["margin"] // 2}px;
                padding: {self.spacing["padding"] // 2}px;
                selection-background-color: {primary_color};
                selection-color: white;
            }}
            
            QTextEdit#text_input:focus {{
                border-color: {secondary_color};
                background-color: #f8f9fa;
            }}
            
            QPushButton#send_button {{
                background-color: {primary_color};
                color: white;
                border: none;
                border-radius: {self.spacing["margin"] // 2}px;
                padding: {self.spacing["padding"] // 2}px;
            }}
            
            QPushButton#send_button:hover:enabled {{
                background-color: {secondary_color};
            }}
            
            QPushButton#send_button:pressed:enabled {{
                background-color: #005a9e;
            }}
            
            QPushButton#send_button:disabled {{
                background-color: #cccccc;
                color: #888888;
            }}
        """
        
        self.setStyleSheet(style)

    def _connect_signals(self):
        """Connect internal signals."""
        # Text change detection for send button state
        self.text_input.textChanged.connect(self._on_text_changed)
        
        # Send button click
        self.send_button.clicked.connect(self._send_message)
        
        # Text input send request
        self.text_input.send_requested.connect(self._send_message_with_text)
        
        # Focus tracking
        self.text_input.focusInEvent = self._on_focus_in
        self.text_input.focusOutEvent = self._on_focus_out

    def _on_text_changed(self):
        """Handle text change to update send button state."""
        text = self.text_input.toPlainText().strip()
        self.send_button.setEnabled(bool(text) and not self.is_sending)

    def _send_message(self):
        """Send the current message in the text input."""
        text = self.text_input.toPlainText().strip()
        if text and not self.is_sending:
            self._send_message_with_text(text)

    def _send_message_with_text(self, text: str):
        """Send a message with the specified text."""
        if not text.strip() or self.is_sending:
            return
        
        # Set sending state - use config text
        self.is_sending = True
        self.send_button.setEnabled(False)
        self.send_button.setText(self.ui_text["sending_button"])
        
        # Clear input
        self.text_input.clear()
        
        # Emit signal
        self.message_sent.emit(text.strip())
        
        logger.info(f"Message sent: {len(text)} characters")
        
        # Reset state after a short delay
        QTimer.singleShot(500, self._reset_send_state)

    def _reset_send_state(self):
        """Reset the sending state."""
        self.is_sending = False
        self.send_button.setText(self.ui_text["send_button"])
        self._on_text_changed()  # Update button state based on current text

    def _on_focus_in(self, event):
        """Handle focus in event."""
        # Call original focus in event
        QTextEdit.focusInEvent(self.text_input, event)
        self.focus_changed.emit(True)

    def _on_focus_out(self, event):
        """Handle focus out event."""
        # Call original focus out event
        QTextEdit.focusOutEvent(self.text_input, event)
        self.focus_changed.emit(False)

    def set_placeholder_text(self, placeholder: str):
        """Set the placeholder text for the input."""
        self.text_input.setPlaceholderText(placeholder)

    def clear_input(self):
        """Clear the text input."""
        self.text_input.clear()

    def set_enabled(self, enabled: bool):
        """Enable or disable the chat input."""
        self.text_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled and bool(self.text_input.toPlainText().strip()))

    def focus_input(self):
        """Set focus to the text input."""
        self.text_input.setFocus()

    def get_current_text(self) -> str:
        """Get the current text in the input."""
        return self.text_input.toPlainText()

    def set_text(self, text: str):
        """Set the text in the input."""
        self.text_input.setPlainText(text)
        self.text_input.moveCursor(QTextCursor.MoveOperation.End) 