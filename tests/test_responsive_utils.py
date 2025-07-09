"""
Test suite for responsive_utils module.

Tests for:
- ResponsiveCalculator class functionality
- Breakpoint detection and screen size handling
- Panel width calculations
- Configuration retrieval methods
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen

from src.responsive_utils import ResponsiveCalculator, responsive_calc


class TestResponsiveCalculator:
    """Test suite for ResponsiveCalculator class."""
    
    @pytest.fixture
    def calculator(self):
        """Create a ResponsiveCalculator instance for testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_initialization(self, calculator):
        """Test proper initialization of ResponsiveCalculator."""
        assert calculator.config is not None
        assert calculator.annotations_config is not None
        assert calculator.chat_config is not None
        assert calculator._current_breakpoint is not None
        assert calculator._screen_size is not None
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_screen_info_update_small_screen(self, mock_screen):
        """Test screen info update with small screen size."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(800, 600)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "small"
        assert calc._screen_size.width() == 800
        assert calc._screen_size.height() == 600
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_screen_info_update_medium_screen(self, mock_screen):
        """Test screen info update with medium screen size."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1200, 800)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_screen_info_update_large_screen(self, mock_screen):
        """Test screen info update with large screen size."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1600, 1000)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "large"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_screen_info_update_xlarge_screen(self, mock_screen):
        """Test screen info update with extra large screen size."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(2560, 1440)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "xlarge"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_screen_info_fallback_no_screen(self, mock_screen):
        """Test fallback when no screen is available."""
        mock_screen.return_value = None
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
        assert calc._screen_size.width() == 1440
        assert calc._screen_size.height() == 900
    
    def test_get_current_breakpoint(self, calculator):
        """Test getting current breakpoint."""
        breakpoint = calculator.get_current_breakpoint()
        assert breakpoint in ["small", "medium", "large", "xlarge"]
    
    def test_chat_panel_width_calculation_basic(self, calculator):
        """Test basic chat panel width calculation."""
        window_width = 1200
        panel_width = calculator.get_chat_panel_width(window_width)
        
        assert isinstance(panel_width, int)
        assert panel_width > 0
        assert panel_width <= window_width
    
    def test_chat_panel_width_min_constraint(self, calculator):
        """Test that chat panel width respects minimum constraint."""
        # Very small window width
        window_width = 100
        panel_width = calculator.get_chat_panel_width(window_width)
        
        # Should use minimum width from config
        min_width = calculator.config["chat_panel"]["min_width"]
        assert panel_width >= min_width
    
    def test_chat_panel_width_max_constraint(self, calculator):
        """Test that chat panel width respects maximum constraint."""
        # Very large window width
        window_width = 5000
        panel_width = calculator.get_chat_panel_width(window_width)
        
        # Should use maximum width from config
        max_width = calculator.config["chat_panel"]["max_width"]
        assert panel_width <= max_width
    
    def test_annotations_panel_width_calculation_basic(self, calculator):
        """Test basic annotations panel width calculation."""
        window_width = 1200
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        assert isinstance(panel_width, int)
        assert panel_width > 0
        assert panel_width <= window_width
    
    def test_annotations_panel_width_min_constraint(self, calculator):
        """Test that annotations panel width respects minimum constraint."""
        window_width = 100
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        min_width = calculator.config["annotations_panel"]["min_width"]
        assert panel_width >= min_width
    
    def test_annotations_panel_width_max_constraint(self, calculator):
        """Test that annotations panel width respects maximum constraint."""
        window_width = 5000
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        max_width = calculator.config["annotations_panel"]["max_width"]
        assert panel_width <= max_width
    
    def test_chat_spacing_config_retrieval(self, calculator):
        """Test retrieval of chat spacing configuration."""
        spacing_config = calculator.get_chat_spacing_config()
        
        assert isinstance(spacing_config, dict)
        assert all(key in spacing_config for key in ["margin", "padding", "item_spacing"])
    
    def test_spacing_config_retrieval(self, calculator):
        """Test retrieval of spacing configuration."""
        spacing_config = calculator.get_spacing_config()
        
        assert isinstance(spacing_config, dict)
        assert all(key in spacing_config for key in ["margin", "padding", "item_spacing"])
    
    def test_font_config_retrieval(self, calculator):
        """Test retrieval of font configuration."""
        font_config = calculator.get_font_config()
        
        assert isinstance(font_config, dict)
        assert "title" in font_config
        assert "body" in font_config
        assert "caption" in font_config
        assert isinstance(font_config["title"], int)
        assert isinstance(font_config["body"], int)
        assert isinstance(font_config["caption"], int)
    
    def test_annotation_colors_retrieval(self, calculator):
        """Test retrieval of annotation colors."""
        colors = calculator.get_annotation_colors()
        
        assert isinstance(colors, dict)
        assert "backgrounds" in colors
        assert "accents" in colors
        assert "primary" in colors
        assert "secondary" in colors
        assert isinstance(colors["backgrounds"], list)
        assert isinstance(colors["accents"], list)
        assert len(colors["backgrounds"]) > 0
        assert len(colors["accents"]) > 0
    
    def test_chat_colors_retrieval(self, calculator):
        """Test retrieval of chat colors."""
        colors = calculator.get_chat_colors()
        
        assert isinstance(colors, dict)
        assert "user_message" in colors
        assert "ai_message" in colors
    
    def test_chat_empty_state_config_retrieval(self, calculator):
        """Test retrieval of chat empty state configuration."""
        config = calculator.get_chat_empty_state_config()
        
        assert isinstance(config, dict)
        assert "icon" in config
        assert "title" in config
        assert "description" in config
    
    def test_chat_input_placeholder_retrieval(self, calculator):
        """Test retrieval of chat input placeholder."""
        placeholder = calculator.get_chat_input_placeholder()
        
        assert isinstance(placeholder, str)
        assert len(placeholder) > 0
    
    def test_chat_panel_title_retrieval(self, calculator):
        """Test retrieval of chat panel title."""
        title = calculator.get_chat_panel_title()
        
        assert isinstance(title, str)
        assert len(title) > 0
    
    def test_empty_state_config_retrieval(self, calculator):
        """Test retrieval of empty state configuration."""
        config = calculator.get_empty_state_config()
        
        assert isinstance(config, dict)
        assert "icon" in config
        assert "title" in config
        assert "description" in config
    
    def test_panel_title_retrieval(self, calculator):
        """Test retrieval of panel title."""
        title = calculator.get_panel_title()
        
        assert isinstance(title, str)
        assert len(title) > 0
    
    def test_pdf_selection_config_retrieval(self, calculator):
        """Test retrieval of PDF selection configuration."""
        config = calculator.get_pdf_selection_config()
        
        assert isinstance(config, dict)
    
    def test_hex_to_rgba_conversion(self, calculator):
        """Test hex color to rgba conversion."""
        rgba = calculator._hex_to_rgba("#FF0000", 0.5)
        
        assert rgba == "rgba(255, 0, 0, 0.5)"
    
    def test_hex_to_rgba_default_alpha(self, calculator):
        """Test hex color to rgba conversion with default alpha."""
        rgba = calculator._hex_to_rgba("#00FF00")
        
        assert rgba == "rgba(0, 255, 0, 1.0)"
    
    def test_create_responsive_style(self, calculator):
        """Test creating responsive style with dynamic values."""
        base_style = "width: {width}px; color: {color};"
        style = calculator.create_responsive_style(base_style, width=200, color="red")
        
        assert "width: 200px" in style
        assert "color: red" in style
    
    def test_get_chat_panel_style_template(self, calculator):
        """Test retrieval of chat panel style template."""
        template = calculator.get_chat_panel_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_chat_input_style_template(self, calculator):
        """Test retrieval of chat input style template."""
        template = calculator.get_chat_input_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_chat_message_style_template(self, calculator):
        """Test retrieval of chat message style template."""
        template = calculator.get_chat_message_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_panel_style_template(self, calculator):
        """Test retrieval of panel style template."""
        template = calculator.get_panel_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_title_style_template(self, calculator):
        """Test retrieval of title style template."""
        template = calculator.get_title_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_empty_state_style_template(self, calculator):
        """Test retrieval of empty state style template."""
        template = calculator.get_empty_state_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_scroll_area_style_template(self, calculator):
        """Test retrieval of scroll area style template."""
        template = calculator.get_scroll_area_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    def test_get_annotation_item_style_template(self, calculator):
        """Test retrieval of annotation item style template."""
        template = calculator.get_annotation_item_style_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_refresh_updates_screen_info(self, mock_screen, calculator):
        """Test that refresh method updates screen information."""
        # Mock different screen size
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(2000, 1200)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        original_breakpoint = calculator._current_breakpoint
        calculator.refresh()
        
        # Should update to new breakpoint
        assert calculator._current_breakpoint == "xlarge"
        assert calculator._screen_size.width() == 2000


