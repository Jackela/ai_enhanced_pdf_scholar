"""Core stubs for prometheus_client."""

from __future__ import annotations

from . import CollectorRegistry

REGISTRY = CollectorRegistry()

__all__ = ["CollectorRegistry", "REGISTRY"]
