"""
Comprehensive tests for rate limiting middleware
Tests IP-based and endpoint-specific rate limiting with various scenarios
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.middleware.rate_limiting import (
    RateLimitMiddleware,
    RateLimitConfig,
    RateLimitRule,
    InMemoryStore
)

# Try to import RedisStore, but don't fail if Redis is not available
try:
    from backend.api.middleware.rate_limiting import RedisStore
    REDIS_AVAILABLE = True
except (ImportError, AttributeError):
    RedisStore = None
    REDIS_AVAILABLE = False


# Test fixtures
@pytest.fixture
def basic_config():
    """Basic rate limiting configuration for testing."""
    return RateLimitConfig(
        default_limit=RateLimitRule(5, 60),  # 5 requests/minute
        endpoint_limits={
            "/api/upload": RateLimitRule(2, 60),    # 2 uploads/minute
            "/api/query": RateLimitRule(10, 60),    # 10 queries/minute
        },
        global_ip_limit=RateLimitRule(20, 3600),    # 20 requests/hour
        bypass_ips={"127.0.0.1"},
        include_headers=True,
        redis_url=None  # Use in-memory for tests
    )


@pytest.fixture
def test_app(basic_config):
    """FastAPI test application with rate limiting."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, config=basic_config)

    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.post("/api/upload")
    async def upload_endpoint():
        return {"message": "uploaded"}

    @app.get("/api/query")
    async def query_endpoint():
        return {"message": "query result"}

    @app.get("/api/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return app


@pytest.fixture
def test_client(test_app):
    """Test client for the rate limited app."""
    return TestClient(test_app)


class TestInMemoryStore:
    """Test the in-memory rate limiting store."""

    @pytest.fixture
    def store(self):
        return InMemoryStore()

    @pytest.mark.asyncio
    async def test_basic_increment(self, store):
        """Test basic counter increment."""
        count, ttl = await store.incr("test_key", 60)
        assert count == 1
        assert ttl == 60

        count, ttl = await store.incr("test_key", 60)
        assert count == 2
        assert ttl <= 60

    @pytest.mark.asyncio
    async def test_window_reset(self, store):
        """Test that counter resets after window expires."""
        # First increment
        count, _ = await store.incr("test_key", 1)  # 1-second window
        assert count == 1

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Should reset to 1
        count, _ = await store.incr("test_key", 1)
        assert count == 1

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, store):
        """Test that expired entries are cleaned up."""
        # Add entry with short TTL
        await store.set("expired_key", {"count": 1}, 1)

        # Verify it exists
        data = await store.get("expired_key")
        assert data is not None

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup should remove it
        await store._cleanup_expired()
        data = await store.get("expired_key")
        assert data is None


