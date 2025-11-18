"""
Queries API v2 Routes
RESTful endpoints for RAG query operations.

Implements:
- Single document queries
- Multi-document queries
- Query history
- Cached results

References:
- ADR-001: V2.0 Architecture Principles
- ADR-003: API Versioning Strategy
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_document_repository, get_rag_cache_manager
from backend.api.models.requests import MultiDocumentQueryRequest, QueryRequest
from backend.api.models.responses import APIResponse, Links
from config import Config
from src.interfaces.rag_service_interfaces import IRAGCacheManager
from src.interfaces.repository_interfaces import IDocumentRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["queries"])


def _require_queries_enabled() -> None:
    """Raise 501 until real RAG implementation is wired in."""
    if not Config.is_rag_services_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Query service is not available yet. "
            "Set ENABLE_RAG_SERVICES=1 when the implementation is ready.",
        )


# ============================================================================
# Response Models
# ============================================================================


class QueryResultData(BaseModel):
    """Query result data model."""

    query: str = Field(..., description="Original query text")
    document_id: int | None = Field(None, description="Document ID (for single-doc)")
    document_ids: list[int] | None = Field(
        None, description="Document IDs (for multi-doc)"
    )
    response: str = Field(..., description="Generated response")
    sources: list[dict] = Field(default_factory=list, description="Source chunks used")
    cached: bool = Field(False, description="Whether result was cached")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    links: Links | None = Field(None, description="HATEOAS links", alias="_links")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the main findings?",
                "document_id": 1,
                "response": "The main findings are...",
                "sources": [
                    {
                        "chunk_id": "chunk_0",
                        "text": "Source text...",
                        "score": 0.95,
                        "page": 1,
                    }
                ],
                "cached": False,
                "processing_time_ms": 1250,
                "_links": {
                    "self": "/api/queries/123",
                    "related": {
                        "document": "/api/documents/1",
                    },
                },
            }
        }


class QueryResponse(APIResponse[QueryResultData]):
    """Query response envelope."""

    pass


# ============================================================================
# Single Document Query
# ============================================================================


@router.post(
    "/document/{document_id}",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query a document",
    description="Execute RAG query against a single document",
    responses={
        200: {"description": "Query executed successfully"},
        400: {"description": "Invalid query parameters"},
        404: {"description": "Document not found"},
        500: {"description": "Query execution failed"},
    },
)
async def query_document(
    document_id: int,
    request: QueryRequest,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
    cache_manager: IRAGCacheManager = Depends(get_rag_cache_manager),
    # query_executor will be injected when implemented
) -> QueryResponse:
    """
    Execute RAG query against a single document.

    Process:
    1. Validate document exists
    2. Check cache for previous results
    3. Execute query if not cached
    4. Cache result for future queries
    5. Return response with sources

    Args:
        document_id: Document to query
        request: Query request with parameters
        doc_repo: Document repository (injected)
        cache_manager: Cache manager (injected)

    Returns:
        QueryResponse with generated answer and sources

    Raises:
        HTTPException: 404 if document not found, 500 if query fails
    """
    import time

    _require_queries_enabled()

    start_time = time.time()

    try:
        # 1. Validate document exists
        document = doc_repo.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # 2. Check cache
        cached_result = cache_manager.get_cached_query(
            query=request.query,
            document_id=document_id,
        )

        if cached_result is not None:
            # Return cached result
            processing_time_ms = int((time.time() - start_time) * 1000)

            result_data = QueryResultData(
                query=request.query,
                document_id=document_id,
                response=cached_result,
                sources=[],  # Sources not stored in cache currently
                cached=True,
                processing_time_ms=processing_time_ms,
                _links=Links(
                    self=f"/api/queries/document/{document_id}",
                    related={
                        "document": f"/api/documents/{document_id}",
                    },
                ),
            )

            logger.info(
                f"Cache hit for query on document {document_id} "
                f"(time: {processing_time_ms}ms)"
            )

            return QueryResponse(
                success=True,
                data=result_data,
                errors=None,
            )

        # 3. Execute query (placeholder - will be implemented with query_executor)
        # For now, return a placeholder response
        logger.warning("Query executor not yet integrated - returning placeholder")

        response_text = (
            f"[Placeholder] Query '{request.query}' would be executed "
            f"against document {document_id} with temperature={request.temperature}, "
            f"max_results={request.max_results}"
        )

        # 4. Cache result
        cache_manager.cache_query_result(
            query=request.query,
            document_id=document_id,
            result=response_text,
            ttl_seconds=3600,  # 1 hour TTL
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # 5. Return response
        result_data = QueryResultData(
            query=request.query,
            document_id=document_id,
            response=response_text,
            sources=[],  # Placeholder
            cached=False,
            processing_time_ms=processing_time_ms,
            _links=Links(
                self=f"/api/queries/document/{document_id}",
                related={
                    "document": f"/api/documents/{document_id}",
                },
            ),
        )

        logger.info(
            f"Query executed on document {document_id} (time: {processing_time_ms}ms)"
        )

        return QueryResponse(
            success=True,
            data=result_data,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query execution failed",
        ) from e


# ============================================================================
# Multi-Document Query
# ============================================================================


@router.post(
    "/multi-document",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query multiple documents",
    description="Execute RAG query across multiple documents",
    responses={
        200: {"description": "Query executed successfully"},
        400: {"description": "Invalid query parameters"},
        404: {"description": "One or more documents not found"},
        500: {"description": "Query execution failed"},
    },
)
async def query_multiple_documents(
    request: MultiDocumentQueryRequest,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> QueryResponse:
    """
    Execute RAG query across multiple documents.

    Process:
    1. Validate all documents exist
    2. Execute query across all documents
    3. Synthesize results based on mode
    4. Return combined response

    Args:
        request: Multi-document query request
        doc_repo: Document repository (injected)

    Returns:
        QueryResponse with synthesized answer from multiple documents

    Raises:
        HTTPException: 404 if documents not found, 500 if query fails
    """
    import time

    _require_queries_enabled()

    start_time = time.time()

    try:
        # 1. Validate documents exist
        documents = doc_repo.get_by_ids(request.document_ids)

        if len(documents) != len(request.document_ids):
            found_ids = {doc.id for doc in documents}
            missing_ids = set(request.document_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documents not found: {list(missing_ids)}",
            )

        # 2. Execute query (placeholder)
        logger.warning(
            "Multi-document query executor not yet integrated - returning placeholder"
        )

        response_text = (
            f"[Placeholder] Multi-document query '{request.query}' would be "
            f"executed against {len(request.document_ids)} documents "
            f"with synthesis_mode={request.synthesis_mode}"
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # 3. Return response
        result_data = QueryResultData(
            query=request.query,
            document_ids=request.document_ids,
            response=response_text,
            sources=[],  # Placeholder
            cached=False,
            processing_time_ms=processing_time_ms,
            _links=Links(
                self="/api/queries/multi-document",
                related={
                    "documents": f"/api/documents?ids={','.join(map(str, request.document_ids))}"
                },
            ),
        )

        logger.info(
            f"Multi-document query executed across {len(request.document_ids)} "
            f"documents (time: {processing_time_ms}ms)"
        )

        return QueryResponse(
            success=True,
            data=result_data,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute multi-document query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multi-document query execution failed",
        ) from e


# ============================================================================
# Clear Query Cache
# ============================================================================


@router.delete(
    "/cache/document/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear query cache",
    description="Clear all cached queries for a document",
    responses={
        204: {"description": "Cache cleared successfully"},
        500: {"description": "Cache clearing failed"},
    },
)
async def clear_document_cache(
    document_id: int,
    cache_manager: IRAGCacheManager = Depends(get_rag_cache_manager),
) -> None:
    """
    Clear all cached queries for a document.

    Called when:
    - Document is updated
    - Vector index is rebuilt
    - Manual cache invalidation

    Args:
        document_id: Document ID
        cache_manager: Cache manager (injected)

    Raises:
        HTTPException: 500 if cache clearing fails
    """
    _require_queries_enabled()

    try:
        invalidated_count = cache_manager.invalidate_document_cache(document_id)

        logger.info(
            f"Cleared {invalidated_count} cache entries for document {document_id}"
        )

        # 204 No Content - no response body

    except Exception as e:
        logger.error(
            f"Failed to clear cache for document {document_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache clearing failed",
        ) from e


# ============================================================================
# Get Cache Statistics
# ============================================================================


@router.get(
    "/cache/stats",
    response_model=APIResponse[dict],
    summary="Get cache statistics",
    description="Get query cache statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        500: {"description": "Failed to retrieve statistics"},
    },
)
async def get_cache_stats(
    cache_manager: IRAGCacheManager = Depends(get_rag_cache_manager),
) -> APIResponse[dict]:
    """
    Get query cache statistics.

    Returns:
        APIResponse with cache statistics (hit rate, entries, etc.)

    Raises:
        HTTPException: 500 if retrieval fails
    """
    _require_queries_enabled()

    try:
        stats = cache_manager.get_cache_stats()

        logger.debug(f"Cache stats retrieved: {stats}")

        return APIResponse(
            success=True,
            data=stats,
            errors=None,
        )

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics",
        ) from e
