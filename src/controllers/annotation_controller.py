"""
Annotation Controller - UI-Service Decoupling for Annotation Functionality

This controller manages the interaction between annotation UI components and AnnotationService,
handling annotation creation, editing, deletion, and organization operations.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.state_manager import StateManager, StateChangeType
from src.core.config_manager import ConfigManager
from src.services.annotation_service import AnnotationService, AnnotationData

logger = logging.getLogger(__name__)


class AnnotationController(QObject):
    """
    {
        "name": "AnnotationController",
        "version": "1.0.0",
        "description": "Controller for annotation UI-Service coordination with reactive updates.",
        "dependencies": ["AnnotationService", "StateManager", "ConfigManager"],
        "interface": {
            "inputs": ["annotation_events", "text_selections", "ui_interactions"],
            "outputs": "Annotation operations and UI state updates"
        }
    }
    
    Controller that decouples annotation UI components from AnnotationService.
    Manages annotation lifecycle, organization, and reactive UI updates.
    """
    
    # UI Update Signals
    annotation_added = pyqtSignal(dict)  # annotation_data
    annotation_updated = pyqtSignal(str, dict)  # annotation_id, updated_data
    annotation_deleted = pyqtSignal(str)  # annotation_id
    annotations_cleared = pyqtSignal()
    annotation_count_changed = pyqtSignal(int)  # total_count
    annotation_search_results = pyqtSignal(list)  # matching_annotations
    
    def __init__(self,
                 annotation_service: AnnotationService,
                 state_manager: StateManager,
                 config_manager: ConfigManager):
        """
        Initialize annotation controller with service dependencies.
        
        Args:
            annotation_service: Business logic service for annotations
            state_manager: Global state management
            config_manager: Configuration management
        """
        super().__init__()
        
        self._annotation_service = annotation_service
        self._state = state_manager
        self._config = config_manager
        
        # Setup state observers
        self._setup_state_observers()
        
        logger.info("AnnotationController initialized")
    
    def _setup_state_observers(self) -> None:
        """Setup observers for annotation-related state changes."""
        # Annotation list changes
        self._state.subscribe('annotations.items', self._on_annotations_changed)
        
        # Selected text changes (for potential annotation creation)
        self._state.subscribe('pdf.selected_text', self._on_text_selection_changed)
        
        # Annotation filter/search changes
        self._state.subscribe('annotations.filter', self._on_filter_changed)
        self._state.subscribe('annotations.search_query', self._on_search_query_changed)
    
    # Public API for UI Components
    
    def handle_create_annotation(self, 
                                selected_text: str,
                                page_number: int,
                                coordinates: Dict[str, float],
                                ai_content: str = "") -> None:
        """
        Handle annotation creation request from UI.
        
        Args:
            selected_text: Text selected by user
            page_number: Page number where annotation is created
            coordinates: Position coordinates on page
            ai_content: AI-generated content for annotation
        """
        try:
            logger.info(f"Creating annotation on page {page_number}")
            
            # Create annotation through service
            annotation = self._annotation_service.create_annotation(
                selected_text=selected_text,
                page_number=page_number,
                coordinates=coordinates,
                ai_content=ai_content
            )
            
            if annotation:
                logger.info(f"Annotation created with ID: {annotation.id}")
                # Signal will be emitted via state observer
            else:
                logger.error("Failed to create annotation")
                
        except Exception as e:
            logger.error(f"Error creating annotation: {e}")
    
    def handle_update_annotation(self, 
                                annotation_id: str,
                                updates: Dict[str, Any]) -> None:
        """
        Handle annotation update request from UI.
        
        Args:
            annotation_id: ID of annotation to update
            updates: Dictionary of fields to update
        """
        try:
            logger.info(f"Updating annotation: {annotation_id}")
            
            success = self._annotation_service.update_annotation(annotation_id, updates)
            
            if success:
                logger.info(f"Annotation updated: {annotation_id}")
                # Signal will be emitted via state observer
            else:
                logger.warning(f"Failed to update annotation: {annotation_id}")
                
        except Exception as e:
            logger.error(f"Error updating annotation {annotation_id}: {e}")
    
    def handle_delete_annotation(self, annotation_id: str) -> None:
        """
        Handle annotation deletion request from UI.
        
        Args:
            annotation_id: ID of annotation to delete
        """
        try:
            logger.info(f"Deleting annotation: {annotation_id}")
            
            success = self._annotation_service.delete_annotation(annotation_id)
            
            if success:
                logger.info(f"Annotation deleted: {annotation_id}")
                # Signal will be emitted via state observer
            else:
                logger.warning(f"Failed to delete annotation: {annotation_id}")
                
        except Exception as e:
            logger.error(f"Error deleting annotation {annotation_id}: {e}")
    
    def handle_clear_all_annotations(self) -> None:
        """Handle clear all annotations request from UI."""
        try:
            logger.info("Clearing all annotations")
            
            self._annotation_service.clear_all_annotations()
            
            logger.info("All annotations cleared")
            # Signal will be emitted via state observer
            
        except Exception as e:
            logger.error(f"Error clearing annotations: {e}")
    
    def handle_search_annotations(self, query: str) -> None:
        """
        Handle annotation search request from UI.
        
        Args:
            query: Search query string
        """
        try:
            logger.debug(f"Searching annotations: '{query}'")
            
            # Update search state
            self._state.set_state('annotations.search_query', query)
            
            # Perform search through service
            results = self._annotation_service.search_annotations(query)
            
            # Convert to serializable format
            result_data = [ann.to_dict() for ann in results]
            
            # Emit results
            self.annotation_search_results.emit(result_data)
            
            logger.debug(f"Found {len(results)} matching annotations")
            
        except Exception as e:
            logger.error(f"Error searching annotations: {e}")
            self.annotation_search_results.emit([])
    
    def handle_filter_annotations(self, filter_criteria: Dict[str, Any]) -> None:
        """
        Handle annotation filtering request from UI.
        
        Args:
            filter_criteria: Dictionary of filter criteria
        """
        try:
            logger.debug(f"Filtering annotations: {filter_criteria}")
            
            # Update filter state
            self._state.set_state('annotations.filter', filter_criteria)
            
            # Apply filter through service
            filtered_annotations = self._annotation_service.filter_annotations(filter_criteria)
            
            # Update filtered list in state
            filtered_data = [ann.to_dict() for ann in filtered_annotations]
            self._state.set_state('annotations.filtered_items', filtered_data)
            
            logger.debug(f"Filtered to {len(filtered_annotations)} annotations")
            
        except Exception as e:
            logger.error(f"Error filtering annotations: {e}")
    
    def handle_export_annotations(self, format: str = 'json') -> str:
        """
        Handle annotation export request from UI.
        
        Args:
            format: Export format ('json', 'markdown', 'csv')
            
        Returns:
            Exported annotation data
        """
        try:
            logger.info(f"Exporting annotations in {format} format")
            
            export_data = self._annotation_service.export_annotations(format)
            
            logger.info(f"Annotations exported: {len(export_data)} characters")
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting annotations: {e}")
            return ""
    
    def handle_import_annotations(self, data: str, format: str = 'json') -> None:
        """
        Handle annotation import request from UI.
        
        Args:
            data: Import data string
            format: Import format ('json', 'markdown', 'csv')
        """
        try:
            logger.info(f"Importing annotations from {format} format")
            
            imported_count = self._annotation_service.import_annotations(data, format)
            
            logger.info(f"Imported {imported_count} annotations")
            # Signals will be emitted via state observers
            
        except Exception as e:
            logger.error(f"Error importing annotations: {e}")
    
    def handle_annotation_highlight_request(self, text: str) -> None:
        """
        Handle request to create annotation from selected text.
        
        Args:
            text: Selected text to highlight
        """
        # Get current PDF state for context
        pdf_state = self._state.get_state('pdf.selected_text')
        
        if pdf_state and pdf_state.get('text') == text:
            page_number = pdf_state.get('page', 1)
            coordinates = pdf_state.get('coordinates', {})
            
            # Create annotation with selected text
            self.handle_create_annotation(
                selected_text=text,
                page_number=page_number,
                coordinates=coordinates,
                ai_content=""  # Will be filled by AI later
            )
        else:
            logger.warning("No matching PDF selection found for highlight request")
    
    # State Change Handlers
    
    def _on_annotations_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle annotations list state change."""
        annotations = new_value or []
        logger.debug(f"Annotations state changed: {len(annotations)} items")
        
        # Emit count change
        self.annotation_count_changed.emit(len(annotations))
        
        # Check for newly added annotations
        current_ids = {ann.get('id') for ann in annotations if ann.get('id')}
        previous_ids = getattr(self, '_previous_annotation_ids', set())
        
        # Detect new annotations
        new_ids = current_ids - previous_ids
        for ann in annotations:
            if ann.get('id') in new_ids:
                self.annotation_added.emit(ann)
        
        # Detect deleted annotations
        deleted_ids = previous_ids - current_ids
        for deleted_id in deleted_ids:
            self.annotation_deleted.emit(deleted_id)
        
        # Update tracking
        self._previous_annotation_ids = current_ids
    
    def _on_text_selection_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle PDF text selection change."""
        selection_data = new_value
        if selection_data:
            selected_text = selection_data.get('text', '')
            logger.debug(f"Text selection available for annotation: {len(selected_text)} chars")
        else:
            logger.debug("Text selection cleared")
    
    def _on_filter_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle annotation filter criteria change."""
        filter_criteria = new_value
        logger.debug(f"Annotation filter changed: {filter_criteria}")
    
    def _on_search_query_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle annotation search query change."""
        query = new_value
        if query:
            logger.debug(f"Annotation search query: '{query}'")
        else:
            logger.debug("Annotation search cleared")
    
    # Utility Methods
    
    def get_annotation_statistics(self) -> Dict[str, Any]:
        """Get annotation statistics for UI display."""
        return self._annotation_service.get_statistics()
    
    def get_annotations_by_page(self, page_number: int) -> List[Dict[str, Any]]:
        """
        Get annotations for a specific page.
        
        Args:
            page_number: Page number to filter by
            
        Returns:
            List of annotation data dictionaries
        """
        annotations = self._annotation_service.get_annotations_by_page(page_number)
        return [ann.to_dict() for ann in annotations]
    
    def get_all_annotations(self) -> List[Dict[str, Any]]:
        """Get all annotations as data dictionaries."""
        annotations = self._annotation_service.get_all_annotations()
        return [ann.to_dict() for ann in annotations]
    
    def get_annotation_by_id(self, annotation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific annotation by ID.
        
        Args:
            annotation_id: Annotation ID to retrieve
            
        Returns:
            Annotation data dictionary or None
        """
        annotation = self._annotation_service.get_annotation_by_id(annotation_id)
        return annotation.to_dict() if annotation else None
    
    def get_annotation_count(self) -> int:
        """Get total annotation count."""
        return self._annotation_service.get_annotation_count()
    
    def has_annotations(self) -> bool:
        """Check if any annotations exist."""
        return self.get_annotation_count() > 0 