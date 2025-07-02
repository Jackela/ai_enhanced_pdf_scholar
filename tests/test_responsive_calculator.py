"""
Core tests for responsive_utils module.
Tests the essential calculation logic of ResponsiveCalculator class.
"""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from src.responsive_utils import ResponsiveCalculator, responsive_calc


class TestResponsiveCalculator:
    """Test core functionality of ResponsiveCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Create a ResponsiveCalculator instance for testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_initialization(self, calculator):
        """Test proper initialization."""
        assert calculator.config is not None
        assert calculator.annotations_config is not None
        assert calculator.chat_config is not None
        assert calculator._current_breakpoint is not None
        assert calculator._screen_size is not None
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_small_screen_breakpoint(self, mock_screen):
        """Test small screen breakpoint detection."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(800, 600)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "small"
        assert calc._screen_size.width() == 800
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_medium_screen_breakpoint(self, mock_screen):
        """Test medium screen breakpoint detection."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1200, 800)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_large_screen_breakpoint(self, mock_screen):
        """Test large screen breakpoint detection."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1600, 1000)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "large"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_xlarge_screen_breakpoint(self, mock_screen):
        """Test extra large screen breakpoint detection."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(2560, 1440)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "xlarge"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_fallback_no_screen(self, mock_screen):
        """Test fallback when no screen available."""
        mock_screen.return_value = None
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
        assert calc._screen_size.width() == 1440
        assert calc._screen_size.height() == 900
    
    def test_get_current_breakpoint(self, calculator):
        """Test getting current breakpoint."""
        breakpoint = calculator.get_current_breakpoint()
        assert breakpoint in ["small", "medium", "large", "xlarge"]
    
    def test_chat_panel_width_calculation(self, calculator):
        """Test chat panel width calculation."""
        window_width = 1200
        panel_width = calculator.get_chat_panel_width(window_width)
        
        assert isinstance(panel_width, int)
        assert panel_width > 0
        assert panel_width <= window_width
    
    def test_chat_panel_width_min_constraint(self, calculator):
        """Test chat panel minimum width constraint."""
        window_width = 100  # Very small
        panel_width = calculator.get_chat_panel_width(window_width)
        
        min_width = calculator.config["chat_panel"]["min_width"]
        assert panel_width >= min_width
    
    def test_chat_panel_width_max_constraint(self, calculator):
        """Test chat panel maximum width constraint."""
        window_width = 5000  # Very large
        panel_width = calculator.get_chat_panel_width(window_width)
        
        max_width = calculator.config["chat_panel"]["max_width"]
        assert panel_width <= max_width
    
    def test_annotations_panel_width_calculation(self, calculator):
        """Test annotations panel width calculation."""
        window_width = 1200
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        assert isinstance(panel_width, int)
        assert panel_width > 0
        assert panel_width <= window_width
    
    def test_annotations_panel_width_min_constraint(self, calculator):
        """Test annotations panel minimum width constraint."""
        window_width = 100
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        min_width = calculator.config["annotations_panel"]["min_width"]
        assert panel_width >= min_width
    
    def test_annotations_panel_width_max_constraint(self, calculator):
        """Test annotations panel maximum width constraint."""
        window_width = 5000
        panel_width = calculator.get_annotations_panel_width(window_width)
        
        max_width = calculator.config["annotations_panel"]["max_width"]
        assert panel_width <= max_width
    
    def test_chat_spacing_config(self, calculator):
        """Test chat spacing configuration retrieval."""
        config = calculator.get_chat_spacing_config()
        
        assert isinstance(config, dict)
        required_keys = ["margin", "padding", "item_spacing"]
        assert all(key in config for key in required_keys)
    
    def test_spacing_config(self, calculator):
        """Test spacing configuration retrieval."""
        config = calculator.get_spacing_config()
        
        assert isinstance(config, dict)
        required_keys = ["margin", "padding", "item_spacing"]
        assert all(key in config for key in required_keys)
    
    def test_font_config(self, calculator):
        """Test font configuration retrieval."""
        config = calculator.get_font_config()
        
        assert isinstance(config, dict)
        assert "base_size" in config
    
    def test_annotation_colors(self, calculator):
        """Test annotation colors retrieval."""
        colors = calculator.get_annotation_colors()
        
        assert isinstance(colors, dict)
        assert "user_selection" in colors
        assert "ai_response" in colors
    
    def test_chat_colors(self, calculator):
        """Test chat colors retrieval."""
        colors = calculator.get_chat_colors()
        
        assert isinstance(colors, dict)
        assert "user_message" in colors
        assert "ai_message" in colors
    
    def test_chat_empty_state_config(self, calculator):
        """Test chat empty state configuration."""
        config = calculator.get_chat_empty_state_config()
        
        assert isinstance(config, dict)
        assert "icon" in config
        assert "title" in config
        assert "description" in config
    
    def test_chat_input_placeholder(self, calculator):
        """Test chat input placeholder retrieval."""
        placeholder = calculator.get_chat_input_placeholder()
        
        assert isinstance(placeholder, str)
        assert len(placeholder) > 0
    
    def test_chat_panel_title(self, calculator):
        """Test chat panel title retrieval."""
        title = calculator.get_chat_panel_title()
        
        assert isinstance(title, str)
        assert len(title) > 0
    
    def test_empty_state_config(self, calculator):
        """Test empty state configuration."""
        config = calculator.get_empty_state_config()
        
        assert isinstance(config, dict)
        assert "icon" in config
        assert "title" in config
        assert "description" in config
    
    def test_panel_title(self, calculator):
        """Test panel title retrieval."""
        title = calculator.get_panel_title()
        
        assert isinstance(title, str)
        assert len(title) > 0
    
    def test_pdf_selection_config(self, calculator):
        """Test PDF selection configuration."""
        config = calculator.get_pdf_selection_config()
        assert isinstance(config, dict)
    
    def test_hex_to_rgba_conversion(self, calculator):
        """Test hex to RGBA conversion."""
        rgba = calculator._hex_to_rgba("#FF0000", 0.5)
        assert rgba == "rgba(255, 0, 0, 0.5)"
    
    def test_hex_to_rgba_default_alpha(self, calculator):
        """Test hex to RGBA with default alpha."""
        rgba = calculator._hex_to_rgba("#00FF00")
        assert rgba == "rgba(0, 255, 0, 1.0)"
    
    def test_create_responsive_style(self, calculator):
        """Test responsive style creation."""
        base_style = "width: {width}px; color: {color};"
        style = calculator.create_responsive_style(base_style, width=200, color="red")
        
        assert "width: 200px" in style
        assert "color: red" in style
    
    def test_style_templates_exist(self, calculator):
        """Test that all style templates exist and return strings."""
        templates = [
            calculator.get_chat_panel_style_template(),
            calculator.get_chat_input_style_template(),
            calculator.get_chat_message_style_template(),
            calculator.get_panel_style_template(),
            calculator.get_title_style_template(),
            calculator.get_empty_state_style_template(),
            calculator.get_scroll_area_style_template(),
            calculator.get_annotation_item_style_template()
        ]
        
        for template in templates:
            assert isinstance(template, str)
            assert len(template) > 0
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_refresh_updates_screen_info(self, mock_screen, calculator):
        """Test refresh updates screen information."""
        # Mock new screen size
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(2000, 1200)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calculator.refresh()
        
        assert calculator._current_breakpoint == "xlarge"
        assert calculator._screen_size.width() == 2000


class TestResponsiveCalculatorEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_zero_window_width(self, mock_screen):
        """Test handling of zero window width."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1440, 900)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        
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
        
        chat_width = calc.get_chat_panel_width(-100)
        annotations_width = calc.get_annotations_panel_width(-100)
        
        assert chat_width >= calc.config["chat_panel"]["min_width"]
        assert annotations_width >= calc.config["annotations_panel"]["min_width"]
    
    def test_invalid_hex_color_handling(self, calculator):
        """Test handling of invalid hex color."""
        try:
            rgba = calculator._hex_to_rgba("invalid")
            assert isinstance(rgba, str)
        except (ValueError, IndexError):
            # Acceptable to raise exception for invalid input
            pass


