# Tasks: Auth Complexity Refactoring

**Change ID:** `refactor-auth-complexity-p3`
**Estimated Duration:** 5-7 days
**Last Updated:** 2025-01-19

---

## Task Organization

Tasks are ordered by dependency and priority. Each task should take <2 hours to complete.

**Legend:**
- 🔴 Blocking (must complete before next task)
- 🟡 Parallel (can work concurrently)
- 🟢 Optional (nice-to-have)

---

## Week 1: Days 1-2 - Foundation + Password Validation

### 1.1 Baseline Setup 🔴
- [ ] Create comprehensive test suite for auth module
  - Run: `pytest tests/backend/test_auth* -v --cov=backend/api/auth`
  - Document current coverage percentage
  - Save baseline test output for comparison
- [ ] Document all C901/PERF203 violations in auth
  - Run: `ruff check backend/api/auth/ --select C901,PERF203 --output-format=json > auth_violations_baseline.json`
  - Create spreadsheet mapping: file → function → complexity → line number
- [ ] Set up complexity tracking script
  - Create `scripts/track_auth_complexity.sh`
  - Add to CI as non-blocking check
  - Baseline: 25 violations (13 C901 + 12 PERF203)

**Deliverable:** Baseline report with test coverage + violation map

---

### 1.2 Password Validator Protocol 🔴
- [ ] Create `PasswordValidator` protocol in `backend/api/auth/validators.py`
  ```python
  class PasswordValidator(Protocol):
      def validate(self, password: str) -> ValidationResult:
          ...
  ```
- [ ] Create `ValidationResult` dataclass
  ```python
  @dataclass
  class ValidationResult:
      is_valid: bool
      errors: list[str] = field(default_factory=list)
  ```
- [ ] Write unit tests for protocol
  - Test type checking with mypy
  - Test basic conformance

**Deliverable:** `validators.py` with protocol and tests

---

### 1.3 Implement Concrete Validators 🟡
- [ ] `LengthValidator(min_length: int = 8)`
  - Unit test: valid/invalid lengths
  - Unit test: custom min_length parameter
- [ ] `CharacterClassValidator()`
  - Unit test: uppercase, lowercase, digits, special chars
  - Unit test: missing each character class
- [ ] `CommonPasswordValidator(common_passwords: set[str])`
  - Unit test: common password detection
  - Unit test: case-insensitive matching
- [ ] `PatternValidator()`
  - Unit test: sequential patterns (123, abc)
  - Unit test: repeated characters (aaa, 111)

**Deliverable:** 4 validator classes with 100% test coverage

---

### 1.4 Refactor `validate_password_strength()` 🔴
- [ ] Replace implementation in `backend/api/auth/password_security.py:145`
  - Import validators
  - Create validator list
  - Orchestrate validation calls
  - Aggregate errors
- [ ] Verify complexity reduction
  - Before: C901 = 13
  - After: C901 ≤ 6
  - Run: `ruff check backend/api/auth/password_security.py --select C901`
- [ ] Run auth test suite
  - All tests must pass: `pytest tests/backend/test_auth_security.py -v`
  - Verify no behavior changes

**Deliverable:** Refactored function with C901 ≤ 6 + passing tests

---

## Week 1-2: Days 3-4 - Dependency Injection + Migrations

### 2.1 Extract Auth DI Helpers 🔴
- [ ] Create helper methods in `backend/api/auth/dependencies.py`
  - `_extract_token(request: Request) -> str`
  - `_validate_token(token: str) -> dict[str, Any]`
  - `_fetch_user(user_id: int) -> User`
  - `_check_permissions(user: User) -> None`
- [ ] Write unit tests for each helper
  - Mock external dependencies (jwt, user_service)
  - Test success paths
  - Test error paths (401, 403 exceptions)

**Deliverable:** 4 helper methods with unit tests

---

### 2.2 Refactor `__call__()` Method 🔴
- [ ] Replace implementation in `backend/api/auth/dependencies.py:47`
  - Call extracted helpers in sequence
  - Handle exceptions from helpers
  - Preserve exact error messages
- [ ] Verify complexity reduction
  - Before: C901 = 12
  - After: C901 ≤ 8
- [ ] Run integration tests
  - `pytest tests/backend/test_auth_routes_login_refresh.py`
  - Verify auth flow end-to-end

**Deliverable:** Simplified `__call__()` with C901 ≤ 8

---

