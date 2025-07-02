"""
Core tests for annotation module components.
Tests the essential functionality of StickyNoteAnnotation and PanelAnnotation.
"""

import pytest
from unittest.mock import patch
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QRect, QSize

from src.annotation import StickyNoteAnnotation, PanelAnnotation


class TestStickyNoteAnnotation:
    """Test core functionality of StickyNoteAnnotation."""
    
    @pytest.fixture
    def mock_parent(self, qtbot):
        """Create a mock parent widget."""
        parent = QWidget()
        qtbot.addWidget(parent)
        return parent
    
    @pytest.fixture
    def sticky_note(self, qtbot, mock_parent):
        """Create a StickyNoteAnnotation for testing."""
        annotation = StickyNoteAnnotation(
            mock_parent,
            QRect(10, 10, 100, 50),
            "Test annotation text",
            1,
            {'x': 100, 'y': 200, 'page': 1}
        )
        qtbot.addWidget(annotation)
        return annotation
    
    def test_initialization(self, sticky_note):
        """Test proper initialization."""
        assert sticky_note.text == "Test annotation text"
        assert sticky_note.page_number == 1
        assert sticky_note.expanded is False
        assert sticky_note.hover_expanded is False
    
    def test_ui_components_exist(self, sticky_note):
        """Test that UI components are created."""
        assert sticky_note.header_widget is not None
        assert sticky_note.toggle_button is not None
        assert sticky_note.delete_button is not None
        assert sticky_note.preview_label is not None
        # Content area exists
        assert sticky_note.content_text is not None
        # Initially hidden
        assert sticky_note.content_text.isHidden() is True
    
    def test_initial_size(self, sticky_note):
        """Test initial collapsed size."""
        expected_size = QSize(sticky_note.collapsed_width, sticky_note.collapsed_height)
        assert sticky_note.size() == expected_size
    
    def test_toggle_expansion_signal(self, sticky_note, qtbot):
        """Test expansion toggle emits signal."""
        with qtbot.waitSignal(sticky_note.expansion_changed, timeout=1000):
            sticky_note.toggle_expansion()
        assert sticky_note.expanded is True
    
    def test_delete_signal(self, sticky_note, qtbot):
        """Test delete button emits signal."""
        with qtbot.waitSignal(sticky_note.delete_requested, timeout=1000):
            sticky_note.delete_button.click()
    
    def test_color_assignment(self, sticky_note):
        """Test color is assigned."""
        assert isinstance(sticky_note.current_color, str)
        assert sticky_note.current_color.startswith('#')
    
    def test_content_readonly(self, sticky_note):
        """Test content text is read-only."""
        assert sticky_note.content_text.isReadOnly() is True
    
    def test_mouse_tracking(self, sticky_note):
        """Test mouse tracking is enabled."""
        assert sticky_note.hasMouseTracking() is True


class TestPanelAnnotation:
    """Test core functionality of PanelAnnotation."""
    
    @pytest.fixture
    def panel_annotation(self, qtbot):
        """Create a PanelAnnotation for testing."""
        annotation = PanelAnnotation(
            "**Test AI response** with markdown",
            2,
            {'x': 150, 'y': 300, 'page': 2},
            "Selected text portion"
        )
        qtbot.addWidget(annotation)
        return annotation
    
    def test_initialization(self, panel_annotation):
        """Test proper initialization."""
        assert panel_annotation.text == "**Test AI response** with markdown"
        assert panel_annotation.page_number == 2
        assert panel_annotation.selected_text == "Selected text portion"
        assert panel_annotation.expanded is True
    
    def test_ui_components_exist(self, panel_annotation):
        """Test UI components are created."""
        assert hasattr(panel_annotation, 'page_label')
        # preview_label may be None if no selected text
        assert hasattr(panel_annotation, 'content_browser')
        assert hasattr(panel_annotation, 'toggle_button')
        assert hasattr(panel_annotation, 'delete_button')
    
    def test_page_label_content(self, panel_annotation):
        """Test page label shows correct page."""
        assert panel_annotation.page_label.text() == "📄 Page 3"
    
    def test_preview_text_truncation(self, qtbot):
        """Test long preview text is truncated."""
        long_text = "A" * 100
        annotation = PanelAnnotation("AI response", 1, {}, long_text)
        qtbot.addWidget(annotation)
        if annotation.preview_label:
            preview = annotation.preview_label.text()
            assert '"' in preview
            assert len(preview) <= 60
    
    def test_no_preview_empty_selected(self, qtbot):
        """Test no preview when no selected text."""
        annotation = PanelAnnotation("AI response", 1, {}, "")
        qtbot.addWidget(annotation)
        assert annotation.preview_label is None
    
    def test_content_readonly(self, panel_annotation):
        """Test content browser is read-only."""
        assert panel_annotation.content_browser.isReadOnly() is True
    
    def test_toggle_expansion(self, panel_annotation):
        """Test toggle expansion changes state."""
        initial_state = panel_annotation.expanded
        panel_annotation.toggle_expansion()
        assert panel_annotation.expanded != initial_state
    
    def test_delete_signal(self, panel_annotation, qtbot):
        """Test delete button emits signal."""
        with qtbot.waitSignal(panel_annotation.delete_requested, timeout=1000):
            panel_annotation.delete_button.click()
    
    def test_color_assignment(self, panel_annotation):
        """Test color is assigned."""
        assert hasattr(panel_annotation, 'current_color')
        assert panel_annotation.current_color.startswith('#')
    
    def test_max_height_constraint(self, panel_annotation):
        """Test content browser has max height."""
        assert panel_annotation.content_browser.maximumHeight() > 0
    
    def test_markdown_renderer_exists(self, panel_annotation):
        """Test markdown renderer is created."""
        assert hasattr(panel_annotation, 'markdown_renderer')
        assert panel_annotation.markdown_renderer is not None 