"""
RAGFileManager Service Tests

Tests for the specialized service responsible for managing RAG-related file operations,
cleanup, storage optimization, and file system interactions.
"""

import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.rag.exceptions import RAGFileError, RAGStorageError
from src.services.rag.file_manager import RAGFileManager


class TestRAGFileManager:
    """Test suite for RAGFileManager file operations and storage management."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test operations."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_storage_monitor(self):
        """Mock storage monitoring service."""
        mock = Mock()
        mock.get_disk_usage = Mock(return_value={
            "total": 1000 * 1024 * 1024 * 1024,  # 1TB
            "used": 500 * 1024 * 1024 * 1024,    # 500GB
            "free": 500 * 1024 * 1024 * 1024,    # 500GB
            "percent_used": 50.0
        })
        mock.check_storage_health = AsyncMock(return_value={"status": "healthy"})
        return mock

    @pytest.fixture
    def mock_backup_service(self):
        """Mock backup service for file operations."""
        mock = Mock()
        mock.create_backup = AsyncMock(return_value="/backup/path/backup_123.tar.gz")
        mock.restore_from_backup = AsyncMock(return_value=True)
        mock.verify_backup = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def file_manager(self, temp_directory, mock_storage_monitor, mock_backup_service):
        """Create RAGFileManager with mocked dependencies."""
        return RAGFileManager(
            base_storage_path=temp_directory,
            storage_monitor=mock_storage_monitor,
            backup_service=mock_backup_service
        )

    def test_file_manager_initialization(self, file_manager, temp_directory):
        """Test RAGFileManager initializes with correct configuration."""
        assert file_manager.base_storage_path == temp_directory
        assert file_manager.storage_monitor is not None
        assert file_manager.backup_service is not None
        assert file_manager._initialized is True
        assert file_manager._operation_history == []

    def test_ensure_directories_creation(self, file_manager):
        """Test directory structure creation and validation."""
        # Given
        required_dirs = ["indexes", "temp", "backups", "logs"]

        # When
        result = file_manager.ensure_directories(required_dirs)

        # Then
        assert result is True
        for dir_name in required_dirs:
            assert (file_manager.base_storage_path / dir_name).exists()
            assert (file_manager.base_storage_path / dir_name).is_dir()

    def test_ensure_directories_with_permissions(self, file_manager):
        """Test directory creation with specific permissions."""
        # Given
        required_dirs = ["secure_indexes"]
        permissions = 0o755

        # When
        result = file_manager.ensure_directories(required_dirs, permissions=permissions)

        # Then
        assert result is True
        created_dir = file_manager.base_storage_path / "secure_indexes"
        assert created_dir.exists()
        # Note: Permission checking is platform-dependent in tests

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_by_document(self, file_manager):
        """Test cleanup of temporary files for specific document."""
        # Given - create temporary files
        temp_dir = file_manager.base_storage_path / "temp"
        temp_dir.mkdir(exist_ok=True)

        # Create files for document 1
        (temp_dir / "doc_1_temp_chunk_1.txt").write_text("temp data")
        (temp_dir / "doc_1_temp_chunk_2.txt").write_text("temp data")
        (temp_dir / "doc_1_processing.log").write_text("processing log")

        # Create files for other documents
        (temp_dir / "doc_2_temp_chunk_1.txt").write_text("other doc data")

        # When
        cleaned_count = await file_manager.cleanup_temp_files(document_id=1)

        # Then
        assert cleaned_count == 3
        assert not (temp_dir / "doc_1_temp_chunk_1.txt").exists()
        assert not (temp_dir / "doc_1_temp_chunk_2.txt").exists()
        assert not (temp_dir / "doc_1_processing.log").exists()
        assert (temp_dir / "doc_2_temp_chunk_1.txt").exists()  # Should remain

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_all(self, file_manager):
        """Test cleanup of all temporary files."""
        # Given - create various temporary files
        temp_dir = file_manager.base_storage_path / "temp"
        temp_dir.mkdir(exist_ok=True)

        temp_files = [
            "temp_file_1.txt",
            "temp_file_2.log",
            "processing_temp.json",
            "chunk_temp_123.txt"
        ]

        for filename in temp_files:
            (temp_dir / filename).write_text("temp content")

        # When
        cleaned_count = await file_manager.cleanup_temp_files()

        # Then
        assert cleaned_count == len(temp_files)
        for filename in temp_files:
            assert not (temp_dir / filename).exists()

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files(self, file_manager):
        """Test cleanup of orphaned files without parent documents."""
        # Given - create orphaned index files
        indexes_dir = file_manager.base_storage_path / "indexes"
        indexes_dir.mkdir(exist_ok=True)

        # Valid document indexes
        valid_doc_dir = indexes_dir / "document_1"
        valid_doc_dir.mkdir()
        (valid_doc_dir / "vectors.pkl").write_bytes(b"vector data")
        (valid_doc_dir / "metadata.json").write_text('{"doc_id": 1}')

        # Orphaned indexes (document no longer exists)
        orphaned_dir = indexes_dir / "document_999"
        orphaned_dir.mkdir()
        (orphaned_dir / "vectors.pkl").write_bytes(b"orphaned vectors")
        (orphaned_dir / "metadata.json").write_text('{"doc_id": 999}')

        # Mock document existence check
        existing_document_ids = [1]  # Only document 1 exists
        file_manager._get_existing_document_ids = Mock(return_value=existing_document_ids)

        # When
        orphaned_count = await file_manager.cleanup_orphaned_files()

        # Then
        assert orphaned_count == 1
        assert valid_doc_dir.exists()  # Valid document preserved
        assert not orphaned_dir.exists()  # Orphaned document removed

    def test_get_storage_stats_comprehensive(self, file_manager):
        """Test comprehensive storage statistics collection."""
        # Given - create test files with known sizes
        test_dirs = ["indexes", "temp", "backups"]
        for dir_name in test_dirs:
            dir_path = file_manager.base_storage_path / dir_name
            dir_path.mkdir(exist_ok=True)

            # Create files with different sizes
            (dir_path / "file1.txt").write_text("A" * 1000)  # 1KB
            (dir_path / "file2.txt").write_text("B" * 2000)  # 2KB

        # When
        stats = file_manager.get_storage_stats()

        # Then
        assert "total_size" in stats
        assert "file_count" in stats
        assert "directory_breakdown" in stats
        assert stats["total_size"] > 0
        assert stats["file_count"] == 6  # 2 files per directory * 3 directories

        for dir_name in test_dirs:
            assert dir_name in stats["directory_breakdown"]
            assert stats["directory_breakdown"][dir_name]["size"] > 0

    def test_get_storage_stats_by_document(self, file_manager):
        """Test storage statistics for specific document."""
        # Given - create document-specific files
        doc_id = 1
        indexes_dir = file_manager.base_storage_path / "indexes"
        doc_dir = indexes_dir / f"document_{doc_id}"
        doc_dir.mkdir(parents=True)

        # Create index files
        (doc_dir / "vectors.pkl").write_bytes(b"X" * 5000)  # 5KB
        (doc_dir / "metadata.json").write_text("Y" * 1000)  # ~1KB

        # When
        doc_stats = file_manager.get_storage_stats(document_id=doc_id)

        # Then
        assert doc_stats["document_id"] == doc_id
        assert doc_stats["total_size"] > 5000
        assert doc_stats["file_count"] == 2
        assert "files" in doc_stats

    @pytest.mark.asyncio
    async def test_move_files_between_locations(self, file_manager):
        """Test moving files between different storage locations."""
        # Given - create source files
        source_dir = file_manager.base_storage_path / "temp"
        target_dir = file_manager.base_storage_path / "indexes" / "document_1"
        source_dir.mkdir(exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        source_files = [
            source_dir / "vectors_temp.pkl",
            source_dir / "metadata_temp.json"
        ]

        for file_path in source_files:
            file_path.write_text("test content")

        target_files = [
            target_dir / "vectors.pkl",
            target_dir / "metadata.json"
        ]

        file_moves = list(zip(source_files, target_files, strict=False))

        # When
        move_result = await file_manager.move_files(file_moves)

        # Then
        assert move_result["success"] is True
        assert move_result["files_moved"] == 2

        # Verify files moved
        for source_file in source_files:
            assert not source_file.exists()

        for target_file in target_files:
            assert target_file.exists()
            assert target_file.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_copy_files_with_verification(self, file_manager):
        """Test file copying with integrity verification."""
        # Given - create source files
        source_dir = file_manager.base_storage_path / "source"
        target_dir = file_manager.base_storage_path / "backup"
        source_dir.mkdir(exist_ok=True)
        target_dir.mkdir(exist_ok=True)

        source_file = source_dir / "important_data.pkl"
        source_file.write_bytes(b"important data content")

        target_file = target_dir / "important_data_backup.pkl"

        # When
        copy_result = await file_manager.copy_file_with_verification(
            source_file, target_file
        )

        # Then
        assert copy_result["success"] is True
        assert copy_result["verification_passed"] is True
        assert target_file.exists()
        assert source_file.read_bytes() == target_file.read_bytes()

    @pytest.mark.asyncio
    async def test_batch_file_operations(self, file_manager):
        """Test batch processing of multiple file operations."""
        # Given - create multiple files for batch operations
        batch_dir = file_manager.base_storage_path / "batch_test"
        batch_dir.mkdir(exist_ok=True)

        files_to_create = [
            ("file1.txt", "content1"),
            ("file2.txt", "content2"),
            ("file3.txt", "content3"),
            ("file4.txt", "content4"),
            ("file5.txt", "content5")
        ]

        for filename, content in files_to_create:
            (batch_dir / filename).write_text(content)

        # When - batch delete operation
        file_paths = [batch_dir / filename for filename, _ in files_to_create]
        batch_result = await file_manager.batch_delete_files(file_paths)

        # Then
        assert batch_result["success"] is True
        assert batch_result["files_deleted"] == 5
        assert batch_result["errors"] == []

        # Verify all files deleted
        for file_path in file_paths:
            assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_storage_optimization(self, file_manager):
        """Test storage space optimization procedures."""
        # Given - create files that can be optimized
        indexes_dir = file_manager.base_storage_path / "indexes"
        indexes_dir.mkdir(exist_ok=True)

        # Create large uncompressed files
        large_file = indexes_dir / "large_vectors.pkl"
        large_file.write_bytes(b"X" * 10000)  # 10KB uncompressed

        # Create duplicate files
        duplicate1 = indexes_dir / "vectors_copy1.pkl"
        duplicate2 = indexes_dir / "vectors_copy2.pkl"
        duplicate_content = b"duplicate content" * 100
        duplicate1.write_bytes(duplicate_content)
        duplicate2.write_bytes(duplicate_content)

        # When
        optimization_result = await file_manager.optimize_storage()

        # Then
        assert optimization_result["space_saved"] > 0
        assert "compression_applied" in optimization_result
        assert "duplicates_removed" in optimization_result

    def test_file_integrity_verification(self, file_manager):
        """Test file integrity checking with checksums."""
        # Given - create test file
        test_file = file_manager.base_storage_path / "test_integrity.pkl"
        test_content = b"test content for integrity check"
        test_file.write_bytes(test_content)

        # When - verify integrity immediately (should pass)
        integrity_result = file_manager.verify_file_integrity(test_file)

        # Then
        assert integrity_result["valid"] is True
        assert "checksum" in integrity_result
        assert "file_size" in integrity_result

        # When - corrupt the file and verify again
        test_file.write_bytes(b"corrupted content")
        corrupted_result = file_manager.verify_file_integrity(
            test_file, expected_checksum=integrity_result["checksum"]
        )

        # Then
        assert corrupted_result["valid"] is False
        assert "checksum_mismatch" in corrupted_result

    @pytest.mark.asyncio
    async def test_automated_cleanup_schedule(self, file_manager):
        """Test automated cleanup scheduling and execution."""
        # Given - create old temporary files
        temp_dir = file_manager.base_storage_path / "temp"
        temp_dir.mkdir(exist_ok=True)

        old_file = temp_dir / "old_temp.txt"
        old_file.write_text("old content")

        # Artificially age the file
        old_time = time.time() - (24 * 60 * 60 * 7)  # 7 days ago
        os.utime(old_file, (old_time, old_time))

        recent_file = temp_dir / "recent_temp.txt"
        recent_file.write_text("recent content")

        # When
        cleanup_result = await file_manager.run_scheduled_cleanup(
            max_age_days=3
        )

        # Then
        assert cleanup_result["files_cleaned"] == 1
        assert not old_file.exists()  # Old file removed
        assert recent_file.exists()   # Recent file preserved

    @pytest.mark.asyncio
    async def test_storage_quota_management(self, file_manager):
        """Test storage quota enforcement and management."""
        # Given - mock storage monitor to report near quota
        file_manager.storage_monitor.get_disk_usage.return_value = {
            "total": 1000 * 1024 * 1024,      # 1GB
            "used": 900 * 1024 * 1024,       # 900MB (90% used)
            "free": 100 * 1024 * 1024,       # 100MB
            "percent_used": 90.0
        }

        # When
        quota_status = file_manager.check_storage_quota()

        # Then
        assert quota_status["quota_exceeded"] is False
        assert quota_status["quota_warning"] is True
        assert quota_status["percent_used"] == 90.0
        assert "cleanup_recommended" in quota_status

    @pytest.mark.asyncio
    async def test_file_backup_and_restore(self, file_manager):
        """Test file backup and restoration procedures."""
        # Given - create important files
        important_dir = file_manager.base_storage_path / "indexes" / "document_1"
        important_dir.mkdir(parents=True, exist_ok=True)

        important_files = {
            "vectors.pkl": b"vector data content",
            "metadata.json": '{"important": "metadata"}',
            "config.yaml": "configuration: settings"
        }

        for filename, content in important_files.items():
            file_path = important_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)

        # When - create backup
        backup_result = await file_manager.create_backup(
            source_path=important_dir,
            backup_name="document_1_backup"
        )

        # Then
        assert backup_result["success"] is True
        assert "backup_path" in backup_result

        # When - simulate data loss and restore
        shutil.rmtree(important_dir)  # Simulate data loss
        assert not important_dir.exists()

        restore_result = await file_manager.restore_from_backup(
            backup_path=backup_result["backup_path"],
            restore_path=important_dir
        )

        # Then
        assert restore_result["success"] is True
        assert important_dir.exists()

        # Verify all files restored correctly
        for filename, expected_content in important_files.items():
            file_path = important_dir / filename
            assert file_path.exists()

            if isinstance(expected_content, bytes):
                assert file_path.read_bytes() == expected_content
            else:
                assert file_path.read_text() == expected_content

    def test_file_operation_audit_logging(self, file_manager):
        """Test audit logging of file operations."""
        # Given - perform various file operations
        test_file = file_manager.base_storage_path / "audit_test.txt"
        test_file.write_text("audit content")

        # When - perform operations that should be logged
        file_manager._log_operation("create", str(test_file), {"size": 100})
        file_manager._log_operation("delete", str(test_file), {"reason": "cleanup"})

        # Then
        assert len(file_manager._operation_history) == 2

        create_log = file_manager._operation_history[0]
        assert create_log["operation"] == "create"
        assert create_log["file_path"] == str(test_file)
        assert "timestamp" in create_log

        delete_log = file_manager._operation_history[1]
        assert delete_log["operation"] == "delete"
        assert delete_log["metadata"]["reason"] == "cleanup"

    def test_concurrent_file_operations_safety(self, file_manager):
        """Test thread-safety of concurrent file operations."""
        import concurrent.futures

        # Given - multiple files to process concurrently
        concurrent_dir = file_manager.base_storage_path / "concurrent_test"
        concurrent_dir.mkdir(exist_ok=True)

        # Create files to process
        file_count = 10
        for i in range(file_count):
            (concurrent_dir / f"file_{i}.txt").write_text(f"content_{i}")

        # When - process files concurrently
        def process_file(file_index):
            file_path = concurrent_dir / f"file_{file_index}.txt"
            # Simulate file operations
            content = file_path.read_text()
            file_path.write_text(content.upper())
            return f"processed_{file_index}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_file, range(file_count)))

        # Then
        assert len(results) == file_count

        # Verify all files processed correctly
        for i in range(file_count):
            file_path = concurrent_dir / f"file_{i}.txt"
            assert file_path.read_text() == f"CONTENT_{i}"


class TestRAGFileManagerErrorHandling:
    """Test error handling and edge cases for RAGFileManager."""

    @pytest.fixture
    def failing_file_manager(self, temp_directory):
        """Create file manager with failing dependencies."""
        mock_storage_monitor = Mock()
        mock_storage_monitor.get_disk_usage.side_effect = Exception("Storage monitor failed")

        mock_backup_service = Mock()
        mock_backup_service.create_backup.side_effect = Exception("Backup service failed")

        return RAGFileManager(
            base_storage_path=temp_directory,
            storage_monitor=mock_storage_monitor,
            backup_service=mock_backup_service
        )

    def test_permission_denied_handling(self, failing_file_manager):
        """Test handling of permission denied errors."""
        # Given - mock permission error
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("Access denied")):
            # When/Then
            with pytest.raises(RAGFileError) as exc_info:
                failing_file_manager.ensure_directories(["restricted_dir"])

            assert "Permission denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disk_full_handling(self, failing_file_manager):
        """Test handling of disk space exhaustion."""
        # Given - create test file and mock disk full error
        test_file = failing_file_manager.base_storage_path / "test.txt"
        test_file.write_text("test")

        with patch('pathlib.Path.write_text', side_effect=OSError("No space left on device")):
            # When/Then
            with pytest.raises(RAGStorageError) as exc_info:
                await failing_file_manager.copy_file_with_verification(
                    test_file, failing_file_manager.base_storage_path / "copy.txt"
                )

            assert "No space left on device" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self, file_manager):
        """Test handling of corrupted files during operations."""
        # Given - create corrupted file
        corrupted_file = file_manager.base_storage_path / "corrupted.pkl"
        corrupted_file.write_bytes(b"corrupted pickle data")

        # When - attempt to verify corrupted file
        with patch('pickle.load', side_effect=Exception("Pickle corruption")):
            integrity_result = file_manager.verify_file_integrity(corrupted_file)

        # Then
        assert integrity_result["valid"] is False
        assert "corruption_detected" in integrity_result

    @pytest.mark.asyncio
    async def test_network_storage_failure_handling(self, file_manager):
        """Test handling of network storage failures."""
        # Given - simulate network storage failure
        with patch('shutil.copy2', side_effect=OSError("Network path not found")):
            source = file_manager.base_storage_path / "source.txt"
            target = file_manager.base_storage_path / "target.txt"
            source.write_text("content")

            # When/Then
            with pytest.raises(RAGFileError) as exc_info:
                await file_manager.copy_file_with_verification(source, target)

            assert "Network path not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cleanup_failure_recovery(self, file_manager):
        """Test recovery from cleanup operation failures."""
        # Given - create files and mock partial cleanup failure
        temp_dir = file_manager.base_storage_path / "temp"
        temp_dir.mkdir(exist_ok=True)

        files = []
        for i in range(5):
            file_path = temp_dir / f"temp_{i}.txt"
            file_path.write_text(f"content {i}")
            files.append(file_path)

        # Mock failure on third file
        original_unlink = Path.unlink
        def failing_unlink(self):
            if "temp_2.txt" in str(self):
                raise PermissionError("File in use")
            return original_unlink(self)

        with patch.object(Path, 'unlink', failing_unlink):
            # When
            cleanup_result = await file_manager.cleanup_temp_files()

        # Then - should continue with other files despite failure
        assert cleanup_result < 5  # Not all files cleaned due to error
        assert (temp_dir / "temp_2.txt").exists()  # Failed file still exists
