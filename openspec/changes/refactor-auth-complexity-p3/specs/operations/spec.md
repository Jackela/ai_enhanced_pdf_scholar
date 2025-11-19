# Operations Spec Deltas: Auth Complexity Refactoring

**Change ID:** `refactor-auth-complexity-p3`
**Spec:** `openspec/specs/operations/spec.md`
**Type:** MODIFIED + ADDED Requirements
**Last Updated:** 2025-01-19

---

## MODIFIED Requirements

### Requirement: Auth validation MUST use composable helpers

Authentication subsystem validation logic (password strength, token parsing, RBAC enforcement) SHALL decompose complex conditional logic into focused helper methods and validators to maintain cyclomatic complexity ≤10 (C901) and enable granular unit testing.

**Rationale:** Complex authentication functions (C901 >10) are error-prone, difficult to test in isolation, and create barriers to security audits. Composable helpers enable independent testing of each validation rule.

**Applies to:**
- Password validation (`backend/api/auth/password_security.py`)
- Token authentication (`backend/api/auth/dependencies.py`, `jwt_handler.py`)
- RBAC permission checks (`backend/api/auth/rbac.py`)

#### Scenario: Password policy validation decomposition

**GIVEN** a password strength validator function with cyclomatic complexity >10 due to multiple validation checks (length, character classes, common passwords, patterns)

**WHEN** developers refactor using the Strategy pattern with `PasswordValidator` protocol

**THEN:**
- Each validation rule (length, character classes, etc.) becomes a separate validator class
- Each validator implements `validate(password: str) -> ValidationResult` interface
- Main validation function orchestrates validators: `[LengthValidator(), CharacterClassValidator(), ...].map(v => v.validate(pwd))`
- Cyclomatic complexity of main function reduces to ≤6
- Each validator is independently unit-testable with clear success/failure cases

**AND:**
- All existing password validation tests continue to pass (behavior preservation)
- New unit tests added for each individual validator
- `ruff check --select C901` reports no violations in auth module

**Example Implementation:**
```python
# Before refactoring (C901: 13)
def validate_password_strength(password: str) -> ValidationResult:
    errors = []
    if len(password) < 8:
        errors.append("Too short")
    if not has_uppercase(password):
        errors.append("Missing uppercase")
    # ... 6 more conditions
    return ValidationResult(is_valid=len(errors)==0, errors=errors)

# After refactoring (C901: 6)
def validate_password_strength(password: str) -> ValidationResult:
    validators = [
        LengthValidator(min_length=8),
        CharacterClassValidator(),
        CommonPasswordValidator(),
        PatternValidator(),
    ]
    results = [v.validate(password) for v in validators]
    all_errors = [e for r in results for e in r.errors]
    return ValidationResult(is_valid=len(all_errors)==0, errors=all_errors)
```

---

#### Scenario: Auth dependency injection helper extraction

**GIVEN** an authentication dependency injection callable (`__call__` method) with complexity >10 that performs token extraction, validation, user fetching, and permission checking in a single function

**WHEN** developers extract each concern into a dedicated private helper method

**THEN:**
- Token extraction logic moves to `_extract_token(request)` helper (complexity ≤3)
- Token validation logic moves to `_validate_token(token)` helper (complexity ≤4)
- User fetching logic moves to `_fetch_user(user_id)` helper (complexity ≤3)
- Permission checking moves to `_check_permissions(user)` helper (complexity ≤3)
- Main `__call__` method orchestrates helpers with clear error propagation

**AND:**
- Each helper is independently unit-testable with mocked dependencies
- Main method complexity reduces from 12 to ≤8
- Integration tests verify end-to-end auth flow unchanged
- `ruff check --select C901` shows violation eliminated

