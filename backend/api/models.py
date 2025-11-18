"""
API Data Models
Pydantic models for API request/response serialization with comprehensive security validation.
"""

import html
import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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
MAX_PATH_LENGTH = 4096
MAX_SEARCH_QUERY_LENGTH = 500
MAX_TITLE_LENGTH = 500
MAX_METADATA_SIZE = 10240  # 10KB


class SecurityValidationError(ValueError):
    """Custom exception for security validation failures."""

    def __init__(self, field: str, message: str, pattern: str | None = None):
        self.field = field
        self.pattern = pattern
        super().__init__(f"Security validation failed for field '{field}': {message}")


def log_security_event(
    event_type: str, field: str, value: str, details: str | None = None
):
    """Log security validation events."""
    security_logger.warning(
        f"Security event - Type: {event_type}, Field: {field}, "
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


def sanitize_html_content(value: str) -> str:
    """Sanitize HTML content to prevent XSS."""
    if not value:
        return value

    # HTML encode special characters
    sanitized = html.escape(value, quote=True)

    # Additional XSS pattern removal
    for pattern in XSS_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

    return sanitized.strip()


def validate_filename(filename: str) -> str:
    """Validate and sanitize filename."""
    if not filename:
        raise SecurityValidationError("filename", "Filename cannot be empty")

    if len(filename) > MAX_FILENAME_LENGTH:
        raise SecurityValidationError(
            "filename", f"Filename too long (max {MAX_FILENAME_LENGTH} characters)"
        )

    # Check for dangerous characters
    dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\0"]
    for char in dangerous_chars:
        if char in filename:
            raise SecurityValidationError(
                "filename", f"Contains dangerous character: {char}"
            )

    # Check for path traversal attempts
    if ".." in filename or filename.startswith("/") or "\\" in filename:
        raise SecurityValidationError("filename", "Path traversal attempt detected")

    return filename.strip()


def validate_file_content_type(content_type: str, filename: str) -> str:
    """Validate file content type against allowed types."""
    if content_type not in ALLOWED_MIME_TYPES:
        raise SecurityValidationError(
            "content_type",
            f"File type not allowed: {content_type}. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}",
        )

    # Check file extension matches content type
    file_ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
    allowed_extensions = ALLOWED_MIME_TYPES[content_type]

    if file_ext not in allowed_extensions:
        raise SecurityValidationError(
            "filename",
            f"File extension '{file_ext}' doesn't match content type '{content_type}'",
        )

    return content_type


# Base response models
class BaseResponse(BaseModel):
    """Base response model."""

    success: bool = True
    message: str | None = None


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = False
    error_code: str | None = None
    details: dict[str, Any] | None = None


class SecurityValidationErrorResponse(ErrorResponse):
    """Security validation error response model."""

    success: bool = False
    error_code: str = "SECURITY_VALIDATION_ERROR"
    field: str = Field(..., description="Field that failed validation")
    attack_type: str | None = Field(None, description="Type of attack detected")
    pattern_matched: str | None = Field(None, description="Dangerous pattern matched")

    @classmethod
    def from_security_error(
        cls, error: SecurityValidationError
    ) -> "SecurityValidationErrorResponse":
        """Create response from SecurityValidationError."""
        return cls(
            message=f"Security validation failed: {str(error)}",
            field=error.field,
            pattern_matched=error.pattern,
            details={
                "field": error.field,
                "pattern": error.pattern,
                "timestamp": datetime.now().isoformat(),
            },
        )


class ValidationErrorResponse(ErrorResponse):
    """General validation error response model."""

    success: bool = False
    error_code: str = "VALIDATION_ERROR"
    validation_errors: list[dict[str, Any]] = Field(
        default_factory=list, description="List of validation errors"
    )

    @classmethod
    def from_pydantic_error(cls, error) -> "ValidationErrorResponse":
        """Create response from Pydantic ValidationError."""
        validation_errors = [
            {
                "field": ".".join(str(x) for x in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
                "input": str(err.get("input", ""))[:100],  # Limit input display
            }
            for err in error.errors()
        ]

        return cls(
            message="Request validation failed",
            validation_errors=validation_errors,
            details={
                "error_count": len(validation_errors),
                "timestamp": datetime.now().isoformat(),
            },
        )


# Security-focused query parameter models
class DocumentSortField(str, Enum):
    """Enumeration of valid document sort fields for SQL injection prevention."""

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    LAST_ACCESSED = "last_accessed"
    TITLE = "title"
    FILE_SIZE = "file_size"


class SortOrder(str, Enum):
    """Enumeration of valid sort orders for SQL injection prevention."""

    ASC = "asc"
    DESC = "desc"


class DocumentQueryParams(BaseModel):
    """Secure document query parameters with comprehensive validation."""

    search_query: str | None = Field(
        None,
        max_length=MAX_SEARCH_QUERY_LENGTH,
        description="Search documents by title",
    )
    sort_by: DocumentSortField = Field(
        DocumentSortField.CREATED_AT, description="Field to sort by"
    )
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort direction")
    page: int = Field(1, ge=1, le=10000, description="Page number")
    per_page: int = Field(50, ge=1, le=200, description="Items per page")
    show_missing: bool = Field(
        False, description="Include documents with missing files"
    )

    @field_validator("search_query")
    @classmethod
    def validate_search_query(cls, v: str | None) -> str | None:
        """Validate and sanitize search query for security threats."""
        if v is None:
            return v

        # Validate against SQL injection patterns
        validate_against_patterns(
            v, DANGEROUS_SQL_PATTERNS, "search_query", "sql_injection"
        )

        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, "search_query", "xss_attempt")

        # Sanitize HTML content
        sanitized = sanitize_html_content(v)

        # Additional length check after sanitization
        if len(sanitized) > MAX_SEARCH_QUERY_LENGTH:
            raise SecurityValidationError(
                "search_query",
                f"Search query too long after sanitization (max {MAX_SEARCH_QUERY_LENGTH} characters)",
            )

        return sanitized.strip()

    class Config:
        use_enum_values = True


# Document models
class DocumentBase(BaseModel):
    """Base document model with comprehensive security validation."""

    title: str = Field(
        ..., min_length=1, max_length=MAX_TITLE_LENGTH, description="Document title"
    )
    file_path: str | None = Field(
        None, max_length=MAX_PATH_LENGTH, description="File system path"
    )
    file_size: int = Field(
        ...,
        ge=0,
        le=1024 * 1024 * 1024,
        description="File size in bytes",  # 1GB max
    )
    file_type: str | None = Field(
        None,
        min_length=2,
        max_length=20,
        description="Normalized file type/extension (e.g., .pdf)",
    )
    page_count: int | None = Field(None, ge=0, le=10000, description="Number of pages")
    metadata: dict[str, Any] | None = Field(None, description="Document metadata")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate and sanitize document title."""
        # Validate against SQL injection patterns
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, "title", "sql_injection")

        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, "title", "xss_attempt")

        # Sanitize HTML content
        sanitized = sanitize_html_content(v)

        # Additional validation after sanitization
        if not sanitized or not sanitized.strip():
            raise SecurityValidationError(
                "title", "Title cannot be empty after sanitization"
            )

        if len(sanitized) > MAX_TITLE_LENGTH:
            raise SecurityValidationError(
                "title",
                f"Title too long after sanitization (max {MAX_TITLE_LENGTH} characters)",
            )

        return sanitized.strip()

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str | None) -> str | None:
        """Validate file path for security issues."""
        if v is None:
            return v

        # Check for path traversal attempts
        if ".." in v:
            raise SecurityValidationError(
                "file_path", "Path traversal attempt detected"
            )

        # Check for dangerous characters
        dangerous_chars = ["<", ">", "|", "*", "?", "\0"]
        for char in dangerous_chars:
            if char in v:
                raise SecurityValidationError(
                    "file_path", f"Path contains dangerous character: {char}"
                )

        # Validate length
        if len(v) > MAX_PATH_LENGTH:
            raise SecurityValidationError(
                "file_path", f"Path too long (max {MAX_PATH_LENGTH} characters)"
            )

        return v.strip()

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: str | None) -> str | None:
        """Normalize and validate file type extensions."""
        if v is None:
            return v

        normalized = v.strip().lower()
        if not normalized:
            return None

        if len(normalized) > 20:
            raise SecurityValidationError(
                "file_type", "file_type too long (max 20 characters)"
            )

        if any(char in normalized for char in [" ", "<", ">", "|"]):
            raise SecurityValidationError(
                "file_type", "file_type contains unsafe characters"
            )

        if not normalized.startswith("."):
            normalized = f".{normalized}"

        return normalized

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate metadata for security and size limits."""
        if v is None:
            return v

        # Convert to JSON string to check size
        import json

        metadata_json = json.dumps(v)

        if len(metadata_json) > MAX_METADATA_SIZE:
            raise SecurityValidationError(
                "metadata", f"Metadata too large (max {MAX_METADATA_SIZE} bytes)"
            )

        # Sanitize string values in metadata
        sanitized_metadata = {}
        for key, value in v.items():
            # Validate key
            if not isinstance(key, str) or len(key) > 100:
                raise SecurityValidationError(
                    "metadata", f"Invalid metadata key: {key}"
                )

            # Sanitize string values
            if isinstance(value, str):
                # Check for dangerous patterns in string values
                validate_against_patterns(
                    value, DANGEROUS_SQL_PATTERNS, f"metadata.{key}", "sql_injection"
                )
                validate_against_patterns(
                    value, XSS_PATTERNS, f"metadata.{key}", "xss_attempt"
                )
                sanitized_metadata[key] = sanitize_html_content(value)
            else:
                sanitized_metadata[key] = value

        return sanitized_metadata


class DocumentCreate(DocumentBase):
    """Document creation model."""

    check_duplicates: bool = True
    auto_build_index: bool = False


class DocumentUpdate(BaseModel):
    """Document update model with security validation."""

    title: str | None = Field(
        None,
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="Updated document title",
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Updated document metadata"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """Validate and sanitize document title."""
        if v is None:
            return v

        # Validate against SQL injection patterns
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, "title", "sql_injection")

        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, "title", "xss_attempt")

        # Sanitize HTML content
        sanitized = sanitize_html_content(v)

        # Additional validation after sanitization
        if not sanitized or not sanitized.strip():
            raise SecurityValidationError(
                "title", "Title cannot be empty after sanitization"
            )

        if len(sanitized) > MAX_TITLE_LENGTH:
            raise SecurityValidationError(
                "title",
                f"Title too long after sanitization (max {MAX_TITLE_LENGTH} characters)",
            )

        return sanitized.strip()

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate metadata for security and size limits."""
        if v is None:
            return v

        # Convert to JSON string to check size
        import json

        metadata_json = json.dumps(v)

        if len(metadata_json) > MAX_METADATA_SIZE:
            raise SecurityValidationError(
                "metadata", f"Metadata too large (max {MAX_METADATA_SIZE} bytes)"
            )

        # Sanitize string values in metadata
        sanitized_metadata = {}
        for key, value in v.items():
            # Validate key
            if not isinstance(key, str) or len(key) > 100:
                raise SecurityValidationError(
                    "metadata", f"Invalid metadata key: {key}"
                )

            # Sanitize string values
            if isinstance(value, str):
                # Check for dangerous patterns in string values
                validate_against_patterns(
                    value, DANGEROUS_SQL_PATTERNS, f"metadata.{key}", "sql_injection"
                )
                validate_against_patterns(
                    value, XSS_PATTERNS, f"metadata.{key}", "xss_attempt"
                )
                sanitized_metadata[key] = sanitize_html_content(value)
            else:
                sanitized_metadata[key] = value

        return sanitized_metadata


class DocumentResponse(DocumentBase):
    """Document response model."""

    id: int
    file_hash: str
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime | None = None
    is_file_available: bool = True

    class Config:
        from_attributes = True


class DocumentListResponse(BaseResponse):
    """Document list response."""

    documents: list[DocumentResponse]
    total: int
    page: int = 1
    per_page: int = 50


class DocumentImportRequest(BaseModel):
    """Document import request."""

    title: str | None = None
    check_duplicates: bool = True
    auto_build_index: bool = False


class DocumentImportResponse(BaseResponse):
    """Document import response."""

    document: DocumentResponse


# RAG models
class RAGQueryRequest(BaseModel):
    """RAG query request with comprehensive security validation."""

    query: str = Field(..., min_length=1, max_length=2000, description="RAG query text")
    document_id: int = Field(
        ...,
        gt=0,
        le=2147483647,
        description="Target document ID",  # Max 32-bit int
    )
    use_cache: bool = Field(True, description="Whether to use query cache")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and sanitize RAG query."""
        # Validate against SQL injection patterns
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, "query", "sql_injection")

        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, "query", "xss_attempt")

        # Check for prompt injection patterns
        prompt_injection_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+previous\s+instructions",
            r"forget\s+everything\s+above",
            r"system\s*:",
            r"assistant\s*:",
            r"human\s*:",
            r"user\s*:",
            r"###\s*instruction",
            r"please\s+act\s+as",
            r"pretend\s+you\s+are",
        ]

        validate_against_patterns(
            v, prompt_injection_patterns, "query", "prompt_injection"
        )

        # Sanitize HTML content
        sanitized = sanitize_html_content(v)

        # Additional validation after sanitization
        if not sanitized or not sanitized.strip():
            raise SecurityValidationError(
                "query", "Query cannot be empty after sanitization"
            )

        if len(sanitized) > 2000:
            raise SecurityValidationError(
                "query", "Query too long after sanitization (max 2000 characters)"
            )

        return sanitized.strip()

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: int) -> int:
        """Validate document ID is within safe range."""
        if v <= 0:
            raise SecurityValidationError("document_id", "Document ID must be positive")

        if v > 2147483647:  # Max 32-bit signed integer
            raise SecurityValidationError("document_id", "Document ID too large")

        return v


class RAGQueryResponse(BaseResponse):
    """RAG query response."""

    query: str
    response: str
    document_id: int
    from_cache: bool = False
    processing_time_ms: float | None = None


class IndexBuildRequest(BaseModel):
    """Index build request."""

    document_id: int = Field(..., gt=0)
    force_rebuild: bool = False


class IndexStatusResponse(BaseResponse):
    """Index status response."""

    document_id: int
    has_index: bool = False
    index_valid: bool = False
    index_path: str | None = None
    chunk_count: int = 0
    created_at: datetime | None = None
    can_query: bool = False


class IndexBuildResponse(BaseResponse):
    """Index build response."""

    document_id: int
    build_started: bool = True


# Library management models
class LibraryStatsResponse(BaseResponse):
    """Library statistics response."""

    documents: dict[str, Any]
    vector_indexes: dict[str, Any]
    cache: dict[str, Any] | None = None
    storage: dict[str, Any] | None = None
    health: dict[str, Any]


class DuplicateGroup(BaseModel):
    """Duplicate document group."""

    criteria: str
    documents: list[DocumentResponse]


class DuplicatesResponse(BaseResponse):
    """Duplicates detection response."""

    duplicate_groups: list[DuplicateGroup]
    total_duplicates: int


class CleanupRequest(BaseModel):
    """Library cleanup request."""

    remove_orphaned: bool = True
    remove_corrupted: bool = True
    optimize_cache: bool = True


class CleanupResponse(BaseResponse):
    """Library cleanup response."""

    orphaned_removed: int = 0
    corrupted_removed: int = 0
    cache_optimized: int = 0
    storage_optimized: int = 0


class IntegrityCheckResponse(BaseResponse):
    """Document integrity check response."""

    document_id: int
    exists: bool
    file_exists: bool
    file_accessible: bool
    hash_matches: bool
    vector_index_exists: bool
    vector_index_valid: bool
    is_healthy: bool
    errors: list[str] = []
    warnings: list[str] = []


# File upload models with security validation
class SecureFileUpload(BaseModel):
    """Secure file upload validation model."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=MAX_FILENAME_LENGTH,
        description="Original filename",
    )
    content_type: str = Field(..., description="MIME content type")
    file_size: int = Field(
        ...,
        ge=1,
        le=1024 * 1024 * 1024,
        description="File size in bytes",  # 1GB max
    )

    @field_validator("filename")
    @classmethod
    def validate_filename_security(cls, v: str) -> str:
        """Validate filename for security issues."""
        return validate_filename(v)

    @field_validator("content_type")
    @classmethod
    def validate_content_type_security(cls, v: str, info) -> str:
        """Validate content type against allowed types."""
        filename = info.data.get("filename", "")
        if filename:
            return validate_file_content_type(v, filename)
        return v

    @model_validator(mode="after")
    def validate_file_upload(self):
        """Cross-field validation for file uploads."""
        # Additional security checks can go here
        # For example, checking file size vs content type expectations
        if self.content_type == "application/pdf" and self.file_size < 100:
            raise SecurityValidationError("file_size", "PDF file suspiciously small")

        return self


# Search and filter models
class SearchFilter(BaseModel):
    """Search and filter parameters with security validation."""

    query: str | None = Field(
        None, max_length=MAX_SEARCH_QUERY_LENGTH, description="Search query"
    )
    show_missing_files: bool = Field(False, description="Include missing files")
    sort_by: str = Field(
        "created_at",
        pattern="^(created_at|updated_at|last_accessed|title|file_size)$",
        description="Sort field",
    )
    sort_order: str = Field(
        "desc", pattern="^(asc|desc)$", description="Sort direction"
    )
    page: int = Field(1, ge=1, le=10000, description="Page number")
    per_page: int = Field(50, ge=1, le=200, description="Items per page")

    @field_validator("query")
    @classmethod
    def validate_search_query(cls, v: str | None) -> str | None:
        """Validate and sanitize search query for security threats."""
        if v is None:
            return v

        # Validate against SQL injection patterns
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, "query", "sql_injection")

        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, "query", "xss_attempt")

        # Sanitize HTML content
        sanitized = sanitize_html_content(v)

        # Additional length check after sanitization
        if len(sanitized) > MAX_SEARCH_QUERY_LENGTH:
            raise SecurityValidationError(
                "query",
                f"Search query too long after sanitization (max {MAX_SEARCH_QUERY_LENGTH} characters)",
            )

        return sanitized.strip() if sanitized else None


