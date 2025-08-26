"""
Cache Administration API Routes
Administrative endpoints for managing and monitoring the multi-layer cache system.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...config.application_config import get_application_config
from ...services.cache_service_integration import (
    CacheServiceIntegration,
    get_application_cache_status,
    get_cache_service,
)
from ..auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache_admin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CacheOperationRequest(BaseModel):
    """Request model for cache operations."""
    key: str = Field(..., description="Cache key")
    value: Any | None = Field(None, description="Cache value")
    ttl_seconds: int | None = Field(None, description="Time to live in seconds", ge=1)


class BatchCacheRequest(BaseModel):
    """Request model for batch cache operations."""
    data: dict[str, Any] = Field(..., description="Key-value pairs to cache")
    ttl_seconds: int | None = Field(None, description="Time to live in seconds", ge=1)


class CacheInvalidationRequest(BaseModel):
    """Request model for cache invalidation."""
    pattern: str = Field(..., description="Pattern to match keys for invalidation")


class CacheWarmingRequest(BaseModel):
    """Request model for cache warming."""
    data: dict[str, Any] = Field(..., description="Key-value pairs to warm in cache")


class CacheOperationResponse(BaseModel):
    """Response model for cache operations."""
    success: bool
    message: str
    data: Any | None = None
    metadata: dict[str, Any] | None = None


class CacheHealthResponse(BaseModel):
    """Response model for cache health status."""
    overall_status: str
    cache_system_available: bool
    components: dict[str, Any]
    statistics: dict[str, Any] | None = None


class CacheStatisticsResponse(BaseModel):
    """Response model for cache statistics."""
    hit_rate_percent: float
    total_requests: int
    l1_cache: dict[str, Any]
    l2_cache: dict[str, Any]
    l3_cache: dict[str, Any]
    performance: dict[str, Any]


# ============================================================================
# Cache Health and Status Endpoints
# ============================================================================

@router.get("/health", response_model=CacheHealthResponse)
async def get_cache_health(
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service)
):
    """
    Get comprehensive cache system health status.

    Returns detailed information about:
    - Overall cache system status
    - Individual cache layer health
    - Component availability
    - Basic performance statistics
    """
    try:
        app_cache_status = await get_application_cache_status()

        if not app_cache_status.get("cache_system_available", False):
            return CacheHealthResponse(
                overall_status="disabled",
                cache_system_available=False,
                components={
                    "cache_service": False,
                    "reason": app_cache_status.get("reason", "Unknown")
                }
            )

        health_data = app_cache_status.get("health", {})
        statistics = app_cache_status.get("statistics", {})

        return CacheHealthResponse(
            overall_status=health_data.get("overall_status", "unknown"),
            cache_system_available=True,
            components=health_data.get("components", {}),
            statistics=statistics
        )

    except Exception as e:
        logger.error(f"Error getting cache health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache health: {str(e)}"
        )


@router.get("/statistics", response_model=CacheStatisticsResponse)
async def get_cache_statistics(
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication for detailed stats
):
    """
    Get detailed cache performance statistics.

    Requires authentication. Returns:
    - Hit rates by cache level
    - Request counts and performance metrics
    - Cache sizes and efficiency data
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        statistics = cache_service.get_statistics()

        if not statistics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cache statistics not available"
            )

        return CacheStatisticsResponse(**statistics)

    except Exception as e:
        logger.error(f"Error getting cache statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )


@router.get("/configuration")
async def get_cache_configuration(
    current_user=Depends(get_current_user)  # Require authentication for config access
):
    """
    Get current cache system configuration.

    Requires authentication. Returns the current configuration
    of the multi-layer cache system.
    """
    try:
        app_config = get_application_config()

        if not app_config.caching:
            return {
                "cache_system_enabled": False,
                "message": "Cache system not configured"
            }

        config_dict = app_config.caching.to_dict()
        config_dict["cache_system_enabled"] = True

        return config_dict

    except Exception as e:
        logger.error(f"Error getting cache configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache configuration: {str(e)}"
        )


# ============================================================================
# Cache Management Endpoints
# ============================================================================

@router.post("/invalidate", response_model=CacheOperationResponse)
async def invalidate_cache_pattern(
    request: CacheInvalidationRequest,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication for cache management
):
    """
    Invalidate cache entries matching a pattern.

    Requires authentication. Removes all cache entries whose keys
    match the specified pattern across all cache levels.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        invalidated_count = await cache_service.invalidate_pattern(request.pattern)

        logger.info(f"User {current_user.get('id', 'unknown')} invalidated {invalidated_count} cache entries with pattern: {request.pattern}")

        return CacheOperationResponse(
            success=True,
            message=f"Invalidated {invalidated_count} cache entries",
            metadata={
                "pattern": request.pattern,
                "invalidated_count": invalidated_count
            }
        )

    except Exception as e:
        logger.error(f"Error invalidating cache pattern {request.pattern}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.post("/warm", response_model=CacheOperationResponse)
async def warm_cache(
    request: CacheWarmingRequest,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication for cache management
):
    """
    Warm cache with provided data.

    Requires authentication. Pre-loads the cache with specified
    key-value pairs to improve future access performance.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        warmed_count = await cache_service.warm_cache(request.data)

        logger.info(f"User {current_user.get('id', 'unknown')} warmed {warmed_count} cache entries")

        return CacheOperationResponse(
            success=True,
            message=f"Warmed {warmed_count} cache entries",
            metadata={
                "requested_count": len(request.data),
                "warmed_count": warmed_count
            }
        )

    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to warm cache: {str(e)}"
        )


