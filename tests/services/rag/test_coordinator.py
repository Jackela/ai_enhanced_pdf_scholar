"""
RAGCoordinator Service Tests

Tests for the RAG service orchestrator that coordinates between all RAG modules
using dependency injection and SOLID principles.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, call
from pathlib import Path
import asyncio
from typing import Dict, Any

from src.services.rag.coordinator import RAGCoordinator
from src.services.rag.interfaces import (
    IRAGIndexBuilder,
    IRAGQueryEngine,
    IRAGRecoveryService,
    IRAGFileManager
)
from src.database.models import DocumentModel
from src.services.rag.exceptions import RAGProcessingError, RAGIndexError, RAGQueryError


class TestRAGCoordinator:
    """Test suite for RAGCoordinator service orchestration."""

    @pytest.fixture
    def mock_index_builder(self):
        """Mock RAG index builder."""
        mock = Mock(spec=IRAGIndexBuilder)
        mock.build_index = AsyncMock(return_value={"status": "success", "chunks": 50})
        mock.verify_index = AsyncMock(return_value=True)
        mock.get_index_stats = Mock(return_value={"size": 1024, "chunks": 50})
        return mock

    @pytest.fixture
    def mock_query_engine(self):
        """Mock RAG query engine."""
        mock = Mock(spec=IRAGQueryEngine)
        mock.load_index = AsyncMock(return_value=True)
        mock.query = AsyncMock(return_value={
            "answer": "Test response",
            "sources": [{"page": 1, "confidence": 0.9}],
            "processing_time": 0.5
        })
        mock.is_ready = Mock(return_value=True)
        return mock

    @pytest.fixture
    def mock_recovery_service(self):
        """Mock RAG recovery service."""
        mock = Mock(spec=IRAGRecoveryService)
        mock.detect_corruption = AsyncMock(return_value=False)
        mock.repair_index = AsyncMock(return_value={"status": "success"})
        mock.health_check = AsyncMock(return_value={"healthy": True})
        return mock

    @pytest.fixture
    def mock_file_manager(self):
        """Mock RAG file manager."""
        mock = Mock(spec=IRAGFileManager)
        mock.cleanup_temp_files = AsyncMock(return_value=5)
        mock.get_storage_stats = Mock(return_value={"total": 2048, "used": 1024})
        mock.ensure_directories = Mock(return_value=True)
        return mock

    @pytest.fixture
    def rag_coordinator(self, mock_index_builder, mock_query_engine,
                       mock_recovery_service, mock_file_manager):
        """Create RAGCoordinator with all mocked dependencies."""
        return RAGCoordinator(
            index_builder=mock_index_builder,
            query_engine=mock_query_engine,
            recovery_service=mock_recovery_service,
            file_manager=mock_file_manager
        )

    @pytest.fixture
    def sample_document(self):
        """Sample document for testing."""
        return DocumentModel(
            id=1,
            title="Test Document",
            file_path="/test/document.pdf",
            content_hash="abc123",
            mime_type="application/pdf"
        )

    def test_coordinator_initialization(self, rag_coordinator):
        """Test RAGCoordinator initializes with all dependencies."""
        assert rag_coordinator.index_builder is not None
        assert rag_coordinator.query_engine is not None
        assert rag_coordinator.recovery_service is not None
        assert rag_coordinator.file_manager is not None
        assert rag_coordinator._initialized is True

    @pytest.mark.asyncio
    async def test_process_document_complete_workflow(self, rag_coordinator,
                                                    sample_document):
        """Test complete document processing workflow coordination."""
        # When
        result = await rag_coordinator.process_document_complete(sample_document)

        # Then
        assert result["success"] is True
        assert result["document_id"] == 1
        assert "processing_time" in result
        assert "index_stats" in result

        # Verify orchestration sequence
        rag_coordinator.file_manager.ensure_directories.assert_called_once()
        rag_coordinator.index_builder.build_index.assert_called_once_with(sample_document)
        rag_coordinator.index_builder.verify_index.assert_called_once_with(sample_document.id)
        rag_coordinator.query_engine.load_index.assert_called_once_with(sample_document.id)

    @pytest.mark.asyncio
    async def test_process_document_with_index_failure(self, rag_coordinator,
                                                     sample_document):
        """Test document processing handles index building failure."""
        # Given
        rag_coordinator.index_builder.build_index.side_effect = RAGIndexError(
            "Index building failed"
        )

        # When/Then
        with pytest.raises(RAGProcessingError) as exc_info:
            await rag_coordinator.process_document_complete(sample_document)

        assert "Index building failed" in str(exc_info.value)

        # Verify cleanup was attempted
        rag_coordinator.file_manager.cleanup_temp_files.assert_called()

    @pytest.mark.asyncio
    async def test_query_document_with_coordination(self, rag_coordinator, sample_document):
        """Test document querying with service coordination."""
        # When
        result = await rag_coordinator.query_document(
            document_id=1,
            query="What is the main finding?",
            context_window=4000
        )

        # Then
        assert result["answer"] == "Test response"
        assert len(result["sources"]) > 0
        assert result["processing_time"] == 0.5

        # Verify coordination flow
        rag_coordinator.query_engine.is_ready.assert_called_once()
        rag_coordinator.query_engine.query.assert_called_once_with(
            document_id=1,
            query="What is the main finding?",
            context_window=4000
        )

    @pytest.mark.asyncio
    async def test_query_with_index_not_ready(self, rag_coordinator):
        """Test querying when index is not ready triggers loading."""
        # Given
        rag_coordinator.query_engine.is_ready.return_value = False

        # When
        await rag_coordinator.query_document(1, "test query")

        # Then
        rag_coordinator.query_engine.load_index.assert_called_with(1)
        rag_coordinator.query_engine.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_coordination(self, rag_coordinator):
        """Test health check coordinates across all services."""
        # When
        health = await rag_coordinator.health_check()

        # Then
        assert health["overall_status"] == "healthy"
        assert "recovery_service" in health["components"]
        assert "file_manager" in health["components"]

        # Verify all components checked
        rag_coordinator.recovery_service.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_recovery_workflow_coordination(self, rag_coordinator):
        """Test recovery workflow coordination."""
        # Given
        rag_coordinator.recovery_service.detect_corruption.return_value = True

        # When
        result = await rag_coordinator.recover_document_index(document_id=1)

        # Then
        assert result["recovery_performed"] is True

        # Verify recovery sequence
        rag_coordinator.recovery_service.detect_corruption.assert_called_with(1)
        rag_coordinator.recovery_service.repair_index.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_cleanup_coordination(self, rag_coordinator):
        """Test cleanup operations coordination."""
        # When
        result = await rag_coordinator.cleanup_resources(document_id=1)

        # Then
        assert result["cleanup_completed"] is True
        assert result["temp_files_removed"] == 5

        # Verify cleanup sequence
        rag_coordinator.file_manager.cleanup_temp_files.assert_called_with(
            document_id=1
        )

    @pytest.mark.asyncio
    async def test_batch_processing_coordination(self, rag_coordinator):
        """Test batch document processing coordination."""
        # Given
        document_ids = [1, 2, 3]

        # When
        results = await rag_coordinator.batch_process_documents(document_ids)

        # Then
        assert len(results) == 3
        assert all(r["success"] for r in results)

        # Verify batch coordination
        assert rag_coordinator.index_builder.build_index.call_count == 3

    def test_get_service_statistics(self, rag_coordinator):
        """Test service statistics aggregation."""
        # When
        stats = rag_coordinator.get_service_statistics()

        # Then
        assert "index_builder" in stats
        assert "query_engine" in stats
        assert "file_manager" in stats
        assert stats["file_manager"]["total"] == 2048
        assert stats["file_manager"]["used"] == 1024

    @pytest.mark.asyncio
    async def test_error_handling_and_rollback(self, rag_coordinator, sample_document):
        """Test error handling and transaction rollback coordination."""
        # Given - simulate failure at verification stage
        rag_coordinator.index_builder.verify_index.return_value = False

        # When/Then
        with pytest.raises(RAGProcessingError):
            await rag_coordinator.process_document_complete(sample_document)

        # Verify rollback coordination
        rag_coordinator.file_manager.cleanup_temp_files.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_operations_handling(self, rag_coordinator):
        """Test coordinator handles concurrent operations correctly."""
        # When - simulate concurrent queries
        tasks = [
            rag_coordinator.query_document(1, f"query {i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # Then
        assert len(results) == 5
        assert all("answer" in result for result in results)

        # Verify all queries were processed
        assert rag_coordinator.query_engine.query.call_count == 5

    @pytest.mark.asyncio
    async def test_service_dependency_validation(self, mock_index_builder):
        """Test coordinator validates service dependencies."""
        # When/Then - missing required dependencies
        with pytest.raises(ValueError) as exc_info:
            RAGCoordinator(
                index_builder=mock_index_builder,
                query_engine=None,  # Missing required dependency
                recovery_service=None,
                file_manager=None
            )

        assert "query_engine is required" in str(exc_info.value)

    def test_interface_compliance_validation(self, rag_coordinator):
        """Test coordinator validates interface compliance."""
        # Verify all injected services implement required interfaces
        assert hasattr(rag_coordinator.index_builder, 'build_index')
        assert hasattr(rag_coordinator.query_engine, 'query')
        assert hasattr(rag_coordinator.recovery_service, 'detect_corruption')
        assert hasattr(rag_coordinator.file_manager, 'cleanup_temp_files')

    @pytest.mark.asyncio
    async def test_configuration_override_handling(self, rag_coordinator):
        """Test coordinator handles configuration overrides properly."""
        # Given
        config_override = {
            "chunk_size": 2000,
            "chunk_overlap": 300,
            "temperature": 0.2
        }

        # When
        result = await rag_coordinator.query_document(
            document_id=1,
            query="test query",
            config_override=config_override
        )

        # Then
        assert "answer" in result

        # Verify configuration was passed through
        call_args = rag_coordinator.query_engine.query.call_args
        assert call_args.kwargs.get("config_override") == config_override

    @pytest.mark.asyncio
    async def test_monitoring_metrics_collection(self, rag_coordinator):
        """Test coordinator collects monitoring metrics."""
        # When
        await rag_coordinator.query_document(1, "test query")

        metrics = rag_coordinator.get_performance_metrics()

        # Then
        assert "total_queries" in metrics
        assert "average_response_time" in metrics
        assert "success_rate" in metrics
        assert metrics["total_queries"] == 1

    @pytest.mark.asyncio
    async def test_graceful_shutdown_coordination(self, rag_coordinator):
        """Test coordinator gracefully shuts down all services."""
        # When
        await rag_coordinator.shutdown()

        # Then
        assert rag_coordinator._initialized is False

        # Verify cleanup was coordinated
        rag_coordinator.file_manager.cleanup_temp_files.assert_called()


class TestRAGCoordinatorEdgeCases:
    """Test edge cases and error scenarios for RAGCoordinator."""

    @pytest.fixture
    def failing_coordinator(self):
        """Create coordinator with failing dependencies for testing."""
        mock_index_builder = Mock(spec=IRAGIndexBuilder)
        mock_index_builder.build_index = AsyncMock(side_effect=Exception("Service unavailable"))

        mock_query_engine = Mock(spec=IRAGQueryEngine)
        mock_recovery_service = Mock(spec=IRAGRecoveryService)
        mock_file_manager = Mock(spec=IRAGFileManager)

        return RAGCoordinator(
            index_builder=mock_index_builder,
            query_engine=mock_query_engine,
            recovery_service=mock_recovery_service,
            file_manager=mock_file_manager
        )

    @pytest.mark.asyncio
    async def test_cascade_failure_handling(self, failing_coordinator, sample_document):
        """Test coordinator handles cascading service failures."""
        # When/Then
        with pytest.raises(RAGProcessingError):
            await failing_coordinator.process_document_complete(sample_document)

    @pytest.mark.asyncio
    async def test_partial_service_failure_recovery(self, rag_coordinator):
        """Test coordinator recovers from partial service failures."""
        # Given
        rag_coordinator.query_engine.query.side_effect = [
            RAGQueryError("Temporary failure"),
            {"answer": "Success after retry", "sources": []}
        ]

        # When
        result = await rag_coordinator.query_document_with_retry(1, "test query")

        # Then
        assert result["answer"] == "Success after retry"
        assert rag_coordinator.query_engine.query.call_count == 2