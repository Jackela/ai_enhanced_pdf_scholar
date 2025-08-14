# SQL Injection Prevention - Code Review Checklist

## Overview

This checklist ensures that all code changes maintain the SQL injection prevention measures and don't introduce new vulnerabilities.

## Pre-Review Requirements

- [ ] **Security Tests Pass**: All security-related tests must pass
- [ ] **Unit Tests Coverage**: New code has corresponding security tests
- [ ] **Integration Tests**: End-to-end security validation included
- [ ] **Documentation Updated**: Security implications documented

## Database Query Review

### SQL Query Construction

- [ ] **No String Interpolation**: Verify no f-strings or % formatting in SQL queries
  ```python
  # ❌ DANGEROUS
  query = f"SELECT * FROM table WHERE field = {user_input}"

  # ✅ SAFE
  query = "SELECT * FROM table WHERE field = ?"
  params = (user_input,)
  ```

- [ ] **Parameterized Queries**: All user inputs passed as parameters
- [ ] **Whitelist Validation**: Dynamic field names use whitelist validation
- [ ] **Safe Defaults**: Invalid inputs fall back to safe default values
- [ ] **Query Logging**: Security-sensitive queries logged for audit

### Repository Layer Security

- [ ] **Input Sanitization**: All user inputs sanitized at repository boundary
- [ ] **Type Validation**: Parameter types validated before use
- [ ] **Boundary Checks**: Limits enforced on pagination and search parameters
- [ ] **Error Handling**: Database errors caught and sanitized before re-throwing

```python
# ✅ SECURE PATTERN
def get_documents(self, sort_by: str = "created_at") -> List[DocumentModel]:
    # Whitelist validation
    valid_fields = {"created_at": "created_at", "title": "title"}
    safe_sort_by = valid_fields.get(sort_by.lower(), "created_at")

    query = f"SELECT * FROM documents ORDER BY {safe_sort_by}"
    return self.db.fetch_all(query, ())
```

## API Layer Security

### Input Validation

- [ ] **Pydantic Models**: All inputs validated through Pydantic models
- [ ] **Enum Validation**: Sort fields and orders use enum types
- [ ] **Pattern Detection**: Search queries checked for dangerous patterns
- [ ] **Length Limits**: Maximum lengths enforced on string inputs
- [ ] **Range Validation**: Numeric inputs have min/max bounds

### Parameter Handling

- [ ] **Dependency Injection**: Query parameters use `Depends()` with validation
- [ ] **Type Safety**: Strong typing maintained throughout call chain
- [ ] **Error Responses**: Validation errors don't leak internal information
- [ ] **Logging**: Parameter validation failures logged for security monitoring

```python
# ✅ SECURE PATTERN
@router.get("/documents/")
async def get_documents(
    params: DocumentQueryParams = Depends(),  # Validated by Pydantic
    controller: LibraryController = Depends(get_library_controller),
):
    return controller.get_documents(
        sort_by=params.sort_by.value,  # Use enum value
        search_query=params.search_query,  # Already validated
    )
```

## Dangerous Patterns to Check For

### Red Flags - Immediate Security Review Required

- [ ] **String Concatenation in SQL**: Any string building for queries
- [ ] **User Input in Query Structure**: Fields, table names, or operators from user input
- [ ] **Dynamic Query Building**: Complex query construction based on user parameters
- [ ] **Raw SQL Execution**: Direct SQL execution without parameterization
- [ ] **Missing Input Validation**: User inputs not validated before database use

### Examples of Vulnerable Code

```python
# ❌ CRITICAL VULNERABILITIES
def bad_query(user_input):
    # String interpolation
    return f"SELECT * FROM docs WHERE title = '{user_input}'"

def bad_sorting(sort_field):
    # Direct field name interpolation
    return f"SELECT * FROM docs ORDER BY {sort_field}"

def bad_search(search_term):
    # No input validation
    return f"SELECT * FROM docs WHERE content LIKE '%{search_term}%'"
```

## Testing Requirements

### Security Test Coverage

- [ ] **Injection Payloads**: Test with known SQL injection patterns
- [ ] **Boundary Values**: Test parameter limits and edge cases
- [ ] **Error Conditions**: Verify error handling doesn't leak information
- [ ] **Integration Tests**: End-to-end security validation
- [ ] **Performance Tests**: Ensure security doesn't impact performance significantly

### Required Test Cases

