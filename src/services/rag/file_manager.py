"""
RAG File Manager Service

Handles all file system operations for RAG indexes including:
- File verification and integrity checking
- Index file copying and management
- Cleanup operations
- Path management and directory structure

This service encapsulates file system concerns and provides a clean
interface for other RAG services to interact with the filesystem.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RAGFileManagerError(Exception):
    """Base exception for RAG file manager errors."""

    pass


class RAGFileManager:
    """
    Manages file system operations for RAG vector indexes.

    Responsibilities:
    - Index file verification and validation
    - File copying and directory management
    - Cleanup operations and orphan removal
    - Path resolution and directory structure
    """

    def __init__(self, vector_storage_dir: str = "vector_indexes"):
        """
        Initialize RAG file manager.

        Args:
            vector_storage_dir: Base directory for vector index storage
        """
        self.vector_storage_dir = Path(vector_storage_dir)
        self.vector_storage_dir.mkdir(exist_ok=True)
        logger.info(f"RAG File Manager initialized with storage: {vector_storage_dir}")

    def verify_index_files(self, index_path: str) -> bool:
        """
        Verify that all required index files exist and are valid.

        Args:
            index_path: Path to vector index directory

        Returns:
            True if all required files exist and are valid
        """
        try:
            path = Path(index_path)
            if not path.exists() or not path.is_dir():
                logger.debug(
                    f"Index path does not exist or is not directory: {index_path}"
                )
                return False

            # Required LlamaIndex files
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]

            for file_name in required_files:
                file_path = path / file_name
                if not file_path.exists():
                    logger.debug(f"Missing required file: {file_name}")
                    return False

                # Check file is not empty
                if file_path.stat().st_size == 0:
                    logger.debug(f"Required file is empty: {file_name}")
                    return False

                # Validate JSON files can be parsed
                if file_name.endswith(".json"):
                    try:
                        with open(file_path) as f:
                            json.load(f)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.debug(
                            f"JSON file validation failed for {file_name}: {e}"
                        )
                        return False

            logger.debug(f"Index files verified successfully: {index_path}")
            return True

        except Exception as e:
            logger.error(f"Index file verification failed: {e}")
            return False

    def copy_index_files(self, source_path: Path, dest_path: Path) -> None:
        """
        Copy index files from source to destination directory.

        Args:
            source_path: Source directory containing index files
            dest_path: Destination directory for index files

        Raises:
            RAGFileManagerError: If copy operation fails
        """
        try:
            if not source_path.exists():
                raise RAGFileManagerError(f"Source path does not exist: {source_path}")

            if not dest_path.exists():
                dest_path.mkdir(parents=True, exist_ok=True)

            # Copy all files and subdirectories
            for item in source_path.iterdir():
                dest_item = dest_path / item.name

                if item.is_file():
                    shutil.copy2(item, dest_item)
                elif item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)

            logger.debug(
                f"Index files copied successfully: {source_path} → {dest_path}"
            )

        except Exception as e:
            error_msg = (
                f"Failed to copy index files from {source_path} to {dest_path}: {e}"
            )
            logger.error(error_msg)
            raise RAGFileManagerError(error_msg) from e

    def prepare_index_directory(
        self, index_path: Path, overwrite: bool = False
    ) -> None:
        """
        Prepare index directory for writing, optionally removing existing content.

        Args:
            index_path: Path to index directory
            overwrite: If True, remove existing directory content

        Raises:
            RAGFileManagerError: If directory preparation fails
        """
        try:
            if index_path.exists():
                if overwrite:
                    shutil.rmtree(index_path, ignore_errors=False)
                    logger.debug(f"Removed existing index directory: {index_path}")
                else:
                    raise RAGFileManagerError(
                        f"Index directory already exists: {index_path}"
                    )

            index_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Index directory prepared: {index_path}")

        except Exception as e:
            error_msg = f"Failed to prepare index directory {index_path}: {e}"
            logger.error(error_msg)
            raise RAGFileManagerError(error_msg) from e

    def cleanup_index_files(self, index_path: str) -> bool:
        """
        Clean up index files at the specified path.

        Args:
            index_path: Path to index directory to clean up

        Returns:
            True if cleanup was successful
        """
        try:
            path = Path(index_path)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                logger.debug(f"Index files cleaned up: {index_path}")
                return True
            else:
                logger.debug(
                    f"Index path does not exist, nothing to cleanup: {index_path}"
                )
                return True

        except Exception as e:
            logger.warning(f"Failed to cleanup index files at {index_path}: {e}")
            return False

    def get_chunk_count(self, index_path: str) -> int:
        """
        Extract chunk count from vector index metadata.

        Args:
            index_path: Path to vector index directory

        Returns:
            Number of chunks in the index, or 0 if cannot be determined
        """
        try:
            index_dir = Path(index_path)

            # Try metadata.json first (if it exists)
            metadata_path = index_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                    chunk_count = int(metadata.get("document_count", 0))
                    logger.debug(f"Chunk count from metadata: {chunk_count}")
                    return chunk_count

            # Fallback: estimate from vector store file
            vector_store_path = index_dir / "default__vector_store.json"
            if vector_store_path.exists():
                with open(vector_store_path) as f:
                    data = json.load(f)
                    chunk_count = len(data.get("embedding_dict", {}))
                    logger.debug(
                        f"Chunk count estimated from vector store: {chunk_count}"
                    )
                    return chunk_count

            logger.debug("No chunk count metadata found")
            return 0

        except Exception as e:
            logger.warning(f"Could not determine chunk count for {index_path}: {e}")
            return 0

    def generate_index_path(self, document_id: int, content_hash: str) -> Path:
        """
        Generate standardized index path for a document.

        Args:
            document_id: Database document ID
            content_hash: Content hash for uniqueness

        Returns:
            Path object for the index directory
        """
        hash_prefix = content_hash[:8] if content_hash else "unknown"
        directory_name = f"doc_{document_id}_{hash_prefix}"
        return self.vector_storage_dir / directory_name

    def find_orphaned_directories(self, valid_index_paths: list[str]) -> list[Path]:
        """
        Find index directories that don't correspond to valid database records.

        Args:
            valid_index_paths: List of valid index paths from database

        Returns:
            List of orphaned directory paths
        """
        orphaned_dirs: list[Any] = []

        try:
            if not self.vector_storage_dir.exists():
                return orphaned_dirs

            valid_paths_set = {Path(path) for path in valid_index_paths}

            for item in self.vector_storage_dir.iterdir():
                if (
                    item.is_dir()
                    and item.name.startswith("doc_")
                    and item not in valid_paths_set
                ):
                    orphaned_dirs.append(item)
                    logger.debug(f"Found orphaned directory: {item}")

        except Exception as e:
            logger.error(f"Failed to find orphaned directories: {e}")

        return orphaned_dirs

    def cleanup_orphaned_directories(self, orphaned_dirs: list[Path]) -> int:
        """
        Remove orphaned index directories.

        Args:
            orphaned_dirs: List of orphaned directory paths to remove

        Returns:
            Number of directories successfully removed
        """
        cleaned_count = 0

        for orphaned_dir in orphaned_dirs:
            try:
                shutil.rmtree(orphaned_dir, ignore_errors=False)
                logger.info(f"Removed orphaned index directory: {orphaned_dir}")
                cleaned_count += 1

            except Exception as e:
                logger.warning(
                    f"Failed to remove orphaned directory {orphaned_dir}: {e}"
                )

        return cleaned_count

    def get_storage_statistics(self) -> dict[str, Any]:
        """
        Get storage statistics for the vector index storage.

        Returns:
            Dictionary with storage statistics
        """
        stats = {
            "storage_directory": str(self.vector_storage_dir),
            "total_indexes": 0,
            "total_size_bytes": 0,
            "directory_exists": False,
        }

        try:
            if self.vector_storage_dir.exists():
                stats["directory_exists"] = True

                index_dirs = [
                    d for d in self.vector_storage_dir.iterdir() if d.is_dir()
                ]
                stats["total_indexes"] = len(index_dirs)

                # Calculate total size
                total_size = 0
                for index_dir in index_dirs:
                    for file_path in index_dir.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size

                stats["total_size_bytes"] = total_size
                stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)

        except Exception as e:
            logger.error(f"Failed to get storage statistics: {e}")
            stats["error"] = str(e)

        return stats

    def is_accessible(self) -> bool:
        """
        Check if the vector storage directory is accessible for read/write operations.

        Returns:
            True if storage is accessible
        """
        try:
            return (
                self.vector_storage_dir.exists()
                and self.vector_storage_dir.is_dir()
                and self.vector_storage_dir.stat().st_mode  # Check permissions
            )
        except Exception as e:
            logger.error(f"Vector storage accessibility check failed: {e}")
            return False
