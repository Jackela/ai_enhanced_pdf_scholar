"""
RAGQueryEngine Service Tests

Tests for the specialized service responsible for executing RAG queries,
including index loading, semantic search, and response generation.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.rag.exceptions import RAGIndexError, RAGQueryError
from src.services.rag.query_engine import RAGQueryEngine


class TestRAGQueryEngine:
    """Test suite for RAGQueryEngine query execution and response generation."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test indexes."""
        import shutil
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for query operations."""
        mock = Mock()
        mock.load_local = AsyncMock(return_value=True)
        mock.similarity_search = AsyncMock(return_value=[
            Mock(page_content="Sample content chunk 1", metadata={"page": 1, "chunk_id": "1"}),
            Mock(page_content="Sample content chunk 2", metadata={"page": 2, "chunk_id": "2"}),
            Mock(page_content="Sample content chunk 3", metadata={"page": 1, "chunk_id": "3"})
        ])
        mock.similarity_search_with_score = AsyncMock(return_value=[
            (Mock(page_content="High relevance chunk", metadata={"page": 1}), 0.95),
            (Mock(page_content="Medium relevance chunk", metadata={"page": 2}), 0.75),
            (Mock(page_content="Low relevance chunk", metadata={"page": 3}), 0.55)
        ])
        return mock

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client for response generation."""
        mock = Mock()
        mock.generate_response = AsyncMock(return_value={
            "answer": "This is a sample AI-generated answer based on the provided context.",
            "confidence": 0.85,
            "reasoning": "Answer based on multiple relevant document chunks",
            "token_usage": {"input": 500, "output": 150}
        })
        return mock

    @pytest.fixture
    def mock_context_builder(self):
        """Mock context builder for prompt construction."""
        mock = Mock()
        mock.build_context.return_value = {
            "context": "Relevant context from document chunks...",
            "sources": [
                {"page": 1, "chunk_id": "1", "relevance": 0.95},
                {"page": 2, "chunk_id": "2", "relevance": 0.75}
            ],
            "context_length": 1500
        }
        return mock

    @pytest.fixture
    def query_engine(self, temp_directory, mock_vector_store,
                    mock_llm_client, mock_context_builder):
        """Create RAGQueryEngine with mocked dependencies."""
        return RAGQueryEngine(
            index_storage_path=temp_directory,
            vector_store=mock_vector_store,
            llm_client=mock_llm_client,
            context_builder=mock_context_builder
        )

    def test_query_engine_initialization(self, query_engine, temp_directory):
        """Test RAGQueryEngine initializes with correct configuration."""
        assert query_engine.index_storage_path == temp_directory
        assert query_engine.vector_store is not None
        assert query_engine.llm_client is not None
        assert query_engine.context_builder is not None
        assert query_engine._loaded_indexes == {}
        assert query_engine._query_cache == {}

    @pytest.mark.asyncio
    async def test_load_index_success(self, query_engine):
        """Test successful index loading."""
        # Given
        document_id = 1

        # When
        result = await query_engine.load_index(document_id)

        # Then
        assert result is True
        assert document_id in query_engine._loaded_indexes
        query_engine.vector_store.load_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_index_missing_files(self, query_engine):
        """Test index loading with missing index files."""
        # Given
        query_engine.vector_store.load_local.side_effect = FileNotFoundError("Index not found")

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await query_engine.load_index(document_id=999)

        assert "Index not found for document 999" in str(exc_info.value)

    def test_is_ready_with_loaded_index(self, query_engine):
        """Test readiness check with loaded index."""
        # Given
        query_engine._loaded_indexes[1] = {"loaded_at": time.time()}

        # When
        result = query_engine.is_ready(document_id=1)

        # Then
        assert result is True

    def test_is_ready_without_loaded_index(self, query_engine):
        """Test readiness check without loaded index."""
        # When
        result = query_engine.is_ready(document_id=999)

        # Then
        assert result is False

    @pytest.mark.asyncio
    async def test_query_with_loaded_index(self, query_engine):
        """Test query execution with pre-loaded index."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query)

        # Then
        assert result["answer"] == "This is a sample AI-generated answer based on the provided context."
        assert result["confidence"] == 0.85
        assert "sources" in result
        assert "processing_time" in result
        assert len(result["sources"]) == 2

        # Verify query flow
        query_engine.vector_store.similarity_search_with_score.assert_called_once()
        query_engine.context_builder.build_context.assert_called_once()
        query_engine.llm_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_auto_index_loading(self, query_engine):
        """Test query execution with automatic index loading."""
        # Given
        document_id = 1
        query = "What are the main findings?"

        # When
        result = await query_engine.query(document_id, query)

        # Then
        assert result["answer"] is not None
        assert document_id in query_engine._loaded_indexes

        # Verify index was auto-loaded
        query_engine.vector_store.load_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_custom_context_window(self, query_engine):
        """Test query with custom context window size."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        context_window = 8000
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query,
                                        context_window=context_window)

        # Then
        assert result["answer"] is not None

        # Verify context window was passed through
        call_args = query_engine.context_builder.build_context.call_args
        assert call_args[1]["max_length"] == context_window

    @pytest.mark.asyncio
    async def test_query_with_relevance_threshold(self, query_engine):
        """Test query with relevance score filtering."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        relevance_threshold = 0.8
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query,
                                        relevance_threshold=relevance_threshold)

        # Then
        assert result["answer"] is not None

        # Verify only high-relevance sources included
        high_relevance_sources = [s for s in result["sources"] if s["relevance"] >= 0.8]
        assert len(high_relevance_sources) >= 1

    @pytest.mark.asyncio
    async def test_query_caching_mechanism(self, query_engine):
        """Test query result caching for performance."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # When - first query
        result1 = await query_engine.query(document_id, query, enable_cache=True)

        # When - second identical query
        result2 = await query_engine.query(document_id, query, enable_cache=True)

        # Then
        assert result1["answer"] == result2["answer"]
        assert result2.get("from_cache") is True

        # Verify LLM was only called once (cached second time)
        query_engine.llm_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_document_query(self, query_engine):
        """Test querying across multiple documents."""
        # Given
        document_ids = [1, 2, 3]
        query = "What are the common themes?"

        # Load indexes for all documents
        for doc_id in document_ids:
            await query_engine.load_index(doc_id)

        # When
        result = await query_engine.query_multiple(document_ids, query)

        # Then
        assert result["answer"] is not None
        assert result["document_count"] == 3
        assert len(result["sources"]) > 0

        # Verify all document indexes were searched
        assert query_engine.vector_store.similarity_search_with_score.call_count == 3

    @pytest.mark.asyncio
    async def test_query_with_source_citation_tracking(self, query_engine):
        """Test query with detailed source citation tracking."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query,
                                        include_citations=True)

        # Then
        assert result["answer"] is not None
        assert "citations" in result

        for citation in result["citations"]:
            assert "page" in citation
            assert "chunk_id" in citation
            assert "relevance" in citation
            assert "text_excerpt" in citation

    @pytest.mark.asyncio
    async def test_query_performance_tracking(self, query_engine):
        """Test query performance metrics collection."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query)

        # Then
        assert "performance_metrics" in result
        metrics = result["performance_metrics"]
        assert "total_time" in metrics
        assert "search_time" in metrics
        assert "generation_time" in metrics
        assert "context_building_time" in metrics
        assert metrics["total_time"] > 0

    @pytest.mark.asyncio
    async def test_query_with_temperature_control(self, query_engine):
        """Test query with different temperature settings for creativity."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # Test different temperature values
        temperatures = [0.1, 0.5, 0.9]

        for temperature in temperatures:
            # When
            result = await query_engine.query(document_id, query,
                                            temperature=temperature)

            # Then
            assert result["answer"] is not None

            # Verify temperature was passed to LLM
            call_args = query_engine.llm_client.generate_response.call_args
            assert call_args[1]["temperature"] == temperature

    @pytest.mark.asyncio
    async def test_query_with_max_tokens_limit(self, query_engine):
        """Test query with response length limits."""
        # Given
        document_id = 1
        query = "Provide a detailed explanation?"
        max_tokens = 500
        await query_engine.load_index(document_id)

        # When
        result = await query_engine.query(document_id, query,
                                        max_tokens=max_tokens)

        # Then
        assert result["answer"] is not None
        assert result["token_usage"]["output"] <= max_tokens

        # Verify token limit was enforced
        call_args = query_engine.llm_client.generate_response.call_args
        assert call_args[1]["max_tokens"] == max_tokens

    @pytest.mark.asyncio
    async def test_streaming_query_response(self, query_engine):
        """Test streaming query responses for real-time updates."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # Mock streaming response
        async def mock_stream():
            yield {"partial_answer": "This is", "complete": False}
            yield {"partial_answer": "This is a sample", "complete": False}
            yield {"partial_answer": "This is a sample answer", "complete": True}

        query_engine.llm_client.stream_response = AsyncMock(return_value=mock_stream())

        # When
        stream = query_engine.stream_query(document_id, query)
        responses = []
        async for response in stream:
            responses.append(response)

        # Then
        assert len(responses) == 3
        assert responses[-1]["complete"] is True

    def test_query_result_validation(self, query_engine):
        """Test validation of query results before returning."""
        # Given
        raw_result = {
            "answer": "Test answer",
            "confidence": 0.85,
            "sources": [{"page": 1, "relevance": 0.9}],
            "processing_time": 1.5
        }

        # When
        validated = query_engine._validate_query_result(raw_result)

        # Then
        assert validated["answer"] == "Test answer"
        assert 0 <= validated["confidence"] <= 1
        assert len(validated["sources"]) > 0
        assert validated["processing_time"] > 0
        assert "validated_at" in validated

    @pytest.mark.asyncio
    async def test_concurrent_queries_handling(self, query_engine):
        """Test handling of concurrent queries to the same document."""
        import asyncio

        # Given
        document_id = 1
        queries = [
            "What are the main findings?",
            "What is the methodology?",
            "What are the conclusions?",
            "Who are the authors?",
            "What is the significance?"
        ]
        await query_engine.load_index(document_id)

        # When
        tasks = [query_engine.query(document_id, q) for q in queries]
        results = await asyncio.gather(*tasks)

        # Then
        assert len(results) == 5
        assert all("answer" in result for result in results)

        # Verify concurrent handling
        assert query_engine.llm_client.generate_response.call_count == 5

    @pytest.mark.asyncio
    async def test_query_error_recovery_mechanisms(self, query_engine):
        """Test error recovery during query execution."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # Mock temporary LLM failure followed by success
        query_engine.llm_client.generate_response.side_effect = [
            Exception("Temporary service unavailable"),
            {
                "answer": "Recovered response",
                "confidence": 0.8,
                "reasoning": "Answer after retry"
            }
        ]

        # When
        result = await query_engine.query_with_retry(document_id, query,
                                                    max_retries=2)

        # Then
        assert result["answer"] == "Recovered response"
        assert query_engine.llm_client.generate_response.call_count == 2

    def test_index_memory_management(self, query_engine):
        """Test memory management for loaded indexes."""
        # Given - load multiple indexes
        document_ids = list(range(1, 11))  # 10 documents
        for doc_id in document_ids:
            query_engine._loaded_indexes[doc_id] = {
                "loaded_at": time.time(),
                "memory_usage": 50 * 1024 * 1024  # 50MB each
            }

        # When - trigger memory management
        query_engine._manage_index_memory(max_memory=400 * 1024 * 1024)  # 400MB limit

        # Then - should keep only most recent indexes
        assert len(query_engine._loaded_indexes) <= 8  # Should unload oldest

    @pytest.mark.asyncio
    async def test_query_result_post_processing(self, query_engine):
        """Test post-processing of query results for quality enhancement."""
        # Given
        document_id = 1
        query = "What are the main findings?"
        await query_engine.load_index(document_id)

        # Mock raw LLM response needing post-processing
        query_engine.llm_client.generate_response.return_value = {
            "answer": "Raw answer with potential issues...",
            "confidence": 0.75,
            "reasoning": "Basic reasoning"
        }

        # When
        result = await query_engine.query(document_id, query,
                                        enable_post_processing=True)

        # Then
        assert result["answer"] is not None
        assert "quality_score" in result
        assert "post_processed" in result
        assert result["post_processed"] is True


class TestRAGQueryEngineErrorHandling:
    """Test error handling and edge cases for RAGQueryEngine."""

    @pytest.fixture
    def error_prone_engine(self, temp_directory):
        """Create query engine with error-prone dependencies."""
        mock_vector_store = Mock()
        mock_llm_client = Mock()
        mock_context_builder = Mock()

        return RAGQueryEngine(
            index_storage_path=temp_directory,
            vector_store=mock_vector_store,
            llm_client=mock_llm_client,
            context_builder=mock_context_builder
        )

    @pytest.mark.asyncio
    async def test_llm_service_unavailable_handling(self, error_prone_engine):
        """Test handling of LLM service unavailability."""
        # Given
        document_id = 1
        query = "Test query"

        # Mock LLM service failure
        error_prone_engine.vector_store.load_local = AsyncMock(return_value=True)
        error_prone_engine.vector_store.similarity_search_with_score = AsyncMock(return_value=[])
        error_prone_engine.context_builder.build_context.return_value = {"context": "test"}
        error_prone_engine.llm_client.generate_response = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        # When/Then
        with pytest.raises(RAGQueryError) as exc_info:
            await error_prone_engine.query(document_id, query)

        assert "LLM service unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_search_results_handling(self, error_prone_engine):
        """Test handling of queries with no relevant search results."""
        # Given
        document_id = 1
        query = "Completely unrelated query"

        # Mock empty search results
        error_prone_engine.vector_store.load_local = AsyncMock(return_value=True)
        error_prone_engine.vector_store.similarity_search_with_score = AsyncMock(return_value=[])

        # When
        result = await error_prone_engine.query(document_id, query)

        # Then
        assert result["answer"] is not None
        assert result["confidence"] == 0.0
        assert result["sources"] == []
        assert "no_relevant_content" in result

    @pytest.mark.asyncio
    async def test_context_window_overflow_handling(self, error_prone_engine):
        """Test handling of context that exceeds window limits."""
        # Given
        document_id = 1
        query = "Complex query"

        # Mock context that exceeds limits
        large_context = "A" * 20000  # Very large context
        error_prone_engine.vector_store.load_local = AsyncMock(return_value=True)
        error_prone_engine.vector_store.similarity_search_with_score = AsyncMock(return_value=[
            (Mock(page_content=large_context, metadata={"page": 1}), 0.9)
        ])
        error_prone_engine.context_builder.build_context.return_value = {
            "context": large_context,
            "sources": [{"page": 1}],
            "context_length": len(large_context),
            "truncated": True
        }

        # When
        result = await error_prone_engine.query(document_id, query,
                                              context_window=4000)

        # Then
        assert result is not None
        assert result.get("context_truncated") is True

    @pytest.mark.asyncio
    async def test_malformed_query_handling(self, error_prone_engine):
        """Test handling of malformed or problematic queries."""
        # Given
        document_id = 1
        malformed_queries = [
            "",  # Empty query
            "   ",  # Whitespace only
            "A" * 10000,  # Extremely long query
            "<script>alert('xss')</script>",  # Potentially malicious
            None  # None value
        ]

        error_prone_engine.vector_store.load_local = AsyncMock(return_value=True)

        for bad_query in malformed_queries:
            # When/Then
            with pytest.raises(RAGQueryError):
                await error_prone_engine.query(document_id, bad_query)

    @pytest.mark.asyncio
    async def test_index_corruption_detection_and_handling(self, error_prone_engine):
        """Test detection and handling of corrupted vector indexes."""
        # Given
        document_id = 1
        query = "Test query"

        # Mock index corruption
        error_prone_engine.vector_store.load_local = AsyncMock(
            side_effect=Exception("Index file corrupted")
        )

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await error_prone_engine.query(document_id, query)

        assert "Index corruption detected" in str(exc_info.value)