class TestRateLimitConfig:
    """Test rate limiting configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.default_limit.requests == 60
        assert config.default_limit.window == 60
        assert config.global_ip_limit.requests == 1000
        assert "127.0.0.1" in config.bypass_ips

    def test_endpoint_specific_limits(self):
        """Test endpoint-specific rate limits."""
        config = RateLimitConfig()

        # Upload endpoints should have lower limits
        assert config.endpoint_limits["/api/documents/upload"].requests == 10
        assert config.endpoint_limits["/api/library/upload"].requests == 10

        # Query endpoints should have higher limits
        assert config.endpoint_limits["/api/rag/query"].requests == 100


class TestRateLimitMiddleware:
    """Test the rate limiting middleware."""

    def test_bypass_localhost(self, test_client):
        """Test that localhost requests bypass rate limiting."""
        # Make many requests (more than limit)
        for _ in range(10):
            response = test_client.get("/api/test")
            assert response.status_code == 200

    def test_default_endpoint_rate_limit(self, test_client):
        """Test rate limiting on default endpoint."""
        # Change client IP to trigger rate limiting
        with patch.object(TestClient, '_client_ip', '192.168.1.100'):

            # Make requests up to the limit (5 per minute in test config)
            for i in range(5):
                response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.100"})
                assert response.status_code == 200

                # Check rate limit headers
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert int(response.headers["X-RateLimit-Remaining"]) == 4 - i

            # Next request should be rate limited
            response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.100"})
            assert response.status_code == 429

            # Check error response
            data = response.json()
            assert "Rate limit exceeded" in data["error"]
            assert data["limit"] == 5
            assert data["remaining"] == 0

    def test_endpoint_specific_limits(self, test_client):
        """Test endpoint-specific rate limits."""
        # Upload endpoint has limit of 2 per minute in test config
        for i in range(2):
            response = test_client.post("/api/upload", headers={"X-Forwarded-For": "192.168.1.101"})
            assert response.status_code == 200

        # Third request should be rate limited
        response = test_client.post("/api/upload", headers={"X-Forwarded-For": "192.168.1.101"})
        assert response.status_code == 429

        # Query endpoint has higher limit (10 per minute)
        for i in range(10):
            response = test_client.get("/api/query", headers={"X-Forwarded-For": "192.168.1.102"})
            assert response.status_code == 200

        # 11th request should be rate limited
        response = test_client.get("/api/query", headers={"X-Forwarded-For": "192.168.1.102"})
        assert response.status_code == 429

    def test_global_ip_limit(self, test_app):
        """Test global IP rate limiting."""
        # Create config with very low global limit for testing
        config = RateLimitConfig(
            default_limit=RateLimitRule(100, 60),  # High endpoint limit
            global_ip_limit=RateLimitRule(3, 3600),  # Low global limit
            bypass_ips=set(),  # No bypasses
            redis_url=None
        )

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Make requests up to global limit
        for i in range(3):
            response = client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.103"})
            assert response.status_code == 200

        # Next request should hit global limit
        response = client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.103"})
        assert response.status_code == 429

        # Check that it's the global limit that was hit
        data = response.json()
        assert data["limit"] == 3

    def test_different_ips_separate_limits(self, test_client):
        """Test that different IPs have separate rate limits."""
        # IP 1 hits its limit
        for _ in range(5):
            response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.104"})
            assert response.status_code == 200

        response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.104"})
        assert response.status_code == 429

        # IP 2 should still work
        response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.105"})
        assert response.status_code == 200

    def test_user_agent_bypass(self, test_app):
        """Test user agent bypass functionality."""
        config = RateLimitConfig(
            default_limit=RateLimitRule(2, 60),  # Low limit
            bypass_user_agents={"health-check", "monitor"},
            bypass_ips=set(),  # Remove IP bypasses
            redis_url=None
        )

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Regular requests should be limited
        for _ in range(2):
            response = client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.106"})
            assert response.status_code == 200

        response = client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.106"})
        assert response.status_code == 429

        # Health check user agent should bypass
        for _ in range(10):  # Make many requests
            response = client.get(
                "/api/test",
                headers={
                    "X-Forwarded-For": "192.168.1.107",
                    "User-Agent": "health-check-bot"
                }
            )
            assert response.status_code == 200

    def test_rate_limit_headers(self, test_client):
        """Test rate limit headers in responses."""
        response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.108"})
        assert response.status_code == 200

        # Check headers are present
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Check header values
        assert int(response.headers["X-RateLimit-Limit"]) == 5
        assert int(response.headers["X-RateLimit-Remaining"]) == 4

        # Reset time should be in the future
        reset_time = int(response.headers["X-RateLimit-Reset"])
        assert reset_time > int(time.time())

    def test_429_response_format(self, test_client):
        """Test 429 response format."""
        # Hit rate limit
        for _ in range(5):
            test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.109"})

        response = test_client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.109"})
        assert response.status_code == 429

        # Check response format
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "retry_after" in data
        assert "limit" in data
        assert "remaining" in data
        assert "reset" in data

        # Check headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert "Retry-After" in response.headers


class TestEnvironmentConfig:
    """Test environment-specific configurations."""

    @patch.dict('os.environ', {'ENVIRONMENT': 'development'})
    def test_development_config(self):
        """Test development configuration has relaxed limits."""
        from backend.api.rate_limit_config import get_rate_limit_config

        config = get_rate_limit_config()

        # Development should have higher limits
        assert config.default_limit.requests >= 600  # 10x production
        assert "127.0.0.1" in config.bypass_ips

    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    def test_production_config(self):
        """Test production configuration has strict limits."""
        from backend.api.rate_limit_config import get_rate_limit_config

        config = get_rate_limit_config()

        # Production should have strict limits
        assert config.default_limit.requests == 60
        assert len(config.bypass_ips) == 0  # No IP bypasses in production

    @patch.dict('os.environ', {'ENVIRONMENT': 'test'})
    def test_test_config(self):
        """Test testing configuration has very high limits."""
        from backend.api.rate_limit_config import get_rate_limit_config

        config = get_rate_limit_config()

        # Test should have very high limits
        assert config.default_limit.requests >= 6000  # 100x production
        assert "testclient" in config.bypass_ips

    @patch.dict('os.environ', {'RATE_LIMIT_DISABLE': 'true'})
    def test_rate_limit_disable(self):
        """Test disabling rate limiting via environment variable."""
        from backend.api.rate_limit_config import get_env_override_config, get_rate_limit_config

        base_config = get_rate_limit_config()
        config = get_env_override_config(base_config)

        # Should have very high limits (effectively disabled)
        assert config.default_limit.requests == 1000000
        assert config.global_ip_limit.requests == 1000000


class TestRedisIntegration:
    """Test Redis integration (if available)."""

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
    def test_redis_store_creation(self):
        """Test Redis store creation."""
        if RedisStore is not None:
            store = RedisStore("redis://localhost:6379", "test:")
            assert store.redis_url == "redis://localhost:6379"
            assert store.key_prefix == "test:"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
    async def test_redis_fallback(self):
        """Test fallback to in-memory when Redis fails."""
        if RedisStore is not None:
            # Mock Redis to fail
            with patch('backend.api.middleware.rate_limiting.aioredis') as mock_redis:
                mock_redis.from_url.side_effect = Exception("Redis connection failed")

                store = RedisStore("redis://invalid:6379")

                # Should not raise exception, should fallback gracefully
                try:
                    count, ttl = await store.incr("test_key", 60)
                    # If we get here, fallback worked
                    assert True
                except Exception:
                    # Should not happen with proper fallback
                    assert False, "Redis fallback failed"


class TestHighVolumeScenarios:
    """Test high volume and stress scenarios."""

    def test_concurrent_requests_same_ip(self, test_app):
        """Test many concurrent requests from same IP."""
        config = RateLimitConfig(
            default_limit=RateLimitRule(10, 60),
            global_ip_limit=RateLimitRule(50, 3600),
            bypass_ips=set(),
            redis_url=None
        )

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Make many requests quickly
        success_count = 0
        rate_limited_count = 0

        for i in range(15):  # More than the limit
            response = client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.200"})
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1

        # Should have exactly 10 successes and 5 rate limited
        assert success_count == 10
        assert rate_limited_count == 5

    def test_mixed_endpoint_requests(self, test_client):
        """Test requests across different endpoints with different limits."""
        ip = "192.168.1.201"
        headers = {"X-Forwarded-For": ip}

        # Use upload endpoint (limit: 2)
        for _ in range(2):
            response = test_client.post("/api/upload", headers=headers)
            assert response.status_code == 200

        # Upload should now be rate limited
        response = test_client.post("/api/upload", headers=headers)
        assert response.status_code == 429

        # But query endpoint should still work (limit: 10)
        response = test_client.get("/api/query", headers=headers)
        assert response.status_code == 200

        # And default endpoint should work too (limit: 5)
        response = test_client.get("/api/test", headers=headers)
        assert response.status_code == 200