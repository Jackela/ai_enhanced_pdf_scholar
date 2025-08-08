# Unified Error Handling System Guide

## Overview

This document describes the comprehensive unified error handling system implemented for the AI Enhanced PDF Scholar API. The system provides consistent error responses, proper HTTP status codes, correlation IDs for tracing, and structured logging.

## Key Components

### 1. Error Response Structure

All API errors now follow this standardized format:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid data",
    "category": "validation",
    "status_code": 400,
    "correlation_id": "req_123456789",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "field": "email",
      "constraint": "Invalid email format",
      "expected_format": "Valid email address",
      "help_text": "Please provide a valid email address"
    },
    "help_url": "https://docs.api.com/errors/validation"
  }
}
```

### 2. Error Categories

- **validation**: Input validation errors (400)
- **business_logic**: Business rule violations (409, 422)
- **system**: Internal system errors (500)
- **security**: Security validation failures (400)
- **not_found**: Resource not found (404)
- **authentication**: Authentication required (401)
- **authorization**: Permission denied (403)
- **rate_limiting**: Rate limits exceeded (429)
- **external_service**: External API failures (502, 503)

### 3. HTTP Status Code Mapping

#### 400 Bad Request
- `VALIDATION_ERROR`: Request validation failed
- `MALFORMED_REQUEST`: Malformed request structure
- `INVALID_FILE_TYPE`: Unsupported file type
- `SECURITY_VIOLATION`: Security validation failed

#### 401 Unauthorized
- `AUTHENTICATION_REQUIRED`: Authentication required
- `INVALID_CREDENTIALS`: Invalid credentials provided
- `TOKEN_EXPIRED`: Authentication token expired

#### 403 Forbidden
- `PERMISSION_DENIED`: Permission denied
- `INSUFFICIENT_PRIVILEGES`: Insufficient privileges

#### 404 Not Found
- `RESOURCE_NOT_FOUND`: Generic resource not found
- `DOCUMENT_NOT_FOUND`: Document not found
- `FILE_NOT_FOUND`: File not found
- `ENDPOINT_NOT_FOUND`: API endpoint not found

#### 409 Conflict
- `RESOURCE_CONFLICT`: Resource conflict
- `DUPLICATE_RESOURCE`: Duplicate resource exists
- `VERSION_CONFLICT`: Version conflict

#### 422 Unprocessable Entity
- `BUSINESS_RULE_VIOLATION`: Business logic violation
- `INVALID_OPERATION`: Invalid operation
- `DEPENDENCY_CONSTRAINT`: Dependency constraint violated

#### 429 Too Many Requests
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `QUOTA_EXCEEDED`: Usage quota exceeded

#### 500 Internal Server Error
- `INTERNAL_SERVER_ERROR`: Generic server error
- `DATABASE_ERROR`: Database operation failed
- `EXTERNAL_SERVICE_ERROR`: External service error
- `CONFIGURATION_ERROR`: Configuration error

## Usage Examples

### 1. Basic Exception Usage

```python
from backend.api.error_handling import ValidationException, ErrorDetail

# Simple validation error
raise ValidationException("Invalid email format")

# Validation error with details
raise ValidationException(
    message="Request validation failed",
    details=ErrorDetail(
        field="email",
        constraint="Invalid format",
        provided_value="invalid-email",
        expected_format="user@example.com",
        help_text="Please provide a valid email address"
    )
)
```

### 2. Using Error Templates

```python
from backend.api.error_handling import ErrorTemplates

# Document not found
raise ErrorTemplates.document_not_found(document_id)

# File too large
raise ErrorTemplates.file_too_large(file_size, max_size)

# Invalid file type
raise ErrorTemplates.invalid_file_type("text/plain", ["application/pdf"])

# Duplicate document
raise ErrorTemplates.duplicate_document("document.pdf")
```

### 3. Custom Business Logic Errors

```python
from backend.api.error_handling import BusinessLogicException, ErrorDetail

# Business rule violation
raise BusinessLogicException(
    message="Cannot delete document with active references",
    rule_type="dependency",
    details=ErrorDetail(
        field="document_id",
        constraint="Has active references",
        help_text="Remove all references before deleting this document"
    )
)
```

### 4. System Errors

```python
from backend.api.error_handling import SystemException

# Database error
raise SystemException(
    message="Database operation failed",
    error_type="database"
)

