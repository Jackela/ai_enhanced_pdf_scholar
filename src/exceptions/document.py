"""
Document-related Exception Classes
Handles errors related to document management, import, and processing.
"""

from typing import Any, Optional

from .base import PDFScholarError


class DocumentError(PDFScholarError):
    """Base class for document-related errors."""

    def __init__(
        self,
        message: str,
        document_id: Optional[int] = None,
        file_path: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize document error.

        Args:
            message: Error message
            document_id: ID of the document (if applicable)
            file_path: File path (if applicable)
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if document_id:
            context["document_id"] = document_id
        if file_path:
            context["file_path"] = file_path

        super().__init__(message, context=context, **kwargs)
        self.document_id = document_id
        self.file_path = file_path

    def _get_default_user_message(self) -> str:
        return "An error occurred while processing the document."


class DocumentNotFoundError(DocumentError):
    """Raised when a requested document cannot be found."""

    def __init__(self, message: str, document_id: Optional[int] = None, **kwargs: Any):
        super().__init__(message, document_id=document_id, **kwargs)

    def _get_default_user_message(self) -> str:
        if self.document_id:
            return f"Document with ID {self.document_id} was not found."
        return "The requested document was not found."


class DocumentImportError(DocumentError):
    """Raised when document import fails."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize document import error.

        Args:
            message: Error message
            file_path: Path to file being imported
            reason: Specific reason for import failure
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if reason:
            context["reason"] = reason

        super().__init__(message, file_path=file_path, context=context, **kwargs)
        self.reason = reason

    def _get_default_user_message(self) -> str:
        if self.reason:
            return f"Failed to import document: {self.reason}"
        return (
            "Failed to import the document. Please check the file format and try again."
        )


class DuplicateDocumentError(DocumentImportError):
    """Raised when attempting to import a duplicate document."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        existing_document_id: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Initialize duplicate document error.

        Args:
            message: Error message
            file_path: Path to duplicate file
            existing_document_id: ID of existing document
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if existing_document_id:
            context["existing_document_id"] = existing_document_id

        super().__init__(
            message,
            file_path=file_path,
            reason="Document already exists",
            context=context,
            **kwargs,
        )
        self.existing_document_id = existing_document_id

    def _get_default_user_message(self) -> str:
        return "This document already exists in your library."


class DocumentValidationError(DocumentError):
    """Raised when document validation fails."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        validation_issue: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize document validation error.

        Args:
            message: Error message
            file_path: Path to invalid file
            validation_issue: Specific validation issue
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if validation_issue:
            context["validation_issue"] = validation_issue

        super().__init__(message, file_path=file_path, context=context, **kwargs)
        self.validation_issue = validation_issue

    def _get_default_user_message(self) -> str:
        if self.validation_issue:
            return f"Document validation failed: {self.validation_issue}"
        return "The document file is invalid or corrupted."


class DocumentProcessingError(DocumentError):
    """Raised when document processing fails."""

    def __init__(
        self,
        message: str,
        document_id: Optional[int] = None,
        processing_stage: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize document processing error.

        Args:
            message: Error message
            document_id: ID of document being processed
            processing_stage: Stage where processing failed
            **kwargs: Additional arguments for base class
        """
        context = kwargs.pop("context", {})
        if processing_stage:
            context["processing_stage"] = processing_stage

        super().__init__(message, document_id=document_id, context=context, **kwargs)
        self.processing_stage = processing_stage

    def _get_default_user_message(self) -> str:
        if self.processing_stage:
            return f"Document processing failed at {self.processing_stage} stage."
        return "Failed to process the document. Please try again."
