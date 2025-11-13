"""
API Dependencies
Dependency injection for FastAPI endpoints.
"""

import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, HTTPException, status

from backend.api.error_handling import ResourceNotFoundException, SystemException
from backend.api.websocket_manager import WebSocketManager
from backend.config.application_config import get_application_config
from config import Config
from src.controllers.library_controller import LibraryController
from src.database.connection import DatabaseConnection
from src.interfaces.rag_service_interfaces import (
    IRAGCacheManager,
    IRAGHealthChecker,
    IRAGResourceManager,
)
from src.interfaces.repository_interfaces import IDocumentRepository
from src.interfaces.service_interfaces import IDocumentLibraryService
from src.prompt_management.manager import PromptManager
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.content_hash_service import ContentHashService
from src.services.document_library_service import DocumentLibraryService
from src.services.document_preview_service import (
    DocumentPreviewService,
    PreviewSettings,
)
from src.services.enhanced_rag_service import EnhancedRAGService
from src.services.multi_document_rag_service import MultiDocumentRAGService

logger = logging.getLogger(__name__)
# Global instances
_db_connection: DatabaseConnection | None = None
_enhanced_rag_service: EnhancedRAGService | None = None
_library_controller: LibraryController | None = None
_multi_document_rag_service: MultiDocumentRAGService | None = None
_document_repository: IDocumentRepository | None = None
_document_library_service: IDocumentLibraryService | None = None
_document_preview_service: DocumentPreviewService | None = None
_vector_index_repository: VectorIndexRepository | None = None
_rag_cache_manager: IRAGCacheManager | None = None
_rag_health_checker: IRAGHealthChecker | None = None
_rag_resource_manager: IRAGResourceManager | None = None


@lru_cache
def get_database_path() -> str:
    """Get database file path."""
    db_dir = Path.home() / ".ai_pdf_scholar"
    db_dir.mkdir(exist_ok=True)
    return str(db_dir / "documents.db")


_db_lock = threading.Lock()
_doc_repo_lock = threading.Lock()


def get_db() -> DatabaseConnection:
    """Get database connection dependency using proper singleton pattern."""
    global _db_connection
    if _db_connection is None:
        with _db_lock:
            # Double-check pattern for thread safety
            if _db_connection is None:
                try:
                    db_path = get_database_path()
                    # Try to get existing instance first
                    try:
                        _db_connection = DatabaseConnection.get_instance(db_path)
                    except ValueError:
                        # Create new instance if none exists
                        # Disable monitoring for API performance - was blocking server startup
                        _db_connection = DatabaseConnection(
                            db_path, enable_monitoring=False
                        )
                    logger.info(f"Database connection established: {db_path}")
                except Exception as e:
                    logger.error(f"Failed to establish database connection: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database connection failed",
                    ) from e
    return _db_connection


def get_database() -> DatabaseConnection:
    """Backward-compatible alias for legacy imports."""
    return get_db()


def get_enhanced_rag(
    db: DatabaseConnection = Depends(get_db),
) -> EnhancedRAGService | None:
    """Get enhanced RAG service dependency."""
    global _enhanced_rag_service
    if _enhanced_rag_service is None:
        try:
            # Get API key
            api_key = Config.get_gemini_api_key()
            if not api_key:
                logger.warning("No Gemini API key configured, RAG service unavailable")
                return None

            # Check if it's a test/placeholder API key
            test_api_keys = [
                "your_gemini_api_key_here",
                "your_actual_gemini_api_key_here",
                "test_api_key_for_local_testing",
                "test-api-key",
            ]

            is_test_mode = api_key in test_api_keys or api_key.startswith("test")

            if is_test_mode:
                logger.warning(
                    f"Test/placeholder API key detected: {api_key[:10]}... "
                    "Initializing RAG service in test mode"
                )

            # Initialize PromptManager
            prompt_manager = PromptManager(template_dir="prompt_templates")

            # Initialize enhanced RAG service
            vector_storage_dir = Path.home() / ".ai_pdf_scholar" / "vector_indexes"
            _enhanced_rag_service = EnhancedRAGService(
                api_key=api_key,
                db_connection=db,
                vector_storage_dir=str(vector_storage_dir),
                test_mode=is_test_mode,
                prompt_manager=prompt_manager,
            )

            if is_test_mode:
                logger.info("Enhanced RAG service initialized in TEST MODE")
            else:
                logger.info("Enhanced RAG service initialized with valid API key")

        except Exception as e:
            logger.error(f"Failed to initialize enhanced RAG service: {e}")
            return None
    return _enhanced_rag_service


def get_library_controller(
    db: DatabaseConnection = Depends(get_db),
    enhanced_rag: EnhancedRAGService | None = Depends(get_enhanced_rag),
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
            ) from e
    return _library_controller


