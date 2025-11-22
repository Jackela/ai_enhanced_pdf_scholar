# API Routes Baseline Report: Phase 2 Refactoring

**Date:** 2025-01-20
**OpenSpec Change:** refactor-api-routes-complexity
**Phase:** 2 of 3 (Auth → **Routes** → Services)

---

## 📊 Violation Summary

### Total Violations: 8

**C901 (Cyclomatic Complexity >10):** 4 violations
**PERF203 (Try-Except in Loop):** 4 violations

---

## 🔴 C901 Violations (4 instances)

### 1. system.py:450 - `detailed_health_check` (C901: 16) 🔥 HIGHEST

**Complexity:** 16 (60% over limit)
**Lines:** ~150 lines
**Function:** Comprehensive health status check

**Decision Points:**
- Memory status evaluation (3 conditionals)
- Disk status evaluation (3 conditionals)
- CPU status evaluation (3 conditionals)
- Database connectivity (2 conditionals)
- RAG service status (2 conditionals)
- Cache status (2 conditionals)
- Overall status aggregation (1 conditional)

**Refactoring Target:** Extract 8 helpers, reduce to C901 ≤3

---

### 2. system.py:793 - `performance_health_check` (C901: 13)

**Complexity:** 13 (30% over limit)
**Lines:** ~100 lines
**Function:** Performance metrics monitoring

**Decision Points:**
- Cache hit rate calculation (3 conditionals)
- Query performance thresholds (3 conditionals)
- Service latency evaluation (3 conditionals)
- Metric aggregation (2 conditionals)
- Threshold comparisons (2 conditionals)

**Refactoring Target:** Extract 4 helpers, reduce to C901 ≤3

---

### 3. documents.py:454 - `upload_document` (C901: 13)

**Complexity:** 13 (30% over limit)
**Lines:** ~120 lines
**Function:** PDF document upload with validation

**Decision Points:**
- File type validation (2 conditionals)
- File size validation (2 conditionals)
- Duplicate detection strategy (3 conditionals)
- Overwrite logic (2 conditionals)
- Error handling (2 conditionals)
- Database record creation (2 conditionals)

**Refactoring Target:** Extract 4 helpers, reduce to C901 ≤3
**Day:** Day 2

---

### 4. async_rag.py:300 - `websocket_rag_endpoint` (C901: 11)

**Complexity:** 11 (10% over limit)
**Lines:** ~100 lines
**Function:** WebSocket endpoint for streaming RAG queries

**Decision Points:**
- Connection management (2 conditionals)
- Message parsing (2 conditionals)
- Query validation (3 conditionals)
- Stream orchestration (2 conditionals)
- Error recovery (2 conditionals)

**Refactoring Target:** Extract 3 helpers + result pattern, reduce to C901 ≤4
**Day:** Day 2

---

## ⚠️ PERF203 Violations (4 instances)

### 1. system.py:349 - Try-Except in Secrets Backup Loop

**Context:** Secrets backup iteration with per-item error handling

```python
for secret_key in secret_keys:
    try:
        backup_secret(secret_key)  # PERF203
    except Exception as e:
        logger.error(f"Backup failed: {e}")
```

**Refactoring Target:** Result object pattern
**Day:** Day 1

---

### 2. metrics_websocket.py:84 - Try-Except in Metrics Collection Loop

**Context:** CPU/memory/disk metrics collection

```python
for metric_type in ALL_METRICS:
    try:
        collect_metric(metric_type)  # PERF203
    except MetricsError as e:
        errors.append(str(e))
```

**Refactoring Target:** Collect results, handle errors after loop
**Day:** Day 3

---

### 3. metrics_websocket.py:131 - Try-Except in Network Metrics Loop

**Context:** Network interface metrics streaming

```python
for interface in interfaces:
    try:
        data = get_interface_stats(interface)  # PERF203
    except Exception as e:
        logger.warning(f"Interface {interface} failed")
```

**Refactoring Target:** Result object pattern
**Day:** Day 3

---

### 4. metrics_websocket.py:180 - Try-Except in Process Metrics Loop

**Context:** Per-process resource monitoring

```python
for process in processes:
    try:
        stats = process.get_stats()  # PERF203
    except ProcessError as e:
        continue
```

**Refactoring Target:** Filter valid processes before loop
**Day:** Day 3

---

## 📈 Complexity Distribution

