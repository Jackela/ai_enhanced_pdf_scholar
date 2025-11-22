# Design: API Routes Complexity Refactoring

**Change ID:** `refactor-api-routes-complexity`
**Created:** 2025-01-20
**Phase:** 2 of 3-phase complexity reduction initiative

---

## Architectural Context

### System Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │   system.py  │  │ documents.py  │  │  async_rag.py   │  │
│  │              │  │               │  │                 │  │
│  │ • Health     │  │ • Upload      │  │ • WebSocket RAG │  │
│  │ • Metrics    │  │ • Download    │  │ • Streaming     │  │
│  │ • Status     │  │ • List        │  │                 │  │
│  └──────────────┘  └───────────────┘  └─────────────────┘  │
│         │                  │                    │           │
└─────────┼──────────────────┼────────────────────┼───────────┘
          │                  │                    │
          ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│  • DocumentLibraryService  • EnhancedRAGService             │
│  • ContentHashService      • CacheManager                    │
└─────────────────────────────────────────────────────────────┘
```

**THIS CHANGE AFFECTS:** API Layer (Routes) only
**DOES NOT AFFECT:** Service Layer, Database, Frontend

---

## Problem Analysis

### Current Complexity Hotspots

#### 1. system.py::detailed_health_check (C901: 16)

**Root Cause:** Multiple health checks mixed in single function
- System resources (memory, disk, CPU)
- Database connectivity
- RAG service status
- Cache status
- Version information
- Status aggregation logic

**Complexity Breakdown:**
```python
# 16 decision points across:
if memory.percent < 80: ...elif memory.percent < 90: ...  # +3
if disk.free > total * 0.2: ...elif disk.free > total * 0.1: ...  # +3
if cpu_percent < 70: ...elif cpu_percent < 90: ...  # +3
if db_status == "connected": ...  # +2
if rag_status == "ready": ...  # +2
if cache_status == "healthy": ...  # +2
if any(component == "critical"): ...elif any(component == "warning"): ...  # +1
```

#### 2. system.py::performance_health_check (C901: 13)

**Root Cause:** Performance metrics collection + threshold evaluation
- Cache hit rates calculation
- Query performance monitoring
- Service latency checks
- Threshold comparisons for each metric

#### 3. documents.py::upload_document (C901: 13)

**Root Cause:** Multi-stage validation + error handling
- File type validation
- File size validation
- Duplicate detection (with 3 strategies)
- Overwrite logic
- File persistence
- Database record creation

#### 4. async_rag.py::websocket_rag_endpoint (C901: 11)

**Root Cause:** WebSocket message handling + streaming control
- Connection management
- Message parsing
- Query validation
- Stream orchestration
- Error recovery

#### 5. PERF203 Violations (4 instances)

**Location:** metrics_websocket.py + system.py
**Root Cause:** Exception handling inside message processing loops

```python
# Anti-pattern
for message in stream:
    try:
        process(message)  # PERF203 violation
    except Exception as e:
        handle_error(e)
```

---

## Design Approach

### Strategy: Helper Extraction Pattern

Apply the **same proven pattern** from auth refactoring:

```
┌──────────────────────────────────────────────────────────┐
│ BEFORE: Monolithic Endpoint (C901: 13-16)               │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  async def endpoint(...):                                │
│      """100+ lines of mixed concerns"""                  │
│      # Validation (20 lines)                             │
│      # Business logic (30 lines)                         │
│      # Database ops (20 lines)                           │
│      # Response formatting (15 lines)                    │
│      # Error handling (15 lines)                         │
│      return response                                     │
│                                                          │
└──────────────────────────────────────────────────────────┘

                         ↓ REFACTOR

┌──────────────────────────────────────────────────────────┐
│ AFTER: Orchestrator + Helpers (C901: 2-3)               │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  async def endpoint(...):                                │
│      """10-15 lines orchestrating helpers"""             │
│      await _validate_inputs(...)  # C901: 2              │
│      result = await _execute_business_logic(...)  # C901: 3│
│      record = await _persist_data(...)  # C901: 1        │
│      return _format_response(result, record)  # C901: 1  │
│                                                          │
│  + 4-6 private helper methods (each C901 ≤3)            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Pattern Application by Endpoint

#### 1. detailed_health_check Refactoring

