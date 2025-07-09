"""
Chat Panel Component

This module provides the main ChatPanel widget that integrates all chat functionality
including message display, input handling, AI interaction, and RAG document chat.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, 
    QFrame, QPushButton, QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import logging

from src.chat_manager import ChatManager
from src.chat_input import ChatInput
from src.responsive_utils import responsive_calc
from config import AI_CHAT

logger = logging.getLogger(__name__)


class ChatPanel(QWidget):
    """
    {
        "name": "ChatPanel",
        "version": "2.0.0",
        "description": "Enhanced chat panel widget supporting both general AI chat and RAG document conversation.",
        "dependencies": ["ChatManager", "ChatInput", "responsive_utils"],
        "interface": {
            "inputs": ["rag_mode: bool", "pdf_document_name: str"],
            "outputs": "Complete chat panel widget with AI conversation and RAG capabilities"
        }
    }
    
    The main chat panel widget that provides a complete chat interface.
    Features message display, input handling, responsive design, AI integration,
    and RAG-based document conversation capabilities.
    """
    
    # Signal emitted when user sends a message
    user_message_sent = pyqtSignal(str)  # Passes the message text
    
    # Signal emitted when AI response is needed (general chat)
    ai_response_requested = pyqtSignal(str)  # Passes the user message
    
    # Signal emitted when RAG document query is needed
    rag_query_requested = pyqtSignal(str)  # Passes the user message for RAG
    
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
        self.rag_mode = False  # RAG mode flag
        self.pdf_document_name = ""  # Current PDF document name
        
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
        """Create a modern empty state widget with responsive design."""
        empty_frame = QFrame()
        empty_frame.setObjectName("empty_state")
        
        # Main layout with improved spacing
        empty_layout = QVBoxLayout(empty_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setContentsMargins(self.spacing["margin"], self.spacing["margin"], 
                                      self.spacing["margin"], self.spacing["margin"])
        empty_layout.setSpacing(self.spacing["item_spacing"])
        
        # Get responsive content
        current_breakpoint = responsive_calc.get_current_breakpoint()
        empty_config = AI_CHAT["empty_state"]["responsive_content"].get(
            current_breakpoint, 
            AI_CHAT["empty_state"]["responsive_content"]["medium"]
        )
        
        # Modern icon with gradient background
        icon_label = QLabel(empty_config["icon"])
        icon_label.setObjectName("empty_icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(80, 80)  # Fixed size for consistent appearance
        
        # Title with modern typography
        title_label = QLabel(empty_config["title"])
        title_label.setObjectName("empty_title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        
        # Description with improved readability
        description_label = QLabel(empty_config["description"])
        description_label.setObjectName("empty_description")
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setMaximumWidth(500)  # Limit width for better readability
        
        # Add widgets to layout
        empty_layout.addWidget(icon_label)
        empty_layout.addWidget(title_label)
        empty_layout.addWidget(description_label)
        
        # Add quick start suggestions for larger screens
        current_breakpoint = responsive_calc.get_current_breakpoint()
        if current_breakpoint in ["large", "xlarge"]:
            suggestions_frame = self._create_quick_suggestions()
            empty_layout.addWidget(suggestions_frame)
        
        # Add stretch to center content
        empty_layout.addStretch()
        
        return empty_frame

    def _create_quick_suggestions(self) -> QWidget:
        """Create modern quick suggestion buttons with responsive layout."""
        suggestions_frame = QFrame()
        suggestions_frame.setObjectName("suggestions_frame")
        suggestions_layout = QVBoxLayout(suggestions_frame)
        suggestions_layout.setContentsMargins(0, self.spacing["margin"], 0, 0)
        suggestions_layout.setSpacing(self.spacing["item_spacing"])
        
        # Modern suggestions label
        suggestions_label = QLabel(AI_CHAT["suggestions"]["label"])
        suggestions_label.setObjectName("suggestions_label")
        suggestions_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        suggestions_layout.addWidget(suggestions_label)
        
        # Get responsive design configuration
        current_breakpoint = responsive_calc.get_current_breakpoint()
        responsive_design = AI_CHAT.get("responsive_design", {})
        breakpoint_config = responsive_design.get(current_breakpoint, responsive_design.get("medium", {}))
        
        # Determine grid layout based on screen size
        columns = breakpoint_config.get("suggestion_columns", 2)
        max_suggestions = breakpoint_config.get("max_suggestions", 4)
        
        # Create grid layout for suggestions
        suggestions_grid = QGridLayout()
        suggestions_grid.setSpacing(self.spacing["item_spacing"] // 2)
        suggestions_grid.setContentsMargins(0, 0, 0, 0)
        
        # Get suggestion buttons from config
        suggestions = AI_CHAT["suggestions"]["buttons"][:max_suggestions]
        
        # Add suggestion buttons to grid
        for i, suggestion in enumerate(suggestions):
            row = i // columns
            col = i % columns
            
            btn = QPushButton(suggestion)
            btn.setObjectName("suggestion_button")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Remove emoji prefix for input (keeping full text for display)
            clean_text = suggestion[2:] if suggestion.startswith(('📋', '🔍', '💡', '❓')) else suggestion
            
            # Connect to input pre-fill
            btn.clicked.connect(lambda checked, text=clean_text: self._prefill_suggestion(text))
            
            # Add button to grid
            suggestions_grid.addWidget(btn, row, col)
        
        # Add grid to main layout
        suggestions_layout.addLayout(suggestions_grid)
        
        return suggestions_frame

    def _prefill_suggestion(self, suggestion_text: str):
        """Pre-fill the input with a suggestion and focus it."""
        if hasattr(self.parent(), 'chat_input') and self.parent().chat_input:
            self.parent().chat_input.set_text(suggestion_text)
            self.parent().chat_input.focus_input()
        elif hasattr(self, 'chat_input') and self.chat_input:
            self.chat_input.set_text(suggestion_text)
            self.chat_input.focus_input()

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
        """Apply modern responsive styling to the chat panel with PyQt6 compatibility."""
        # Get design configuration
        design_config = AI_CHAT.get("design", {})
        colors = AI_CHAT.get("colors", {})
        responsive_design = AI_CHAT.get("responsive_design", {})
        
        # Get current breakpoint for responsive design
        current_breakpoint = responsive_calc.get_current_breakpoint()
        breakpoint_config = responsive_design.get(current_breakpoint, responsive_design.get("medium", {}))
        
        # Get spacing and font configurations
        spacing = responsive_calc.get_spacing_config()
        fonts = responsive_calc.get_font_config()
        
        # Border radius values
        radius = design_config.get("border_radius", {})
        small_radius = radius.get("small", 8)
        medium_radius = radius.get("medium", 12)
        large_radius = radius.get("large", 16)
        
        # Header height from responsive config
        header_height = breakpoint_config.get("header_height", 70)
        
        # Modern chat panel styles with PyQt6 compatibility (no transform, transition, box-shadow)
        modern_style = f"""
        /* ===== CHAT PANEL CONTAINER ===== */
        ChatPanel {{
            background: {colors.get("container", {}).get("background", "#ffffff")};
            border: 1px solid {colors.get("container", {}).get("border", "#e8eaed")};
            border-radius: {large_radius}px;
            padding: 0px;
            margin: 0px;
        }}
        
        /* ===== MODERN HEADER DESIGN ===== */
        QFrame#chat_header {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {colors.get("header", {}).get("gradient_start", "#667eea")}, 
                stop:1 {colors.get("header", {}).get("gradient_end", "#764ba2")});
            border: none;
            border-radius: {large_radius}px {large_radius}px 0px 0px;
            min-height: {header_height}px;
            max-height: {header_height}px;
            margin: 0px;
            padding: {spacing.get("padding", 16)}px;
        }}
        
        QLabel#chat_title {{
            color: {colors.get("header", {}).get("text", "#ffffff")};
            font-weight: 600;
            font-size: {fonts.get("title", 16)}px;
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        }}
        
        QPushButton#clear_button {{
            background: {colors.get("header", {}).get("accent", "rgba(255, 255, 255, 0.2)")};
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: {small_radius * 2}px;
            color: {colors.get("header", {}).get("text", "#ffffff")};
            font-weight: 600;
            font-size: {fonts.get("caption", 10)}px;
            padding: 6px 12px;
            min-width: 60px;
        }}
        
        QPushButton#clear_button:hover {{
            background: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
        }}
        
        QPushButton#clear_button:pressed {{
            background: rgba(255, 255, 255, 0.1);
        }}
        
        /* ===== MESSAGES CONTAINER ===== */
        QWidget#messages_container {{
            background: transparent;
            border: none;
            padding: {spacing.get("padding", 16)}px;
        }}
        
        /* ===== MODERN EMPTY STATE ===== */
        QFrame#empty_state {{
            background: transparent;
            border: none;
            padding: {spacing.get("padding", 16) * 2}px {spacing.get("padding", 16)}px;
        }}
        
        QLabel#empty_icon {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {colors.get("header", {}).get("gradient_start", "#667eea")}, 
                stop:1 {colors.get("header", {}).get("gradient_end", "#764ba2")});
            border-radius: {medium_radius * 2}px;
            color: white;
            font-size: {fonts.get("title", 16) * 2}px;
            padding: {medium_radius}px;
            margin: {spacing.get("margin", 12)}px auto;
        }}
        
        QLabel#empty_title {{
            color: {colors.get("empty_state", {}).get("text_primary", "#202124")};
            font-size: {fonts.get("title", 16) + 2}px;
            font-weight: 700;
            background: transparent;
            border: none;
            margin: {spacing.get("item_spacing", 12)}px 0px {spacing.get("item_spacing", 12) // 2}px 0px;
        }}
        
        QLabel#empty_description {{
            color: {colors.get("empty_state", {}).get("text_secondary", "#5f6368")};
            font-size: {fonts.get("body", 13)}px;
            font-weight: 400;
            background: transparent;
            border: none;
            margin: 0px 0px {spacing.get("margin", 12)}px 0px;
        }}
        
        /* ===== MODERN SUGGESTIONS ===== */
        QFrame#suggestions_frame {{
            background: transparent;
            border: none;
            padding: {spacing.get("margin", 12)}px 0px 0px 0px;
        }}
        
        QLabel#suggestions_label {{
            color: {colors.get("empty_state", {}).get("text_primary", "#202124")};
            font-size: {fonts.get("caption", 10) + 1}px;
            font-weight: 600;
            background: transparent;
            border: none;
            margin: 0px 0px {spacing.get("item_spacing", 12) // 2}px 0px;
        }}
        
        QPushButton#suggestion_button {{
            background: {colors.get("suggestion", {}).get("background", "rgba(103, 126, 234, 0.08)")};
            border: 1px solid {colors.get("suggestion", {}).get("border", "rgba(103, 126, 234, 0.2)")};
            border-radius: {medium_radius}px;
            color: {colors.get("suggestion", {}).get("text", "#3c4043")};
            font-size: {fonts.get("caption", 10)}px;
            font-weight: 500;
            padding: {spacing.get("comfortable", 12)}px {spacing.get("spacious", 16)}px;
            text-align: left;
            min-height: 36px;
        }}
        
        QPushButton#suggestion_button:hover {{
            background: {colors.get("suggestion", {}).get("hover_bg", "rgba(103, 126, 234, 0.12)")};
            border-color: {colors.get("suggestion", {}).get("hover_border", "#667eea")};
        }}
        
        QPushButton#suggestion_button:pressed {{
            background: {colors.get("suggestion", {}).get("active_bg", "rgba(103, 126, 234, 0.16)")};
        }}
        
        /* ===== SCROLL AREA MODERN STYLING ===== */
        QScrollArea {{
            background: transparent;
            border: none;
            border-radius: 0px;
        }}
        
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            border-radius: 4px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background: rgba(0, 0, 0, 0.1);
            border-radius: 4px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: rgba(0, 0, 0, 0.2);
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        
        /* ===== INPUT CONTAINER MODERN STYLING ===== */
        QWidget#input_container {{
            background: {colors.get("container", {}).get("background", "#ffffff")};
            border: none;
            border-top: 1px solid {colors.get("container", {}).get("border", "#e8eaed")};
            padding: {spacing.get("padding", 16)}px;
            border-radius: 0px 0px {large_radius}px {large_radius}px;
        }}
        """
        
        self.setStyleSheet(modern_style)
        logger.info("Applied PyQt6-compatible modern styling to ChatPanel")

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
        
        # Emit appropriate signal based on current mode
        self.user_message_sent.emit(message_text)
        
        if self.rag_mode:
            # RAG document query
            self.rag_query_requested.emit(message_text)
            logger.info(f"RAG query handled: {len(message_text)} characters")
        else:
            # General AI chat
            self.ai_response_requested.emit(message_text)
            logger.info(f"General chat message handled: {len(message_text)} characters")

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

    def set_rag_mode(self, enabled: bool, pdf_name: str = ""):
        """
        Enable or disable RAG mode for document conversation.
        
        Args:
            enabled: Whether to enable RAG mode
            pdf_name: Name of the PDF document (for display)
        """
        self.rag_mode = enabled
        self.pdf_document_name = pdf_name if enabled else ""
        
        # Update UI to reflect mode change
        self._update_mode_ui()
        
        # Clear existing conversation when switching modes
        self.clear_chat()
        
        logger.info(f"RAG mode {'enabled' if enabled else 'disabled'}, document: {pdf_name}")

    def _update_mode_ui(self):
        """Update UI elements based on current mode (RAG vs general chat)."""
        # Update title
        if self.rag_mode and self.pdf_document_name:
            title_text = f"💬 文档对话 - {self.pdf_document_name}"
        else:
            title_text = responsive_calc.get_chat_panel_title()
        
        self.title_label.setText(title_text)
        
        # Update empty state
        self._update_empty_state()
        
        # Update chat input placeholder
        if hasattr(self, 'chat_input'):
            if self.rag_mode:
                self.chat_input.set_placeholder_text("向文档提问...")
            else:
                self.chat_input.set_placeholder_text("Ask AI anything...")

    def _update_empty_state(self):
        """Update empty state content based on current mode."""
        if self.rag_mode:
            # RAG mode empty state
            empty_config = {
                "icon": "💬",
                "title": "开始与文档对话！",
                "description": f"你现在可以向《{self.pdf_document_name}》提问了。\n\n尝试询问：\n• \"总结这个文档\"\n• \"解释关键概念\"\n• \"帮助我理解这篇论文\"\n• 任何关于文档内容的问题"
            }
        else:
            # General chat mode empty state
            empty_config = responsive_calc.get_chat_empty_state_config()
        
        if hasattr(self, 'empty_message'):
            # Update icon
            if hasattr(self.empty_message, 'layout') and self.empty_message.layout():
                icon_label = self.empty_message.layout().itemAt(0).widget()
                if icon_label:
                    icon_label.setText(empty_config["icon"])
                
                # Update title
                title_label = self.empty_message.layout().itemAt(1).widget()
                if title_label:
                    title_label.setText(empty_config["title"])
                
                # Update description
                desc_label = self.empty_message.layout().itemAt(2).widget()
                if desc_label:
                    desc_label.setText(empty_config["description"])

    def is_rag_mode(self) -> bool:
        """Check if currently in RAG mode."""
        return self.rag_mode

    def get_pdf_document_name(self) -> str:
        """Get the current PDF document name."""
        return self.pdf_document_name 