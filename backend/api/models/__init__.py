"""
API Models Package
==================

This module contains all Pydantic models for API request/response handling.
"""

# Import SystemHealthResponse from the main models.py file after multi_document imports
# This avoids the circular import issue
import importlib
import os
import sys

from backend.api.models.multi_document_models import (
    ALLOWED_MIME_TYPES,
    DANGEROUS_SQL_PATTERNS,
    MAX_FILENAME_LENGTH,
    XSS_PATTERNS,
    BaseResponse,
    CacheClearResponse,
    CacheStatsResponse,
    CleanupRequest,
    CleanupResponse,
    CollectionStatisticsResponse,
    ComponentHealth,
    ConfigurationResponse,
    ConfigurationUpdate,
    CrossDocumentInsight,
    CrossDocumentQueryRequest,
    DocumentBase,
    DocumentCreate,
    DocumentDeleteResponse,
    DocumentImportResponse,
    # DocumentListResponse, -- REMOVED: import from main models.py instead
    DocumentMetadata,
    # DocumentQueryParams, -- REMOVED: import from main models.py instead
    DocumentReference,
    DocumentResponse,
    DocumentSortField,
    DocumentStats,
    DocumentUpdate,
    DocumentUploadResponse,
    DuplicateGroup,
    DuplicatesResponse,
    ErrorResponse,
    HealthStatus,
    IndexBuildRequest,
    IndexBuildResponse,
    IndexStatusResponse,
    IntegrityCheckResponse,
    LibraryInitRequest,
    LibraryStatsResponse,
    MultiDocumentQueryResponse,
    QueryResult,
    RAGQueryRequest,
    RAGQueryResponse,
    SecureFileUpload,
    SecurityValidationError,
    SecurityValidationErrorResponse,
    SessionInfoResponse,
    SessionQueryResponse,
    SessionStartRequest,
    SortOrder,
    # SystemHealthResponse removed - conflicting with the one in models.py
    log_security_event,
    validate_against_patterns,
)

# Get the path to models.py in the parent directory
models_path = os.path.join(os.path.dirname(__file__), "..", "models.py")
if os.path.exists(models_path):
    # Load the module directly
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backend_api_models_main", models_path
    )
    models_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models_main)
    SystemHealthResponse = models_main.SystemHealthResponse
    SearchFilter = models_main.SearchFilter
    DocumentQueryParams = (
        models_main.DocumentQueryParams
    )  # Import from main models.py with security validation
    DocumentListResponse = (
        models_main.DocumentListResponse
    )  # Import from main models.py with correct structure

    # CRITICAL: Import RAG models from main models.py (has document_id field)
    # The multi_document_models version has user_id/session_id instead
    RAGQueryRequest = models_main.RAGQueryRequest  # Override multi_document import
    RAGQueryResponse = models_main.RAGQueryResponse  # Override multi_document import
    IndexBuildRequest = models_main.IndexBuildRequest  # Override multi_document import
    IndexBuildResponse = (
        models_main.IndexBuildResponse
    )  # Override multi_document import
    IndexStatusResponse = (
        models_main.IndexStatusResponse
    )  # Override multi_document import
    CacheStatsResponse = (
        models_main.CacheStatsResponse
    )  # Override multi_document import
    CacheClearResponse = (
        models_main.CacheClearResponse
    )  # Override multi_document import

    # CRITICAL: Import library models from main models.py (correct field names)
    # multi_document_models has different fields (removed_count vs orphaned_removed, etc.)
    CleanupResponse = models_main.CleanupResponse  # Override multi_document import
    DuplicatesResponse = (
        models_main.DuplicatesResponse
    )  # Override multi_document import
    DuplicateGroup = models_main.DuplicateGroup  # Override multi_document import

    sanitize_html_content = models_main.sanitize_html_content
    validate_filename = models_main.validate_filename
    validate_file_content_type = models_main.validate_file_content_type
    ValidationErrorResponse = models_main.ValidationErrorResponse
    SecurityValidationErrorResponse = models_main.SecurityValidationErrorResponse
