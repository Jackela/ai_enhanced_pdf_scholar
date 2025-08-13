"""
Exception Hierarchy for AI Enhanced PDF Scholar
Provides standardized error handling with consistent exception types.
"""

from .auth import (
    AccountError,
    AuthenticationError,
    AuthorizationError,
    PasswordError,
    SessionError,
    TokenError,
)
from .base import (
    ConfigurationError,
    PDFScholarError,
    RepositoryError,
    ServiceError,
    ValidationError,
)
from .document import (
    DocumentError,
    DocumentImportError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentValidationError,
    DuplicateDocumentError,
)
from .service import (
    ContentHashError,
    EmailServiceError,
    RAGServiceError,
    VectorIndexError,
)
from .storage import (
    ConnectionError,
    DatabaseError,
    FileAccessError,
    FileNotFoundError,
    StorageError,
)

__all__ = [
    # Base exceptions
    "PDFScholarError",
    "ValidationError",
    "ConfigurationError",
    "ServiceError",
    "RepositoryError",
    # Document exceptions
    "DocumentError",
    "DocumentNotFoundError",
    "DocumentImportError",
    "DuplicateDocumentError",
    "DocumentValidationError",
    "DocumentProcessingError",
    # Authentication exceptions
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "AccountError",
    "PasswordError",
    "SessionError",
    # Storage exceptions
    "StorageError",
    "FileNotFoundError",
    "FileAccessError",
    "DatabaseError",
    "ConnectionError",
    # Service exceptions
    "RAGServiceError",
    "VectorIndexError",
    "ContentHashError",
    "EmailServiceError",
]
