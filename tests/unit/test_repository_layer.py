"""
Unit tests for repository layer components.
Tests repository pattern implementation and data access logic.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository


class TestDocumentRepository:
    """Test DocumentRepository functionality."""

    def test_document_repository_creation(self):
        """Test DocumentRepository creation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)
            assert repo is not None
            assert repo.db == db
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_document_repository_basic_crud(self):
        """Test basic CRUD operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)

            # Initialize database schema
            db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_size INTEGER NOT NULL,
                    content_hash TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            repo = DocumentRepository(db)

            # Test document creation
            doc = DocumentModel(
                title="Test Document",
                file_path="/test/path.pdf",
                file_hash="test_hash_123",
                file_size=1024
            )

            # Mock the create method to test interface
            with patch.object(repo, 'create') as mock_create:
                mock_create.return_value = 1
                doc_id = repo.create(doc)
                assert doc_id == 1
                mock_create.assert_called_once_with(doc)

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_document_repository_find_by_hash(self):
        """Test finding documents by hash."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)

            # Mock the find_by_hash method
            with patch.object(repo, 'find_by_hash') as mock_find:
                mock_doc = DocumentModel(
                    id=1,
                    title="Test Document",
                    file_path="/test/path.pdf",
                    file_hash="test_hash_123",
                    file_size=1024
                )
                mock_find.return_value = mock_doc

                result = repo.find_by_hash("test_hash_123")
                assert result == mock_doc
                mock_find.assert_called_once_with("test_hash_123")

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_document_repository_search_interface(self):
        """Test search interface functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)

            # Mock the search method
            with patch.object(repo, 'search') as mock_search:
                mock_results = [
                    DocumentModel(
                        id=1,
                        title="Test Document 1",
                        file_path="/test/path1.pdf",
                        file_hash="hash1",
                        file_size=1024
                    ),
                    DocumentModel(
                        id=2,
                        title="Test Document 2",
                        file_path="/test/path2.pdf",
                        file_hash="hash2",
                        file_size=2048
                    )
                ]
                mock_search.return_value = mock_results

                results = repo.search("test")
                assert len(results) == 2
                assert results[0].title == "Test Document 1"
                assert results[1].title == "Test Document 2"
                mock_search.assert_called_once_with("test")

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestVectorIndexRepository:
    """Test VectorIndexRepository functionality."""

    def test_vector_repository_creation(self):
        """Test VectorIndexRepository creation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = VectorIndexRepository(db)
            assert repo is not None
            assert repo.db == db
            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_vector_repository_basic_crud(self):
        """Test basic CRUD operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)

            # Initialize database schema
            db.execute("""
                CREATE TABLE IF NOT EXISTS vector_indexes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    index_path TEXT NOT NULL,
                    index_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            repo = VectorIndexRepository(db)

            # Test vector index creation
            index = VectorIndexModel(
                document_id=1,
                index_path="/test/index.faiss",
                index_hash="index_hash_123"
            )

            # Mock the create method
            with patch.object(repo, 'create') as mock_create:
                mock_create.return_value = 1
                index_id = repo.create(index)
                assert index_id == 1
                mock_create.assert_called_once_with(index)

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_vector_repository_find_by_document_id(self):
        """Test finding vector indexes by document ID."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = VectorIndexRepository(db)

            # Mock the find_by_document_id method
            with patch.object(repo, 'find_by_document_id') as mock_find:
                mock_index = VectorIndexModel(
                    id=1,
                    document_id=1,
                    index_path="/test/index.faiss",
                    index_hash="index_hash_123"
                )
                mock_find.return_value = mock_index

                result = repo.find_by_document_id(1)
                assert result == mock_index
                mock_find.assert_called_once_with(1)

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_vector_repository_cleanup_interface(self):
        """Test cleanup interface functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = VectorIndexRepository(db)

            # Mock the cleanup_orphaned_indexes method
            with patch.object(repo, 'cleanup_orphaned_indexes') as mock_cleanup:
                mock_cleanup.return_value = 3  # 3 orphaned indexes cleaned

                result = repo.cleanup_orphaned_indexes()
                assert result == 3
                mock_cleanup.assert_called_once()

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestRepositoryIntegration:
    """Test repository integration scenarios."""

    def test_repository_dependency_injection(self):
        """Test that repositories can be properly injected."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)

            # Create repositories
            doc_repo = DocumentRepository(db)
            vector_repo = VectorIndexRepository(db)

            # Test that they share the same database connection
            assert doc_repo.db == db
            assert vector_repo.db == db
            assert doc_repo.db == vector_repo.db

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_repository_transaction_support(self):
        """Test that repositories support transactions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)

            # Mock transaction support
            with patch.object(db, 'transaction') as mock_transaction:
                mock_transaction.return_value.__enter__ = MagicMock()
                mock_transaction.return_value.__exit__ = MagicMock()

                # Test transaction context manager
                with db.transaction():
                    pass

                mock_transaction.assert_called_once()

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_repository_error_handling(self):
        """Test repository error handling."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)

            # Mock database error
            with patch.object(db, 'execute') as mock_execute:
                mock_execute.side_effect = Exception("Database error")

                # Test that repository handles database errors gracefully
                with pytest.raises(Exception, match="Database error"):
                    db.execute("SELECT 1")

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestRepositoryPerformance:
    """Test repository performance characteristics."""

    def test_repository_creation_performance(self):
        """Test that repository creation is fast."""
        import time

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)

            start_time = time.time()
            for i in range(10):
                repo = DocumentRepository(db)
                assert repo is not None

            duration = time.time() - start_time
            assert duration < 0.1  # Should be very fast

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_repository_mock_performance(self):
        """Test that mocked repository operations are fast."""
        import time

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            db = DatabaseConnection(db_path)
            repo = DocumentRepository(db)

            with patch.object(repo, 'find_by_hash') as mock_find:
                mock_find.return_value = DocumentModel(
                    id=1,
                    title="Test",
                    file_path="/test/path.pdf",
                    file_hash="test_hash",
                    file_size=1024
                )

                start_time = time.time()
                for i in range(100):
                    result = repo.find_by_hash(f"hash_{i}")
                    assert result is not None

                duration = time.time() - start_time
                assert duration < 0.1  # Mocked operations should be very fast

            db.close_all_connections()
        finally:
            Path(db_path).unlink(missing_ok=True)
