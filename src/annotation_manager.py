from typing import Dict, List, TYPE_CHECKING
from PyQt6.QtCore import QObject, QRectF, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QApplication
import fitz
import logging

from src.annotation import PanelAnnotation

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.pdf_viewer import PDFViewer

class AnnotationManager(QObject):
    """
    {
        "name": "AnnotationManager", 
        "version": "2.0.0",
        "description": "Manages annotations in a right-side panel layout for better user experience.",
        "dependencies": ["PanelAnnotation"],
        "interface": {}
    }
    Manages the lifecycle of annotation widgets within the right-side panel.
    Simplified from complex positioning to simple vertical stacking.
    """
    def __init__(self, viewer: 'PDFViewer', annotations_layout, empty_message_widget, parent=None):
        """
        @param {PDFViewer} viewer - The PDF viewer widget for reference.
        @param {QVBoxLayout} annotations_layout - The layout for the annotations panel.
        @param {QWidget} empty_message_widget - Widget to show when no annotations exist.
        @param {QObject} parent - The parent QObject.
        """
        super().__init__(parent)
        self.viewer = viewer
        self.annotations_layout = annotations_layout
        self.empty_message_widget = empty_message_widget
        # List to maintain annotation order
        self.annotations: List[PanelAnnotation] = []

    def add_annotation(self, page_number: int, pdf_coords: fitz.Rect, text: str, selected_text: str = ""):
        """
        Add a new annotation to the panel.
        
        @param {int} page_number - The page number (0-indexed) where the annotation is located.
        @param {fitz.Rect} pdf_coords - The PDF coordinates of the annotation.
        @param {str} text - The AI response text to display.
        @param {str} selected_text - The text that was selected by the user.
        """
        # Check for duplicate annotations to prevent multiple triggers
        annotation_key = f"{page_number}_{pdf_coords.x0}_{pdf_coords.y0}_{hash(text[:100])}"
        
        # Check if similar annotation already exists
        for existing_annotation in self.annotations:
            # Skip Mock objects in tests that don't have real attributes
            if not hasattr(existing_annotation, 'page_number') or not hasattr(existing_annotation, 'pdf_coords') or not hasattr(existing_annotation, 'text'):
                continue
                
            existing_key = f"{existing_annotation.page_number}_{existing_annotation.pdf_coords.x0}_{existing_annotation.pdf_coords.y0}_{hash(existing_annotation.text[:100])}"
            if annotation_key == existing_key:
                logger.warning(f"Duplicate annotation detected for page {page_number}, skipping...")
                return
        
        # Create the annotation widget
        annotation_widget = PanelAnnotation(
            text=text, 
            page_number=page_number, 
            pdf_coords=pdf_coords, 
            selected_text=selected_text
        )
        
        # Connect signals for interaction
        annotation_widget.delete_requested.connect(self.remove_annotation)
        # Note: highlight_requested could be used for future features
        if hasattr(annotation_widget, 'highlight_requested'):
            annotation_widget.highlight_requested.connect(self._handle_highlight_request)
        
        # Add to layout (newest at bottom for consistency with tests)
        self.annotations_layout.addWidget(annotation_widget)
        
        # Store annotation reference
        self.annotations.append(annotation_widget)
        
        # Hide empty message if this is the first annotation
        if len(self.annotations) == 1:
            self.empty_message_widget.hide()
            
        logger.info(f"Added annotation to page {page_number} at coordinates {pdf_coords}")
        
        # Process layout changes
        QApplication.processEvents()

    def _handle_highlight_request(self, annotation):
        """Handle highlight request from annotation widget."""
        # This could be used to highlight the source in PDF viewer
        logger.info(f"Highlight requested for annotation on page {annotation.page_number}")

    def remove_annotation(self, annotation):
        """
        Removes a specific annotation from the panel.
        @param {PanelAnnotation} annotation - The annotation to remove.
        """
        if annotation in self.annotations:
            self.annotations.remove(annotation)
            self.annotations_layout.removeWidget(annotation)
            annotation.deleteLater()
            
            # Show empty message if no annotations left
            if not self.annotations:
                self.empty_message_widget.show()
            
            logger.info(f"Removed panel annotation. Remaining annotations: {len(self.annotations)}")

    def clear_all_annotations(self):
        """Removes all annotations from the panel and clears the records."""
        logger.info(f"Clearing all panel annotations ({len(self.annotations)} total)")
        
        for annotation in self.annotations[:]:  # Copy list to avoid modification during iteration
            self.remove_annotation(annotation)
        
        self.annotations.clear()
        self.empty_message_widget.show()

    def handle_viewer_changed(self):
        """
        Handle viewer changes. In panel mode, this is simplified since we don't need 
        complex positioning - annotations are always visible in the panel.
        """
        logger.info("Viewer changed - panel annotations remain visible")
        # In panel mode, we don't need to reposition annotations
        # They remain visible and accessible in the right panel regardless of PDF state

    def get_annotation_count(self) -> int:
        """Get the total number of annotations."""
        return len(self.annotations) 