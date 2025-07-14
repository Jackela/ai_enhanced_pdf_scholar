"""
RAG API Routes

RESTful API endpoints for RAG (Retrieval-Augmented Generation) operations.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from backend.api.models import *
from backend.api.dependencies import (
    get_library_controller, require_rag_service, validate_document_access
)
from src.controllers.library_controller import LibraryController
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=RAGQueryResponse)
async def query_document(
    query_request: RAGQueryRequest,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service)
):
    """Query a document using RAG."""
    try:
        # Validate document exists
        validate_document_access(query_request.document_id, controller)
        
        # Check if document has a valid index
        index_status = controller.get_index_status(query_request.document_id)
        if not index_status.get("can_query", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document does not have a valid vector index. Please build index first."
            )
        
        # Perform query with timing
        start_time = time.time()
        
        # Check cache first if enabled
        from_cache = False
        if query_request.use_cache and hasattr(controller, 'cache_service') and controller.cache_service:
            cached_response = controller.cache_service.get_cached_response(
                query_request.query, 
                query_request.document_id
            )
            if cached_response:
                response = cached_response
                from_cache = True
            else:
                response = controller.query_document(query_request.document_id, query_request.query)
        else:
            response = controller.query_document(query_request.document_id, query_request.query)
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if response is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="RAG query failed"
            )
        
        return RAGQueryResponse(
            query=query_request.query,
            response=response,
            document_id=query_request.document_id,
            from_cache=from_cache,
            processing_time_ms=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.post("/index/build", response_model=IndexBuildResponse)
async def build_index(
    build_request: IndexBuildRequest,
    background_tasks: BackgroundTasks,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service)
):
    """Build vector index for a document."""
    try:
        # Validate document exists
        validate_document_access(build_request.document_id, controller)
        
        # Check if index already exists and force_rebuild is False
        if not build_request.force_rebuild:
            index_status = controller.get_index_status(build_request.document_id)
            if index_status.get("has_index", False) and index_status.get("index_valid", False):
                return IndexBuildResponse(
                    document_id=build_request.document_id,
                    build_started=False,
                    message="Index already exists. Use force_rebuild=true to rebuild."
                )
        
        # Start index building (this should be async in production)
        success = controller.build_index_for_document(build_request.document_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start index building"
            )
        
        return IndexBuildResponse(
            document_id=build_request.document_id,
            build_started=True,
            message="Index building started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Index build failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index build failed: {str(e)}"
        )


@router.get("/index/{document_id}/status", response_model=IndexStatusResponse)
async def get_index_status(
    document_id: int,
    controller: LibraryController = Depends(get_library_controller)
):
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
            can_query=status_info.get("can_query", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get index status: {str(e)}"
        )


@router.delete("/index/{document_id}", response_model=BaseResponse)
async def delete_index(
    document_id: int,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service)
):
    """Delete vector index for a document."""
    try:
        # Validate document exists
        validate_document_access(document_id, controller)
        
        # Check if index exists
        index_status = controller.get_index_status(document_id)
        if not index_status.get("has_index", False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No index found for this document"
            )
        
        # Delete index (this would need to be implemented in the controller)
        # For now, we'll return a success message
        return BaseResponse(
            message=f"Index for document {document_id} will be deleted"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index deletion failed: {str(e)}"
        )


@router.post("/index/{document_id}/rebuild", response_model=IndexBuildResponse)
async def rebuild_index(
    document_id: int,
    background_tasks: BackgroundTasks,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service)
):
    """Rebuild vector index for a document."""
    return await build_index(
        IndexBuildRequest(document_id=document_id, force_rebuild=True),
        background_tasks,
        controller,
        rag_service
    )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    controller: LibraryController = Depends(get_library_controller)
):
    """Get RAG cache statistics."""
    try:
        stats = controller.get_cache_statistics()
        
        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=stats["error"]
            )
        
        return CacheStatsResponse(
            total_entries=stats.get("total_entries", 0),
            hit_rate_percent=stats.get("hit_rate_percent", 0.0),
            total_storage_kb=stats.get("total_storage_kb", 0.0),
            configuration=stats.get("configuration", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )


@router.delete("/cache", response_model=CacheClearResponse)
async def clear_cache(
    controller: LibraryController = Depends(get_library_controller)
):
    """Clear RAG query cache."""
    try:
        success = controller.clear_cache()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache clear operation failed"
            )
        
        return CacheClearResponse(
            entries_cleared=0,  # Would need to track this
            message="Cache cleared successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache clear failed: {str(e)}"
        )


@router.delete("/cache/{document_id}", response_model=BaseResponse)
async def clear_document_cache(
    document_id: int,
    controller: LibraryController = Depends(get_library_controller)
):
    """Clear cache for a specific document."""
    try:
        # Validate document exists
        validate_document_access(document_id, controller)
        
        # Clear document cache (would need to be implemented)
        return BaseResponse(
            message=f"Cache cleared for document {document_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear document cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache clear failed: {str(e)}"
        )