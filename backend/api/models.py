"""
API Data Models
Pydantic models for API request/response serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# Base response models
class BaseResponse(BaseModel):
    """Base response model."""

    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# Document models
class DocumentBase(BaseModel):
    """Base document model."""

    title: str = Field(..., min_length=1, max_length=500)
    file_path: Optional[str] = None
    file_size: int = Field(..., ge=0)
    page_count: Optional[int] = Field(None, ge=0)
    metadata: Optional[Dict[str, Any]] = None


class DocumentCreate(DocumentBase):
    """Document creation model."""

    check_duplicates: bool = True
    auto_build_index: bool = False


class DocumentUpdate(BaseModel):
    """Document update model."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(DocumentBase):
    """Document response model."""

    id: int
    file_hash: str
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime] = None
    is_file_available: bool = True

    class Config:
        from_attributes = True


class DocumentListResponse(BaseResponse):
    """Document list response."""

    documents: List[DocumentResponse]
    total: int
    page: int = 1
    per_page: int = 50


class DocumentImportRequest(BaseModel):
    """Document import request."""

    title: Optional[str] = None
    check_duplicates: bool = True
    auto_build_index: bool = False


class DocumentImportResponse(BaseResponse):
    """Document import response."""

    document: DocumentResponse


# RAG models
class RAGQueryRequest(BaseModel):
    """RAG query request."""

    query: str = Field(..., min_length=1, max_length=2000)
    document_id: int = Field(..., gt=0)
    use_cache: bool = True


class RAGQueryResponse(BaseResponse):
    """RAG query response."""

    query: str
    response: str
    document_id: int
    from_cache: bool = False
    processing_time_ms: Optional[float] = None


class IndexBuildRequest(BaseModel):
    """Index build request."""

    document_id: int = Field(..., gt=0)
    force_rebuild: bool = False


class IndexStatusResponse(BaseResponse):
    """Index status response."""

    document_id: int
    has_index: bool = False
    index_valid: bool = False
    index_path: Optional[str] = None
    chunk_count: int = 0
    created_at: Optional[datetime] = None
    can_query: bool = False


class IndexBuildResponse(BaseResponse):
    """Index build response."""

    document_id: int
    build_started: bool = True


# Library management models
class LibraryStatsResponse(BaseResponse):
    """Library statistics response."""

    documents: Dict[str, Any]
    vector_indexes: Dict[str, Any]
    cache: Optional[Dict[str, Any]] = None
    storage: Optional[Dict[str, Any]] = None
    health: Dict[str, Any]


class DuplicateGroup(BaseModel):
    """Duplicate document group."""

    criteria: str
    documents: List[DocumentResponse]


class DuplicatesResponse(BaseResponse):
    """Duplicates detection response."""

    duplicate_groups: List[DuplicateGroup]
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
    errors: List[str] = []
    warnings: List[str] = []


# Search and filter models
class SearchFilter(BaseModel):
    """Search and filter parameters."""

    query: Optional[str] = None
    show_missing_files: bool = False
    sort_by: str = Field(
        "created_at", pattern="^(created_at|updated_at|last_accessed|title|file_size)$"
    )
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)


# WebSocket models
class WebSocketMessage(BaseModel):
    """WebSocket message base."""

    type: str
    data: Optional[Dict[str, Any]] = None


class RAGProgressMessage(WebSocketMessage):
    """RAG progress message."""

    type: str = "rag_progress"
    message: str
    document_id: Optional[int] = None


class RAGResponseMessage(WebSocketMessage):
    """RAG response message."""

    type: str = "rag_response"
    query: str
    response: str
    document_id: int
    processing_time_ms: Optional[float] = None


class IndexBuildProgressMessage(WebSocketMessage):
    """Index build progress message."""

    type: str = "index_progress"
    document_id: int
    document_title: str
    status: str
    progress_percentage: Optional[int] = None


class ErrorMessage(WebSocketMessage):
    """Error message."""

    type: str = "error"
    error: str
    error_code: Optional[str] = None


# System models
class SystemHealthResponse(BaseResponse):
    """System health response."""

    status: str = "healthy"
    database_connected: bool = True
    rag_service_available: bool = False
    api_key_configured: bool = False
    storage_health: str = "unknown"
    uptime_seconds: Optional[float] = None


class ConfigurationResponse(BaseResponse):
    """Configuration response."""

    features: Dict[str, bool]
    limits: Dict[str, Any]
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
    configuration: Dict[str, Any]


class CacheClearResponse(BaseResponse):
    """Cache clear response."""

    entries_cleared: int = 0