# WebSocket models
class WebSocketMessage(BaseModel):
    """WebSocket message base."""

    type: str
    data: dict[str, Any] | None = None


class RAGProgressMessage(WebSocketMessage):
    """RAG progress message."""

    type: str = "rag_progress"
    message: str
    document_id: int | None = None


class RAGResponseMessage(WebSocketMessage):
    """RAG response message."""

    type: str = "rag_response"
    query: str
    response: str
    document_id: int
    processing_time_ms: float | None = None


class IndexBuildProgressMessage(WebSocketMessage):
    """Index build progress message."""

    type: str = "index_progress"
    document_id: int
    document_title: str
    status: str
    progress_percentage: int | None = None


class ErrorMessage(WebSocketMessage):
    """Error message."""

    type: str = "error"
    error: str
    error_code: str | None = None


# System models
class SystemHealthResponse(BaseResponse):
    """System health response."""

    status: str = "healthy"
    database_connected: bool = True
    rag_service_available: bool = False
    api_key_configured: bool = False
    storage_health: str = "unknown"
    uptime_seconds: float | None = None


class ConfigurationResponse(BaseResponse):
    """Configuration response."""

    features: dict[str, bool]
    limits: dict[str, Any]
    version: str = "2.0.0"


# File upload models
class FileUploadResponse(BaseResponse):
    """File upload response."""

    filename: str
    file_size: int
    content_type: str
    upload_path: str


# Cache models
class CacheStatsResponse(BaseResponse):
    """Cache statistics response."""

    total_entries: int = 0
    hit_rate_percent: float = 0.0
    total_storage_kb: float = 0.0
    configuration: dict[str, Any]


class CacheClearResponse(BaseResponse):
    """Cache clear response."""

    entries_cleared: int = 0
