# Proposal: Refactor API Routes Complexity (Phase 2)

**Change ID:** `refactor-api-routes-complexity`
**Status:** Proposed
**Created:** 2025-01-20
**Capability:** `operations`
**Phase:** 2 of 3 (Auth → **Routes** → Services)

---

## What

Reduce cyclomatic complexity (C901) and eliminate performance anti-patterns (PERF203) in API routes subsystem by applying proven refactoring patterns from auth subsystem work.

**Scope:** 4 route files in `backend/api/routes/`
- `system.py` - Health check endpoints (2 C901, 1 PERF203)
- `documents.py` - Document upload endpoint (1 C901)
- `async_rag.py` - WebSocket RAG endpoint (1 C901)
- `metrics_websocket.py` - Metrics streaming (3 PERF203)

**Violations to Eliminate:**
- 4 C901 violations (complexity 11-16)
- 4 PERF203 violations (try-except in loops)
- Total: 8 violations → 0 violations

---

## Why

API routes are **user-facing critical paths** where complexity directly impacts:
- **Maintainability**: Complex endpoints harder to modify safely
- **Debuggability**: Multi-concern functions obscure error sources
- **Testability**: Monolithic endpoints resist unit testing
- **Performance**: Exception overhead in hot paths (WebSocket streams)

**Current State:**
- `system.py::detailed_health_check` has C901=16 (highest in codebase)
- WebSocket endpoints have PERF203 in message processing loops
- No granular unit tests for endpoint validation logic

**Success Criteria:**
- All 8 violations eliminated
- Complexity reduced by ≥70% (auth achieved 93%)
- 100% test suite passing
- Zero functional regressions

---

## How

Apply **proven patterns** from completed auth refactoring:

### Pattern 1: Helper Extraction (C901)
**For:** Complex orchestration endpoints (health checks, upload)

Extract concerns into focused helpers:
- `detailed_health_check` (C901: 16) →
  - `_check_system_resources()` - Memory/disk/CPU
  - `_check_database_status()` - DB connectivity
  - `_check_rag_status()` - RAG service health
  - `_check_cache_status()` - Cache health
  - `_aggregate_health_status()` - Status rollup

- `upload_document` (C901: 13) →
  - `_validate_file_upload()` - Type/size checks
  - `_handle_duplicate_detection()` - Duplicate logic
  - `_save_document_file()` - File persistence
  - `_create_document_record()` - Database insert

**Outcome:** Main endpoints become 5-10 line orchestrators (C901 ≤3)

### Pattern 2: Validation-First (PERF203)
**For:** Loop-based processing (WebSocket message streams)

Move exception handling outside loops:
- Collect results in loop (no try-except)
- Filter errors after loop completes
- Batch error reporting

**Outcome:** 4 PERF203 violations eliminated, improved stream performance

### Pattern 3: Comprehensive Testing
**For:** All extracted helpers

Create unit test suites:
- Mock dependencies for isolated testing
- Cover success + all error paths
- Verify behavior preservation

**Outcome:** 40-50 new unit tests (similar to auth's 49 tests)

---

## Impact

**Code Quality:**
- **Before:** 4 functions with C901 >10, 4 PERF203 violations
- **After:** 0 violations, all helpers C901 ≤5
- **Test Coverage:** +40-50 unit tests for helpers

**User-Facing Improvements:**
- Faster WebSocket message processing (no exception overhead)
- More reliable health checks (isolated component checks)
- Better error messages (granular validation feedback)

**Developer Experience:**
- Easier to debug (single-responsibility helpers)
- Safer to modify (comprehensive unit tests)
- Clearer to understand (orchestrator pattern)

---

## Timeline

**3 Days** (2-3 days, aligned with auth work that took 2 days)

- **Day 1:** System health checks (C901: 16, 13 → <5) + 1 PERF203
- **Day 2:** Document upload + WebSocket RAG (C901: 13, 11 → <5)
- **Day 3:** Metrics WebSocket PERF203 (3 violations) + comprehensive testing

---

## Dependencies

**Required:**
- ✅ Auth refactoring complete (patterns established)
- ✅ Existing route tests passing (baseline)

**Blockers:**
- None (routes are independent subsystem)

---

## Risks

**Low Risk:**
- **Pattern proven:** Same approach successfully used on auth
- **Clear scope:** 4 files, 8 violations (well-defined)
- **Isolated subsystem:** Routes don't affect auth/services

**Mitigations:**
- Behavior preservation testing (all existing tests must pass)
- Incremental approach (one file per day)
- Regression monitoring (test suite at each step)

---

## Alternatives Considered

**Option A: Fix only C901 (skip PERF203)**
- ❌ Leaves 4 performance anti-patterns in WebSocket hot paths
- ❌ Inconsistent with completed auth work

**Option B: Defer to Phase 3 (do services first)**
- ❌ Routes are higher-impact than services (user-facing)
- ❌ Loses momentum (patterns fresh from auth work)

**Option C: Opportunistic fixes without OpenSpec**
- ❌ Violates project standards (CLAUDE.md requires OpenSpec)
- ❌ No tracking/documentation for review

**Selected: Structured refactoring (this proposal)**
- ✅ Consistent with project standards
- ✅ Tackles highest-complexity code first
- ✅ Maintains momentum from auth work

---

## Success Metrics

**Quantitative:**
- [ ] C901 violations: 4 → 0 (100% elimination)
- [ ] PERF203 violations: 4 → 0 (100% elimination)
- [ ] Average endpoint complexity: 13.25 → <5 (≥62% reduction)
- [ ] New unit tests: ≥40 tests created
- [ ] Test suite: 100% passing

**Qualitative:**
- [ ] Code review confirms single-responsibility helpers
- [ ] Endpoint orchestration is self-documenting
- [ ] Error messages remain user-friendly
- [ ] No performance regressions in health checks/uploads

---

## Related Work

**Precedent:**
- `archive/2025-11-20-refactor-auth-complexity-p3` - Auth subsystem (4 violations → 0)

**Next Phase:**
- Phase 3: Services subsystem refactoring (35+ violations)

**Patterns Established:**
- Helper Extraction (auth DI, password validation)
- Validation-First (migration loops)
- Strategy Pattern (password validators)
