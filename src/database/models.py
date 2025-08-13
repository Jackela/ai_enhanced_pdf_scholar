"""
Database Models
Data models representing the database entities for document management
and vector indexing. These are pure data classes without business logic.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_get(row_obj, key):
    """Safely get value from row object (dict or sqlite3.Row)."""
    if hasattr(row_obj, "get"):
        return row_obj.get(key)
    else:
        try:
            return row_obj[key]
        except (KeyError, IndexError):
            return None


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
    file_path: str | None
    file_hash: str
    file_size: int
    content_hash: str | None = None
    page_count: int | None = None
    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_accessed: datetime | None = None
    # Database ID (set after insertion)
    id: int | None = None
    # Metadata as JSON dict
    metadata: dict[str, Any] | None = None
    # Tags as comma-separated string
    tags: str = ""
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
        cls, file_path: str, file_hash: str, title: str | None = None
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
    def from_database_row(cls, row: dict[str, Any]) -> "DocumentModel":
        """
        Create DocumentModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            DocumentModel instance
        """
        # Parse timestamps - handle both dict and Row objects
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
        updated_at_str = safe_get(row, "updated_at")
        updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else None
        last_accessed_str = safe_get(row, "last_accessed")
        last_accessed = (
            datetime.fromisoformat(last_accessed_str) if last_accessed_str else None
        )
        # Parse metadata JSON
        metadata_str = safe_get(row, "metadata")
        metadata = json.loads(metadata_str) if metadata_str else {}
        return cls(
            id=row["id"],
            title=row["title"],
            file_path=safe_get(row, "file_path"),
            file_hash=row["file_hash"],
            content_hash=safe_get(row, "content_hash"),
            file_size=row["file_size"],
            page_count=safe_get(row, "page_count"),
            created_at=created_at,
            updated_at=updated_at,
            last_accessed=last_accessed,
            metadata=metadata,
            tags=safe_get(row, "tags") or "",
            _from_database=True,
        )

    def to_database_dict(self) -> dict[str, Any]:
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
            "tags": self.tags,
        }

    def to_api_dict(self) -> dict[str, Any]:
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

    def is_processed(self) -> bool:
        """
        Check if the document has been fully processed.
        A document is considered processed if it has content_hash and page_count.
        """
        return bool(self.content_hash and self.page_count is not None)


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
    chunk_count: int | None = None
    # Timestamps
    created_at: datetime | None = None
    # Database ID (set after insertion)
    id: int | None = None
    # Metadata as JSON dict
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Set default timestamp
        if self.created_at is None:
            self.created_at = datetime.now()
        # Initialize metadata if not provided
        if self.metadata is None:
            self.metadata = {}
        # Validate required fields
        if self.document_id <= 0:
            raise ValueError("Document ID must be positive")
        if not self.index_path.strip():
            raise ValueError("Index path cannot be empty")
        if not self.index_hash.strip():
            raise ValueError("Index hash cannot be empty")

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "VectorIndexModel":
        """
        Create VectorIndexModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            VectorIndexModel instance
        """
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
        # Parse metadata JSON
        metadata_str = safe_get(row, "metadata")
        metadata = json.loads(metadata_str) if metadata_str else {}
        return cls(
            id=row["id"],
            document_id=row["document_id"],
            index_path=row["index_path"],
            index_hash=row["index_hash"],
            chunk_count=safe_get(row, "chunk_count"),
            created_at=created_at,
            metadata=metadata,
        )

    def to_database_dict(self) -> dict[str, Any]:
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
            "metadata": json.dumps(self.metadata) if self.metadata else "{}",
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
        return all((index_path / file_name).exists() for file_name in required_files)


@dataclass
class TagModel:
    """
    {
        "name": "TagModel",
        "version": "1.0.0",
        "description": "Pure data model representing a tag for documents.",
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
    color: str | None = None
    # Database ID (set after insertion)
    id: int | None = None
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
    def from_database_row(cls, row: dict[str, Any]) -> "TagModel":
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

    def to_database_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {"name": self.name, "color": self.color}


@dataclass
class CitationModel:
    """
    {
        "name": "CitationModel",
        "version": "1.0.0",
        "description": (
            "Pure data model representing a citation extracted from a document."
        ),
        "dependencies": ["DocumentModel"],
        "interface": {
            "inputs": [
                "document_id", "raw_text", "authors",
                "title", "publication_year"
            ],
            "outputs": "Citation data object with parsed metadata"
        }
    }
    Pure data model for citations extracted from academic documents.
    Contains parsed citation information and metadata.
    """

    # Core fields
    document_id: int
    raw_text: str
    authors: str | None = None
    title: str | None = None
    publication_year: int | None = None
    journal_or_venue: str | None = None
    doi: str | None = None
    page_range: str | None = None
    citation_type: str | None = None  # "journal", "conference", "book", "website", etc.
    confidence_score: float | None = None  # 0.0 to 1.0
    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Database ID (set after insertion)
    id: int | None = None
    # Internal flag to distinguish between new creation and database loading
    _from_database: bool = field(default=False, init=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Only set defaults for new citations, not when loading from database
        if not self._from_database:
            # Set default timestamps
            if self.created_at is None:
                self.created_at = datetime.now()
            if self.updated_at is None:
                self.updated_at = self.created_at

        # Validate required fields
        if self.document_id <= 0:
            raise ValueError("Document ID must be positive")
        if not self.raw_text.strip():
            raise ValueError("Raw citation text cannot be empty")

        # Validate optional fields
        current_year = datetime.now().year
        if self.publication_year is not None and (
            self.publication_year < 1000 or self.publication_year > current_year + 1
        ):
            raise ValueError(f"Invalid publication year: {self.publication_year}")

        if (
            self.confidence_score is not None
            and not 0.0 <= self.confidence_score <= 1.0
        ):
            raise ValueError("Confidence score must be between 0.0 and 1.0")

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "CitationModel":
        """
        Create CitationModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            CitationModel instance
        """
        # Parse timestamps - handle both dict and Row objects
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
        updated_at_str = safe_get(row, "updated_at")
        updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else None

        return cls(
            id=row["id"],
            document_id=row["document_id"],
            raw_text=row["raw_text"],
            authors=safe_get(row, "authors"),
            title=safe_get(row, "title"),
            publication_year=safe_get(row, "publication_year"),
            journal_or_venue=safe_get(row, "journal_or_venue"),
            doi=safe_get(row, "doi"),
            page_range=safe_get(row, "page_range"),
            citation_type=safe_get(row, "citation_type"),
            confidence_score=safe_get(row, "confidence_score"),
            created_at=created_at,
            updated_at=updated_at,
            _from_database=True,
        )

    def to_database_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {
            "id": self.id,
            "document_id": self.document_id,
            "raw_text": self.raw_text,
            "authors": self.authors,
            "title": self.title,
            "publication_year": self.publication_year,
            "journal_or_venue": self.journal_or_venue,
            "doi": self.doi,
            "page_range": self.page_range,
            "citation_type": self.citation_type,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_api_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for API responses.
        Returns:
            Dictionary suitable for API response models
        """
        return {
            "id": self.id,
            "document_id": self.document_id,
            "raw_text": self.raw_text,
            "authors": self.authors,
            "title": self.title,
            "publication_year": self.publication_year,
            "journal_or_venue": self.journal_or_venue,
            "doi": self.doi,
            "page_range": self.page_range,
            "citation_type": self.citation_type,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_formatted_citation(self, style: str = "apa") -> str:
        """
        Get formatted citation string in specified style.
        Args:
            style: Citation style ("apa", "mla", "chicago")
        Returns:
            Formatted citation string
        """
        if style.lower() == "apa":
            return self._format_apa()
        elif style.lower() == "mla":
            return self._format_mla()
        elif style.lower() == "chicago":
            return self._format_chicago()
        else:
            return self.raw_text

    def _format_apa(self) -> str:
        """Format citation in APA style."""
        parts = []
        if self.authors:
            parts.append(self.authors)
        if self.publication_year:
            parts.append(f"({self.publication_year})")
        if self.title:
            parts.append(self.title)
        if self.journal_or_venue:
            parts.append(f"*{self.journal_or_venue}*")
        return ". ".join(filter(None, parts)) + "."

    def _format_mla(self) -> str:
        """Format citation in MLA style."""
        parts = []
        if self.authors:
            parts.append(self.authors)
        if self.title:
            parts.append(f'"{self.title}"')
        if self.journal_or_venue:
            parts.append(f"*{self.journal_or_venue}*")
        if self.publication_year:
            parts.append(str(self.publication_year))
        return ", ".join(filter(None, parts)) + "."

    def _format_chicago(self) -> str:
        """Format citation in Chicago style."""
        parts = []
        if self.authors:
            parts.append(self.authors)
        if self.title:
            parts.append(f'"{self.title}"')
        if self.journal_or_venue:
            parts.append(self.journal_or_venue)
        if self.publication_year:
            parts.append(f"({self.publication_year})")
        return ". ".join(filter(None, parts)) + "."

    def is_complete(self) -> bool:
        """Check if citation has sufficient parsed information."""
        return bool(self.authors and self.title and self.publication_year)


@dataclass
class CitationRelationModel:
    """
    {
        "name": "CitationRelationModel",
        "version": "1.0.0",
        "description": (
            "Pure data model representing relationships between citations "
            "and documents."
        ),
        "dependencies": ["DocumentModel", "CitationModel"],
        "interface": {
            "inputs": [
                "source_document_id", "source_citation_id", "target_document_id"
            ],
            "outputs": "Citation relationship data object"
        }
    }
    Pure data model for relationships between citations and documents.
    Tracks which documents cite other documents in the library.
    """

    # Core fields
    source_document_id: int  # Document that contains the citation
    source_citation_id: int  # Citation within the source document
    target_document_id: int | None = None  # Document being cited (if in our library)
    target_citation_id: int | None = None  # Citation representing the target document
    relation_type: str = "cites"  # "cites", "cited_by", "references"
    confidence_score: float | None = None  # 0.0 to 1.0
    # Timestamps
    created_at: datetime | None = None
    # Database ID (set after insertion)
    id: int | None = None

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Set default timestamp
        if self.created_at is None:
            self.created_at = datetime.now()

        # Validate required fields
        if self.source_document_id <= 0:
            raise ValueError("Source document ID must be positive")
        if self.source_citation_id <= 0:
            raise ValueError("Source citation ID must be positive")

        # Validate optional fields
        if self.target_document_id is not None and self.target_document_id <= 0:
            raise ValueError("Target document ID must be positive")
        if self.target_citation_id is not None and self.target_citation_id <= 0:
            raise ValueError("Target citation ID must be positive")

        if (
            self.confidence_score is not None
            and not 0.0 <= self.confidence_score <= 1.0
        ):
            raise ValueError("Confidence score must be between 0.0 and 1.0")

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "CitationRelationModel":
        """
        Create CitationRelationModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            CitationRelationModel instance
        """
        created_at = (
            datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
        )

        return cls(
            id=row["id"],
            source_document_id=row["source_document_id"],
            source_citation_id=row["source_citation_id"],
            target_document_id=safe_get(row, "target_document_id"),
            target_citation_id=safe_get(row, "target_citation_id"),
            relation_type=safe_get(row, "relation_type") or "cites",
            confidence_score=safe_get(row, "confidence_score"),
            created_at=created_at,
        )

    def to_database_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        return {
            "id": self.id,
            "source_document_id": self.source_document_id,
            "source_citation_id": self.source_citation_id,
            "target_document_id": self.target_document_id,
            "target_citation_id": self.target_citation_id,
            "relation_type": self.relation_type,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
