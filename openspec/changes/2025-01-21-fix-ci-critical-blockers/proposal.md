# Change: Fix Critical CI Blockers

## Why
The CI pipeline currently fails due to critical issues that prevent code from being tested, built, and deployed. These issues block all development work and must be resolved immediately to restore CI functionality.

Current blocking issues:
- Backend tests fail with import errors (`ModuleNotFoundError: No module named 'backend.api'`)
- Frontend TypeScript compilation fails with 11 type errors in metricsWebSocket.ts
- 16 critical security vulnerabilities (SQL injection, weak RNG)
- 2 Black formatting violations
- 26 ESLint warnings exceed max threshold (configured as 0)

## What Changes
- **Test Infrastructure**: Fix PyMuPDF import issue causing backend test failures by implementing lazy imports in document_preview_service.py
- **Frontend Type Safety**: Add missing type definitions to WebSocketMessage interface in metricsWebSocket.ts
- **Security Fixes**:
  - Replace SQL string concatenation with parameterized queries (S608 - 9 violations)
  - Replace `random` module with `secrets` module for cryptographic operations (S311 - 7 violations)
- **Code Formatting**: Auto-fix Black formatting in 2 files (l2_redis_cache.py, secrets_monitoring_service.py)
- **Frontend Quality**: Fix 26 ESLint warnings (React hooks dependencies, explicit `any` types)

## Impact
**Affected Specs:**
- test-infrastructure (ADDED)
- security (ADDED)
- code-quality (MODIFIED)

**Affected Code:**
- Backend: 18 files
  - `src/services/document_preview_service.py` (test import fix)
  - 9 files with SQL injection vulnerabilities
  - 7 files with weak RNG usage
  - 2 files needing Black formatting

- Frontend: 12 files
  - `frontend/src/lib/metricsWebSocket.ts` (11 TypeScript errors)
  - 11 files with ESLint warnings

**Breaking Changes:** None

**Risk Level:** Low-Medium
- Test import fix: Medium risk (could affect test discovery)
- TypeScript fixes: Low risk (compile-time only)
- Security fixes: Low risk (behavior-preserving hardening)
- Formatting: Zero risk (automated)

**Success Criteria:**
- ✅ All backend tests run without import errors
- ✅ Frontend TypeScript compilation succeeds
- ✅ Zero critical security violations (Bandit HIGH severity)
- ✅ Zero Black formatting violations
- ✅ ESLint warnings ≤ 0 (CI requirement)
- ✅ CI pipeline passes all quality gates
