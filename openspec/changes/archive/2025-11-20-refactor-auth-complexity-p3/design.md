# Technical Design: Auth Complexity Refactoring

**Change ID:** `refactor-auth-complexity-p3`
**Version:** 1.0
**Last Updated:** 2025-01-19

---

## Overview

This document describes the technical approach for reducing cyclomatic complexity (C901) and eliminating try-except-in-loop anti-patterns (PERF203) in the authentication subsystem.

**Goals:**
- Reduce avg function complexity from 11.5 to <8
- Extract 20+ helper functions with single responsibility
- Establish reusable patterns for Phase 2-3 refactoring

---

## Refactoring Patterns

### Pattern 1: Strategy Pattern for Validation

**Use Case:** Functions with multiple independent validation checks

**Example: Password Strength Validation**

```python
# BEFORE (C901: 13) - backend/api/auth/password_security.py:145
def validate_password_strength(password: str) -> ValidationResult:
    """Validate password meets security requirements."""
    errors = []

    # Length check
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")

    # Character class checks
    if not any(c.isupper() for c in password):
        errors.append("Password must contain uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain digit")

    if not any(c in "!@#$%^&*" for c in password):
        errors.append("Password must contain special character")

    # Common password check
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common")

    # Sequential pattern check
    if has_sequential_pattern(password):
        errors.append("Password contains sequential patterns")

    # Repeated character check
    if has_repeated_chars(password, max_repeat=3):
        errors.append("Password has too many repeated characters")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors
    )
```

**After (C901: 6) - Extracted validators:**

```python
# Protocol for composable validators
class PasswordValidator(Protocol):
    """Interface for password validation rules."""

    def validate(self, password: str) -> ValidationResult:
        """Return validation result with errors if invalid."""
        ...

# Concrete validators (each <10 lines, C901: 1-2)
class LengthValidator:
    def __init__(self, min_length: int = 8):
        self.min_length = min_length

    def validate(self, password: str) -> ValidationResult:
        if len(password) < self.min_length:
            return ValidationResult.fail(
                f"Password must be at least {self.min_length} characters"
            )
        return ValidationResult.ok()

class CharacterClassValidator:
    def validate(self, password: str) -> ValidationResult:
        errors = []
        if not any(c.isupper() for c in password):
            errors.append("Must contain uppercase letter")
        if not any(c.islower() for c in password):
            errors.append("Must contain lowercase letter")
        if not any(c.isdigit() for c in password):
            errors.append("Must contain digit")
        if not any(c in "!@#$%^&*" for c in password):
            errors.append("Must contain special character")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

class CommonPasswordValidator:
    def __init__(self, common_passwords: set[str]):
        self.common_passwords = common_passwords

    def validate(self, password: str) -> ValidationResult:
        if password.lower() in self.common_passwords:
            return ValidationResult.fail("Password is too common")
        return ValidationResult.ok()

class PatternValidator:
    def validate(self, password: str) -> ValidationResult:
        if has_sequential_pattern(password):
            return ValidationResult.fail("Contains sequential patterns")
        if has_repeated_chars(password, max_repeat=3):
            return ValidationResult.fail("Too many repeated characters")
        return ValidationResult.ok()

# Main validator orchestrates (C901: 6)
def validate_password_strength(password: str) -> ValidationResult:
    """Validate password using composable validators."""
    validators = [
        LengthValidator(min_length=8),
        CharacterClassValidator(),
        CommonPasswordValidator(COMMON_PASSWORDS),
        PatternValidator(),
    ]

    all_errors = []
    for validator in validators:
        result = validator.validate(password)
        if not result.is_valid:
            all_errors.extend(result.errors)

    return ValidationResult(
        is_valid=len(all_errors) == 0,
        errors=all_errors
    )
```

**Benefits:**
- Each validator is independently testable
- Easy to add/remove validation rules
- Complexity reduced from 13 to 6
- Reusable pattern for other validation scenarios

---

### Pattern 2: Helper Extraction for Sequential Logic

**Use Case:** Functions performing multiple sequential operations

**Example: Dependency Injection Auth**

