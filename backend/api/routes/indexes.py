"""
Indexes API v2 Routes
RESTful endpoints for vector index management.

Implements:
- Index building and rebuilding
- Index status and metadata
- Index verification
- Orphaned index cleanup

References:
- ADR-001: V2.0 Architecture Principles
- ADR-003: API Versioning Strategy
"""
from typing import Any


import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    get_document_repository,
    get_rag_health_checker,
    get_rag_resource_manager,
    get_vector_index_repository,
)
from backend.api.models.requests import IndexBuildRequest
from backend.api.models.responses import APIResponse, Links
from config import Config
from src.interfaces.rag_service_interfaces import IRAGHealthChecker, IRAGResourceManager
from src.interfaces.repository_interfaces import (
    IDocumentRepository,
    IVectorIndexRepository,
)

logger = logging.getLogger(__name__)

# Note: No prefix here because it's set[str] in main.py when including the router
router = APIRouter(tags=["indexes"])


def _require_indexes_enabled() -> None:
    """Raise 503 until the vector index service is live."""
    if not Config.is_rag_services_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector index service is not available yet. "
            "Set ENABLE_RAG_SERVICES=1 when the implementation is ready.",
        )


# ============================================================================
# Response Models
# ============================================================================


class IndexData(BaseModel):
    """Vector index data model."""

    id: int = Field(..., description="Index ID")
    document_id: int = Field(..., description="Document ID")
    vector_index_path: str = Field(..., description="Index storage path")
    index_hash: str = Field(..., description="Index content hash")
    chunk_count: int = Field(..., description="Number of chunks")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    status: str = Field(..., description="Index status")
    links: Links | None = Field(None, description="HATEOAS links", alias="_links")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "document_id": 1,
                "vector_index_path": "/vector_indexes/doc_1",
                "index_hash": "abc123...",
                "chunk_count": 42,
                "created_at": "2025-01-12T10:00:00Z",
                "updated_at": "2025-01-12T10:00:00Z",
                "status": "ready",
                "_links": {
                    "self": "/api/indexes/1",
                    "related": {
                        "document": "/api/documents/1",
                        "rebuild": "/api/indexes/1/rebuild",
                        "verify": "/api/indexes/1/verify",
                    },
                },
            }
        }


class IndexResponse(APIResponse[IndexData]):
    """Index response envelope."""

    pass


class IndexBuildResultData(BaseModel):
    """Index build result data."""

    document_id: int = Field(..., description="Document ID")
    index_id: int | None = Field(None, description="Created index ID")
    success: bool = Field(..., description="Build success status")
    build_duration_ms: int = Field(..., description="Build duration in milliseconds")
    chunk_count: int = Field(..., description="Number of chunks created")
    error: str | None = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": 1,
                "index_id": 1,
                "success": True,
                "build_duration_ms": 5420,
                "chunk_count": 42,
                "error": None,
            }
        }


class IndexBuildResponse(APIResponse[IndexBuildResultData]):
    """Index build response envelope."""

    pass


# ============================================================================
# Get Index for Document
# ============================================================================


