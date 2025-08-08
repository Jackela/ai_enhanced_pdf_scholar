# Security Validation Implementation

## Overview

This document details the comprehensive security validation system implemented across all API endpoints to strengthen input validation and prevent common attack vectors including SQL injection, XSS, prompt injection, and file upload vulnerabilities.

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [Validation Categories](#validation-categories)
3. [Enhanced Pydantic Models](#enhanced-pydantic-models)
4. [Security Validators](#security-validators)
5. [Error Handling](#error-handling)
6. [API Route Integration](#api-route-integration)
7. [Testing Strategy](#testing-strategy)
8. [Monitoring and Logging](#monitoring-and-logging)

## Security Architecture

### Core Components

- **Security Validation Functions**: Pattern-based validation against known attack vectors
- **Enhanced Pydantic Models**: All API models include comprehensive field validation
- **Custom Exception Handling**: Standardized security error responses
- **Logging System**: Comprehensive security event logging
- **Middleware Layer**: Centralized security validation error handling

### Security Layers

```
Request → Security Middleware → Pydantic Validation → Business Logic → Response
    ↓           ↓                    ↓                    ↓            ↓
Logging    Error Handling      Field Validation    Safe Processing  Sanitized Output
```

## Validation Categories

### 1. String Fields Validation

All string input fields are validated against:

- **SQL Injection Patterns**: Detects common SQL injection attempts
- **XSS Patterns**: Prevents cross-site scripting attacks
- **Length Limits**: Enforces maximum field lengths
- **Content Sanitization**: HTML encoding and dangerous pattern removal

```python
# Example patterns detected:
DANGEROUS_SQL_PATTERNS = [
    r'--[\s]*',           # SQL comments
    r';[\s]*',            # Statement terminators
    r'\bunion\b.*\bselect\b',  # Union attacks
    r'\bdrop\b.*\btable\b',    # Drop statements
]

XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',                 # JavaScript protocol
    r'on\w+\s*=',                  # Event handlers
]
```

### 2. Numeric Fields Validation

- **Range Validation**: Enforces minimum/maximum values
- **Type Coercion Safety**: Prevents integer overflow attacks
- **Business Logic Validation**: Context-appropriate limits

### 3. File Upload Security

- **MIME Type Validation**: Only allowed file types accepted
- **File Size Limits**: Prevents resource exhaustion
- **Filename Security**: Path traversal and dangerous character prevention
- **Content Verification**: File extension matches declared MIME type

### 4. Search Query Protection

- **Prompt Injection Detection**: Prevents AI prompt manipulation
- **Query Length Limits**: Prevents resource exhaustion
- **Pattern-based Filtering**: Multiple attack vector detection

## Enhanced Pydantic Models

### DocumentQueryParams

Enhanced with comprehensive search query validation:

```python
class DocumentQueryParams(BaseModel):
    search_query: Optional[str] = Field(None, max_length=MAX_SEARCH_QUERY_LENGTH)
    
    @field_validator('search_query')
    @classmethod
    def validate_search_query(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        
        # Validate against SQL injection patterns
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, 'search_query', 'sql_injection')
        
        # Validate against XSS patterns
        validate_against_patterns(v, XSS_PATTERNS, 'search_query', 'xss_attempt')
        
        # Sanitize HTML content
        sanitized = sanitize_html_content(v)
        
        return sanitized.strip()
```

### DocumentBase

Enhanced with title and metadata validation:

```python
class DocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    metadata: Optional[Dict[str, Any]] = Field(None)
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        # Multi-layer validation
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, 'title', 'sql_injection')
        validate_against_patterns(v, XSS_PATTERNS, 'title', 'xss_attempt')
        sanitized = sanitize_html_content(v)
        return sanitized.strip()
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        
        # Size limit check
        metadata_json = json.dumps(v)
        if len(metadata_json) > MAX_METADATA_SIZE:
            raise SecurityValidationError('metadata', 'Metadata too large')
        
        # Sanitize string values
        sanitized_metadata = {}
        for key, value in v.items():
            if isinstance(value, str):
                validate_against_patterns(value, DANGEROUS_SQL_PATTERNS, f'metadata.{key}', 'sql_injection')
                sanitized_metadata[key] = sanitize_html_content(value)
            else:
                sanitized_metadata[key] = value
        
        return sanitized_metadata
```

### RAGQueryRequest

Enhanced with prompt injection detection:

```python
class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        # Standard validation
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, 'query', 'sql_injection')
        validate_against_patterns(v, XSS_PATTERNS, 'query', 'xss_attempt')
        
        # Prompt injection detection
        prompt_injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'disregard\s+previous\s+instructions',
            r'system\s*:',
            r'###\s*instruction',
        ]
        
        validate_against_patterns(v, prompt_injection_patterns, 'query', 'prompt_injection')
        
        return sanitize_html_content(v).strip()
```

### SecureFileUpload

Comprehensive file upload validation:

```python
class SecureFileUpload(BaseModel):
    filename: str = Field(..., min_length=1, max_length=MAX_FILENAME_LENGTH)
    content_type: str = Field(...)
    file_size: int = Field(..., ge=1, le=1024*1024*1024)  # 1GB max
    
    @field_validator('filename')
    @classmethod
    def validate_filename_security(cls, v: str) -> str:
        return validate_filename(v)  # Path traversal and dangerous character check
    
    @field_validator('content_type')
    @classmethod
    def validate_content_type_security(cls, v: str, info) -> str:
        filename = info.data.get('filename', '')
        if filename:
            return validate_file_content_type(v, filename)
        return v
    
    @model_validator(mode='after')
    def validate_file_upload(self):
        # Cross-field validation
        if self.content_type == 'application/pdf' and self.file_size < 100:
            raise SecurityValidationError('file_size', 'PDF file suspiciously small')
        return self
```

## Security Validators

### Core Validation Functions

#### validate_against_patterns()

```python
def validate_against_patterns(value: str, patterns: List[str], field_name: str, 
                            event_type: str = "dangerous_pattern") -> str:
    """Validate string against dangerous patterns."""
    if not value:
        return value
    
    value_lower = value.lower()
    for pattern in patterns:
        if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
            log_security_event(event_type, field_name, value, f"Matched pattern: {pattern}")
            raise SecurityValidationError(
                field_name, 
                f"Contains potentially dangerous pattern: {pattern}",
                pattern
            )
    return value
```

#### sanitize_html_content()

```python
def sanitize_html_content(value: str) -> str:
    """Sanitize HTML content to prevent XSS."""
    if not value:
        return value
    
    # HTML encode special characters
    sanitized = html.escape(value, quote=True)
    
    # Additional XSS pattern removal
    for pattern in XSS_PATTERNS:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    return sanitized.strip()
```

#### validate_filename()

```python
def validate_filename(filename: str) -> str:
    """Validate and sanitize filename."""
    if not filename:
        raise SecurityValidationError("filename", "Filename cannot be empty")
    
    if len(filename) > MAX_FILENAME_LENGTH:
        raise SecurityValidationError("filename", f"Filename too long")
    
    # Check for dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in dangerous_chars:
        if char in filename:
            raise SecurityValidationError("filename", f"Contains dangerous character: {char}")
    
    # Check for path traversal attempts
    if '..' in filename or filename.startswith('/') or '\\' in filename:
        raise SecurityValidationError("filename", "Path traversal attempt detected")
    
    return filename.strip()
```

## Error Handling

### Security Exception Responses

#### SecurityValidationErrorResponse

```python
class SecurityValidationErrorResponse(ErrorResponse):
    success: bool = False
    error_code: str = "SECURITY_VALIDATION_ERROR"
    field: str = Field(..., description="Field that failed validation")
    attack_type: Optional[str] = Field(None, description="Type of attack detected")
    pattern_matched: Optional[str] = Field(None, description="Dangerous pattern matched")
    
    @classmethod
    def from_security_error(cls, error: SecurityValidationError):
        return cls(
            message=f"Security validation failed: {str(error)}",
            field=error.field,
            pattern_matched=error.pattern,
            details={
                "field": error.field,
                "pattern": error.pattern,
                "timestamp": datetime.now().isoformat()
            }
        )
```

#### ValidationErrorResponse

```python
class ValidationErrorResponse(ErrorResponse):
    success: bool = False
    error_code: str = "VALIDATION_ERROR"
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    @classmethod
    def from_pydantic_error(cls, error):
        validation_errors = []
        for err in error.errors():
            validation_errors.append({
                "field": ".".join(str(x) for x in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
                "input": str(err.get("input", ""))[:100]
            })
        
        return cls(
            message="Request validation failed",
            validation_errors=validation_errors
        )
```

### Security Middleware

```python
class SecurityValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except SecurityValidationError as e:
            log_security_event(
                event_type="security_validation_failure",
                field=e.field,
                value=str(request.url),
                details=f"Pattern: {e.pattern}, Client: {request.client.host}"
            )
            
            error_response = SecurityValidationErrorResponse.from_security_error(e)
            
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response.dict()
            )
```

## API Route Integration

### Enhanced Upload Endpoint

```python
@router.post("/upload", response_model=DocumentImportResponse)
async def upload_document(file: UploadFile = File(...), title: Optional[str] = None):
    try:
        # Security validation
        secure_upload = SecureFileUpload(
            filename=file.filename or "unknown.pdf",
            content_type=file.content_type or "application/pdf",
            file_size=0  # Will be calculated during streaming
        )
    except SecurityValidationError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=SecurityValidationErrorResponse.from_security_error(e).dict()
        )
    
    # Continue with secure processing...
```

## Testing Strategy

### Security Test Coverage

1. **SQL Injection Tests**: Validate all string fields against SQL injection patterns
2. **XSS Prevention Tests**: Test script tag and event handler injection
3. **File Upload Security Tests**: Malicious filename and content type testing
4. **Prompt Injection Tests**: RAG query manipulation attempts
5. **Length Limit Tests**: Buffer overflow and resource exhaustion prevention
6. **Path Traversal Tests**: File system access attempts

### Test Implementation

```python
class TestSecurityValidation:
    def test_sql_injection_detection(self):
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
        ]
        
        for dangerous_input in dangerous_inputs:
            with pytest.raises(SecurityValidationError):
                validate_against_patterns(dangerous_input, DANGEROUS_SQL_PATTERNS, "test_field")
    
    def test_xss_detection(self):
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img onload='alert(1)' src='x'>",
        ]
        
        for xss_input in xss_inputs:
            with pytest.raises(SecurityValidationError):
                validate_against_patterns(xss_input, XSS_PATTERNS, "test_field")
```

## Monitoring and Logging

### Security Event Logging

```python
def log_security_event(event_type: str, field: str, value: str, details: Optional[str] = None):
    security_logger.warning(
        f"Security event - Type: {event_type}, Field: {field}, "
        f"Value: {value[:50]}{'...' if len(value) > 50 else ''}, "
        f"Details: {details or 'None'}"
    )
```

### Security Metrics

- **Attack Attempt Frequency**: Count of security validation failures by type
- **Field-specific Vulnerabilities**: Which fields receive the most attacks
- **Client IP Tracking**: Identify repeat offenders
- **Pattern Effectiveness**: Most commonly matched dangerous patterns

### Log Format

```
2024-01-19 10:30:15 [WARNING] security.validation: Security event - Type: sql_injection, Field: search_query, Value: '; DROP TABLE documents; --, Details: Matched pattern: ;[\s]*, Client: 192.168.1.100
```

## Security Constants

```python
# Maximum field lengths
MAX_FILENAME_LENGTH = 255
MAX_PATH_LENGTH = 4096
MAX_SEARCH_QUERY_LENGTH = 500
MAX_TITLE_LENGTH = 500
MAX_METADATA_SIZE = 10240  # 10KB

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'text/plain': ['.txt'],
    'application/json': ['.json'],
}
```

## Implementation Benefits

1. **Comprehensive Protection**: Multiple attack vectors covered
2. **Centralized Validation**: Consistent security across all endpoints
3. **Detailed Logging**: Full visibility into security events
4. **User-Friendly Errors**: Clear, actionable error messages
5. **Performance Optimized**: Efficient pattern matching and validation
6. **Extensible Design**: Easy to add new validation rules

## Best Practices

1. **Defense in Depth**: Multiple validation layers
2. **Fail Secure**: Default to denying suspicious input
3. **Log Everything**: Comprehensive security event logging
4. **Regular Updates**: Keep attack patterns current
5. **Performance Monitoring**: Ensure validation doesn't impact performance
6. **User Education**: Clear error messages help users understand requirements

## Future Enhancements

1. **Machine Learning Detection**: AI-based attack pattern recognition
2. **Rate Limiting Integration**: Automatic IP blocking for repeat offenders
3. **Behavioral Analysis**: User pattern-based anomaly detection
4. **Real-time Threat Intelligence**: External threat feed integration
5. **Advanced File Analysis**: Deep content inspection for uploads

---

**Note**: This implementation provides enterprise-grade security validation while maintaining system performance and user experience. All validation rules are configurable and can be adjusted based on specific security requirements.