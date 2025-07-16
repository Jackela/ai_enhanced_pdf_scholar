"""
Database Models
Data models representing the database entities for document management
and vector indexing. These are pure data classes without business logic.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DocumentModel:
    """
    {
        "name": "DocumentModel",
        "version": "1.0.0",
        "description": "Pure data model representing a document in the system.",
        "dependencies": [],
        "interface": {
            "inputs": ["title", "file_path", "file_hash", "file_size", "page_count"],
            "outputs": "Document data object with metadata"
        }
    }
    Pure data model for documents stored in the system.
    Contains file metadata, indexing status, and access tracking.
    """

    # Core fields
    title: str
    file_path: Optional[str]
    file_hash: str
    file_size: int
    content_hash: Optional[str] = None
    page_count: Optional[int] = None
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    # Database ID (set after insertion)
    id: Optional[int] = None
    # Metadata as JSON dict
    metadata: Optional[Dict[str, Any]] = None
    # Internal flag to distinguish between new creation and database loading
    _from_database: bool = field(default=False, init=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Only set defaults for new documents, not when loading from database
        if not self._from_database:
            # Set default timestamps
            if self.created_at is None:
                self.created_at = datetime.now()
            if self.updated_at is None:
                self.updated_at = self.created_at
        # Initialize metadata if not provided
        if self.metadata is None:
            self.metadata = {}
        # Validate required fields
        # Note: We allow empty title as get_display_name() provides fallback logic
        if not self.file_hash.strip():
            raise ValueError("File hash cannot be empty")
        if self.file_size < 0:
            raise ValueError("File size cannot be negative")

    @classmethod
    def from_file(
        cls, file_path: str, file_hash: str, title: Optional[str] = None
    ) -> "DocumentModel":
        """
        Create DocumentModel from file path.
        Args:
            file_path: Path to the PDF file
            file_hash: Content hash of the file
            title: Document title (defaults to filename)
        Returns:
            DocumentModel instance
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        # Extract title from filename if not provided
        if title is None:
            title = path.stem
        # Get file stats
        stat = path.stat()
        return cls(
            title=title,
            file_path=str(path.absolute()),
            file_hash=file_hash,
            file_size=stat.st_size,
            metadata={
                "file_extension": path.suffix.lower(),
                "original_filename": path.name,
                "file_modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            },
        )

    @classmethod
    def from_database_row(cls, row: Dict[str, Any]) -> "DocumentModel":
        """
        Create DocumentModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            DocumentModel instance
        """
        # Parse timestamps
        created_at = (
            datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
        )
        updated_at = (
            datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
        )
        last_accessed = (
            datetime.fromisoformat(row["last_accessed"])
            if row.get("last_accessed")
            else None
        )
        # Parse metadata JSON
        metadata = json.loads(row["metadata"]) if row.get("metadata") else {}
        return cls(
            id=row["id"],
            title=row["title"],
            file_path=row.get("file_path"),
            file_hash=row["file_hash"],
            content_hash=row.get("content_hash"),
            file_size=row["file_size"],
            page_count=row.get("page_count"),
            created_at=created_at,
            updated_at=updated_at,
            last_accessed=last_accessed,
            metadata=metadata,
            _from_database=True,
        )

    def to_database_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {
            "id": self.id,
            "title": self.title,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "content_hash": self.content_hash,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "metadata": json.dumps(self.metadata) if self.metadata else "{}",
        }

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for API responses.
        Returns:
            Dictionary suitable for API response models
        """
        return {
            "id": self.id,
            "title": self.title,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "content_hash": self.content_hash,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "metadata": self.metadata or {},
        }

    def update_access_time(self) -> None:
        """Update the last accessed timestamp to now."""
        self.last_accessed = datetime.now()

    def get_display_name(self) -> str:
        """Get user-friendly display name."""
        if self.metadata:
            return self.title or self.metadata.get(
                "original_filename", "Unknown Document"
            )
        return self.title or "Unknown Document"

    def get_file_extension(self) -> str:
        """Get file extension from metadata."""
        if self.metadata:
            result = self.metadata.get("file_extension", ".pdf")
            return str(result) if result is not None else ".pdf"
        return ".pdf"

    def is_file_available(self) -> bool:
        """Check if the original file is still available."""
        if not self.file_path:
            return False
        return Path(self.file_path).exists()


@dataclass
class VectorIndexModel:
    """
    {
        "name": "VectorIndexModel",
        "version": "1.0.0",
        "description": "Pure data model representing a vector index for a document.",
        "dependencies": ["DocumentModel"],
        "interface": {
            "inputs": ["document_id", "index_path", "index_hash"],
            "outputs": "Vector index data object with metadata"
        }
    }
    Pure data model for vector indexes associated with documents.
    Contains index metadata, chunk information, and storage location.
    """

    # Core fields
    document_id: int
    index_path: str
    index_hash: str
    chunk_count: Optional[int] = None
    # Timestamps
    created_at: Optional[datetime] = None
    # Database ID (set after insertion)
    id: Optional[int] = None

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Set default timestamp
        if self.created_at is None:
            self.created_at = datetime.now()
        # Validate required fields
        if self.document_id <= 0:
            raise ValueError("Document ID must be positive")
        if not self.index_path.strip():
            raise ValueError("Index path cannot be empty")
        if not self.index_hash.strip():
            raise ValueError("Index hash cannot be empty")

    @classmethod
    def from_database_row(cls, row: Dict[str, Any]) -> "VectorIndexModel":
        """
        Create VectorIndexModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            VectorIndexModel instance
        """
        created_at = (
            datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
        )
        return cls(
            id=row["id"],
            document_id=row["document_id"],
            index_path=row["index_path"],
            index_hash=row["index_hash"],
            chunk_count=row.get("chunk_count"),
            created_at=created_at,
        )

    def to_database_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {
            "id": self.id,
            "document_id": self.document_id,
            "index_path": self.index_path,
            "index_hash": self.index_hash,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_index_available(self) -> bool:
        """Check if the index files are still available."""
        index_path = Path(self.index_path)
        if not index_path.exists():
            return False
        # Check for essential LlamaIndex files
        required_files = [
            "default__vector_store.json",
            "graph_store.json",
            "index_store.json",
        ]
        for file_name in required_files:
            if not (index_path / file_name).exists():
                return False
        return True


@dataclass
class TagModel:
    """
    {
        "name": "TagModel",
        "version": "1.0.0",
        "description": "Pure data model representing a tag for document categorization.",
        "dependencies": [],
        "interface": {
            "inputs": ["name", "color"],
            "outputs": "Tag data object"
        }
    }
    Pure data model for tags used to categorize documents.
    """

    # Core fields
    name: str
    color: Optional[str] = None
    # Database ID (set after insertion)
    id: Optional[int] = None
    # Internal flag to distinguish between new creation and database loading
    _from_database: bool = field(default=False, init=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization validation."""
        if not self.name.strip():
            raise ValueError("Tag name cannot be empty")
        # Normalize name
        self.name = self.name.strip().lower()
        # Set default color only for new tags, not when loading from database
        if not self._from_database and self.color is None:
            self.color = "#0078d4"  # Default blue

    @classmethod
    def from_database_row(cls, row: Dict[str, Any]) -> "TagModel":
        """
        Create TagModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            TagModel instance
        """
        return cls(
            id=row["id"], name=row["name"], color=row.get("color"), _from_database=True
        )

    def to_database_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {"name": self.name, "color": self.color}
