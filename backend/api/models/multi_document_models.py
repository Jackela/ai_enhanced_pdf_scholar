"""
Multi-Document RAG API Models
Pydantic models for multi-document collection and query endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentSourceResponse(BaseModel):
    """Document source in query results."""
    document_id: int
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    excerpt: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None


class CrossReferenceResponse(BaseModel):
    """Cross-reference between documents."""
    source_doc_id: int
    target_doc_id: int
    relation_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: Optional[str] = None


class CreateCollectionRequest(BaseModel):
    """Request to create a new document collection."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    document_ids: List[int] = Field(..., min_items=1)


class UpdateCollectionRequest(BaseModel):
    """Request to update a document collection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


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
    description: Optional[str]
    document_ids: List[int]
    document_count: int
    created_at: Optional[str]
    updated_at: Optional[str]


class CollectionListResponse(BaseModel):
    """Response for collection list."""
    collections: List[CollectionResponse]
    total_count: int
    page: int
    limit: int


class CrossDocumentQueryRequest(BaseModel):
    """Request for cross-document query."""
    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)
    user_id: Optional[str] = None


class MultiDocumentQueryResponse(BaseModel):
    """Response for multi-document query."""
    id: int
    query: str
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[DocumentSourceResponse]
    cross_references: List[CrossReferenceResponse]
    processing_time_ms: int
    tokens_used: Optional[int] = None
    status: str
    created_at: str


class QueryHistoryResponse(BaseModel):
    """Response for query history."""
    queries: List[MultiDocumentQueryResponse]
    total_count: int
    page: int
    limit: int


class CollectionIndexResponse(BaseModel):
    """Response for collection index information."""
    id: int
    collection_id: int
    index_path: str
    embedding_model: str
    chunk_count: Optional[int]
    created_at: str


class CollectionStatisticsResponse(BaseModel):
    """Response for collection statistics."""
    collection_id: int
    name: str
    document_count: int
    total_file_size: int
    avg_file_size: int
    created_at: Optional[str]
    recent_queries: int = 0
    avg_query_time_ms: Optional[float] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None