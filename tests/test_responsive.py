"""
Tests for responsive_utils module - core calculation functionality.
"""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QSize

from src.responsive_utils import ResponsiveCalculator, responsive_calc


class TestResponsiveCalculator:
    """Test core ResponsiveCalculator functionality."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator with mocked screen."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_initialization(self, calculator):
        """Test proper initialization."""
        assert calculator.config is not None
        assert calculator._current_breakpoint is not None
        assert calculator._screen_size is not None
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_breakpoint_detection_small(self, mock_screen):
        """Test small screen breakpoint."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(800, 600)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "small"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_breakpoint_detection_medium(self, mock_screen):
        """Test medium screen breakpoint."""
        mock_geometry = Mock()
        mock_geometry.size.return_value = QSize(1200, 800)
        mock_screen.return_value.availableGeometry.return_value = mock_geometry
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
    
    @patch('src.responsive_utils.QApplication.primaryScreen')
    def test_no_screen_fallback(self, mock_screen):
        """Test fallback when no screen."""
        mock_screen.return_value = None
        
        calc = ResponsiveCalculator()
        assert calc._current_breakpoint == "medium"
        assert calc._screen_size.width() == 1440
    
    def test_chat_panel_width_basic(self, calculator):
        """Test basic chat panel width calculation."""
        width = calculator.get_chat_panel_width(1200)
        
        assert isinstance(width, int)
        assert width > 0
        assert width <= 1200
    
    def test_chat_panel_width_min_constraint(self, calculator):
        """Test minimum width constraint."""
        width = calculator.get_chat_panel_width(100)
        min_width = calculator.config["chat_panel"]["min_width"]
        assert width >= min_width
    
    def test_chat_panel_width_max_constraint(self, calculator):
        """Test maximum width constraint."""
        width = calculator.get_chat_panel_width(5000)
        max_width = calculator.config["chat_panel"]["max_width"]
        assert width <= max_width
    
    def test_annotations_panel_width_basic(self, calculator):
        """Test basic annotations panel width calculation."""
        width = calculator.get_annotations_panel_width(1200)
        
        assert isinstance(width, int)
        assert width > 0
        assert width <= 1200
    
    def test_spacing_config_retrieval(self, calculator):
        """Test spacing configuration retrieval."""
        config = calculator.get_spacing_config()
        
        assert isinstance(config, dict)
        assert "margin" in config
        assert "padding" in config
        assert "item_spacing" in config
    
    def test_font_config_retrieval(self, calculator):
        """Test font configuration retrieval."""
        config = calculator.get_font_config()
        
        assert isinstance(config, dict)
        # Check for any valid font keys (actual keys: body, caption, title)
        assert any(key in config for key in ["body", "caption", "title", "base_size"])
    
    def test_colors_retrieval(self, calculator):
        """Test color configuration retrieval."""
        annotation_colors = calculator.get_annotation_colors()
        chat_colors = calculator.get_chat_colors()
        
        assert isinstance(annotation_colors, dict)
        assert isinstance(chat_colors, dict)
        # Check for actual keys that exist
        assert any(key in annotation_colors for key in ["backgrounds", "accents", "primary"])
        assert any(key in chat_colors for key in ["user_message", "ai_message", "backgrounds"])
    
    def test_empty_state_config(self, calculator):
        """Test empty state configuration."""
        config = calculator.get_empty_state_config()
        
        assert isinstance(config, dict)
        assert "icon" in config
        assert "title" in config
        assert "description" in config
    
    def test_hex_to_rgba_conversion(self, calculator):
        """Test hex color conversion."""
        rgba = calculator._hex_to_rgba("#FF0000", 0.5)
        assert rgba == "rgba(255, 0, 0, 0.5)"
        
        rgba_default = calculator._hex_to_rgba("#00FF00")
        assert rgba_default == "rgba(0, 255, 0, 1.0)"
    
    def test_responsive_style_creation(self, calculator):
        """Test responsive style creation."""
        base_style = "width: {width}px; color: {color};"
        style = calculator.create_responsive_style(base_style, width=200, color="red")
        
        assert "width: 200px" in style
        assert "color: red" in style
    
    def test_style_templates_return_strings(self, calculator):
        """Test all style templates return valid strings."""
        templates = [
            calculator.get_panel_style_template(),
            calculator.get_title_style_template(),
            calculator.get_empty_state_style_template(),
            calculator.get_scroll_area_style_template()
        ]
        
        for template in templates:
            assert isinstance(template, str)
            assert len(template) > 0


class TestResponsiveCalculatorEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator for edge case testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_zero_window_width(self, calculator):
        """Test zero window width handling."""
        chat_width = calculator.get_chat_panel_width(0)
        annotations_width = calculator.get_annotations_panel_width(0)
        
        assert chat_width >= calculator.config["chat_panel"]["min_width"]
        assert annotations_width >= calculator.config["annotations_panel"]["min_width"]
    
    def test_negative_window_width(self, calculator):
        """Test negative window width handling."""
        chat_width = calculator.get_chat_panel_width(-100)
        annotations_width = calculator.get_annotations_panel_width(-100)
        
        assert chat_width >= calculator.config["chat_panel"]["min_width"]
        assert annotations_width >= calculator.config["annotations_panel"]["min_width"]


class TestGlobalResponsiveCalcInstance:
    """Test the global responsive_calc instance."""
    
    def test_instance_exists(self):
        """Test global instance exists and works."""
        assert responsive_calc is not None
        assert isinstance(responsive_calc, ResponsiveCalculator)
    
    def test_instance_functionality(self):
        """Test global instance basic functionality."""
        breakpoint = responsive_calc.get_current_breakpoint()
        assert breakpoint in ["small", "medium", "large", "xlarge"]
        
        width = responsive_calc.get_chat_panel_width(1200)
        assert isinstance(width, int)
        assert width > 0


class TestResponsiveCalculatorConsistency:
    """Test calculation consistency and reliability."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator for consistency testing."""
        with patch('src.responsive_utils.QApplication.primaryScreen') as mock_screen:
            mock_geometry = Mock()
            mock_geometry.size.return_value = QSize(1440, 900)
            mock_screen.return_value.availableGeometry.return_value = mock_geometry
            return ResponsiveCalculator()
    
    def test_calculation_consistency(self, calculator):
        """Test calculations are consistent."""
        window_width = 1200
        
        # Multiple calls should return same result
        width1 = calculator.get_chat_panel_width(window_width)
        width2 = calculator.get_chat_panel_width(window_width)
        
        assert width1 == width2
    
    def test_rapid_calculations_stability(self, calculator):
        """Test rapid calculations don't cause issues."""
        for i in range(50):
            width = 1000 + i * 10
            chat_width = calculator.get_chat_panel_width(width)
            annotations_width = calculator.get_annotations_panel_width(width)
            
            assert isinstance(chat_width, int)
            assert isinstance(annotations_width, int)
            assert chat_width > 0
            assert annotations_width > 0 