```python
# BEFORE (C901: 16, 150+ lines)
async def detailed_health_check(db, rag_service):
    health_data = {}
    # 50 lines of system resource checks
    # 30 lines of database checks
    # 30 lines of RAG service checks
    # 20 lines of cache checks
    # 20 lines of status aggregation
    return BaseResponse(success=True, data=health_data)

# AFTER (C901: 2, 12 lines)
async def detailed_health_check(db, rag_service):
    """Comprehensive health check with component isolation."""
    system_health = _check_system_resources()
    db_health = await _check_database_status(db)
    rag_health = await _check_rag_status(rag_service)
    cache_health = _check_cache_status()

    overall_status = _aggregate_health_status([
        system_health, db_health, rag_health, cache_health
    ])

    return BaseResponse(success=True, data={
        "components": {
            "system": system_health,
            "database": db_health,
            "rag": rag_health,
            "cache": cache_health,
        },
        "overall_status": overall_status,
    })

# Helper Functions (each C901 ≤3)
def _check_system_resources() -> dict:
    """Check memory, disk, CPU with threshold evaluation."""
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu = psutil.cpu_percent(interval=1)

    return {
        "memory": _evaluate_memory_status(memory),
        "disk": _evaluate_disk_status(disk),
        "cpu": _evaluate_cpu_status(cpu),
    }

def _evaluate_memory_status(memory) -> dict:
    """Evaluate memory status against thresholds. (C901: 2)"""
    status = "critical" if memory.percent >= 90 else \
             "warning" if memory.percent >= 80 else "healthy"

    return {
        "total_bytes": memory.total,
        "available_bytes": memory.available,
        "used_percent": memory.percent,
        "status": status,
    }

# Similar helpers for disk, CPU, database, RAG, cache, aggregation
```

**Benefits:**
- Each helper tests one thing (memory OR disk OR CPU)
- Threshold logic isolated (easy to tune)
- Orchestrator is self-documenting
- Unit testable with simple mocks

#### 2. upload_document Refactoring

```python
# BEFORE (C901: 13, 120+ lines)
async def upload_document(file, title, check_duplicates, overwrite_duplicates, ...):
    # 25 lines of file validation
    # 40 lines of duplicate detection
    # 30 lines of file persistence
    # 25 lines of database record creation
    return DocumentResponse(...)

# AFTER (C901: 3, 15 lines)
async def upload_document(file, title, check_duplicates, overwrite_duplicates, ...):
    """Upload document with validation and duplicate handling."""
    # Step 1: Validate file
    _validate_file_upload(file)

    # Step 2: Handle duplicates
    existing_doc = await _handle_duplicate_detection(
        file, check_duplicates, overwrite_duplicates, library_service
    )
    if existing_doc and not overwrite_duplicates:
        return DocumentResponse(data=existing_doc, message="Duplicate found")

    # Step 3: Save file and create record
    file_path = await _save_document_file(file, documents_dir)
    document = await _create_document_record(
        file_path, title or file.filename, library_service
    )

    return DocumentResponse(data=document, message="Upload successful")

# Helper Functions
def _validate_file_upload(file: UploadFile) -> None:
    """Validate file type and size. (C901: 2)"""
    if not file.content_type == "application/pdf":
        raise HTTPException(415, "Only PDF files supported")

    # Size check in actual implementation
    # Raises HTTPException(413) if too large

async def _handle_duplicate_detection(...) -> Document | None:
    """Check for duplicates using configured strategy. (C901: 3)"""
    if not check_duplicates:
        return None

    # Content hash duplicate check
    content_hash = await calculate_hash(file)
    existing = await library_service.find_by_content_hash(content_hash)

    return existing
```

**Benefits:**
- Validation isolated (easy to add new checks)
- Duplicate logic testable independently
- Clear separation of concerns
- Easy to add new duplicate strategies

#### 3. WebSocket PERF203 Refactoring

```python
# BEFORE (PERF203 violation)
async def websocket_rag_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        try:
            message = await websocket.receive_json()
            result = await process_message(message)  # PERF203
            await websocket.send_json(result)
        except WebSocketDisconnect:
            break
        except Exception as e:
            await websocket.send_json({"error": str(e)})

# AFTER (no PERF203)
async def websocket_rag_endpoint(websocket: WebSocket):
    await websocket.accept()

    async for message in websocket.iter_json():
        # Process message (no exception in loop)
        result = await _process_message_safe(message)

        # Send response (error already in result object)
        await websocket.send_json(result.to_dict())

async def _process_message_safe(message: dict) -> MessageResult:
    """Process message and return result object (no exceptions). (C901: 2)"""
    try:
        validated = _validate_message_format(message)
        response = await rag_service.query(validated.query)
        return MessageResult.success(response)
    except ValidationError as e:
        return MessageResult.error("validation_failed", str(e))
    except RAGError as e:
        return MessageResult.error("rag_failed", str(e))
```

**Benefits:**
- No exception overhead in hot loop
- Error handling centralized
- Result object pattern (testable)
- Clearer control flow

---

## Testing Strategy

### Unit Test Approach

**For each helper function:**
```python
# Example: test_check_system_resources.py

def test_memory_healthy_status():
    """Test memory status when under 80% usage."""
    mock_memory = MagicMock(total=16GB, available=8GB, percent=50)

    with patch('psutil.virtual_memory', return_value=mock_memory):
        result = _check_system_resources()

    assert result["memory"]["status"] == "healthy"
    assert result["memory"]["used_percent"] == 50

def test_memory_warning_status():
    """Test memory status between 80-90% usage."""
    mock_memory = MagicMock(percent=85)

    with patch('psutil.virtual_memory', return_value=mock_memory):
        result = _check_system_resources()

    assert result["memory"]["status"] == "warning"

def test_memory_critical_status():
    """Test memory status above 90% usage."""
    mock_memory = MagicMock(percent=95)

    with patch('psutil.virtual_memory', return_value=mock_memory):
        result = _check_system_resources()

    assert result["memory"]["status"] == "critical"
```

