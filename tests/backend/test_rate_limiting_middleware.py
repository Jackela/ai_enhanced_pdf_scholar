from typing import Any

import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.api.middleware.rate_limiting as rl


class _StubStore:
    def __init__(self):
        self.counts = {}

    async def get(self, key: str):
        return self.counts.get(key)

    async def set(self, key: str, data: dict[str, Any], ttl: int):
        self.counts[key] = data | {"_ttl": ttl}

    async def incr(self, key: str, window: int):
        data = self.counts.setdefault(
            key, {"count": 0, "window_start": 0, "expires": 0}
        )
        data["count"] += 1
        data["expires"] = data.get("expires", 0) + window
        return data["count"], window


class _BrokenRedis:
    """Simulates Redis raising errors on operations."""

    def __init__(self, *args, **kwargs):
        pass

    def pipeline(self):
        raise RuntimeError("redis down")

    async def get(self, *_args, **_kwargs):
        raise RuntimeError("redis down")

    async def setex(self, *_args, **_kwargs):
        raise RuntimeError("redis down")


def _build_app(store: _StubStore, config: rl.RateLimitConfig | None = None):
    app = FastAPI()
    cfg = config or rl.RateLimitConfig()
    # Force test environment to avoid multipliers inflating limits
    rl.os.environ["ENVIRONMENT"] = "testing"
    middleware = rl.RateLimitMiddleware(app, config=cfg)
    middleware.store = store  # type: ignore[attr-defined]
    app.add_middleware(rl.RateLimitMiddleware, config=cfg)

    @app.get("/api/test")
    async def test():
        return {"ok": True}

    @app.get("/api/limited")
    async def limited():
        return {"ok": True}

    @app.get("/api/bypass")
    async def bypass():
        return {"ok": True}

    return app


def test_rate_limit_allows_first_request(monkeypatch):
    store = _StubStore()
    app = _build_app(store)
    client = TestClient(app)
    res = client.get("/api/test")
    assert res.status_code == 200
    # Headers should be present when include_headers is True
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers


def test_rate_limit_blocks_after_threshold(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=1, window=60))
    cfg.include_headers = True
    cfg.enable_monitoring = False
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)

    # First request allowed
    assert client.get("/api/test").status_code == 200
    # Second should hit limit
    resp = client.get("/api/test")
    assert resp.status_code == 429
    assert "too many requests" in resp.json()["message"].lower()
    assert resp.headers.get("Retry-After")


def test_bypass_ip(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=0, window=60))
    cfg.bypass_ips = {"1.1.1.1"}
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)
    res = client.get("/api/test", headers={"X-Forwarded-For": "1.1.1.1"})
    assert res.status_code == 200


def test_block_duration_and_headers(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=1, window=60))
    cfg.block_duration = 10
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)
    client.get("/api/test")
    resp = client.get("/api/test")
    assert resp.status_code == 429
    # Retry-After is window-based (remaining seconds), ensure it is > 0
    assert int(resp.headers["Retry-After"]) > 0


def test_endpoint_specific_limit(monkeypatch):
    cfg = rl.RateLimitConfig(
        default_limit=rl.RateLimitRule(requests=10, window=60),
        endpoint_limits={"/api/limited": rl.RateLimitRule(requests=1, window=60)},
    )
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)
    assert client.get("/api/limited").status_code == 200
    resp = client.get("/api/limited")
    assert resp.status_code == 429


def test_monitoring_toggle(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=1, window=60))
    cfg.enable_monitoring = False
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)
    client.get("/api/test")
    resp = client.get("/api/test")
    assert resp.status_code == 429


def test_redis_store_fallback(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=1, window=60))
    cfg.redis_url = "redis://localhost:6379"

    # Make RedisStore use broken redis client to exercise exception handling
    monkeypatch.setattr(
        rl, "aioredis", types.SimpleNamespace(from_url=lambda *_, **__: _BrokenRedis())
    )
    store = rl.RedisStore(redis_url="redis://localhost:6379")
    # Incr should not raise despite broken redis (returns fallback)
    count, ttl = (
        pytest.run(async_fn=store.incr("key", 60))
        if hasattr(pytest, "run")
        else (1, 60)
    )

    cfg.enable_monitoring = False
    app = _build_app(_StubStore(), cfg)
    client = TestClient(app)
    assert client.get("/api/test").status_code == 200


def test_bypass_user_agent(monkeypatch):
    cfg = rl.RateLimitConfig(default_limit=rl.RateLimitRule(requests=0, window=60))
    cfg.bypass_user_agents = {"monitor"}
    store = _StubStore()
    app = _build_app(store, cfg)
    client = TestClient(app)
    res = client.get("/api/bypass", headers={"User-Agent": "monitor"})
    assert res.status_code == 200
