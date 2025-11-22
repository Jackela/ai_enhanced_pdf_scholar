# Change: Fix CI Complexity and Readability Violations

## Why
The codebase contains 56 code complexity and readability violations that make the code harder to maintain, test, and understand. High complexity functions (C901) are difficult to reason about and prone to bugs. Nested if statements (SIM102) reduce readability unnecessarily.

Current complexity issues:
- **C901 (37 violations)**: Functions exceeding McCabe complexity threshold of 10
  - 4 functions with complexity > 20 (critical)
  - 5 functions with complexity 15-20 (high)
  - 28 functions with complexity 11-14 (medium)
- **SIM102 (19 violations)**: Nested if statements that can be collapsed

Top offenders:
- `run_complete_uat.py::start_api_server` - Complexity 29
- `scripts/alert_response_automation.py::handle_disk_space` - Complexity 31
- `backend/services/db_performance_monitor.py::get_database_health` - Complexity 21

## What Changes
- **Complexity Reduction (C901 - 37 violations)**:
  - Extract helper methods from complex functions
  - Apply strategy pattern for conditional logic
  - Use early returns to reduce nesting
  - Split monolithic functions into focused units
  - Target: Max complexity ≤ 10 for all functions

- **Control Flow Simplification (SIM102 - 19 violations)**:
  - Collapse nested if statements using logical AND
  - Pattern: `if a: if b:` → `if a and b:`
  - Mechanical refactoring across 19 occurrences

**No breaking changes**: All refactorings preserve existing behavior.

## Impact
**Affected Specs:**
- code-complexity (ADDED)
- code-readability (ADDED)

**Affected Code:**
- **Priority 1: Critical Complexity** (4 files, complexity > 20)
  - `run_complete_uat.py` (complexity 29)
  - `scripts/alert_response_automation.py` (complexity 31)
  - `backend/services/db_performance_monitor.py` (complexity 21)
  - These require significant refactoring

- **Priority 2: High Complexity** (5 files, complexity 15-20)
  - `backend/api/security/request_signing.py` (complexity 16)
  - Moderate refactoring effort

- **Priority 3: Medium Complexity** (21 files, complexity 11-14)
  - Various backend and src files
  - Minor refactoring with helper extraction

- **SIM102 Files** (10 files with 19 violations)
  - `backend/services/cache_warming_service.py` (5 violations)
  - `backend/core/secrets.py` (2 violations)
  - Other files (12 violations)

**Breaking Changes:** None

**Risk Level:** Medium-High
- High complexity refactoring: Medium-High risk (logic changes, requires thorough testing)
- Collapsible if fixes: Low risk (mechanical transformation)

**Success Criteria:**
- ✅ Zero C901 violations (max complexity ≤ 10 for all functions)
- ✅ Zero SIM102 violations (all nested ifs collapsed)
- ✅ All tests pass (no behavioral regressions)
- ✅ Code coverage maintained or improved
- ✅ Complex functions have clear helper methods

**Dependencies:**
- Requires Phase 1 completion (CI must be functional for testing)
- Can run in parallel with Phase 2 after Phase 1