else:
    # Fallback - use the one from multi_document_models (not ideal but prevents errors)
    # Create a basic SearchFilter fallback
    from pydantic import BaseModel, Field

    from backend.api.models.multi_document_models import (
        DocumentListResponse as MultiDocumentListResponse,
    )
    from backend.api.models.multi_document_models import (
        DocumentQueryParams as MultiDocumentQueryParams,
    )
    from backend.api.models.multi_document_models import SystemHealthResponse

    # Use the multi_document version as fallback (less secure but functional)
    DocumentQueryParams = MultiDocumentQueryParams
    DocumentListResponse = MultiDocumentListResponse

    class SearchFilter(BaseModel):
        query: str | None = Field(None, description="Search query")
        show_missing_files: bool = Field(False, description="Include missing files")

    # Fallback functions
    def sanitize_html_content(value: str) -> str:
        """Fallback HTML sanitization"""
        import html

        return html.escape(value, quote=True) if value else value

    def validate_filename(filename: str) -> str:
        """Fallback filename validation"""
        return filename.strip() if filename else ""

    def validate_file_content_type(content_type: str, filename: str) -> str:
        """Fallback content type validation"""
        return content_type

    class ValidationErrorResponse(ErrorResponse):
        """Fallback validation error response."""

        message: str = "Validation Error"
        errors: list[dict[str, str]] = []

        @classmethod
        def from_pydantic_error(cls, error):
            error_items = []
            try:
                error_items = error.errors()
            except Exception:
                error_items = []
            return cls(
                message="Validation Error",
                error_code="VALIDATION_ERROR",
                details={"errors": error_items},
            )

    class SecurityValidationErrorResponse(ErrorResponse):
        """Fallback security validation response."""

        error_code: str = "SECURITY_VALIDATION_ERROR"
        field: str | None = None
        pattern: str | None = None

        @classmethod
        def from_security_error(cls, error):
            return cls(
                message=str(error),
                field=getattr(error, "field", None),
                pattern=getattr(error, "pattern", None),
                error_code="SECURITY_VALIDATION_ERROR",
            )


__all__ = [
    "DANGEROUS_SQL_PATTERNS",
    "XSS_PATTERNS",
    "ALLOWED_MIME_TYPES",
    "MAX_FILENAME_LENGTH",
    "BaseResponse",
    "ErrorResponse",
    "CacheClearResponse",
    "CacheStatsResponse",
    "CleanupRequest",
    "CleanupResponse",
    "ConfigurationResponse",
    "ConfigurationUpdate",
    "DocumentBase",
    "DocumentCreate",
    "DocumentResponse",
    "DocumentImportResponse",
    "DocumentQueryParams",
    "DocumentSortField",
    "DocumentUpdate",
    "IndexBuildRequest",
    "IndexBuildResponse",
    "IndexStatusResponse",
    "IntegrityCheckResponse",
    "SecureFileUpload",
    "SecurityValidationErrorResponse",
    "DocumentUploadResponse",
    "CrossDocumentQueryRequest",
    "MultiDocumentQueryResponse",
    "DocumentListResponse",
    "DocumentMetadata",
    "QueryResult",
    "CrossDocumentInsight",
    "DocumentReference",
    "DocumentDeleteResponse",
    "DuplicateGroup",
    "DuplicatesResponse",
    "LibraryInitRequest",
    "LibraryStatsResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "SessionInfoResponse",
    "SessionQueryResponse",
    "SessionStartRequest",
    "SortOrder",
    "CollectionStatisticsResponse",
    "DocumentStats",
    "SystemHealthResponse",  # Now imported correctly from models.py
    "HealthStatus",
    "ComponentHealth",
    "SecurityValidationError",
    "SearchFilter",
    "log_security_event",
    "validate_against_patterns",
    "sanitize_html_content",
    "validate_filename",
    "validate_file_content_type",
]
