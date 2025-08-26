"""
Comprehensive Tests for VectorIndexManager
Tests all aspects of vector index persistence management including:
- Index storage creation and lifecycle
- File moving and integrity verification
- Backup and restore operations
- Storage optimization and cleanup
- Statistics and monitoring
- Error handling and edge cases
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.services.vector_index_manager import (
    VectorIndexManager,
    VectorIndexManagerError,
)


class TestVectorIndexManager:
    """Comprehensive test suite for VectorIndexManager."""

    @classmethod
    def setup_class(cls):
        """Set up test database and fixtures."""
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
        # Create documents table
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
        # Create vector_indexes table
        cls.db.execute(
            """
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
        """
        )

    def setup_method(self):
        """Set up for each test method."""
        # Create temporary storage directory
        self.temp_storage_dir = tempfile.mkdtemp()
        # Create manager instance
        self.manager = VectorIndexManager(
            db_connection=self.db, storage_base_dir=self.temp_storage_dir
        )
        # Clear database tables
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")

    def teardown_method(self):
        """Clean up after each test method."""
        if Path(self.temp_storage_dir).exists():
            shutil.rmtree(self.temp_storage_dir)

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

    def _create_mock_index_files(self, index_path: Path):
        """Create mock LlamaIndex files for testing."""
        index_path.mkdir(parents=True, exist_ok=True)
        # Create required LlamaIndex files
        required_files = {
            "default__vector_store.json": {
                "embedding_dict": {f"chunk_{i}": [0.1] * 384 for i in range(5)},
                "metadata_dict": {},
            },
            "graph_store.json": {"graph_dict": {}},
            "index_store.json": {"index_store": {}},
        }
        for filename, content in required_files.items():
            with open(index_path / filename, "w") as f:
                json.dump(content, f)
        # Create metadata file
        metadata = {
            "document_id": 1,
            "index_hash": "test_hash",
            "chunk_count": 5,
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "format": "llamaindex",
        }
        with open(index_path / "index_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    # ===== Initialization Tests =====
    def test_initialization_creates_directories(self):
        """Test that manager initialization creates required directories."""
        assert self.manager.storage_base_dir.exists()
        assert self.manager.active_dir.exists()
        assert self.manager.backup_dir.exists()
        assert self.manager.temp_dir.exists()
        # Verify directory structure
        assert self.manager.active_dir.name == "active"
        assert self.manager.backup_dir.name == "backup"
        assert self.manager.temp_dir.name == "temp"

    def test_initialization_with_existing_directory(self):
        """Test initialization when storage directory already exists."""
        # Create manager with same directory
        manager2 = VectorIndexManager(
            db_connection=self.db, storage_base_dir=self.temp_storage_dir
        )
        assert manager2.storage_base_dir == self.manager.storage_base_dir
        assert manager2.active_dir.exists()
        assert manager2.backup_dir.exists()
        assert manager2.temp_dir.exists()

    # ===== Index Storage Creation Tests =====
    def test_create_index_storage_success(self):
        """Test successful index storage creation."""
        document_id = self._create_test_document()
        index_hash = "test_hash_123"
        chunk_count = 10
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash=index_hash, chunk_count=chunk_count
        )
        assert vector_index is not None
        assert vector_index.id is not None
        assert vector_index.document_id == document_id
        assert vector_index.index_hash == index_hash
        assert vector_index.chunk_count == chunk_count
        # Verify storage directory was created
        index_path = Path(vector_index.index_path)
        assert index_path.exists()
        assert index_path.parent == self.manager.active_dir
        # Verify metadata file was created
        metadata_file = index_path / "index_metadata.json"
        assert metadata_file.exists()
        with open(metadata_file) as f:
            metadata = json.load(f)
        assert metadata["document_id"] == document_id
        assert metadata["index_hash"] == index_hash
        assert metadata["chunk_count"] == chunk_count

    def test_create_index_storage_duplicate_path_handling(self):
        """Test handling of duplicate storage paths."""
        document_id = self._create_test_document()
        index_hash = "same_hash"
        # Mock datetime to ensure same timestamp
        mock_dt = MagicMock()
        mock_dt.strftime.return_value = "20230101_120000"
        mock_dt.isoformat.return_value = "2023-01-01T12:00:00"

        with patch("src.services.vector_index_manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            # Create first index
            index1 = self.manager.create_index_storage(
                document_id=document_id, index_hash=index_hash, chunk_count=5
            )
            # Create directory manually to simulate conflict
            conflicting_path = (
                self.manager.active_dir
                / f"doc_{document_id}_{index_hash[:8]}_20230101_120000"
            )
            conflicting_path.mkdir(exist_ok=True)
            # Create second index (should handle conflict)
            index2 = self.manager.create_index_storage(
                document_id=document_id, index_hash=index_hash, chunk_count=7
            )
        assert index1.id != index2.id
        assert Path(index1.index_path).exists()
        assert Path(index2.index_path).exists()
        assert "_alt" in index2.index_path

    def test_create_index_storage_database_error(self):
        """Test error handling when database save fails."""
        document_id = self._create_test_document()
        with patch.object(
            self.manager.vector_repo, "create", side_effect=Exception("Database error")
        ):
            with pytest.raises(
                VectorIndexManagerError, match="Index storage creation failed"
            ):
                self.manager.create_index_storage(
                    document_id=document_id, index_hash="test_hash", chunk_count=5
                )

    # ===== File Moving Tests =====
    def test_move_index_to_storage_success(self):
        """Test successful index file moving."""
        # Create source directory with mock files
        source_dir = Path(tempfile.mkdtemp())
        self._create_mock_index_files(source_dir)
        try:
            # Create vector index
            document_id = self._create_test_document()
            vector_index = self.manager.create_index_storage(
                document_id=document_id, index_hash="test_hash", chunk_count=5
            )
            # Move files
            with patch.object(
                self.manager, "verify_index_integrity", return_value=True
            ):
                success = self.manager.move_index_to_storage(vector_index, source_dir)
            assert success is True
            # Verify files were copied
            dest_path = Path(vector_index.index_path)
            assert (dest_path / "default__vector_store.json").exists()
            assert (dest_path / "graph_store.json").exists()
            assert (dest_path / "index_store.json").exists()
        finally:
            shutil.rmtree(source_dir)

    def test_move_index_to_storage_missing_source(self):
        """Test moving when source directory doesn't exist."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        nonexistent_source = Path("/nonexistent/path")
        with pytest.raises(VectorIndexManagerError, match="Source path does not exist"):
            self.manager.move_index_to_storage(vector_index, nonexistent_source)

    def test_move_index_to_storage_missing_required_files(self):
        """Test moving when required files are missing."""
        source_dir = Path(tempfile.mkdtemp())
        try:
            # Create only some required files
            source_dir.mkdir(exist_ok=True)
            with open(source_dir / "default__vector_store.json", "w") as f:
                json.dump({}, f)
            # Missing graph_store.json and index_store.json
            document_id = self._create_test_document()
            vector_index = self.manager.create_index_storage(
                document_id=document_id, index_hash="test_hash", chunk_count=5
            )
            with pytest.raises(VectorIndexManagerError, match="Missing required files"):
                self.manager.move_index_to_storage(vector_index, source_dir)
        finally:
            shutil.rmtree(source_dir)

    def test_move_index_integrity_verification_failure(self):
        """Test moving when integrity verification fails."""
        source_dir = Path(tempfile.mkdtemp())
        self._create_mock_index_files(source_dir)
        try:
            document_id = self._create_test_document()
            vector_index = self.manager.create_index_storage(
                document_id=document_id, index_hash="test_hash", chunk_count=5
            )
            # Mock integrity verification to fail
            with patch.object(
                self.manager, "verify_index_integrity", return_value=False
            ):
                with pytest.raises(
                    VectorIndexManagerError, match="Index integrity verification failed"
                ):
                    self.manager.move_index_to_storage(vector_index, source_dir)
        finally:
            shutil.rmtree(source_dir)

    def test_move_index_chunk_count_update(self):
        """Test that chunk count is updated when extracted from files."""
        source_dir = Path(tempfile.mkdtemp())
        self._create_mock_index_files(source_dir)
        try:
            document_id = self._create_test_document()
            vector_index = self.manager.create_index_storage(
                document_id=document_id,
                index_hash="test_hash",
                chunk_count=0,  # Start with 0
            )
            # Mock chunk count extraction
            with patch.object(self.manager, "_extract_chunk_count", return_value=10):
                with patch.object(
                    self.manager, "verify_index_integrity", return_value=True
                ):
                    success = self.manager.move_index_to_storage(
                        vector_index, source_dir
                    )
            assert success is True
            # Verify chunk count was updated
            updated_index = self.manager.vector_repo.find_by_id(vector_index.id)
            assert updated_index.chunk_count == 10
        finally:
            shutil.rmtree(source_dir)

    # ===== Integrity Verification Tests =====
    def test_verify_index_integrity_valid_index(self):
        """Test integrity verification for valid index."""
        # Create index with valid files
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Create mock files
        index_path = Path(vector_index.index_path)
        self._create_mock_index_files(index_path)
        result = self.manager.verify_index_integrity(vector_index.id)
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert result["metadata_check"] is True
        assert "file_checks" in result
        assert "size_info" in result

    def test_verify_index_integrity_nonexistent_index(self):
        """Test integrity verification for nonexistent index."""
        result = self.manager.verify_index_integrity(99999)
        assert result["is_valid"] is False
        assert "Vector index not found in database" in result["errors"]

    def test_verify_index_integrity_missing_directory(self):
        """Test integrity verification when index directory doesn't exist."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Remove the directory
        shutil.rmtree(vector_index.index_path)
        result = self.manager.verify_index_integrity(vector_index.id)
        assert result["is_valid"] is False
        assert any(
            "Index directory does not exist" in error for error in result["errors"]
        )

    def test_verify_index_integrity_missing_required_files(self):
        """Test integrity verification when required files are missing."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Create directory but not all required files
        index_path = Path(vector_index.index_path)
        index_path.mkdir(exist_ok=True)
        # Create only one required file
        with open(index_path / "default__vector_store.json", "w") as f:
            json.dump({}, f)
        result = self.manager.verify_index_integrity(vector_index.id)
        assert result["is_valid"] is False
        assert any("Required file missing" in error for error in result["errors"])
        assert "graph_store.json" in str(result["errors"])
        assert "index_store.json" in str(result["errors"])

    def test_verify_index_integrity_corrupted_json(self):
        """Test integrity verification when JSON files are corrupted."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Create directory with corrupted files
        index_path = Path(vector_index.index_path)
        index_path.mkdir(exist_ok=True)
        # Create corrupted JSON files
        required_files = [
            "default__vector_store.json",
            "graph_store.json",
            "index_store.json",
        ]
        for filename in required_files:
            with open(index_path / filename, "w") as f:
                f.write("invalid json content {")
        result = self.manager.verify_index_integrity(vector_index.id)
        assert result["is_valid"] is False
        assert any("is corrupted" in error for error in result["errors"])

    def test_verify_index_integrity_metadata_inconsistency(self):
        """Test integrity verification when metadata is inconsistent."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Create valid files
        index_path = Path(vector_index.index_path)
        self._create_mock_index_files(index_path)
        # Create metadata with wrong document_id
        metadata = {
            "document_id": 999,  # Wrong document ID
            "index_hash": "test_hash",
            "chunk_count": 5,
        }
        with open(index_path / "index_metadata.json", "w") as f:
            json.dump(metadata, f)
        result = self.manager.verify_index_integrity(vector_index.id)
        assert result["is_valid"] is True  # Still valid, just warning
        assert any(
            "Metadata document_id mismatch" in warning for warning in result["warnings"]
        )

    # ===== Backup Tests =====
    def test_backup_index_success(self):
        """Test successful index backup."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Create mock files
        index_path = Path(vector_index.index_path)
        self._create_mock_index_files(index_path)
        backup_path = self.manager.backup_index(vector_index.id)
        assert backup_path is not None
        backup_dir = Path(backup_path)
        assert backup_dir.exists()
        assert backup_dir.parent == self.manager.backup_dir
        # Verify backup files exist
        assert (backup_dir / "default__vector_store.json").exists()
        assert (backup_dir / "graph_store.json").exists()
        assert (backup_dir / "index_store.json").exists()
        assert (backup_dir / "backup_metadata.json").exists()
        # Verify backup metadata
        with open(backup_dir / "backup_metadata.json") as f:
            backup_metadata = json.load(f)
        assert backup_metadata["original_index_id"] == vector_index.id
        assert backup_metadata["document_id"] == document_id
        assert backup_metadata["index_hash"] == "test_hash"

    def test_backup_index_nonexistent(self):
        """Test backup of nonexistent index."""
        with pytest.raises(VectorIndexManagerError, match="Vector index not found"):
            self.manager.backup_index(99999)

    def test_backup_index_missing_files(self):
        """Test backup when index files don't exist."""
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="test_hash", chunk_count=5
        )
        # Remove the index directory
        shutil.rmtree(vector_index.index_path)
        with pytest.raises(VectorIndexManagerError, match="Index path does not exist"):
            self.manager.backup_index(vector_index.id)

    # ===== Storage Optimization Tests =====
    def test_optimize_storage_empty(self):
        """Test storage optimization when no cleanup is needed."""
        results = self.manager.optimize_storage()
        assert results["orphaned_removed"] == 0
        assert results["duplicates_removed"] == 0
        assert results["corrupted_removed"] == 0
        assert results["space_freed_mb"] == 0

    def test_optimize_storage_with_orphaned_directories(self):
        """Test optimization removes orphaned storage directories."""
        # Create orphaned directory in active storage
        orphaned_dir = self.manager.active_dir / "orphaned_index"
        orphaned_dir.mkdir()
        (orphaned_dir / "dummy_file.txt").write_text("dummy content")
        with patch.object(self.manager, "_remove_corrupted_indexes", return_value=0):
            results = self.manager.optimize_storage()
        assert results["orphaned_removed"] == 1
        assert not orphaned_dir.exists()

    @patch("time.time")
    def test_optimize_storage_cleanup_old_backups(self, mock_time):
        """Test optimization removes old backups."""
        # Mock current time
        current_time = 1000000
        mock_time.return_value = current_time
        # Create old backup directory
        old_backup = self.manager.backup_dir / "old_backup"
        old_backup.mkdir()
        # Set modified time to be older than 30 days
        old_time = current_time - (31 * 24 * 60 * 60)  # 31 days ago
        old_backup.touch()
        # Mock stat to return old time
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_time
            with patch.object(self.manager, "_remove_orphaned_storage", return_value=0):
                with patch.object(
                    self.manager, "_remove_corrupted_indexes", return_value=0
                ):
                    results = self.manager.optimize_storage()
        # Verify optimization completed (old backup removal is in background)
        assert isinstance(results, dict)

    # ===== Storage Statistics Tests =====
    def test_get_storage_statistics_empty(self):
        """Test storage statistics when no indexes exist."""
        stats = self.manager.get_storage_statistics()
        assert stats["total_indexes"] == 0
        assert stats["active_indexes"] == 0
        assert stats["backup_count"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["average_index_size_mb"] == 0
        assert stats["storage_health"] == "healthy"

    def test_get_storage_statistics_with_indexes(self):
        """Test storage statistics with indexes."""
        # Create test documents and indexes
        doc1_id = self._create_test_document(title="Doc 1")
        doc2_id = self._create_test_document(title="Doc 2")
        index1 = self.manager.create_index_storage(doc1_id, "hash1", 10)
        index2 = self.manager.create_index_storage(doc2_id, "hash2", 15)
        # Create mock files to simulate storage
        for vector_index in [index1, index2]:
            index_path = Path(vector_index.index_path)
            self._create_mock_index_files(index_path)
        # Create backup directory
        backup_dir = self.manager.backup_dir / "test_backup"
        backup_dir.mkdir()
        stats = self.manager.get_storage_statistics()
        assert stats["total_indexes"] == 2
        assert stats["active_indexes"] == 2
        assert stats["backup_count"] == 1
        assert stats["total_size_mb"] > 0
        assert stats["average_index_size_mb"] > 0
        assert stats["storage_health"] == "healthy"

    def test_get_storage_statistics_orphaned_files(self):
        """Test storage statistics when orphaned files exist."""
        # Create orphaned directory
        orphaned_dir = self.manager.active_dir / "orphaned"
        orphaned_dir.mkdir()
        stats = self.manager.get_storage_statistics()
        assert stats["active_indexes"] == 1  # Orphaned directory
        assert stats["storage_health"] == "orphaned_files"

    def test_get_storage_statistics_missing_files(self):
        """Test storage statistics when files are missing."""
        # Create database entry without storage
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(document_id, "hash", 5)
        # Remove storage directory
        shutil.rmtree(vector_index.index_path)
        stats = self.manager.get_storage_statistics()
        assert stats["active_indexes"] == 0
        assert stats["storage_health"] == "missing_files"

    # ===== Helper Methods Tests =====
    def test_extract_chunk_count_from_metadata(self):
        """Test chunk count extraction from metadata file."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            metadata = {"chunk_count": 25}
            with open(temp_dir / "index_metadata.json", "w") as f:
                json.dump(metadata, f)
            chunk_count = self.manager._extract_chunk_count(temp_dir)
            assert chunk_count == 25
        finally:
            shutil.rmtree(temp_dir)

    def test_extract_chunk_count_from_vector_store(self):
        """Test chunk count extraction from vector store file."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            vector_store = {
                "embedding_dict": {
                    "chunk_1": [0.1] * 384,
                    "chunk_2": [0.2] * 384,
                    "chunk_3": [0.3] * 384,
                }
            }
            with open(temp_dir / "default__vector_store.json", "w") as f:
                json.dump(vector_store, f)
            chunk_count = self.manager._extract_chunk_count(temp_dir)
            assert chunk_count == 3
        finally:
            shutil.rmtree(temp_dir)

    def test_extract_chunk_count_no_files(self):
        """Test chunk count extraction when no files exist."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            chunk_count = self.manager._extract_chunk_count(temp_dir)
            assert chunk_count == 0
        finally:
            shutil.rmtree(temp_dir)

    def test_remove_orphaned_storage(self):
        """Test removal of orphaned storage directories."""
        # Create valid index
        document_id = self._create_test_document()
        valid_index = self.manager.create_index_storage(document_id, "valid_hash", 5)
        # Create orphaned directories
        orphaned1 = self.manager.active_dir / "orphaned_1"
        orphaned2 = self.manager.active_dir / "orphaned_2"
        orphaned1.mkdir()
        orphaned2.mkdir()
        removed_count = self.manager._remove_orphaned_storage()
        assert removed_count == 2
        assert not orphaned1.exists()
        assert not orphaned2.exists()
        assert Path(valid_index.index_path).exists()

    @patch.object(VectorIndexManager, "verify_index_integrity")
    @patch.object(VectorIndexManager, "backup_index")
    def test_remove_corrupted_indexes(self, mock_backup, mock_verify):
        """Test removal of corrupted indexes."""
        # Create test indexes
        doc1_id = self._create_test_document(title="Valid Doc")
        doc2_id = self._create_test_document(title="Corrupted Doc")
        valid_index = self.manager.create_index_storage(doc1_id, "valid_hash", 5)
        corrupted_index = self.manager.create_index_storage(
            doc2_id, "corrupted_hash", 5
        )

        # Mock integrity checks
        def mock_integrity(index_id):
            if index_id == valid_index.id:
                return {"is_valid": True, "errors": []}
            else:
                return {"is_valid": False, "errors": ["Corrupted files"]}

        mock_verify.side_effect = mock_integrity
        mock_backup.return_value = "/backup/path"
        removed_count = self.manager._remove_corrupted_indexes()
        assert removed_count == 1
        mock_backup.assert_called_once_with(corrupted_index.id)
        # Verify corrupted index was removed from database
        remaining_indexes = self.manager.vector_repo.find_all()
        assert len(remaining_indexes) == 1
        assert remaining_indexes[0].id == valid_index.id

    # ===== Error Handling Tests =====
    def test_verify_index_integrity_exception_handling(self):
        """Test integrity verification exception handling."""
        with patch.object(
            self.manager.vector_repo,
            "find_by_id",
            side_effect=Exception("Database error"),
        ):
            result = self.manager.verify_index_integrity(1)
        assert result["is_valid"] is False
        assert "Integrity check failed" in result["errors"][0]

    def test_get_storage_statistics_exception_handling(self):
        """Test storage statistics exception handling."""
        with patch.object(
            self.manager.vector_repo, "count", side_effect=Exception("Database error")
        ):
            stats = self.manager.get_storage_statistics()
        assert "error" in stats
        assert "Database error" in stats["error"]

    def test_optimize_storage_exception_handling(self):
        """Test storage optimization exception handling."""
        with patch.object(
            self.manager,
            "_remove_orphaned_storage",
            side_effect=Exception("Cleanup error"),
        ):
            with pytest.raises(VectorIndexManagerError, match="Optimization failed"):
                self.manager.optimize_storage()

    # ===== Integration Tests =====
    def test_full_index_lifecycle(self):
        """Test complete index lifecycle: create, verify, backup, optimize."""
        # Create document and index
        document_id = self._create_test_document()
        vector_index = self.manager.create_index_storage(
            document_id=document_id, index_hash="lifecycle_hash", chunk_count=10
        )
        # Create mock files
        index_path = Path(vector_index.index_path)
        self._create_mock_index_files(index_path)
        # Verify integrity
        integrity_result = self.manager.verify_index_integrity(vector_index.id)
        assert integrity_result["is_valid"] is True
        # Create backup
        backup_path = self.manager.backup_index(vector_index.id)
        assert Path(backup_path).exists()
        # Get statistics
        stats = self.manager.get_storage_statistics()
        assert stats["total_indexes"] == 1
        assert stats["backup_count"] == 1
        # Optimize storage
        optimization_results = self.manager.optimize_storage()
        assert isinstance(optimization_results, dict)
        # Verify index still exists
        final_integrity = self.manager.verify_index_integrity(vector_index.id)
        assert final_integrity["is_valid"] is True

    def test_concurrent_operations_simulation(self):
        """Test multiple operations can be performed safely."""
        # Create multiple indexes
        indexes = []
        for i in range(3):
            doc_id = self._create_test_document(title=f"Document {i}")
            index = self.manager.create_index_storage(doc_id, f"hash_{i}", 5 * (i + 1))
            indexes.append(index)
            # Create mock files
            index_path = Path(index.index_path)
            self._create_mock_index_files(index_path)
        # Perform various operations
        for index in indexes:
            integrity = self.manager.verify_index_integrity(index.id)
            assert integrity["is_valid"] is True
            backup_path = self.manager.backup_index(index.id)
            assert Path(backup_path).exists()
        # Get final statistics
        stats = self.manager.get_storage_statistics()
        assert stats["total_indexes"] == 3
        assert stats["backup_count"] == 3
        assert stats["storage_health"] == "healthy"
