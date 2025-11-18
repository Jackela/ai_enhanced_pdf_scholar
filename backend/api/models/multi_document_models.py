"""
Multi-Document RAG API Models
Pydantic models for multi-document collection and query endpoints.
"""

import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Configure security validation logger
security_logger = logging.getLogger("security.validation")

# Security validation constants and patterns
DANGEROUS_SQL_PATTERNS = [
    r"--[\s]*",  # SQL comments
    r";[\s]*",  # Statement terminators
    r"/\*.*?\*/",  # Block comments
    r"\bexec(ute)?\b",  # Execute commands
    r"\bsp_\w+\b",  # Stored procedures
    r"\bxp_\w+\b",  # Extended procedures
    r"\bunion\b.*\bselect\b",  # Union attacks
    r"\binsert\b.*\binto\b",  # Insert statements
    r"\bupdate\b.*\bset\b",  # Update statements
    r"\bdelete\b.*\bfrom\b",  # Delete statements
    r"\bdrop\b.*\btable\b",  # Drop statements
    r"\bcreate\b.*\btable\b",  # Create statements
    r"\balter\b.*\btable\b",  # Alter statements
    r"\bgrant\b",  # Grant statements
    r"\brevoke\b",  # Revoke statements
    r"'\s*(or|and)\s*['\"]\d+['\"]\s*=\s*['\"]\d+['\"]",  # Classic OR/AND injection
    r"'\s*(or|and)\s*\d+\s*=\s*\d+",  # Numeric OR/AND injection
    r"\bor\b\s+\d+\s*=\s*\d+",  # OR 1=1 style attacks
    r"\band\b\s+\d+\s*=\s*\d+",  # AND 1=1 style attacks
    r"'\s*or\s*'",  # Single quote OR attacks
    r'"\s*or\s*"',  # Double quote OR attacks
    r"'\s*and\s*'",  # Single quote AND attacks
    r'"\s*and\s*"',  # Double quote AND attacks
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",  # Script tags
    r"javascript:",  # JavaScript protocol
    r"on\w+\s*=",  # Event handlers
    r"<iframe[^>]*>",  # Iframe tags
    r"<object[^>]*>",  # Object tags
    r"<embed[^>]*>",  # Embed tags
    r"<link[^>]*>",  # Link tags
    r"<meta[^>]*>",  # Meta tags
    r"eval\s*\(",  # Eval function
    r"expression\s*\(",  # CSS expressions
]

ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "text/plain": [".txt"],
    "application/json": [".json"],
}

MAX_FILENAME_LENGTH = 255


class BaseResponse(BaseModel):
    """Base response model."""

    success: bool = True
    message: str | None = None


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = False
    error: str | None = None
    detail: str | None = None
    error_code: str | None = None


class DocumentSourceResponse(BaseModel):
    """Document source in query results."""

    document_id: int
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    excerpt: str
    page_number: int | None = None
    chunk_id: str | None = None


class CrossReferenceResponse(BaseModel):
    """Cross-reference between documents."""

    source_doc_id: int
    target_doc_id: int
    relation_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: str | None = None


class CreateCollectionRequest(BaseModel):
    """Request to create a new document collection."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    document_ids: list[int] = Field(..., min_items=1)


class UpdateCollectionRequest(BaseModel):
    """Request to update a document collection."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class AddDocumentRequest(BaseModel):
    """Request to add a document to collection."""

    document_id: int = Field(..., gt=0)


class RemoveDocumentRequest(BaseModel):
    """Request to remove a document from collection."""

    document_id: int = Field(..., gt=0)


class CollectionResponse(BaseModel):
    """Response for collection data."""

    id: int
    name: str
    description: str | None
    document_ids: list[int]
    document_count: int
    created_at: str | None
    updated_at: str | None


class CollectionListResponse(BaseModel):
    """Response for collection list."""

    collections: list[CollectionResponse]
    total_count: int
    page: int
    limit: int


class CrossDocumentQueryRequest(BaseModel):
    """Request for cross-document query."""

    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)
    user_id: str | None = None


class MultiDocumentQueryResponse(BaseModel):
    """Response for multi-document query."""

    id: int
    query: str
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[DocumentSourceResponse]
    cross_references: list[CrossReferenceResponse]
    processing_time_ms: int
    tokens_used: int | None = None
    status: str
    created_at: str