```python
# ✅ REQUIRED SECURITY TESTS
def test_sql_injection_blocked():
    """Test that injection attempts are blocked."""
    dangerous_inputs = [
        "'; DROP TABLE users; --",
        "' UNION SELECT password FROM admin",
        "1' OR '1'='1"
    ]
    for payload in dangerous_inputs:
        # Should be blocked or sanitized
        result = repository.search(payload)
        assert_no_injection_occurred(result)

def test_parameter_validation():
    """Test that invalid parameters are rejected."""
    with pytest.raises(ValidationError):
        invalid_params = {"sort_by": "invalid; DROP TABLE docs"}
        DocumentQueryParams(**invalid_params)
```

## Documentation Requirements

### Security Documentation

- [ ] **Threat Model**: Document security assumptions and protections
- [ ] **Attack Vectors**: List known attack patterns and mitigations
- [ ] **Validation Rules**: Document all input validation requirements
- [ ] **Error Handling**: Document secure error response patterns
- [ ] **Monitoring**: Document security logging and alerting

### Code Comments

- [ ] **Security Rationale**: Explain why security measures are implemented
- [ ] **Validation Logic**: Comment complex validation code
- [ ] **Safe Assumptions**: Document security assumptions in code
- [ ] **Audit Points**: Mark security-critical code sections

```python
# ✅ GOOD SECURITY DOCUMENTATION
def get_documents(self, sort_by: str) -> List[DocumentModel]:
    """
    Get documents with secure sorting.

    Security: sort_by parameter is validated against whitelist to prevent
    SQL injection. Only predefined field names are allowed.

    Args:
        sort_by: Sort field name (validated against whitelist)
    """
    # SECURITY: Whitelist validation prevents SQL injection
    valid_fields = {"created_at": "created_at", "title": "title"}
    safe_sort_by = valid_fields.get(sort_by.lower(), "created_at")

    # AUDIT: Log security-critical operations
    logger.debug(f"Executing secure query with sort_by='{safe_sort_by}'")

    query = f"SELECT * FROM documents ORDER BY {safe_sort_by}"
    return self.db.fetch_all(query, ())
```

## Deployment Security

### Pre-deployment Checks

- [ ] **Security Tests Pass**: All security tests green
- [ ] **Performance Benchmarks**: No significant performance degradation
- [ ] **Error Monitoring**: Error tracking configured for validation failures
- [ ] **Logging Configured**: Security audit logging enabled
- [ ] **Monitoring Alerts**: Alerts set up for security events

### Post-deployment Monitoring

- [ ] **Query Monitoring**: Monitor for unusual query patterns
- [ ] **Error Rate Tracking**: Track validation error rates for attack detection
- [ ] **Performance Monitoring**: Ensure security measures don't impact performance
- [ ] **Log Analysis**: Regular review of security logs

## Review Checklist Sign-off

### Security Reviewer Checklist

- [ ] **Code Review Completed**: All security items verified
- [ ] **Tests Reviewed**: Security test coverage adequate
- [ ] **Documentation Reviewed**: Security docs updated
- [ ] **Risk Assessment**: Security risk level acceptable
- [ ] **Deployment Approval**: Safe to deploy

### Reviewer Information

- **Reviewer Name**: _______________
- **Review Date**: _______________
- **Security Approval**: [ ] Approved [ ] Needs Changes
- **Comments**: _______________

---

## Quick Reference

### Secure Coding Patterns

```python
# ✅ SECURE REPOSITORY METHOD
def secure_query(self, user_param: str) -> List[Model]:
    # 1. Validate input
    whitelist = {"allowed": "allowed_value"}
    safe_param = whitelist.get(user_param, "default")

    # 2. Use parameterized query
    query = "SELECT * FROM table WHERE safe_field = ?"
    params = (safe_param,)

    # 3. Log for audit
    logger.debug(f"Secure query: {safe_param}")

    return self.db.fetch_all(query, params)

# ✅ SECURE API ENDPOINT
@router.get("/items/")
async def get_items(params: SecureParams = Depends()):
    return service.get_items(
        sort_by=params.sort_by.value,  # Enum value
        search=params.search  # Validated by Pydantic
    )
```

### Common Pitfalls

- Dynamic query building with user input
- Missing input validation at API boundary
- Error messages leaking internal information
- Insufficient testing of edge cases
- Logging sensitive user data

---

**Checklist Version**: 1.0
**Last Updated**: 2025-01-19
**Next Review**: 2025-04-19