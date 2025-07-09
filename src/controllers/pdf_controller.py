"""
PDF Controller - UI-Service Decoupling for PDF Functionality

This controller manages the interaction between PDF UI components and PDFService,
handling document loading, navigation, and text selection operations.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.state_manager import StateManager, StateChangeType
from src.core.config_manager import ConfigManager
from src.services.pdf_service import PDFService

logger = logging.getLogger(__name__)


class PDFController(QObject):
    """
    {
        "name": "PDFController",
        "version": "1.0.0",
        "description": "Controller for PDF UI-Service coordination with state management.",
        "dependencies": ["PDFService", "StateManager", "ConfigManager"],
        "interface": {
            "inputs": ["file_paths", "navigation_events", "selection_events"],
            "outputs": "PDF operations and UI state updates"
        }
    }
    
    Controller that decouples PDF UI components from PDFService.
    Manages document loading, navigation, zoom, and text selection operations.
    """
    
    # UI Update Signals
    document_loaded = pyqtSignal(str, int)  # file_path, page_count
    document_load_failed = pyqtSignal(str)  # error_message
    page_changed = pyqtSignal(int, int)  # current_page, total_pages
    zoom_changed = pyqtSignal(float)  # zoom_level
    text_selected = pyqtSignal(str, int, dict)  # selected_text, page_num, coordinates
    document_closed = pyqtSignal()
    
    def __init__(self,
                 pdf_service: PDFService,
                 state_manager: StateManager,
                 config_manager: ConfigManager):
        """
        Initialize PDF controller with service dependencies.
        
        Args:
            pdf_service: Business logic service for PDF operations
            state_manager: Global state management
            config_manager: Configuration management
        """
        super().__init__()
        
        self._pdf_service = pdf_service
        self._state = state_manager
        self._config = config_manager
        
        # Setup state observers
        self._setup_state_observers()
        
        logger.info("PDFController initialized")
    
    def _setup_state_observers(self) -> None:
        """Setup observers for PDF-related state changes."""
        # Document state changes
        self._state.subscribe('pdf.current_document', self._on_document_changed)
        self._state.subscribe('pdf.current_page', self._on_page_changed)
        self._state.subscribe('pdf.zoom_level', self._on_zoom_changed)
        self._state.subscribe('pdf.selected_text', self._on_text_selection_changed)
    
    # Public API for UI Components
    
    def handle_load_document(self, file_path: str) -> None:
        """
        Handle document loading request from UI.
        
        Args:
            file_path: Path to PDF file to load
        """
        if not file_path or not Path(file_path).exists():
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            self.document_load_failed.emit(error_msg)
            return
        
        try:
            logger.info(f"Loading PDF document: {file_path}")
            
            # Load document through service (Note: PDFService uses load_pdf method)
            metadata = self._pdf_service.load_pdf(file_path)
            
            if metadata:
                # Update state
                self._state.set_state('pdf.current_document', file_path)
                self._state.set_state('pdf.page_count', metadata.get('total_pages', 0))
                self._state.set_state('pdf.current_page', 1)
                
                # Emit success signal
                self.document_loaded.emit(file_path, metadata.get('total_pages', 0))
                
                logger.info(f"PDF loaded successfully: {metadata.get('total_pages', 0)} pages")
            else:
                error_msg = "Unknown error loading document"
                logger.error(f"Failed to load PDF: {error_msg}")
                self.document_load_failed.emit(error_msg)
                
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"PDF document error: {e}")
            self.document_load_failed.emit(str(e))
        except Exception as e:
            logger.error(f"Unexpected error loading PDF: {e}")
            self.document_load_failed.emit(f"Unexpected error: {e}")
    
    def handle_close_document(self) -> None:
        """Handle document close request from UI."""
        logger.info("Closing PDF document")
        
        # Close through service
        self._pdf_service.close_pdf()
        
        # Clear state will be handled by service
        # Emit signal
        self.document_closed.emit()
    
    def handle_navigate_to_page(self, page_number: int) -> None:
        """
        Handle page navigation request from UI.
        
        Args:
            page_number: Target page number (1-based)
        """
        try:
            # Convert to 0-based for service
            zero_based_page = page_number - 1
            success = self._pdf_service.navigate_to_page(zero_based_page)
            
            if success:
                logger.debug(f"Navigated to page {page_number}")
            else:
                logger.warning(f"Page navigation failed: page {page_number}")
                
        except Exception as e:
            logger.error(f"Error navigating to page {page_number}: {e}")
    
    def handle_next_page(self) -> None:
        """Handle next page navigation."""
        try:
            success = self._pdf_service.next_page()
            if not success:
                logger.debug("Already at last page")
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
    
    def handle_previous_page(self) -> None:
        """Handle previous page navigation."""
        try:
            success = self._pdf_service.previous_page()
            if not success:
                logger.debug("Already at first page")
        except Exception as e:
            logger.error(f"Error navigating to previous page: {e}")
    
    def handle_zoom_change(self, zoom_level: float) -> None:
        """
        Handle zoom level change from UI.
        
        Args:
            zoom_level: New zoom level (1.0 = 100%)
        """
        try:
            success = self._pdf_service.set_zoom_level(zoom_level)
            
            if success:
                logger.debug(f"Zoom level set to {zoom_level:.2f}")
            else:
                logger.warning(f"Zoom change failed for level {zoom_level}")
                
        except Exception as e:
            logger.error(f"Error changing zoom level: {e}")
    
    def handle_text_selection(self, start_pos: Tuple[float, float], 
                            end_pos: Tuple[float, float],
                            page_number: int) -> None:
        """
        Handle text selection from UI.
        
        Args:
            start_pos: Start position (x, y)
            end_pos: End position (x, y) 
            page_number: Page number where selection occurred
        """
        try:
            logger.debug(f"Processing text selection on page {page_number}")
            
            # Create selection data
            selection_data = {
                'start_pos': start_pos,
                'end_pos': end_pos,
                'page': page_number,
                'text': '',  # Would be filled by actual text extraction
                'coordinates': {
                    'x1': start_pos[0],
                    'y1': start_pos[1],
                    'x2': end_pos[0], 
                    'y2': end_pos[1]
                }
            }
            
            # Set selection in service
            self._pdf_service.set_text_selection(selection_data)
            
            # Update state
            self._state.set_state('pdf.selected_text', selection_data)
            
            # Emit signal
            self.text_selected.emit(selection_data['text'], page_number, selection_data['coordinates'])
            
            logger.info(f"Text selection processed on page {page_number}")
                
        except Exception as e:
            logger.error(f"Error processing text selection: {e}")
    
    def handle_clear_selection(self) -> None:
        """Handle clear text selection request."""
        try:
            self._pdf_service.clear_text_selection()
            self._state.set_state('pdf.selected_text', None)
            logger.debug("Text selection cleared")
        except Exception as e:
            logger.error(f"Error clearing text selection: {e}")
    
    # State Change Handlers
    
    def _on_document_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle document state change."""
        document_path = new_value
        if document_path:
            logger.debug(f"Document state changed: {document_path}")
        else:
            logger.debug("Document state cleared")
    
    def _on_page_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle page number state change."""
        page_number = new_value
        page_count = self._state.get_state('pdf.page_count', 0)
        self.page_changed.emit(page_number, page_count)
        logger.debug(f"Page changed to {page_number}/{page_count}")
    
    def _on_zoom_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle zoom level state change."""
        zoom_level = new_value
        self.zoom_changed.emit(zoom_level)
        logger.debug(f"Zoom changed to {zoom_level:.2f}")
    
    def _on_text_selection_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle text selection state change."""
        selection_data = new_value
        if selection_data:
            logger.debug(f"Text selection updated: {len(selection_data.get('text', ''))} chars")
        else:
            logger.debug("Text selection cleared")
    
    # Utility Methods
    
    def get_document_info(self) -> Dict[str, Any]:
        """Get current document information."""
        return {
            'path': self._state.get_state('pdf.current_document'),
            'current_page': self._state.get_state('pdf.current_page', 0),
            'page_count': self._state.get_state('pdf.page_count', 0),
            'zoom_level': self._state.get_state('pdf.zoom_level', 1.0),
            'has_selection': bool(self._state.get_state('pdf.selected_text'))
        }
    
    def get_selected_text_info(self) -> Optional[Dict[str, Any]]:
        """Get current text selection information."""
        return self._state.get_state('pdf.selected_text')
    
    def is_document_loaded(self) -> bool:
        """Check if a document is currently loaded."""
        return bool(self._state.get_state('pdf.current_document'))
    
    def get_current_page(self) -> int:
        """Get current page number."""
        return self._state.get_state('pdf.current_page', 0)
    
    def get_page_count(self) -> int:
        """Get total page count."""
        return self._state.get_state('pdf.page_count', 0)
    
    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self._state.get_state('pdf.zoom_level', 1.0) 