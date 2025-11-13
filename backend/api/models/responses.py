"""
API v2 Response Models
Standardized response formats for v2 API endpoints.

All responses follow the envelope pattern for consistency:
{
    "success": true/false,
    "data": {...},
    "meta": {...},
    "errors": null/[...]
}
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# Generic type for data payload
T = TypeVar("T")


class Links(BaseModel):
    """
    HATEOAS links for resource discovery.

    Example:
        {
            "self": "/api/documents/1",
            "queries": "/api/documents/1/queries",
            "indexes": "/api/documents/1/indexes"
        }
    """

    self: str | None = Field(None, description="Link to this resource")
    related: dict[str, str] | None = Field(
        None, description="Links to related resources"
    )


class Meta(BaseModel):
    """
    Metadata about the response.

    Includes:
    - Timestamp
    - API version
    - Pagination info (if applicable)
    - Request ID (for tracking)
    """

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp (UTC)"
    )
    version: str = Field("v2", description="API version")
    request_id: str | None = Field(None, description="Request ID for tracking")


class PaginationMeta(Meta):
    """
    Extended metadata for paginated responses.
    """

    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class ErrorDetail(BaseModel):
    """
    Detailed error information.
    """

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(
        None, description="Field that caused the error (for validation errors)"
    )
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    This is the base response format for all v2 API endpoints.

    Example Success:
        {
            "success": true,
            "data": {"id": 1, "title": "Document"},
            "meta": {"timestamp": "2025-01-11T10:00:00Z", "version": "v2"},
            "errors": null
        }

    Example Error:
        {
            "success": false,
            "data": null,
            "meta": {"timestamp": "2025-01-11T10:00:00Z", "version": "v2"},
            "errors": [
                {"code": "NOT_FOUND", "message": "Document not found"}
            ]
        }
    """

    success: bool = Field(..., description="Whether the request succeeded")
    data: T | None = Field(None, description="Response data payload")
    meta: Meta = Field(default_factory=Meta, description="Response metadata")
    errors: list[ErrorDetail] | None = Field(None, description="Error details (if any)")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "title": "Example Document"},
                "meta": {
                    "timestamp": "2025-01-11T10:00:00Z",
                    "version": "v2",
                },
                "errors": None,
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated API response.

    Used for endpoints that return lists of items with pagination.

    Example:
        {
            "success": true,
            "data": [
                {"id": 1, "title": "Doc 1"},
                {"id": 2, "title": "Doc 2"}
            ],
            "meta": {
                "timestamp": "2025-01-11T10:00:00Z",
                "version": "v2",
                "page": 1,
                "per_page": 20,
                "total": 45,
                "total_pages": 3,
                "has_next": true,
                "has_prev": false
            },
            "errors": null
        }
    """

    success: bool = Field(True, description="Whether the request succeeded")
    data: list[T] = Field(..., description="Array of data items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    errors: list[ErrorDetail] | None = Field(None, description="Error details (if any)")


# ============================================================================
# Domain-Specific Response Models
# ============================================================================


class DocumentData(BaseModel):
    """
    Document data for API responses.
    """

    id: int = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    file_path: str | None = Field(None, description="File system path (optional)")
    file_hash: str = Field(..., description="File content hash")
    file_size: int | None = Field(None, description="File size in bytes")
    file_type: str | None = Field(
        None, description="Normalized file type/extension (e.g., .pdf)"
    )
    page_count: int | None = Field(None, description="Number of pages in the document")
    content_hash: str | None = Field(None, description="Document content hash")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    is_file_available: bool = Field(..., description="Whether file exists on disk")
    preview_url: str | None = Field(
        None,
        description="Endpoint for requesting a rendered page preview",
    )
    thumbnail_url: str | None = Field(
        None,
        description="Endpoint for requesting the cached thumbnail",
    )
    links: Links = Field(..., description="HATEOAS links", alias="_links")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "Research Paper.pdf",
                "file_path": "/path/to/document.pdf",
                "file_hash": "abc123...",
                "file_size": 1048576,
                "file_type": ".pdf",
                "page_count": 24,
                "content_hash": "def456...",
                "created_at": "2025-01-11T10:00:00Z",
                "updated_at": "2025-01-11T10:30:00Z",
                "is_file_available": True,
                "preview_url": "/api/documents/1/preview",
                "thumbnail_url": "/api/documents/1/thumbnail",
                "_links": {
                    "self": "/api/documents/1",
                    "related": {
                        "queries": "/api/documents/1/queries",
                        "indexes": "/api/documents/1/indexes",
                    },
                },
            }
        }


class VectorIndexData(BaseModel):
    """
    Vector index data for API responses.
    """

    id: int = Field(..., description="Index ID")
    document_id: int = Field(..., description="Associated document ID")
    index_path: str = Field(..., description="Index file path")
    index_hash: str = Field(..., description="Index content hash")
    index_valid: bool = Field(..., description="Whether index is valid")
    created_at: datetime = Field(..., description="Creation timestamp")
    links: Links = Field(..., description="HATEOAS links", alias="_links")


class QueryResultData(BaseModel):
    """
    RAG query result data.
    """

    query: str = Field(..., description="Original query text")
    answer: str = Field(..., description="Generated answer")
    sources: list[dict[str, Any]] = Field(..., description="Source documents/chunks")
    confidence: float | None = Field(None, ge=0, le=1, description="Confidence score")
    processing_time_ms: float = Field(
        ..., ge=0, description="Processing time in milliseconds"
    )
    links: Links = Field(..., description="HATEOAS links", alias="_links")


# ============================================================================
# Typed Response Aliases
# ============================================================================

DocumentResponse = APIResponse[DocumentData]
DocumentListResponse = PaginatedResponse[DocumentData]
VectorIndexResponse = APIResponse[VectorIndexData]
QueryResultResponse = APIResponse[QueryResultData]
