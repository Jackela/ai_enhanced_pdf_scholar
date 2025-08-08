"""
Library Management API Routes
RESTful API endpoints for document library management operations.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_library_controller
from backend.api.models import (
    BaseResponse,
    CleanupRequest,
    CleanupResponse,
    DocumentListResponse,
    DocumentResponse,
    DuplicateGroup,
    DuplicatesResponse,
    LibraryStatsResponse,
)
from backend.api.error_handling import SystemException, ErrorTemplates
from src.controllers.library_controller import LibraryController

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_statistics(
    controller: LibraryController = Depends(get_library_controller),
):
    """Get comprehensive library statistics."""
    try:
        stats = controller.get_library_statistics()
        if "error" in stats:
            raise SystemException(
                message=f"Failed to get library statistics: {stats['error']}",
                error_type="general"
            )
        return LibraryStatsResponse(
            documents=stats.get("documents", {}),
            vector_indexes=stats.get("vector_indexes", {}),
            cache=stats.get("cache"),
            storage=stats.get("storage"),
            health=stats.get("health", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get library statistics: {e}")
        raise SystemException(
            message="Failed to retrieve library statistics",
            error_type="database"
        )


@router.get("/duplicates", response_model=DuplicatesResponse)
async def find_duplicate_documents(
    controller: LibraryController = Depends(get_library_controller),
):
    """Find duplicate documents in the library."""
    try:
        duplicates = controller.find_duplicate_documents()
        duplicate_groups = []
        total_duplicates = 0
        for criteria, docs in duplicates:
            # Convert documents to response models
            doc_responses = []
            for doc in docs:
                doc_dict = doc.to_api_dict()
                doc_dict["is_file_available"] = doc.is_file_available()
                doc_responses.append(DocumentResponse(**doc_dict))
            duplicate_groups.append(
                DuplicateGroup(criteria=criteria, documents=doc_responses)
            )
            total_duplicates += len(docs)
        return DuplicatesResponse(
            duplicate_groups=duplicate_groups, total_duplicates=total_duplicates
        )
    except Exception as e:
        logger.error(f"Failed to find duplicates: {e}")
        raise SystemException(
            message="Duplicate detection failed",
            error_type="general"
        )


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_library(
    cleanup_request: CleanupRequest,
    controller: LibraryController = Depends(get_library_controller),
):
    """Perform library cleanup operations."""
    try:
        results = controller.cleanup_library()
        if "error" in results:
            raise SystemException(
                message=f"Library cleanup failed: {results['error']}",
                error_type="general"
            )
        return CleanupResponse(
            orphaned_removed=results.get("orphaned_indexes_cleaned", 0),
            corrupted_removed=results.get("invalid_indexes_cleaned", 0),
            cache_optimized=results.get("cache_optimized", 0),
            storage_optimized=results.get("storage_optimized", 0),
            message="Library cleanup completed successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Library cleanup failed: {e}")
        raise SystemException(
            message="Library cleanup operation failed",
            error_type="general"
        )


@router.get("/health", response_model=BaseResponse)
async def check_library_health(
    controller: LibraryController = Depends(get_library_controller),
):
    """Check library health status."""
    try:
        stats = controller.get_library_statistics()
        health = stats.get("health", {})
        # Determine overall health
        issues = []
        if health.get("orphaned_indexes", 0) > 0:
            issues.append(f"{health['orphaned_indexes']} orphaned indexes")
        if health.get("invalid_indexes", 0) > 0:
            issues.append(f"{health['invalid_indexes']} invalid indexes")
        if issues:
            return BaseResponse(
                success=False,
                message=f"Library health issues detected: {', '.join(issues)}",
            )
        else:
            return BaseResponse(message="Library is healthy")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise SystemException(
            message="Library health check failed",
            error_type="general"
        )


@router.post("/optimize", response_model=BaseResponse)
async def optimize_library(
    controller: LibraryController = Depends(get_library_controller),
):
    """Optimize library storage and performance."""
    try:
        # This could include various optimization operations
        results = controller.cleanup_library()
        if "error" in results:
            raise SystemException(
                message=f"Library optimization failed: {results['error']}",
                error_type="general"
            )
        optimizations = []
        if results.get("orphaned_indexes_cleaned", 0) > 0:
            optimizations.append(
                f"Removed {results['orphaned_indexes_cleaned']} orphaned indexes"
            )
        if results.get("invalid_indexes_cleaned", 0) > 0:
            optimizations.append(
                f"Removed {results['invalid_indexes_cleaned']} invalid indexes"
            )
        if results.get("cache_optimized", 0) > 0:
            optimizations.append(
                f"Optimized {results['cache_optimized']} cache entries"
            )
        if results.get("storage_optimized", 0) > 0:
            optimizations.append(
                f"Optimized {results['storage_optimized']} storage items"
            )
        if optimizations:
            message = f"Library optimized: {', '.join(optimizations)}"
        else:
            message = "Library was already optimized"
        return BaseResponse(message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Library optimization failed: {e}")
        raise SystemException(
            message="Library optimization operation failed",
            error_type="general"
        )


@router.get("/search", response_model=DocumentListResponse)
async def search_documents(
    q: str,
    limit: int = 50,
    controller: LibraryController = Depends(get_library_controller),
):
    """Search documents by title and content."""
    try:
        documents = controller.get_documents(search_query=q, limit=limit)
        # Convert to response models
        doc_responses = []
        for doc in documents:
            doc_dict = doc.to_api_dict()
            doc_dict["is_file_available"] = doc.is_file_available()
            doc_responses.append(DocumentResponse(**doc_dict))
        return DocumentListResponse(
            documents=doc_responses, total=len(doc_responses), page=1, per_page=limit
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise SystemException(
            message="Document search failed",
            error_type="database"
        )


@router.get("/recent", response_model=DocumentListResponse)
async def get_recent_documents(
    limit: int = 20, controller: LibraryController = Depends(get_library_controller)
):
    """Get recently accessed documents."""
    try:
        # Use the library service directly for recent documents
        recent_docs = controller.library_service.get_recent_documents(limit)
        # Convert to response models
        doc_responses = []
        for doc in recent_docs:
            doc_dict = doc.to_api_dict()
            doc_dict["is_file_available"] = doc.is_file_available()
            doc_responses.append(DocumentResponse(**doc_dict))
        return DocumentListResponse(
            documents=doc_responses, total=len(doc_responses), page=1, per_page=limit
        )
    except Exception as e:
        logger.error(f"Failed to get recent documents: {e}")
        raise SystemException(
            message="Failed to retrieve recent documents",
            error_type="database"
        )
