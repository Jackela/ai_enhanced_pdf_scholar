"""
Exception Hierarchy for AI Enhanced PDF Scholar
Provides standardized error handling with consistent exception types.
"""

from .base import (
    PDFScholarError,
    ValidationError,
    ConfigurationError,
    ServiceError,
    RepositoryError,
)

from .document import (
    DocumentError,
    DocumentNotFoundError,
    DocumentImportError,
    DuplicateDocumentError,
    DocumentValidationError,
    DocumentProcessingError,
)

from .auth import (
    AuthenticationError,
    AuthorizationError,
    TokenError,
    AccountError,
    PasswordError,
    SessionError,
)

from .storage import (
    StorageError,
    FileNotFoundError,
    FileAccessError,
    DatabaseError,
    ConnectionError,
)

from .service import (
    RAGServiceError,
    VectorIndexError,
    ContentHashError,
    EmailServiceError,
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