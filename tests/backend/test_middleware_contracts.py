from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.error_handling import (
    ErrorHandlingMiddleware,
    setup_error_handlers,
)
from backend.api.middleware.rate_limiting import (
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitRule,
)


def test_error_handling_middleware_standardizes_response():
    app = FastAPI()
    setup_error_handlers(app)
    app.add_middleware(ErrorHandlingMiddleware, include_debug_info=False)

    @app.get("/boom")
    def boom() -> None:  # pragma: no cover - exercised via middleware
        raise ValueError("boom")

    with TestClient(app) as client:
        resp = client.get("/boom")

    assert resp.status_code in (400, 500)
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["status_code"] == resp.status_code
    assert payload["error"]["correlation_id"]


def test_rate_limit_middleware_blocks_after_threshold():
    config = RateLimitConfig(
        default_limit=RateLimitRule(1, 60),
        endpoint_limits={},
        global_ip_limit=RateLimitRule(100, 60),
        bypass_ips=set(),
        bypass_user_agents=set(),
        include_headers=True,
        enable_monitoring=False,
        dev_multiplier=1.0,
        test_multiplier=1.0,
    )
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, config=config)

    @app.get("/")
    async def root():
        return {"ok": True}

    with TestClient(app) as client:
        first = client.get("/")
        assert first.status_code == 200
        assert first.headers.get("X-RateLimit-Limit") == "1"
        assert first.headers.get("X-RateLimit-Remaining") == "0"

        second = client.get("/")
        assert second.status_code == 429
        assert second.headers.get("Retry-After")
        body = second.json()
        assert body["error"] == "Rate limit exceeded"
        assert body["limit"] == 1
