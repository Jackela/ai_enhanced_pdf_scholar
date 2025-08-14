"""
Unified Error Handling System
Comprehensive error response standardization with consistent HTTP status codes,
error categorization, correlation IDs, and structured logging.
"""

import logging
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# Configure error handling logger
error_logger = logging.getLogger("api.errors")


class ErrorCategory(str, Enum):
    """Error categorization for better error handling and monitoring."""

    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    SECURITY = "security"
    NOT_FOUND = "not_found"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMITING = "rate_limiting"
    EXTERNAL_SERVICE = "external_service"


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Validation Errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FIELD_FORMAT = "INVALID_FIELD_FORMAT"

    # Authentication Errors (401)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # Authorization Errors (403)
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_PRIVILEGES = "INSUFFICIENT_PRIVILEGES"

    # Not Found Errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    ENDPOINT_NOT_FOUND = "ENDPOINT_NOT_FOUND"

    # Conflict Errors (409)
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    VERSION_CONFLICT = "VERSION_CONFLICT"

    # Unprocessable Entity (422)
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INVALID_OPERATION = "INVALID_OPERATION"
    DEPENDENCY_CONSTRAINT = "DEPENDENCY_CONSTRAINT"

    # Rate Limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # System Errors (500)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Security Errors
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    SQL_INJECTION_ATTEMPT = "SQL_INJECTION_ATTEMPT"
    XSS_ATTEMPT = "XSS_ATTEMPT"
    PATH_TRAVERSAL_ATTEMPT = "PATH_TRAVERSAL_ATTEMPT"


class ErrorDetail(BaseModel):
    """Detailed error information for specific fields or constraints."""

    field: Optional[str] = Field(None, description="Field that caused the error")
    constraint: Optional[str] = Field(None, description="Constraint that was violated")
    provided_value: Optional[str] = Field(None, description="Value that caused the error (sanitized)")
    expected_format: Optional[str] = Field(None, description="Expected format or value")
    help_text: Optional[str] = Field(None, description="Helpful guidance for fixing the error")


class ErrorContext(BaseModel):
    """Additional context information for debugging and monitoring."""

    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    endpoint: Optional[str] = Field(None, description="API endpoint where error occurred")
    method: Optional[str] = Field(None, description="HTTP method")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    trace_id: Optional[str] = Field(None, description="Distributed tracing ID")


class StandardErrorResponse(BaseModel):
    """Unified error response model with comprehensive information."""

    success: bool = Field(False, description="Always false for error responses")
    error: Dict[str, Any] = Field(..., description="Error information")

    @classmethod
    def create(
        cls,
        code: ErrorCode,
        message: str,
        category: ErrorCategory,
        status_code: int,
        correlation_id: Optional[str] = None,
        details: Optional[Union[ErrorDetail, List[ErrorDetail]]] = None,
        context: Optional[ErrorContext] = None,
        help_url: Optional[str] = None,
        localization: Optional[Dict[str, str]] = None
    ) -> "StandardErrorResponse":
        """Create a standardized error response."""

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        error_data = {
            "code": code.value,
            "message": message,
            "category": category.value,
            "status_code": status_code,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat()
        }

        if details:
            if isinstance(details, list):
                error_data["details"] = [detail.dict() for detail in details]
            else:
                error_data["details"] = details.dict()

        if context:
            error_data["context"] = context.dict()

        if help_url:
            error_data["help_url"] = help_url

        if localization:
            error_data["localization"] = localization

        return cls(error=error_data)