**Test Coverage Goals:**
- 3-5 tests per helper function
- Cover all status thresholds
- Mock external dependencies (psutil, database, services)
- Verify error handling

### Integration Test Preservation

```python
# Existing integration tests MUST continue passing
@pytest.mark.integration
def test_detailed_health_check_integration():
    """Test full health check endpoint (behavior preservation)."""
    response = client.get("/api/system/health/detailed")

    assert response.status_code == 200
    assert "components" in response.json()["data"]
    assert "overall_status" in response.json()["data"]
```

---

## Migration Strategy

### Incremental Approach (3 Days)

**Day 1: System Health Checks**
1. Extract helpers from `detailed_health_check`
2. Extract helpers from `performance_health_check`
3. Create 15-20 unit tests
4. Fix 1 PERF203 in `system.py:349`
5. Verify all existing tests pass

**Day 2: Upload and WebSocket**
1. Extract helpers from `upload_document`
2. Refactor `websocket_rag_endpoint`
3. Create 12-15 unit tests
4. Verify upload integration tests pass

**Day 3: Metrics WebSocket + Final Testing**
1. Fix 3 PERF203 in `metrics_websocket.py`
2. Create 10-12 unit tests
3. Run full test suite
4. Performance regression testing
5. Final validation

### Rollback Plan

If issues arise:
1. Each file is independent (can revert individually)
2. Git commits are atomic (one file per commit)
3. Integration tests catch regressions immediately
4. No database migrations (pure code refactoring)

---

## Performance Considerations

### Expected Performance Impact

**PERF203 Elimination:**
- **Before:** Exception setup/teardown on every loop iteration
- **After:** Result object pattern (zero exception overhead)
- **Impact:** 10-30% faster WebSocket message processing

**Helper Extraction:**
- **Impact:** Neutral (function call overhead negligible)
- **Trade-off:** Slightly more stack frames for better testability

### Benchmarking Plan

```python
# Benchmark WebSocket throughput before/after
python scripts/benchmark_websocket.py
# Expected: ≥10% improvement in messages/second

# Benchmark health check latency before/after
python scripts/benchmark_health_checks.py
# Expected: ±5% (neutral, helper calls are cheap)
```

---

## Security Considerations

**No Security Impact:**
- Refactoring preserves all validation logic
- No changes to authentication/authorization
- File upload limits unchanged
- Error messages unchanged

**Code Review Focus:**
- Verify all validation checks still execute
- Confirm error responses identical
- Ensure no new exception swallowing

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Behavioral regression | Low | High | Comprehensive integration tests + manual testing |
| Performance degradation | Very Low | Medium | Benchmark before/after, validate ≤5% variance |
| Test maintenance burden | Low | Low | Clear test structure, good naming conventions |
| Merge conflicts | Low | Low | Small scope (4 files), coordinate with team |

---

## Decision Log

### Why Helper Extraction vs Strategy Pattern?

**Strategy Pattern** (used for password validators):
- ✅ Good for: Multiple validation algorithms, pluggable behavior
- ❌ Bad for: Endpoints (no need for pluggability)

**Helper Extraction** (used for auth DI):
- ✅ Good for: Decomposing complex orchestration, single-responsibility
- ✅ Better fit: Endpoints are orchestrators, not strategy consumers

**Decision:** Use Helper Extraction for all endpoint refactoring

### Why Not Extract to Service Layer?

**Option:** Move complexity to new service classes
**Rejected because:**
- Services already exist (DocumentLibraryService, RAGService)
- Endpoints should orchestrate services, not replicate them
- Helper extraction keeps logic in presentation layer where it belongs

**Decision:** Keep helpers as private methods in route modules

### Why 3 Days Timeline?

**Data from auth refactoring:**
- Day 1: Password validation (C901: 13 → 0) - 4 hours
- Day 2: DI helpers (C901: 15 → 1) + migration (PERF203: 2 → 0) - 6 hours

**This refactoring:**
- Similar complexity (C901: 11-16 vs 13-15)
- More violations (8 vs 4) → longer timeline
- Proven patterns → faster execution

**Decision:** 3 days provides buffer for WebSocket complexity

---

## References

**Precedent Work:**
- `archive/2025-11-20-refactor-auth-complexity-p3/design.md` - Auth refactoring design
- `archive/2025-11-20-refactor-auth-complexity-p3/reports/day1_summary.md` - Password validation pattern
- `archive/2025-11-20-refactor-auth-complexity-p3/reports/day2_summary.md` - DI helpers + PERF203 pattern

**Code Locations:**
- `backend/api/routes/system.py:450` - detailed_health_check (C901: 16)
- `backend/api/routes/system.py:793` - performance_health_check (C901: 13)
- `backend/api/routes/documents.py:454` - upload_document (C901: 13)
- `backend/api/routes/async_rag.py:300` - websocket_rag_endpoint (C901: 11)
- `backend/api/routes/metrics_websocket.py:84,131,180` - PERF203 violations (3×)
- `backend/api/routes/system.py:349` - PERF203 violation (1×)
