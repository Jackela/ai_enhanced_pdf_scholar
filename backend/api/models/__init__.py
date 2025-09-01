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
else:
    # Fallback - use the one from multi_document_models (not ideal but prevents errors)
    from backend.api.models.multi_document_models import SystemHealthResponse

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
    'log_security_event',
    'validate_against_patterns'
]
