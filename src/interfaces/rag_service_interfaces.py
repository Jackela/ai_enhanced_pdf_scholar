"""Interfaces for placeholder RAG services used by the API layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IRAGCacheManager(ABC):
    """Contract for cache helpers wired into the queries endpoints."""

    @abstractmethod
    def get_cached_query(self, *, query: str, document_id: int) -> str | None:
        """Return a cached result if one exists."""

    @abstractmethod
    def cache_query_result(
        self, query: str, document_id: int, result: str, ttl_seconds: int
    ) -> None:
        """Persist a query result for later reuse."""

    @abstractmethod
    def invalidate_document_cache(self, document_id: int) -> int:
        """Invalidate cached queries for a document."""

    @abstractmethod
    def get_cache_stats(self) -> dict[str, Any]:
        """Return implementation-specific cache statistics."""


class IRAGHealthChecker(ABC):
    """Health checking contract for the index routes."""

    @abstractmethod
    def perform_health_check(self) -> dict[str, Any]:
        """Return aggregated health information."""


class IRAGResourceManager(ABC):
    """Resource manager contract for index maintenance routes."""

    @abstractmethod
    def cleanup_orphaned_indexes(self) -> int:
        """Remove orphaned vector indexes."""

    @abstractmethod
    def get_storage_stats(self) -> dict[str, Any]:
        """Return storage statistics for vector indexes."""
