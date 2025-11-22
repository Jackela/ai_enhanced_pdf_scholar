# Implementation Tasks

## 1. Setup & Analysis
- [ ] 1.1 Run `ruff check src backend --select=PERF203,PERF401 --output-format=json` to get detailed violation list
- [ ] 1.2 Group violations by file and severity
- [ ] 1.3 Create helper functions for common refactoring patterns
- [ ] 1.4 Set up performance benchmarks for affected code paths

## 2. Group A: Cache Services (PERF203 - 35 violations)
- [ ] 2.1 Fix `backend/services/cache_coherency_manager.py` (8 violations)
  - [ ] Extract try-except from coherency check loop
  - [ ] Create `safe_check_coherency()` wrapper function
- [ ] 2.2 Fix `backend/services/cache_warming_service.py` (7 violations)
  - [ ] Extract try-except from cache warming loop
  - [ ] Implement Result pattern for cache operations
- [ ] 2.3 Fix `backend/services/cache_optimization.py` (5 violations)
- [ ] 2.4 Fix `backend/services/integrated_cache_manager.py` (4 violations)
- [ ] 2.5 Fix `backend/services/l2_redis_cache.py` (3 violations)
- [ ] 2.6 Fix remaining cache service files (8 violations across 5 files)
- [ ] 2.7 Run cache service tests to verify no regressions

## 3. Group B: Database Layer (PERF203 - 30 violations)
- [ ] 3.1 Fix `backend/database/production_config.py` (5 violations)
  - [ ] Extract try-except from connection validation loop
  - [ ] Use connection pool's built-in error handling
- [ ] 3.2 Fix `backend/database/sharding_manager.py` (5 violations)
  - [ ] Extract try-except from shard iteration
  - [ ] Implement shard health check batch operation
- [ ] 3.3 Fix `backend/database/postgresql_config.py` (4 violations)
- [ ] 3.4 Fix `backend/config/redis_cluster.py` (4 violations)
- [ ] 3.5 Fix remaining database files (12 violations across 4 files)
- [ ] 3.6 Run database integration tests to verify connectivity

## 4. Group C: Core Services (PERF203 - 61 violations)
- [ ] 4.1 Fix `backend/services/connection_pool_manager.py` (8 violations)
  - [ ] Extract try-except from connection checkout loop
  - [ ] Use async context managers for cleanup
- [ ] 4.2 Fix `backend/services/redis_monitoring.py` (6 violations)
- [ ] 4.3 Fix `backend/services/secrets_integration.py` (5 violations)
- [ ] 4.4 Fix `backend/api/security/ip_whitelist.py` (5 violations)
- [ ] 4.5 Fix `src/repositories/vector_repository.py` (4 violations)
- [ ] 4.6 Fix `src/services/error_recovery.py` (5 violations)
- [ ] 4.7 Fix `src/services/rag/file_manager.py` (4 violations)
- [ ] 4.8 Fix remaining core service files (24 violations across 10 files)
- [ ] 4.9 Run core service tests to verify functionality

## 5. List Operations (PERF401 - 28 violations)
- [ ] 5.1 Fix `backend/core/secrets_migration.py` (4 violations)
  - [ ] Replace manual loop with list comprehension
  - [ ] Pattern: `result = [transform(x) for x in items]`
- [ ] 5.2 Fix `backend/api/routes/performance_monitoring.py` (2 violations)
- [ ] 5.3 Fix `backend/api/routes/rbac_admin.py` (2 violations)
- [ ] 5.4 Fix `backend/api/routes/rate_limit_admin.py` (1 violation)
- [ ] 5.5 Fix `backend/api/cors_config.py` (2 violations)
  - [ ] Replace manual append with list.extend()
- [ ] 5.6 Fix `src/services/rag/chunking_strategies.py` (3 violations)
- [ ] 5.7 Fix remaining files (14 violations across 4 files)
- [ ] 5.8 Run full test suite to verify list operation changes

## 6. Validation & Performance Testing
- [ ] 6.1 Run `ruff check src backend --select=PERF203,PERF401` to verify 0 violations
- [ ] 6.2 Run full pytest suite: `pytest tests/ -n auto --dist=loadfile`
- [ ] 6.3 Run performance benchmarks on affected services:
  - [ ] 6.3.1 Cache hit/miss latency
  - [ ] 6.3.2 Database query processing time
  - [ ] 6.3.3 Connection pool checkout time
- [ ] 6.4 Compare benchmark results with baseline (must not regress)
- [ ] 6.5 Verify error logging still captures all expected errors
- [ ] 6.6 Update this tasks.md with results

## 7. Documentation
- [ ] 7.1 Document Result/Either pattern in helper functions
- [ ] 7.2 Add inline comments explaining refactored error handling
- [ ] 7.3 Update CLAUDE.md with performance optimization patterns
- [ ] 7.4 Document performance improvements in commit messages

## Completion Criteria
All checkboxes above must be `[x]` before marking this change as ready for archive.

## Estimated Effort
- Group A (Cache): 5-6 hours
- Group B (Database): 4-5 hours
- Group C (Core): 5-6 hours
- List Operations: 2-3 hours
- Testing: 2-3 hours
- **Total: 18-23 hours**

## Dependencies
- **Requires:** Phase 1 completion (critical CI blockers fixed)
- **Blocks:** None (Phase 3 can start in parallel after Phase 1)
