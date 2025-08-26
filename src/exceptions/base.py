"""
Base Exception Classes
Provides the foundation for the exception hierarchy.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PDFScholarError(Exception):
    """
    Base exception class for all AI Enhanced PDF Scholar errors.

    Provides common functionality for error context, logging, and user messages.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        user_message: str | None = None,
        log_level: int = logging.ERROR,
    ):
        """
        Initialize base exception.

        Args:
            message: Technical error message for logging
            error_code: Optional error code for programmatic handling
            context: Optional context information for debugging
            user_message: Optional user-friendly message
            log_level: Logging level for this error
        """
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.user_message = user_message or self._get_default_user_message()
        self.log_level = log_level

        # Log the error automatically
        self._log_error()

    def _get_default_user_message(self) -> str:
        """Get default user-friendly message for this error type."""
        return "An error occurred while processing your request."

    def _log_error(self) -> None:
        """Log the error with appropriate level and context."""
        log_message = f"[{self.error_code}] {str(self)}"
        if self.context:
            log_message += f" | Context: {self.context}"

        logger.log(self.log_level, log_message)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation of the error
        """
        return {
            "error": self.error_code,
            "message": str(self),
            "user_message": self.user_message,
            "context": self.context,
        }

    def with_context(self, **kwargs: Any) -> "PDFScholarError":
        """
        Add context information to the exception.

        Args:
            **kwargs: Context key-value pairs

        Returns:
            Self for method chaining
        """
        self.context.update(kwargs)
        return self


class ValidationError(PDFScholarError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        **kwargs: Any,
    ):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
            value: Invalid value
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)

        super().__init__(message, context=context, **kwargs)
        self.field = field
        self.value = value

    def _get_default_user_message(self) -> str:
        if self.field:
            return f"Invalid value provided for field '{self.field}'"
        return "Invalid input provided"


class ConfigurationError(PDFScholarError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: str | None = None, **kwargs: Any):
        """
        Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if config_key:
            context["config_key"] = config_key

        super().__init__(message, context=context, **kwargs)
        self.config_key = config_key

    def _get_default_user_message(self) -> str:
        return "System configuration error. Please contact support."


class ServiceError(PDFScholarError):
    """Raised when a service operation fails."""

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ):
        """
        Initialize service error.

        Args:
            message: Error message
            service_name: Name of the service that failed
            operation: Operation that was attempted
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if service_name:
            context["service"] = service_name
        if operation:
            context["operation"] = operation

        super().__init__(message, context=context, **kwargs)
        self.service_name = service_name
        self.operation = operation

    def _get_default_user_message(self) -> str:
        if self.operation:
            return f"Failed to complete {self.operation}. Please try again."
        return "Service operation failed. Please try again."


class RepositoryError(PDFScholarError):
    """Raised when repository operations fail."""

    def __init__(
        self,
        message: str,
        repository: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ):
        """
        Initialize repository error.

        Args:
            message: Error message
            repository: Repository name
            operation: Database operation that failed
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if repository:
            context["repository"] = repository
        if operation:
            context["operation"] = operation

        super().__init__(message, context=context, **kwargs)
        self.repository = repository
        self.operation = operation

    def _get_default_user_message(self) -> str:
        return "Database operation failed. Please try again."