class APIException(HTTPException):
    """Base API exception with enhanced error information."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        category: ErrorCategory,
        status_code: int,
        details: Optional[Union[ErrorDetail, List[ErrorDetail]]] = None,
        correlation_id: Optional[str] = None,
        help_url: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.category = category
        self.details = details
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.help_url = help_url

        super().__init__(status_code=status_code, detail=message)


class ValidationException(APIException):
    """Validation error exception (400 Bad Request)."""

    def __init__(
        self,
        message: str = "Request validation failed",
        details: Optional[Union[ErrorDetail, List[ErrorDetail]]] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/errors/validation"
        )


class SecurityException(APIException):
    """Security violation exception (400 Bad Request)."""

    def __init__(
        self,
        message: str = "Security validation failed",
        security_type: str = "general",
        details: Optional[Union[ErrorDetail, List[ErrorDetail]]] = None,
        correlation_id: Optional[str] = None
    ):
        code_mapping = {
            "sql_injection": ErrorCode.SQL_INJECTION_ATTEMPT,
            "xss_attempt": ErrorCode.XSS_ATTEMPT,
            "path_traversal": ErrorCode.PATH_TRAVERSAL_ATTEMPT,
            "general": ErrorCode.SECURITY_VIOLATION
        }

        super().__init__(
            code=code_mapping.get(security_type, ErrorCode.SECURITY_VIOLATION),
            message=message,
            category=ErrorCategory.SECURITY,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/security/validation"
        )


class AuthenticationException(APIException):
    """Authentication required exception (401 Unauthorized)."""

    def __init__(
        self,
        message: str = "Authentication required",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/auth/getting-started"
        )


class AuthorizationException(APIException):
    """Authorization failed exception (403 Forbidden)."""

    def __init__(
        self,
        message: str = "Permission denied",
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            code=ErrorCode.PERMISSION_DENIED,
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            status_code=status.HTTP_403_FORBIDDEN,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/auth/permissions"
        )


class ResourceNotFoundException(APIException):
    """Resource not found exception (404 Not Found)."""

    def __init__(
        self,
        resource_type: str = "resource",
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        if message is None:
            if resource_id:
                message = f"{resource_type.title()} with ID '{resource_id}' not found"
            else:
                message = f"{resource_type.title()} not found"

        code_mapping = {
            "document": ErrorCode.DOCUMENT_NOT_FOUND,
            "file": ErrorCode.FILE_NOT_FOUND,
            "endpoint": ErrorCode.ENDPOINT_NOT_FOUND
        }

        super().__init__(
            code=code_mapping.get(resource_type.lower(), ErrorCode.RESOURCE_NOT_FOUND),
            message=message,
            category=ErrorCategory.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/errors/not-found"
        )


class ConflictException(APIException):
    """Resource conflict exception (409 Conflict)."""

    def __init__(
        self,
        message: str = "Resource conflict detected",
        resource_type: str = "resource",
        conflict_type: str = "duplicate",
        correlation_id: Optional[str] = None
    ):
        code_mapping = {
            "duplicate": ErrorCode.DUPLICATE_RESOURCE,
            "version": ErrorCode.VERSION_CONFLICT
        }

        super().__init__(
            code=code_mapping.get(conflict_type, ErrorCode.RESOURCE_CONFLICT),
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/errors/conflicts"
        )


class BusinessLogicException(APIException):
    """Business logic violation exception (422 Unprocessable Entity)."""

    def __init__(
        self,
        message: str = "Business rule violation",
        rule_type: str = "general",
        details: Optional[Union[ErrorDetail, List[ErrorDetail]]] = None,
        correlation_id: Optional[str] = None
    ):
        code_mapping = {
            "invalid_operation": ErrorCode.INVALID_OPERATION,
            "dependency": ErrorCode.DEPENDENCY_CONSTRAINT,
            "general": ErrorCode.BUSINESS_RULE_VIOLATION
        }

        super().__init__(
            code=code_mapping.get(rule_type, ErrorCode.BUSINESS_RULE_VIOLATION),
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/errors/business-rules"
        )


class RateLimitException(APIException):
    """Rate limit exceeded exception (429 Too Many Requests)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            category=ErrorCategory.RATE_LIMITING,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/rate-limiting"
        )

        if retry_after:
            self.headers = {"Retry-After": str(retry_after)}