### 2.3 Audit Migration PERF203 Instances 🔴
- [ ] List all 12 PERF203 violations in `backend/api/auth/migrations.py`
  - Document loop type (user iteration, role migration, etc.)
  - Identify exception types being caught
  - Estimate batch size (rows processed per loop)
- [ ] Categorize by refactoring difficulty
  - Easy: Simple validation-first (6 instances)
  - Medium: Requires bulk operations (4 instances)
  - Hard: Complex error handling (2 instances)

**Deliverable:** Migration audit spreadsheet with categorization

---

### 2.4 Refactor Easy Migrations (6 instances) 🟡
- [ ] Apply validation-first pattern to 6 easy instances
  - Extract validation outside loop
  - Collect errors after iteration
  - Use bulk operations where possible
- [ ] Verify PERF203 resolution
  - Run: `ruff check backend/api/auth/migrations.py --select PERF203`
  - Expected: 12 → 6 violations
- [ ] Run migration tests
  - `pytest tests/backend/test_auth_migrations.py`
  - Verify idempotency (run twice, same result)

**Deliverable:** 6 PERF203 violations eliminated

---

### 2.5 Refactor Medium/Hard Migrations (6 instances) 🟡
- [ ] Apply advanced patterns to remaining 6 instances
  - Implement bulk error collection
  - Add transaction batching for performance
  - Handle partial failures gracefully
- [ ] Benchmark migration performance
  - Run: `python scripts/benchmark_migrations.py`
  - Compare before/after duration
  - Verify no regression (±5% acceptable)
- [ ] Verify all PERF203 eliminated
  - Run: `ruff check backend/api/auth/ --select PERF203`
  - Expected: 0 violations

**Deliverable:** All 12 PERF203 violations eliminated + benchmark report

---

## Week 2: Days 5-7 - Remaining Functions + Validation

### 3.1 Refactor `authenticate_user()` 🔴
- [ ] Apply helper extraction pattern to `backend/api/auth/service.py:89`
  - Extract: `_validate_credentials()`, `_check_rate_limit()`, `_create_session()`
  - Simplify main function to orchestration
- [ ] Verify complexity reduction
  - Before: C901 = 11
  - After: C901 ≤ 7
- [ ] Run auth service tests
  - `pytest tests/backend/test_auth_service_*.py`

**Deliverable:** Simplified `authenticate_user()` with C901 ≤ 7

---

### 3.2 Refactor Remaining 10 Functions 🟡
Functions to refactor (list from baseline audit):

- [ ] `backend/api/auth/routes.py::login_handler` (C901: 11 → 7)
- [ ] `backend/api/auth/routes.py::refresh_token_handler` (C901: 11 → 7)
- [ ] `backend/api/auth/service.py::register_user` (C901: 12 → 8)
- [ ] `backend/api/auth/service.py::reset_password` (C901: 11 → 7)
- [ ] `backend/api/auth/rbac.py::check_permission` (C901: 11 → 7)
- [ ] `backend/api/auth/rbac.py::evaluate_policy` (C901: 12 → 8)
- [ ] `backend/api/auth/jwt_handler.py::create_token` (C901: 11 → 7)
- [ ] `backend/api/auth/jwt_handler.py::refresh_token` (C901: 11 → 7)
- [ ] `backend/api/auth/security.py::hash_password` (C901: 11 → 7)
- [ ] `backend/api/auth/security.py::verify_password` (C901: 11 → 7)

**Process per function:**
1. Apply appropriate pattern (helper extraction or strategy)
2. Write/update unit tests
3. Verify C901 reduction
4. Run related test suite

**Deliverable:** 10 functions refactored with C901 ≤ 8

---

### 3.3 Full Auth Regression Test 🔴
- [ ] Run complete auth test suite
  - `pytest tests/backend/test_auth* -v --cov=backend/api/auth`
  - Coverage must be ≥95%
  - All tests must pass (0 failures)
- [ ] Run integration tests
  - `pytest tests/integration/test_auth_flow.py`
  - Test login → access resource → refresh → logout flow
- [ ] Manual smoke test
  - Start dev server
  - Test auth endpoints via Postman/curl
  - Verify error messages unchanged

**Deliverable:** Test report showing 100% pass rate

---

### 3.4 Ruff Validation 🔴
- [ ] Verify all violations resolved
  - Run: `ruff check backend/api/auth/ --select C901,PERF203`
  - Expected: 0 violations (down from 25)
