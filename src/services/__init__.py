"""
Business Logic Services

This package contains all business logic services that are completely
decoupled from UI frameworks. Services handle core application logic
and can be easily tested in isolation or used with different UI frameworks.

Key Services:
- ChatService: Chat message processing and conversation management
- AnnotationService: PDF annotation creation and management  
- PDFService: PDF document processing and analysis
- RAGService: Document indexing and retrieval-augmented generation
"""

from .chat_service import ChatService
from .annotation_service import AnnotationService
from .pdf_service import PDFService

__all__ = ['ChatService', 'AnnotationService', 'PDFService'] 