from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QGraphicsDropShadowEffect, QFrame, QTextEdit, QTextBrowser
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
import logging
import markdown
from src.responsive_utils import responsive_calc

logger = logging.getLogger(__name__)


class StickyNoteAnnotation(QWidget):
    """
    A sticky note-style annotation widget that can be expanded/collapsed.
    Features beautiful styling with shadows, rounded corners, and smooth animations.
    Supports mouse hover auto-expansion when collapsed.
    """
    
    # Signal emitted when the annotation is deleted
    delete_requested = pyqtSignal(object)  # Passes self as argument
    
    # Signal emitted when annotation expansion state changes (for repositioning)
    expansion_changed = pyqtSignal(object)  # Passes self as argument
    
    def __init__(self, parent, rect, text, page_number, pdf_coords):
        super().__init__(parent)
        
        # Core properties
        self.selection_rect = rect
        self.text = text
        self.expanded = False
        self.page_number = page_number
        self.pdf_coords = pdf_coords
        
        # Hover state tracking
        self.hover_expanded = False
        self.was_manually_expanded = False
        
        # Styling properties
        self.collapsed_width = 200
        self.collapsed_height = 35
        self.expanded_width = 300
        self.expanded_height = 150
        
        # Colors for sticky note
        self.colors = [
            "#FFE66D",  # Yellow
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal  
            "#95E1D3",  # Mint
            "#A8E6CF",  # Light green
            "#FFD93D",  # Gold
            "#6C5CE7",  # Purple
            "#FD79A8"   # Pink
        ]
        self.current_color = self.colors[hash(text) % len(self.colors)]
        
        self._setup_ui()
        self._apply_styling()
        self._setup_animations()
        
        # Start in collapsed state
        self.setFixedSize(self.collapsed_width, self.collapsed_height)
        
        # Ensure proper z-order and visibility settings
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Use Widget instead of SubWindow for better control
        self.setWindowFlags(Qt.WindowType.Widget)
        
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        
        # Initially hidden - AnnotationManager will show it
        self.hide()
        
        logger.info(f"Created sticky note annotation for page {page_number} with size {self.collapsed_width}x{self.collapsed_height}")

    def _setup_ui(self):
        """Setup the UI components of the sticky note."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(0) # No space between header and content

        # --- Header Widget ---
        self.header_widget = QWidget(self)
        self.header_widget.setObjectName("header_widget")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(5, 3, 5, 3)
        header_layout.setSpacing(5)
        
        self.toggle_button = QPushButton("💭", self.header_widget)
        self.toggle_button.setFixedSize(25, 25)
        self.toggle_button.clicked.connect(self.toggle_expansion)
        self.toggle_button.setToolTip("Expand/Collapse note")
        
        self.delete_button = QPushButton("✕", self.header_widget)
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.clicked.connect(self._request_delete)
        self.delete_button.setToolTip("Delete note")
        
        # Preview text (always visible when collapsed)
        self.preview_label = QLabel(self.header_widget)
        self.preview_label.setWordWrap(True)
        self._update_preview_text()
        
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.preview_label, 1) # Stretch
        header_layout.addWidget(self.delete_button)
        
        # --- Content Area ---
        self.content_text = QTextEdit(self) # Parent is the main annotation widget
        self.content_text.setPlainText(self.text)
        self.content_text.setReadOnly(True)
        self.content_text.hide()
        
        self.layout.addWidget(self.header_widget)
        self.layout.addWidget(self.content_text)

    def _update_preview_text(self):
        """Update the preview text shown in collapsed state."""
        # Show first 50 characters with ellipsis
        preview = self.text[:47] + "..." if len(self.text) > 50 else self.text
        self.preview_label.setText(preview)

    def _apply_styling(self):
        """Apply beautiful sticky note styling."""
        header_color = QColor(self.current_color).darker(115).name()
        
        # Main widget styling
        self.setStyleSheet(f"""
            StickyNoteAnnotation {{
                background-color: {self.current_color};
                border: 1px solid #AAA;
                border-radius: 8px;
            }}
            
            #header_widget {{
                background-color: {header_color};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #AAA;
            }}
            
            QLabel {{
                background-color: transparent;
                color: #FFF; /* White text on dark header */
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                border: none;
            }}
            
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
                color: #FFF; /* White text on dark header */
            }}
            
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.4);
                border-color: #999;
            }}
            
            QPushButton:pressed {{
                background-color: rgba(200, 200, 200, 0.8);
            }}
            
            QTextEdit {{
                background-color: {self.current_color};
                border: none;
                padding: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                color: #333;
            }}
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

    def _setup_animations(self):
        """Setup smooth animations for expand/collapse."""
        self.size_animation = QPropertyAnimation(self, b"size")
        self.size_animation.setDuration(250)
        self.size_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _request_delete(self):
        """Request deletion of this annotation."""
        logger.info(f"Delete requested for annotation on page {self.page_number}")
        self.delete_requested.emit(self)

    def toggle_expansion(self):
        """Toggle between expanded and collapsed states with animation."""
        # Update manual expansion tracking
        self.was_manually_expanded = not self.expanded if not self.hover_expanded else self.was_manually_expanded
        
        self.expanded = not self.expanded
        
        if self.expanded:
            logger.info(f"Expanding annotation on page {self.page_number}")
            self.toggle_button.setText("📖")
            self.toggle_button.setToolTip("Collapse note")
            
            # Start animation to expanded size
            self.size_animation.setStartValue(self.size())
            self.size_animation.setEndValue(QSize(self.expanded_width, self.expanded_height))
            self.size_animation.finished.connect(self._on_expansion_finished)
            self.size_animation.start()
        else:
            logger.info(f"Collapsing annotation on page {self.page_number}")
            # Hide content first, then animate size
            self.content_text.hide()
            
            self.toggle_button.setText("💭")
            self.toggle_button.setToolTip("Expand note")
            
            self.size_animation.setStartValue(self.size())
            self.size_animation.setEndValue(QSize(self.collapsed_width, self.collapsed_height))
            self.size_animation.finished.connect(self._on_expansion_finished)
            self.size_animation.start()
        
        # Emit signal for repositioning
        self.expansion_changed.emit(self)

    def _on_expansion_finished(self):
        """Called after expansion/collapse animation finishes."""
        self.size_animation.finished.disconnect()
        if self.expanded:
            self.setFixedSize(self.expanded_width, self.expanded_height)
            self.content_text.show()
        else:
            self.setFixedSize(self.collapsed_width, self.collapsed_height)

    def _show_content(self):
        """Show the content text when expanded."""
        self.content_text.show()

    def paintEvent(self, event):
        """Custom paint event for rounded corners and shadows."""
        super().paintEvent(event)
        
        # Draw border around selection area if needed
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw a subtle border
        pen = QPen(QColor("#CCC"), 1)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def enterEvent(self, event):
        """Handle mouse enter event for auto-expansion."""
        if not self.expanded and not self.was_manually_expanded:
            self.hover_expanded = True
            self._expand_for_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave event for auto-collapse."""
        if self.hover_expanded:
            self.hover_expanded = False
            self._collapse_from_hover()
        super().leaveEvent(event)

    def _expand_for_hover(self):
        """Expand the annotation when mouse hovers over it."""
        logger.info(f"Auto-expanding annotation on page {self.page_number} due to hover")
        self.expanded = True
        
        self.toggle_button.setText("📖")
        self.toggle_button.setToolTip("Collapse note")
        
        # Start animation to expanded size
        self.size_animation.setStartValue(self.size())
        self.size_animation.setEndValue(QSize(self.expanded_width, self.expanded_height))
        self.size_animation.finished.connect(self._on_hover_expansion_finished)
        self.size_animation.start()
        
        # Emit signal for repositioning
        self.expansion_changed.emit(self)

    def _collapse_from_hover(self):
        """Collapse the annotation when mouse leaves."""
        logger.info(f"Auto-collapsing annotation on page {self.page_number} as mouse left")
        self.expanded = False
        
        # Hide content first, then animate size
        self.content_text.hide()
        
        self.toggle_button.setText("💭")
        self.toggle_button.setToolTip("Expand note")
        
        self.size_animation.setStartValue(self.size())
        self.size_animation.setEndValue(QSize(self.collapsed_width, self.collapsed_height))
        self.size_animation.finished.connect(self._on_hover_collapse_finished)
        self.size_animation.start()
        
        # Emit signal for repositioning
        self.expansion_changed.emit(self)

    def _on_hover_expansion_finished(self):
        """Called after hover expansion animation finishes."""
        self.size_animation.finished.disconnect()
        self.setFixedSize(self.expanded_width, self.expanded_height)
        self.content_text.show()

    def _on_hover_collapse_finished(self):
        """Called after hover collapse animation finishes."""
        self.size_animation.finished.disconnect()
        self.setFixedSize(self.collapsed_width, self.collapsed_height)


# Keep the old class name as an alias for backward compatibility
Annotation = StickyNoteAnnotation

class PanelAnnotation(QWidget):
    """
    A modern panel-style annotation widget for the right sidebar.
    Features optimized layout with minimal selected text preview and 
    Markdown-rendered AI responses for enhanced readability.
    """
    
    # Signal emitted when the annotation is deleted
    delete_requested = pyqtSignal(object)  # Passes self as argument
    
    # Signal emitted when user wants to highlight the source in PDF
    highlight_requested = pyqtSignal(object)  # Passes self as argument
    
    def __init__(self, text, page_number, pdf_coords, selected_text=""):
        super().__init__()
        
        # Core properties
        self.text = text
        self.page_number = page_number
        self.pdf_coords = pdf_coords
        self.selected_text = selected_text
        self.expanded = True  # Start expanded to show AI content
        
        # Markdown renderer
        self.markdown_renderer = markdown.Markdown(
            extensions=['extra', 'codehilite'],
            extension_configs={
                'codehilite': {
                    'use_pygments': False,  # Use simple styling instead of Pygments
                    'css_class': 'highlight'
                }
            }
        )
        
        # Get responsive color scheme from config
        colors_config = responsive_calc.get_annotation_colors()
        self.colors = colors_config["backgrounds"]
        self.accent_colors = colors_config["accents"]
        
        color_index = hash(text) % len(self.colors)
        self.current_color = self.colors[color_index]
        self.accent_color = self.accent_colors[color_index]
        
        self._setup_ui()
        self._apply_styling()
        
        logger.info(f"Created modern panel annotation for page {page_number}")

    def _setup_ui(self):
        """Setup the modern UI components with responsive layout."""
        # Get responsive spacing configuration
        spacing_config = responsive_calc.get_spacing_config()
        fonts_config = responsive_calc.get_font_config()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(
            spacing_config["padding"]//2, 
            spacing_config["margin"]//2, 
            spacing_config["padding"]//2, 
            spacing_config["margin"]//2
        )
        self.layout.setSpacing(spacing_config["item_spacing"]//2)

        # --- Compact Header Section ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(spacing_config["item_spacing"]//2)
        
        # Page indicator with responsive styling
        self.page_label = QLabel(f"📄 Page {self.page_number + 1}")
        self.page_label.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                color: {self.accent_color};
                font-size: {fonts_config["caption"]}px;
                padding: 2px 6px;
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 4px;
            }}
        """)
        
        # Control buttons with responsive design
        button_size = max(24, fonts_config["body"] + 12)  # Responsive button size
        self.toggle_button = QPushButton("📖" if self.expanded else "💭")
        self.toggle_button.setFixedSize(button_size, button_size)
        self.toggle_button.clicked.connect(self.toggle_expansion)
        self.toggle_button.setToolTip("Expand/Collapse AI response")
        
        self.delete_button = QPushButton("🗑️")
        self.delete_button.setFixedSize(button_size, button_size)
        self.delete_button.clicked.connect(self._request_delete)
        self.delete_button.setToolTip("Delete annotation")
        
        header_layout.addWidget(self.page_label)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.delete_button)
        
        # --- Minimal Selected Text Preview (responsive) ---
        if self.selected_text:
            # Responsive preview text length based on screen size
            max_chars = 27 if responsive_calc.get_current_breakpoint() in ["small", "medium"] else 35
            preview_text = self.selected_text[:max_chars-3] + "..." if len(self.selected_text) > max_chars else self.selected_text
            self.preview_label = QLabel(f'"{preview_text}"')
            
            # Store full text for expansion
            self.full_selected_text = self.selected_text
            self.is_preview_expanded = False
            
            # Responsive height based on font size
            max_height = fonts_config["caption"] + 8
            
            self.preview_label.setStyleSheet(f"""
                QLabel {{
                    font-style: italic;
                    color: {self.accent_color};
                    font-size: {fonts_config["caption"]}px;
                    padding: 4px 8px;
                    background-color: rgba(255, 255, 255, 0.6);
                    border-left: 3px solid {self.accent_color};
                    border-radius: 4px;
                    margin: 2px 0px;
                    cursor: pointer;
                }}
                QLabel:hover {{
                    background-color: rgba(255, 255, 255, 0.8);
                    border-left: 4px solid {self.accent_color};
                }}
            """)
            self.preview_label.setWordWrap(False)  # Keep it to single line initially
            self.preview_label.setMaximumHeight(max_height)  # Responsive height
            
            # Enable mouse tracking and events
            self.preview_label.setMouseTracking(True)
            self.preview_label.enterEvent = self._on_preview_enter
            self.preview_label.leaveEvent = self._on_preview_leave
            self.preview_label.mousePressEvent = self._on_preview_click
        else:
            self.preview_label = None
        
        # --- AI Response with Markdown Support (Primary Content) ---
        self.content_browser = QTextBrowser()
        self.content_browser.setReadOnly(True)
        self.content_browser.setOpenExternalLinks(True)
        
        # Render Markdown to HTML
        try:
            html_content = self.markdown_renderer.convert(self.text)
            wrapped_html = self._wrap_html_with_styling(html_content)
            self.content_browser.setHtml(wrapped_html)
            logger.debug(f"Markdown rendered successfully for annotation on page {self.page_number}")
        except Exception as e:
            logger.warning(f"Failed to render Markdown: {e}")
            # Fallback to plain text
            self.content_browser.setPlainText(self.text)
        
        # Set responsive height for AI content based on screen size
        breakpoint = responsive_calc.get_current_breakpoint()
        if breakpoint == "small":
            min_height, max_height = 100, 300
        elif breakpoint == "medium":
            min_height, max_height = 120, 350
        elif breakpoint == "large":
            min_height, max_height = 140, 400
        else:  # xlarge
            min_height, max_height = 160, 450
            
        self.content_browser.setMinimumHeight(min_height)
        self.content_browser.setMaximumHeight(max_height)
        
        # Add to layout
        self.layout.addLayout(header_layout)
        if self.preview_label:
            self.layout.addWidget(self.preview_label)
        self.layout.addWidget(self.content_browser)
        
        # Ensure proper initial visibility based on expanded state
        if self.expanded:
            self.content_browser.show()
            self.toggle_button.setText("📖")
            self.toggle_button.setToolTip("Collapse AI response")
        else:
            self.content_browser.hide()
            self.toggle_button.setText("💭")
            self.toggle_button.setToolTip("Expand AI response")

    def _wrap_html_with_styling(self, html_content):
        """Wrap the Markdown HTML with responsive CSS styling."""
        fonts_config = responsive_calc.get_font_config()
        spacing_config = responsive_calc.get_spacing_config()
        
        return f"""
        <div style="
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: {fonts_config['body']}px;
            line-height: 1.4;
            color: #2c3e50;
            margin: 0;
            padding: {spacing_config['margin']//2}px;
        ">
            {html_content}
        </div>
        <style>
            h1, h2, h3, h4, h5, h6 {{
                color: {self.accent_color};
                margin: {spacing_config['margin']//2}px 0 {spacing_config['margin']//4}px 0;
                font-weight: 600;
            }}
            h1 {{ font-size: {fonts_config['title']}px; }}
            h2 {{ font-size: {fonts_config['body'] + 2}px; }}
            h3 {{ font-size: {fonts_config['body'] + 1}px; }}
            p {{ margin: {spacing_config['margin']//4}px 0; }}
            strong {{ color: {self.accent_color}; font-weight: 600; }}
            em {{ color: #7f8c8d; }}
            code {{
                background-color: rgba(0, 0, 0, 0.05);
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {fonts_config['caption']}px;
            }}
            pre {{
                background-color: rgba(0, 0, 0, 0.05);
                padding: {spacing_config['margin']//2}px;
                border-radius: 4px;
                border-left: 3px solid {self.accent_color};
                margin: {spacing_config['margin']//2}px 0;
                overflow-x: auto;
            }}
            blockquote {{
                border-left: 3px solid {self.accent_color};
                margin: {spacing_config['margin']//2}px 0;
                padding-left: {spacing_config['padding']//2}px;
                font-style: italic;
                color: #7f8c8d;
            }}
            ul, ol {{ margin: {spacing_config['margin']//4}px 0; padding-left: {spacing_config['padding']}px; }}
            li {{ margin: 2px 0; }}
        </style>
        """

    def _apply_styling(self):
        """Apply modern Material Design inspired styling."""
        self.setStyleSheet(f"""
            PanelAnnotation {{
                background-color: {self.current_color};
                border: 1px solid {self.accent_color}40;
                border-radius: 8px;
                margin: 3px;
            }}
            
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid {self.accent_color}60;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 500;
                color: {self.accent_color};
            }}
            
            QPushButton:hover {{
                background-color: {self.accent_color}15;
                border-color: {self.accent_color};
            }}
            
            QPushButton:pressed {{
                background-color: {self.accent_color}30;
            }}
            
            QTextBrowser {{
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid {self.accent_color}30;
                border-radius: 6px;
                padding: 2px;
                selection-background-color: {self.accent_color}40;
            }}
        """)
        
        # Add modern drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def toggle_expansion(self):
        """Toggle between expanded and collapsed states."""
        self.expanded = not self.expanded
        
        if self.expanded:
            self.toggle_button.setText("📖")
            self.toggle_button.setToolTip("Collapse AI response")
            self.content_browser.show()
        else:
            self.toggle_button.setText("💭")
            self.toggle_button.setToolTip("Expand AI response")
            self.content_browser.hide()
        
        logger.info(f"Panel annotation {'expanded' if self.expanded else 'collapsed'}")

    def _request_delete(self):
        """Request deletion of this annotation."""
        logger.info(f"Delete requested for panel annotation on page {self.page_number}")
        self.delete_requested.emit(self)

    def _on_preview_enter(self, event):
        """Handle mouse enter event on preview label - expand to show full text."""
        if self.preview_label and not self.is_preview_expanded and len(self.full_selected_text) > 35:
            self.is_preview_expanded = True
            self.preview_label.setText(f'"{self.full_selected_text}"')
            self.preview_label.setWordWrap(True)
            self.preview_label.setMaximumHeight(120)  # Allow expansion
            self.preview_label.adjustSize()
            
    def _on_preview_leave(self, event):
        """Handle mouse leave event on preview label - collapse back to preview."""
        if self.preview_label and self.is_preview_expanded:
            self.is_preview_expanded = False
            # Reset to preview text
            fonts_config = responsive_calc.get_font_config()
            max_chars = 27 if responsive_calc.get_current_breakpoint() in ["small", "medium"] else 35
            preview_text = self.full_selected_text[:max_chars-3] + "..." if len(self.full_selected_text) > max_chars else self.full_selected_text
            self.preview_label.setText(f'"{preview_text}"')
            self.preview_label.setWordWrap(False)
            max_height = fonts_config["caption"] + 8
            self.preview_label.setMaximumHeight(max_height)
            self.preview_label.adjustSize()
            
    def _on_preview_click(self, event):
        """Handle click event on preview label - toggle expansion."""
        if self.preview_label and len(self.full_selected_text) > 35:
            if self.is_preview_expanded:
                self._on_preview_leave(None)
            else:
                self._on_preview_enter(None)
