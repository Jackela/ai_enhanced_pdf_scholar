"""
Vector Index Persistence Manager
This module provides comprehensive vector index persistence management,
including index lifecycle, integrity verification, and optimization.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.models import VectorIndexModel
from src.repositories.vector_repository import VectorIndexRepository

logger = logging.getLogger(__name__)


class VectorIndexManagerError(Exception):
    """Base exception for vector index manager errors."""

    pass


class IndexCorruptionError(VectorIndexManagerError):
    """Raised when index corruption is detected."""

    pass


class VectorIndexManager:
    """
    {
        "name": "VectorIndexManager",
        "version": "1.0.0",
        "description": "Comprehensive vector index persistence and lifecycle management.",
        "dependencies": ["DatabaseConnection", "VectorIndexRepository", "ContentHashService"],
        "interface": {
            "inputs": [
                {"name": "db_connection", "type": "DatabaseConnection"},
                {"name": "storage_base_dir", "type": "string"}
            ],
            "outputs": "Vector index persistence operations and management"
        }
    }
    Manages the complete lifecycle of vector indexes including creation, validation,
    optimization, and cleanup. Provides integrity verification and performance monitoring.
    """

    def __init__(
        self,
        db_connection: DatabaseConnection,
        storage_base_dir: str = "vector_indexes",
    ) -> None:
        """
        Initialize vector index manager.
        Args:
            db_connection: Database connection instance
            storage_base_dir: Base directory for vector index storage
        """
        self.db = db_connection
        self.vector_repo = VectorIndexRepository(db_connection)
        # Storage configuration
        self.storage_base_dir = Path(storage_base_dir)
        self.storage_base_dir.mkdir(exist_ok=True)
        # Create subdirectories for organization
        self.active_dir = self.storage_base_dir / "active"
        self.backup_dir = self.storage_base_dir / "backup"
        self.temp_dir = self.storage_base_dir / "temp"
        for directory in [self.active_dir, self.backup_dir, self.temp_dir]:
            directory.mkdir(exist_ok=True)
        logger.info(
            f"Vector index manager initialized with storage: {storage_base_dir}"
        )

    def create_index_storage(
        self, document_id: int, index_hash: str, chunk_count: int = 0
    ) -> VectorIndexModel:
        """
        Create persistent storage for a vector index.
        Args:
            document_id: Document ID this index belongs to
            index_hash: Content hash for integrity verification
            chunk_count: Number of chunks in the index
        Returns:
            Created vector index model
        Raises:
            VectorIndexManagerError: If creation fails
        """
        try:
            logger.info(f"Creating index storage for document {document_id}")
            # Generate unique storage path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            index_dir_name = f"doc_{document_id}_{index_hash[:8]}_{timestamp}"
            index_path = self.active_dir / index_dir_name
            # Ensure directory doesn't exist
            if index_path.exists():
                logger.warning(
                    f"Index path already exists, adding suffix: {index_path}"
                )
                index_path = self.active_dir / f"{index_dir_name}_alt"
            # Create index directory
            index_path.mkdir(exist_ok=True)
            # Create index metadata
            metadata = {
                "document_id": document_id,
                "index_hash": index_hash,
                "chunk_count": chunk_count,
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "format": "llamaindex",
            }
            # Save metadata
            metadata_path = index_path / "index_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            # Create vector index model
            vector_index = VectorIndexModel(
                document_id=document_id,
                index_path=str(index_path),
                index_hash=index_hash,
                chunk_count=chunk_count,
            )
            # Save to database
            saved_index = self.vector_repo.create(vector_index)
            logger.info(f"Index storage created: {saved_index.id} at {index_path}")
            return saved_index
        except Exception as e:
            logger.error(
                f"Failed to create index storage for document {document_id}: {e}"
            )
            raise VectorIndexManagerError(f"Index storage creation failed: {e}") from e

    def move_index_to_storage(
        self, vector_index: VectorIndexModel, source_path: Path
    ) -> bool:
        """
        Move index files from temporary location to persistent storage.
        Args:
            vector_index: Vector index model
            source_path: Source path containing index files
        Returns:
            True if move successful
        Raises:
            VectorIndexManagerError: If move fails
        """
        try:
            dest_path = Path(vector_index.index_path)
            logger.info(f"Moving index files from {source_path} to {dest_path}")
            # Verify source exists and has required files
            if not source_path.exists():
                raise VectorIndexManagerError(
                    f"Source path does not exist: {source_path}"
                )
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]
            missing_files = [
                f for f in required_files if not (source_path / f).exists()
            ]
            if missing_files:
                raise VectorIndexManagerError(
                    f"Missing required files: {missing_files}"
                )
            # Ensure destination directory exists
            dest_path.mkdir(exist_ok=True)
            # Copy all files from source to destination
            for item in source_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_path / item.name)
                elif item.is_dir():
                    shutil.copytree(item, dest_path / item.name, dirs_exist_ok=True)
            # Verify integrity after copy
            if not self.verify_index_integrity(vector_index.id):
                raise VectorIndexManagerError(
                    "Index integrity verification failed after move"
                )
            # Update chunk count if metadata available
            chunk_count = self._extract_chunk_count(dest_path)
            if chunk_count > 0 and chunk_count != vector_index.chunk_count:
                vector_index.chunk_count = chunk_count
                self.vector_repo.update(vector_index)
            logger.info(f"Index files moved successfully to {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to move index files: {e}")
            raise VectorIndexManagerError(f"Index move failed: {e}") from e

    def verify_index_integrity(self, vector_index_id: int) -> dict[str, Any]:
        """
        Verify the integrity of a vector index.
        Args:
            vector_index_id: Vector index ID to verify
        Returns:
            Dictionary with integrity check results
        """
        try:
            result = {
                "index_id": vector_index_id,
                "is_valid": False,
                "errors": [],
                "warnings": [],
                "file_checks": {},
                "metadata_check": False,
                "size_info": {},
            }
            # Get vector index
            vector_index = self.vector_repo.find_by_id(vector_index_id)
            if not vector_index:
                result["errors"].append("Vector index not found in database")
                return result
            index_path = Path(vector_index.index_path)
            # Check if directory exists
            if not index_path.exists():
                result["errors"].append(f"Index directory does not exist: {index_path}")
                return result
            # Check required files
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]
            for file_name in required_files:
                file_path = index_path / file_name
                file_check = {
                    "exists": file_path.exists(),
                    "readable": False,
                    "size": 0,
                    "valid_json": False,
                }
                if file_check["exists"]:
                    try:
                        file_check["size"] = file_path.stat().st_size
                        file_check["readable"] = True
                        # Verify JSON structure
                        with open(file_path) as f:
                            json.load(f)
                        file_check["valid_json"] = True
                    except Exception as e:
                        result["errors"].append(f"File {file_name} is corrupted: {e}")
                        file_check["valid_json"] = False
                else:
                    result["errors"].append(f"Required file missing: {file_name}")
                result["file_checks"][file_name] = file_check
            # Check metadata file
            metadata_path = index_path / "index_metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    result["metadata_check"] = True
                    # Verify metadata consistency
                    if metadata.get("document_id") != vector_index.document_id:
                        result["warnings"].append("Metadata document_id mismatch")
                except Exception as e:
                    result["warnings"].append(f"Metadata file corrupted: {e}")
            else:
                result["warnings"].append("Index metadata file missing")
            # Calculate directory size
            total_size = sum(
                f.stat().st_size for f in index_path.rglob("*") if f.is_file()
            )
            result["size_info"] = {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": len(list(index_path.rglob("*"))),
            }
            # Overall validity
            all_files_valid = all(
                check["exists"] and check["valid_json"]
                for check in result["file_checks"].values()
            )
            result["is_valid"] = all_files_valid and len(result["errors"]) == 0
            logger.debug(
                f"Index integrity check completed for {vector_index_id}: {'VALID' if result['is_valid'] else 'INVALID'}"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to verify index integrity for {vector_index_id}: {e}")
            return {
                "index_id": vector_index_id,
                "is_valid": False,
                "errors": [f"Integrity check failed: {e}"],
            }

    def backup_index(self, vector_index_id: int) -> str:
        """
        Create a backup of a vector index.
        Args:
            vector_index_id: Vector index ID to backup
        Returns:
            Path to backup directory
        Raises:
            VectorIndexManagerError: If backup fails
        """
        try:
            vector_index = self.vector_repo.find_by_id(vector_index_id)
            if not vector_index:
                raise VectorIndexManagerError(
                    f"Vector index not found: {vector_index_id}"
                )
            source_path = Path(vector_index.index_path)
            if not source_path.exists():
                raise VectorIndexManagerError(
                    f"Index path does not exist: {source_path}"
                )
            # Create backup directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_doc_{vector_index.document_id}_{timestamp}"
            backup_path = self.backup_dir / backup_name
            # Copy index to backup
            shutil.copytree(source_path, backup_path)
            # Create backup metadata
            backup_metadata = {
                "original_index_id": vector_index_id,
                "document_id": vector_index.document_id,
                "backup_created_at": datetime.now().isoformat(),
                "original_path": str(source_path),
                "index_hash": vector_index.index_hash,
            }
            with open(backup_path / "backup_metadata.json", "w") as f:
                json.dump(backup_metadata, f, indent=2)
            logger.info(f"Index backup created: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to backup index {vector_index_id}: {e}")
            raise VectorIndexManagerError(f"Index backup failed: {e}") from e

    def optimize_storage(self) -> dict[str, int]:
        """
        Optimize vector index storage by removing duplicates and cleaning up.
        Returns:
            Dictionary with optimization results
        """
        try:
            logger.info("Starting vector index storage optimization")
            results = {
                "orphaned_removed": 0,
                "duplicates_removed": 0,
                "corrupted_removed": 0,
                "space_freed_mb": 0,
            }
            # Remove orphaned indexes (no database record)
            orphaned_removed = self._remove_orphaned_storage()
            results["orphaned_removed"] = orphaned_removed
            # Remove corrupted indexes
            corrupted_removed = self._remove_corrupted_indexes()
            results["corrupted_removed"] = corrupted_removed
            # Clean up temporary files
            self._cleanup_temp_files()
            # Remove old backups (older than 30 days)
            self._cleanup_old_backups(days=30)
            logger.info(f"Storage optimization completed: {results}")
            return results
        except Exception as e:
            logger.error(f"Storage optimization failed: {e}")
            raise VectorIndexManagerError(f"Optimization failed: {e}") from e

    def get_storage_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive storage statistics.
        Returns:
            Dictionary with storage statistics
        """
        try:
            stats = {
                "storage_base_dir": str(self.storage_base_dir),
                "total_indexes": 0,
                "active_indexes": 0,
                "backup_count": 0,
                "total_size_mb": 0,
                "average_index_size_mb": 0,
                "largest_index_mb": 0,
                "storage_health": "unknown",
            }
            # Count active indexes
            if self.active_dir.exists():
                active_indexes = list(self.active_dir.iterdir())
                stats["active_indexes"] = len([d for d in active_indexes if d.is_dir()])
            # Count backups
            if self.backup_dir.exists():
                backup_dirs = list(self.backup_dir.iterdir())
                stats["backup_count"] = len([d for d in backup_dirs if d.is_dir()])
            # Calculate total size
            total_size = 0
            index_sizes = []
            for index_dir in self.active_dir.iterdir():
                if index_dir.is_dir():
                    size = sum(
                        f.stat().st_size for f in index_dir.rglob("*") if f.is_file()
                    )
                    total_size += size
                    index_sizes.append(size)
            stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
            stats["total_indexes"] = len(index_sizes)
            if index_sizes:
                stats["average_index_size_mb"] = round(
                    sum(index_sizes) / len(index_sizes) / (1024 * 1024), 2
                )
                stats["largest_index_mb"] = round(max(index_sizes) / (1024 * 1024), 2)
            # Storage health assessment
            db_index_count = self.vector_repo.count()
            if stats["active_indexes"] == db_index_count:
                stats["storage_health"] = "healthy"
            elif stats["active_indexes"] > db_index_count:
                stats["storage_health"] = "orphaned_files"
            else:
                stats["storage_health"] = "missing_files"
            return stats
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {e}")
            return {"error": str(e)}

    # Private helper methods
    def _extract_chunk_count(self, index_path: Path) -> int:
        """Extract chunk count from index files."""
        try:
            # Try metadata first
            metadata_path = index_path / "index_metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                    return metadata.get("chunk_count", 0)
            # Fallback to vector store
            vector_store_path = index_path / "default__vector_store.json"
            if vector_store_path.exists():
                with open(vector_store_path) as f:
                    data = json.load(f)
                    return len(data.get("embedding_dict", {}))
            return 0
        except Exception as _:
            logger.warning(f"Could not extract chunk count from {index_path}")
            return 0

    def _remove_orphaned_storage(self) -> int:
        """Remove storage directories with no database record."""
        try:
            removed_count = 0
            # Get all index IDs from database
            db_paths = {idx.index_path for idx in self.vector_repo.find_all()}
            # Check each directory in active storage
            for index_dir in self.active_dir.iterdir():
                if index_dir.is_dir() and str(index_dir) not in db_paths:
                    logger.info(f"Removing orphaned storage directory: {index_dir}")
                    shutil.rmtree(index_dir, ignore_errors=True)
                    removed_count += 1
            return removed_count
        except Exception as e:
            logger.error(f"Failed to remove orphaned storage: {e}")
            return 0

    def _remove_corrupted_indexes(self) -> int:
        """Remove corrupted index storage."""
        try:
            removed_count = 0
            # Check all indexes in database
            for vector_index in self.vector_repo.find_all():
                integrity = self.verify_index_integrity(vector_index.id)
                if not integrity["is_valid"] and "does not exist" not in str(
                    integrity.get("errors", [])
                ):
                    logger.info(f"Removing corrupted index: {vector_index.id}")
                    # Backup before removal
                    try:
                        self.backup_index(vector_index.id)
                    except Exception as e:
                        logger.warning(
                            f"Could not backup corrupted index {vector_index.id}: {e}"
                        )
                    # Remove storage
                    index_path = Path(vector_index.index_path)
                    if index_path.exists():
                        shutil.rmtree(index_path, ignore_errors=True)
                    # Remove database record
                    self.vector_repo.delete(vector_index.id)
                    removed_count += 1
            return removed_count
        except Exception as e:
            logger.error(f"Failed to remove corrupted indexes: {e}")
            return 0

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files."""
        try:
            if self.temp_dir.exists():
                for item in self.temp_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Could not cleanup temp files: {e}")

    def _cleanup_old_backups(self, days: int = 30) -> None:
        """Clean up backups older than specified days."""
        try:
            import time

            cutoff_time = time.time() - (days * 24 * 60 * 60)
            if self.backup_dir.exists():
                for backup_dir in self.backup_dir.iterdir():
                    if backup_dir.is_dir() and backup_dir.stat().st_mtime < cutoff_time:
                        logger.info(f"Removing old backup: {backup_dir}")
                        shutil.rmtree(backup_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Could not cleanup old backups: {e}")