```python
# BEFORE (C901: 12) - backend/api/auth/dependencies.py:47
async def __call__(self, request: Request) -> User:
    """Authenticate user from JWT token."""
    # Token extraction (5 lines)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(401, "Missing authorization header")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid authorization header format")

    token = parts[1]

    # Token validation (8 lines)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing user ID")

    # User fetching (6 lines)
    user = await self.user_service.get_user(int(user_id))
    if not user:
        raise HTTPException(401, "User not found")

    if not user.is_active:
        raise HTTPException(403, "User account disabled")

    # Permission check (4 lines)
    if self.required_permission:
        if not user.has_permission(self.required_permission):
            raise HTTPException(403, "Insufficient permissions")

    return user
```

**After (C901: 6) - Extracted helpers:**

```python
# Helper methods (each C901: 2-3)
def _extract_token(self, request: Request) -> str:
    """Extract JWT token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(401, "Missing authorization header")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid authorization header format")

    return parts[1]

def _validate_token(self, token: str) -> dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(401, "Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, "Invalid token") from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing user ID")

    return payload

async def _fetch_user(self, user_id: int) -> User:
    """Fetch and validate user from database."""
    user = await self.user_service.get_user(user_id)
    if not user:
        raise HTTPException(401, "User not found")

    if not user.is_active:
        raise HTTPException(403, "User account disabled")

    return user

def _check_permissions(self, user: User) -> None:
    """Verify user has required permissions."""
    if self.required_permission:
        if not user.has_permission(self.required_permission):
            raise HTTPException(403, "Insufficient permissions")

# Main method orchestrates (C901: 6)
async def __call__(self, request: Request) -> User:
    """Authenticate user from JWT token."""
    token = self._extract_token(request)
    payload = self._validate_token(token)
    user = await self._fetch_user(int(payload["sub"]))
    self._check_permissions(user)
    return user
```

**Benefits:**
- Clear separation of concerns
- Each helper is independently testable
- Easier to mock for unit tests
- Complexity reduced from 12 to 6

---

### Pattern 3: Validation-First for Loop Optimization

**Use Case:** PERF203 - try-except blocks inside loops

**Example: Batch User Migration**

```python
# BEFORE (PERF203) - backend/api/auth/migrations.py
def migrate_users_batch(user_ids: list[int]) -> MigrationResult:
    """Migrate users to new schema."""
    migrated = []
    failed = []

    for user_id in user_ids:  # PERF203: try-except in loop
        try:
            user = db.get_user(user_id)
            new_user = transform_user_schema(user)
            db.save_user(new_user)
            migrated.append(user_id)
        except UserNotFoundError as e:
            failed.append((user_id, str(e)))
        except ValidationError as e:
            failed.append((user_id, str(e)))
        except DatabaseError as e:
            failed.append((user_id, str(e)))

    return MigrationResult(migrated=migrated, failed=failed)
```

**After (No PERF203) - Validation first:**

```python
def migrate_users_batch(user_ids: list[int]) -> MigrationResult:
    """Migrate users to new schema (optimized)."""
    # Step 1: Bulk fetch and validate
    users = db.get_users_bulk(user_ids)
    existing_ids = {u.id for u in users}
    missing_ids = set(user_ids) - existing_ids

    # Step 2: Transform (no exceptions expected)
    transformed_users = []
    for user in users:
        try:
            transformed = transform_user_schema(user)
            transformed_users.append(transformed)
        except ValidationError as e:
            # Validation errors collected, not in hot path
            logger.warning(f"Validation failed for user {user.id}: {e}")

    # Step 3: Batch save
    migrated_ids = []
    failed_ids = []

    try:
        db.save_users_bulk(transformed_users)
        migrated_ids = [u.id for u in transformed_users]
    except DatabaseError as e:
        # Handle batch failure
        logger.error(f"Batch save failed: {e}")
        failed_ids = [u.id for u in transformed_users]

    # Step 4: Collect all failures
    all_failed = [
        (uid, "User not found") for uid in missing_ids
    ] + [
        (uid, "Database error") for uid in failed_ids
    ]

    return MigrationResult(migrated=migrated_ids, failed=all_failed)
```

