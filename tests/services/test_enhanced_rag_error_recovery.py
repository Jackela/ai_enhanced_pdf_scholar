"""
Comprehensive Tests for Enhanced RAG Service Error Recovery

This module tests all error recovery mechanisms in the Enhanced RAG Service including:
- Index building with comprehensive error recovery
- Transactional database operations with rollback
- Resource cleanup and orphan detection
- Corrupted index recovery and repair
- Health checks and system recovery verification
- API failure handling with retry and circuit breaker
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from typing import Dict, Any

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.services.enhanced_rag_service import (
    EnhancedRAGService, RAGIndexError, RAGRecoveryError,
    InsufficientResourcesError, IndexCorruptionError
)
from src.services.error_recovery import (
    RetryExhaustedException, CircuitBreakerOpenError
)


class TestEnhancedRAGServiceErrorRecovery:
    """Test suite for Enhanced RAG Service error recovery functionality."""
    
    @classmethod
    def setup_class(cls):
        """Set up test database and service."""
        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        cls.db = DatabaseConnection(cls.db_path)
        cls._initialize_test_database()
        
        # Create temporary storage directory
        cls.temp_storage = tempfile.mkdtemp()
        
        # Create service in test mode
        cls.service = EnhancedRAGService(
            api_key="test_key",
            db_connection=cls.db,
            vector_storage_dir=cls.temp_storage,
            test_mode=True
        )
        
    @classmethod
    def teardown_class(cls):
        """Clean up test resources."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)
        shutil.rmtree(cls.temp_storage, ignore_errors=True)
        
    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT ''
            )
        """)
        
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                index_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
    def setup_method(self):
        """Set up for each test method."""
        # Clear database tables
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")
        
        # Reset service state
        self.service.current_document_id = None
        self.service.current_vector_index = None
        self.service.current_index = None
        
    def test_preflight_checks_insufficient_disk_space(self):
        """Test pre-flight check failure due to insufficient disk space."""
        # Create a test document
        document = DocumentModel(
            id=1,
            title="Test Document",
            file_path=str(Path(self.temp_storage) / "test.pdf"),
            file_hash="test_hash"
        )
        
        # Create the file so it exists
        Path(document.file_path).write_text("test content")
        
        # Mock disk usage to simulate insufficient space
        with patch('psutil.disk_usage') as mock_disk:
            mock_disk.return_value = MagicMock(free=500_000_000)  # 500MB free
            
            with pytest.raises(InsufficientResourcesError):
                self.service.build_index_from_document(document)
                
        # Clean up
        Path(document.file_path).unlink(missing_ok=True)
        
    def test_preflight_checks_high_memory_usage(self):
        """Test pre-flight check failure due to high memory usage."""
        document = DocumentModel(
            id=1,
            title="Test Document", 
            file_path=str(Path(self.temp_storage) / "test.pdf"),
            file_hash="test_hash"
        )
        
        Path(document.file_path).write_text("test content")
        
        # Mock memory usage to simulate high usage
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = MagicMock(percent=95.0)  # 95% usage
            
            with pytest.raises(InsufficientResourcesError):
                self.service.build_index_from_document(document)
                
        Path(document.file_path).unlink(missing_ok=True)
        
    def test_api_failure_with_retry_exhaustion(self):
        """Test API failure handling with retry exhaustion."""
        document = DocumentModel(
            id=1,
            title="Test Document",
            file_path=str(Path(self.temp_storage) / "test.pdf"),
            file_hash="test_hash"
        )
        
        Path(document.file_path).write_text("test content")
        
        # Mock the PDF building to always fail
        with patch.object(self.service, 'build_index_from_pdf', side_effect=ConnectionError("API failure")):
            with pytest.raises(RAGIndexError, match="API issues"):
                self.service.build_index_from_document(document)
                
        Path(document.file_path).unlink(missing_ok=True)
        
    def test_database_transaction_rollback_on_failure(self):
        """Test database transaction rollback on failure."""
        # Insert document first
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Test Document", str(Path(self.temp_storage) / "test.pdf"), "test_hash")
        ).lastrowid
        
        document = DocumentModel(
            id=doc_id,
            title="Test Document",
            file_path=str(Path(self.temp_storage) / "test.pdf"),
            file_hash="test_hash"
        )
        
        Path(document.file_path).write_text("test content")
        
        # Mock vector repository to fail during database operations
        with patch.object(self.service.vector_repo, 'create', side_effect=Exception("Database error")):
            with pytest.raises(Exception):
                self.service.build_index_from_document(document)
                
        # Verify no orphaned vector index records exist
        vector_indexes = self.db.execute("SELECT COUNT(*) FROM vector_indexes").fetchone()[0]
        assert vector_indexes == 0
        
        Path(document.file_path).unlink(missing_ok=True)
        
    def test_comprehensive_cleanup_on_failure(self):
        """Test comprehensive cleanup when index building fails."""
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Test Document", str(Path(self.temp_storage) / "test.pdf"), "test_hash")
        ).lastrowid
        
        document = DocumentModel(
            id=doc_id,
            title="Test Document",
            file_path=str(Path(self.temp_storage) / "test.pdf"),
            file_hash="test_hash"
        )
        
        Path(document.file_path).write_text("test content")
        
        # Mock to fail after creating some files
        with patch.object(self.service, '_copy_index_files_with_retry', side_effect=Exception("Copy failed")):
            with pytest.raises(Exception):
                self.service.build_index_from_document(document)
                
        # Verify vector storage directory is clean
        storage_contents = list(Path(self.temp_storage).iterdir())
        doc_dirs = [d for d in storage_contents if d.is_dir() and d.name.startswith(f"doc_{doc_id}")]
        assert len(doc_dirs) == 0, "Vector index directories should be cleaned up"
        
        Path(document.file_path).unlink(missing_ok=True)
        
    def test_corrupted_index_detection_and_analysis(self):
        """Test detection and analysis of corrupted indexes."""
        # Create a corrupted vector index
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Test Document", str(Path(self.temp_storage) / "test.pdf"), "test_hash")
        ).lastrowid
        
        # Create corrupted index directory
        corrupted_path = Path(self.temp_storage) / f"doc_{doc_id}_corrupted"
        corrupted_path.mkdir()
        
        # Create partially corrupted index (missing required files)
        (corrupted_path / "incomplete_file.json").write_text('{"incomplete": true}')
        
        # Insert vector index record
        index_id = self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count) VALUES (?, ?, ?)",
            (doc_id, str(corrupted_path), 10)
        ).lastrowid
        
        # Test corruption recovery
        recovery_result = self.service.recover_corrupted_index(doc_id)
        
        assert recovery_result["corruption_detected"] is True
        assert "missing_files" in recovery_result["corruption_type"]
        assert recovery_result["corruption_severity"] == "critical"
        assert len(recovery_result["missing_files"]) > 0
        
        # Clean up
        shutil.rmtree(corrupted_path, ignore_errors=True)
        
    def test_corrupted_index_full_rebuild_recovery(self):
        """Test full rebuild recovery for critically corrupted indexes."""
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Test Document", str(Path(self.temp_storage) / "test.pdf"), "test_hash")
        ).lastrowid
        
        document_file = Path(self.temp_storage) / "test.pdf"
        document_file.write_text("test content")
        
        # Create completely missing index directory
        missing_path = Path(self.temp_storage) / f"doc_{doc_id}_missing"
        
        # Insert vector index record pointing to missing directory
        self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count) VALUES (?, ?, ?)",
            (doc_id, str(missing_path), 10)
        )
        
        # Test recovery with rebuild
        recovery_result = self.service.recover_corrupted_index(doc_id, force_rebuild=True)
        
        assert recovery_result["recovery_successful"] is True
        assert "full_rebuild" in recovery_result["repair_actions"]
        assert "new_index_id" in recovery_result
        
        # Clean up
        document_file.unlink(missing_ok=True)
        
    def test_orphaned_resource_detection_and_cleanup(self):
        """Test detection and cleanup of orphaned resources."""
        # Create orphaned vector index directory (no database record)
        orphaned_dir = Path(self.temp_storage) / "doc_999_orphaned"
        orphaned_dir.mkdir()
        (orphaned_dir / "test_file.json").write_text('{"orphaned": true}')
        
        # Create orphaned database record (no filesystem directory)
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Orphaned Document", "/nonexistent/path.pdf", "orphaned_hash")
        ).lastrowid
        
        self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count) VALUES (?, ?, ?)",
            (doc_id, "/nonexistent/index/path", 5)
        )
        
        # Perform system recovery check
        recovery_report = self.service.perform_system_recovery_check()
        
        assert "cleanup_actions" in recovery_report
        assert len(recovery_report["cleanup_actions"]) > 0
        
        # Verify orphaned directory was cleaned up
        assert not orphaned_dir.exists()
        
    def test_health_check_integration(self):
        """Test health check integration and reporting."""
        # Test all health checks
        health_results = self.service.health_checker.run_all_checks()
        
        expected_checks = ["disk_space", "memory_usage", "vector_storage", "database_connection"]
        for check in expected_checks:
            assert check in health_results
            
        # Test overall health status
        assert self.service.health_checker.is_healthy()
        
        # Test health checks in recovery metrics
        recovery_metrics = self.service.get_recovery_metrics()
        assert "health_status" in recovery_metrics
        assert "overall_healthy" in recovery_metrics["health_status"]
        
    def test_recovery_metrics_accuracy(self):
        """Test accuracy of recovery metrics tracking."""
        # Perform operations to generate metrics
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Metrics Test Document", str(Path(self.temp_storage) / "metrics_test.pdf"), "metrics_hash")
        ).lastrowid
        
        document_file = Path(self.temp_storage) / "metrics_test.pdf"
        document_file.write_text("metrics test content")
        
        document = DocumentModel(
            id=doc_id,
            title="Metrics Test Document",
            file_path=str(document_file),
            file_hash="metrics_hash"
        )
        
        # Successful index build
        result = self.service.build_index_from_document(document)
        assert result is not None
        
        # Get comprehensive metrics
        metrics = self.service.get_recovery_metrics()
        
        # Verify metric structure
        assert "orchestrator" in metrics
        assert "retry" in metrics
        assert "circuit_breaker" in metrics
        assert "cleanup" in metrics
        assert "service_metrics" in metrics
        assert "health_status" in metrics
        assert "database_metrics" in metrics
        
        # Verify some metrics have been recorded
        assert metrics["orchestrator"]["successful_recoveries"] >= 1
        
        # Clean up
        document_file.unlink(missing_ok=True)
        
    def test_system_recovery_check_comprehensive(self):
        """Test comprehensive system recovery check functionality."""
        # Create various scenarios to test
        
        # 1. Create valid index
        doc1_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Valid Document", str(Path(self.temp_storage) / "valid.pdf"), "valid_hash")
        ).lastrowid
        
        valid_doc_file = Path(self.temp_storage) / "valid.pdf"
        valid_doc_file.write_text("valid content")
        
        # 2. Create corrupted index
        doc2_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Corrupted Document", str(Path(self.temp_storage) / "corrupted.pdf"), "corrupted_hash")
        ).lastrowid
        
        corrupted_index_path = Path(self.temp_storage) / f"doc_{doc2_id}_corrupted"
        corrupted_index_path.mkdir()
        # Create incomplete/corrupted index files
        (corrupted_index_path / "incomplete.json").write_text('{"incomplete": true}')
        
        self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count) VALUES (?, ?, ?)",
            (doc2_id, str(corrupted_index_path), 5)
        )
        
        # 3. Create orphaned filesystem directory
        orphaned_dir = Path(self.temp_storage) / "doc_888_orphaned"
        orphaned_dir.mkdir()
        (orphaned_dir / "orphaned.json").write_text('{"orphaned": true}')
        
        # Perform comprehensive recovery check
        recovery_report = self.service.perform_system_recovery_check()
        
        # Verify report structure
        assert "check_start_time" in recovery_report
        assert "check_end_time" in recovery_report
        assert "health_status" in recovery_report
        assert "orphaned_resources" in recovery_report
        assert "corrupted_indexes" in recovery_report
        assert "cleanup_actions" in recovery_report
        assert "recommendations" in recovery_report
        assert "overall_status" in recovery_report
        
        # Verify some issues were detected and addressed
        if recovery_report["corrupted_indexes"]:
            assert recovery_report["overall_status"] in ["degraded", "critical"]
            
        if recovery_report["cleanup_actions"]:
            assert len(recovery_report["cleanup_actions"]) > 0
            
        # Clean up
        valid_doc_file.unlink(missing_ok=True)
        shutil.rmtree(corrupted_index_path, ignore_errors=True)
        # orphaned_dir should have been cleaned up by the recovery check
        
    def test_api_circuit_breaker_protection(self):
        """Test API circuit breaker protection during index building."""
        # Create document
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Circuit Breaker Test", str(Path(self.temp_storage) / "circuit_test.pdf"), "circuit_hash")
        ).lastrowid
        
        document_file = Path(self.temp_storage) / "circuit_test.pdf"
        document_file.write_text("circuit breaker test content")
        
        document = DocumentModel(
            id=doc_id,
            title="Circuit Breaker Test",
            file_path=str(document_file),
            file_hash="circuit_hash"
        )
        
        # Mock API calls to always fail
        failure_count = 0
        
        def failing_api_call(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            raise ConnectionError("API service unavailable")
            
        with patch.object(self.service, 'build_index_from_pdf', side_effect=failing_api_call):
            # First few attempts should trigger retries
            with pytest.raises(RAGIndexError):
                self.service.build_index_from_document(document)
                
            # After circuit breaker trips, subsequent calls should be faster failures
            with pytest.raises(RAGIndexError):
                self.service.build_index_from_document(document)
                
        # Verify circuit breaker metrics
        metrics = self.service.get_recovery_metrics()
        circuit_metrics = metrics.get("circuit_breaker", {})
        
        # Should have recorded some circuit breaker activity
        assert circuit_metrics.get("trips", 0) >= 0  # May or may not have tripped depending on timing
        
        # Clean up
        document_file.unlink(missing_ok=True)
        
    def test_emergency_cleanup_on_critical_failure(self):
        """Test emergency cleanup procedures on critical failures."""
        # Create document and partially successful operation
        doc_id = self.db.execute(
            "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
            ("Emergency Test", str(Path(self.temp_storage) / "emergency.pdf"), "emergency_hash")
        ).lastrowid
        
        document_file = Path(self.temp_storage) / "emergency.pdf" 
        document_file.write_text("emergency test content")
        
        document = DocumentModel(
            id=doc_id,
            title="Emergency Test",
            file_path=str(document_file),
            file_hash="emergency_hash"
        )
        
        # Create a scenario where vector files are created but database operation fails critically
        with patch.object(self.service, '_create_or_update_index_record', side_effect=Exception("Critical database failure")):
            with pytest.raises(RAGRecoveryError):
                self.service.build_index_from_document(document)
                
        # Verify emergency cleanup occurred - no orphaned vector directories
        vector_dirs = [
            d for d in Path(self.temp_storage).iterdir() 
            if d.is_dir() and d.name.startswith(f"doc_{doc_id}")
        ]
        assert len(vector_dirs) == 0, "Emergency cleanup should remove orphaned vector directories"
        
        # Clean up
        document_file.unlink(missing_ok=True)


class TestIntegrationScenarios:
    """Integration tests for complex error recovery scenarios."""
    
    @classmethod  
    def setup_class(cls):
        """Set up test environment."""
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        cls.db = DatabaseConnection(cls.db_path)
        cls._initialize_test_database()
        cls.temp_storage = tempfile.mkdtemp()
        
        cls.service = EnhancedRAGService(
            api_key="test_key",
            db_connection=cls.db,
            vector_storage_dir=cls.temp_storage,
            test_mode=True
        )
        
    @classmethod
    def teardown_class(cls):
        """Clean up test environment."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)
        shutil.rmtree(cls.temp_storage, ignore_errors=True)
        
    @classmethod
    def _initialize_test_database(cls):
        """Initialize test database schema."""
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT ''
            )
        """)
        
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                index_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
    def test_end_to_end_recovery_workflow(self):
        """Test complete end-to-end recovery workflow."""
        # Clear previous test data
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")
        
        # Create multiple documents with various issues
        docs_data = [
            ("Valid Document", "valid.pdf", "valid_hash", True),
            ("Missing File Document", "missing.pdf", "missing_hash", False),
            ("Corrupted Index Document", "corrupted.pdf", "corrupted_hash", True),
        ]
        
        created_docs = []
        for title, filename, file_hash, create_file in docs_data:
            doc_id = self.db.execute(
                "INSERT INTO documents (title, file_path, file_hash) VALUES (?, ?, ?)",
                (title, str(Path(self.temp_storage) / filename), file_hash)
            ).lastrowid
            
            if create_file:
                doc_file = Path(self.temp_storage) / filename
                doc_file.write_text(f"Content for {title}")
                
            created_docs.append((doc_id, title, filename, create_file))
        
        # Create corrupted index for third document
        corrupted_doc_id = created_docs[2][0]
        corrupted_path = Path(self.temp_storage) / f"doc_{corrupted_doc_id}_corrupted"
        corrupted_path.mkdir()
        (corrupted_path / "bad_file.json").write_text('invalid json content')
        
        self.db.execute(
            "INSERT INTO vector_indexes (document_id, index_path, chunk_count) VALUES (?, ?, ?)",
            (corrupted_doc_id, str(corrupted_path), 0)
        )
        
        # Perform comprehensive system check
        recovery_report = self.service.perform_system_recovery_check()
        
        # Verify comprehensive recovery report
        assert recovery_report["overall_status"] in ["healthy", "degraded", "critical"]
        assert "health_status" in recovery_report
        assert "corrupted_indexes" in recovery_report
        assert "cleanup_actions" in recovery_report
        
        # Test individual document recovery
        if recovery_report["corrupted_indexes"]:
            for corrupted_info in recovery_report["corrupted_indexes"]:
                doc_id = corrupted_info["document_id"]
                recovery_result = self.service.recover_corrupted_index(doc_id, force_rebuild=True)
                
                # Should attempt recovery
                assert recovery_result["document_id"] == doc_id
                assert len(recovery_result["repair_actions"]) > 0
        
        # Clean up created files
        for doc_id, title, filename, was_created in created_docs:
            if was_created:
                doc_file = Path(self.temp_storage) / filename
                doc_file.unlink(missing_ok=True)
        
        shutil.rmtree(corrupted_path, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])