import pytest
from unittest.mock import Mock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
import fitz
import markdown

from src.annotation import PanelAnnotation


class TestPanelAnnotation:
    """Test suite for the PanelAnnotation class."""

    @pytest.fixture
    def sample_annotation(self, qtbot):
        """Create a sample PanelAnnotation for testing."""
        text = "This is a test AI response about the selected content."
        page_number = 0
        pdf_coords = fitz.Rect(100, 100, 200, 150)
        selected_text = "This is the selected text from the PDF document."
        
        annotation = PanelAnnotation(
            text=text,
            page_number=page_number,
            pdf_coords=pdf_coords,
            selected_text=selected_text
        )
        qtbot.addWidget(annotation)
        return annotation

    def test_initialization(self, sample_annotation):
        """Test that PanelAnnotation initializes correctly."""
        assert sample_annotation.text == "This is a test AI response about the selected content."
        assert sample_annotation.page_number == 0
        assert sample_annotation.selected_text == "This is the selected text from the PDF document."
        assert sample_annotation.expanded is False  # Should start collapsed

    def test_ui_components_creation(self, sample_annotation):
        """Test that all UI components are created properly."""
        # Check header components
        assert sample_annotation.page_label is not None
        assert sample_annotation.toggle_button is not None
        assert sample_annotation.delete_button is not None
        
        # Check content components
        assert sample_annotation.content_text is not None
        assert sample_annotation.preview_label is not None
        
        # Check initial states
        assert sample_annotation.content_text.isHidden()  # Should start collapsed
        assert sample_annotation.toggle_button.text() == "💭"  # Collapsed icon

    def test_page_label_content(self, sample_annotation):
        """Test the page label shows correct page number."""
        expected_text = "📄 Page 1"  # Page number is 0-indexed, display is 1-indexed
        assert sample_annotation.page_label.text() == expected_text

    def test_preview_text_truncation(self, qtbot):
        """Test that long selected text is properly truncated in preview."""
        long_text = "This is a very long selected text that should be truncated " * 5
        annotation = PanelAnnotation(
            text="AI response",
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            selected_text=long_text
        )
        qtbot.addWidget(annotation)
        
        preview_text = annotation.preview_label.text()
        assert "..." in preview_text
        assert len(preview_text) <= 70  # 60 chars + quotes + ellipsis

    def test_no_preview_when_no_selected_text(self, qtbot):
        """Test that no preview is shown when selected_text is empty."""
        annotation = PanelAnnotation(
            text="AI response",
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            selected_text=""
        )
        qtbot.addWidget(annotation)
        
        assert annotation.preview_label is None

    def test_toggle_expansion(self, sample_annotation, qtbot):
        """Test the expansion toggle functionality."""
        # Initially collapsed
        assert sample_annotation.expanded is False
        assert sample_annotation.content_text.isHidden()
        assert sample_annotation.toggle_button.text() == "💭"
        
        # Click to expand
        qtbot.mouseClick(sample_annotation.toggle_button, Qt.MouseButton.LeftButton)
        
        # Should now be expanded
        assert sample_annotation.expanded is True
        # Note: In test environment, widget visibility behavior may differ
        # Check the internal state rather than isVisible()
        assert not sample_annotation.content_text.isHidden()
        assert sample_annotation.toggle_button.text() == "📖"
        
        # Click to collapse
        qtbot.mouseClick(sample_annotation.toggle_button, Qt.MouseButton.LeftButton)
        
        # Should be collapsed again
        assert sample_annotation.expanded is False
        assert sample_annotation.content_text.isHidden()
        assert sample_annotation.toggle_button.text() == "💭"

    def test_delete_signal_emission(self, sample_annotation, qtbot):
        """Test that delete signal is emitted when delete button is clicked."""
        # Connect a mock slot to the delete signal
        mock_slot = Mock()
        sample_annotation.delete_requested.connect(mock_slot)
        
        # Click delete button
        qtbot.mouseClick(sample_annotation.delete_button, Qt.MouseButton.LeftButton)
        
        # Check that signal was emitted with the annotation itself
        mock_slot.assert_called_once_with(sample_annotation)

    def test_content_text_readonly(self, sample_annotation):
        """Test that the content text is read-only."""
        assert sample_annotation.content_text.isReadOnly() is True

    def test_content_text_content(self, sample_annotation):
        """Test that the content text displays the AI response."""
        expected_text = "This is a test AI response about the selected content."
        assert sample_annotation.content_text.toPlainText() == expected_text

    def test_color_assignment(self, qtbot):
        """Test that annotations get consistent colors based on text hash."""
        text1 = "First annotation text"
        text2 = "Second annotation text"
        
        annotation1 = PanelAnnotation(text1, 0, fitz.Rect(0, 0, 100, 100))
        annotation2 = PanelAnnotation(text2, 0, fitz.Rect(0, 0, 100, 100))
        annotation3 = PanelAnnotation(text1, 1, fitz.Rect(0, 0, 100, 100))  # Same text, different page
        
        qtbot.addWidget(annotation1)
        qtbot.addWidget(annotation2)
        qtbot.addWidget(annotation3)
        
        # Same text should give same color
        assert annotation1.current_color == annotation3.current_color
        
        # Different text will likely give different color (though not guaranteed due to hash collisions)
        # At least check that a color was assigned
        assert annotation1.current_color in annotation1.colors
        assert annotation2.current_color in annotation2.colors

    def test_tooltip_text(self, sample_annotation):
        """Test that buttons have appropriate tooltips."""
        assert "Expand/Collapse" in sample_annotation.toggle_button.toolTip()
        assert "Delete" in sample_annotation.delete_button.toolTip()

    def test_max_height_constraint(self, sample_annotation):
        """Test that content text has a maximum height to fit in panel."""
        assert sample_annotation.content_text.maximumHeight() == 200

    def test_annotation_with_special_characters(self, qtbot):
        """Test handling of special characters in text content."""
        special_text = "Text with émojis 🚀, 中文, and symbols: @#$%^&*()"
        selected_special = "Special chars: ñáéíóú"
        
        annotation = PanelAnnotation(
            text=special_text,
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            selected_text=selected_special
        )
        qtbot.addWidget(annotation)
        
        assert annotation.content_text.toPlainText() == special_text
        assert selected_special in annotation.preview_label.text()

    def test_button_size_constraints(self, sample_annotation):
        """Test that buttons have fixed sizes for consistent layout."""
        assert sample_annotation.toggle_button.size().width() == 24
        assert sample_annotation.toggle_button.size().height() == 24
        assert sample_annotation.delete_button.size().width() == 24
        assert sample_annotation.delete_button.size().height() == 24


