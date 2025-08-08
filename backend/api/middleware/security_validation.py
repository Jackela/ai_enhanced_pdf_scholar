"""
Security Validation Middleware
Handles security validation errors and provides consistent error responses.
"""

import logging
from typing import Callable, Any

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.models import (
    SecurityValidationError,
    SecurityValidationErrorResponse, 
    ValidationErrorResponse,
    log_security_event
)

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security.validation")


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle security validation errors."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle security validation errors."""
        
        try:
            response = await call_next(request)
            return response
            
        except SecurityValidationError as e:
            # Log the security event
            log_security_event(
                event_type="security_validation_failure",
                field=e.field,
                value=str(request.url),
                details=f"Pattern: {e.pattern}, Client: {request.client.host if request.client else 'unknown'}"
            )
            
            # Create security validation error response
            error_response = SecurityValidationErrorResponse.from_security_error(e)
            
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response.dict()
            )
            
        except ValidationError as e:
            # Handle Pydantic validation errors
            logger.warning(f"Validation error: {e}")
            
            error_response = ValidationErrorResponse.from_pydantic_error(e)
            
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response.dict()
            )
            
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error in security middleware: {e}", exc_info=True)
            # Let other middleware handle it
            raise


def create_security_exception_handlers() -> dict[Any, Callable]:
    """Create exception handlers for security validation errors."""
    
    async def security_validation_handler(request: Request, exc: SecurityValidationError) -> JSONResponse:
        """Handle SecurityValidationError."""
        # Log the security event
        log_security_event(
            event_type="security_validation_failure",
            field=exc.field,
            value=str(request.url),
            details=f"Pattern: {exc.pattern}, Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Create security validation error response
        error_response = SecurityValidationErrorResponse.from_security_error(exc)
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.dict()
        )
    
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic ValidationError."""
        logger.warning(f"Validation error for {request.url}: {exc}")
        
        error_response = ValidationErrorResponse.from_pydantic_error(exc)
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.dict()
        )
    
    return {
        SecurityValidationError: security_validation_handler,
        ValidationError: validation_error_handler,
    }


def log_security_metrics(event_type: str, field: str, client_ip: str = None):
    """Log security metrics for monitoring."""
    metrics_logger = logging.getLogger("security.metrics")
    
    metrics_data = {
        "event_type": event_type,
        "field": field,
        "client_ip": client_ip,
        "timestamp": logging.Formatter().formatTime(logging.LogRecord(
            name="security", level=logging.INFO, pathname="", lineno=0, 
            msg="", args=(), exc_info=None
        ))
    }
    
    metrics_logger.info(f"SECURITY_METRIC: {metrics_data}")