| File | Functions | C901 >10 | Max Complexity | PERF203 |
|------|-----------|----------|----------------|---------|
| system.py | 12 | 2 | 16 | 1 |
| documents.py | 8 | 1 | 13 | 0 |
| async_rag.py | 5 | 1 | 11 | 0 |
| metrics_websocket.py | 6 | 0 | 9 | 3 |
| **TOTAL** | **31** | **4** | **16** | **4** |

---

## 🧪 Test Coverage Baseline

### Existing Route Tests

**Document Routes:**
- `test_documents_upload_route.py` - 6 tests (upload validation, duplicates)
- `test_documents_download_route.py` - 4 tests
- `test_documents_api_contract.py` - 12 tests

**System Routes:**
- `test_system_route_basic.py` - (import issues, needs PYTHONPATH)
- `test_settings_route_comprehensive.py` - (import issues, needs PYTHONPATH)

**Other Routes:**
- `test_auth_routes_login_refresh.py` - 8 tests
- `test_queries_route_comprehensive.py` - 15 tests
- `test_rag_route_comprehensive.py` - 10 tests

**Total Existing:** ~55 route tests

**Coverage Gaps:**
- No unit tests for helper functions (all are integration tests)
- No tests for WebSocket message processing
- No tests for health check components

---

## 🎯 Refactoring Targets (Day 1 Only)

### Day 1 Scope

**Files:**
- `backend/api/routes/system.py` (2 C901, 1 PERF203)

**Violations to Eliminate:**
- C901: 2 violations (complexity 16, 13)
- PERF203: 1 violation (line 349)

**Helpers to Extract:** 12 total
- detailed_health_check: 8 helpers
- performance_health_check: 4 helpers

**Tests to Create:** 15-20 unit tests
- File: `tests/backend/test_routes_system_helpers.py`

**Expected Outcomes:**
- C901 violations: 4 → 2 (50% reduction for Phase 2, 100% for Day 1)
- PERF203 violations: 4 → 3 (75% remaining, 25% Day 1)
- New tests: +15-20
- Complexity reduction: 16,13 → <3 (≥80%)

---

## 📋 Methodology

**Pattern:** Helper Extraction (proven on auth DI)

**Approach:**
1. Identify logical concerns in complex function
2. Extract each concern to private helper method
3. Refactor main function to orchestrator (calls helpers)
4. Create unit tests for each helper with mocked dependencies
5. Verify integration tests still pass (behavior preservation)

**Quality Gates:**
- All helpers have C901 ≤5
- Main orchestrator has C901 ≤3
- All existing tests pass unchanged
- All new helper tests pass

---

## 🔄 Comparison to Phase 1 (Auth)

| Metric | Phase 1 (Auth) | Phase 2 Day 1 (Routes) |
|--------|----------------|------------------------|
| **Total Violations** | 4 | 3 (Day 1 only) |
| **C901 Instances** | 2 (complexity 13, 15) | 2 (complexity 16, 13) |
| **PERF203 Instances** | 2 | 1 |
| **Max Complexity** | 15 | 16 |
| **Files Modified** | 3 | 1 |
| **Helpers Extracted** | 6 | 12 |
| **Tests Created** | 49 | 15-20 (target) |
| **Timeline** | 2 days | 1 day |

**Similarity:** Day 1 routes scope is comparable to full auth Phase 1

---

## 📝 Next Steps

### Immediate (Day 1)

1. ✅ Baseline report created
2. Extract helpers from `detailed_health_check` (C901: 16 → <5)
3. Extract helpers from `performance_health_check` (C901: 13 → <5)
4. Fix PERF203 at system.py:349
5. Create 15-20 unit tests
6. Verify all tests passing
7. Commit Day 1 changes

### Day 2

- Refactor `upload_document` (C901: 13 → <5)
- Refactor `websocket_rag_endpoint` (C901: 11 → <5)
- Create 20-25 unit tests

### Day 3

- Fix 3 PERF203 in `metrics_websocket.py`
- Create 10-12 unit tests
- Final integration testing
- Performance benchmarking

---

## ✅ Success Criteria (Day 1)

- [ ] C901 violations in system.py: 2 → 0
- [ ] PERF203 violations in system.py: 1 → 0
- [ ] All 12 helpers have C901 ≤5
- [ ] 15-20 new unit tests created
- [ ] All existing route tests pass
- [ ] Ruff checks pass on system.py

---

**Baseline Recorded:** 2025-01-20 11:15 UTC
**Ready to Begin:** Day 1 Refactoring

**Command to verify:**
```bash
ruff check backend/api/routes/system.py --select C901,PERF203
# Current: 3 errors (2 C901, 1 PERF203)
# Target: 0 errors
```