class TestPanelAnnotationIntegration:
    """Integration tests for PanelAnnotation."""

    def test_multiple_annotations_layout(self, qtbot):
        """Test that multiple annotations can be created and displayed."""
        annotations = []
        
        for i in range(3):
            annotation = PanelAnnotation(
                text=f"AI response {i}",
                page_number=i,
                pdf_coords=fitz.Rect(0, 0, 100, 100),
                selected_text=f"Selected text {i}"
            )
            qtbot.addWidget(annotation)
            annotations.append(annotation)
        
        # All annotations should be created successfully
        assert len(annotations) == 3
        
        # Each should have unique content
        for i, annotation in enumerate(annotations):
            assert f"AI response {i}" in annotation.content_text.toPlainText()
            assert f"Page {i + 1}" in annotation.page_label.text()

    def test_styling_application(self, qtbot):
        """Test that styling is applied to the annotation."""
        # Create annotation specifically for this test
        annotation = PanelAnnotation(
            text="Test styling",
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            selected_text="Test text"
        )
        qtbot.addWidget(annotation)
        
        # Check that the annotation has a background color
        style = annotation.styleSheet()
        assert "background-color" in style
        assert "border-radius" in style
        
        # Check that color is from the predefined palette
        assert annotation.current_color in annotation.colors 