class TestResponsiveCalcGlobalInstance:
    """Test the global responsive_calc instance."""
    
    def test_instance_exists(self):
        """Test global instance exists."""
        assert responsive_calc is not None
        assert isinstance(responsive_calc, ResponsiveCalculator)
    
    def test_instance_methods_work(self):
        """Test global instance methods work."""
        breakpoint = responsive_calc.get_current_breakpoint()
        assert breakpoint in ["small", "medium", "large", "xlarge"]
        
        chat_width = responsive_calc.get_chat_panel_width(1200)
        assert isinstance(chat_width, int)
        assert chat_width > 0


class TestResponsiveCalculatorPerformance:
    """Test performance characteristics."""
    
    def test_rapid_calculations(self, calculator):
        """Test rapid successive calculations."""
        for i in range(50):
            width = 1000 + i * 10
            chat_width = calculator.get_chat_panel_width(width)
            annotations_width = calculator.get_annotations_panel_width(width)
            
            assert isinstance(chat_width, int)
            assert isinstance(annotations_width, int)
    
    def test_memory_stability(self, calculator):
        """Test memory usage remains stable."""
        initial_attrs = len(calculator.__dict__)
        
        for _ in range(25):
            calculator.get_chat_panel_width(1200)
            calculator.get_spacing_config()
            calculator.get_font_config()
            calculator.refresh()
        
        final_attrs = len(calculator.__dict__)
        assert final_attrs == initial_attrs


class TestResponsiveCalculatorWidthCalculations:
    """Test specific width calculation logic."""
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_width_calculation_consistency(self, mock_screen):
        """Test width calculations are consistent."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1440, 900)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        window_width = 1200
        
        # Multiple calls should return same result
        width1 = calc.get_chat_panel_width(window_width)
        width2 = calc.get_chat_panel_width(window_width)
        
        assert width1 == width2
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_width_scales_with_window(self, mock_screen):
        """Test that panel width scales appropriately with window size."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1440, 900)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        
        small_window = calc.get_chat_panel_width(800)
        large_window = calc.get_chat_panel_width(1600)
        
        # Larger window should generally have larger panel (unless constrained)
        max_width = calc.config["chat_panel"]["max_width"]
        if large_window < max_width:
            assert large_window >= small_window
    
    def test_ratio_based_calculation(self, calculator):
        """Test that width calculation uses ratio correctly."""
        window_width = 1000
        panel_width = calculator.get_chat_panel_width(window_width)
        
        # Should be based on ratio from config
        current_breakpoint = calculator.get_current_breakpoint()
        ratio = calculator.config["chat_panel"]["width_ratio"][current_breakpoint]
        expected_width = int(window_width * ratio)
        
        # Account for min/max constraints
        min_width = calculator.config["chat_panel"]["min_width"]
        max_width = calculator.config["chat_panel"]["max_width"]
        expected_constrained = max(min_width, min(max_width, expected_width))
        
        assert panel_width == expected_constrained 