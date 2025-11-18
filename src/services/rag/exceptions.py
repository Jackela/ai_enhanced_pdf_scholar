"""
RAG Service Exceptions

Custom exception classes for RAG service operations with detailed error information
and recovery suggestions for robust error handling.
"""

from typing import Any


class RAGBaseException(Exception):
    """Base exception for all RAG-related errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.suggestions = suggestions or []
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
        }


# Processing Exceptions


class RAGProcessingError(RAGBaseException):
    """Raised when document processing fails."""

    pass


class RAGIndexError(RAGBaseException):
    """Raised when index operations fail."""

    pass


class RAGQueryError(RAGBaseException):
    """Raised when query processing fails."""

    pass


class RAGRecoveryError(RAGBaseException):
    """Raised when recovery operations fail."""

    pass


class RAGFileError(RAGBaseException):
    """Raised when file operations fail."""

    pass


class RAGStorageError(RAGBaseException):
    """Raised when storage operations fail."""

    pass


class RAGVectorError(RAGBaseException):
    """Raised when vector operations fail."""

    pass


class RAGQualityError(RAGBaseException):
    """Raised when quality assessment fails."""

    pass


class RAGPerformanceError(RAGBaseException):
    """Raised when performance issues detected."""

    pass


class RAGMemoryError(RAGBaseException):
    """Raised when memory-related issues occur."""

    pass


class RAGTimeoutError(RAGBaseException):
    """Raised when operations timeout."""

    pass


class RAGConfigurationError(RAGBaseException):
    """Raised when configuration is invalid."""

    pass


class RAGValidationError(RAGBaseException):
    """Raised when input validation fails."""

    pass


class RAGAuthenticationError(RAGBaseException):
    """Raised when authentication fails."""

    pass


class RAGAuthorizationError(RAGBaseException):
    """Raised when authorization fails."""

    pass


# Specific processing errors


class DocumentProcessingError(RAGProcessingError):
    """Raised when document processing fails."""

    def __init__(self, document_id: int, stage: str, message: str, **kwargs) -> None:
        self.document_id = document_id
        self.stage = stage
        details = {
            "document_id": document_id,
            "processing_stage": stage,
            **kwargs.get("details", {}),
        }
        suggestions = [
            f"Retry processing for document {document_id}",
            "Check document format and integrity",
            f"Verify processing stage '{stage}' configuration",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class IndexBuildError(RAGIndexError):
    """Raised when index building fails."""

    def __init__(self, document_id: int, message: str, **kwargs) -> None:
        self.document_id = document_id
        details = {"document_id": document_id, **kwargs.get("details", {})}
        suggestions = [
            "Check document text extraction",
            "Verify vector store connectivity",
            "Ensure sufficient disk space",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class QueryProcessingError(RAGQueryError):
    """Raised when query processing fails."""

    def __init__(
        self, query: str, document_id: int | None = None, message: str = "", **kwargs
    ) -> None:
        self.query = query
        self.document_id = document_id
        details = {
            "query": query,
            "document_id": document_id,
            **kwargs.get("details", {}),
        }
        suggestions = [
            "Verify query format and length",
            "Check document index availability",
            "Ensure LLM service connectivity",
        ]
        super().__init__(
            message or f"Failed to process query: {query[:100]}...",
            details=details,
            suggestions=suggestions,
        )


class VectorStoreError(RAGVectorError):
    """Raised when vector store operations fail."""

    def __init__(self, operation: str, message: str, **kwargs) -> None:
        self.operation = operation
        details = {"operation": operation, **kwargs.get("details", {})}
        suggestions = [
            f"Retry {operation} operation",
            "Check vector store connectivity",
            "Verify storage permissions",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class LLMServiceError(RAGBaseException):
    """Raised when LLM service interactions fail."""

    def __init__(self, service: str, message: str, **kwargs) -> None:
        self.service = service
        details = {"service": service, **kwargs.get("details", {})}
        suggestions = [
            f"Check {service} API connectivity",
            "Verify API credentials",
            "Check rate limits and quotas",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class ContextBuildError(RAGBaseException):
    """Raised when context building fails."""

    def __init__(self, context_type: str, message: str, **kwargs) -> None:
        self.context_type = context_type
        details = {"context_type": context_type, **kwargs.get("details", {})}
        suggestions = [
            f"Check {context_type} context builder configuration",
            "Verify retrieved documents format",
            "Ensure context length limits",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


# File and storage specific exceptions


class FileOperationError(RAGFileError):
    """Raised when file operations fail."""

    def __init__(self, operation: str, file_path: str, message: str, **kwargs) -> None:
        self.operation = operation
        self.file_path = file_path
        details = {
            "operation": operation,
            "file_path": file_path,
            **kwargs.get("details", {}),
        }
        suggestions = [
            f"Check file permissions for {file_path}",
            f"Verify file exists for {operation}",
            "Ensure sufficient disk space",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class StorageQuotaExceededError(RAGStorageError):
    """Raised when storage quota is exceeded."""

    def __init__(self, current_usage: int, quota_limit: int, **kwargs) -> None:
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        details = {
            "current_usage_mb": current_usage,
            "quota_limit_mb": quota_limit,
            "usage_percentage": (current_usage / quota_limit) * 100,
            **kwargs.get("details", {}),
        }
        suggestions = [
            "Clean up temporary files",
            "Remove unused document indexes",
            "Consider increasing storage quota",
        ]
        message = (
            f"Storage quota exceeded: {current_usage}MB used of {quota_limit}MB limit"
        )
        super().__init__(message, details=details, suggestions=suggestions)


# Performance and quality exceptions


class PerformanceDegradationError(RAGPerformanceError):
    """Raised when significant performance degradation detected."""

    def __init__(
        self, metric: str, current_value: float, threshold: float, **kwargs
    ) -> None:
        self.metric = metric
        self.current_value = current_value
        self.threshold = threshold
        details = {
            "metric": metric,
            "current_value": current_value,
            "threshold": threshold,
            "degradation_factor": current_value / threshold,
            **kwargs.get("details", {}),
        }
        suggestions = [
            f"Investigate {metric} performance issues",
            "Check system resource usage",
            "Consider scaling system resources",
        ]
        message = f"Performance degradation detected: {metric} = {current_value} (threshold: {threshold})"
        super().__init__(message, details=details, suggestions=suggestions)


class QualityAssessmentError(RAGQualityError):
    """Raised when quality assessment fails."""

    def __init__(self, assessment_type: str, message: str, **kwargs) -> None:
        self.assessment_type = assessment_type
        details = {"assessment_type": assessment_type, **kwargs.get("details", {})}
        suggestions = [
            f"Review {assessment_type} assessment criteria",
            "Check response and context quality",
            "Verify assessment model availability",
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class HallucinationDetectedError(RAGQualityError):
    """Raised when potential hallucination is detected in responses."""

    def __init__(
        self, confidence: float, fabricated_claims: list[str], **kwargs
    ) -> None:
        self.confidence = confidence
        self.fabricated_claims = fabricated_claims
        details = {
            "confidence": confidence,
            "fabricated_claims": fabricated_claims,
            **kwargs.get("details", {}),
        }
        suggestions = [
            "Review source documents for accuracy",
            "Adjust LLM temperature settings",
            "Improve context quality",
        ]
        message = f"Potential hallucination detected (confidence: {confidence:.2f})"
        super().__init__(message, details=details, suggestions=suggestions)


# Memory and resource exceptions


class MemoryLimitExceededError(RAGMemoryError):
    """Raised when memory limits are exceeded."""

    def __init__(self, current_usage: int, memory_limit: int, **kwargs) -> None:
        self.current_usage = current_usage
        self.memory_limit = memory_limit
        details = {
            "current_usage_mb": current_usage,
            "memory_limit_mb": memory_limit,
            "usage_percentage": (current_usage / memory_limit) * 100,
            **kwargs.get("details", {}),
        }
        suggestions = [
            "Enable streaming processing mode",
            "Reduce batch sizes",
            "Clean up unused objects",
        ]
        message = (
            f"Memory limit exceeded: {current_usage}MB used of {memory_limit}MB limit"
        )
        super().__init__(message, details=details, suggestions=suggestions)


class ConcurrencyLimitError(RAGBaseException):
    """Raised when concurrency limits are exceeded."""

    def __init__(self, active_operations: int, max_concurrent: int, **kwargs) -> None:
        self.active_operations = active_operations
        self.max_concurrent = max_concurrent
        details = {
            "active_operations": active_operations,
            "max_concurrent": max_concurrent,
            **kwargs.get("details", {}),
        }
        suggestions = [
            "Wait for current operations to complete",
            "Increase concurrency limits",
            "Implement operation queuing",
        ]
        message = f"Concurrency limit exceeded: {active_operations} active (max: {max_concurrent})"
        super().__init__(message, details=details, suggestions=suggestions)


# Utility functions for exception handling


def create_processing_error(
    document_id: int, stage: str, original_exception: Exception
) -> DocumentProcessingError:
    """Create a DocumentProcessingError from an original exception."""
    return DocumentProcessingError(
        document_id=document_id,
        stage=stage,
        message=f"Processing failed at stage '{stage}': {str(original_exception)}",
        details={"original_error": str(original_exception)},
    )


def create_query_error(
    query: str, document_id: int | None, original_exception: Exception
) -> QueryProcessingError:
    """Create a QueryProcessingError from an original exception."""
    return QueryProcessingError(
        query=query,
        document_id=document_id,
        message=f"Query processing failed: {str(original_exception)}",
        details={"original_error": str(original_exception)},
    )


def is_retriable_error(exception: RAGBaseException) -> bool:
    """Check if an exception represents a retriable error."""
    retriable_types = [
        RAGTimeoutError,
        LLMServiceError,
        VectorStoreError,
        RAGPerformanceError,
    ]
    return any(isinstance(exception, error_type) for error_type in retriable_types)


def get_error_recovery_strategy(exception: RAGBaseException) -> dict[str, Any]:
    """Get recovery strategy for an exception."""
    if isinstance(exception, MemoryLimitExceededError):
        return {
            "strategy": "reduce_memory_usage",
            "actions": ["enable_streaming", "reduce_batch_size", "cleanup_cache"],
        }
    elif isinstance(exception, PerformanceDegradationError):
        return {
            "strategy": "performance_optimization",
            "actions": ["scale_resources", "optimize_queries", "enable_caching"],
        }
    elif isinstance(exception, StorageQuotaExceededError):
        return {
            "strategy": "storage_cleanup",
            "actions": ["cleanup_temp_files", "remove_old_indexes", "compress_data"],
        }
    elif isinstance(exception, ConcurrencyLimitError):
        return {
            "strategy": "queue_operations",
            "actions": ["implement_queue", "increase_workers", "batch_requests"],
        }
    else:
        return {
            "strategy": "generic_retry",
            "actions": ["retry_operation", "check_configuration", "validate_inputs"],
        }


# Export all exceptions
__all__ = [
    "RAGBaseException",
    "RAGProcessingError",
    "RAGIndexError",
    "RAGQueryError",
    "RAGRecoveryError",
    "RAGFileError",
    "RAGStorageError",
    "RAGVectorError",
    "RAGQualityError",
    "RAGPerformanceError",
    "RAGMemoryError",
    "RAGTimeoutError",
    "RAGConfigurationError",
    "RAGValidationError",
    "RAGAuthenticationError",
    "RAGAuthorizationError",
    "DocumentProcessingError",
    "IndexBuildError",
    "QueryProcessingError",
    "VectorStoreError",
    "LLMServiceError",
    "ContextBuildError",
    "FileOperationError",
    "StorageQuotaExceededError",
    "PerformanceDegradationError",
    "QualityAssessmentError",
    "HallucinationDetectedError",
    "MemoryLimitExceededError",
    "ConcurrencyLimitError",
    "create_processing_error",
    "create_query_error",
    "is_retriable_error",
    "get_error_recovery_strategy",
]
