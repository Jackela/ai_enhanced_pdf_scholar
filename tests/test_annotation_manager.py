import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
import fitz

from src.annotation_manager import AnnotationManager
from src.annotation import PanelAnnotation


class TestAnnotationManager:
    """Test suite for the AnnotationManager class in panel mode."""

    @pytest.fixture
    def mock_viewer(self):
        """Create a mock PDF viewer."""
        viewer = Mock()
        viewer.get_current_page_number.return_value = 0
        return viewer

    @pytest.fixture
    def mock_layout(self):
        """Create a mock layout for annotations."""
        layout = Mock(spec=QVBoxLayout)
        return layout

    @pytest.fixture
    def mock_empty_message(self):
        """Create a mock empty message widget."""
        widget = Mock(spec=QLabel)
        widget.hide = Mock()
        widget.show = Mock()
        return widget

    @pytest.fixture
    def annotation_manager(self, mock_viewer, mock_layout, mock_empty_message):
        """Create an AnnotationManager instance for testing."""
        return AnnotationManager(
            viewer=mock_viewer,
            annotations_layout=mock_layout,
            empty_message_widget=mock_empty_message
        )

    def test_initialization(self, annotation_manager, mock_viewer, mock_layout, mock_empty_message):
        """Test that AnnotationManager initializes correctly in panel mode."""
        assert annotation_manager.viewer == mock_viewer
        assert annotation_manager.annotations_layout == mock_layout
        assert annotation_manager.empty_message_widget == mock_empty_message
        assert annotation_manager.annotations == []

    @patch('src.annotation_manager.PanelAnnotation')
    def test_add_annotation(self, mock_annotation_class, annotation_manager, mock_layout, mock_empty_message):
        """Test adding an annotation to the panel."""
        # Setup mock annotation
        mock_annotation = Mock(spec=PanelAnnotation)
        mock_annotation_class.return_value = mock_annotation
        
        # Add annotation
        page_number = 0
        pdf_coords = fitz.Rect(100, 100, 200, 150)
        text = "Test AI response"
        selected_text = "Selected text"
        
        annotation_manager.add_annotation(page_number, pdf_coords, text, selected_text)
        
        # Verify annotation creation
        mock_annotation_class.assert_called_once_with(
            text=text,
            page_number=page_number,
            pdf_coords=pdf_coords,
            selected_text=selected_text
        )
        
        # Verify it's added to layout and list
        mock_layout.addWidget.assert_called_once_with(mock_annotation)
        assert len(annotation_manager.annotations) == 1
        assert annotation_manager.annotations[0] == mock_annotation
        
        # Verify empty message is hidden
        mock_empty_message.hide.assert_called_once()

    @patch('src.annotation_manager.PanelAnnotation')
    def test_add_multiple_annotations(self, mock_annotation_class, annotation_manager, mock_layout, mock_empty_message):
        """Test adding multiple annotations."""
        mock_annotations = [Mock(spec=PanelAnnotation) for _ in range(3)]
        mock_annotation_class.side_effect = mock_annotations
        
        # Add three annotations
        for i in range(3):
            annotation_manager.add_annotation(
                page_number=i,
                pdf_coords=fitz.Rect(0, 0, 100, 100),
                text=f"Response {i}",
                selected_text=f"Text {i}"
            )
        
        # Verify all were added
        assert len(annotation_manager.annotations) == 3
        assert mock_layout.addWidget.call_count == 3
        
        # Empty message should only be hidden once (on first annotation)
        mock_empty_message.hide.assert_called_once()

    def test_remove_annotation(self, annotation_manager, mock_layout, mock_empty_message):
        """Test removing an annotation from the panel."""
        # Create a mock annotation and add it to the manager
        mock_annotation = Mock(spec=PanelAnnotation)
        annotation_manager.annotations.append(mock_annotation)
        
        # Remove the annotation
        annotation_manager.remove_annotation(mock_annotation)
        
        # Verify it's removed from layout and list
        mock_layout.removeWidget.assert_called_once_with(mock_annotation)
        mock_annotation.deleteLater.assert_called_once()
        assert len(annotation_manager.annotations) == 0
        
        # Verify empty message is shown when no annotations left
        mock_empty_message.show.assert_called_once()

    def test_remove_annotation_not_in_list(self, annotation_manager, mock_layout, mock_empty_message):
        """Test removing an annotation that's not in the list."""
        mock_annotation = Mock(spec=PanelAnnotation)
        
        # Try to remove annotation that was never added
        annotation_manager.remove_annotation(mock_annotation)
        
        # Nothing should happen
        mock_layout.removeWidget.assert_not_called()
        mock_annotation.deleteLater.assert_not_called()
        mock_empty_message.show.assert_not_called()

    def test_remove_annotation_leaves_others(self, annotation_manager, mock_layout, mock_empty_message):
        """Test that removing one annotation leaves others intact."""
        # Add two mock annotations
        mock_annotation1 = Mock(spec=PanelAnnotation)
        mock_annotation2 = Mock(spec=PanelAnnotation)
        annotation_manager.annotations.extend([mock_annotation1, mock_annotation2])
        
        # Remove the first one
        annotation_manager.remove_annotation(mock_annotation1)
        
        # Verify only the first one was removed
        assert len(annotation_manager.annotations) == 1
        assert annotation_manager.annotations[0] == mock_annotation2
        
        # Empty message should NOT be shown (still have one annotation)
        mock_empty_message.show.assert_not_called()

    def test_clear_all_annotations(self, annotation_manager, mock_layout, mock_empty_message):
        """Test clearing all annotations."""
        # Add some mock annotations
        mock_annotations = [Mock(spec=PanelAnnotation) for _ in range(3)]
        annotation_manager.annotations.extend(mock_annotations)
        
        # Mock the remove_annotation method to avoid infinite recursion
        with patch.object(annotation_manager, 'remove_annotation') as mock_remove:
            annotation_manager.clear_all_annotations()
            
            # Verify remove_annotation was called for each annotation
            assert mock_remove.call_count == 3
            for annotation in mock_annotations:
                mock_remove.assert_any_call(annotation)
        
        # Verify the list is cleared and empty message is shown
        assert len(annotation_manager.annotations) == 0
        mock_empty_message.show.assert_called_once()

    def test_clear_all_annotations_when_empty(self, annotation_manager, mock_empty_message):
        """Test clearing annotations when the list is already empty."""
        # Start with empty list
        assert len(annotation_manager.annotations) == 0
        
        # Clear all (should not crash)
        annotation_manager.clear_all_annotations()
        
        # Should still be empty and show empty message
        assert len(annotation_manager.annotations) == 0
        mock_empty_message.show.assert_called_once()

    def test_handle_viewer_changed(self, annotation_manager):
        """Test handling viewer changes in panel mode."""
        # In panel mode, this should be a no-op since annotations are always visible
        # Just verify it doesn't crash
        annotation_manager.handle_viewer_changed()
        
        # No specific assertions needed since this is simplified in panel mode

    def test_get_annotation_count(self, annotation_manager):
        """Test getting the annotation count."""
        # Initially zero
        assert annotation_manager.get_annotation_count() == 0
        
        # Add some mock annotations
        mock_annotations = [Mock(spec=PanelAnnotation) for _ in range(5)]
        annotation_manager.annotations.extend(mock_annotations)
        
        # Should return correct count
        assert annotation_manager.get_annotation_count() == 5

    @patch('src.annotation_manager.PanelAnnotation')
    def test_annotation_signal_connection(self, mock_annotation_class, annotation_manager):
        """Test that annotation signals are properly connected."""
        mock_annotation = Mock(spec=PanelAnnotation)
        mock_annotation_class.return_value = mock_annotation
        
        # Add an annotation
        annotation_manager.add_annotation(0, fitz.Rect(0, 0, 100, 100), "Test", "Selected")
        
        # Verify that delete signal is connected
        mock_annotation.delete_requested.connect.assert_called_once_with(
            annotation_manager.remove_annotation
        )

    @patch('src.annotation_manager.PanelAnnotation')
    def test_add_annotation_without_selected_text(self, mock_annotation_class, annotation_manager):
        """Test adding annotation without selected text (default parameter)."""
        mock_annotation = Mock(spec=PanelAnnotation)
        mock_annotation_class.return_value = mock_annotation
        
        # Add annotation without selected_text parameter
        annotation_manager.add_annotation(0, fitz.Rect(0, 0, 100, 100), "Test response")
        
        # Verify it was called with empty selected_text
        mock_annotation_class.assert_called_once_with(
            text="Test response",
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            selected_text=""
        )


class TestAnnotationManagerIntegration:
    """Integration tests for AnnotationManager with real components."""

    @pytest.fixture
    def real_components(self, qtbot):
        """Create real QWidget components for integration testing."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        layout = QVBoxLayout()
        empty_message = QLabel("No annotations")
        viewer = Mock()
        viewer.get_current_page_number.return_value = 0
        
        return viewer, layout, empty_message

    def test_real_annotation_lifecycle(self, real_components, qtbot):
        """Test the complete lifecycle with real widgets."""
        viewer, layout, empty_message = real_components
        manager = AnnotationManager(viewer, layout, empty_message)
        
        # Add an annotation
        manager.add_annotation(
            page_number=0,
            pdf_coords=fitz.Rect(0, 0, 100, 100),
            text="Real test annotation",
            selected_text="Real selected text"
        )
        
        # Verify it was added
        assert manager.get_annotation_count() == 1
        assert not empty_message.isVisible()
        
        # Get the annotation and remove it
        annotation = manager.annotations[0]
        manager.remove_annotation(annotation)
        
        # Verify it was removed
        assert manager.get_annotation_count() == 0
        assert empty_message.isVisible() 