class QueryHistoryResponse(BaseModel):
    """Response for query history."""

    queries: list[MultiDocumentQueryResponse]
    total_count: int
    page: int
    limit: int


class CollectionIndexResponse(BaseModel):
    """Response for collection index information."""

    id: int
    collection_id: int
    index_path: str
    embedding_model: str
    chunk_count: int | None
    created_at: str


class CollectionStatisticsResponse(BaseModel):
    """Response for collection statistics."""

    collection_id: int
    name: str
    document_count: int
    total_file_size: int
    avg_file_size: int
    created_at: str | None
    recent_queries: int = 0
    avg_query_time_ms: float | None = None


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    success: bool
    message: str
    document_id: int | None = None
    filename: str | None = None
    file_size: int | None = None


class DocumentDeleteResponse(BaseModel):
    """Response after document deletion."""

    success: bool
    message: str
    document_id: int | None = None


class DocumentMetadata(BaseModel):
    """Document metadata information."""

    id: int
    filename: str
    file_path: str
    file_size: int
    file_type: str | None = None
    content_hash: str
    upload_date: str
    page_count: int | None = None


class DocumentListResponse(BaseModel):
    """Response for document list."""

    documents: list[DocumentMetadata]
    total_count: int
    page: int = 1
    limit: int = 20


class DocumentStats(BaseModel):
    """Document statistics."""

    total_documents: int
    total_size_bytes: int
    avg_document_size: float
    total_pages: int | None = None


class QueryResult(BaseModel):
    """Result of a query operation."""

    query: str
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[str]
    processing_time_ms: int


class CrossDocumentInsight(BaseModel):
    """Cross-document insight from analysis."""

    insight_type: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    related_documents: list[int]


class DocumentReference(BaseModel):
    """Reference to a document."""

    document_id: int
    title: str | None = None
    excerpt: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class HealthStatus(str, Enum):
    """Health status enum."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Component health information."""

    name: str
    status: HealthStatus
    message: str | None = None
    metrics: dict[str, Any] | None = None


class SystemHealthResponse(BaseModel):
    """System health response."""

    status: HealthStatus
    components: list[ComponentHealth]
    uptime_seconds: float | None = None
    version: str | None = None


class DocumentBase(BaseModel):
    """Base document model."""

    title: str = Field(..., min_length=1, max_length=500)
    file_path: str | None = None
    file_size: int = Field(..., ge=0, le=1024 * 1024 * 1024)  # 1GB max
    file_type: str | None = Field(
        None,
        description="Normalized file type/extension (e.g., .pdf)",
        min_length=2,
        max_length=20,
    )
    page_count: int | None = Field(None, ge=0, le=10000)


class DocumentResponse(DocumentBase):
    """Document response model."""

    id: int
    file_hash: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DocumentImportResponse(BaseResponse):
    """Document import response."""

    document: DocumentResponse | None = None


class DocumentQueryParams(BaseModel):
    """Document query parameters."""

    search_query: str | None = Field(None, max_length=1000)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    sort_by: str | None = None
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class DocumentUpdate(BaseModel):
    """Document update model."""

    title: str | None = Field(None, min_length=1, max_length=500)
    metadata: dict[str, Any] | None = None


class IntegrityCheckResponse(BaseResponse):
    """Document integrity check response."""

    document_id: int
    exists: bool
    file_exists: bool
    hash_match: bool | None = None


class SecureFileUpload(BaseModel):
    """Secure file upload validation model."""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(..., ge=0, le=1024 * 1024 * 1024)


class SecurityValidationErrorResponse(ErrorResponse):
    """Security validation error response model."""

    error_code: str = "SECURITY_VALIDATION_ERROR"
    field: str = Field(..., description="Field that failed validation")
    pattern: str | None = Field(None, description="Pattern that matched")


class CleanupRequest(BaseModel):
    """Cleanup request model."""

    remove_orphaned: bool = True
    remove_duplicates: bool = False
    verify_integrity: bool = True


class CleanupResponse(BaseResponse):
    """Cleanup response model."""

    removed_count: int = 0
    duplicate_count: int = 0
    errors: list[str] = Field(default_factory=list)


class DuplicateGroup(BaseModel):
    """Group of duplicate documents."""

    hash: str
    documents: list[DocumentResponse]
    count: int


