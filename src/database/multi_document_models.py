"""
Multi-Document RAG Data Models
Data models for supporting cross-document queries, collections, and multi-document indexing.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.database.models import safe_get


@dataclass
class DocumentSource:
    """
    Represents a source document in query results.
    Contains relevance information and excerpt from the document.
    """
    document_id: int
    relevance_score: float
    excerpt: str
    page_number: int | None = None
    chunk_id: str | None = None

    def __post_init__(self) -> None:
        """Validation for document source."""
        if self.document_id <= 0:
            raise ValueError("Document ID must be positive")
        if not 0.0 <= self.relevance_score <= 1.0:
            raise ValueError("Relevance score must be between 0.0 and 1.0")
        if not self.excerpt.strip():
            raise ValueError("Excerpt cannot be empty")


@dataclass
class CrossReference:
    """
    Represents a cross-reference relationship between two documents.
    Used to show how documents relate to each other in query results.
    """
    source_doc_id: int
    target_doc_id: int
    relation_type: str  # "supports", "contradicts", "extends", "cites"
    confidence: float = 0.5
    description: str | None = None

    def __post_init__(self) -> None:
        """Validation for cross reference."""
        if self.source_doc_id <= 0 or self.target_doc_id <= 0:
            raise ValueError("Document IDs must be positive")
        if self.source_doc_id == self.target_doc_id:
            raise ValueError("Source and target documents cannot be the same")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")


@dataclass
class MultiDocumentCollectionModel:
    """
    Pure data model representing a collection of documents for multi-document queries.
    Contains metadata about the collection and list of document IDs.
    """

    # Core fields
    name: str
    document_ids: list[int]
    description: str | None = None

    # Computed field
    document_count: int = field(init=False)

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Database ID (set after insertion)
    id: int | None = None

    # Internal flag to distinguish between new creation and database loading
    _from_database: bool = field(default=False, init=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Set computed field
        self.document_count = len(self.document_ids)

        # Only set defaults for new collections, not when loading from database
        if not self._from_database:
            # Set default timestamps
            if self.created_at is None:
                self.created_at = datetime.now()
            if self.updated_at is None:
                self.updated_at = self.created_at

        # Validate required fields
        if not self.name.strip():
            raise ValueError("Collection name cannot be empty")
        if not self.document_ids:
            raise ValueError("Collection must contain at least one document")
        if any(doc_id <= 0 for doc_id in self.document_ids):
            raise ValueError("All document IDs must be positive")

    def add_document(self, document_id: int) -> None:
        """Add a document to the collection if not already present."""
        if document_id <= 0:
            raise ValueError("Document ID must be positive")
        if document_id not in self.document_ids:
            self.document_ids.append(document_id)
            self.document_count = len(self.document_ids)
            self.updated_at = datetime.now()

    def remove_document(self, document_id: int) -> bool:
        """
        Remove a document from the collection.
        Returns True if document was removed, False if not found.
        Raises ValueError if trying to remove the last document.
        """
        if len(self.document_ids) <= 1:
            raise ValueError("Cannot remove the last document from a collection")

        if document_id in self.document_ids:
            self.document_ids.remove(document_id)
            self.document_count = len(self.document_ids)
            self.updated_at = datetime.now()
            return True
        return False

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "MultiDocumentCollectionModel":
        """
        Create MultiDocumentCollectionModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            MultiDocumentCollectionModel instance
        """
        # Parse timestamps
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
        updated_at_str = safe_get(row, "updated_at")
        updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else None

        # Parse document IDs from JSON string
        document_ids_str = safe_get(row, "document_ids")
        document_ids = json.loads(document_ids_str) if document_ids_str else []

        return cls(
            id=row["id"],
            name=row["name"],
            description=safe_get(row, "description"),
            document_ids=document_ids,
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
            "name": self.name,
            "description": self.description,
            "document_ids": json.dumps(self.document_ids),
            "document_count": self.document_count,
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
            "name": self.name,
            "description": self.description,
            "document_ids": self.document_ids,
            "document_count": self.document_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class MultiDocumentIndexModel:
    """
    Pure data model representing a vector index for a collection of documents.
    Contains index metadata and storage location for cross-document queries.
    """

    # Core fields
    collection_id: int
    index_path: str
    index_hash: str
    embedding_model: str = "text-embedding-ada-002"
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
        if self.collection_id <= 0:
            raise ValueError("Collection ID must be positive")
        if not self.index_path.strip():
            raise ValueError("Index path cannot be empty")
        if not self.index_hash.strip():
            raise ValueError("Index hash cannot be empty")

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "MultiDocumentIndexModel":
        """
        Create MultiDocumentIndexModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            MultiDocumentIndexModel instance
        """
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None

        # Parse metadata JSON
        metadata_str = safe_get(row, "metadata")
        metadata = json.loads(metadata_str) if metadata_str else {}

        return cls(
            id=row["id"],
            collection_id=row["collection_id"],
            index_path=row["index_path"],
            index_hash=row["index_hash"],
            embedding_model=safe_get(row, "embedding_model") or "text-embedding-ada-002",
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
            "collection_id": self.collection_id,
            "index_path": self.index_path,
            "index_hash": self.index_hash,
            "embedding_model": self.embedding_model,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": json.dumps(self.metadata) if self.metadata else "{}",
        }


@dataclass
class CrossDocumentQueryModel:
    """
    Pure data model representing a cross-document query and its results.
    Contains query information, response data, and performance metrics.
    """

    # Core fields
    collection_id: int
    query_text: str
    user_id: str | None = None

    # Response fields
    response_text: str | None = None
    confidence_score: float | None = None
    sources: list[DocumentSource] = field(default_factory=list)
    cross_references: list[CrossReference] = field(default_factory=list)

    # Status and error handling
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    error_message: str | None = None

    # Performance metrics
    processing_time_ms: int | None = None
    tokens_used: int | None = None

    # Timestamps
    created_at: datetime | None = None
    completed_at: datetime | None = None

    # Database ID (set after insertion)
    id: int | None = None

    def __post_init__(self) -> None:
        """Post-initialization validation and defaults."""
        # Set default timestamp
        if self.created_at is None:
            self.created_at = datetime.now()

        # Validate required fields
        if self.collection_id <= 0:
            raise ValueError("Collection ID must be positive")
        if not self.query_text.strip():
            raise ValueError("Query text cannot be empty")

    def set_response(
        self,
        answer: str,
        confidence: float,
        sources: list[DocumentSource],
        cross_references: list[CrossReference],
        processing_time_ms: int | None = None,
        tokens_used: int | None = None
    ) -> None:
        """Set successful query response."""
        self.response_text = answer
        self.confidence_score = confidence
        self.sources = sources
        self.cross_references = cross_references
        self.processing_time_ms = processing_time_ms
        self.tokens_used = tokens_used
        self.status = "completed"
        self.completed_at = datetime.now()
        self.error_message = None

    def set_error(self, error_message: str) -> None:
        """Set query error state."""
        self.error_message = error_message
        self.status = "failed"
        self.completed_at = datetime.now()

    @classmethod
    def from_database_row(cls, row: dict[str, Any]) -> "CrossDocumentQueryModel":
        """
        Create CrossDocumentQueryModel from database row.
        Args:
            row: Database row as dictionary
        Returns:
            CrossDocumentQueryModel instance
        """
        # Parse timestamps
        created_at_str = safe_get(row, "created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
        completed_at_str = safe_get(row, "completed_at")
        completed_at = datetime.fromisoformat(completed_at_str) if completed_at_str else None

        # Parse sources from JSON
        sources_str = safe_get(row, "sources")
        sources = []
        if sources_str:
            sources_data = json.loads(sources_str)
            sources = [
                DocumentSource(
                    document_id=s["document_id"],
                    relevance_score=s["relevance_score"],
                    excerpt=s["excerpt"],
                    page_number=s.get("page_number"),
                    chunk_id=s.get("chunk_id")
                )
                for s in sources_data
            ]

        # Parse cross references from JSON
        cross_refs_str = safe_get(row, "cross_references")
        cross_references = []
        if cross_refs_str:
            cross_refs_data = json.loads(cross_refs_str)
            cross_references = [
                CrossReference(
                    source_doc_id=cr["source_doc_id"],
                    target_doc_id=cr["target_doc_id"],
                    relation_type=cr["relation_type"],
                    confidence=cr.get("confidence", 0.5),
                    description=cr.get("description")
                )
                for cr in cross_refs_data
            ]

        return cls(
            id=row["id"],
            collection_id=row["collection_id"],
            query_text=row["query_text"],
            user_id=safe_get(row, "user_id"),
            response_text=safe_get(row, "response_text"),
            confidence_score=safe_get(row, "confidence_score"),
            sources=sources,
            cross_references=cross_references,
            status=safe_get(row, "status") or "pending",
            error_message=safe_get(row, "error_message"),
            processing_time_ms=safe_get(row, "processing_time_ms"),
            tokens_used=safe_get(row, "tokens_used"),
            created_at=created_at,
            completed_at=completed_at,
        )

    def to_database_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for database insertion.
        Returns:
            Dictionary suitable for database operations
        """
        # Serialize sources to JSON
        sources_json = json.dumps([
            {
                "document_id": s.document_id,
                "relevance_score": s.relevance_score,
                "excerpt": s.excerpt,
                "page_number": s.page_number,
                "chunk_id": s.chunk_id
            }
            for s in self.sources
        ])

        # Serialize cross references to JSON
        cross_refs_json = json.dumps([
            {
                "source_doc_id": cr.source_doc_id,
                "target_doc_id": cr.target_doc_id,
                "relation_type": cr.relation_type,
                "confidence": cr.confidence,
                "description": cr.description
            }
            for cr in self.cross_references
        ])

        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "query_text": self.query_text,
            "user_id": self.user_id,
            "response_text": self.response_text,
            "confidence_score": self.confidence_score,
            "sources": sources_json,
            "cross_references": cross_refs_json,
            "status": self.status,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_api_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary for API responses.
        Returns:
            Dictionary suitable for API response models
        """
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "query_text": self.query_text,
            "user_id": self.user_id,
            "response_text": self.response_text,
            "confidence_score": self.confidence_score,
            "sources": [
                {
                    "document_id": s.document_id,
                    "relevance_score": s.relevance_score,
                    "excerpt": s.excerpt,
                    "page_number": s.page_number,
                    "chunk_id": s.chunk_id
                }
                for s in self.sources
            ],
            "cross_references": [
                {
                    "source_doc_id": cr.source_doc_id,
                    "target_doc_id": cr.target_doc_id,
                    "relation_type": cr.relation_type,
                    "confidence": cr.confidence,
                    "description": cr.description
                }
                for cr in self.cross_references
            ],
            "status": self.status,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
