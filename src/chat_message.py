"""
Chat Message Component

This module provides the ChatMessage widget for displaying individual chat messages
in the chat panel. It supports both user and AI messages with different styling,
Markdown rendering for AI responses, and responsive design.
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, 
    QTextBrowser, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor
from datetime import datetime
import markdown
import logging

from src.responsive_utils import responsive_calc

logger = logging.getLogger(__name__)


class ChatMessage(QWidget):
    """
    {
        "name": "ChatMessage",
        "version": "1.0.0", 
        "description": "Individual chat message widget supporting user and AI messages with Markdown rendering.",
        "dependencies": ["markdown", "responsive_utils"],
        "interface": {
            "inputs": [
                {"name": "message_text", "type": "string"},
                {"name": "is_user", "type": "boolean"},
                {"name": "timestamp", "type": "datetime", "optional": true}
            ],
            "outputs": "QWidget with styled chat message"
        }
    }
    
    A modern chat message widget that displays user and AI messages with distinct styling.
    Features Markdown rendering for AI responses, timestamps, and responsive design.
    """
    
    # Signal emitted when the message is deleted
    delete_requested = pyqtSignal(object)  # Passes self as argument
    
    def __init__(self, message_text: str, is_user: bool, timestamp: datetime = None):
        """
        Initialize a chat message widget.
        
        Args:
            message_text: The message content
            is_user: True if this is a user message, False for AI message
            timestamp: When the message was created (defaults to now)
        """
        super().__init__()
        
        self.message_text = message_text
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now()
        
        # Get responsive configuration
        self.colors = responsive_calc.get_chat_colors()
        self.spacing = responsive_calc.get_chat_spacing_config()
        self.fonts = responsive_calc.get_font_config()
        
        self._setup_ui()
        self._apply_styling()
        
        logger.info(f"Created chat message: {'user' if is_user else 'AI'} message with {len(message_text)} characters")

    def _setup_ui(self):
        """Setup the UI components of the chat message."""
        self.setContentsMargins(0, 0, 0, 0)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            self.spacing["margin"],
            self.spacing["margin"] // 2,
            self.spacing["margin"], 
            self.spacing["margin"] // 2
        )
        main_layout.setSpacing(self.spacing["item_spacing"] // 2)
        
        # Message container
        message_container = QFrame()
        message_container.setObjectName("message_container")
        container_layout = QVBoxLayout(message_container)
        container_layout.setContentsMargins(
            self.spacing["padding"],
            self.spacing["padding"] // 2,
            self.spacing["padding"],
            self.spacing["padding"] // 2
        )
        container_layout.setSpacing(self.spacing["item_spacing"] // 3)
        
        # Header with sender and timestamp
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(self.spacing["item_spacing"])
        
        # Sender label
        sender_label = QLabel("You" if self.is_user else "AI Assistant")
        sender_label.setObjectName("sender_label")
        sender_font = QFont()
        sender_font.setPointSize(self.fonts["caption"])
        sender_font.setBold(True)
        sender_label.setFont(sender_font)
        
        # Timestamp label
        timestamp_label = QLabel(self.timestamp.strftime("%H:%M"))
        timestamp_label.setObjectName("timestamp_label")
        timestamp_font = QFont()
        timestamp_font.setPointSize(self.fonts["caption"] - 1)
        timestamp_label.setFont(timestamp_font)
        
        if self.is_user:
            header_layout.addStretch()
            header_layout.addWidget(timestamp_label)
            header_layout.addWidget(sender_label)
        else:
            header_layout.addWidget(sender_label)
            header_layout.addWidget(timestamp_label)
            header_layout.addStretch()
        
        # Message content
        if self.is_user:
            # Simple text for user messages
            self.content_label = QLabel()
            self.content_label.setObjectName("user_content")
            self.content_label.setText(self.message_text)
            self.content_label.setWordWrap(True)
            self.content_label.setAlignment(Qt.AlignmentFlag.AlignRight if self.is_user else Qt.AlignmentFlag.AlignLeft)
            
            content_font = QFont()
            content_font.setPointSize(self.fonts["body"])
            self.content_label.setFont(content_font)
            
            container_layout.addLayout(header_layout)
            container_layout.addWidget(self.content_label)
        else:
            # Markdown rendering for AI messages
            self.content_browser = QTextBrowser()
            self.content_browser.setObjectName("ai_content")
            self._setup_markdown_renderer()
            self._render_markdown_content()
            
            # Set minimum height and scrollbar policy
            self.content_browser.setMaximumHeight(300)
            self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            container_layout.addLayout(header_layout)
            container_layout.addWidget(self.content_browser)
        
        # Adjust alignment based on sender
        if self.is_user:
            main_layout.addStretch()
            main_layout.addWidget(message_container, alignment=Qt.AlignmentFlag.AlignRight)
            message_container.setMaximumWidth(int(self.parent().width() * 0.8) if self.parent() else 300)
        else:
            main_layout.addWidget(message_container, alignment=Qt.AlignmentFlag.AlignLeft)
            main_layout.addStretch()
            message_container.setMaximumWidth(int(self.parent().width() * 0.85) if self.parent() else 350)

    def _setup_markdown_renderer(self):
        """Setup Markdown rendering for AI messages."""
        if hasattr(self, 'content_browser'):
            # Configure the QTextBrowser for better Markdown display
            self.content_browser.setOpenExternalLinks(False)
            self.content_browser.setOpenLinks(False)
            
            # Set font
            content_font = QFont()
            content_font.setPointSize(self.fonts["body"])
            content_font.setFamily("Segoe UI, Arial, sans-serif")
            self.content_browser.setFont(content_font)

    def _render_markdown_content(self):
        """Render the message content as Markdown."""
        if hasattr(self, 'content_browser'):
            # Convert Markdown to HTML
            html_content = markdown.markdown(
                self.message_text,
                extensions=[
                    'markdown.extensions.fenced_code',
                    'markdown.extensions.codehilite',
                    'markdown.extensions.tables',
                    'markdown.extensions.toc'
                ]
            )
            
            # Wrap with custom styling
            styled_html = self._wrap_html_with_styling(html_content)
            self.content_browser.setHtml(styled_html)

    def _wrap_html_with_styling(self, html_content: str) -> str:
        """Wrap HTML content with custom CSS styling."""
        ai_colors = self.colors["ai_message"]
        
        css_style = f"""
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: {self.fonts["body"]}px;
                line-height: 1.5;
                color: {ai_colors["text"]};
                margin: 0;
                padding: 0;
                background-color: transparent;
            }}
            
            h1, h2, h3, h4, h5, h6 {{
                color: {self.colors["primary"]};
                margin-top: 0.5em;
                margin-bottom: 0.3em;
                font-weight: 600;
            }}
            
            p {{
                margin: 0.3em 0;
            }}
            
            code {{
                background-color: #f1f3f4;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {self.fonts["body"] - 1}px;
                color: #d73a49;
            }}
            
            pre {{
                background-color: #f6f8fa;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 8px 12px;
                overflow-x: auto;
                margin: 0.5em 0;
            }}
            
            pre code {{
                background-color: transparent;
                padding: 0;
                color: #24292e;
            }}
            
            ul, ol {{
                margin: 0.3em 0;
                padding-left: 1.5em;
            }}
            
            li {{
                margin: 0.1em 0;
            }}
            
            blockquote {{
                border-left: 4px solid {self.colors["primary"]};
                margin: 0.5em 0;
                padding-left: 1em;
                font-style: italic;
                opacity: 0.8;
            }}
            
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 0.5em 0;
            }}
            
            th, td {{
                border: 1px solid #e1e4e8;
                padding: 4px 8px;
                text-align: left;
            }}
            
            th {{
                background-color: #f6f8fa;
                font-weight: 600;
            }}
            
            a {{
                color: {self.colors["primary"]};
                text-decoration: none;
            }}
            
            a:hover {{
                text-decoration: underline;
            }}
        </style>
        """
        
        return f"<html><head>{css_style}</head><body>{html_content}</body></html>"

    def _apply_styling(self):
        """Apply styling to the chat message based on sender type."""
        if self.is_user:
            # User message styling (right-aligned, blue)
            user_colors = self.colors["user_message"]
            
            message_style = f"""
                QFrame#message_container {{
                    background-color: {user_colors["background"]};
                    border: 1px solid {user_colors["border"]};
                    border-radius: {self.spacing["margin"]}px;
                    border-bottom-right-radius: 4px;
                }}
                
                QLabel#sender_label {{
                    color: white;
                    font-weight: bold;
                }}
                
                QLabel#timestamp_label {{
                    color: rgba(255, 255, 255, 0.8);
                }}
                
                QLabel#user_content {{
                    color: {user_colors["text"]};
                    background-color: transparent;
                }}
            """
        else:
            # AI message styling (left-aligned, light gray)
            ai_colors = self.colors["ai_message"]
            
            message_style = f"""
                QFrame#message_container {{
                    background-color: {ai_colors["background"]};
                    border: 1px solid {ai_colors["border"]};
                    border-radius: {self.spacing["margin"]}px;
                    border-bottom-left-radius: 4px;
                }}
                
                QLabel#sender_label {{
                    color: {self.colors["primary"]};
                    font-weight: bold;
                }}
                
                QLabel#timestamp_label {{
                    color: #888888;
                }}
                
                QTextBrowser#ai_content {{
                    background-color: transparent;
                    border: none;
                    color: {ai_colors["text"]};
                }}
            """
        
        self.setStyleSheet(message_style)

    def get_message_text(self) -> str:
        """Get the message text content."""
        return self.message_text

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.is_user

    def get_timestamp(self) -> datetime:
        """Get the message timestamp."""
        return self.timestamp

    def update_max_width(self, parent_width: int):
        """Update the maximum width based on parent container width."""
        if hasattr(self, 'message_container'):
            max_width = int(parent_width * (0.8 if self.is_user else 0.85))
            # Find the message container and update its maximum width
            container = self.findChild(QFrame, "message_container")
            if container:
                container.setMaximumWidth(max_width) 