class SystemException(APIException):
    """System error exception (500 Internal Server Error)."""

    def __init__(
        self,
        message: str = "An internal server error occurred",
        error_type: str = "general",
        correlation_id: Optional[str] = None,
        include_traceback: bool = False
    ):
        code_mapping = {
            "database": ErrorCode.DATABASE_ERROR,
            "external_service": ErrorCode.EXTERNAL_SERVICE_ERROR,
            "configuration": ErrorCode.CONFIGURATION_ERROR,
            "general": ErrorCode.INTERNAL_SERVER_ERROR
        }

        details = None
        if include_traceback:
            details = ErrorDetail(
                field="traceback",
                provided_value=traceback.format_exc(),
                help_text="This information is only included in development mode"
            )

        super().__init__(
            code=code_mapping.get(error_type, ErrorCode.INTERNAL_SERVER_ERROR),
            message=message,
            category=ErrorCategory.SYSTEM,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            correlation_id=correlation_id,
            help_url="https://docs.api.com/errors/system-errors"
        )


class ErrorLogger:
    """Structured error logging with correlation IDs."""

    @staticmethod
    def log_error(
        exception: Union[APIException, Exception],
        request: Optional[Request] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ):
        """Log error with structured information and correlation ID."""

        correlation_id = getattr(exception, 'correlation_id', str(uuid.uuid4()))

        log_data = {
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            "exception_type": type(exception).__name__,
            "error_message": str(exception)
        }

        if isinstance(exception, APIException):
            log_data.update({
                "error_code": exception.code.value,
                "category": exception.category.value,
                "status_code": exception.status_code
            })

        if request:
            log_data.update({
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            })

        if extra_context:
            log_data["extra_context"] = extra_context

        # Log with appropriate level based on error type
        if isinstance(exception, APIException):
            if exception.category in [ErrorCategory.SYSTEM, ErrorCategory.EXTERNAL_SERVICE]:
                error_logger.error("System error occurred", extra=log_data)
            elif exception.category == ErrorCategory.SECURITY:
                error_logger.warning("Security violation detected", extra=log_data)
            else:
                error_logger.info("Client error occurred", extra=log_data)
        else:
            error_logger.error("Unhandled exception occurred", extra=log_data, exc_info=True)


def create_error_response(
    exception: Union[APIException, HTTPException, Exception],
    request: Optional[Request] = None,
    include_debug_info: bool = False
) -> JSONResponse:
    """Create a standardized error response from any exception."""

    correlation_id = str(uuid.uuid4())

    # Handle APIException (our custom exceptions)
    if isinstance(exception, APIException):
        ErrorLogger.log_error(exception, request)

        error_response = StandardErrorResponse.create(
            code=exception.code,
            message=exception.message,
            category=exception.category,
            status_code=exception.status_code,
            correlation_id=exception.correlation_id,
            details=exception.details,
            help_url=exception.help_url
        )

        return JSONResponse(
            status_code=exception.status_code,
            content=error_response.dict(),
            headers=getattr(exception, 'headers', None)
        )

    # Handle FastAPI HTTPException
    elif isinstance(exception, HTTPException):
        ErrorLogger.log_error(exception, request)

        # Map status code to appropriate error code and category
        status_code = exception.status_code
        if status_code == 404:
            code = ErrorCode.RESOURCE_NOT_FOUND
            category = ErrorCategory.NOT_FOUND
        elif status_code == 401:
            code = ErrorCode.AUTHENTICATION_REQUIRED
            category = ErrorCategory.AUTHENTICATION
        elif status_code == 403:
            code = ErrorCode.PERMISSION_DENIED
            category = ErrorCategory.AUTHORIZATION
        elif status_code == 409:
            code = ErrorCode.RESOURCE_CONFLICT
            category = ErrorCategory.BUSINESS_LOGIC
        elif status_code == 422:
            code = ErrorCode.BUSINESS_RULE_VIOLATION
            category = ErrorCategory.BUSINESS_LOGIC
        elif status_code == 429:
            code = ErrorCode.RATE_LIMIT_EXCEEDED
            category = ErrorCategory.RATE_LIMITING
        elif 400 <= status_code < 500:
            code = ErrorCode.VALIDATION_ERROR
            category = ErrorCategory.VALIDATION
        else:
            code = ErrorCode.INTERNAL_SERVER_ERROR
            category = ErrorCategory.SYSTEM

        error_response = StandardErrorResponse.create(
            code=code,
            message=exception.detail,
            category=category,
            status_code=status_code,
            correlation_id=correlation_id
        )

        return JSONResponse(
            status_code=status_code,
            content=error_response.dict(),
            headers=exception.headers
        )

    # Handle unexpected exceptions
    else:
        ErrorLogger.log_error(exception, request)

        # In production, don't expose internal error details
        message = "An unexpected error occurred"
        details = None

        if include_debug_info:
            message = f"Unexpected error: {str(exception)}"
            details = ErrorDetail(
                field="exception_details",
                provided_value=type(exception).__name__,
                help_text="This detailed information is only available in debug mode"
            )

        error_response = StandardErrorResponse.create(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            category=ErrorCategory.SYSTEM,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            correlation_id=correlation_id,
            details=details
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.dict()
        )


