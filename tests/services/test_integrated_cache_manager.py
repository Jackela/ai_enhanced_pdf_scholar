from __future__ import annotations

import time

import pytest

from backend.config.caching_config import CachingConfig
from backend.services.integrated_cache_manager import IntegratedCacheManager


class _StubMetric:
    def __init__(self):
        self.calls = []

    def labels(self, **labels):
        parent = self

        class _Recorder:
            def inc(self_inner, value: int = 1):
                parent.calls.append(("inc", labels, value))

            def observe(self_inner, value: float):
                parent.calls.append(("observe", labels, value))

        return _Recorder()


class _StubMetrics:
    def __init__(self):
        self.cache_operations_total = _StubMetric()
        self.cache_operation_duration = _StubMetric()


@pytest.mark.asyncio
async def test_handle_cache_hit_updates_stats_and_metrics():
    manager = IntegratedCacheManager(CachingConfig(), metrics=_StubMetrics())
    result = await manager._handle_cache_hit(
        value="payload",
        level="L1",
        source="memory",
        start_time=time.time(),
    )
    assert result.hit is True
    assert manager.statistics.total_hits == 1
    assert manager.statistics.l1_hits == 1
    assert manager.metrics.cache_operations_total.calls
    assert manager.metrics.cache_operation_duration.calls


@pytest.mark.asyncio
async def test_handle_cache_miss_updates_stats_and_metrics():
    manager = IntegratedCacheManager(CachingConfig(), metrics=_StubMetrics())
    result = await manager._handle_cache_miss(start_time=time.time(), default="none")
    assert result.hit is False
    assert result.value == "none"
    assert manager.statistics.total_misses == 1
    assert manager.metrics.cache_operations_total.calls
    assert manager.metrics.cache_operation_duration.calls


@pytest.mark.asyncio
async def test_coherency_step_runs_manager_and_updates_stats():
    manager = IntegratedCacheManager(CachingConfig(), metrics=_StubMetrics())

    class _StubCoherency:
        def __init__(self):
            self.called = 0

        async def run_coherency_check(self):
            self.called += 1

    manager.coherency_manager = _StubCoherency()
    interval = await manager._coherency_step()

    assert manager.coherency_manager.called == 1
    assert manager.statistics.coherency_operations == 1
    assert interval == manager.config.coherency.coherency_check_interval


@pytest.mark.asyncio
async def test_performance_step_collects_metrics(monkeypatch):
    manager = IntegratedCacheManager(CachingConfig(), metrics=_StubMetrics())
    called: dict[str, bool] = {"ran": False}

    async def _fake_collect():
        called["ran"] = True

    monkeypatch.setattr(manager, "_collect_performance_metrics", _fake_collect)
    interval = await manager._performance_step()

    assert called["ran"] is True
    assert interval == manager.config.metrics_collection_interval


@pytest.mark.asyncio
async def test_warming_step_respects_prefetch_toggle():
    manager = IntegratedCacheManager(CachingConfig(), metrics=_StubMetrics())
    manager.warming_service = object()

    manager.config.prefetch_popular_content = True
    assert await manager._warming_step() == 300.0

    manager.config.prefetch_popular_content = False
    assert await manager._warming_step() == 600.0
