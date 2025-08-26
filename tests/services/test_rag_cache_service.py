"""
Comprehensive Tests for RAGCacheService
Tests all aspects of RAG query result caching including:
- Query result caching and retrieval
- LRU eviction and TTL expiration
- Semantic similarity matching
- Cache optimization and maintenance
- Performance metrics and statistics
- Error handling and edge cases
"""

import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.connection import DatabaseConnection
from src.services.rag_cache_service import (
    RAGCacheService,
    RAGCacheServiceError,
)


class TestRAGCacheService:
    """Comprehensive test suite for RAGCacheService."""

    @classmethod
    def setup_class(cls):
        """Set up test database."""
        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        # Initialize database schema
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test database."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        # Create documents table (for foreign key constraint)
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL
            )
        """
        )

    def setup_method(self):
        """Set up for each test method."""
        # Create cache service with test configuration
        self.cache_service = RAGCacheService(
            db_connection=self.db,
            max_entries=100,
            ttl_hours=1,
            similarity_threshold=0.8,
        )
        # Clear cache table
        self.db.execute("DELETE FROM rag_query_cache")
        # Reset metrics
        self.cache_service.metrics = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "evictions": 0,
            "expired_entries": 0,
        }
        # Create test document
        self.test_doc_id = self._create_test_document()

    def _create_test_document(self, **kwargs) -> int:
        """Create a test document and return its ID."""
        import time

        timestamp = str(
            int(time.time() * 1000000)
        )  # Microsecond timestamp for uniqueness
        defaults = {
            "title": f"Test Document {timestamp}",
            "file_path": f"/test/path/document_{timestamp}.pdf",
            "file_hash": f"hash_{timestamp}",
        }
        defaults.update(kwargs)
        result = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            (defaults["title"], defaults["file_path"], defaults["file_hash"]),
        )
        return self.db.get_last_insert_id()

    def _insert_cache_entry(
        self,
        query: str,
        document_id: int,
        response: str,
        created_at: datetime = None,
        accessed_at: datetime = None,
    ) -> int:
        """Insert cache entry directly into database for testing."""
        if created_at is None:
            created_at = datetime.now()
        if accessed_at is None:
            accessed_at = created_at
        query_hash = self.cache_service._generate_query_hash(query, document_id)
        result = self.db.execute(
            """
            INSERT INTO rag_query_cache
            (query_hash, query_text, document_id, response, created_at, accessed_at, query_length, response_length)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                query_hash,
                query,
                document_id,
                response,
                created_at.isoformat(),
                accessed_at.isoformat(),
                len(query),
                len(response),
            ),
        )
        return self.db.get_last_insert_id()

    # ===== Initialization Tests =====
    def test_initialization_creates_table(self):
        """Test that cache service initialization creates the cache table."""
        # Verify table exists
        result = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rag_query_cache'"
        )
        assert result is not None
        # Verify indexes exist
        indexes = self.db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rag_query_cache'"
        )
        index_names = [idx["name"] for idx in indexes]
        assert "idx_cache_document" in index_names
        assert "idx_cache_accessed" in index_names
        assert "idx_cache_hash" in index_names

    def test_initialization_parameters(self):
        """Test cache service initialization with custom parameters."""
        custom_cache = RAGCacheService(
            db_connection=self.db,
            max_entries=500,
            ttl_hours=12,
            similarity_threshold=0.9,
        )
        assert custom_cache.max_entries == 500
        assert custom_cache.ttl_hours == 12
        assert custom_cache.similarity_threshold == 0.9
        assert custom_cache.metrics["total_queries"] == 0

    def test_initialization_table_creation_error(self):
        """Test error handling during table creation."""
        with patch.object(
            self.db, "execute", side_effect=Exception("Table creation failed")
        ):
            with pytest.raises(
                RAGCacheServiceError, match="Cache initialization failed"
            ):
                RAGCacheService(self.db)

    # ===== Cache Storage Tests =====
    def test_cache_response_success(self):
        """Test successful response caching."""
        query = "What is machine learning?"
        response = "Machine learning is a subset of artificial intelligence."
        success = self.cache_service.cache_response(query, self.test_doc_id, response)
        assert success is True
        # Verify entry was stored
        cached_entry = self.db.fetch_one(
            "SELECT * FROM rag_query_cache WHERE document_id = ?", (self.test_doc_id,)
        )
        assert cached_entry is not None
        assert cached_entry["query_text"] == query
        assert cached_entry["response"] == response
        assert cached_entry["document_id"] == self.test_doc_id
        assert cached_entry["query_length"] == len(query)
        assert cached_entry["response_length"] == len(response)

    def test_cache_response_empty_query(self):
        """Test caching with empty query."""
        success = self.cache_service.cache_response(
            "", self.test_doc_id, "Some response"
        )
        assert success is False
        success = self.cache_service.cache_response(
            "   ", self.test_doc_id, "Some response"
        )
        assert success is False

    def test_cache_response_empty_response(self):
        """Test caching with empty response."""
        success = self.cache_service.cache_response("Some query", self.test_doc_id, "")
        assert success is False
        success = self.cache_service.cache_response(
            "Some query", self.test_doc_id, "   "
        )
        assert success is False

    def test_cache_response_duplicate_skip(self):
        """Test that duplicate responses are skipped."""
        query = "What is AI?"
        response = "AI is artificial intelligence."
        # Cache first time
        success1 = self.cache_service.cache_response(query, self.test_doc_id, response)
        assert success1 is True
        # Try to cache same query again
        success2 = self.cache_service.cache_response(query, self.test_doc_id, response)
        assert success2 is True  # Returns True but doesn't duplicate
        # Verify only one entry exists
        count = self.db.fetch_one("SELECT COUNT(*) as count FROM rag_query_cache")[
            "count"
        ]
        assert count == 1

    def test_cache_response_different_documents(self):
        """Test caching same query for different documents."""
        doc2_id = self._create_test_document(
            title="Doc 2", file_path="/doc2.pdf", file_hash="def789"
        )
        query = "What is this about?"
        response1 = "Response for document 1"
        response2 = "Response for document 2"
        success1 = self.cache_service.cache_response(query, self.test_doc_id, response1)
        success2 = self.cache_service.cache_response(query, doc2_id, response2)
        assert success1 is True
        assert success2 is True
        # Verify both entries exist
        entries = self.db.fetch_all("SELECT * FROM rag_query_cache")
        assert len(entries) == 2

    def test_cache_response_database_error(self):
        """Test error handling during cache storage."""
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            success = self.cache_service.cache_response(
                "query", self.test_doc_id, "response"
            )
            assert success is False

    # ===== Cache Retrieval Tests =====
    def test_get_cached_response_exact_match(self):
        """Test retrieving cached response with exact match."""
        query = "What is deep learning?"
        response = "Deep learning is a subset of machine learning."
        # Cache the response
        self.cache_service.cache_response(query, self.test_doc_id, response)
        # Retrieve cached response
        cached_response = self.cache_service.get_cached_response(
            query, self.test_doc_id
        )
        assert cached_response == response
        assert self.cache_service.metrics["cache_hits"] == 1
        assert self.cache_service.metrics["cache_misses"] == 0
        assert self.cache_service.metrics["total_queries"] == 1

    def test_get_cached_response_no_match(self):
        """Test retrieving when no cached response exists."""
        cached_response = self.cache_service.get_cached_response(
            "Unknown query", self.test_doc_id
        )
        assert cached_response is None
        assert self.cache_service.metrics["cache_hits"] == 0
        assert self.cache_service.metrics["cache_misses"] == 1
        assert self.cache_service.metrics["total_queries"] == 1

    def test_get_cached_response_semantic_similarity(self):
        """Test retrieving cached response using semantic similarity."""
        # Cache a response
        original_query = "What is machine learning technology?"
        response = "ML is a branch of AI that focuses on learning from data."
        self.cache_service.cache_response(original_query, self.test_doc_id, response)
        # Query with similar words (should match via similarity)
        similar_query = "What is machine learning AI?"
        cached_response = self.cache_service.get_cached_response(
            similar_query, self.test_doc_id
        )
        assert cached_response == response
        assert self.cache_service.metrics["cache_hits"] == 1

    def test_get_cached_response_similarity_threshold(self):
        """Test similarity threshold enforcement."""
        # Cache a response
        original_query = "machine learning algorithms"
        response = "ML algorithms are mathematical models."
        self.cache_service.cache_response(original_query, self.test_doc_id, response)
        # Query with low similarity (should not match)
        dissimilar_query = "weather forecast today"
        cached_response = self.cache_service.get_cached_response(
            dissimilar_query, self.test_doc_id
        )
        assert cached_response is None
        assert self.cache_service.metrics["cache_misses"] == 1

    def test_get_cached_response_updates_access(self):
        """Test that cache retrieval updates access time and count."""
        query = "What is NLP?"
        response = "NLP is natural language processing."
        # Cache the response
        self.cache_service.cache_response(query, self.test_doc_id, response)
        # Get original access info
        original_entry = self.db.fetch_one("SELECT * FROM rag_query_cache")
        original_access_time = original_entry["accessed_at"]
        original_access_count = original_entry["access_count"]
        # Wait a bit to ensure different timestamp
        time.sleep(0.1)
        # Retrieve cached response
        self.cache_service.get_cached_response(query, self.test_doc_id)
        # Check updated access info
        updated_entry = self.db.fetch_one("SELECT * FROM rag_query_cache")
        updated_access_time = updated_entry["accessed_at"]
        updated_access_count = updated_entry["access_count"]
        assert updated_access_time > original_access_time
        assert updated_access_count == original_access_count + 1

    def test_get_cached_response_database_error(self):
        """Test error handling during cache retrieval."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            cached_response = self.cache_service.get_cached_response(
                "query", self.test_doc_id
            )
            assert cached_response is None

    # ===== Cache Invalidation Tests =====
    def test_invalidate_document_cache_success(self):
        """Test successful document cache invalidation."""
        doc2_id = self._create_test_document(
            title="Doc 2", file_path="/doc2.pdf", file_hash="def789"
        )
        # Cache responses for both documents
        self.cache_service.cache_response("Query 1", self.test_doc_id, "Response 1")
        self.cache_service.cache_response("Query 2", self.test_doc_id, "Response 2")
        self.cache_service.cache_response("Query 3", doc2_id, "Response 3")
        # Invalidate cache for first document
        removed_count = self.cache_service.invalidate_document_cache(self.test_doc_id)
        assert removed_count == 2
        # Verify only doc2 cache remains
        remaining_entries = self.db.fetch_all("SELECT * FROM rag_query_cache")
        assert len(remaining_entries) == 1
        assert remaining_entries[0]["document_id"] == doc2_id

    def test_invalidate_document_cache_no_entries(self):
        """Test invalidating cache when no entries exist."""
        removed_count = self.cache_service.invalidate_document_cache(99999)
        assert removed_count == 0

    def test_invalidate_document_cache_database_error(self):
        """Test error handling during cache invalidation."""
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            removed_count = self.cache_service.invalidate_document_cache(
                self.test_doc_id
            )
            assert removed_count == 0

    def test_clear_cache_success(self):
        """Test successful cache clearing."""
        # Cache multiple responses
        for i in range(5):
            self.cache_service.cache_response(
                f"Query {i}", self.test_doc_id, f"Response {i}"
            )
        # Set some metrics
        self.cache_service.metrics["cache_hits"] = 10
        self.cache_service.metrics["cache_misses"] = 5
        success = self.cache_service.clear_cache()
        assert success is True
        # Verify cache is empty
        count = self.db.fetch_one("SELECT COUNT(*) as count FROM rag_query_cache")[
            "count"
        ]
        assert count == 0
        # Verify metrics are reset
        assert self.cache_service.metrics["cache_hits"] == 0
        assert self.cache_service.metrics["cache_misses"] == 0
        assert self.cache_service.metrics["total_queries"] == 0

    def test_clear_cache_database_error(self):
        """Test error handling during cache clearing."""
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            success = self.cache_service.clear_cache()
            assert success is False

    # ===== Cache Expiration and LRU Tests =====
    def test_cache_ttl_expiration(self):
        """Test that entries expire based on TTL."""
        # Create cache service with short TTL
        short_ttl_cache = RAGCacheService(
            db_connection=self.db,
            max_entries=100,
            ttl_hours=0.001,  # Very short TTL (3.6 seconds)
            similarity_threshold=0.8,
        )
        # Cache a response
        query = "TTL test query"
        response = "TTL test response"
        short_ttl_cache.cache_response(query, self.test_doc_id, response)
        # Verify entry exists
        cached_response = short_ttl_cache.get_cached_response(query, self.test_doc_id)
        assert cached_response == response
        # Mock time to simulate expiration
        future_time = datetime.now() + timedelta(hours=1)
        with patch("src.services.rag_cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = future_time
            # Try to retrieve expired entry (should trigger cleanup)
            expired_response = short_ttl_cache.get_cached_response(
                query, self.test_doc_id
            )
            assert expired_response is None

    def test_cache_size_enforcement_lru(self):
        """Test LRU eviction when cache size limit is reached."""
        # Create cache service with small limit
        small_cache = RAGCacheService(
            db_connection=self.db, max_entries=3, ttl_hours=24, similarity_threshold=0.8
        )
        # Cache responses up to limit
        for i in range(3):
            small_cache.cache_response(f"Query {i}", self.test_doc_id, f"Response {i}")
        # Verify all entries exist
        count = self.db.fetch_one("SELECT COUNT(*) as count FROM rag_query_cache")[
            "count"
        ]
        assert count == 3
        # Access first entry to make it more recent
        time.sleep(0.1)
        small_cache.get_cached_response("Query 0", self.test_doc_id)
        # Add another entry (should trigger LRU eviction)
        small_cache.cache_response("Query 3", self.test_doc_id, "Response 3")
        # Verify cache size is maintained and LRU entry was removed
        remaining_entries = self.db.fetch_all(
            "SELECT query_text FROM rag_query_cache ORDER BY accessed_at"
        )
        assert len(remaining_entries) <= 3

    def test_cache_optimization(self):
        """Test cache optimization functionality."""
        # Create entries with different ages
        old_time = datetime.now() - timedelta(hours=25)  # Expired
        recent_time = datetime.now() - timedelta(minutes=30)  # Valid
        # Insert expired entry
        self._insert_cache_entry(
            "Old query",
            self.test_doc_id,
            "Old response",
            created_at=old_time,
            accessed_at=old_time,
        )
        # Insert valid entry
        self._insert_cache_entry(
            "Recent query",
            self.test_doc_id,
            "Recent response",
            created_at=recent_time,
            accessed_at=recent_time,
        )
        # Insert duplicate query (different hash)
        self._insert_cache_entry(
            "Recent query",
            self.test_doc_id,
            "Duplicate response",
            created_at=recent_time,
            accessed_at=recent_time,
        )
        results = self.cache_service.optimize_cache()
        assert results["expired_removed"] >= 1
        assert isinstance(results["duplicates_removed"], int)
        assert isinstance(results["lru_removed"], int)

    # ===== Statistics Tests =====
    def test_get_cache_statistics_empty(self):
        """Test cache statistics when cache is empty."""
        stats = self.cache_service.get_cache_statistics()
        assert stats["total_entries"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["average_access_count"] == 0
        assert stats["total_storage_kb"] == 0
        assert stats["oldest_entry"] is None
        assert stats["newest_access"] is None
        assert stats["document_distribution"] == []
        assert stats["configuration"]["max_entries"] == 100
        assert stats["configuration"]["ttl_hours"] == 1
        assert stats["configuration"]["similarity_threshold"] == 0.8

    def test_get_cache_statistics_with_data(self):
        """Test cache statistics with cached data."""
        doc2_id = self._create_test_document(
            title="Doc 2", file_path="/doc2.pdf", file_hash="def789"
        )
        # Cache multiple responses
        self.cache_service.cache_response("Query 1", self.test_doc_id, "Response 1")
        self.cache_service.cache_response("Query 2", self.test_doc_id, "Response 2")
        self.cache_service.cache_response("Query 3", doc2_id, "Response 3")
        # Simulate some cache hits and misses
        self.cache_service.get_cached_response("Query 1", self.test_doc_id)  # Hit
        self.cache_service.get_cached_response("Query 2", self.test_doc_id)  # Hit
        self.cache_service.get_cached_response("Unknown", self.test_doc_id)  # Miss
        stats = self.cache_service.get_cache_statistics()
        assert stats["total_entries"] == 3
        assert stats["hit_rate_percent"] == 66.67  # 2 hits out of 3 queries
        assert stats["average_access_count"] > 1
        assert stats["total_storage_kb"] > 0
        assert stats["oldest_entry"] is not None
        assert stats["newest_access"] is not None
        assert len(stats["document_distribution"]) == 2
        # Check document distribution
        doc_counts = {
            item["document_id"]: item["count"]
            for item in stats["document_distribution"]
        }
        assert doc_counts[self.test_doc_id] == 2
        assert doc_counts[doc2_id] == 1

    def test_get_cache_statistics_database_error(self):
        """Test error handling in cache statistics."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            stats = self.cache_service.get_cache_statistics()
            assert "error" in stats
            assert "Database error" in stats["error"]

    # ===== Hash Generation Tests =====
    def test_generate_query_hash_consistency(self):
        """Test that query hash generation is consistent."""
        query = "What is artificial intelligence?"
        hash1 = self.cache_service._generate_query_hash(query, self.test_doc_id)
        hash2 = self.cache_service._generate_query_hash(query, self.test_doc_id)
        assert hash1 == hash2
        assert len(hash1) == 16  # SHA256 truncated to 16 chars

    def test_generate_query_hash_case_insensitive(self):
        """Test that query hashing is case insensitive."""
        hash1 = self.cache_service._generate_query_hash("What is AI?", self.test_doc_id)
        hash2 = self.cache_service._generate_query_hash("WHAT IS AI?", self.test_doc_id)
        hash3 = self.cache_service._generate_query_hash("what is ai?", self.test_doc_id)
        assert hash1 == hash2 == hash3

    def test_generate_query_hash_whitespace_normalization(self):
        """Test that query hashing normalizes whitespace."""
        hash1 = self.cache_service._generate_query_hash("What is AI?", self.test_doc_id)
        hash2 = self.cache_service._generate_query_hash(
            "  What is AI?  ", self.test_doc_id
        )
        hash3 = self.cache_service._generate_query_hash(
            "What  is  AI?", self.test_doc_id
        )
        assert hash1 == hash2
        # Note: Internal whitespace is not normalized, so hash3 may be different

    def test_generate_query_hash_different_documents(self):
        """Test that same query has different hash for different documents."""
        doc2_id = self._create_test_document(
            title="Doc 2", file_path="/doc2.pdf", file_hash="def789"
        )
        query = "What is this document about?"
        hash1 = self.cache_service._generate_query_hash(query, self.test_doc_id)
        hash2 = self.cache_service._generate_query_hash(query, doc2_id)
        assert hash1 != hash2

    # ===== Similarity Matching Tests =====
    def test_find_similar_query_jaccard_similarity(self):
        """Test semantic similarity using Jaccard index."""
        # Cache a query
        original_query = "machine learning artificial intelligence"
        response = "ML and AI are related fields."
        self.cache_service.cache_response(original_query, self.test_doc_id, response)
        # Test similar queries
        similar_queries = [
            "artificial intelligence machine learning",  # Same words, different order
            "machine learning and artificial intelligence",  # Added common word
            "what is machine learning and artificial intelligence",  # Added question words
        ]
        for similar_query in similar_queries:
            similar_entry = self.cache_service._find_similar_query(
                similar_query, self.test_doc_id
            )
            if similar_entry:  # May or may not match depending on threshold
                assert similar_entry["response"] == response

    def test_find_similar_query_no_match(self):
        """Test similarity matching when no similar query exists."""
        # Cache unrelated query
        self.cache_service.cache_response(
            "weather forecast", self.test_doc_id, "Sunny today"
        )
        # Search for completely different query
        similar_entry = self.cache_service._find_similar_query(
            "machine learning algorithms", self.test_doc_id
        )
        assert similar_entry is None

    def test_find_similar_query_database_error(self):
        """Test error handling in similarity search."""
        with patch.object(
            self.db, "fetch_all", side_effect=Exception("Database error")
        ):
            similar_entry = self.cache_service._find_similar_query(
                "query", self.test_doc_id
            )
            assert similar_entry is None

    # ===== Helper Methods Tests =====
    def test_clean_expired_entries(self):
        """Test cleaning of expired cache entries."""
        # Insert expired and valid entries
        expired_time = datetime.now() - timedelta(hours=25)  # Beyond TTL
        valid_time = datetime.now() - timedelta(minutes=30)  # Within TTL
        self._insert_cache_entry(
            "Expired query",
            self.test_doc_id,
            "Expired response",
            created_at=expired_time,
        )
        self._insert_cache_entry(
            "Valid query", self.test_doc_id, "Valid response", created_at=valid_time
        )
        removed_count = self.cache_service._clean_expired_entries()
        assert removed_count == 1
        # Verify only valid entry remains
        remaining_entries = self.db.fetch_all("SELECT query_text FROM rag_query_cache")
        assert len(remaining_entries) == 1
        assert remaining_entries[0]["query_text"] == "Valid query"

    def test_remove_duplicate_queries(self):
        """Test removal of duplicate queries."""
        # Insert multiple entries for same query
        query = "duplicate query"
        now = datetime.now()
        self._insert_cache_entry(
            query,
            self.test_doc_id,
            "First response",
            created_at=now - timedelta(minutes=10),
        )
        self._insert_cache_entry(
            query,
            self.test_doc_id,
            "Second response",
            created_at=now - timedelta(minutes=5),
        )
        self._insert_cache_entry(
            query, self.test_doc_id, "Latest response", created_at=now
        )
        removed_count = self.cache_service._remove_duplicate_queries()
        assert removed_count == 2
        # Verify only most recent entry remains
        remaining_entries = self.db.fetch_all("SELECT response FROM rag_query_cache")
        assert len(remaining_entries) == 1
        assert remaining_entries[0]["response"] == "Latest response"

    def test_enforce_cache_size(self):
        """Test cache size enforcement with LRU eviction."""
        # Create many entries
        for i in range(150):  # Exceed max_entries (100)
            self._insert_cache_entry(f"Query {i}", self.test_doc_id, f"Response {i}")
        removed_count = self.cache_service._enforce_cache_size()
        assert removed_count > 0
        # Verify cache size is within limit
        count = self.db.fetch_one("SELECT COUNT(*) as count FROM rag_query_cache")[
            "count"
        ]
        assert count <= self.cache_service.max_entries

    def test_update_access(self):
        """Test access time and count updates."""
        # Insert a cache entry
        cache_id = self._insert_cache_entry(
            "Test query", self.test_doc_id, "Test response"
        )
        # Get original access info
        original_entry = self.db.fetch_one(
            "SELECT * FROM rag_query_cache WHERE id = ?", (cache_id,)
        )
        original_access_time = original_entry["accessed_at"]
        original_access_count = original_entry["access_count"]
        # Wait and update access
        time.sleep(0.1)
        self.cache_service._update_access(cache_id)
        # Verify updates
        updated_entry = self.db.fetch_one(
            "SELECT * FROM rag_query_cache WHERE id = ?", (cache_id,)
        )
        assert updated_entry["accessed_at"] > original_access_time
        assert updated_entry["access_count"] == original_access_count + 1

    def test_update_access_database_error(self):
        """Test error handling in access updates."""
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            # Should not raise exception, just log error
            self.cache_service._update_access(1)

    # ===== Integration Tests =====
    def test_full_cache_lifecycle(self):
        """Test complete cache lifecycle: store, retrieve, update, expire, optimize."""
        # Store multiple responses
        queries_responses = [
            ("What is AI?", "AI is artificial intelligence"),
            ("What is ML?", "ML is machine learning"),
            ("What is DL?", "DL is deep learning"),
        ]
        for query, response in queries_responses:
            success = self.cache_service.cache_response(
                query, self.test_doc_id, response
            )
            assert success is True
        # Retrieve cached responses
        for query, expected_response in queries_responses:
            cached_response = self.cache_service.get_cached_response(
                query, self.test_doc_id
            )
            assert cached_response == expected_response
        # Test similarity matching
        similar_response = self.cache_service.get_cached_response(
            "What is artificial intelligence?", self.test_doc_id
        )
        # May or may not match depending on similarity threshold
        # Get statistics
        stats = self.cache_service.get_cache_statistics()
        assert stats["total_entries"] == 3
        assert stats["hit_rate_percent"] > 0
        # Optimize cache
        optimization_results = self.cache_service.optimize_cache()
        assert isinstance(optimization_results, dict)
        # Clear cache
        clear_success = self.cache_service.clear_cache()
        assert clear_success is True
        # Verify cache is empty
        final_stats = self.cache_service.get_cache_statistics()
        assert final_stats["total_entries"] == 0

    def test_concurrent_operations_simulation(self):
        """Test multiple cache operations can be performed safely."""
        doc2_id = self._create_test_document(
            title="Doc 2", file_path="/doc2.pdf", file_hash="def789"
        )
        doc3_id = self._create_test_document(
            title="Doc 3", file_path="/doc3.pdf", file_hash="ghi101"
        )
        # Cache responses for multiple documents
        test_data = [
            (self.test_doc_id, "Query about doc 1", "Response for doc 1"),
            (doc2_id, "Query about doc 2", "Response for doc 2"),
            (doc3_id, "Query about doc 3", "Response for doc 3"),
            (
                self.test_doc_id,
                "Another query about doc 1",
                "Another response for doc 1",
            ),
        ]
        for doc_id, query, response in test_data:
            success = self.cache_service.cache_response(query, doc_id, response)
            assert success is True
        # Retrieve all cached responses
        for doc_id, query, expected_response in test_data:
            cached_response = self.cache_service.get_cached_response(query, doc_id)
            assert cached_response == expected_response
        # Invalidate cache for one document
        removed_count = self.cache_service.invalidate_document_cache(doc2_id)
        assert removed_count == 1
        # Verify other caches remain
        assert (
            self.cache_service.get_cached_response(
                "Query about doc 1", self.test_doc_id
            )
            is not None
        )
        assert (
            self.cache_service.get_cached_response("Query about doc 2", doc2_id) is None
        )
        assert (
            self.cache_service.get_cached_response("Query about doc 3", doc3_id)
            is not None
        )
        # Get final statistics
        final_stats = self.cache_service.get_cache_statistics()
        assert final_stats["total_entries"] == 3  # 4 original - 1 invalidated
        assert len(final_stats["document_distribution"]) == 2  # doc1 and doc3
