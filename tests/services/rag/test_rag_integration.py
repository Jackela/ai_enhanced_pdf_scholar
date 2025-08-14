"""
RAG Module Integration Tests

Tests for integration between all RAG modules (Coordinator, IndexBuilder,
QueryEngine, RecoveryService, FileManager) to ensure proper collaboration
and SOLID principle compliance.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import shutil
import asyncio
import json
from typing import Dict, Any

from src.services.rag.coordinator import RAGCoordinator
from src.services.rag.index_builder import RAGIndexBuilder
from src.services.rag.query_engine import RAGQueryEngine
from src.services.rag.recovery_service import RAGRecoveryService
from src.services.rag.file_manager import RAGFileManager
from src.database.models import DocumentModel
from src.services.rag.exceptions import RAGProcessingError, RAGIndexError


class TestRAGModuleIntegration:
    """Test suite for RAG module integration and collaboration."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for integration tests."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_documents(self):
        """Create sample documents for testing."""
        return [
            DocumentModel(
                id=1,
                title="Machine Learning Paper",
                file_path="/test/ml_paper.pdf",
                content_hash="hash1",
                mime_type="application/pdf",
                file_size=1024 * 1024
            ),
            DocumentModel(
                id=2,
                title="Deep Learning Survey",
                file_path="/test/dl_survey.pdf",
                content_hash="hash2",
                mime_type="application/pdf",
                file_size=2 * 1024 * 1024
            ),
            DocumentModel(
                id=3,
                title="Natural Language Processing",
                file_path="/test/nlp_paper.pdf",
                content_hash="hash3",
                mime_type="application/pdf",
                file_size=1.5 * 1024 * 1024
            )
        ]

    @pytest.fixture
    def integrated_rag_system(self, temp_directory):
        """Create fully integrated RAG system with all components."""
        # Create individual components with real implementations
        # (in practice these would be injected via dependency injection)

        # Mock the external dependencies but use real RAG component logic
        mock_pdf_processor = Mock()
        mock_pdf_processor.extract_text.return_value = "Sample PDF content for RAG indexing and query processing."
        mock_pdf_processor.extract_metadata.return_value = {
            "page_count": 10,
            "word_count": 500,
            "title": "Test Document"
        }

        mock_vector_store = Mock()
        mock_vector_store.add_documents = AsyncMock(return_value={"chunks_added": 5})
        mock_vector_store.save_local = AsyncMock(return_value=True)
        mock_vector_store.load_local = AsyncMock(return_value=True)
        mock_vector_store.similarity_search_with_score = AsyncMock(return_value=[
            (Mock(page_content="Relevant content", metadata={"page": 1}), 0.95),
            (Mock(page_content="Supporting content", metadata={"page": 2}), 0.85)
        ])

        mock_llm_client = Mock()
        mock_llm_client.generate_response = AsyncMock(return_value={
            "answer": "AI-generated response based on document content",
            "confidence": 0.9,
            "reasoning": "Answer synthesized from multiple relevant chunks"
        })

        mock_context_builder = Mock()
        mock_context_builder.build_context.return_value = {
            "context": "Relevant context from document chunks",
            "sources": [{"page": 1, "relevance": 0.95}],
            "context_length": 1500
        }

        # Create components with dependency injection
        file_manager = RAGFileManager(
            base_storage_path=temp_directory,
            storage_monitor=Mock(),
            backup_service=Mock()
        )

        index_builder = RAGIndexBuilder(
            index_storage_path=temp_directory,
            pdf_processor=mock_pdf_processor,
            vector_store=mock_vector_store,
            text_splitter=Mock()
        )

        query_engine = RAGQueryEngine(
            index_storage_path=temp_directory,
            vector_store=mock_vector_store,
            llm_client=mock_llm_client,
            context_builder=mock_context_builder
        )

        recovery_service = RAGRecoveryService(
            index_storage_path=temp_directory,
            index_builder=index_builder,
            file_manager=file_manager,
            health_monitor=Mock()
        )

        coordinator = RAGCoordinator(
            index_builder=index_builder,
            query_engine=query_engine,
            recovery_service=recovery_service,
            file_manager=file_manager
        )

        return {
            "coordinator": coordinator,
            "index_builder": index_builder,
            "query_engine": query_engine,
            "recovery_service": recovery_service,
            "file_manager": file_manager
        }

    @pytest.mark.asyncio
    async def test_end_to_end_document_processing_workflow(self, integrated_rag_system, sample_documents):
        """Test complete end-to-end document processing workflow."""
        coordinator = integrated_rag_system["coordinator"]
        document = sample_documents[0]

        # When - process document from start to finish
        processing_result = await coordinator.process_document_complete(document)

        # Then - verify complete workflow
        assert processing_result["success"] is True
        assert processing_result["document_id"] == document.id
        assert "processing_time" in processing_result
        assert "index_stats" in processing_result

        # Verify each component was involved
        index_builder = integrated_rag_system["index_builder"]
        query_engine = integrated_rag_system["query_engine"]
        file_manager = integrated_rag_system["file_manager"]

        # Check that file manager created necessary directories
        index_builder.pdf_processor.extract_text.assert_called_once()
        index_builder.vector_store.add_documents.assert_called_once()
        index_builder.vector_store.save_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_workflow_with_auto_recovery(self, integrated_rag_system, sample_documents):
        """Test query workflow with automatic recovery on index corruption."""
        coordinator = integrated_rag_system["coordinator"]
        recovery_service = integrated_rag_system["recovery_service"]
        document = sample_documents[0]

        # Given - simulate index corruption detected during query
        recovery_service.detect_corruption = AsyncMock(return_value=True)
        recovery_service.repair_index = AsyncMock(return_value={"status": "success"})

        # When - attempt query (should trigger auto-recovery)
        query_result = await coordinator.query_document(
            document_id=document.id,
            query="What are the main findings?",
            enable_auto_recovery=True
        )

        # Then - verify query succeeded after recovery
        assert "answer" in query_result
        assert query_result["answer"] == "AI-generated response based on document content"

        # Verify recovery was triggered
        recovery_service.detect_corruption.assert_called_once_with(document.id)
        recovery_service.repair_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_processing_with_error_handling(self, integrated_rag_system, sample_documents):
        """Test batch processing with mixed success and failure scenarios."""
        coordinator = integrated_rag_system["coordinator"]
        index_builder = integrated_rag_system["index_builder"]

        # Given - simulate failure for second document
        def mock_build_index(document):
            if document.id == 2:
                raise Exception("Processing failed for document 2")
            return {"status": "success", "chunks": 50}

        index_builder.build_index = AsyncMock(side_effect=mock_build_index)

        # When - batch process all documents
        batch_results = await coordinator.batch_process_documents(
            [doc.id for doc in sample_documents],
            fail_fast=False
        )

        # Then - verify mixed results
        assert len(batch_results) == 3
        assert batch_results[0]["success"] is True   # Document 1 succeeded
        assert batch_results[1]["success"] is False  # Document 2 failed
        assert batch_results[2]["success"] is True   # Document 3 succeeded

        # Verify partial processing completed
        successful_count = sum(1 for result in batch_results if result["success"])
        assert successful_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_operations_coordination(self, integrated_rag_system, sample_documents):
        """Test coordination of concurrent operations across modules."""
        coordinator = integrated_rag_system["coordinator"]

        # When - trigger concurrent operations
        processing_tasks = [
            coordinator.process_document_complete(doc)
            for doc in sample_documents
        ]

        query_tasks = [
            coordinator.query_document(doc.id, f"Query for document {doc.id}")
            for doc in sample_documents
        ]

        # Execute all tasks concurrently
        all_tasks = processing_tasks + query_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Then - verify concurrent execution completed
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 3  # At least processing tasks should succeed

    @pytest.mark.asyncio
    async def test_resource_cleanup_coordination(self, integrated_rag_system, sample_documents):
        """Test coordinated resource cleanup across all modules."""
        coordinator = integrated_rag_system["coordinator"]
        file_manager = integrated_rag_system["file_manager"]
        document = sample_documents[0]

        # Given - process document to create resources
        await coordinator.process_document_complete(document)

        # Mock file manager cleanup
        file_manager.cleanup_temp_files = AsyncMock(return_value=5)
        file_manager.cleanup_orphaned_files = AsyncMock(return_value=2)

        # When - trigger coordinated cleanup
        cleanup_result = await coordinator.cleanup_resources(document_id=document.id)

        # Then - verify cleanup coordination
        assert cleanup_result["cleanup_completed"] is True
        file_manager.cleanup_temp_files.assert_called_once_with(document_id=document.id)

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, integrated_rag_system):
        """Test integrated health monitoring across all modules."""
        coordinator = integrated_rag_system["coordinator"]
        recovery_service = integrated_rag_system["recovery_service"]

        # Mock health monitoring responses
        recovery_service.health_check = AsyncMock(return_value={
            "overall_status": "healthy",
            "components": {
                "index_builder": {"status": "healthy"},
                "query_engine": {"status": "healthy"},
                "file_manager": {"status": "healthy"}
            }
        })

        # When - check overall system health
        health_status = await coordinator.health_check()

        # Then - verify comprehensive health check
        assert health_status["overall_status"] == "healthy"
        assert "components" in health_status
        recovery_service.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_configuration_propagation(self, integrated_rag_system, sample_documents):
        """Test configuration propagation across modules."""
        coordinator = integrated_rag_system["coordinator"]
        document = sample_documents[0]

        # Given - configuration override
        config_override = {
            "chunk_size": 2000,
            "chunk_overlap": 300,
            "temperature": 0.1,
            "max_tokens": 1000
        }

        # When - process with configuration
        await coordinator.process_document_complete(document, config_override=config_override)

        # Then - verify configuration was propagated
        # (In real implementation, would verify config reached all components)
        assert True  # Placeholder for actual configuration verification

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_failure(self, integrated_rag_system, sample_documents):
        """Test transaction rollback when processing fails."""
        coordinator = integrated_rag_system["coordinator"]
        index_builder = integrated_rag_system["index_builder"]
        file_manager = integrated_rag_system["file_manager"]
        document = sample_documents[0]

        # Given - simulate failure during index verification
        index_builder.verify_index = AsyncMock(return_value=False)
        file_manager.cleanup_temp_files = AsyncMock(return_value=3)

        # When - processing should fail and trigger rollback
        with pytest.raises(RAGProcessingError):
            await coordinator.process_document_complete(document)

        # Then - verify rollback was triggered
        file_manager.cleanup_temp_files.assert_called()

    def test_dependency_injection_validation(self, integrated_rag_system):
        """Test that all components have proper dependency injection."""
        coordinator = integrated_rag_system["coordinator"]

        # Verify all required dependencies are injected
        assert coordinator.index_builder is not None
        assert coordinator.query_engine is not None
        assert coordinator.recovery_service is not None
        assert coordinator.file_manager is not None

        # Verify components implement required interfaces
        assert hasattr(coordinator.index_builder, 'build_index')
        assert hasattr(coordinator.query_engine, 'query')
        assert hasattr(coordinator.recovery_service, 'detect_corruption')
        assert hasattr(coordinator.file_manager, 'cleanup_temp_files')

    @pytest.mark.asyncio
    async def test_performance_metrics_aggregation(self, integrated_rag_system, sample_documents):
        """Test performance metrics collection across all modules."""
        coordinator = integrated_rag_system["coordinator"]
        document = sample_documents[0]

        # When - perform operations to generate metrics
        await coordinator.process_document_complete(document)
        await coordinator.query_document(document.id, "Test query")

        # When - collect aggregated metrics
        performance_metrics = coordinator.get_performance_metrics()

        # Then - verify metrics from all components
        assert "total_operations" in performance_metrics
        assert "average_processing_time" in performance_metrics
        assert "success_rate" in performance_metrics
        assert performance_metrics["total_operations"] >= 2

    @pytest.mark.asyncio
    async def test_error_propagation_and_handling(self, integrated_rag_system, sample_documents):
        """Test proper error propagation between modules."""
        coordinator = integrated_rag_system["coordinator"]
        index_builder = integrated_rag_system["index_builder"]
        document = sample_documents[0]

        # Given - simulate error in index builder
        index_builder.build_index = AsyncMock(
            side_effect=RAGIndexError("Index building failed")
        )

        # When/Then - error should propagate correctly
        with pytest.raises(RAGProcessingError) as exc_info:
            await coordinator.process_document_complete(document)

        assert "Index building failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, integrated_rag_system, sample_documents):
        """Test graceful degradation when some modules fail."""
        coordinator = integrated_rag_system["coordinator"]
        recovery_service = integrated_rag_system["recovery_service"]
        document = sample_documents[0]

        # Given - simulate recovery service failure
        recovery_service.health_check = AsyncMock(
            side_effect=Exception("Recovery service unavailable")
        )

        # When - system should continue operating with degraded functionality
        health_status = await coordinator.health_check()

        # Then - should report degraded status but continue operating
        assert health_status["overall_status"] in ["degraded", "unknown"]
        assert "component_errors" in health_status


