# Tasks: API Routes Complexity Refactoring

**Change ID:** `refactor-api-routes-complexity`
**Timeline:** 3 days
**Phase:** 2 of 3 (Auth → **Routes** → Services)

---

## Day 1: System Health Checks (C901: 16, 13 → <5)

### 1.1 Baseline & Planning

- [ ] Run baseline Ruff checks and record violations
  ```bash
  ruff check backend/api/routes/ --select C901,PERF203 > reports/routes_baseline.txt
  ```
- [ ] Run existing route tests to establish baseline
  ```bash
  pytest tests/backend/test_routes_* -v
  ```
- [ ] Create `reports/routes_baseline_report.md` documenting:
  - 4 C901 violations (complexity 11-16)
  - 4 PERF203 violations
  - Current test coverage

### 1.2 Extract Helpers from `detailed_health_check`

**File:** `backend/api/routes/system.py:450`

- [ ] Create `_check_system_resources()` helper
  - Extract memory/disk/CPU checks (currently lines 458-490)
  - Return dict with system resource status
  - Helper complexity target: ≤3
- [ ] Create `_evaluate_memory_status(memory)` helper
  - Extract memory threshold logic
  - Helper complexity: ≤2
- [ ] Create `_evaluate_disk_status(disk)` helper
  - Extract disk threshold logic
  - Helper complexity: ≤2
- [ ] Create `_evaluate_cpu_status(cpu)` helper
  - Extract CPU threshold logic
  - Helper complexity: ≤2
- [ ] Create `_check_database_status(db)` helper
  - Extract database connectivity check
  - Helper complexity: ≤2
- [ ] Create `_check_rag_status(rag_service)` helper
  - Extract RAG service health check
  - Helper complexity: ≤2
- [ ] Create `_check_cache_status()` helper
  - Extract cache health check
  - Helper complexity: ≤2
- [ ] Create `_aggregate_health_status(components)` helper
  - Extract overall status determination logic
  - Helper complexity: ≤3
- [ ] Refactor `detailed_health_check` to orchestrator (10-15 lines)
  - Call helpers in sequence
  - Aggregate results
  - Return response
- [ ] Verify C901 reduces from 16 to ≤3
  ```bash
  ruff check backend/api/routes/system.py --select C901
  ```

### 1.3 Extract Helpers from `performance_health_check`

**File:** `backend/api/routes/system.py:793`

- [ ] Create `_collect_cache_metrics()` helper
  - Extract cache hit rate calculation
  - Helper complexity: ≤2
- [ ] Create `_collect_query_metrics()` helper
  - Extract query performance monitoring
  - Helper complexity: ≤2
- [ ] Create `_collect_service_latency()` helper
  - Extract service latency checks
  - Helper complexity: ≤2
- [ ] Create `_evaluate_performance_thresholds(metrics)` helper
  - Extract threshold comparison logic
  - Helper complexity: ≤3
- [ ] Refactor `performance_health_check` to orchestrator
- [ ] Verify C901 reduces from 13 to ≤3

### 1.4 Fix PERF203 in `system.py:349`

**File:** `backend/api/routes/system.py:349`

- [ ] Identify the try-except in loop
- [ ] Create result object class for error handling
- [ ] Refactor loop to collect results (no try-except inside)
- [ ] Handle errors after loop completes
- [ ] Verify PERF203 eliminated
  ```bash
  ruff check backend/api/routes/system.py --select PERF203
  ```

### 1.5 Create Unit Tests for System Route Helpers

**File:** `tests/backend/test_routes_system_helpers.py`

- [x] Test `_evaluate_memory_status()`
  - Test healthy status (<80%)
  - Test warning status (80-90%)
  - Test critical status (>90%)
- [x] Test `_evaluate_disk_status()`
  - Test healthy, warning, critical thresholds
- [x] Test `_evaluate_cpu_status()`
  - Test healthy, warning, critical thresholds
