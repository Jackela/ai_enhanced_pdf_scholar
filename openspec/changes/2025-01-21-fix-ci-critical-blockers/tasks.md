# Implementation Tasks

## 1. Backend Test Infrastructure Fix
- [ ] 1.1 Investigate PyMuPDF import chain in `src/services/document_preview_service.py`
- [ ] 1.2 Implement lazy import pattern for `fitz` (PyMuPDF) module
- [ ] 1.3 Verify all 5 affected test files can import backend.api modules
- [ ] 1.4 Run full test suite to confirm no import errors
- [ ] 1.5 Document the lazy import pattern in code comments

## 2. Frontend TypeScript Fixes
- [ ] 2.1 Add missing `SystemMetrics` interface to `metricsWebSocket.ts` or import it
- [ ] 2.2 Extend `WebSocketMessage` interface with missing properties:
  - [ ] 2.2.1 Add `message?: string`
  - [ ] 2.2.2 Add `health_summary?: SystemHealthStatus`
  - [ ] 2.2.3 Add `alerts?: Alert[]`
  - [ ] 2.2.4 Add `subscribed_metrics?: string[]`
  - [ ] 2.2.5 Add `error?: string`
- [ ] 2.3 Run `npm run type-check` to verify all errors resolved
- [ ] 2.4 Verify frontend build succeeds

## 3. Security Fixes - SQL Injection (S608)
- [ ] 3.1 Fix `backend/database/postgresql_config.py` (4 violations)
  - [ ] 3.1.1 Replace string formatting in SQL queries with parameterized queries
  - [ ] 3.1.2 Use psycopg2 placeholders (%s) or SQLAlchemy text() with bound parameters
- [ ] 3.2 Fix `backend/database/sharding_manager.py` (1 violation)
- [ ] 3.3 Fix `backend/services/incremental_backup_service.py` (2 violations)
- [ ] 3.4 Fix remaining 2 files with S608 violations
- [ ] 3.5 Run Bandit to verify S608 violations reduced to 0

## 4. Security Fixes - Weak RNG (S311)
- [ ] 4.1 Identify all uses of `random` module for security-sensitive operations
- [ ] 4.2 Replace `random.random()` with `secrets.token_hex()` or `secrets.SystemRandom()`
- [ ] 4.3 Fix `backend/database/production_config.py` (2 violations)
- [ ] 4.4 Fix `backend/services/l2_redis_cache.py` (1 violation)
  - Note: Cache TTL jitter may use `random` (non-security context) - verify context
- [ ] 4.5 Fix remaining 4 files with S311 violations
- [ ] 4.6 Run Bandit to verify S311 violations reduced to 0

## 5. Code Formatting Fixes
- [ ] 5.1 Run `black backend/services/l2_redis_cache.py backend/services/secrets_monitoring_service.py`
- [ ] 5.2 Verify Black formatting check passes with `black --check src backend`
- [ ] 5.3 Commit formatting changes

## 6. Frontend ESLint Fixes (26 warnings)
- [ ] 6.1 Fix React Hook dependency warnings (5 files):
  - [ ] 6.1.1 `DocumentPreviewModal.tsx` - Add `toast` to useEffect deps or use useCallback
  - [ ] 6.1.2 `CollectionViewer.tsx` - Add `loadCollectionDetails` to deps
  - [ ] 6.1.3 `CreateCollectionModal.tsx` - Add `fetchAvailableDocuments` to deps
  - [ ] 6.1.4 `CollectionsView.tsx` - Add `fetchCollections` to deps
  - [ ] 6.1.5 `MonitoringDashboard.tsx` - Add `initializeConnection` to deps
- [ ] 6.2 Fix explicit `any` type warnings (21 warnings):
  - [ ] 6.2.1 `MonitoringDashboard.tsx` (9 warnings) - Define proper metric types
  - [ ] 6.2.2 `DatabaseMetricsPanel.tsx`, `SystemMetricsChart.tsx`, `WebSocketMetricsPanel.tsx` - Replace `any` with specific types
  - [ ] 6.2.3 `SecureMessage.tsx`, `ChatView.tsx`, `useSecurity.ts` - Replace `any` types
  - [ ] 6.2.4 `metricsWebSocket.ts`, `preload.ts`, `security.ts`, `vite.config.ts` - Replace `any` types
- [ ] 6.3 Run `npm run lint` to verify 0 warnings
- [ ] 6.4 Run `npm run build` to verify production build succeeds

## 7. Validation & Testing
- [ ] 7.1 Run complete CI checks locally:
  - [ ] 7.1.1 `ruff check src backend --select=F821,F401,F841,E902` (lightning check)
  - [ ] 7.1.2 `black --check src backend` (formatting)
  - [ ] 7.1.3 `bandit -r src backend -f json -o bandit-report.json` (security)
  - [ ] 7.1.4 `pytest tests/ -n auto --dist=loadfile` (backend tests)
  - [ ] 7.1.5 `npm run type-check` (TypeScript)
  - [ ] 7.1.6 `npm run lint` (ESLint)
  - [ ] 7.1.7 `npm run build` (frontend build)
- [ ] 7.2 Verify all critical issues resolved:
  - [ ] Test imports: 0 errors
  - [ ] TypeScript: 0 errors
  - [ ] Bandit HIGH: 0 violations
  - [ ] Black: 0 violations
  - [ ] ESLint: 0 warnings
- [ ] 7.3 Document any non-obvious changes in commit messages
- [ ] 7.4 Update this tasks.md with final status

## 8. Documentation
- [ ] 8.1 Add inline comments explaining lazy import pattern
- [ ] 8.2 Update CLAUDE.md if new patterns introduced
- [ ] 8.3 Document security fix rationale in commit messages

## Completion Criteria
All checkboxes above must be `[x]` before marking this change as ready for archive.

## Estimated Effort
- Backend: 6-8 hours
- Frontend: 4-6 hours
- Testing: 2-3 hours
- **Total: 12-17 hours**

## Dependencies
None - This is Phase 1 and must complete before other phases can begin.
