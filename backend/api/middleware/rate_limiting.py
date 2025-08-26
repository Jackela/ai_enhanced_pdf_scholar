"""
Rate Limiting Middleware for FastAPI
Implements comprehensive IP-based and endpoint-specific rate limiting with Redis support
"""

import json
import logging
import os
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Optional monitoring import
try:
    from .rate_limit_monitor import record_rate_limit_event
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    aioredis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds
    burst: int | None = None  # Burst capacity (if different from requests)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    # Default limits
    default_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(60, 60))  # 60 req/min

    # Endpoint-specific limits
    endpoint_limits: dict[str, RateLimitRule] = field(default_factory=lambda: {
        # Upload endpoints - strict limits
        "/api/documents/upload": RateLimitRule(10, 60),           # 10 uploads/min
        "/api/library/upload": RateLimitRule(10, 60),             # 10 uploads/min

        # Query endpoints - moderate limits
        "/api/rag/query": RateLimitRule(100, 60),                 # 100 queries/min
        "/api/rag/chat": RateLimitRule(100, 60),                  # 100 chat/min
        "/api/documents/query": RateLimitRule(100, 60),           # 100 doc queries/min

        # Admin endpoints - higher limits
        "/api/system": RateLimitRule(200, 60),                    # 200 admin/min
        "/api/system/health": RateLimitRule(1000, 60),            # Health checks unrestricted

        # Library operations
        "/api/library": RateLimitRule(120, 60),                   # 120 library ops/min
        "/api/documents": RateLimitRule(120, 60),                 # 120 doc ops/min
    })

    # Global limits (applied before endpoint-specific)
    global_ip_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(1000, 3600))  # 1000/hour

    # Redis configuration
    redis_url: str | None = None
    redis_key_prefix: str = "rate_limit:"

    # Environment-specific multipliers
    dev_multiplier: float = 10.0     # 10x limits in development
    test_multiplier: float = 100.0   # 100x limits in testing

    # Bypass configuration
    bypass_ips: set = field(default_factory=lambda: {"127.0.0.1", "::1"})  # localhost bypass
    bypass_user_agents: set = field(default_factory=lambda: {"health-check", "monitor"})

    # Response configuration
    include_headers: bool = True
    block_duration: int = 60  # Block duration after rate limit hit (seconds)

    # Monitoring configuration
    enable_monitoring: bool = True
    monitoring_log_file: str | None = None


class InMemoryStore:
    """In-memory rate limiting store with automatic cleanup."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = defaultdict(dict)
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    async def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, data in self._data.items():
            if data.get('expires', 0) < current_time:
                expired_keys.append(key)

        for key in expired_keys:
            del self._data[key]

        self._last_cleanup = current_time
        logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get rate limit data for key."""
        await self._cleanup_expired()
        return self._data.get(key)

    async def set(self, key: str, data: dict[str, Any], ttl: int) -> None:
        """Set rate limit data with TTL."""
        data['expires'] = time.time() + ttl
        self._data[key] = data

    async def incr(self, key: str, window: int) -> tuple[int, int]:
        """Increment counter and return (current_count, ttl)."""
        await self._cleanup_expired()
        current_time = time.time()

        if key not in self._data:
            self._data[key] = {
                'count': 1,
                'window_start': current_time,
                'expires': current_time + window
            }
            return 1, window

        data = self._data[key]

        # Check if we're in a new window
        if current_time - data['window_start'] >= window:
            data['count'] = 1
            data['window_start'] = current_time
            data['expires'] = current_time + window
            return 1, window
        else:
            data['count'] += 1
            remaining_ttl = int(data['expires'] - current_time)
            return data['count'], remaining_ttl


