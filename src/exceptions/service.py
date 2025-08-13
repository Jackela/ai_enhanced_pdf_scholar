"""
Service-specific Exception Classes
Handles errors specific to various services like RAG, vector indexing, etc.
"""

from typing import Any, Optional

from .base import ServiceError


class RAGServiceError(ServiceError):
    """Raised when RAG service operations fail."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        document_id: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Initialize RAG service error.

        Args:
            message: Error message
            query: Query that failed
            document_id: Document ID being queried
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if query:
            context["query"] = query
        if document_id:
            context["document_id"] = document_id

        super().__init__(message, service_name="RAGService", context=context, **kwargs)
        self.query = query
        self.document_id = document_id

    def _get_default_user_message(self) -> str:
        return "Failed to process your query. Please try again."


class VectorIndexError(ServiceError):
    """Raised when vector index operations fail."""

    def __init__(
        self,
        message: str,
        index_id: Optional[int] = None,
        index_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize vector index error.

        Args:
            message: Error message
            index_id: Vector index ID
            index_path: Path to index files
            operation: Index operation that failed
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if index_id:
            context["index_id"] = index_id
        if index_path:
            context["index_path"] = index_path

        super().__init__(
            message,
            service_name="VectorIndexService",
            operation=operation,
            context=context,
            **kwargs,
        )
        self.index_id = index_id
        self.index_path = index_path

    def _get_default_user_message(self) -> str:
        if self.operation == "build":
            return "Failed to build document index. Please try again."
        elif self.operation == "search":
            return "Search index unavailable. Please try again later."
        return "Vector index operation failed. Please try again."


class ContentHashError(ServiceError):
    """Raised when content hashing operations fail."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        hash_type: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize content hash error.

        Args:
            message: Error message
            file_path: File path being hashed
            hash_type: Type of hash being calculated
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if file_path:
            context["file_path"] = file_path
        if hash_type:
            context["hash_type"] = hash_type

        super().__init__(
            message,
            service_name="ContentHashService",
            operation="calculate_hash",
            context=context,
            **kwargs,
        )
        self.file_path = file_path
        self.hash_type = hash_type

    def _get_default_user_message(self) -> str:
        return "Failed to process file content. Please check the file and try again."


class EmailServiceError(ServiceError):
    """Raised when email service operations fail."""

    def __init__(
        self,
        message: str,
        recipient: Optional[str] = None,
        template: Optional[str] = None,
        smtp_error: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize email service error.

        Args:
            message: Error message
            recipient: Email recipient
            template: Email template used
            smtp_error: SMTP-specific error
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if recipient:
            context["recipient"] = recipient
        if template:
            context["template"] = template
        if smtp_error:
            context["smtp_error"] = smtp_error

        super().__init__(
            message,
            service_name="EmailService",
            operation="send_email",
            context=context,
            **kwargs,
        )
        self.recipient = recipient
        self.template = template
        self.smtp_error = smtp_error

    def _get_default_user_message(self) -> str:
        return (
            "Failed to send email. Please check your email address or try again later."
        )
