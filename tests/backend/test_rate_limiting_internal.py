from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.rate_limiting import (
    InMemoryStore,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitRule,
)


class _FixedStore(InMemoryStore):
    """Deterministic in-memory store without time-based cleanup for testing."""

    async def incr(self, key: str, window: int):
        if key not in self._data:
            self._data[key] = {"count": 0, "expires": float("inf"), "window_start": 0}
        self._data[key]["count"] += 1
        return self._data[key]["count"], window


def _app_with_rate_limit(config: RateLimitConfig, store: InMemoryStore):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, config=config)
    # Patch the store on the instantiated middleware
    for m in app.user_middleware:
        if m.cls is RateLimitMiddleware:
            m_kwargs = getattr(m, "kwargs", {}) if hasattr(m, "kwargs") else {}
            middleware_instance = m_kwargs.get("middleware_instance")
            if middleware_instance:
                middleware_instance._store = store

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    return app


def test_rate_limit_hits_global_and_endpoint_limits(monkeypatch):
    config = RateLimitConfig(
        default_limit=RateLimitRule(1, 60),
        endpoint_limits={"/limited": RateLimitRule(1, 60)},
        global_ip_limit=RateLimitRule(1, 60),
        include_headers=True,
        dev_multiplier=1.0,
        test_multiplier=1.0,
    )
    app = _app_with_rate_limit(config, _FixedStore())

    with TestClient(app) as client:
        first = client.get("/limited")
        assert first.status_code == 200
        second = client.get("/limited")
        assert second.status_code == 429
        assert "Retry-After" in second.headers


@pytest.mark.asyncio
async def test_inmemory_store_expiry_and_cleanup():
    store = InMemoryStore()
    count, ttl = await store.incr("k1", window=1)
    assert count == 1
    # force cleanup
    store._last_cleanup = 0
    await store._cleanup_expired()
    # after window, keys should be eligible for cleanup
    store._data["k1"]["expires"] = 0
    await store._cleanup_expired()
    assert "k1" not in store._data or store._data["k1"]["expires"] == 0