- [ ] Compare with baseline
  - Load `auth_violations_baseline.json`
  - Generate diff report
  - Confirm all 13 C901 + 12 PERF203 eliminated
- [ ] Update Ruff baseline
  - Update `.ruff_baseline.json` if using baseline mode
  - Document remaining violations in other subsystems

**Deliverable:** Clean Ruff report for auth subsystem

---

### 3.5 Update OpenSpec Operations Spec 🔴
- [ ] Write spec deltas in `specs/operations/spec.md`
  - MODIFIED: Auth validation composable helpers requirement
  - ADDED: Batch operations error handler requirement
  - Include 4 scenarios with GIVEN/WHEN/THEN
- [ ] Validate spec syntax
  - Run: `openspec validate refactor-auth-complexity-p3 --strict`
  - Fix any validation errors
- [ ] Cross-reference related specs
  - Link to cache orchestration requirement (precedent)
  - Link to resilience testing requirement

**Deliverable:** Validated spec deltas

---

### 3.6 Update Architecture Documentation 🟡
- [ ] Update `docs/ARCHITECTURE.md`
  - Add "Complexity Management" section
  - Document helper extraction pattern
  - Document validation-first pattern
- [ ] Update `CLAUDE.md`
  - Add refactoring best practices
  - Document when to extract helpers (C901 >10)
  - Add PERF203 elimination guidelines
- [ ] Create pattern library
  - `docs/patterns/helper-extraction.md`
  - `docs/patterns/validation-first.md`
  - Include code examples from this refactoring

**Deliverable:** Updated architecture docs + pattern library

---

### 3.7 Code Review & Submission 🔴
- [ ] Create PR with descriptive title
  - Title: "refactor(auth): Reduce complexity (C901/PERF203) - Phase 3"
  - Link to OpenSpec proposal
  - Include before/after complexity metrics
- [ ] Self-review checklist
  - All tests passing
  - No functional changes (behavior preservation)
  - Code follows project style guide
  - Documentation updated
- [ ] Request 2+ reviewer approvals
- [ ] Address review feedback
- [ ] Merge after approval

**Deliverable:** Merged PR with complexity improvements

---

### 3.8 Archive OpenSpec Change 🔴
- [ ] Run `openspec archive refactor-auth-complexity-p3`
- [ ] Verify archived in `openspec/changes/archive/2025-01-19-refactor-auth-complexity-p3/`
- [ ] Update project status
  - Mark Phase 1 complete in tracking doc
  - Plan Phase 2 kick-off (services subsystem)
- [ ] Celebrate! 🎉
  - Auth subsystem now has 0 complexity violations
  - Established patterns for Phase 2-3

**Deliverable:** Archived change + Phase 2 planning doc

---

## Dependencies

### Prerequisites
- ✅ Phase 1-3 Ruff fixes completed (E722, B007, etc.)
- ✅ Auth test suite exists with reasonable coverage
- ✅ CI pipeline includes Ruff checks

### Blocks
- 🚫 Phase 2 (services refactoring) - blocked until this completes
- 🚫 CI lint enforcement - requires all 3 phases complete

---

## Risk Mitigation Checklist

Before starting each task, review risks:
- [ ] Have I identified all affected tests?
- [ ] Do I understand the current behavior I'm preserving?
- [ ] Have I considered edge cases (empty inputs, null values, etc.)?
- [ ] Is there a rollback plan if this breaks production?

After completing each task:
- [ ] Did tests pass?
- [ ] Did complexity reduce as expected?
- [ ] Are error messages identical to before?
- [ ] Did I document any surprises or learnings?

---

## Progress Tracking

Update this section daily:

**Day 1:** _____ (e.g., "Tasks 1.1-1.2 complete, 1.3 in progress")
**Day 2:** _____
**Day 3:** _____
**Day 4:** _____
**Day 5:** _____
**Day 6:** _____
**Day 7:** _____

**Blocked Items:** None currently
**Unexpected Issues:** None currently

---

## Success Criteria

Final validation checklist:
- [ ] All 13 C901 violations eliminated (Ruff clean)
- [ ] All 12 PERF203 violations eliminated
- [ ] 100% auth test suite passing
- [ ] Average function complexity <8
- [ ] No performance regression (±5%)
- [ ] Code review approved by 2+ reviewers
- [ ] OpenSpec proposal archived
- [ ] Documentation updated (architecture + patterns)
- [ ] CI pipeline green

**Definition of Done:** All checklist items complete + PR merged