# Configuration error
raise SystemException(
    message="API key not configured",
    error_type="configuration"
)
```

## Error Logging and Monitoring

### Structured Logging

All errors are logged with structured information:

```json
{
  "correlation_id": "req_123456789",
  "timestamp": "2024-01-15T10:30:00Z",
  "exception_type": "ValidationException",
  "message": "Invalid email format",
  "error_code": "VALIDATION_ERROR",
  "category": "validation",
  "status_code": 400,
  "method": "POST",
  "url": "https://api.example.com/users",
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

### Error Metrics

The system automatically collects error metrics:

- Total error count by type
- Error rates over time
- Most common error types
- Error breakdown by endpoint
- Client IP error patterns

Access metrics via:
- `GET /api/admin/error-metrics` - Current error metrics
- `POST /api/admin/error-metrics/reset` - Reset metrics

## Middleware Integration

The error handling system is automatically integrated via middleware:

```python
from backend.api.middleware.error_handling import setup_comprehensive_error_handling

# In main.py
setup_comprehensive_error_handling(app, include_debug_info=False)
```

### Features Provided by Middleware

1. **Automatic Exception Handling**: Catches all unhandled exceptions
2. **Validation Error Processing**: Converts Pydantic errors to standardized format
3. **Security Error Detection**: Identifies and properly categorizes security violations
4. **Error Metrics Collection**: Automatically tracks error statistics
5. **Correlation ID Generation**: Assigns unique IDs for request tracing
6. **Structured Logging**: Logs all errors with context information

## Security Considerations

### Security Error Handling

Security violations are automatically detected and logged:

```python
# These are handled automatically by the system
- SQL injection attempts
- XSS attacks
- Path traversal attempts
- Invalid file uploads
- Suspicious input patterns
```

### Error Information Disclosure

- In production: Generic error messages to prevent information leakage
- In development: Detailed error information for debugging
- Security events: Always logged with full context for analysis
- Sensitive data: Automatically sanitized in error responses

## Best Practices

### 1. Use Appropriate Error Types

```python
# Good: Specific error type
raise ResourceNotFoundException("document", document_id)

# Avoid: Generic HTTP exceptions
raise HTTPException(404, "Not found")
```

### 2. Provide Helpful Error Messages

```python
# Good: Actionable error message
raise ValidationException(
    "File size exceeds limit",
    details=ErrorDetail(
        field="file_size",
        help_text="Try compressing your PDF or splitting into smaller files"
    )
)

# Avoid: Vague error messages
raise ValidationException("Invalid file")
```

### 3. Use Error Templates for Common Cases

```python
# Good: Use predefined templates
raise ErrorTemplates.document_not_found(document_id)

# Avoid: Manual error construction
raise ResourceNotFoundException("document", str(document_id), "Document not found")
```

### 4. Include Context in System Errors

```python
# Good: Specific context
raise SystemException(
    "Failed to process document upload",
    error_type="external_service"
)

# Avoid: Generic system errors
raise SystemException("Something went wrong")
```

## Migration from Old Error Handling

### Before (Old System)

```python
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Document not found"
)
```

### After (New System)

```python
raise ErrorTemplates.document_not_found(document_id)
```

### Benefits of Migration

1. **Consistent Format**: All errors follow the same structure
2. **Better Debugging**: Correlation IDs and structured logging
3. **Client-Friendly**: Helpful error messages and guidance
4. **Security**: Automatic detection and proper handling of security issues
5. **Monitoring**: Built-in error metrics and alerting capabilities
6. **Maintainability**: Centralized error handling reduces code duplication

## Testing Error Handling

### Example Test Cases

```python
def test_document_not_found_error():
    """Test document not found error format."""
    response = client.get("/api/documents/99999")
    assert response.status_code == 404
    
    error_data = response.json()
    assert error_data["success"] is False
    assert error_data["error"]["code"] == "DOCUMENT_NOT_FOUND"
    assert error_data["error"]["category"] == "not_found"
    assert "correlation_id" in error_data["error"]
    assert error_data["error"]["help_url"] is not None

def test_validation_error_format():
    """Test validation error with details."""
    response = client.post("/api/documents/upload", files={})
    assert response.status_code == 400
    
    error_data = response.json()
    assert "details" in error_data["error"]
    assert "help_text" in error_data["error"]["details"]
```

## Troubleshooting

### Common Issues

1. **Missing Correlation IDs**: Ensure middleware is properly configured
2. **Inconsistent Error Format**: Use custom exceptions instead of HTTPException
3. **Missing Context**: Include request information in error logs
4. **Security Information Leakage**: Verify production error messages are sanitized

### Debugging Tips

1. Use correlation IDs to trace errors across logs
2. Check error metrics for patterns
3. Monitor security event logs for attack attempts
4. Use structured logging for better analysis

## Configuration

### Environment Variables

```bash
# Error handling configuration
DEBUG_MODE=false                    # Enable detailed error information
ENABLE_ERROR_METRICS=true          # Enable error metrics collection
LOG_SECURITY_EVENTS=true           # Log security violations
```

### Customization

Error messages, help URLs, and categories can be customized by modifying the error handling classes and templates in `backend/api/error_handling.py`.