**Benefits:**
- No exception handling in hot loop (PERF203 resolved)
- Bulk operations improve performance
- Errors collected and reported after processing
- Clearer separation of validation and processing logic

---

## Testing Strategy

### Unit Testing Approach

**1. Helper Function Tests:**
```python
# Test each extracted helper independently
def test_extract_token_valid():
    request = Mock(headers={"Authorization": "Bearer token123"})
    assert auth._extract_token(request) == "token123"

def test_extract_token_missing_header():
    request = Mock(headers={})
    with pytest.raises(HTTPException) as exc:
        auth._extract_token(request)
    assert exc.value.status_code == 401
```

**2. Validator Tests:**
```python
# Test each validator in isolation
def test_length_validator():
    validator = LengthValidator(min_length=8)

    # Valid case
    result = validator.validate("password123")
    assert result.is_valid

    # Invalid case
    result = validator.validate("pass")
    assert not result.is_valid
    assert "at least 8 characters" in result.errors[0]
```

**3. Property-Based Testing:**
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=8, max_size=128))
def test_password_validation_always_returns_result(password: str):
    """Verify validation always returns well-formed result."""
    result = validate_password_strength(password)
    assert isinstance(result, ValidationResult)
    assert isinstance(result.is_valid, bool)
    assert isinstance(result.errors, list)
```

### Integration Testing

**Before/After Comparison:**
```python
def test_auth_flow_behavior_equivalence():
    """Verify refactored auth has identical behavior."""
    test_cases = [
        (valid_token, expected_user),
        (expired_token, HTTPException(401)),
        (invalid_token, HTTPException(401)),
        (missing_permission, HTTPException(403)),
    ]

    for token, expected in test_cases:
        # Test both old and new implementations
        old_result = old_auth(token)
        new_result = new_auth(token)
        assert old_result == new_result
```

### Performance Benchmarking

**Migration Performance:**
```python
import pytest
import time

def test_migration_performance():
    """Verify PERF203 fixes don't degrade performance."""
    user_ids = list(range(1000))

    start = time.perf_counter()
    result = migrate_users_batch(user_ids)
    duration = time.perf_counter() - start

    # Should complete in reasonable time
    assert duration < 5.0  # 5 seconds for 1000 users
    assert len(result.migrated) + len(result.failed) == 1000
```

---

## Implementation Phases

### Phase 1: Foundation (Day 1)
- Create test baseline for auth module
- Document current violations
- Set up complexity tracking

### Phase 2: Password Validation (Day 1-2)
- Implement `PasswordValidator` protocol
- Create concrete validators
- Refactor `validate_password_strength()`
- Add unit tests

### Phase 3: Dependency Injection (Day 2-3)
- Extract helper methods
- Refactor `__call__()` method
- Add integration tests

### Phase 4: Migrations (Day 3-4)
- Refactor 12 PERF203 instances
- Implement validation-first pattern
- Benchmark performance

### Phase 5: Remaining Functions (Day 4-5)
- Apply patterns to 10 remaining functions
- Full regression testing

### Phase 6: Validation (Day 5-7)
- Ruff verification
- Code review
- Documentation updates

---

## Risks & Mitigation

### Risk 1: Behavior Regression

**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Comprehensive test coverage (target: >95%)
- Property-based testing for edge cases
- Integration tests comparing old/new behavior
- Gradual rollout with feature flags

### Risk 2: Performance Degradation

**Likelihood:** Low
**Impact:** Medium
**Mitigation:**
- Benchmark critical paths (auth flow, migrations)
- PERF203 fixes should improve performance
- Monitor production metrics after deployment

### Risk 3: Team Adoption

**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Document patterns in CLAUDE.md
- Code review training sessions
- Establish pattern library for Phase 2-3

---

## Success Metrics

- [ ] All 13 C901 violations resolved (Ruff clean)
- [ ] All 12 PERF203 violations resolved
- [ ] 100% test suite passing
- [ ] Average function complexity <8
- [ ] No performance regression (benchmark within 5%)
- [ ] Code review approved
- [ ] Patterns documented for reuse
