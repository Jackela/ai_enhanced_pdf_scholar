"""
Rate Limiting Configuration Module
Provides environment-aware configuration for rate limiting
"""

import os

from backend.api.middleware.rate_limiting import RateLimitConfig, RateLimitRule


def get_rate_limit_config() -> RateLimitConfig:
    """Get rate limiting configuration based on environment."""

    environment = os.getenv("ENVIRONMENT", "development").lower()
    redis_url = os.getenv("REDIS_URL")

    if environment == "production":
        return create_production_config(redis_url)
    elif environment == "test":
        return create_test_config(redis_url)
    else:  # development or default
        return create_development_config(redis_url)


def create_production_config(redis_url: str | None = None) -> RateLimitConfig:
    """Create production rate limiting configuration."""

    return RateLimitConfig(
        # Conservative production limits
        default_limit=RateLimitRule(60, 60),  # 60 requests/minute
        endpoint_limits={
            # Upload endpoints - very restrictive
            "/api/documents/upload": RateLimitRule(5, 60),  # 5 uploads/minute
            "/api/library/upload": RateLimitRule(5, 60),  # 5 uploads/minute
            # Processing endpoints - moderate
            "/api/rag/query": RateLimitRule(30, 60),  # 30 queries/minute
            "/api/rag/chat": RateLimitRule(50, 60),  # 50 chat/minute
            "/api/documents/query": RateLimitRule(30, 60),  # 30 doc queries/minute
            # Read-only endpoints - generous
            "/api/documents": RateLimitRule(100, 60),  # 100 reads/minute
            "/api/library": RateLimitRule(100, 60),  # 100 library ops/minute
            # System endpoints
            "/api/system/health": RateLimitRule(1000, 60),  # Health checks
            "/api/system": RateLimitRule(20, 60),  # Admin operations
        },
        # Global limits
        global_ip_limit=RateLimitRule(500, 3600),  # 500 requests/hour per IP
        # Redis configuration
        redis_url=redis_url,
        redis_key_prefix="rl:prod:",
        # No bypasses in production
        bypass_ips=set(),
        bypass_user_agents={"monitor", "health-check"},
        # Response configuration
        include_headers=True,
        block_duration=300,  # 5-minute block after limit exceeded
    )


def create_development_config(redis_url: str | None = None) -> RateLimitConfig:
    """Create development rate limiting configuration."""

    return RateLimitConfig(
        # Relaxed development limits (10x production)
        default_limit=RateLimitRule(600, 60),  # 600 requests/minute
        endpoint_limits={
            # Upload endpoints
            "/api/documents/upload": RateLimitRule(50, 60),  # 50 uploads/minute
            "/api/library/upload": RateLimitRule(50, 60),  # 50 uploads/minute
            # Processing endpoints
            "/api/rag/query": RateLimitRule(300, 60),  # 300 queries/minute
            "/api/rag/chat": RateLimitRule(500, 60),  # 500 chat/minute
            "/api/documents/query": RateLimitRule(300, 60),  # 300 doc queries/minute
            # Read-only endpoints
            "/api/documents": RateLimitRule(1000, 60),  # 1000 reads/minute
            "/api/library": RateLimitRule(1000, 60),  # 1000 library ops/minute
            # System endpoints - no limits in dev
            "/api/system/health": RateLimitRule(10000, 60),  # Unlimited health checks
            "/api/system": RateLimitRule(200, 60),  # 200 admin ops/minute
        },
        # Global limits - very high for development
        global_ip_limit=RateLimitRule(5000, 3600),  # 5000 requests/hour
        # Redis configuration (optional in dev)
        redis_url=redis_url,
        redis_key_prefix="rl:dev:",
        # Localhost bypass
        bypass_ips={"127.0.0.1", "::1", "localhost"},
        bypass_user_agents={"monitor", "health-check", "development"},
        # Response configuration
        include_headers=True,
        block_duration=60,  # 1-minute block
    )


def create_test_config(redis_url: str | None = None) -> RateLimitConfig:
    """Create test rate limiting configuration."""

    return RateLimitConfig(
        # Very high limits for testing (100x production)
        default_limit=RateLimitRule(6000, 60),  # 6000 requests/minute
        endpoint_limits={
            # All endpoints get high limits for testing
            "/api/documents/upload": RateLimitRule(500, 60),
            "/api/library/upload": RateLimitRule(500, 60),
            "/api/rag/query": RateLimitRule(3000, 60),
            "/api/rag/chat": RateLimitRule(5000, 60),
            "/api/documents/query": RateLimitRule(3000, 60),
            "/api/documents": RateLimitRule(10000, 60),
            "/api/library": RateLimitRule(10000, 60),
            "/api/system/health": RateLimitRule(100000, 60),
            "/api/system": RateLimitRule(2000, 60),
        },
        # Very high global limits for testing
        global_ip_limit=RateLimitRule(50000, 3600),  # 50k requests/hour
        # No Redis in tests (use in-memory)
        redis_url=None,
        redis_key_prefix="rl:test:",
        # Bypass everything in tests
        bypass_ips={"127.0.0.1", "::1", "localhost", "testclient"},
        bypass_user_agents={"test", "pytest", "monitor", "health-check"},
        # Response configuration
        include_headers=True,
        block_duration=1,  # Minimal block duration for tests
    )


# Environment variable configurations
RATE_LIMIT_ENV_VARS = {
    "REDIS_URL": "Redis connection URL for distributed rate limiting",
    "RATE_LIMIT_REDIS_PREFIX": "Redis key prefix for rate limiting (default: rl:)",
    "RATE_LIMIT_GLOBAL_LIMIT": "Global requests per hour per IP (default: varies by env)",
    "RATE_LIMIT_DEFAULT_LIMIT": "Default requests per minute (default: varies by env)",
    "RATE_LIMIT_UPLOAD_LIMIT": "Upload requests per minute (default: varies by env)",
    "RATE_LIMIT_DISABLE": "Set to 'true' to disable rate limiting completely",
}


def get_env_override_config(base_config: RateLimitConfig) -> RateLimitConfig:
    """Apply environment variable overrides to base configuration."""

    # Check if rate limiting is completely disabled
    if os.getenv("RATE_LIMIT_DISABLE", "").lower() == "true":
        # Return a config with very high limits (effectively disabled)
        return RateLimitConfig(
            default_limit=RateLimitRule(1000000, 60),
            global_ip_limit=RateLimitRule(1000000, 3600),
            endpoint_limits={},
            redis_url=None,
            bypass_ips={"*"},  # Bypass everything
        )

    # Apply specific overrides
    if global_limit := os.getenv("RATE_LIMIT_GLOBAL_LIMIT"):
        try:
            base_config.global_ip_limit.requests = int(global_limit)
        except ValueError:
            pass

    if default_limit := os.getenv("RATE_LIMIT_DEFAULT_LIMIT"):
        try:
            base_config.default_limit.requests = int(default_limit)
        except ValueError:
            pass

    if upload_limit := os.getenv("RATE_LIMIT_UPLOAD_LIMIT"):
        try:
            limit_val = int(upload_limit)
            base_config.endpoint_limits["/api/documents/upload"] = RateLimitRule(
                limit_val, 60
            )
            base_config.endpoint_limits["/api/library/upload"] = RateLimitRule(
                limit_val, 60
            )
        except ValueError:
            pass

    if redis_prefix := os.getenv("RATE_LIMIT_REDIS_PREFIX"):
        base_config.redis_key_prefix = redis_prefix

    return base_config
