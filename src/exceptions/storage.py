"""
Storage and Database Exception Classes
Handles errors related to file storage, database operations, and connections.
"""

from typing import Any, Optional

from .base import PDFScholarError, RepositoryError


class StorageError(PDFScholarError):
    """Base class for storage-related errors."""

    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize storage error.

        Args:
            message: Error message
            path: File or directory path
            operation: Storage operation that failed
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if path:
            context["path"] = path
        if operation:
            context["operation"] = operation

        super().__init__(message, context=context, **kwargs)
        self.path = path
        self.operation = operation

    def _get_default_user_message(self) -> str:
        if self.operation:
            return f"Failed to {self.operation}. Please check file permissions and try again."
        return "File system operation failed. Please try again."


class FileNotFoundError(StorageError):
    """Raised when a requested file cannot be found."""

    def __init__(self, message: str, path: Optional[str] = None, **kwargs: Any):
        super().__init__(message, path=path, operation="locate file", **kwargs)

    def _get_default_user_message(self) -> str:
        if self.path:
            return f"File not found: {self.path}"
        return "The requested file was not found."


class FileAccessError(StorageError):
    """Raised when file access is denied or fails."""

    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        access_type: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize file access error.

        Args:
            message: Error message
            path: File path
            access_type: Type of access attempted (read, write, delete)
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if access_type:
            context["access_type"] = access_type

        operation = f"{access_type} file" if access_type else "access file"
        super().__init__(
            message, path=path, operation=operation, context=context, **kwargs
        )
        self.access_type = access_type

    def _get_default_user_message(self) -> str:
        if self.access_type:
            return f"Permission denied: cannot {self.access_type} file."
        return "File access denied. Please check permissions."


class DatabaseError(RepositoryError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        table: Optional[str] = None,
        constraint: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize database error.

        Args:
            message: Error message
            query: SQL query that failed (if applicable)
            table: Database table involved
            constraint: Database constraint that was violated
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if query:
            context["query"] = query
        if table:
            context["table"] = table
        if constraint:
            context["constraint"] = constraint

        super().__init__(message, repository="database", context=context, **kwargs)
        self.query = query
        self.table = table
        self.constraint = constraint

    def _get_default_user_message(self) -> str:
        if self.constraint:
            return "Data constraint violation. Please check your input."
        return "Database operation failed. Please try again."


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        database: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize connection error.

        Args:
            message: Error message
            host: Database host
            database: Database name
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if host:
            context["host"] = host
        if database:
            context["database"] = database

        super().__init__(message, operation="connect", context=context, **kwargs)
        self.host = host
        self.database = database

    def _get_default_user_message(self) -> str:
        return "Unable to connect to the database. Please try again later."
