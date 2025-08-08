"""
Error Handling Middleware
Centralized error handling middleware for FastAPI application with comprehensive
error logging, monitoring, and response standardization.
"""

import json
import logging
import time
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from ..error_handling import (
    APIException,
    ErrorLogger,
    ValidationException,
    SecurityException,
    SystemException,
    create_error_response,
    ErrorCode,
    ErrorCategory,
    ErrorDetail,
    StandardErrorResponse
)
from ..models import SecurityValidationError, ValidationErrorResponse, SecurityValidationErrorResponse


logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling middleware that catches all unhandled exceptions
    and converts them to standardized error responses.
    """
    
    def __init__(self, app: FastAPI, include_debug_info: bool = False):
        super().__init__(app)
        self.include_debug_info = include_debug_info
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle any exceptions that occur."""
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Log successful requests (optional, for monitoring)
            processing_time = time.time() - start_time
            if response.status_code >= 400:
                logger.warning(
                    f"Request failed: {request.method} {request.url} "
                    f"-> {response.status_code} ({processing_time:.3f}s)"
                )
            
            return response
            
        except Exception as exc:
            # Calculate processing time for error logging
            processing_time = time.time() - start_time
            
            # Log the error with request context
            logger.error(
                f"Unhandled exception in middleware: {request.method} {request.url} "
                f"-> {type(exc).__name__}: {str(exc)} ({processing_time:.3f}s)",
                exc_info=True
            )
            
            # Create standardized error response
            return create_error_response(
                exception=exc,
                request=request,
                include_debug_info=self.include_debug_info
            )


class ValidationErrorHandler:
    """Handler for Pydantic validation errors."""
    
    @staticmethod
    def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle FastAPI request validation errors."""
        
        # Convert Pydantic errors to our standardized format
        error_details = []
        
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
            error_detail = ErrorDetail(
                field=field_path,
                constraint=error.get("type", ""),
                provided_value=str(error.get("input", ""))[:100],  # Limit length
                expected_format=error.get("msg", ""),
                help_text=ValidationErrorHandler._get_help_text(error.get("type", ""))
            )
            error_details.append(error_detail)
        
        # Create validation exception
        validation_exc = ValidationException(
            message=f"Request validation failed with {len(error_details)} error(s)",
            details=error_details
        )
        
        return create_error_response(validation_exc, request)
    
    @staticmethod
    def handle_pydantic_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic model validation errors."""
        
        error_details = []
        
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
            error_detail = ErrorDetail(
                field=field_path,
                constraint=error.get("type", ""),
                provided_value=str(error.get("input", ""))[:100],
                expected_format=error.get("msg", ""),
                help_text=ValidationErrorHandler._get_help_text(error.get("type", ""))
            )
            error_details.append(error_detail)
        
        validation_exc = ValidationException(
            message=f"Data validation failed with {len(error_details)} error(s)",
            details=error_details
        )
        
        return create_error_response(validation_exc, request)
    
    @staticmethod
    def handle_security_validation_error(request: Request, exc: SecurityValidationError) -> JSONResponse:
        """Handle custom security validation errors."""
        
        error_detail = ErrorDetail(
            field=exc.field,
            constraint="Security validation failed",
            help_text="Please ensure your input doesn't contain potentially dangerous patterns"
        )
        
        # Determine security violation type from the error message
        security_type = "general"
        if "sql" in str(exc).lower():
            security_type = "sql_injection"
        elif "xss" in str(exc).lower() or "script" in str(exc).lower():
            security_type = "xss_attempt"
        elif "path" in str(exc).lower() or "traversal" in str(exc).lower():
            security_type = "path_traversal"
        
        security_exc = SecurityException(
            message=str(exc),
            security_type=security_type,
            details=error_detail
        )
        
        return create_error_response(security_exc, request)
    
    @staticmethod
    def _get_help_text(error_type: str) -> str:
        """Get helpful text for common validation error types."""
        
        help_texts = {
            "missing": "This field is required and cannot be empty",
            "string_too_short": "The provided value is too short",
            "string_too_long": "The provided value is too long",
            "value_error": "The provided value is not valid",
            "type_error": "The provided value is not the correct type",
            "greater_than": "The value must be greater than the minimum",
            "less_than": "The value must be less than the maximum",
            "greater_than_equal": "The value must be greater than or equal to the minimum",
            "less_than_equal": "The value must be less than or equal to the maximum",
            "string_pattern_mismatch": "The value doesn't match the required format",
            "enum": "The value must be one of the allowed options",
            "json_invalid": "The provided JSON is not valid"
        }
        
        return help_texts.get(error_type, "Please check the provided value and try again")