@router.get(
    "/document/{document_id}",
    response_model=IndexResponse,
    summary="Get document index",
    description="Get vector index for a document",
    responses={
        200: {"description": "Index retrieved successfully"},
        404: {"description": "Index not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_document_index(
    document_id: int,
    vector_repo: IVectorIndexRepository = Depends(get_vector_index_repository),
) -> IndexResponse:
    """
    Get vector index for a document.

    Args:
        document_id: Document ID
        vector_repo: Vector index repository (injected)

    Returns:
        IndexResponse with index metadata

    Raises:
        HTTPException: 404 if index not found
    """
    _require_indexes_enabled()

    try:
        # Get index from repository
        index = vector_repo.find_by_document_id(document_id)

        if index is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index not found for document {document_id}",
            )

        # Convert to response format
        index_data = IndexData(
            id=index.id,
            document_id=index.document_id,
            vector_index_path=index.index_path or "",
            index_hash=index.index_hash or "",
            chunk_count=index.chunk_count or 0,
            created_at=index.created_at.isoformat() if index.created_at else "",
            updated_at=index.created_at.isoformat() if index.created_at else "",
            status="ready",  # Placeholder - could check file existence
            _links=Links(
                self=f"/api/indexes/{index.id}",
                related={
                    "document": f"/api/documents/{document_id}",
                    "rebuild": f"/api/indexes/document/{document_id}/rebuild",
                    "verify": f"/api/indexes/{index.id}/verify",
                },
            ),
        )

        return IndexResponse(
            success=True,
            data=index_data,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get index for document {document_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve index",
        ) from e


# ============================================================================
# Build Index
# ============================================================================


@router.post(
    "/document/{document_id}/build",
    response_model=IndexBuildResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Build document index",
    description="Build vector index for a document",
    responses={
        201: {"description": "Index built successfully"},
        400: {"description": "Invalid parameters"},
        404: {"description": "Document not found"},
        409: {"description": "Index already exists"},
        500: {"description": "Index building failed"},
    },
)
async def build_document_index(
    document_id: int,
    request: IndexBuildRequest,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
    vector_repo: IVectorIndexRepository = Depends(get_vector_index_repository),
    health_checker: IRAGHealthChecker = Depends(get_rag_health_checker),
    # index_builder will be injected when implemented
) -> IndexBuildResponse:
    """
    Build vector index for a document.

    Process:
    1. Validate document exists
    2. Check if index already exists
    3. Perform health checks
    4. Build index
    5. Return result

    Args:
        document_id: Document ID to build index for
        request: Index build parameters
        doc_repo: Document repository (injected)
        vector_repo: Vector index repository (injected)
        health_checker: Health checker (injected)

    Returns:
        IndexBuildResponse with build results

    Raises:
        HTTPException: Various status codes for different errors
    """
    import time

    _require_indexes_enabled()

    start_time = time.time()

    try:
        # 1. Validate document exists
        document = doc_repo.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # 2. Check if index exists
        existing_index = vector_repo.find_by_document_id(document_id)
        if existing_index and not request.force_rebuild:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Index already exists for document {document_id}. "
                "Use force_rebuild=true to rebuild.",
            )

        # 3. Health checks
        health_status = health_checker.perform_health_check()
        if not health_status["healthy"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"System health check failed: {health_status['issues']}",
            )

        # 4. Build index (placeholder)
        logger.warning("Index builder not yet integrated - returning placeholder")

        # Simulate build
        build_duration_ms = int((time.time() - start_time) * 1000)

        # Placeholder result
        result_data = IndexBuildResultData(
            document_id=document_id,
            index_id=None,  # Would be actual index ID
            success=True,
            build_duration_ms=build_duration_ms,
            chunk_count=0,  # Placeholder
            error=None,
        )

        logger.info(
            f"[Placeholder] Index build for document {document_id} "
            f"(time: {build_duration_ms}ms)"
        )

        return IndexBuildResponse(
            success=True,
            data=result_data,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        build_duration_ms = int((time.time() - start_time) * 1000)

        logger.error(
            f"Failed to build index for document {document_id}: {e}", exc_info=True
        )

        # Return error response
        result_data = IndexBuildResultData(
            document_id=document_id,
            index_id=None,
            success=False,
            build_duration_ms=build_duration_ms,
            chunk_count=0,
            error=str(e),
        )

        return IndexBuildResponse(
            success=False,
            data=result_data,
            errors=[{"code": "INDEX_BUILD_FAILED", "message": str(e)}],
        )


# ============================================================================
# Rebuild Index
# ============================================================================


@router.post(
    "/document/{document_id}/rebuild",
    response_model=IndexBuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Rebuild document index",
    description="Rebuild existing vector index for a document",
    responses={
        200: {"description": "Index rebuilt successfully"},
        404: {"description": "Document not found"},
        500: {"description": "Index rebuilding failed"},
    },
)
async def rebuild_document_index(
    document_id: int,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
    vector_repo: IVectorIndexRepository = Depends(get_vector_index_repository),
    health_checker: IRAGHealthChecker = Depends(get_rag_health_checker),
) -> IndexBuildResponse:
    """
    Rebuild existing vector index for a document.

    Args:
        document_id: Document ID
        doc_repo: Document repository (injected)

    Returns:
        IndexBuildResponse with rebuild results
    """
    # Force rebuild by calling build with force_rebuild=True
    _require_indexes_enabled()
    request = IndexBuildRequest(force_rebuild=True)
    return await build_document_index(
        document_id,
        request,
        doc_repo,
        vector_repo,
        health_checker,
    )


# ============================================================================
# Verify Index Integrity
# ============================================================================


@router.get(
    "/{index_id}/verify",
    response_model=APIResponse[dict[str, Any]],
    summary="Verify index integrity",
    description="Verify vector index files and metadata",
    responses={
        200: {"description": "Verification complete"},
        404: {"description": "Index not found"},
        500: {"description": "Verification failed"},
    },
)
async def verify_index(
    index_id: int,
    vector_repo: IVectorIndexRepository = Depends(get_vector_index_repository),
) -> APIResponse[dict[str, Any]]:
    """
    Verify index integrity.

    Checks:
    1. Index record exists in database
    2. Index files exist on disk
    3. Chunk count matches metadata

    Args:
        index_id: Index ID
        vector_repo: Vector index repository (injected)

    Returns:
        APIResponse with verification results
    """
    _require_indexes_enabled()

    try:
        # Get index
        index = vector_repo.get_by_id(index_id)
        if index is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index {index_id} not found",
            )

        # Verify (placeholder)
        from pathlib import Path

        index_path = Path(index.index_path) if index.index_path else None

        verification_result = {
            "index_id": index_id,
            "valid": True,  # Placeholder
            "checks": {
                "database_record": True,
                "files_exist": index_path.exists() if index_path else False,
                "chunk_count_match": True,  # Placeholder
            },
            "issues": [],
        }

        if not verification_result["checks"]["files_exist"]:
            verification_result["valid"] = False
            verification_result["issues"].append("Index files not found on disk")

        logger.debug(f"Index {index_id} verification: {verification_result}")

        return APIResponse(
            success=True,
            data=verification_result,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify index {index_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Index verification failed",
        ) from e


# ============================================================================
# Cleanup Orphaned Indexes
# ============================================================================


@router.post(
    "/cleanup/orphaned",
    response_model=APIResponse[dict[str, Any]],
    summary="Cleanup orphaned indexes",
    description="Remove vector indexes for deleted documents",
    responses={
        200: {"description": "Cleanup complete"},
        500: {"description": "Cleanup failed"},
    },
)
async def cleanup_orphaned_indexes(
    resource_manager: IRAGResourceManager = Depends(get_rag_resource_manager),
) -> APIResponse[dict[str, Any]]:
    """
    Cleanup orphaned vector indexes.

    Removes indexes for documents that no longer exist.

    Args:
        resource_manager: Resource manager (injected)

    Returns:
        APIResponse with cleanup results
    """
    _require_indexes_enabled()

    try:
        cleaned_count = resource_manager.cleanup_orphaned_indexes()

        result = {
            "cleaned_count": cleaned_count,
            "message": f"Cleaned up {cleaned_count} orphaned indexes",
        }

        logger.info(f"Orphaned index cleanup: {cleaned_count} indexes removed")

        return APIResponse(
            success=True,
            data=result,
            errors=None,
        )

    except Exception as e:
        logger.error(f"Failed to cleanup orphaned indexes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Orphaned index cleanup failed",
        ) from e


# ============================================================================
# Get Storage Statistics
# ============================================================================


@router.get(
    "/stats/storage",
    response_model=APIResponse[dict[str, Any]],
    summary="Get storage statistics",
    description="Get vector index storage statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        500: {"description": "Failed to retrieve statistics"},
    },
)
async def get_storage_stats(
    resource_manager: IRAGResourceManager = Depends(get_rag_resource_manager),
) -> APIResponse[dict[str, Any]]:
    """
    Get vector index storage statistics.

    Returns:
        APIResponse with storage statistics

    Raises:
        HTTPException: 500 if retrieval fails
    """
    _require_indexes_enabled()

    try:
        stats = resource_manager.get_storage_stats()

        logger.debug(f"Storage stats retrieved: {stats}")

        return APIResponse(
            success=True,
            data=stats,
            errors=None,
        )

    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve storage statistics",
        ) from e