- [x] Test `_check_database_status()`
  - Test connected status
  - Test connection failure
  - Mock database connection
- [x] Test `_check_rag_status()`
  - Test RAG service ready
  - Test RAG service unavailable
  - Mock RAG service
- [x] Test `_check_storage_status()`
  - Test storage healthy
  - Test storage not initialized
  - Test directory missing
- [x] Test `_check_api_configuration()`
  - Test API key configured/not configured
- [x] Test `_calculate_overall_health()`
  - Test all healthy → overall healthy
  - Test one warning → overall warning
  - Test one critical → overall critical
- [x] Test `_check_system_resources()`
  - Integration test for resource collection
- [x] Test all 11 performance helper functions
  - CPU/memory/disk/network/process metrics
  - Database performance
  - Health evaluators
- [x] Target: 15-20 unit tests for system helpers
  - **Actual: 55 unit tests created** ✅

### 1.6 Day 1 Checkpoint

- [x] Run all route tests to verify behavior preservation
  ```bash
  pytest tests/backend/test_routes_* -v
  # Result: 95 tests passed (55 new + 40 existing)
  ```
- [x] Verify C901 violations reduced: 2 → 0
  - system.py:450 detailed_health_check (C901: 16 → <5) ✅
  - system.py:793 performance_health_check (C901: 13 → <5) ✅
- [x] Verify PERF203 violations reduced: 1 → 0
  - system.py:349 compliance standards loop ✅
- [x] Commit Day 1 changes
  ```bash
  # Commit 1: Refactored helpers (20 helpers extracted)
  git commit 61b1060f
  # Commit 2: Unit tests (55 tests created)
  git commit 1dafdbde
  ```

---

## Day 2: Upload & WebSocket Endpoints (C901: 13, 11 → <5)

### 2.1 Extract Helpers from `upload_document`

**File:** `backend/api/routes/documents.py:454`

- [ ] Create `_validate_file_upload(file)` helper
  - Extract file type validation (lines 498-503)
  - Extract file size validation
  - Raises HTTPException(415, 413) for invalid files
  - Helper complexity: ≤2
- [ ] Create `_handle_duplicate_detection()` helper
  - Extract duplicate check logic
  - Handle check_duplicates flag
  - Handle overwrite_duplicates flag
  - Return existing document or None
  - Helper complexity: ≤3
- [ ] Create `_save_document_file(file, documents_dir)` helper
  - Extract file persistence logic
  - Handle file write errors
  - Return saved file path
  - Helper complexity: ≤2
- [ ] Create `_create_document_record(file_path, title, library_service)` helper
  - Extract database record creation
  - Call library service
  - Return document model
  - Helper complexity: ≤2
- [ ] Refactor `upload_document` to orchestrator (12-18 lines)
  - Validate file
  - Check duplicates
  - Save file
  - Create record
  - Return response
- [ ] Verify C901 reduces from 13 to ≤3
  ```bash
  ruff check backend/api/routes/documents.py --select C901
  ```

### 2.2 Extract Helpers from `websocket_rag_endpoint`

**File:** `backend/api/routes/async_rag.py:300`

- [ ] Create `MessageResult` dataclass
  - Fields: success, data, error_type, error_message
  - Method: `to_dict()` for JSON serialization
  - Method: `success(data)` class method
  - Method: `error(error_type, message)` class method
- [ ] Create `_validate_websocket_message(message)` helper
  - Extract message format validation
  - Return validated message or raise ValidationError
  - Helper complexity: ≤2
- [ ] Create `_process_message_safe(message, rag_service)` helper
  - Process message and return MessageResult (no exceptions)
  - Handle ValidationError, RAGError
  - Helper complexity: ≤3
- [ ] Refactor `websocket_rag_endpoint` to use result pattern
  - Accept connection
  - Loop: receive → process → send (no try-except in loop)
  - Handle WebSocketDisconnect only
- [ ] Verify C901 reduces from 11 to ≤4
  ```bash
  ruff check backend/api/routes/async_rag.py --select C901
  ```

