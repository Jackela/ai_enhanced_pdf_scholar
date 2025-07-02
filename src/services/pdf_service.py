"""
PDF Service - PDF Document Business Logic

This module provides PDF document functionality as pure business logic,
completely decoupled from UI frameworks.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from src.core.state_manager import StateManager

logger = logging.getLogger(__name__)


class PDFService:
    """
    {
        "name": "PDFService",
        "version": "1.0.0",
        "description": "Pure business logic for PDF document management, completely UI-independent.",
        "dependencies": ["StateManager"],
        "interface": {
            "inputs": ["pdf_path: str"],
            "outputs": "PDF document state and metadata"
        }
    }
    
    Pure business logic service for PDF document functionality.
    Handles PDF loading, navigation, and metadata management
    without any UI framework dependencies.
    """
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize PDF service with state management.
        
        Args:
            state_manager: Global state management
        """
        self._state = state_manager
        
        # Initialize PDF state if not exists
        if not self._state.get_state('pdf.current_path'):
            self._state.set_state('pdf.current_path', None)
            self._state.set_state('pdf.current_page', 0)
            self._state.set_state('pdf.total_pages', 0)
            self._state.set_state('pdf.zoom_level', 1.0)
            self._state.set_state('pdf.selection', None)
        
        logger.info("PDFService initialized")
    
    def load_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Load PDF document and update state.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with PDF metadata
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If file is not a valid PDF
        """
        # Validate file
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if not pdf_path.lower().endswith('.pdf'):
            raise ValueError(f"File is not a PDF: {pdf_path}")
        
        try:
            # Get PDF metadata (would use PyMuPDF in real implementation)
            # For now, simulate PDF loading
            total_pages = self._get_pdf_page_count(pdf_path)
            
            # Update state
            self._state.set_state('pdf.current_path', str(pdf_file.absolute()))
            self._state.set_state('pdf.current_page', 0)
            self._state.set_state('pdf.total_pages', total_pages)
            self._state.set_state('pdf.zoom_level', 1.0)
            self._state.set_state('pdf.selection', None)
            
            # Update app state
            self._state.set_state('app.current_pdf', str(pdf_file.absolute()))
            
            metadata = {
                'path': str(pdf_file.absolute()),
                'filename': pdf_file.name,
                'size_bytes': pdf_file.stat().st_size,
                'total_pages': total_pages,
                'current_page': 0,
                'zoom_level': 1.0
            }
            
            logger.info(f"Loaded PDF: {pdf_file.name} ({total_pages} pages)")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to load PDF {pdf_path}: {e}")
            raise
    
    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """
        Get number of pages in PDF document.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of pages
        """
        try:
            # In real implementation, would use PyMuPDF
            import fitz
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except ImportError:
            # Fallback for testing without PyMuPDF
            logger.warning("PyMuPDF not available, using dummy page count")
            return 10
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return 1
    
    def navigate_to_page(self, page_number: int) -> bool:
        """
        Navigate to specific page.
        
        Args:
            page_number: Page number (0-based)
            
        Returns:
            True if navigation successful, False otherwise
        """
        total_pages = self._state.get_state('pdf.total_pages', 0)
        
        if total_pages == 0:
            logger.warning("No PDF loaded for navigation")
            return False
        
        if not (0 <= page_number < total_pages):
            logger.warning(f"Page {page_number} out of range (0-{total_pages-1})")
            return False
        
        self._state.set_state('pdf.current_page', page_number)
        self._state.set_state('pdf.selection', None)  # Clear selection
        
        logger.debug(f"Navigated to page {page_number}")
        return True
    
    def next_page(self) -> bool:
        """Navigate to next page."""
        current_page = self._state.get_state('pdf.current_page', 0)
        return self.navigate_to_page(current_page + 1)
    
    def previous_page(self) -> bool:
        """Navigate to previous page."""
        current_page = self._state.get_state('pdf.current_page', 0)
        return self.navigate_to_page(current_page - 1)
    
    def set_zoom_level(self, zoom_level: float) -> bool:
        """
        Set PDF zoom level.
        
        Args:
            zoom_level: Zoom factor (e.g., 1.0 = 100%, 1.5 = 150%)
            
        Returns:
            True if zoom level set successfully
        """
        if zoom_level <= 0:
            logger.warning(f"Invalid zoom level: {zoom_level}")
            return False
        
        # Clamp zoom level to reasonable range
        zoom_level = max(0.1, min(5.0, zoom_level))
        
        self._state.set_state('pdf.zoom_level', zoom_level)
        logger.debug(f"Set zoom level to {zoom_level}")
        return True
    
    def zoom_in(self, factor: float = 1.2) -> bool:
        """Zoom in by specified factor."""
        current_zoom = self._state.get_state('pdf.zoom_level', 1.0)
        return self.set_zoom_level(current_zoom * factor)
    
    def zoom_out(self, factor: float = 1.2) -> bool:
        """Zoom out by specified factor."""
        current_zoom = self._state.get_state('pdf.zoom_level', 1.0)
        return self.set_zoom_level(current_zoom / factor)
    
    def reset_zoom(self) -> bool:
        """Reset zoom to 100%."""
        return self.set_zoom_level(1.0)
    
    def set_text_selection(self, selection_data: Dict[str, Any]) -> None:
        """
        Set current text selection.
        
        Args:
            selection_data: Selection data with coordinates and text
        """
        self._state.set_state('pdf.selection', selection_data)
        logger.debug(f"Set text selection: {selection_data.get('text', '')[:50]}...")
    
    def clear_text_selection(self) -> None:
        """Clear current text selection."""
        self._state.set_state('pdf.selection', None)
        logger.debug("Cleared text selection")
    
    def get_current_pdf_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about currently loaded PDF.
        
        Returns:
            PDF information dictionary or None if no PDF loaded
        """
        pdf_path = self._state.get_state('pdf.current_path')
        if not pdf_path:
            return None
        
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            # PDF file was moved or deleted
            self.close_pdf()
            return None
        
        return {
            'path': pdf_path,
            'filename': pdf_file.name,
            'size_bytes': pdf_file.stat().st_size,
            'current_page': self._state.get_state('pdf.current_page', 0),
            'total_pages': self._state.get_state('pdf.total_pages', 0),
            'zoom_level': self._state.get_state('pdf.zoom_level', 1.0),
            'has_selection': self._state.get_state('pdf.selection') is not None
        }
    
    def close_pdf(self) -> None:
        """Close current PDF and clear state."""
        pdf_info = self.get_current_pdf_info()
        
        # Clear PDF state
        self._state.set_state('pdf.current_path', None)
        self._state.set_state('pdf.current_page', 0)
        self._state.set_state('pdf.total_pages', 0)
        self._state.set_state('pdf.zoom_level', 1.0)
        self._state.set_state('pdf.selection', None)
        
        # Clear app state
        self._state.set_state('app.current_pdf', None)
        
        if pdf_info:
            logger.info(f"Closed PDF: {pdf_info['filename']}")
        else:
            logger.info("Closed PDF")
    
    def is_pdf_loaded(self) -> bool:
        """Check if a PDF is currently loaded."""
        pdf_path = self._state.get_state('pdf.current_path')
        return pdf_path is not None and Path(pdf_path).exists()
    
    def get_page_range_info(self, start_page: int = None, end_page: int = None) -> Dict[str, Any]:
        """
        Get information about a range of pages.
        
        Args:
            start_page: Starting page (0-based, None = first page)
            end_page: Ending page (0-based, None = last page)
            
        Returns:
            Page range information
        """
        if not self.is_pdf_loaded():
            return {'error': 'No PDF loaded'}
        
        total_pages = self._state.get_state('pdf.total_pages', 0)
        
        start_page = start_page if start_page is not None else 0
        end_page = end_page if end_page is not None else total_pages - 1
        
        # Validate range
        start_page = max(0, min(start_page, total_pages - 1))
        end_page = max(start_page, min(end_page, total_pages - 1))
        
        return {
            'start_page': start_page,
            'end_page': end_page,
            'page_count': end_page - start_page + 1,
            'total_pages': total_pages
        }
    
    def get_pdf_statistics(self) -> Dict[str, Any]:
        """Get PDF document statistics."""
        if not self.is_pdf_loaded():
            return {'error': 'No PDF loaded'}
        
        pdf_info = self.get_current_pdf_info()
        current_page = self._state.get_state('pdf.current_page', 0)
        total_pages = self._state.get_state('pdf.total_pages', 0)
        
        # Calculate reading progress
        progress_percent = ((current_page + 1) / total_pages * 100) if total_pages > 0 else 0
        
        return {
            'filename': pdf_info['filename'],
            'size_mb': round(pdf_info['size_bytes'] / (1024 * 1024), 2),
            'total_pages': total_pages,
            'current_page': current_page + 1,  # 1-based for display
            'progress_percent': round(progress_percent, 1),
            'zoom_level': self._state.get_state('pdf.zoom_level', 1.0),
            'has_selection': pdf_info['has_selection']
        }
    
    def validate_pdf_state(self) -> Dict[str, Any]:
        """Validate current PDF state and return status."""
        pdf_path = self._state.get_state('pdf.current_path')
        
        if not pdf_path:
            return {'valid': True, 'status': 'no_pdf_loaded'}
        
        # Check if file still exists
        if not Path(pdf_path).exists():
            self.close_pdf()
            return {'valid': False, 'status': 'file_not_found', 'path': pdf_path}
        
        # Check page bounds
        current_page = self._state.get_state('pdf.current_page', 0)
        total_pages = self._state.get_state('pdf.total_pages', 0)
        
        if current_page >= total_pages:
            # Reset to last valid page
            self.navigate_to_page(max(0, total_pages - 1))
            return {'valid': True, 'status': 'page_reset', 'new_page': max(0, total_pages - 1)}
        
        return {'valid': True, 'status': 'ok'} 