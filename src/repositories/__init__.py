"""
Repository Package
This package provides data access layer implementations following the Repository pattern.
All database operations are encapsulated here to maintain separation of concerns.
"""

from .base_repository import BaseRepository
from .document_repository import DocumentRepository
from .vector_repository import VectorIndexRepository

__all__ = ["BaseRepository", "DocumentRepository", "VectorIndexRepository"]
