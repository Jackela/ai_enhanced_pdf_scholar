"""
Annotation Service - PDF Annotation Business Logic

This module provides annotation functionality as pure business logic,
completely decoupled from UI frameworks.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json

from src.core.state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class AnnotationData:
    """
    {
        "name": "AnnotationData",
        "version": "1.0.0",
        "description": "Pure data model for PDF annotations without UI dependencies.",
        "dependencies": [],
        "interface": {
            "inputs": ["text: str", "ai_response: str", "page: int", "coordinates: dict"],
            "outputs": "Annotation data object"
        }
    }
    
    Pure data class representing a PDF annotation without any UI coupling.
    """
    id: str
    selected_text: str
    ai_response: str
    page_number: int
    coordinates: Dict[str, float]  # x1, y1, x2, y2
    created_at: datetime
    color: str = "#FFE082"
    category: str = "general"
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert annotation to dictionary for serialization."""
        return {
            'id': self.id,
            'selected_text': self.selected_text,
            'ai_response': self.ai_response,
            'page_number': self.page_number,
            'coordinates': self.coordinates,
            'created_at': self.created_at.isoformat(),
            'color': self.color,
            'category': self.category,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnnotationData':
        """Create annotation from dictionary."""
        return cls(
            id=data['id'],
            selected_text=data['selected_text'],
            ai_response=data['ai_response'],
            page_number=data['page_number'],
            coordinates=data['coordinates'],
            created_at=datetime.fromisoformat(data['created_at']),
            color=data.get('color', '#FFE082'),
            category=data.get('category', 'general'),
            tags=data.get('tags', [])
        )


class AnnotationService:
    """
    {
        "name": "AnnotationService",
        "version": "1.0.0",
        "description": "Pure business logic for PDF annotation management, completely UI-independent.",
        "dependencies": ["StateManager"],
        "interface": {
            "inputs": ["text: str", "ai_response: str", "page: int", "coordinates: dict"],
            "outputs": "AnnotationData object"
        }
    }
    
    Pure business logic service for PDF annotation functionality.
    Handles annotation creation, management, and organization
    without any UI framework dependencies.
    """
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize annotation service with state management.
        
        Args:
            state_manager: Global state management
        """
        self._state = state_manager
        
        # Initialize annotation state if not exists
        if not self._state.get_state('annotations.items'):
            self._state.set_state('annotations.items', [])
        
        logger.info("AnnotationService initialized")
    
    def create_annotation(self, 
                         selected_text: str,
                         ai_response: str,
                         page_number: int,
                         coordinates: Dict[str, float],
                         color: str = "#FFE082",
                         category: str = "general",
                         tags: List[str] = None) -> AnnotationData:
        """
        Create a new annotation.
        
        Args:
            selected_text: Text selected from PDF
            ai_response: AI-generated response/insight
            page_number: PDF page number (0-based)
            coordinates: Selection coordinates {x1, y1, x2, y2}
            color: Annotation color
            category: Annotation category
            tags: Optional tags
            
        Returns:
            Created AnnotationData object
            
        Raises:
            ValueError: If required parameters are invalid
        """
        if not selected_text or not selected_text.strip():
            raise ValueError("Selected text cannot be empty")
        
        if not ai_response or not ai_response.strip():
            raise ValueError("AI response cannot be empty")
        
        if page_number < 0:
            raise ValueError("Page number must be non-negative")
        
        if not coordinates or not all(k in coordinates for k in ['x1', 'y1', 'x2', 'y2']):
            raise ValueError("Coordinates must contain x1, y1, x2, y2")
        
        # Generate unique ID
        annotation_id = f"ann_{datetime.now().timestamp()}_{page_number}"
        
        # Create annotation
        annotation = AnnotationData(
            id=annotation_id,
            selected_text=selected_text.strip(),
            ai_response=ai_response.strip(),
            page_number=page_number,
            coordinates=coordinates,
            created_at=datetime.now(),
            color=color,
            category=category,
            tags=tags or []
        )
        
        # Add to state
        self._add_annotation_to_state(annotation)
        
        logger.info(f"Created annotation {annotation_id} on page {page_number}")
        return annotation
    
    def _add_annotation_to_state(self, annotation: AnnotationData) -> None:
        """Add annotation to global state and update counters."""
        # Get current annotations
        annotations = self._state.get_state('annotations.items') or []
        
        # Add new annotation
        annotations.append(annotation)
        
        # Update state
        self._state.set_state('annotations.items', annotations)
        self._state.update_state('annotations.total_count', lambda x: x + 1)
        self._state.set_state('annotations.last_added', annotation.id)
        
        logger.debug(f"Added annotation to state (total: {len(annotations)})")
    
    def get_annotations(self, page_number: int = None) -> List[AnnotationData]:
        """
        Get annotations, optionally filtered by page.
        
        Args:
            page_number: Optional page filter (None = all annotations)
            
        Returns:
            List of AnnotationData objects
        """
        annotations_data = self._state.get_state('annotations.items') or []
        
        # Convert to AnnotationData objects if needed
        annotations = []
        for ann_data in annotations_data:
            if isinstance(ann_data, AnnotationData):
                annotations.append(ann_data)
            elif isinstance(ann_data, dict):
                annotations.append(AnnotationData.from_dict(ann_data))
        
        # Filter by page if specified
        if page_number is not None:
            annotations = [ann for ann in annotations if ann.page_number == page_number]
        
        return annotations
    
    def get_annotation_by_id(self, annotation_id: str) -> Optional[AnnotationData]:
        """Get specific annotation by ID."""
        annotations = self.get_annotations()
        for annotation in annotations:
            if annotation.id == annotation_id:
                return annotation
        return None
    
    def update_annotation(self, annotation_id: str, **updates) -> bool:
        """
        Update existing annotation.
        
        Args:
            annotation_id: ID of annotation to update
            **updates: Fields to update
            
        Returns:
            True if annotation was updated, False if not found
        """
        annotations = self.get_annotations()
        
        for i, annotation in enumerate(annotations):
            if annotation.id == annotation_id:
                # Update allowed fields
                if 'ai_response' in updates:
                    annotation.ai_response = updates['ai_response']
                if 'color' in updates:
                    annotation.color = updates['color']
                if 'category' in updates:
                    annotation.category = updates['category']
                if 'tags' in updates:
                    annotation.tags = updates['tags']
                
                # Update state
                self._state.set_state('annotations.items', annotations)
                
                logger.info(f"Updated annotation {annotation_id}")
                return True
        
        logger.warning(f"Annotation {annotation_id} not found for update")
        return False
    
    def delete_annotation(self, annotation_id: str) -> bool:
        """
        Delete annotation by ID.
        
        Args:
            annotation_id: ID of annotation to delete
            
        Returns:
            True if annotation was deleted, False if not found
        """
        annotations = self.get_annotations()
        
        for i, annotation in enumerate(annotations):
            if annotation.id == annotation_id:
                # Remove annotation
                annotations.pop(i)
                
                # Update state
                self._state.set_state('annotations.items', annotations)
                self._state.update_state('annotations.total_count', lambda x: max(0, x - 1))
                
                logger.info(f"Deleted annotation {annotation_id}")
                return True
        
        logger.warning(f"Annotation {annotation_id} not found for deletion")
        return False
    
    def clear_annotations(self, page_number: int = None) -> int:
        """
        Clear annotations, optionally filtered by page.
        
        Args:
            page_number: Optional page filter (None = all annotations)
            
        Returns:
            Number of annotations cleared
        """
        if page_number is None:
            # Clear all annotations
            annotation_count = len(self._state.get_state('annotations.items') or [])
            self._state.set_state('annotations.items', [])
            self._state.set_state('annotations.total_count', 0)
            self._state.set_state('annotations.selected_annotation', None)
            self._state.set_state('annotations.last_added', None)
            
            logger.info(f"Cleared all {annotation_count} annotations")
            return annotation_count
        else:
            # Clear annotations for specific page
            annotations = self.get_annotations()
            page_annotations = [ann for ann in annotations if ann.page_number == page_number]
            remaining_annotations = [ann for ann in annotations if ann.page_number != page_number]
            
            # Update state
            self._state.set_state('annotations.items', remaining_annotations)
            self._state.set_state('annotations.total_count', len(remaining_annotations))
            
            logger.info(f"Cleared {len(page_annotations)} annotations from page {page_number}")
            return len(page_annotations)
    
    def search_annotations(self, query: str, search_fields: List[str] = None) -> List[AnnotationData]:
        """
        Search annotations by text content.
        
        Args:
            query: Search query string
            search_fields: Fields to search in ['selected_text', 'ai_response', 'tags']
            
        Returns:
            List of matching annotations
        """
        if not query or not query.strip():
            return []
        
        query = query.lower().strip()
        search_fields = search_fields or ['selected_text', 'ai_response', 'tags']
        
        annotations = self.get_annotations()
        matches = []
        
        for annotation in annotations:
            # Search in selected fields
            if 'selected_text' in search_fields and query in annotation.selected_text.lower():
                matches.append(annotation)
                continue
            
            if 'ai_response' in search_fields and query in annotation.ai_response.lower():
                matches.append(annotation)
                continue
            
            if 'tags' in search_fields:
                for tag in annotation.tags:
                    if query in tag.lower():
                        matches.append(annotation)
                        break
        
        logger.debug(f"Found {len(matches)} annotations matching '{query}'")
        return matches
    
    def get_annotations_by_category(self, category: str) -> List[AnnotationData]:
        """Get all annotations in a specific category."""
        annotations = self.get_annotations()
        return [ann for ann in annotations if ann.category == category]
    
    def get_annotation_statistics(self) -> Dict[str, Any]:
        """Get annotation statistics and insights."""
        annotations = self.get_annotations()
        
        if not annotations:
            return {
                'total_annotations': 0,
                'pages_with_annotations': 0,
                'categories': {},
                'average_per_page': 0,
                'most_annotated_page': None,
                'oldest_annotation': None,
                'newest_annotation': None
            }
        
        # Calculate statistics
        pages = set(ann.page_number for ann in annotations)
        categories = {}
        for ann in annotations:
            categories[ann.category] = categories.get(ann.category, 0) + 1
        
        # Find most annotated page
        page_counts = {}
        for ann in annotations:
            page_counts[ann.page_number] = page_counts.get(ann.page_number, 0) + 1
        most_annotated_page = max(page_counts.items(), key=lambda x: x[1])
        
        # Time statistics
        sorted_annotations = sorted(annotations, key=lambda x: x.created_at)
        
        return {
            'total_annotations': len(annotations),
            'pages_with_annotations': len(pages),
            'categories': categories,
            'average_per_page': len(annotations) / len(pages) if pages else 0,
            'most_annotated_page': most_annotated_page[0],
            'most_annotated_page_count': most_annotated_page[1],
            'oldest_annotation': sorted_annotations[0].created_at.isoformat(),
            'newest_annotation': sorted_annotations[-1].created_at.isoformat(),
            'unique_pages': sorted(list(pages))
        }
    
    def export_annotations(self, format: str = 'json', page_number: int = None) -> str:
        """
        Export annotations in specified format.
        
        Args:
            format: Export format ('json', 'csv', 'markdown')
            page_number: Optional page filter
            
        Returns:
            Formatted annotations string
        """
        annotations = self.get_annotations(page_number)
        
        if format == 'json':
            return json.dumps([ann.to_dict() for ann in annotations], indent=2)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['ID', 'Page', 'Selected Text', 'AI Response', 'Category', 'Created At'])
            
            # Data
            for ann in annotations:
                writer.writerow([
                    ann.id,
                    ann.page_number,
                    ann.selected_text,
                    ann.ai_response,
                    ann.category,
                    ann.created_at.strftime("%Y-%m-%d %H:%M:%S")
                ])
            
            return output.getvalue()
        
        elif format == 'markdown':
            lines = ["# PDF Annotations Export", ""]
            
            if page_number is not None:
                lines.append(f"**Page {page_number} Annotations**")
            else:
                lines.append("**All Annotations**")
            lines.append("")
            
            for ann in annotations:
                lines.append(f"## Annotation {ann.id}")
                lines.append(f"**Page:** {ann.page_number}")
                lines.append(f"**Category:** {ann.category}")
                lines.append(f"**Created:** {ann.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")
                lines.append("**Selected Text:**")
                lines.append(f"> {ann.selected_text}")
                lines.append("")
                lines.append("**AI Response:**")
                lines.append(ann.ai_response)
                lines.append("")
                if ann.tags:
                    lines.append(f"**Tags:** {', '.join(ann.tags)}")
                    lines.append("")
                lines.append("---")
                lines.append("")
            
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_selected_annotation(self) -> Optional[str]:
        """Get currently selected annotation ID."""
        return self._state.get_state('annotations.selected_annotation')
    
    def set_selected_annotation(self, annotation_id: Optional[str]) -> None:
        """Set currently selected annotation."""
        self._state.set_state('annotations.selected_annotation', annotation_id)
        logger.debug(f"Selected annotation: {annotation_id}") 