class DuplicatesResponse(BaseResponse):
    """Response for duplicate detection."""

    duplicate_groups: list[DuplicateGroup]
    total_duplicates: int
    space_wasted: int


class LibraryStatsResponse(BaseResponse):
    """Library statistics response."""

    total_documents: int
    total_size: int
    average_size: float
    file_types: dict[str, int] = Field(default_factory=dict)
    recent_documents: int = 0


class RAGQueryRequest(BaseModel):
    """RAG query request."""

    query: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None
    session_id: str | None = None
    max_results: int = Field(5, ge=1, le=20)


class RAGQueryResponse(BaseResponse):
    """RAG query response."""

    query: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    processing_time_ms: int = 0


class SessionStartRequest(BaseModel):
    """Session start request."""

    user_id: str
    session_type: str = "default"
    metadata: dict[str, Any] | None = None


class SessionInfoResponse(BaseResponse):
    """Session information response."""

    session_id: str
    user_id: str
    created_at: str
    last_active: str
    query_count: int = 0


class SessionQueryResponse(BaseResponse):
    """Session query response."""

    session_id: str
    queries: list[RAGQueryResponse] = Field(default_factory=list)
    total_queries: int = 0


class SortOrder(str, Enum):
    """Sort order enumeration."""

    ASC = "asc"
    DESC = "desc"


class DocumentSortField(str, Enum):
    """Document sorting field enumeration."""

    TITLE = "title"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    FILE_SIZE = "file_size"
    PAGE_COUNT = "page_count"


class DocumentCreate(BaseModel):
    """Document creation request model."""

    title: str = Field(..., min_length=1, max_length=500)
    file_path: str
    file_hash: str
    file_size: int = Field(gt=0)
    page_count: int = Field(gt=0)
    metadata: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)


class LibraryInitRequest(BaseModel):
    """Library initialization request."""

    reset_database: bool = False
    create_indexes: bool = True


class CacheClearResponse(BaseResponse):
    """Cache clear response."""

    cleared_count: int = 0
    cache_type: str | None = None


class CacheStatsResponse(BaseResponse):
    """Cache statistics response."""

    hit_rate: float = 0.0
    miss_rate: float = 0.0
    total_hits: int = 0
    total_misses: int = 0
    cache_size: int = 0
    max_size: int = 0


class IndexBuildRequest(BaseModel):
    """Index build request."""

    document_ids: list[int] | None = None
    force_rebuild: bool = False
    chunk_size: int = Field(512, ge=128, le=2048)


class IndexBuildResponse(BaseResponse):
    """Index build response."""

    indexed_documents: int = 0
    total_chunks: int = 0
    build_time_ms: int = 0


class IndexStatusResponse(BaseResponse):
    """Index status response."""

    is_built: bool = False
    document_count: int = 0
    chunk_count: int = 0
    last_updated: str | None = None


class ConfigurationResponse(BaseResponse):
    """Configuration response."""

    config: dict[str, Any] = Field(default_factory=dict)
    environment: str = "development"


class ConfigurationUpdate(BaseModel):
    """Configuration update request."""

    settings: dict[str, Any] = Field(default_factory=dict)


class SecurityValidationError(ValueError):
    """Custom exception for security validation failures."""

    def __init__(self, field: str, message: str, pattern: str | None = None):
        self.field = field
        self.pattern = pattern
        super().__init__(f"Security validation failed for field '{field}': {message}")


def log_security_event(
    event_type: str, field: str, value: str, details: str | None = None
):
    """Log security validation events for monitoring and alerting."""
    security_logger.warning(
        f"Security Event: Type={event_type}, Field={field}, "
        f"Value: {value[:50]}{'...' if len(value) > 50 else ''}, "
        f"Details: {details or 'None'}"
    )


def validate_against_patterns(
    value: str,
    patterns: list[str],
    field_name: str,
    event_type: str = "dangerous_pattern",
) -> str:
    """Validate string against dangerous patterns."""
    if not value:
        return value

    value_lower = value.lower()
    for pattern in patterns:
        if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
            log_security_event(
                event_type, field_name, value, f"Matched pattern: {pattern}"
            )
            raise SecurityValidationError(
                field_name,
                f"Contains potentially dangerous pattern: {pattern}",
                pattern,
            )
    return value