def setup_error_handlers(app: FastAPI) -> None:
    """Set up all error handlers for the FastAPI application."""
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        """Handle custom API exceptions."""
        return create_error_response(exc, request)
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        return create_error_response(exc, request)
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle request validation errors."""
        return ValidationErrorHandler.handle_request_validation_error(request, exc)
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""
        return ValidationErrorHandler.handle_pydantic_validation_error(request, exc)
    
    @app.exception_handler(SecurityValidationError)
    async def security_validation_exception_handler(request: Request, exc: SecurityValidationError) -> JSONResponse:
        """Handle security validation errors."""
        return ValidationErrorHandler.handle_security_validation_error(request, exc)
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle ValueError exceptions."""
        # Check if this is actually a security validation error
        if isinstance(exc, SecurityValidationError):
            return ValidationErrorHandler.handle_security_validation_error(request, exc)
        
        # Otherwise treat as general validation error
        validation_exc = ValidationException(
            message=f"Invalid value provided: {str(exc)}",
            details=ErrorDetail(
                constraint="Invalid value",
                help_text="Please check the provided value and ensure it meets the requirements"
            )
        )
        return create_error_response(validation_exc, request)
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all other unhandled exceptions."""
        return create_error_response(exc, request, include_debug_info=False)


class ErrorMetricsCollector:
    """Collect error metrics for monitoring and alerting."""
    
    def __init__(self):
        self.error_counts = {}
        self.error_rates = {}
        self.start_time = time.time()
    
    def record_error(self, error_code: str, category: str, status_code: int):
        """Record an error occurrence."""
        key = f"{error_code}:{category}:{status_code}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
    
    def get_error_summary(self) -> dict:
        """Get error summary for monitoring."""
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "total_errors": sum(self.error_counts.values()),
            "error_breakdown": self.error_counts,
            "error_rate_per_hour": sum(self.error_counts.values()) / (uptime / 3600) if uptime > 0 else 0
        }
    
    def reset_metrics(self):
        """Reset error metrics."""
        self.error_counts.clear()
        self.start_time = time.time()


# Global error metrics collector
error_metrics = ErrorMetricsCollector()


class ErrorMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting error metrics and monitoring."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect error metrics."""
        
        try:
            response = await call_next(request)
            
            # Record error metrics for 4xx and 5xx responses
            if response.status_code >= 400:
                # Try to extract error information from response
                if hasattr(response, 'body'):
                    try:
                        body = json.loads(response.body.decode())
                        if 'error' in body:
                            error_info = body['error']
                            error_metrics.record_error(
                                error_info.get('code', 'UNKNOWN'),
                                error_info.get('category', 'unknown'),
                                response.status_code
                            )
                    except (json.JSONDecodeError, AttributeError):
                        # Fallback for non-JSON responses
                        error_metrics.record_error(
                            'HTTP_ERROR',
                            'unknown',
                            response.status_code
                        )
            
            return response
            
        except Exception as exc:
            # Record exception metrics
            if isinstance(exc, APIException):
                error_metrics.record_error(
                    exc.code.value,
                    exc.category.value,
                    exc.status_code
                )
            else:
                error_metrics.record_error(
                    'UNHANDLED_EXCEPTION',
                    'system',
                    500
                )
            
            raise  # Re-raise for normal error handling


def add_error_monitoring_endpoint(app: FastAPI) -> None:
    """Add endpoint for retrieving error metrics."""
    
    @app.get("/admin/error-metrics")
    async def get_error_metrics():
        """Get current error metrics (admin only)."""
        return error_metrics.get_error_summary()
    
    @app.post("/admin/error-metrics/reset")
    async def reset_error_metrics():
        """Reset error metrics (admin only)."""
        error_metrics.reset_metrics()
        return {"message": "Error metrics reset successfully"}


def setup_comprehensive_error_handling(app: FastAPI, include_debug_info: bool = False) -> None:
    """Set up comprehensive error handling for the application."""
    
    # Add error handling middleware
    app.add_middleware(ErrorHandlingMiddleware, include_debug_info=include_debug_info)
    
    # Add error monitoring middleware  
    app.add_middleware(ErrorMonitoringMiddleware)
    
    # Set up exception handlers
    setup_error_handlers(app)
    
    # Add error monitoring endpoints (optional)
    add_error_monitoring_endpoint(app)
    
    logger.info("Comprehensive error handling system initialized")