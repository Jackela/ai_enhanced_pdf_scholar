"""
API Dependencies

Dependency injection for FastAPI endpoints.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status

from config import Config
from src.controllers.library_controller import LibraryController
from src.database.connection import DatabaseConnection
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)

# Global instances
_db_connection: Optional[DatabaseConnection] = None
_enhanced_rag_service: Optional[EnhancedRAGService] = None
_library_controller: Optional[LibraryController] = None


@lru_cache()
def get_database_path() -> str:
    """Get database file path."""
    db_dir = Path.home() / ".ai_pdf_scholar"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "documents.db")


def get_db() -> DatabaseConnection:
    """Get database connection dependency."""
    global _db_connection

    if _db_connection is None:
        try:
            db_path = get_database_path()
            _db_connection = DatabaseConnection(db_path)
            logger.info(f"Database connection established: {db_path}")
        except Exception as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed",
            )

    return _db_connection


def get_enhanced_rag(
    db: DatabaseConnection = Depends(get_db),
) -> Optional[EnhancedRAGService]:
    """Get enhanced RAG service dependency."""
    global _enhanced_rag_service

    if _enhanced_rag_service is None:
        try:
            # Get API key
            api_key = Config.get_gemini_api_key()
            if not api_key:
                logger.warning("No Gemini API key configured, RAG service unavailable")
                return None

            # Initialize enhanced RAG service
            vector_storage_dir = Path.home() / ".ai_pdf_scholar" / "vector_indexes"
            _enhanced_rag_service = EnhancedRAGService(
                api_key=api_key,
                db_connection=db,
                vector_storage_dir=str(vector_storage_dir),
            )

            logger.info("Enhanced RAG service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize enhanced RAG service: {e}")
            return None

    return _enhanced_rag_service


def get_library_controller(
    db: DatabaseConnection = Depends(get_db),
    enhanced_rag: Optional[EnhancedRAGService] = Depends(get_enhanced_rag),
) -> LibraryController:
    """Get library controller dependency."""
    global _library_controller

    if _library_controller is None:
        try:
            _library_controller = LibraryController(
                db_connection=db, enhanced_rag_service=enhanced_rag
            )
            logger.info("Library controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize library controller: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Library controller initialization failed",
            )

    return _library_controller


def require_rag_service(
    rag_service: Optional[EnhancedRAGService] = Depends(get_enhanced_rag),
) -> EnhancedRAGService:
    """Require RAG service to be available."""
    if rag_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service is not available. Please configure Gemini API key.",
        )
    return rag_service


def get_upload_directory() -> Path:
    """Get upload directory for temporary files."""
    upload_dir = Path.home() / ".ai_pdf_scholar" / "uploads"
    upload_dir.mkdir(exist_ok=True)
    return upload_dir


def get_documents_directory() -> Path:
    """Get permanent documents storage directory."""
    docs_dir = Path.home() / ".ai_pdf_scholar" / "documents"
    docs_dir.mkdir(exist_ok=True)
    return docs_dir


def validate_document_access(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
):
    """Validate that document exists and is accessible."""
    document = controller.get_document_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return document


# Configuration helpers
@lru_cache()
def get_api_config() -> dict:
    """Get API configuration."""
    return {
        "max_file_size_mb": 100,
        "allowed_file_types": [".pdf"],
        "max_query_length": 2000,
        "cache_enabled": True,
        "websocket_enabled": True,
        "version": "2.0.0",
    }
