"""Lightweight stub of prometheus_client for local development."""

from __future__ import annotations

from typing import Any

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class CollectorRegistry:
    def __init__(self) -> None:
        self.metrics: list[_Metric] = []


class _Metric:
    def __init__(self, *args: Any, registry: CollectorRegistry | None = None, **kwargs: Any) -> None:
        if registry is not None:
            registry.metrics.append(self)

    def labels(self, *args: Any, **kwargs: Any) -> _Metric:
        return self

    def inc(self, *args: Any, **kwargs: Any) -> None:
        return None

    def dec(self, *args: Any, **kwargs: Any) -> None:
        return None

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set(self, *args: Any, **kwargs: Any) -> None:
        return None

    def time(self, *args: Any, **kwargs: Any) -> _Metric:
        return self

    def state(self, *args: Any, **kwargs: Any) -> None:
        return None

    def info(self, *args: Any, **kwargs: Any) -> None:
        return None


class Counter(_Metric):
    pass


class Gauge(_Metric):
    pass


class Histogram(_Metric):
    pass


class Summary(_Metric):
    pass


class Enum(_Metric):
    pass


class Info(_Metric):
    pass


def generate_latest(registry: CollectorRegistry | None = None) -> bytes:
    return b""


def push_to_gateway(*args: Any, **kwargs: Any) -> None:
    return None


def start_http_server(*args: Any, **kwargs: Any) -> None:
    return None