**Example Implementation:**
```python
# Before (C901: 12)
async def __call__(self, request: Request) -> User:
    # 30+ lines of mixed concerns

# After (C901: 6)
async def __call__(self, request: Request) -> User:
    token = self._extract_token(request)
    payload = self._validate_token(token)
    user = await self._fetch_user(int(payload["sub"]))
    self._check_permissions(user)
    return user
```

---

## ADDED Requirements

### Requirement: Batch operations MUST extract error handlers

Services processing collections in loops (auth migrations, user batch operations) SHALL validate inputs before iteration and collect errors outside loop bodies to eliminate try-except-in-loop anti-patterns (PERF203) while preserving error reporting behavior.

**Rationale:** Exception handling inside loops creates performance overhead (repeated setup/teardown) and makes code harder to reason about. The validation-first pattern improves performance and clarity without sacrificing error handling.

**Applies to:**
- Auth migration scripts (`backend/api/auth/migrations.py`)
- Batch user validation/creation
- Token batch refresh operations

#### Scenario: Auth migration loop refactoring

**GIVEN** an auth migration script that processes multiple users/roles in a loop, with try-except blocks inside the loop to handle per-item errors (PERF203 violation)

**WHEN** developers refactor using the validation-first pattern

**THEN:**
- Input validation happens before the processing loop (pre-filter invalid items)
- Valid items are processed in the loop without exception handlers
- Errors are collected in a list and handled after iteration completes
- Bulk database operations replace individual inserts where possible

**AND:**
- Migration behavior remains identical (same items migrated, same errors reported)
- Migration performance improves or stays within ±5% (benchmark required)
- `ruff check --select PERF203` shows violation eliminated
- Migration is idempotent (running twice produces same result)

**Example Implementation:**
```python
# Before (PERF203 violation)
def migrate_users(user_ids: list[int]) -> MigrationResult:
    migrated = []
    failed = []
    for user_id in user_ids:
        try:
            user = db.get_user(user_id)
            new_user = transform(user)
            db.save(new_user)
            migrated.append(user_id)
        except Exception as e:
            failed.append((user_id, str(e)))
    return MigrationResult(migrated, failed)

# After (no PERF203)
def migrate_users(user_ids: list[int]) -> MigrationResult:
    # Step 1: Bulk validation
    users = db.get_users_bulk(user_ids)
    existing_ids = {u.id for u in users}
    missing_ids = set(user_ids) - existing_ids

    # Step 2: Transform (no exceptions expected)
    transformed = [transform(u) for u in users]

    # Step 3: Bulk save
    db.save_users_bulk(transformed)
    migrated_ids = [u.id for u in transformed]

    # Step 4: Collect failures
    failed = [(uid, "Not found") for uid in missing_ids]
    return MigrationResult(migrated_ids, failed)
```

---

#### Scenario: Batch validation error collection

**GIVEN** a service validating multiple user inputs (registration, bulk import) with try-except inside the validation loop

**WHEN** developers refactor to collect validation errors after processing

**THEN:**
- Validation functions return `Result[T, Error]` instead of raising exceptions
- Loop iterates over inputs, calling validation functions and collecting results
- After loop completes, errors are aggregated and formatted for response
- No exception handling occurs inside the hot path (loop body)

**AND:**
- Validation behavior unchanged (same items pass/fail)
- Error messages remain user-friendly and detailed
- Performance improves for large batches (benchmark on 1000+ items)
- `ruff check --select PERF203` passes

**Example Implementation:**
```python
# Before (PERF203)
def validate_users_batch(users: list[UserInput]) -> list[ValidationError]:
    errors = []
    for i, user in enumerate(users):
        try:
            validate_email(user.email)
            validate_username(user.username)
        except ValidationError as e:
            errors.append(ValidationError(index=i, message=str(e)))
    return errors

# After (no PERF203)
def validate_users_batch(users: list[UserInput]) -> list[ValidationError]:
    # Validation functions return Result, not raise
    results = [
        (i, validate_user_safe(user))  # Returns Result[User, Error]
        for i, user in enumerate(users)
    ]

    # Extract errors after iteration
    errors = [
        ValidationError(index=i, message=result.error)
        for i, result in results
        if result.is_error
    ]
    return errors
```