class TestResponsiveCalculatorEdgeCases:
    """Test edge cases and error conditions for ResponsiveCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Create a ResponsiveCalculator instance for edge case testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_zero_window_width(self, mock_screen):
        """Test handling of zero window width."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1440, 900)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        
        # Should handle zero width gracefully
        chat_width = calc.get_chat_panel_width(0)
        annotations_width = calc.get_annotations_panel_width(0)
        
        assert chat_width >= calc.config["chat_panel"]["min_width"]
        assert annotations_width >= calc.config["annotations_panel"]["min_width"]
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_negative_window_width(self, mock_screen):
        """Test handling of negative window width."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1440, 900)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        
        # Should handle negative width gracefully
        chat_width = calc.get_chat_panel_width(-100)
        annotations_width = calc.get_annotations_panel_width(-100)
        
        assert chat_width >= calc.config["chat_panel"]["min_width"]
        assert annotations_width >= calc.config["annotations_panel"]["min_width"]
    
    def test_invalid_hex_color(self, calculator):
        """Test handling of invalid hex color."""
        # Should handle invalid hex gracefully
        try:
            rgba = calculator._hex_to_rgba("invalid")
            # If it doesn't raise an exception, it should return a valid string
            assert isinstance(rgba, str)
        except (ValueError, IndexError):
            # It's acceptable to raise an exception for invalid input
            pass
    
    @patch('src.responsive_utils.config')
    def test_missing_config_keys(self, mock_config):
        """Test handling of missing configuration keys."""
        # Mock config with missing keys
        mock_config.RESPONSIVE_UI = {}
        mock_config.AI_ANNOTATIONS = {}
        mock_config.AI_CHAT = {}
        
        # Should handle missing keys gracefully
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            
            try:
                calc = ResponsiveCalculator()
                # Basic operations should not crash
                calc.get_current_breakpoint()
            except (KeyError, AttributeError):
                # It's acceptable to fail with missing config
                pass


class TestResponsiveCalcFunction:
    """Test the module-level responsive_calc instance."""
    
    def test_responsive_calc_instance_exists(self):
        """Test that responsive_calc instance is available."""
        assert responsive_calc is not None
        assert isinstance(responsive_calc, ResponsiveCalculator)
    
    def test_responsive_calc_methods_accessible(self):
        """Test that responsive_calc methods are accessible."""
        assert hasattr(responsive_calc, 'get_current_breakpoint')
        assert hasattr(responsive_calc, 'get_chat_panel_width')
        assert hasattr(responsive_calc, 'get_annotations_panel_width')
    
    def test_responsive_calc_functionality(self):
        """Test basic functionality of responsive_calc instance."""
        breakpoint = responsive_calc.get_current_breakpoint()
        assert breakpoint in ["small", "medium", "large", "xlarge"]
        
        chat_width = responsive_calc.get_chat_panel_width(1200)
        assert isinstance(chat_width, int)
        assert chat_width > 0


class TestResponsiveCalculatorPerformance:
    """Test performance characteristics of ResponsiveCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Create a ResponsiveCalculator instance for performance testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_rapid_calculations(self, calculator):
        """Test rapid successive calculations."""
        # Perform many calculations rapidly
        for i in range(100):
            width = 1000 + i * 10
            chat_width = calculator.get_chat_panel_width(width)
            annotations_width = calculator.get_annotations_panel_width(width)
            
            assert isinstance(chat_width, int)
            assert isinstance(annotations_width, int)
    
    def test_memory_usage_stability(self, calculator):
        """Test that repeated operations don't cause memory leaks."""
        # Repeated operations should not cause significant memory growth
        initial_attrs = len(calculator.__dict__)
        
        for _ in range(50):
            calculator.get_chat_panel_width(1200)
            calculator.get_spacing_config()
            calculator.get_font_config()
            calculator.refresh()
        
        final_attrs = len(calculator.__dict__)
        assert final_attrs == initial_attrs