### 2.3 Create Unit Tests for Upload & WebSocket Helpers

**File:** `tests/backend/test_routes_documents_helpers.py`

- [ ] Test `_validate_file_upload()`
  - Test valid PDF file
  - Test invalid content type (raises 415)
  - Test file too large (raises 413)
  - Mock UploadFile
- [ ] Test `_handle_duplicate_detection()`
  - Test no duplicates found
  - Test duplicate found, check_duplicates=False
  - Test duplicate found, overwrite=True
  - Test duplicate found, overwrite=False
  - Mock library service
- [ ] Test `_save_document_file()`
  - Test successful file save
  - Test file write error
  - Mock file system
- [ ] Test `_create_document_record()`
  - Test successful record creation
  - Mock library service
- [ ] Target: 12-15 unit tests for upload helpers

**File:** `tests/backend/test_routes_websocket_helpers.py`

- [ ] Test `MessageResult` dataclass
  - Test success() constructor
  - Test error() constructor
  - Test to_dict() serialization
- [ ] Test `_validate_websocket_message()`
  - Test valid message format
  - Test missing query field
  - Test query too long
- [ ] Test `_process_message_safe()`
  - Test successful processing
  - Test validation error handling
  - Test RAG error handling
  - Mock RAG service
- [ ] Target: 8-10 unit tests for WebSocket helpers

### 2.4 Day 2 Checkpoint

- [ ] Run all route tests to verify behavior preservation
  ```bash
  pytest tests/backend/test_routes_* -v
  ```
- [ ] Run upload integration tests
  ```bash
  pytest tests/integration/test_real_document_library.py -v
  ```
- [ ] Verify C901 violations reduced: 2 → 0 (total 4 → 0)
- [ ] Commit Day 2 changes
  ```bash
  git add backend/api/routes/documents.py backend/api/routes/async_rag.py \
           tests/backend/test_routes_documents_helpers.py \
           tests/backend/test_routes_websocket_helpers.py
  git commit -m "refactor(routes): Day 2 - Upload & WebSocket helpers (C901: 13,11 → <5)"
  git push origin v2.0-refactor
  ```

---

## Day 3: Metrics WebSocket PERF203 & Final Testing

### 3.1 Fix PERF203 in `metrics_websocket.py`

**File:** `backend/api/routes/metrics_websocket.py:84,131,180`

- [ ] Create `MetricResult` dataclass
  - Fields: metric_type, data, is_success, error_message
  - Method: `to_dict()` for JSON serialization
- [ ] Create `_collect_metric_safe(metric_type)` helper
  - Collect metric and return MetricResult (no exceptions)
  - Handle MetricsError
  - Helper complexity: ≤2
- [ ] Refactor metrics collection loops (3 instances)
  - Line 84: Refactor to result pattern
  - Line 131: Refactor to result pattern
  - Line 180: Refactor to result pattern
- [ ] Verify PERF203 violations eliminated (3 → 0)
  ```bash
  ruff check backend/api/routes/metrics_websocket.py --select PERF203
  ```

### 3.2 Create Unit Tests for Metrics WebSocket

**File:** `tests/backend/test_routes_metrics_helpers.py`

- [ ] Test `MetricResult` dataclass
  - Test success result
  - Test error result
  - Test to_dict() serialization
- [ ] Test `_collect_metric_safe()`
  - Test successful metric collection (cpu, memory, disk, network)
  - Test metric collection error
  - Mock metrics collection functions
- [ ] Test metrics loop refactoring
  - Test batch metric collection
  - Test error handling for individual metrics
- [ ] Target: 10-12 unit tests for metrics helpers

### 3.3 Comprehensive Testing & Verification

- [ ] Run full route test suite
  ```bash
  pytest tests/backend/test_routes* -v --cov=backend/api/routes
  ```
