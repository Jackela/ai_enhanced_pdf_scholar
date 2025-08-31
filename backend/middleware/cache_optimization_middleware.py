"""
Cache Optimization Middleware
Request-level caching middleware with intelligent optimization.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..services.cache_warming_service import CacheWarmingService
from ..services.metrics_service import MetricsService

# Import our services
from ..services.redis_cache_service import RedisCacheService
from ..services.smart_cache_manager import SmartCacheManager

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Configuration
# ============================================================================

class CacheConfig:
    """Configuration for cache optimization middleware."""

    def __init__(self):
        # Cache strategies
        self.enabled = True
        self.cache_get_requests = True
        self.cache_post_responses = False  # Usually not safe
        self.cache_private_data = False

        # TTL settings
        self.default_ttl = 3600  # 1 hour
        self.max_ttl = 86400  # 24 hours
        self.min_ttl = 60  # 1 minute

        # Response size limits
        self.max_response_size = 1024 * 1024  # 1MB
        self.min_response_size = 100  # 100 bytes

        # Cache conditions
        self.cache_status_codes = {200, 201, 202}
        self.bypass_headers = {"cache-control", "authorization", "cookie"}
        self.cache_content_types = {
            "application/json",
            "text/plain",
            "text/html",
            "application/xml"
        }

        # Performance settings
        self.cache_key_prefix = "api:"
        self.enable_compression = True
        self.compression_threshold = 1024  # bytes

        # Route-specific settings
        self.route_configs: dict[str, dict[str, Any]] = {
            "/api/documents": {"ttl": 7200, "enabled": True},
            "/api/search": {"ttl": 1800, "enabled": True},
            "/api/rag/query": {"ttl": 3600, "enabled": True},
            "/api/users/profile": {"ttl": 900, "enabled": False},  # Private data
        }

        # Headers to vary cache by
        self.vary_headers = {"accept", "accept-language", "user-agent"}


# ============================================================================
# Cache Key Generation
# ============================================================================

class CacheKeyGenerator:
    """Generate cache keys for HTTP requests."""

    def __init__(self, config: CacheConfig):
        self.config = config

    async def generate_key(self, request: Request) -> str:
        """Generate cache key for request."""
        # Base components
        components = [
            self.config.cache_key_prefix,
            request.method,
            str(request.url.path),
        ]

        # Add query parameters (sorted for consistency)
        if request.query_params:
            query_items = sorted(request.query_params.items())
            query_string = "&".join(f"{k}={v}" for k, v in query_items)
            components.append(f"q:{hashlib.sha256(query_string.encode()).hexdigest()[:8]}")

        # Add request body hash for POST/PUT requests
        if request.method in {"POST", "PUT", "PATCH"}:
            # Read body (will be consumed, so we need to replace it)
            body = await request.body()
            if body:
                body_hash = hashlib.sha256(body).hexdigest()[:8]
                components.append(f"b:{body_hash}")

                # Replace request stream for downstream processing
                async def receive():
                    return {"type": "http.request", "body": body, "more_body": False}

                request._receive = receive

        # Add vary headers
        for header_name in self.config.vary_headers:
            header_value = request.headers.get(header_name)
            if header_value:
                header_hash = hashlib.sha256(header_value.encode()).hexdigest()[:4]
                components.append(f"h:{header_name}:{header_hash}")

        # Join and hash for final key
        key_string = ":".join(components)

        # Use full string if short enough, otherwise hash it
        if len(key_string) > 100:
            key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
            return f"{self.config.cache_key_prefix}hash:{key_hash}"

        return key_string

    def should_cache_request(self, request: Request) -> bool:
        """Determine if request should be cached."""
        # Check if caching is enabled
        if not self.config.enabled:
            return False

        # Check method
        if request.method == "GET" and not self.config.cache_get_requests:
            return False
        if request.method == "POST" and not self.config.cache_post_responses:
            return False
        if request.method in {"PUT", "DELETE", "PATCH"}:
            return False

        # Check for bypass headers
        for header in self.config.bypass_headers:
            if header in request.headers:
                return False

        # Check route-specific config
        path = str(request.url.path)
        route_config = self.config.route_configs.get(path)
        if route_config and not route_config.get("enabled", True):
            return False

        return True

    def should_cache_response(self, response: Response) -> bool:
        """Determine if response should be cached."""
        # Check status code
        if response.status_code not in self.config.cache_status_codes:
            return False

        # Check content type
        content_type = response.headers.get("content-type", "").split(";")[0]
        if content_type not in self.config.cache_content_types:
            return False

        # Check cache control headers
        cache_control = response.headers.get("cache-control", "")
        if "no-cache" in cache_control or "no-store" in cache_control:
            return False

        return True


# ============================================================================
# Cache Optimization Middleware
# ============================================================================

class CacheOptimizationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for intelligent HTTP caching with optimization.
    """

    def __init__(
        self,
        app,
        redis_cache: RedisCacheService,
        smart_cache: SmartCacheManager | None = None,
        warming_service: CacheWarmingService | None = None,
        metrics_service: MetricsService | None = None,
        config: CacheConfig | None = None
    ):
        """Initialize cache optimization middleware."""
        super().__init__(app)

        self.redis_cache = redis_cache
        self.smart_cache = smart_cache
        self.warming_service = warming_service
        self.metrics_service = metrics_service
        self.config = config or CacheConfig()
        self.key_generator = CacheKeyGenerator(self.config)

        # Performance tracking
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_sets": 0,
            "cache_bypassed": 0,
            "errors": 0,
            "total_time_saved_ms": 0.0
        }

        logger.info("Cache Optimization Middleware initialized")

    async def dispatch(self, request: Request, call_next: Callable):
        """Main middleware dispatch method."""
        start_time = time.time()

        try:
            self.stats["total_requests"] += 1

            # Check if request should be cached
            if not self.key_generator.should_cache_request(request):
                self.stats["cache_bypassed"] += 1
                response = await call_next(request)
                return response

            # Generate cache key
            cache_key = await self.key_generator.generate_key(request)

            # Try to get from cache
            cached_response = await self._get_cached_response(request, cache_key)

            if cached_response:
                # Cache hit
                self.stats["cache_hits"] += 1
                processing_time = (time.time() - start_time) * 1000
                self.stats["total_time_saved_ms"] += processing_time

                # Record cache hit for smart caching
                if self.smart_cache:
                    await self.smart_cache.get(
                        cache_key,
                        user_id=self._extract_user_id(request)
                    )

                # Report metrics
                if self.metrics_service:
                    self.metrics_service.record_cache_operation(
                        operation="get",
                        cache_type="http",
                        hit=True,
                        duration=processing_time / 1000
                    )

                logger.debug(f"Cache HIT for {request.method} {request.url.path}")
                return cached_response

            else:
                # Cache miss - process request
                self.stats["cache_misses"] += 1
                response = await call_next(request)

                # Try to cache response
                if self.key_generator.should_cache_response(response):
                    await self._cache_response(request, cache_key, response)
                    self.stats["cache_sets"] += 1

                # Handle cache miss for warming service
                if self.warming_service:
                    await self.warming_service.handle_cache_miss(
                        cache_key,
                        user_id=self._extract_user_id(request)
                    )

                # Record cache miss
                if self.smart_cache:
                    await self.smart_cache.get(
                        cache_key,
                        user_id=self._extract_user_id(request)
                    )

                # Report metrics
                processing_time = (time.time() - start_time) * 1000
                if self.metrics_service:
                    self.metrics_service.record_cache_operation(
                        operation="get",
                        cache_type="http",
                        hit=False,
                        duration=processing_time / 1000
                    )

                logger.debug(f"Cache MISS for {request.method} {request.url.path}")
                return response

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache middleware error: {e}")

            # Fallback to normal processing
            return await call_next(request)

    # ========================================================================
    # Cache Operations
    # ========================================================================

    async def _get_cached_response(self, request: Request, cache_key: str) -> Response | None:
        """Get cached response if available."""
        try:
            # Get from cache
            cached_data = self.redis_cache.get(cache_key)

            if not cached_data:
                return None

            # Deserialize cached response
            if isinstance(cached_data, dict):
                response_data = cached_data
            else:
                # Fallback for non-dict cached data
                return None

            # Reconstruct response
            content = response_data.get("content", "")
            headers = response_data.get("headers", {})
            status_code = response_data.get("status_code", 200)

            # Create response
            if isinstance(content, str):
                response = Response(
                    content=content,
                    status_code=status_code,
                    headers=headers
                )
            else:
                # JSON response
                response = JSONResponse(
                    content=content,
                    status_code=status_code,
                    headers=headers
                )

            # Add cache headers
            response.headers["X-Cache"] = "HIT"
            response.headers["X-Cache-Key"] = cache_key

            return response

        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None

    async def _cache_response(self, request: Request, cache_key: str, response: Response):
        """Cache response for future use."""
        try:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Check response size limits
            if len(response_body) > self.config.max_response_size:
                logger.debug(f"Response too large to cache: {len(response_body)} bytes")
                return

            if len(response_body) < self.config.min_response_size:
                logger.debug(f"Response too small to cache: {len(response_body)} bytes")
                return

            # Prepare cache data
            try:
                # Try to parse as JSON
                content = json.loads(response_body.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Store as string
                content = response_body.decode(errors="ignore")

            cache_data = {
                "content": content,
                "headers": dict(response.headers),
                "status_code": response.status_code,
                "cached_at": datetime.utcnow().isoformat(),
                "request_method": request.method,
                "request_path": str(request.url.path)
            }

            # Calculate TTL
            ttl = self._calculate_ttl(request)

            # Store in cache
            if self.smart_cache:
                await self.smart_cache.set(
                    cache_key,
                    cache_data,
                    ttl=ttl,
                    user_id=self._extract_user_id(request)
                )
            else:
                self.redis_cache.set(cache_key, cache_data, ttl=ttl)

            # Replace response body iterator
            async def new_body_iterator():
                yield response_body

            response.body_iterator = new_body_iterator()

            # Add cache headers to response
            response.headers["X-Cache"] = "MISS"
            response.headers["X-Cache-Key"] = cache_key
            response.headers["X-Cache-TTL"] = str(ttl)

            logger.debug(f"Cached response for key: {cache_key} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Error caching response: {e}")

    def _calculate_ttl(self, request: Request) -> int:
        """Calculate TTL for caching based on request characteristics."""
        # Start with default TTL
        ttl = self.config.default_ttl

        # Check route-specific configuration
        path = str(request.url.path)
        route_config = self.config.route_configs.get(path)
        if route_config and "ttl" in route_config:
            ttl = route_config["ttl"]

        # Adjust based on request patterns
        if "search" in path:
            ttl = min(ttl, 1800)  # Search results - 30 minutes max
        elif "profile" in path or "user" in path:
            ttl = min(ttl, 900)  # User data - 15 minutes max
        elif "static" in path or path.endswith((".js", ".css", ".png", ".jpg")):
            ttl = max(ttl, 7200)  # Static assets - 2 hours min

        # Ensure TTL is within limits
        ttl = max(self.config.min_ttl, min(ttl, self.config.max_ttl))

        return ttl

    def _extract_user_id(self, request: Request) -> str | None:
        """Extract user ID from request for analytics."""
        # Try to get from JWT token
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # Simple extraction - in production would properly decode JWT
                token = auth_header[7:]
                # Would decode JWT and extract user_id
                return f"token_{hashlib.sha256(token.encode()).hexdigest()[:8]}"
            except:
                pass

        # Try to get from session
        session_id = request.headers.get("x-session-id")
        if session_id:
            return f"session_{session_id}"

        # Fallback to IP-based identifier
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        return f"ip_{hashlib.sha256(client_ip.encode()).hexdigest()[:8]}"

    # ========================================================================
    # Cache Management
    # ========================================================================

    async def invalidate_cache_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern."""
        try:
            count = self.redis_cache.delete_by_pattern(f"{self.config.cache_key_prefix}{pattern}")
            logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")
            return count
        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {e}")
            return 0

    async def invalidate_cache_by_path(self, path: str) -> int:
        """Invalidate all cache entries for a specific path."""
        pattern = f"*{path}*"
        return await self.invalidate_cache_pattern(pattern)

    async def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate cache entries for a specific user."""
        # This is challenging with HTTP caching since user info is in headers
        # Would need more sophisticated key generation to support this effectively
        logger.info(f"User cache invalidation requested for user: {user_id}")
        return 0

    async def preload_cache(self, paths: list[str], base_url: str = "http://localhost"):
        """Preload cache with common requests."""
        if not self.warming_service:
            logger.warning("No warming service available for cache preloading")
            return

        for path in paths:
            # Create a warming task for each path
            cache_key = f"{self.config.cache_key_prefix}GET:{path}"

            # Define a loader function
            async def load_path_data(url=f"{base_url}{path}"):
                # This would make an internal HTTP request
                # For now, just a placeholder
                return {"preloaded": True, "path": path}

            if self.warming_service:
                self.warming_service.add_warming_task(
                    key=cache_key,
                    priority=self.warming_service.WarmingPriority.MEDIUM,
                    strategy=self.warming_service.WarmingStrategy.SCHEDULED,
                    loader_func=load_path_data
                )

        logger.info(f"Scheduled preloading for {len(paths)} paths")

    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["total_requests"]

        return {
            "total_requests": total_requests,
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_bypassed": self.stats["cache_bypassed"],
            "cache_sets": self.stats["cache_sets"],
            "errors": self.stats["errors"],
            "hit_rate": (
                (self.stats["cache_hits"] / total_requests * 100)
                if total_requests > 0 else 0
            ),
            "miss_rate": (
                (self.stats["cache_misses"] / total_requests * 100)
                if total_requests > 0 else 0
            ),
            "bypass_rate": (
                (self.stats["cache_bypassed"] / total_requests * 100)
                if total_requests > 0 else 0
            ),
            "total_time_saved_seconds": self.stats["total_time_saved_ms"] / 1000,
            "average_time_saved_per_hit_ms": (
                (self.stats["total_time_saved_ms"] / self.stats["cache_hits"])
                if self.stats["cache_hits"] > 0 else 0
            )
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_sets": 0,
            "cache_bypassed": 0,
            "errors": 0,
            "total_time_saved_ms": 0.0
        }
        logger.info("Cache statistics reset")

    def get_cache_health(self) -> dict[str, Any]:
        """Get cache health information."""
        stats = self.get_cache_stats()

        # Determine health status
        hit_rate = stats["hit_rate"]
        error_rate = (stats["errors"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0

        if hit_rate >= 80 and error_rate < 1:
            health_status = "healthy"
        elif hit_rate >= 60 and error_rate < 5:
            health_status = "degraded"
        else:
            health_status = "unhealthy"

        return {
            "status": health_status,
            "hit_rate": hit_rate,
            "error_rate": error_rate,
            "recommendations": self._get_health_recommendations(stats)
        }

    def _get_health_recommendations(self, stats: dict[str, Any]) -> list[str]:
        """Get health recommendations based on statistics."""
        recommendations = []

        hit_rate = stats["hit_rate"]
        error_rate = (stats["errors"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0

        if hit_rate < 50:
            recommendations.append("Low cache hit rate. Consider increasing TTL or improving cache key generation.")

        if error_rate > 5:
            recommendations.append("High error rate detected. Check Redis connectivity and error logs.")

        if stats["cache_bypassed"] > stats["cache_hits"]:
            recommendations.append("Many requests are being bypassed. Review cache configuration and bypass conditions.")

        if stats["total_requests"] > 0 and stats["cache_sets"] == 0:
            recommendations.append("No responses are being cached. Check response caching conditions.")

        return recommendations


# ============================================================================
# Utility Functions
# ============================================================================

def create_cache_middleware(
    redis_cache: RedisCacheService,
    smart_cache: SmartCacheManager | None = None,
    warming_service: CacheWarmingService | None = None,
    metrics_service: MetricsService | None = None,
    config: CacheConfig | None = None
) -> CacheOptimizationMiddleware:
    """Factory function to create cache middleware."""
    return lambda app: CacheOptimizationMiddleware(
        app,
        redis_cache=redis_cache,
        smart_cache=smart_cache,
        warming_service=warming_service,
        metrics_service=metrics_service,
        config=config
    )


# Example usage in FastAPI app
if __name__ == "__main__":
    from fastapi import FastAPI

    from ..services.redis_cache_service import RedisCacheService, RedisConfig

    # Create services
    redis_config = RedisConfig()
    redis_cache = RedisCacheService(redis_config)

    # Create FastAPI app
    app = FastAPI()

    # Add cache middleware
    cache_middleware = CacheOptimizationMiddleware(
        app,
        redis_cache=redis_cache
    )

    app.add_middleware(CacheOptimizationMiddleware, redis_cache=redis_cache)

    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "This response will be cached", "timestamp": datetime.utcnow().isoformat()}

    @app.get("/api/cache/stats")
    async def cache_stats():
        return cache_middleware.get_cache_stats()

    print("Example FastAPI app with cache middleware created")