def require_rag_service(
    rag_service: EnhancedRAGService | None = Depends(get_enhanced_rag),
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


def get_documents_dir() -> Path:
    """Backward-compatible alias for FastAPI dependencies."""
    return get_documents_directory()


def validate_document_access(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
):
    """Validate that document exists and is accessible."""
    try:
        document = controller.get_document_by_id(document_id)
        if not document:
            raise ResourceNotFoundException(
                resource_type="document", resource_id=str(document_id)
            )
        return document
    except Exception as e:
        if "not found" in str(e).lower():
            raise ResourceNotFoundException(
                resource_type="document", resource_id=str(document_id)
            ) from e
        raise SystemException(
            message="Failed to validate document access", error_type="database"
        ) from e


# Configuration helpers
@lru_cache
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


def get_document_repository(
    db: DatabaseConnection = Depends(get_db),
) -> IDocumentRepository:
    """Provide a shared DocumentRepository instance."""
    global _document_repository
    if _document_repository is None:
        with _doc_repo_lock:
            if _document_repository is None:
                _document_repository = DocumentRepository(db)
                logger.info("Document repository initialized")
    return _document_repository


def get_document_preview_service(
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> DocumentPreviewService:
    """Get the preview service singleton."""
    global _document_preview_service
    if _document_preview_service is None:
        config = get_application_config()
        preview_config = getattr(config, "preview", None)
        if not preview_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document previews are not configured",
            )
        settings = PreviewSettings(
            enabled=preview_config.enabled,
            cache_dir=Path(preview_config.cache_dir),
            max_width=preview_config.max_width,
            min_width=preview_config.min_width,
            thumbnail_width=preview_config.thumbnail_width,
            max_page_number=preview_config.max_page_number,
            cache_ttl_seconds=preview_config.cache_ttl_seconds,
        )
        _document_preview_service = DocumentPreviewService(doc_repo, settings)
    return _document_preview_service


def get_document_library_service(
    repo: IDocumentRepository = Depends(get_document_repository),
) -> IDocumentLibraryService:
    """Provide the DocumentLibraryService for document routes."""
    global _document_library_service
    if _document_library_service is None:
        with _doc_repo_lock:
            if _document_library_service is None:
                hash_service = ContentHashService()
                _document_library_service = DocumentLibraryService(
                    document_repository=repo,
                    hash_service=hash_service,
                )
                logger.info("Document library service initialized")
    return _document_library_service


def get_vector_index_repository(
    db: DatabaseConnection = Depends(get_db),
) -> VectorIndexRepository:
    """Provide a shared VectorIndexRepository instance."""
    global _vector_index_repository
    if _vector_index_repository is None:
        with _doc_repo_lock:
            if _vector_index_repository is None:
                _vector_index_repository = VectorIndexRepository(db)
                logger.info("Vector index repository initialized")
    return _vector_index_repository


def get_rag_cache_manager() -> IRAGCacheManager:
    """Provide a placeholder cache manager until the real service is wired in."""
    global _rag_cache_manager
    if _rag_cache_manager is None:
        _rag_cache_manager = _NullCacheManager()
    return _rag_cache_manager


def get_rag_health_checker() -> IRAGHealthChecker:
    """Provide a placeholder health checker for the index routes."""
    global _rag_health_checker
    if _rag_health_checker is None:
        _rag_health_checker = _NullHealthChecker()
    return _rag_health_checker


def get_rag_resource_manager() -> IRAGResourceManager:
    """Provide a placeholder resource manager for the index maintenance routes."""
    global _rag_resource_manager
    if _rag_resource_manager is None:
        _rag_resource_manager = _NullResourceManager()
    return _rag_resource_manager


def get_rag_query_executor() -> None:
    """Placeholder for the future RAG query executor."""
    logger.warning("RAG query executor requested but not configured")
    return None


class _NullCacheManager(IRAGCacheManager):
    def get_cached_query(self, *, query: str, document_id: int) -> str | None:
        return None

    def cache_query_result(
        self, query: str, document_id: int, result: str, ttl_seconds: int
    ) -> None:
        return None

    def invalidate_document_cache(self, document_id: int) -> int:
        return 0

    def get_cache_stats(self) -> dict[str, int]:
        return {"entries": 0, "hits": 0, "misses": 0}


class _NullHealthChecker(IRAGHealthChecker):
    def perform_health_check(self) -> dict[str, Any]:
        return {"healthy": True, "issues": []}


class _NullResourceManager(IRAGResourceManager):
    def cleanup_orphaned_indexes(self) -> int:
        return 0

    def get_storage_stats(self) -> dict[str, Any]:
        return {
            "total_indexes": 0,
            "storage_bytes": 0,
            "avg_index_size_bytes": 0,
        }


# WebSocket Manager dependency
_websocket_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """Get WebSocket manager dependency."""
    global _websocket_manager
    if _websocket_manager is None:
        try:
            _websocket_manager = WebSocketManager()
            logger.info("WebSocket manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket manager: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WebSocket manager initialization failed",
            ) from e
    return _websocket_manager


def get_multi_document_rag_service(
    db: DatabaseConnection = Depends(get_db),
    enhanced_rag: Optional[EnhancedRAGService] = Depends(get_enhanced_rag),
) -> MultiDocumentRAGService:
    """Get multi-document RAG service dependency."""
    global _multi_document_rag_service
    if _multi_document_rag_service is None:
        try:
            # Import repositories here to avoid circular imports
            from src.repositories.document_repository import DocumentRepository
            from src.repositories.multi_document_repositories import (
                CrossDocumentQueryRepository,
                MultiDocumentCollectionRepository,
                MultiDocumentIndexRepository,
            )

            # Create repository instances
            doc_repo = DocumentRepository(db)
            collection_repo = MultiDocumentCollectionRepository(db)
            index_repo = MultiDocumentIndexRepository(db)
            query_repo = CrossDocumentQueryRepository(db)

            # Create service instance
            index_storage_path = Path.home() / ".ai_pdf_scholar" / "multi_doc_indexes"
            _multi_document_rag_service = MultiDocumentRAGService(
                collection_repository=collection_repo,
                index_repository=index_repo,
                query_repository=query_repo,
                document_repository=doc_repo,
                enhanced_rag_service=enhanced_rag,
                index_storage_path=str(index_storage_path),
            )
            logger.info("Multi-document RAG service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize multi-document RAG service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Multi-document RAG service initialization failed",
            ) from e
    return _multi_document_rag_service
