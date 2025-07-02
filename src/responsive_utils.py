"""
Responsive UI Utilities

This module provides utilities for creating responsive user interfaces
that adapt to different screen sizes and resolutions.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize
import config
import logging

logger = logging.getLogger(__name__)


class ResponsiveCalculator:
    """
    A utility class for calculating responsive UI dimensions and styles
    based on screen size and application configuration.
    """
    
    def __init__(self):
        self.config = config.RESPONSIVE_UI
        self.annotations_config = config.AI_ANNOTATIONS
        self.chat_config = config.AI_CHAT
        self._current_breakpoint = None
        self._screen_size = None
        self._update_screen_info()
    
    def _update_screen_info(self):
        """Update current screen information and breakpoint."""
        screen = QApplication.primaryScreen()
        if screen:
            self._screen_size = screen.availableGeometry().size()
            width = self._screen_size.width()
            
            # Determine current breakpoint
            breakpoints = self.config["breakpoints"]
            if width <= breakpoints["small"]:
                self._current_breakpoint = "small"
            elif width <= breakpoints["medium"]:
                self._current_breakpoint = "medium"
            elif width <= breakpoints["large"]:
                self._current_breakpoint = "large"
            else:
                self._current_breakpoint = "xlarge"
                
            logger.info(f"Screen size: {width}x{self._screen_size.height()}, breakpoint: {self._current_breakpoint}")
        else:
            # Fallback for missing screen info
            self._current_breakpoint = "medium"
            self._screen_size = QSize(1440, 900)
            logger.warning("Could not detect screen size, using medium breakpoint fallback")
    
    def get_current_breakpoint(self) -> str:
        """Get the current responsive breakpoint."""
        return self._current_breakpoint
    
    def get_chat_panel_width(self, window_width: int) -> int:
        """
        Calculate optimal width for chat panel based on window size.
        
        Args:
            window_width: Current window width in pixels
            
        Returns:
            Optimal panel width in pixels
        """
        panel_config = self.config["chat_panel"]
        
        # Calculate width based on ratio
        ratio = panel_config["width_ratio"][self._current_breakpoint]
        calculated_width = int(window_width * ratio)
        
        # Apply min/max constraints
        min_width = panel_config["min_width"]
        max_width = panel_config["max_width"]
        
        final_width = max(min_width, min(max_width, calculated_width))
        
        logger.debug(f"Chat panel width calculation: window={window_width}, ratio={ratio}, calculated={calculated_width}, final={final_width}")
        return final_width
    
    def get_annotations_panel_width(self, window_width: int) -> int:
        """
        Calculate optimal width for annotations panel based on window size.
        
        Args:
            window_width: Current window width in pixels
            
        Returns:
            Optimal panel width in pixels
        """
        panel_config = self.config["annotations_panel"]
        
        # Calculate width based on ratio
        ratio = panel_config["width_ratio"][self._current_breakpoint]
        calculated_width = int(window_width * ratio)
        
        # Apply min/max constraints
        min_width = panel_config["min_width"]
        max_width = panel_config["max_width"]
        
        final_width = max(min_width, min(max_width, calculated_width))
        
        logger.debug(f"Panel width calculation: window={window_width}, ratio={ratio}, calculated={calculated_width}, final={final_width}")
        return final_width
    
    def get_chat_spacing_config(self) -> dict:
        """Get spacing configuration for chat panel based on current breakpoint."""
        return self.config["chat_panel"]["spacing"][self._current_breakpoint]
    
    def get_spacing_config(self) -> dict:
        """Get spacing configuration for current breakpoint."""
        return self.config["annotations_panel"]["spacing"][self._current_breakpoint]
    
    def get_font_config(self) -> dict:
        """Get font size configuration for current breakpoint."""
        return self.config["fonts"][self._current_breakpoint]
    
    def get_annotation_colors(self) -> dict:
        """Get color configuration for annotations."""
        return self.annotations_config["colors"]
    
    def get_chat_empty_state_config(self) -> dict:
        """Get responsive empty state configuration for chat panel based on current breakpoint."""
        empty_state = self.chat_config["empty_state"]
        
        # Get responsive content if available
        if "responsive_content" in empty_state and self._current_breakpoint in empty_state["responsive_content"]:
            responsive_content = empty_state["responsive_content"][self._current_breakpoint]
            logger.debug(f"Using responsive chat empty state content for breakpoint: {self._current_breakpoint}")
            return responsive_content
        else:
            # Fallback to default content
            logger.debug("Using fallback chat empty state content")
            return {
                "icon": empty_state.get("icon", "🤖"),
                "title": empty_state.get("title", "AI Chat Assistant"),
                "description": empty_state.get("description", "Start a conversation with your AI assistant!")
            }
    
    def get_chat_input_placeholder(self) -> str:
        """Get responsive placeholder text for chat input based on current breakpoint."""
        placeholder_config = self.chat_config["input_placeholder"]
        
        # Get responsive placeholder if available
        if "responsive_content" in placeholder_config and self._current_breakpoint in placeholder_config["responsive_content"]:
            return placeholder_config["responsive_content"][self._current_breakpoint]
        else:
            # Fallback to default
            return "Ask AI anything..."
    
    def get_chat_panel_title(self) -> str:
        """Get the chat panel title from configuration."""
        return self.chat_config["panel_title"]
    
    def get_chat_colors(self) -> dict:
        """Get color configuration for chat messages."""
        return self.chat_config["colors"]
    
    def get_empty_state_config(self) -> dict:
        """Get responsive empty state configuration based on current breakpoint."""
        empty_state = self.annotations_config["empty_state"]
        
        # Get responsive content if available
        if "responsive_content" in empty_state and self._current_breakpoint in empty_state["responsive_content"]:
            responsive_content = empty_state["responsive_content"][self._current_breakpoint]
            logger.debug(f"Using responsive empty state content for breakpoint: {self._current_breakpoint}")
            return responsive_content
        else:
            # Fallback to default content
            logger.debug("Using fallback empty state content")
            return {
                "icon": empty_state.get("icon", "🚀"),
                "title": empty_state.get("title", "Start Your AI Journey"),
                "description": empty_state.get("description", "Select text to create annotations!")
            }
    
    def get_panel_title(self) -> str:
        """Get the panel title from configuration."""
        return self.annotations_config["panel_title"]
    
    def get_pdf_selection_config(self) -> dict:
        """Get PDF selection styling configuration."""
        return config.PDF_SELECTION
    
    def _hex_to_rgba(self, hex_color: str, alpha: float = 1.0) -> str:
        """Convert hex color to rgba string."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"
    
    def create_responsive_style(self, base_style: str, **dynamic_values) -> str:
        """
        Create a responsive style string by interpolating dynamic values.
        
        Args:
            base_style: Base CSS style template with placeholders
            **dynamic_values: Values to interpolate into the template
            
        Returns:
            Complete CSS style string
        """
        spacing = self.get_spacing_config()
        fonts = self.get_font_config()
        colors = self.get_annotation_colors()
        
        # Add responsive color variations
        style_values = {
            **spacing,
            **fonts,
            **colors,
            # Convert hex colors to rgba for gradients
            "primary_light": self._hex_to_rgba(colors["primary"], 0.1),
            "primary_medium": self._hex_to_rgba(colors["primary"], 0.2),
            "secondary_light": self._hex_to_rgba(colors["secondary"], 0.1),
            "border_light": self._hex_to_rgba(colors["primary"], 0.15),
            **dynamic_values
        }
        
        try:
            return base_style.format(**style_values)
        except KeyError as e:
            logger.warning(f"Missing style value: {e}")
            return base_style
    
    def get_chat_panel_style_template(self) -> str:
        """Get the responsive style template for the chat panel."""
        return """
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255, 255, 255, 0.95), stop:1 {primary_light});
                border-right: {margin}px solid {border_light};
                border-radius: {margin}px 0px 0px {margin}px;
                margin: {margin}px 0px;
            }}
        """
    
    def get_chat_input_style_template(self) -> str:
        """Get the responsive style template for chat input area."""
        return """
            QTextEdit {{
                background-color: white;
                border: 2px solid {primary};
                border-radius: {margin}px;
                padding: {padding}px;
                font-size: {body}px;
                font-family: 'Segoe UI', Arial, sans-serif;
                max-height: 80px;
                min-height: 36px;
            }}
            QTextEdit:focus {{
                border-color: {secondary};
                background-color: #f8f9fa;
            }}
            
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {primary}, stop:1 {secondary});
                color: white;
                border: none;
                border-radius: {margin}px;
                padding: 8px 16px;
                font-weight: 600;
                min-width: 60px;
                max-height: 36px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {secondary}, stop:1 {primary});
            }}
            QPushButton:pressed {{
                background: {secondary};
                padding: 9px 15px 7px 17px;
            }}
            QPushButton:disabled {{
                background: #cccccc;
                color: #888888;
            }}
        """
    
    def get_chat_message_style_template(self) -> str:
        """Get the responsive style template for chat messages."""
        return """
            .chat-message {{
                margin: {item_spacing}px 0px;
                padding: {padding}px;
                border-radius: {margin}px;
                font-size: {body}px;
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.4;
            }}
            .user-message {{
                background-color: {{user_bg}};
                color: {{user_text}};
                margin-left: 20px;
                border-bottom-right-radius: 4px;
            }}
            .ai-message {{
                background-color: {{ai_bg}};
                color: {{ai_text}};
                margin-right: 20px;
                border-bottom-left-radius: 4px;
            }}
        """
    
    def get_panel_style_template(self) -> str:
        """Get the responsive style template for the annotations panel."""
        return """
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255, 255, 255, 0.95), stop:1 {primary_light});
                border-left: {margin}px solid {border_light};
                border-radius: 0px {margin}px {margin}px 0px;
                margin: {margin}px 0px;
            }}
        """
    
    def get_title_style_template(self) -> str:
        """Get the responsive style template for the panel title."""
        return """
            QLabel {{
                font-size: {title}px;
                font-weight: 600;
                color: white;
                padding: {padding}px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {primary}, stop:1 {secondary});
                border-radius: {margin}px;
                margin-bottom: {margin}px;
                text-align: center;
            }}
        """
    
    def get_empty_state_style_template(self) -> str:
        """Get the responsive style template for empty state message."""
        return """
            QLabel {{
                color: {primary};
                font-size: {body}px;
                font-weight: 400;
                line-height: 1.5;
                padding: {padding}px {padding}px {padding}px {padding}px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9), stop:1 {primary_light});
                border: 2px solid {primary_light};
                border-radius: {margin}px;
                margin: {margin}px;
                text-align: center;
                min-height: 140px;
            }}
            QLabel:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 1.0), stop:1 {primary_medium});
                border-color: {primary};
            }}
        """
    
    def get_scroll_area_style_template(self) -> str:
        """Get the responsive style template for scroll area."""
        # Calculate responsive scrollbar width
        scrollbar_width = max(6, self.get_spacing_config()["margin"] // 2)
        
        return f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {self._hex_to_rgba(self.get_annotation_colors()["primary"], 0.1)};
                width: {scrollbar_width}px;
                border-radius: {scrollbar_width // 2}px;
            }}
            QScrollBar::handle:vertical {{
                background: {self._hex_to_rgba(self.get_annotation_colors()["primary"], 0.4)};
                border-radius: {scrollbar_width // 2}px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {self._hex_to_rgba(self.get_annotation_colors()["primary"], 0.6)};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """
    
    def get_annotation_item_style_template(self) -> str:
        """Get the responsive style template for individual annotation items."""
        return """
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9), stop:1 {primary_light});
                border: 1px solid {border_light};
                border-radius: {margin}px;
                margin: {item_spacing}px 0px;
                padding: 0px;
            }}
            QFrame:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 1.0), stop:1 {primary_medium});
                border-color: {primary};
            }}
        """
    
    def refresh(self):
        """Refresh screen information and recalculate responsive values."""
        self._update_screen_info()


# Global instance for easy access
responsive_calc = ResponsiveCalculator() 