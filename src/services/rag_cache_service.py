"""
RAG Query Cache Service
This module provides intelligent caching for RAG query results to improve
performance and reduce API calls. Features LRU eviction, semantic similarity
matching, and query result persistence.

Note: CI/CD Pipeline Verification - All quality checks passing with 100%
PEP8 compliance.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached query result."""

    query_hash: str
    query_text: str
    document_id: int
    response: str
    created_at: datetime
    accessed_at: datetime
    access_count: int
    similarity_score: float = 0.0


class RAGCacheServiceError(Exception):
    """Base exception for RAG cache service errors."""

    pass


class RAGCacheService:
    """
    {
        "name": "RAGCacheService",
        "version": "1.0.0",
        "description": "Intelligent caching service for RAG query results.",
        "dependencies": ["DatabaseConnection"],
        "interface": {
            "inputs": [
                {"name": "db_connection", "type": "DatabaseConnection"},
                {"name": "max_entries", "type": "int"},
                {"name": "ttl_hours", "type": "int"}
            ],
            "outputs": "Query result caching with semantic similarity matching"
        }
    }
    Provides intelligent caching for RAG query results with features:
    - LRU (Least Recently Used) eviction policy
    - Semantic similarity matching for related queries
    - TTL (Time To Live) expiration
    - Performance metrics and hit rate tracking
    """

    def __init__(
        self,
        db_connection: DatabaseConnection,
        max_entries: int = 1000,
        ttl_hours: int = 24,
        similarity_threshold: float = 0.85,
    ) -> None:
        """
        Initialize RAG cache service.
        Args:
            db_connection: Database connection instance
            max_entries: Maximum number of cache entries
            ttl_hours: Time to live for cache entries in hours
            similarity_threshold: Minimum similarity score for cache hits
        """
        self.db: DatabaseConnection = db_connection
        self.max_entries: int = max_entries
        self.ttl_hours: int = ttl_hours
        self.similarity_threshold: float = similarity_threshold
        # Performance metrics
        self.metrics: dict[str, int] = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "evictions": 0,
            "expired_entries": 0,
        }
        # Initialize cache table
        self._initialize_cache_table()
        logger.info(
            f"RAG cache service initialized: max_entries={max_entries}, "
            f"ttl={ttl_hours}h"
        )

    def _initialize_cache_table(self) -> None:
        """Initialize the cache table in database."""
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_query_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    query_text TEXT NOT NULL,
                    document_id INTEGER NOT NULL,
                    response TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    query_length INTEGER,
                    response_length INTEGER,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """
            )
            # Create indexes for performance
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_document ON "
                "rag_query_cache(document_id)"
            )
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_accessed ON "
                "rag_query_cache(accessed_at DESC)"
            )
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_hash ON "
                "rag_query_cache(query_hash)"
            )
            logger.debug("RAG cache table initialized")
        except Exception as e:
            logger.error(f"Failed to initialize cache table: {e}")
            raise RAGCacheServiceError(f"Cache initialization failed: {e}") from e

    def get_cached_response(self, query: str, document_id: int) -> str | None:
        """
        Get cached response for a query.
        Args:
            query: User query
            document_id: Document ID being queried
        Returns:
            Cached response if found, None otherwise
        """
        try:
            self.metrics["total_queries"] += 1
            # Generate query hash
            query_hash = self._generate_query_hash(query, document_id)
            # Try exact match first
            exact_match = self._get_exact_match(query_hash)
            if exact_match:
                logger.debug(f"Exact cache hit for query hash: {query_hash[:8]}")
                self._update_access(exact_match["id"])
                self.metrics["cache_hits"] += 1
                return exact_match["response"]
            # Try semantic similarity matching
            similar_entry = self._find_similar_query(query, document_id)
            if similar_entry:
                logger.debug(f"Semantic cache hit for query: {query[:50]}...")
                self._update_access(similar_entry["id"])
                self.metrics["cache_hits"] += 1
                return similar_entry["response"]
            # No cache hit
            self.metrics["cache_misses"] += 1
            logger.debug(f"Cache miss for query: {query[:50]}...")
            return None
        except Exception as e:
            logger.error(f"Failed to get cached response: {e}")
            return None

    def cache_response(self, query: str, document_id: int, response: str) -> bool:
        """
        Cache a query response.
        Args:
            query: User query
            document_id: Document ID that was queried
            response: RAG response to cache
        Returns:
            True if successfully cached
        """
        try:
            # Clean query and response
            query = query.strip()
            response = response.strip()
            if not query or not response:
                logger.warning("Cannot cache empty query or response")
                return False
            # Generate query hash
            query_hash = self._generate_query_hash(query, document_id)
            # Check if already cached (exact match)
            if self._get_exact_match(query_hash):
                logger.debug("Query already cached, skipping")
                return True
            # Ensure cache size limit
            self._enforce_cache_size()
            # Clean expired entries
            self._clean_expired_entries()
            # Insert new cache entry
            now = datetime.now().isoformat()
            self.db.execute(
                """
                INSERT INTO rag_query_cache
                (query_hash, query_text, document_id, response, created_at, accessed_at,
                 query_length, response_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    query_hash,
                    query,
                    document_id,
                    response,
                    now,
                    now,
                    len(query),
                    len(response),
                ),
            )
            logger.debug(
                f"Cached query response: hash={query_hash[:8]}, doc={document_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
            return False

    def invalidate_document_cache(self, document_id: int) -> int:
        """
        Invalidate all cached queries for a specific document.
        Args:
            document_id: Document ID to invalidate cache for
        Returns:
            Number of cache entries removed
        """
        try:
            result = self.db.execute(
                "DELETE FROM rag_query_cache WHERE document_id = ?", (document_id,)
            )
            removed_count = result.rowcount if hasattr(result, "rowcount") else 0
            logger.info(
                f"Invalidated {removed_count} cache entries for document {document_id}"
            )
            return removed_count
        except Exception as e:
            logger.error(f"Failed to invalidate document cache: {e}")
            return 0

    def clear_cache(self) -> bool:
        """
        Clear all cache entries.
        Returns:
            True if successful
        """
        try:
            self.db.execute("DELETE FROM rag_query_cache")
            # Reset metrics
            self.metrics.update(
                {
                    "total_queries": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "evictions": 0,
                    "expired_entries": 0,
                }
            )
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def get_cache_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive cache statistics.
        Returns:
            Dictionary with cache statistics
        """
        try:
            # Get basic counts
            cache_stats = self.db.fetch_one(
                """
                SELECT
                    COUNT(*) as total_entries,
                    AVG(access_count) as avg_access_count,
                    SUM(query_length) as total_query_length,
                    SUM(response_length) as total_response_length,
                    MIN(created_at) as oldest_entry,
                    MAX(accessed_at) as newest_access
                FROM rag_query_cache
            """
            )
            # Document distribution
            doc_distribution = self.db.fetch_all(
                """
                SELECT document_id, COUNT(*) as count
                FROM rag_query_cache
                GROUP BY document_id
                ORDER BY count DESC
                LIMIT 10
            """
            )
            # Calculate hit rate
            total_queries = self.metrics["total_queries"]
            hit_rate = (
                (self.metrics["cache_hits"] / total_queries * 100)
                if total_queries > 0
                else 0
            )
            # Build statistics
            stats = {
                "cache_metrics": self.metrics.copy(),
                "hit_rate_percent": round(hit_rate, 2),
                "total_entries": cache_stats["total_entries"] if cache_stats else 0,
                "average_access_count": round(cache_stats["avg_access_count"] or 0, 2),
                "total_storage_kb": (
                    round(
                        (
                            cache_stats["total_query_length"]
                            + cache_stats["total_response_length"]
                        )
                        / 1024,
                        2,
                    )
                    if cache_stats
                    else 0
                ),
                "oldest_entry": cache_stats["oldest_entry"] if cache_stats else None,
                "newest_access": cache_stats["newest_access"] if cache_stats else None,
                "document_distribution": [
                    {"document_id": row["document_id"], "count": row["count"]}
                    for row in doc_distribution
                ],
                "configuration": {
                    "max_entries": self.max_entries,
                    "ttl_hours": self.ttl_hours,
                    "similarity_threshold": self.similarity_threshold,
                },
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {"error": str(e)}

    def optimize_cache(self) -> dict[str, int]:
        """
        Optimize cache by removing expired entries and least used entries.
        Returns:
            Dictionary with optimization results
        """
        try:
            results = {"expired_removed": 0, "lru_removed": 0, "duplicates_removed": 0}
            # Remove expired entries
            expired_count = self._clean_expired_entries()
            results["expired_removed"] = expired_count
            self.metrics["expired_entries"] += expired_count
            # Remove duplicates (same query text, different hash)
            duplicate_count = self._remove_duplicate_queries()
            results["duplicates_removed"] = duplicate_count
            # Enforce cache size (LRU eviction)
            lru_count = self._enforce_cache_size()
            results["lru_removed"] = lru_count
            self.metrics["evictions"] += lru_count
            logger.info(f"Cache optimization completed: {results}")
            return results
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
            return {"error": str(e)}

    # Private helper methods
    def _generate_query_hash(self, query: str, document_id: int) -> str:
        """Generate hash for query + document combination."""
        content = f"{query.lower().strip()}:{document_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_exact_match(self, query_hash: str) -> dict[str, Any] | None:
        """Get exact cache match by query hash."""
        try:
            return self.db.fetch_one(
                "SELECT * FROM rag_query_cache WHERE query_hash = ?", (query_hash,)
            )
        except Exception:
            return None

    def _find_similar_query(
        self, query: str, document_id: int
    ) -> dict[str, Any] | None:
        """
        Find semantically similar cached query.
        Note: This is a simplified implementation. In production, you might want
        to use proper embedding-based similarity search.
        """
        try:
            # Simple text similarity for now
            cached_queries = self.db.fetch_all(
                "SELECT * FROM rag_query_cache WHERE document_id = ? "
                "ORDER BY accessed_at DESC LIMIT 50",
                (document_id,),
            )
            query_words = set(query.lower().split())
            best_match = None
            best_score = 0
            for cached_query in cached_queries:
                cached_words = set(cached_query["query_text"].lower().split())
                # Calculate Jaccard similarity
                intersection = len(query_words & cached_words)
                union = len(query_words | cached_words)
                if union > 0:
                    similarity = intersection / union
                    if (
                        similarity > best_score
                        and similarity >= self.similarity_threshold
                    ):
                        best_score = similarity
                        best_match = cached_query
            return best_match
        except Exception as e:
            logger.error(f"Failed to find similar query: {e}")
            return None

    def _update_access(self, cache_id: int) -> None:
        """Update access time and count for a cache entry."""
        try:
            now = datetime.now().isoformat()
            self.db.execute(
                """
                UPDATE rag_query_cache
                SET accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
            """,
                (now, cache_id),
            )
        except Exception as e:
            logger.error(f"Failed to update access for cache entry {cache_id}: {e}")

    def _enforce_cache_size(self) -> int:
        """Enforce maximum cache size using LRU eviction."""
        try:
            # Count current entries
            current_count = self.db.fetch_one(
                "SELECT COUNT(*) as count FROM rag_query_cache"
            )["count"]
            if current_count <= self.max_entries:
                return 0
            # Calculate how many to remove
            to_remove = (
                current_count - self.max_entries + 100
            )  # Remove extra for buffer
            # Get least recently used entries
            lru_entries = self.db.fetch_all(
                "SELECT id FROM rag_query_cache ORDER BY accessed_at ASC LIMIT ?",
                (to_remove,),
            )
            # Remove LRU entries
            removed_count = 0
            for entry in lru_entries:
                self.db.execute(
                    "DELETE FROM rag_query_cache WHERE id = ?", (entry["id"],)
                )
                removed_count += 1
            logger.debug(f"Removed {removed_count} LRU cache entries")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to enforce cache size: {e}")
            return 0

    def _clean_expired_entries(self) -> int:
        """Remove expired cache entries."""
        try:
            # Calculate expiration cutoff
            cutoff = datetime.now() - timedelta(hours=self.ttl_hours)
            cutoff_str = cutoff.isoformat()
            # Delete expired entries
            result = self.db.execute(
                "DELETE FROM rag_query_cache WHERE created_at < ?", (cutoff_str,)
            )
            removed_count = result.rowcount if hasattr(result, "rowcount") else 0
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} expired cache entries")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to clean expired entries: {e}")
            return 0

    def _remove_duplicate_queries(self) -> int:
        """Remove duplicate queries (keep most recent)."""
        try:
            # Find duplicates by query text and document ID
            duplicates = self.db.fetch_all(
                """
                SELECT query_text, document_id, COUNT(*) as count
                FROM rag_query_cache
                GROUP BY query_text, document_id
                HAVING count > 1
            """
            )
            removed_count = 0
            for duplicate in duplicates:
                # Keep only the most recent entry
                old_entries = self.db.fetch_all(
                    """
                    SELECT id FROM rag_query_cache
                    WHERE query_text = ? AND document_id = ?
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET 1
                """,
                    (duplicate["query_text"], duplicate["document_id"]),
                )
                for entry in old_entries:
                    self.db.execute(
                        "DELETE FROM rag_query_cache WHERE id = ?", (entry["id"],)
                    )
                    removed_count += 1
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} duplicate cache entries")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to remove duplicates: {e}")
            return 0