class RedisStore:
    """Redis-based rate limiting store."""

    def __init__(self, redis_url: str, key_prefix: str = "rate_limit:"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis = None

    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get rate limit data for key."""
        try:
            redis_client = await self._get_redis()
            data = await redis_client.get(f"{self.key_prefix}{key}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    async def set(self, key: str, data: dict[str, Any], ttl: int) -> None:
        """Set rate limit data with TTL."""
        try:
            redis_client = await self._get_redis()
            await redis_client.setex(
                f"{self.key_prefix}{key}",
                ttl,
                json.dumps(data)
            )
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    async def incr(self, key: str, window: int) -> tuple[int, int]:
        """Increment counter using Redis sliding window."""
        try:
            redis_client = await self._get_redis()
            pipe = redis_client.pipeline()

            # Use sliding window counter
            current_time = time.time()
            window_start = current_time - window

            key_name = f"{self.key_prefix}{key}"

            # Remove old entries and count current
            pipe.zremrangebyscore(key_name, 0, window_start)
            pipe.zadd(key_name, {str(current_time): current_time})
            pipe.zcount(key_name, window_start, current_time)
            pipe.expire(key_name, window)

            results = await pipe.execute()
            count = results[2]  # zcount result

            return count, window

        except Exception as e:
            logger.warning(f"Redis incr failed: {e}")
            # Fallback to simple increment
            return await self._simple_incr(key, window)

    async def _simple_incr(self, key: str, window: int) -> tuple[int, int]:
        """Simple increment fallback."""
        try:
            redis_client = await self._get_redis()
            key_name = f"{self.key_prefix}{key}"
            count = await redis_client.incr(key_name)
            if count == 1:
                await redis_client.expire(key_name, window)
            ttl = await redis_client.ttl(key_name)
            return count, ttl if ttl > 0 else window
        except Exception as e:
            logger.error(f"Redis simple incr failed: {e}")
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting with Redis support and graceful fallback."""

    def __init__(self, app: ASGIApp, config: RateLimitConfig | None = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()

        # Initialize storage backend
        self._store = self._init_store()

        # Apply environment-specific multipliers
        self._apply_env_multipliers()

        # Cache for bypass decisions
        self._bypass_cache: dict[str, bool] = {}

        logger.info(f"Rate limiting initialized with {type(self._store).__name__}")

    def _init_store(self):
        """Initialize storage backend (Redis with in-memory fallback)."""
        redis_url = self.config.redis_url or os.getenv("REDIS_URL")

        if redis_url and REDIS_AVAILABLE:
            try:
                return RedisStore(redis_url, self.config.redis_key_prefix)
            except Exception as e:
                logger.warning(f"Redis initialization failed: {e}, falling back to in-memory")

        return InMemoryStore()

    def _apply_env_multipliers(self) -> None:
        """Apply environment-specific rate limit multipliers."""
        env = os.getenv("ENVIRONMENT", "production").lower()

        multiplier = 1.0
        if env == "development":
            multiplier = self.config.dev_multiplier
        elif env == "test":
            multiplier = self.config.test_multiplier

        if multiplier > 1.0:
            # Apply multiplier to all limits
            self.config.default_limit.requests = int(self.config.default_limit.requests * multiplier)
            self.config.global_ip_limit.requests = int(self.config.global_ip_limit.requests * multiplier)

            for endpoint, rule in self.config.endpoint_limits.items():
                rule.requests = int(rule.requests * multiplier)

            logger.info(f"Applied {multiplier}x rate limit multiplier for {env} environment")

    def _should_bypass(self, request: Request) -> bool:
        """Check if request should bypass rate limiting."""
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "").lower()

        # Cache bypass decisions for performance
        cache_key = f"{client_ip}:{user_agent}"
        if cache_key in self._bypass_cache:
            return self._bypass_cache[cache_key]

        bypass = (
            client_ip in self.config.bypass_ips or
            any(ua in user_agent for ua in self.config.bypass_user_agents)
        )

        self._bypass_cache[cache_key] = bypass
        return bypass

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP considering reverse proxy headers."""
        # Check for reverse proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _get_rate_limit_rule(self, request: Request) -> RateLimitRule:
        """Get appropriate rate limit rule for the request."""
        path = request.url.path

        # Check for exact matches first
        if path in self.config.endpoint_limits:
            return self.config.endpoint_limits[path]

        # Check for prefix matches
        for endpoint_path, rule in self.config.endpoint_limits.items():
            if path.startswith(endpoint_path):
                return rule

        return self.config.default_limit

    def _create_rate_limit_response(self,
                                  limit: int,
                                  remaining: int,
                                  reset_time: int,
                                  retry_after: int) -> JSONResponse:
        """Create rate limit exceeded response."""
        headers = {}

        if self.config.include_headers:
            headers.update({
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(retry_after)
            })

        return JSONResponse(
            status_code=429,
            headers=headers,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {limit} requests per {retry_after} seconds.",
                "retry_after": retry_after,
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time
            }
        )

    def _record_event(self, request: Request, response: Response, response_time: float,
                     limit_type: str = None, limit_value: int = None, remaining: int = None):
        """Record monitoring event if enabled."""
        if not (self.config.enable_monitoring and MONITORING_AVAILABLE):
            return

        try:
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent")

            record_rate_limit_event(
                client_ip=client_ip,
                endpoint=request.url.path,
                status_code=response.status_code,
                response_time=response_time,
                user_agent=user_agent,
                limit_type=limit_type,
                limit_value=limit_value,
                remaining=remaining
            )
        except Exception as e:
            logger.debug(f"Failed to record monitoring event: {e}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting."""
        start_time = time.time()

        # Skip rate limiting for certain requests
        if self._should_bypass(request):
            response = await call_next(request)
            self._record_event(request, response, time.time() - start_time, "bypass")
            return response

        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Check global IP limit first
        global_key = f"global_ip:{client_ip}"
        try:
            count, ttl = await self._store.incr(global_key, self.config.global_ip_limit.window)

            if count > self.config.global_ip_limit.requests:
                reset_time = int(time.time() + ttl)
                response = self._create_rate_limit_response(
                    self.config.global_ip_limit.requests,
                    0,
                    reset_time,
                    ttl
                )
                self._record_event(request, response, time.time() - start_time,
                                 "global", self.config.global_ip_limit.requests, 0)
                return response
        except Exception as e:
            logger.error(f"Global rate limit check failed: {e}")
            # Continue processing - don't block on storage errors

        # Check endpoint-specific limit
        rule = self._get_rate_limit_rule(request)
        endpoint_key = f"endpoint:{client_ip}:{path}"

        try:
            count, ttl = await self._store.incr(endpoint_key, rule.window)

            if count > rule.requests:
                reset_time = int(time.time() + ttl)
                response = self._create_rate_limit_response(
                    rule.requests,
                    0,
                    reset_time,
                    ttl
                )
                self._record_event(request, response, time.time() - start_time,
                                 "endpoint", rule.requests, 0)
                return response

            # Process request
            response = await call_next(request)

            # Add rate limit headers to successful responses
            remaining = max(0, rule.requests - count)
            if self.config.include_headers and hasattr(response, 'headers'):
                reset_time = int(time.time() + ttl)

                response.headers["X-RateLimit-Limit"] = str(rule.requests)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_time)

            # Record successful event
            self._record_event(request, response, time.time() - start_time,
                             "endpoint", rule.requests, remaining)

            return response

        except Exception as e:
            logger.error(f"Endpoint rate limit check failed: {e}")
            # Continue processing - don't block on storage errors
            response = await call_next(request)
            self._record_event(request, response, time.time() - start_time, "error")
            return response


# Configuration factory functions
def create_development_config() -> RateLimitConfig:
    """Create rate limiting configuration for development."""
    return RateLimitConfig(
        dev_multiplier=10.0,
        redis_url=os.getenv("REDIS_URL", None),
        bypass_ips={"127.0.0.1", "::1", "localhost"}
    )


def create_production_config() -> RateLimitConfig:
    """Create rate limiting configuration for production."""
    return RateLimitConfig(
        redis_url=os.getenv("REDIS_URL"),
        bypass_ips=set(),  # No bypasses in production
        include_headers=True
    )


def create_testing_config() -> RateLimitConfig:
    """Create rate limiting configuration for testing."""
    return RateLimitConfig(
        test_multiplier=100.0,
        redis_url=None,  # Use in-memory for tests
        bypass_ips={"127.0.0.1", "::1", "localhost", "testclient"}
    )
