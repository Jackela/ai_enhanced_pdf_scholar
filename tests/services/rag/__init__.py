"""
RAG Module Test Package

This package contains comprehensive tests for the new modular RAG architecture
including all specialized services and their integration.

Test Coverage:
- RAGCoordinator: Service orchestration and coordination
- RAGIndexBuilder: PDF processing and vector index building
- RAGQueryEngine: Query execution and response generation
- RAGRecoveryService: Corruption detection and recovery
- RAGFileManager: File operations and storage management
- Integration: Module interaction and SOLID principle compliance

Usage:
    pytest tests/services/rag/                    # Run all RAG tests
    pytest tests/services/rag/test_coordinator.py # Run specific module tests
    pytest tests/services/rag/test_rag_integration.py # Run integration tests
"""

# Import test classes for easier access
from .test_coordinator import TestRAGCoordinator, TestRAGCoordinatorEdgeCases
from .test_index_builder import TestRAGIndexBuilder, TestRAGIndexBuilderErrorHandling
from .test_query_engine import TestRAGQueryEngine, TestRAGQueryEngineErrorHandling
from .test_recovery_service import TestRAGRecoveryService, TestRAGRecoveryServiceErrorHandling
from .test_file_manager import TestRAGFileManager, TestRAGFileManagerErrorHandling
from .test_rag_integration import TestRAGModuleIntegration, TestRAGModuleSOLIDCompliance

__all__ = [
    # Core module tests
    "TestRAGCoordinator",
    "TestRAGIndexBuilder",
    "TestRAGQueryEngine",
    "TestRAGRecoveryService",
    "TestRAGFileManager",

    # Error handling tests
    "TestRAGCoordinatorEdgeCases",
    "TestRAGIndexBuilderErrorHandling",
    "TestRAGQueryEngineErrorHandling",
    "TestRAGRecoveryServiceErrorHandling",
    "TestRAGFileManagerErrorHandling",

    # Integration tests
    "TestRAGModuleIntegration",
    "TestRAGModuleSOLIDCompliance"
]

# Test configuration
TEST_CONFIG = {
    "timeout": 30,  # seconds
    "markers": {
        "unit": "Unit tests for individual RAG modules",
        "integration": "Integration tests for RAG module interactions",
        "asyncio": "Tests requiring asyncio event loop",
        "slow": "Slow running tests (>5 seconds)"
    }
}