class TestPanelAnnotationModernFeatures:
    """Test suite for the modernized PanelAnnotation component with Markdown support."""
    
    def test_initialization_with_markdown_renderer(self, qtbot):
        """Test that PanelAnnotation initializes with proper Markdown renderer."""
        text = "This is **bold** and *italic* text"
        annotation = PanelAnnotation(text, 0, (100, 100), "selected text")
        qtbot.addWidget(annotation)
        
        # Verify markdown renderer is initialized
        assert hasattr(annotation, 'markdown_renderer')
        assert isinstance(annotation.markdown_renderer, markdown.Markdown)
        
        # Verify extensions are properly configured
        assert 'extra' in annotation.markdown_renderer.treeprocessors
        assert 'codehilite' in annotation.markdown_renderer.treeprocessors

    def test_markdown_rendering_in_content(self, qtbot):
        """Test that Markdown content is properly rendered to HTML."""
        markdown_text = """
        # Header 1
        ## Header 2
        
        This is **bold** text and *italic* text.
        
        - List item 1
        - List item 2
        
        `inline code` and:
        
        ```python
        def hello():
            print("Hello World")
        ```
        
        > This is a blockquote
        """
        
        annotation = PanelAnnotation(markdown_text, 0, (100, 100), "sample")
        qtbot.addWidget(annotation)
        
        # Verify content browser contains HTML
        html_content = annotation.content_browser.toHtml()
        
        # Check for HTML elements that should be rendered from Markdown
        assert '<h1>' in html_content or '<h2>' in html_content
        assert '<strong>' in html_content  # Bold text
        assert '<em>' in html_content     # Italic text
        assert '<ul>' in html_content or '<li>' in html_content  # Lists
        assert '<code>' in html_content   # Inline code
        assert '<blockquote>' in html_content  # Blockquote

    def test_markdown_fallback_to_plain_text(self, qtbot):
        """Test fallback to plain text when Markdown rendering fails."""
        text = "Simple text without markdown"
        
        # Mock markdown conversion to raise an exception
        with patch.object(markdown.Markdown, 'convert', side_effect=Exception("Markdown error")):
            annotation = PanelAnnotation(text, 0, (100, 100), "selected")
            qtbot.addWidget(annotation)
            
            # Should fallback to plain text
            content = annotation.content_browser.toPlainText()
            assert text in content

    def test_minimal_selected_text_preview(self, qtbot):
        """Test that selected text preview is minimal (30 characters max)."""
        long_text = "This is a very long selected text that should be truncated"
        annotation = PanelAnnotation("AI response", 0, (100, 100), long_text)
        qtbot.addWidget(annotation)
        
        if annotation.preview_label:
            preview_text = annotation.preview_label.text()
            # Should be truncated to ~30 characters
            assert len(preview_text) <= 35  # Including quotes and ellipsis
            assert "..." in preview_text
            
            # Should be single line
            assert annotation.preview_label.maximumHeight() == 20

    def test_ai_content_area_sizing(self, qtbot):
        """Test that AI content area has proper sizing without restrictive limits."""
        text = "AI response content"
        annotation = PanelAnnotation(text, 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Should have reasonable minimum and maximum heights
        assert annotation.content_browser.minimumHeight() == 120
        assert annotation.content_browser.maximumHeight() == 400

    def test_modern_color_scheme(self, qtbot):
        """Test that modern Material Design color scheme is applied."""
        text = "Test content"
        annotation = PanelAnnotation(text, 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Verify color properties are set
        assert hasattr(annotation, 'current_color')
        assert hasattr(annotation, 'accent_color')
        
        # Colors should be from the modern palette
        modern_colors = [
            "#E3F2FD", "#F3E5F5", "#E8F5E8", "#FFF3E0",
            "#F9FBE7", "#FCE4EC", "#E0F2F1", "#FFF8E1"
        ]
        assert annotation.current_color in modern_colors

    def test_starts_expanded_by_default(self, qtbot):
        """Test that annotations start in expanded state to show AI content."""
        annotation = PanelAnnotation("AI response", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Should start expanded
        assert annotation.expanded is True
        assert annotation.content_browser.isVisible()
        assert annotation.toggle_button.text() == "📖"

    def test_toggle_expansion_functionality(self, qtbot):
        """Test the expand/collapse toggle functionality."""
        annotation = PanelAnnotation("AI response", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Initially expanded
        assert annotation.expanded is True
        assert annotation.content_browser.isVisible()
        
        # Toggle to collapse
        annotation.toggle_button.click()
        assert annotation.expanded is False
        assert not annotation.content_browser.isVisible()
        assert annotation.toggle_button.text() == "💭"
        
        # Toggle back to expand
        annotation.toggle_button.click()
        assert annotation.expanded is True
        assert annotation.content_browser.isVisible()
        assert annotation.toggle_button.text() == "📖"

    def test_delete_signal_emission(self, qtbot):
        """Test that delete button emits proper signal."""
        annotation = PanelAnnotation("AI response", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Connect signal to mock
        delete_mock = Mock()
        annotation.delete_requested.connect(delete_mock)
        
        # Click delete button
        annotation.delete_button.click()
        
        # Verify signal was emitted with annotation as argument
        delete_mock.assert_called_once_with(annotation)

    def test_modern_styling_application(self, qtbot):
        """Test that modern styling is properly applied."""
        annotation = PanelAnnotation("Test content", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Verify stylesheet contains modern elements
        stylesheet = annotation.styleSheet()
        assert "border-radius" in stylesheet  # Modern rounded corners
        assert "background-color" in stylesheet  # Color scheme
        
        # Verify shadow effect is applied
        assert annotation.graphicsEffect() is not None

    def test_html_content_wrapping(self, qtbot):
        """Test the HTML content wrapping with custom CSS."""
        text = "**Bold text** and `code`"
        annotation = PanelAnnotation(text, 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        html_content = annotation.content_browser.toHtml()
        
        # Should contain custom styling
        assert "font-family: 'Segoe UI'" in html_content
        assert "line-height: 1.4" in html_content
        assert annotation.accent_color in html_content  # Accent color in styles

    def test_page_label_modern_styling(self, qtbot):
        """Test that page label has modern styling."""
        annotation = PanelAnnotation("Test", 2, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Verify page label content and styling
        assert annotation.page_label.text() == "📄 Page 3"  # 0-indexed + 1
        
        # Verify modern styling is applied
        label_style = annotation.page_label.styleSheet()
        assert "font-weight: 600" in label_style
        assert "border-radius" in label_style

    def test_content_browser_properties(self, qtbot):
        """Test QTextBrowser specific properties."""
        annotation = PanelAnnotation("Test content", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Verify QTextBrowser properties
        assert annotation.content_browser.isReadOnly()
        assert annotation.content_browser.openExternalLinks()

    def test_no_selected_text_handling(self, qtbot):
        """Test proper handling when no selected text is provided."""
        annotation = PanelAnnotation("AI response", 0, (100, 100), "")
        qtbot.addWidget(annotation)
        
        # Should handle empty selected text gracefully
        assert annotation.preview_label is None
        assert annotation.content_browser.isVisible()  # AI content still shown

    def test_button_tooltip_updates(self, qtbot):
        """Test that button tooltips update correctly with state changes."""
        annotation = PanelAnnotation("Test", 0, (100, 100), "selected")
        qtbot.addWidget(annotation)
        
        # Initial tooltips
        assert "Collapse AI response" in annotation.toggle_button.toolTip()
        assert "Delete annotation" in annotation.delete_button.toolTip()
        
        # After toggling
        annotation.toggle_button.click()
        assert "Expand AI response" in annotation.toggle_button.toolTip()


class TestPanelAnnotationIntegration:
    """Integration tests for PanelAnnotation with real-world scenarios."""
    
    def test_complex_markdown_rendering(self, qtbot):
        """Test rendering of complex Markdown content."""
        complex_markdown = """
        # AI Analysis Results
        
        ## Summary
        This text discusses **machine learning** concepts.
        
        ### Key Points:
        1. *Neural networks* are powerful
        2. `Deep learning` requires data
        3. **Training** is computationally intensive
        
        ### Code Example:
        ```python
        import torch
        model = torch.nn.Linear(10, 1)
        ```
        
        > Important: Always validate your models!
        
        [Learn more](https://example.com)
        """
        
        annotation = PanelAnnotation(complex_markdown, 1, (100, 100), "ML text")
        qtbot.addWidget(annotation)
        
        html = annotation.content_browser.toHtml()
        
        # Verify complex elements are rendered
        assert '<h1>' in html  # Headers
        assert '<strong>' in html  # Bold
        assert '<em>' in html  # Italic  
        assert '<code>' in html  # Inline code
        assert '<pre>' in html  # Code blocks
        assert '<blockquote>' in html  # Quotes
        assert '<ol>' in html or '<ul>' in html  # Lists

    def test_responsive_layout_adaptation(self, qtbot):
        """Test that annotation adapts to different content sizes."""
        short_text = "Short"
        long_text = "This is a very long AI response that should adapt properly to the available space and maintain readability while using the full content area effectively."
        
        short_annotation = PanelAnnotation(short_text, 0, (100, 100), "test")
        long_annotation = PanelAnnotation(long_text, 0, (100, 100), "test")
        
        qtbot.addWidget(short_annotation)
        qtbot.addWidget(long_annotation)
        
        # Both should have proper minimum height but adapt to content
        assert short_annotation.content_browser.minimumHeight() == 120
        assert long_annotation.content_browser.minimumHeight() == 120
        
        # Maximum height should be consistent
        assert short_annotation.content_browser.maximumHeight() == 400
        assert long_annotation.content_browser.maximumHeight() == 400

    def test_color_consistency_across_instances(self, qtbot):
        """Test that color assignment is consistent for same content."""
        text = "Same content"
        annotation1 = PanelAnnotation(text, 0, (100, 100), "selected")
        annotation2 = PanelAnnotation(text, 1, (200, 200), "other")
        
        qtbot.addWidget(annotation1)
        qtbot.addWidget(annotation2)
        
        # Same text should result in same color
        assert annotation1.current_color == annotation2.current_color
        assert annotation1.accent_color == annotation2.accent_color 