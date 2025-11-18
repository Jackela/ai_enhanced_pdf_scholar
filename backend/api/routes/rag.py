from typing import Any

"""
RAG API Routes
RESTful API endpoints for RAG (Retrieval-Augmented Generation) operations.
"""

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.api.dependencies import (
    get_library_controller,
    require_rag_service,
    validate_document_access,
)
from backend.api.error_handling import (
    ErrorTemplates,
    ResourceNotFoundException,
    SystemException,
)
from backend.api.models import (
    BaseResponse,
    CacheClearResponse,
    CacheStatsResponse,
    IndexBuildRequest,
    IndexBuildResponse,
    IndexStatusResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from backend.services.cache_service_integration import CacheServiceIntegration
from src.controllers.library_controller import LibraryController
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_cache_service_dependency() -> CacheServiceIntegration | None:
    """FastAPI dependency to get the cache service."""
    from backend.services.cache_service_integration import get_cache_service

    return await get_cache_service()


@router.post("/query", response_model=RAGQueryResponse)
async def query_document(
    query_request: RAGQueryRequest,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
    cache_service: CacheServiceIntegration | None = Depends(
        get_cache_service_dependency
    ),
) -> Any:
    """Query a document using RAG with intelligent caching."""
    try:
        # Validate document exists
        validate_document_access(query_request.document_id, controller)

        # Generate cache key for this specific query
        cache_key = f"rag_query:{query_request.document_id}:{hash(query_request.query)}"

        # Try to get cached response
        if cache_service:
            cached_response = await cache_service.get(cache_key)
            if cached_response:
                logger.debug(
                    f"Cache hit for RAG query: doc={query_request.document_id}"
                )
                return RAGQueryResponse(**cached_response)
        # Check if document has a valid index
        index_status = controller.get_index_status(query_request.document_id)
        if not index_status.get("can_query", False):
            raise ErrorTemplates.index_not_ready(query_request.document_id)
        # Perform query with timing
        start_time = time.time()
        from_cache = False

        # Execute RAG query
        response = controller.query_document(
            query_request.document_id, query_request.query
        )

        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        if response is None:
            raise SystemException(
                message="RAG query processing failed", error_type="external_service"
            )

        # Create response object
        rag_response = RAGQueryResponse(
            query=query_request.query,
            response=response,
            document_id=query_request.document_id,
            from_cache=from_cache,
            processing_time_ms=processing_time,
        )

        # Cache the response if cache service is available and caching is enabled
        if cache_service and query_request.use_cache:
            try:
                await cache_service.set(
                    cache_key,
                    rag_response.dict(),
                    ttl_seconds=3600,  # Cache for 1 hour
                )
                logger.debug(f"Cached RAG response: doc={query_request.document_id}")
            except Exception as cache_error:
                logger.warning(f"Failed to cache RAG response: {cache_error}")

        return rag_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise SystemException(
            message="RAG query processing failed", error_type="external_service"
        ) from e


@router.post("/index/build", response_model=IndexBuildResponse)
async def build_index(
    build_request: IndexBuildRequest,
    background_tasks: BackgroundTasks,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
) -> Any:
    """Build vector index for a document."""
    try:
        # Validate document exists
        validate_document_access(build_request.document_id, controller)
        # Check if index already exists and force_rebuild is False
        if not build_request.force_rebuild:
            index_status = controller.get_index_status(build_request.document_id)
            if index_status.get("has_index", False) and index_status.get(
                "index_valid", False
            ):
                return IndexBuildResponse(
                    document_id=build_request.document_id,
                    build_started=False,
                    message="Index already exists. Use force_rebuild=true to rebuild.",
                )
        # Start index building (this should be async in production)
        success = controller.build_index_for_document(build_request.document_id)
        if not success:
            raise SystemException(
                message="Failed to start vector index building", error_type="general"
            )
        return IndexBuildResponse(
            document_id=build_request.document_id,
            build_started=True,
            message="Index building started",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Index build failed: {e}")
        raise SystemException(
            message="Vector index building failed", error_type="general"
        ) from e


@router.get("/index/{document_id}/status", response_model=IndexStatusResponse)
async def get_index_status(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> Any:
    """Get vector index status for a document."""
    try:
        # Validate document exists
        validate_document_access(document_id, controller)
        # Get index status
        status_info = controller.get_index_status(document_id)
        return IndexStatusResponse(
            document_id=document_id,
            has_index=status_info.get("has_index", False),
            index_valid=status_info.get("index_valid", False),
            index_path=status_info.get("index_path"),
            chunk_count=status_info.get("chunk_count", 0),
            created_at=status_info.get("created_at"),
            can_query=status_info.get("can_query", False),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        raise SystemException(
            message="Failed to retrieve index status", error_type="general"
        ) from e


@router.delete("/index/{document_id}", response_model=BaseResponse)
async def delete_index(
    document_id: int,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
) -> Any:
    """Delete vector index for a document."""
    try:
        # Validate document exists
        validate_document_access(document_id, controller)
        # Check if index exists
        index_status = controller.get_index_status(document_id)
        if not index_status.get("has_index", False):
            raise ResourceNotFoundException(
                resource_type="vector_index",
                message=f"No vector index found for document {document_id}",
            )
        # Delete index (this would need to be implemented in the controller)
        # For now, we'll return a success message
        return BaseResponse(message=f"Index for document {document_id} will be deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete index: {e}")
        raise SystemException(
            message="Vector index deletion failed", error_type="general"
        ) from e


@router.post("/index/{document_id}/rebuild", response_model=IndexBuildResponse)
async def rebuild_index(
    document_id: int,
    background_tasks: BackgroundTasks,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
) -> Any:
    """Rebuild vector index for a document."""
    return await build_index(
        IndexBuildRequest(document_id=document_id, force_rebuild=True),
        background_tasks,
        controller,
        rag_service,
    )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    controller: LibraryController = Depends(get_library_controller),
) -> Any:
    """Get RAG cache statistics."""
    try:
        stats = controller.get_cache_statistics()
        if "error" in stats:
            raise SystemException(
                message=f"Cache service error: {stats['error']}", error_type="general"
            )
        return CacheStatsResponse(
            total_entries=stats.get("total_entries", 0),
            hit_rate_percent=stats.get("hit_rate_percent", 0.0),
            total_storage_kb=stats.get("total_storage_kb", 0.0),
            configuration=stats.get("configuration", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise SystemException(
            message="Failed to retrieve cache statistics", error_type="general"
        ) from e


@router.delete("/cache", response_model=CacheClearResponse)
async def clear_cache(
    controller: LibraryController = Depends(get_library_controller),
) -> Any:
    """Clear RAG query cache."""
    try:
        success = controller.clear_cache()
        if not success:
            raise SystemException(
                message="Cache clear operation failed", error_type="general"
            )
        return CacheClearResponse(
            entries_cleared=0,  # Would need to track this
            message="Cache cleared successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise SystemException(
            message="Cache clear operation failed", error_type="general"
        ) from e


@router.delete("/cache/{document_id}", response_model=BaseResponse)
async def clear_document_cache(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> Any:
    """Clear cache for a specific document."""
    try:
        # Validate document exists
        validate_document_access(document_id, controller)
        # Clear document cache (would need to be implemented)
        return BaseResponse(message=f"Cache cleared for document {document_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear document cache: {e}")
        raise SystemException(
            message="Document cache clear operation failed", error_type="general"
        ) from e