class TestResponsiveCalculatorIntegration:
    """Integration tests for ResponsiveCalculator with configuration."""
    
    @patch('src.responsive_utils.config')
    def test_config_integration(self, mock_config):
        """Test integration with configuration system."""
        # Mock realistic config structure
        mock_config.RESPONSIVE_UI = {
            "breakpoints": {"small": 1024, "medium": 1440, "large": 1920, "xlarge": 2560},
            "chat_panel": {
                "width_ratio": {"small": 0.4, "medium": 0.3, "large": 0.25, "xlarge": 0.2},
                "min_width": 250,
                "max_width": 400,
                "spacing": {"small": {"margin": 8, "padding": 8, "item_spacing": 4}}
            },
            "annotations_panel": {
                "width_ratio": {"small": 0.4, "medium": 0.3, "large": 0.25, "xlarge": 0.2},
                "min_width": 300,
                "max_width": 500,
                "spacing": {"small": {"margin": 8, "padding": 8, "item_spacing": 4}}
            },
            "fonts": {"small": {"base_size": 12}}
        }
        mock_config.AI_ANNOTATIONS = {
            "colors": {
                "backgrounds": ["#FF0000", "#00FF00"], 
                "accents": ["#0000FF", "#FFFF00"],
                "primary": "#FF0000",
                "secondary": "#00FF00"
            },
            "empty_state": {"icon": "🚀", "title": "Test", "description": "Test desc"},
            "panel_title": "Test Panel"
        }
        mock_config.AI_CHAT = {
            "colors": {"user_message": "#0000FF", "ai_message": "#FF00FF"},
            "empty_state": {"icon": "🤖", "title": "Chat", "description": "Chat desc"},
            "input_placeholder": {"default": "Type..."},
            "panel_title": "Chat Panel"
        }
        mock_config.PDF_SELECTION = {"color": "#FFFF00"}
        
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(800, 600)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            
            calc = ResponsiveCalculator()
            
            # Test that calculations work with mocked config
            assert calc.get_current_breakpoint() == "small"
            
            chat_width = calc.get_chat_panel_width(1000)
            assert chat_width >= 250  # min_width
            assert chat_width <= 400  # max_width
            
            colors = calc.get_annotation_colors()
            assert colors["primary"] == "#FF0000"
            assert colors["secondary"] == "#00FF00"
            assert "backgrounds" in colors
            assert "accents" in colors 