# Common error templates for quick use
class ErrorTemplates:
    """Pre-configured error templates for common scenarios."""

    @staticmethod
    def document_not_found(document_id: Union[int, str]) -> ResourceNotFoundException:
        """Document not found error."""
        return ResourceNotFoundException(
            resource_type="document",
            resource_id=str(document_id),
            message=f"Document with ID '{document_id}' was not found"
        )

    @staticmethod
    def file_not_found(filename: str) -> ResourceNotFoundException:
        """File not found error."""
        return ResourceNotFoundException(
            resource_type="file",
            resource_id=filename,
            message=f"File '{filename}' was not found or is not accessible"
        )

    @staticmethod
    def duplicate_document(filename: str) -> ConflictException:
        """Duplicate document error."""
        return ConflictException(
            message=f"Document '{filename}' already exists in the library",
            resource_type="document",
            conflict_type="duplicate"
        )

    @staticmethod
    def invalid_file_type(provided_type: str, allowed_types: List[str]) -> ValidationException:
        """Invalid file type error."""
        return ValidationException(
            message=f"File type '{provided_type}' is not allowed",
            details=ErrorDetail(
                field="content_type",
                provided_value=provided_type,
                expected_format=f"One of: {', '.join(allowed_types)}",
                help_text="Only PDF files are currently supported"
            )
        )

    @staticmethod
    def file_too_large(file_size: int, max_size: int) -> ValidationException:
        """File too large error."""
        return ValidationException(
            message=f"File size exceeds maximum allowed size",
            details=ErrorDetail(
                field="file_size",
                provided_value=f"{file_size} bytes",
                expected_format=f"Maximum {max_size} bytes",
                help_text="Try compressing your PDF or splitting it into smaller files"
            )
        )

    @staticmethod
    def missing_api_key() -> SystemException:
        """Missing API key configuration error."""
        return SystemException(
            message="RAG service is not available due to missing API key configuration",
            error_type="configuration"
        )

    @staticmethod
    def database_error(operation: str) -> SystemException:
        """Database operation error."""
        return SystemException(
            message=f"Database operation failed: {operation}",
            error_type="database"
        )

    @staticmethod
    def index_not_ready(document_id: int) -> BusinessLogicException:
        """Vector index not ready error."""
        return BusinessLogicException(
            message="Document vector index is not ready for querying",
            rule_type="invalid_operation",
            details=ErrorDetail(
                field="document_id",
                provided_value=str(document_id),
                help_text="Build the vector index first before querying this document"
            )
        )