---

#### Scenario: Idempotent migration with error recovery

**GIVEN** an auth migration that must be safe to run multiple times (idempotent) and handle partial failures gracefully

**WHEN** developers implement using validation-first + transaction batching

**THEN:**
- Migration checks for existing migrated items before processing (idempotency)
- Processes items in batches with transaction boundaries
- Partial failure (batch fails) does not corrupt database state
- Failed batches are logged with item IDs for manual recovery
- Re-running migration completes remaining items without re-processing successful ones

**AND:**
- Integration test verifies running migration twice produces same final state
- Benchmark shows performance improvement with batching (vs. per-item transactions)
- Monitoring logs include success/failure counts per batch
- `ruff check --select PERF203` passes

**Example Implementation:**
```python
# Migration with idempotency and batching
def migrate_auth_schema(batch_size: int = 100) -> MigrationResult:
    # Step 1: Find items needing migration (idempotency)
    all_ids = db.get_all_user_ids()
    migrated_ids = db.get_migrated_user_ids()
    pending_ids = set(all_ids) - set(migrated_ids)

    # Step 2: Process in batches
    migrated = []
    failed = []

    for batch in chunked(pending_ids, batch_size):
        try:
            with db.transaction():
                users = db.get_users_bulk(batch)
                transformed = [transform_schema(u) for u in users]
                db.save_users_bulk(transformed)
                migrated.extend(batch)
        except DatabaseError as e:
            logger.error(f"Batch failed: {batch}, error: {e}")
            failed.extend(batch)

    return MigrationResult(migrated=migrated, failed=failed)
```

---

## Verification

### Automated Checks

All requirements in this spec delta SHALL be verified by:

1. **Lint Enforcement:**
   ```bash
   # No C901 violations in auth subsystem
   ruff check backend/api/auth/ --select C901
   # Expected: 0 errors (down from 13)

   # No PERF203 violations in auth subsystem
   ruff check backend/api/auth/ --select PERF203
   # Expected: 0 errors (down from 12)
   ```

2. **Test Coverage:**
   ```bash
   # Auth test suite must pass with ≥95% coverage
   pytest tests/backend/test_auth* --cov=backend/api/auth --cov-report=term-missing
   # Expected: 100% pass rate, coverage ≥95%
   ```

3. **Performance Benchmarks:**
   ```bash
   # Migration performance must not regress
   python scripts/benchmark_migrations.py
   # Expected: Duration within ±5% of baseline
   ```

### Manual Checks

- [ ] Code review confirms helper functions have single responsibility
- [ ] Code review confirms validators follow protocol interface
- [ ] Integration testing verifies auth flow unchanged (login → access → refresh)
- [ ] Security audit confirms no authentication logic altered

---

## Related Requirements

**Cross-References:**
- `openspec/specs/operations/spec.md:28` - "Cache orchestration MUST separate per-layer logic"
  - Similar C901/PERF203 refactoring pattern applied to cache managers
  - Validates helper extraction approach

- `openspec/specs/operations/spec.md:42` - "Resilience services MUST have regression tests"
  - Ensures behavior preservation during refactoring
  - Test coverage requirements aligned

**Precedent Changes:**
- `archive/2025-11-13-refactor-integrated-cache-manager` - Successful C901 reduction in cache subsystem
- `archive/2025-11-16-expand-backend-coverage-rag-auth` - Auth test suite expansion

---

## Notes

- This spec delta is part of a 3-phase complexity reduction initiative (auth → services → api)
- Patterns established here (Strategy, helper extraction, validation-first) will be reused in Phase 2-3
- All refactoring preserves behavior (no functional changes, only structural improvements)
- Performance improvements from PERF203 fixes are side effects, not primary goals