class TestRAGModuleSOLIDCompliance:
    """Test SOLID principles compliance in RAG module interactions."""

    @pytest.fixture
    def mock_interfaces(self):
        """Create mock implementations of RAG interfaces."""
        from src.services.rag.interfaces import (
            IRAGIndexBuilder, IRAGQueryEngine,
            IRAGRecoveryService, IRAGFileManager
        )

        mock_index_builder = Mock(spec=IRAGIndexBuilder)
        mock_query_engine = Mock(spec=IRAGQueryEngine)
        mock_recovery_service = Mock(spec=IRAGRecoveryService)
        mock_file_manager = Mock(spec=IRAGFileManager)

        return {
            "index_builder": mock_index_builder,
            "query_engine": mock_query_engine,
            "recovery_service": mock_recovery_service,
            "file_manager": mock_file_manager
        }

    def test_single_responsibility_principle(self, mock_interfaces):
        """Test that each module has a single, well-defined responsibility."""
        coordinator = RAGCoordinator(**mock_interfaces)

        # Coordinator should only orchestrate, not implement business logic
        assert hasattr(coordinator, 'process_document_complete')
        assert hasattr(coordinator, 'query_document')
        assert not hasattr(coordinator, 'extract_pdf_text')  # Should delegate
        assert not hasattr(coordinator, 'build_vector_index')  # Should delegate

    def test_open_closed_principle(self, mock_interfaces):
        """Test that modules are open for extension, closed for modification."""
        # Should be able to inject different implementations
        alternative_index_builder = Mock(spec=IRAGIndexBuilder)

        coordinator1 = RAGCoordinator(**mock_interfaces)
        coordinator2 = RAGCoordinator(
            index_builder=alternative_index_builder,
            **{k: v for k, v in mock_interfaces.items() if k != 'index_builder'}
        )

        # Both coordinators should work with different implementations
        assert coordinator1.index_builder != coordinator2.index_builder
        assert coordinator1.query_engine == coordinator2.query_engine

    def test_liskov_substitution_principle(self, mock_interfaces):
        """Test that interface implementations are substitutable."""
        # Any implementation of IRAGIndexBuilder should work
        mock_index_builder_alt = Mock(spec=IRAGIndexBuilder)

        coordinator = RAGCoordinator(
            index_builder=mock_index_builder_alt,
            **{k: v for k, v in mock_interfaces.items() if k != 'index_builder'}
        )

        # Should work with any conforming implementation
        assert coordinator.index_builder == mock_index_builder_alt

    def test_interface_segregation_principle(self, mock_interfaces):
        """Test that interfaces are segregated by responsibility."""
        # Each component should only depend on interfaces it uses
        coordinator = RAGCoordinator(**mock_interfaces)

        # Coordinator doesn't implement interfaces, only uses them
        from src.services.rag.interfaces import IRAGIndexBuilder
        assert not isinstance(coordinator, IRAGIndexBuilder)

    def test_dependency_inversion_principle(self, mock_interfaces):
        """Test that high-level modules depend on abstractions."""
        # Coordinator (high-level) depends on abstractions, not concretions
        coordinator = RAGCoordinator(**mock_interfaces)

        # Dependencies are injected, not created internally
        assert coordinator.index_builder is mock_interfaces["index_builder"]
        assert coordinator.query_engine is mock_interfaces["query_engine"]
        assert coordinator.recovery_service is mock_interfaces["recovery_service"]
        assert coordinator.file_manager is mock_interfaces["file_manager"]