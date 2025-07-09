"""
Index Worker Module

This module provides the IndexWorker class for performing PDF indexing operations
asynchronously in a separate thread to prevent UI freezing.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.rag_service import RAGService

logger = logging.getLogger(__name__)


class IndexWorker(QThread):
    """
    {
        "name": "IndexWorker",
        "version": "1.0.0",
        "description": "A QThread subclass to perform PDF indexing operations asynchronously.",
        "dependencies": ["RAGService"],
        "interface": {
            "inputs": [
                {"name": "rag_service", "type": "RAGService"},
                {"name": "pdf_path", "type": "string"}
            ],
            "outputs": "Emits signals for indexing completion or errors"
        }
    }
    
    Executes PDF indexing operations in a separate thread to prevent the UI
    from freezing. It handles exceptions from the RAG service and emits
    appropriate signals for success or failure.
    """
    
    # Signal emitted when indexing completes successfully
    indexing_completed = pyqtSignal(str)  # Emits the PDF path that was indexed
    
    # Signal emitted when indexing fails
    indexing_failed = pyqtSignal(str)  # Emits an error message string
    
    # Signal emitted for progress updates (optional for future use)
    progress_update = pyqtSignal(str)  # Emits progress message

    def __init__(self, pdf_path: str, rag_service: 'RAGService', parent=None):
        """
        Initialize the IndexWorker.
        
        @param {string} pdf_path - The path to the PDF file to index.
        @param {RAGService} rag_service - An instance of RAGService for indexing operations.
        @param {QObject} parent - The parent QObject.
        @raises {ValueError} - If required parameters are missing or invalid.
        """
        super().__init__(parent)
        
        # Validate inputs as expected by tests
        if not isinstance(pdf_path, str) or not pdf_path or not pdf_path.strip():
            raise ValueError("PDF path is required and must be a non-empty string")
        
        if rag_service is None:
            raise ValueError("RAG service is required")
        
        self.rag_service = rag_service
        self.pdf_path = pdf_path.strip()
        
        logger.info(f"IndexWorker initialized for PDF: {pdf_path}")

    def run(self):
        """
        Execute the PDF indexing operation in the worker thread.
        Emits appropriate signals based on the result.
        """
        try:
            logger.info(f"Starting indexing operation for: {self.pdf_path}")
            
            # Emit progress update
            self.progress_update.emit("正在为文档创建智能索引...")
            
            # Perform the indexing operation
            self.rag_service.build_index_from_pdf(self.pdf_path)
            
            # Emit success signal
            logger.info(f"Indexing completed successfully for: {self.pdf_path}")
            self.indexing_completed.emit(self.pdf_path)
            
        except Exception as e:
            # Handle any indexing errors
            error_message = f"索引创建失败: {str(e)}"
            logger.error(f"Indexing failed for {self.pdf_path}: {e}")
            self.indexing_failed.emit(error_message)
    
    def get_pdf_path(self) -> str:
        """
        Get the PDF path being processed by this worker.
        
        @returns {string} The PDF file path.
        """
        return self.pdf_path 