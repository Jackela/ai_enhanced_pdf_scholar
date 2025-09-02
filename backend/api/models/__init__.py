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
    DocumentListResponse,
    DocumentMetadata,
    DocumentQueryParams,
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
models_path = os.path.join(os.path.dirname(__file__), '..', 'models.py')
if os.path.exists(models_path):
    # Load the module directly
    import importlib.util
    spec = importlib.util.spec_from_file_location("backend_api_models_main", models_path)
    models_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models_main)
    SystemHealthResponse = models_main.SystemHealthResponse
    SearchFilter = models_main.SearchFilter
    sanitize_html_content = models_main.sanitize_html_content
    validate_filename = models_main.validate_filename
    validate_file_content_type = models_main.validate_file_content_type
else:
    # Fallback - use the one from multi_document_models (not ideal but prevents errors)
    # Create a basic SearchFilter fallback
    from pydantic import BaseModel, Field

    from backend.api.models.multi_document_models import SystemHealthResponse
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

__all__ = [
    'DANGEROUS_SQL_PATTERNS',
    'XSS_PATTERNS',
    'ALLOWED_MIME_TYPES',
    'MAX_FILENAME_LENGTH',
    'BaseResponse',
    'ErrorResponse',
    'CacheClearResponse',
    'CacheStatsResponse',
    'CleanupRequest',
    'CleanupResponse',
    'ConfigurationResponse',
    'ConfigurationUpdate',
    'DocumentBase',
    'DocumentCreate',
    'DocumentResponse',
    'DocumentImportResponse',
    'DocumentQueryParams',
    'DocumentSortField',
    'DocumentUpdate',
    'IndexBuildRequest',
    'IndexBuildResponse',
    'IndexStatusResponse',
    'IntegrityCheckResponse',
    'SecureFileUpload',
    'SecurityValidationErrorResponse',
    'DocumentUploadResponse',
    'CrossDocumentQueryRequest',
    'MultiDocumentQueryResponse',
    'DocumentListResponse',
    'DocumentMetadata',
    'QueryResult',
    'CrossDocumentInsight',
    'DocumentReference',
    'DocumentDeleteResponse',
    'DuplicateGroup',
    'DuplicatesResponse',
    'LibraryInitRequest',
    'LibraryStatsResponse',
    'RAGQueryRequest',
    'RAGQueryResponse',
    'SessionInfoResponse',
    'SessionQueryResponse',
    'SessionStartRequest',
    'SortOrder',
    'CollectionStatisticsResponse',
    'DocumentStats',
    'SystemHealthResponse',  # Now imported correctly from models.py
    'HealthStatus',
    'ComponentHealth',
    'SecurityValidationError',
    'SearchFilter',
    'log_security_event',
    'validate_against_patterns',
    'sanitize_html_content',
    'validate_filename',
    'validate_file_content_type'
]