- [ ] Run integration tests
  ```bash
  pytest tests/integration/test_api_endpoints.py -v
  pytest tests/integration/test_real_document_library.py -v
  ```
- [ ] Verify test count increase
  - Before: ~30 route tests
  - After: ~70+ route tests (+40-50 new tests)
- [ ] Run Ruff checks on all routes
  ```bash
  ruff check backend/api/routes/ --select C901,PERF203
  ```
  - Expected: 0 C901 violations (down from 4)
  - Expected: 0 PERF203 violations (down from 4)

### 3.4 Performance Regression Testing

- [ ] Benchmark WebSocket message throughput
  ```bash
  python scripts/benchmark_websocket.py
  ```
  - Record baseline (before refactoring)
  - Record after PERF203 fixes
  - Expected: ≥10% improvement or neutral (±5%)
- [ ] Benchmark health check latency
  ```bash
  python scripts/benchmark_health_checks.py
  ```
  - Expected: Neutral (±5%, helper calls are cheap)
- [ ] Document benchmark results in `reports/routes_performance.md`

### 3.5 Final Documentation

- [ ] Create `reports/day1_summary.md` (system health checks)
- [ ] Create `reports/day2_summary.md` (upload & WebSocket)
- [ ] Create `reports/day3_summary.md` (metrics WebSocket + testing)
- [ ] Create `reports/routes_refactoring_summary.md` with:
  - Total violations eliminated (8 → 0)
  - Complexity reduction metrics
  - Test coverage increase
  - Performance impact
  - Patterns established

### 3.6 Day 3 Checkpoint & Final Commit

- [ ] Update all task checkboxes in `tasks.md` to `[x]`
- [ ] Run final validation
  ```bash
  openspec validate refactor-api-routes-complexity --strict
  ```
- [ ] Commit Day 3 changes
  ```bash
  git add backend/api/routes/metrics_websocket.py \
           tests/backend/test_routes_metrics_helpers.py \
           reports/*.md
  git commit -m "refactor(routes): Day 3 - Metrics PERF203 fixes + comprehensive testing

  Phase 2 Complete: API Routes Refactoring
  - C901 violations: 4 → 0 (100% elimination)
  - PERF203 violations: 4 → 0 (100% elimination)
  - Tests added: +40-50 unit tests
  - All integration tests passing

  🤖 Generated with Claude Code
  Co-Authored-By: Claude <noreply@anthropic.com>"

  git push origin v2.0-refactor
  ```

---

## Post-Completion Tasks

### Archive Preparation

- [ ] Verify all tasks marked complete
- [ ] Ensure all tests passing
- [ ] Create final summary report
- [ ] Prepare for OpenSpec archiving
  ```bash
  openspec archive refactor-api-routes-complexity --yes
  ```

### Phase 3 Planning

- [ ] Document lessons learned for Phase 3 (Services subsystem)
- [ ] Identify next target subsystem
  - Option A: `src/services/rag/` (8 C901, ~15 PERF203)
  - Option B: `backend/services/` (6 C901, ~85 PERF203)
- [ ] Draft Phase 3 OpenSpec proposal when ready

---

## Progress Tracking

**Overall Progress:**
- Day 1: ⬜ System health checks (2 C901, 1 PERF203) + 15-20 tests
- Day 2: ⬜ Upload & WebSocket (2 C901) + 20-25 tests
- Day 3: ⬜ Metrics WebSocket (3 PERF203) + 10-12 tests + final testing

**Violations Eliminated:**
- C901: 0/4 complete (target: 4 → 0)
- PERF203: 0/4 complete (target: 4 → 0)

**Tests Created:**
- Day 1: 0/20 tests
- Day 2: 0/25 tests
- Day 3: 0/12 tests
- Total: 0/57 target tests

**Success Criteria:**
- [ ] All 8 violations eliminated
- [ ] 40+ new unit tests created
- [ ] All existing tests passing (100%)
- [ ] Performance neutral or improved (±5%)
- [ ] Code complexity reduced by ≥70%