@router.delete("/clear", response_model=CacheOperationResponse)
async def clear_all_caches(
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication for dangerous operations
):
    """
    Clear all cache entries across all levels.

    **WARNING**: This is a destructive operation that clears all cached data.
    Requires authentication. Use with caution.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        # Clear all caches by invalidating all patterns
        invalidated_count = await cache_service.invalidate_pattern("*")

        logger.warning(f"User {current_user.get('id', 'unknown')} cleared all caches ({invalidated_count} entries)")

        return CacheOperationResponse(
            success=True,
            message=f"Cleared all caches ({invalidated_count} entries)",
            metadata={
                "operation": "clear_all",
                "cleared_count": invalidated_count
            }
        )

    except Exception as e:
        logger.error(f"Error clearing all caches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear caches: {str(e)}"
        )


# ============================================================================
# Direct Cache Operations (Development/Testing)
# ============================================================================

@router.get("/get/{key}")
async def get_cache_value(
    key: str,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication
):
    """
    Get value from cache by key.

    Development/testing endpoint for direct cache access.
    Requires authentication.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        value = await cache_service.get(key)

        if value is None:
            return CacheOperationResponse(
                success=False,
                message="Key not found in cache",
                data=None
            )

        return CacheOperationResponse(
            success=True,
            message="Value retrieved from cache",
            data=value
        )

    except Exception as e:
        logger.error(f"Error getting cache value for key {key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache value: {str(e)}"
        )


@router.post("/set", response_model=CacheOperationResponse)
async def set_cache_value(
    request: CacheOperationRequest,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication
):
    """
    Set value in cache.

    Development/testing endpoint for direct cache access.
    Requires authentication.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    if request.value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Value is required for set operation"
        )

    try:
        success = await cache_service.set(
            request.key,
            request.value,
            request.ttl_seconds
        )

        return CacheOperationResponse(
            success=success,
            message="Value set in cache" if success else "Failed to set value in cache",
            metadata={
                "key": request.key,
                "ttl_seconds": request.ttl_seconds
            }
        )

    except Exception as e:
        logger.error(f"Error setting cache value for key {request.key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set cache value: {str(e)}"
        )


@router.delete("/delete/{key}", response_model=CacheOperationResponse)
async def delete_cache_value(
    key: str,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication
):
    """
    Delete value from cache.

    Development/testing endpoint for direct cache access.
    Requires authentication.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    try:
        success = await cache_service.delete(key)

        return CacheOperationResponse(
            success=success,
            message="Key deleted from cache" if success else "Key not found in cache",
            metadata={"key": key}
        )

    except Exception as e:
        logger.error(f"Error deleting cache value for key {key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete cache value: {str(e)}"
        )


@router.post("/mset", response_model=CacheOperationResponse)
async def set_multiple_cache_values(
    request: BatchCacheRequest,
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication
):
    """
    Set multiple values in cache.

    Development/testing endpoint for batch cache operations.
    Requires authentication.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    if not request.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data dictionary cannot be empty"
        )

    try:
        success = await cache_service.mset(request.data, request.ttl_seconds)

        return CacheOperationResponse(
            success=success,
            message=f"Batch set {'successful' if success else 'failed'}",
            metadata={
                "keys_count": len(request.data),
                "ttl_seconds": request.ttl_seconds
            }
        )

    except Exception as e:
        logger.error(f"Error in batch cache set: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set multiple cache values: {str(e)}"
        )


@router.post("/mget")
async def get_multiple_cache_values(
    keys: list[str],
    cache_service: CacheServiceIntegration | None = Depends(get_cache_service),
    current_user=Depends(get_current_user)  # Require authentication
):
    """
    Get multiple values from cache.

    Development/testing endpoint for batch cache operations.
    Requires authentication.
    """
    if not cache_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available"
        )

    if not keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keys list cannot be empty"
        )

    try:
        results = await cache_service.mget(keys)

        return CacheOperationResponse(
            success=True,
            message=f"Retrieved {len(results)} values from cache",
            data=results,
            metadata={
                "requested_keys": len(keys),
                "found_keys": len(results)
            }
        )

    except Exception as e:
        logger.error(f"Error in batch cache get: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get multiple cache values: {str(e)}"
        )
