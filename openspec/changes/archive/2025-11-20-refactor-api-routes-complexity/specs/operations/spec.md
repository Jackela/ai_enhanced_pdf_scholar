# Operations Spec Deltas: API Routes Complexity Refactoring (Phase 2)

**Change ID:** `refactor-api-routes-complexity`
**Spec:** `openspec/specs/operations/spec.md`
**Type:** MODIFIED Requirements
**Last Updated:** 2025-01-20
**Phase:** 2 of 3 (Auth → **Routes** → Services)

---

## MODIFIED Requirements

### Requirement: API endpoints MUST use helper extraction for orchestration

API route handlers SHALL decompose multi-concern logic into focused helper methods to maintain cyclomatic complexity ≤10 (C901) and enable granular unit testing of validation, business logic, and response formatting.

**Rationale:** Complex route handlers (C901 >10) mix validation, business logic, database operations, and error handling, making them difficult to test, debug, and modify safely. Helper extraction creates single-responsibility functions that are independently testable.

**Applies to:**
- Health check endpoints (`backend/api/routes/system.py`)
- Document upload endpoint (`backend/api/routes/documents.py`)
- WebSocket endpoints (`backend/api/routes/async_rag.py`)
- All route handlers with C901 >10

---

#### Scenario: Health check endpoint decomposition

**GIVEN** a comprehensive health check endpoint with cyclomatic complexity >10 due to multiple component checks (system resources, database, RAG service, cache) each with threshold-based status evaluation

**WHEN** developers refactor using helper extraction pattern

**THEN:**
- System resource checks move to `_check_system_resources()` helper (complexity ≤3)
- Database connectivity moves to `_check_database_status(db)` helper (complexity ≤2)
- RAG service health moves to `_check_rag_status(service)` helper (complexity ≤2)
- Cache health moves to `_check_cache_status()` helper (complexity ≤2)
- Status aggregation moves to `_aggregate_health_status(components)` helper (complexity ≤3)
- Main endpoint becomes 10-15 line orchestrator calling helpers in sequence

**AND:**
- Each helper is independently unit-testable with mocked dependencies
- Main endpoint complexity reduces from 16 to ≤3
- Integration tests verify end-to-end health check flow unchanged
- `ruff check --select C901` shows violation eliminated

**Example Implementation:**
```python
# Before (C901: 16, 150+ lines)
async def detailed_health_check(db, rag_service):
    health_data = {}

    # 50 lines checking system resources (memory, disk, CPU)
    memory = psutil.virtual_memory()
    health_data["memory"] = {
        "status": "critical" if memory.percent >= 90 else
                  "warning" if memory.percent >= 80 else "healthy",
        # ... nested conditionals
    }
    # ... disk, CPU checks with similar nesting

    # 30 lines checking database
    try:
        db.execute("SELECT 1")
        health_data["database"] = {"status": "healthy"}
    except:
        health_data["database"] = {"status": "critical"}

    # ... similar blocks for RAG, cache
    return BaseResponse(success=True, data=health_data)

# After (C901: 2, 12 lines)
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
```

---

#### Scenario: Upload endpoint validation extraction

**GIVEN** a document upload endpoint with complexity >10 due to multi-stage validation (file type, size, duplicates), file persistence, and database record creation

**WHEN** developers extract each concern into dedicated helpers

**THEN:**
- File validation logic moves to `_validate_file_upload(file)` helper (complexity ≤2)
- Duplicate detection moves to `_handle_duplicate_detection(...)` helper (complexity ≤3)
- File saving moves to `_save_document_file(file, dir)` helper (complexity ≤1)
- Record creation moves to `_create_document_record(...)` helper (complexity ≤2)
- Main endpoint orchestrates helpers with clear error propagation

**AND:**
- Each helper raises HTTPException with appropriate status codes
- Unit tests mock file operations for isolated validation testing
- Integration tests verify end-to-end upload flow with real files
- Endpoint complexity reduces from 13 to ≤3

**Example Implementation:**
```python
# Before (C901: 13, 120+ lines)
async def upload_document(file, title, check_duplicates, ...):
    # 25 lines of file validation
    if not file.content_type == "application/pdf":
        raise HTTPException(415, ...)
    if file.size > MAX_SIZE:
        raise HTTPException(413, ...)

    # 40 lines of duplicate detection
    if check_duplicates:
        content_hash = calculate_hash(file)
        existing = library_service.find_by_hash(content_hash)
        if existing and not overwrite_duplicates:
            # ... complex overwrite logic
        # ... handle different duplicate scenarios

    # 30 lines of file persistence
    file_path = documents_dir / file.filename
    # ... save file, handle errors

    # 25 lines of database record creation
    document = library_service.create_document(...)
    return DocumentResponse(data=document)

# After (C901: 3, 15 lines)
async def upload_document(file, title, check_duplicates, overwrite_duplicates, ...):
    """Upload document with validation and duplicate handling."""
    _validate_file_upload(file)

    existing_doc = await _handle_duplicate_detection(
        file, check_duplicates, overwrite_duplicates, library_service
    )
    if existing_doc and not overwrite_duplicates:
        return DocumentResponse(data=existing_doc, message="Duplicate found")

    file_path = await _save_document_file(file, documents_dir)
    document = await _create_document_record(
        file_path, title or file.filename, library_service
    )

    return DocumentResponse(data=document, message="Upload successful")
```

---

#### Scenario: WebSocket endpoint message processing

**GIVEN** a WebSocket RAG endpoint with complexity >10 due to connection management, message parsing, query validation, stream orchestration, and error recovery

**WHEN** developers extract message processing into helpers

**THEN:**
- Message validation moves to `_validate_websocket_message(msg)` helper (complexity ≤2)
- Query processing moves to `_process_rag_query(query)` helper (complexity ≤3)
- Stream handling moves to `_stream_rag_results(results)` helper (complexity ≤2)
- Main endpoint manages WebSocket lifecycle only (accept, receive, send loop)

**AND:**
- Helpers return result objects instead of raising exceptions
- Unit tests mock WebSocket and service dependencies
- Integration tests use WebSocket test client
- Endpoint complexity reduces from 11 to ≤4

**Example Implementation:**
```python
# Before (C901: 11, 100+ lines)
async def websocket_rag_endpoint(websocket, rag_service):
    await websocket.accept()

    while True:
        try:
            message = await websocket.receive_json()

            # 30 lines of message validation
            if "query" not in message:
                await websocket.send_json({"error": "Missing query"})
                continue
            if len(message["query"]) > MAX_QUERY_LENGTH:
                # ... error handling

            # 40 lines of RAG query processing
            query = message["query"]
            result = await rag_service.query(query)
            # ... handle different result types

            # 20 lines of streaming results
            for chunk in result.stream():
                await websocket.send_json(chunk)
                # ... handle stream errors

        except WebSocketDisconnect:
            break
        except Exception as e:
            await websocket.send_json({"error": str(e)})

# After (C901: 4, 18 lines)
async def websocket_rag_endpoint(websocket, rag_service):
    """WebSocket endpoint for streaming RAG queries."""
    await websocket.accept()

    try:
        async for message in websocket.iter_json():
            result = await _process_message_safe(message, rag_service)
            await websocket.send_json(result.to_dict())
    except WebSocketDisconnect:
        logger.info("Client disconnected")

async def _process_message_safe(message: dict, rag_service) -> MessageResult:
    """Process WebSocket message and return result object. (C901: 2)"""
    try:
        validated = _validate_websocket_message(message)
        response = await rag_service.query(validated.query)
        return MessageResult.success(response)
    except ValidationError as e:
        return MessageResult.error("validation_failed", str(e))
    except RAGError as e:
        return MessageResult.error("rag_failed", str(e))
```

---

## MODIFIED Requirements

### Requirement: WebSocket message loops MUST NOT use try-except

WebSocket and streaming endpoints SHALL validate messages and collect errors outside loop bodies to eliminate try-except-in-loop anti-patterns (PERF203) while preserving error reporting for individual messages.

**Rationale:** Exception handling inside WebSocket message loops creates performance overhead (repeated setup/teardown) and makes code harder to reason about. Result object pattern improves performance and clarity without sacrificing error handling.

**Applies to:**
- WebSocket RAG endpoint (`backend/api/routes/async_rag.py`)
- Metrics WebSocket endpoint (`backend/api/routes/metrics_websocket.py`)
- Any streaming/long-polling endpoints

---

#### Scenario: WebSocket message loop refactoring

**GIVEN** a WebSocket endpoint that processes messages in a loop, with try-except blocks inside the loop to handle per-message errors (PERF203 violation)

**WHEN** developers refactor using result object pattern

**THEN:**
- Message processing function returns `Result[T, Error]` instead of raising exceptions
- Loop iterates over messages, calling processing function and collecting results
- Errors are handled by sending error result to client (no exception raised)
- No exception handling occurs inside the hot path (loop body)

**AND:**
- Message processing behavior unchanged (same messages succeed/fail)
- Error messages remain user-friendly and detailed
- Performance improves for high-throughput WebSocket streams
- `ruff check --select PERF203` passes

**Example Implementation:**
```python
# Before (PERF203 violation)
async def metrics_websocket(websocket: WebSocket):
    await websocket.accept()

    for metric_type in ["cpu", "memory", "disk", "network"]:
        try:
            data = await collect_metrics(metric_type)  # PERF203
            await websocket.send_json({"type": metric_type, "data": data})
        except MetricsError as e:
            await websocket.send_json({"type": metric_type, "error": str(e)})

# After (no PERF203)
async def metrics_websocket(websocket: WebSocket):
    await websocket.accept()

    # Collect all metrics (no exceptions)
    results = [
        await _collect_metric_safe(metric_type)
        for metric_type in ["cpu", "memory", "disk", "network"]
    ]

    # Send results (errors already in result objects)
    for result in results:
        await websocket.send_json(result.to_dict())

async def _collect_metric_safe(metric_type: str) -> MetricResult:
    """Collect metric and return result object (no exceptions)."""
    try:
        data = await collect_metrics(metric_type)
        return MetricResult.success(metric_type, data)
    except MetricsError as e:
        return MetricResult.error(metric_type, str(e))
```

---

#### Scenario: Batch metrics collection with error reporting

**GIVEN** a metrics WebSocket that streams multiple metric types in a loop, with try-except for each metric collection

**WHEN** developers refactor to collect all metrics then filter errors

**THEN:**
- Metric collection functions return `MetricResult` objects
- Loop iterates over metric types, calling collection functions
- After loop completes, successful results and errors are separated
- Both successful metrics and error reports sent to client

**AND:**
- Behavior unchanged (same metrics collected, same errors reported)
- Performance improves (no exception overhead in loop)
- Monitoring logs include success/error counts
- `ruff check --select PERF203` passes

**Example Implementation:**
```python
# Before (PERF203 violation)
async def stream_all_metrics(websocket: WebSocket):
    await websocket.accept()

    while True:
        metrics = []
        errors = []

        for metric_type in ALL_METRIC_TYPES:
            try:
                data = await collect_metric(metric_type)  # PERF203
                metrics.append({"type": metric_type, "data": data})
            except Exception as e:
                errors.append({"type": metric_type, "error": str(e)})

        await websocket.send_json({"metrics": metrics, "errors": errors})
        await asyncio.sleep(5)

# After (no PERF203)
async def stream_all_metrics(websocket: WebSocket):
    await websocket.accept()

    while True:
        # Collect all metrics (no exceptions in loop)
        results = [
            await _collect_metric_safe(metric_type)
            for metric_type in ALL_METRIC_TYPES
        ]

        # Separate successes and errors after collection
        metrics = [r.to_dict() for r in results if r.is_success]
        errors = [r.to_dict() for r in results if r.is_error]

        await websocket.send_json({"metrics": metrics, "errors": errors})
        await asyncio.sleep(5)
```

---

## Verification

### Automated Checks

All requirements in this spec delta SHALL be verified by:

1. **Lint Enforcement:**
   ```bash
   # No C901 violations in API routes
   ruff check backend/api/routes/ --select C901
   # Expected: 0 errors (down from 4)

   # No PERF203 violations in API routes
   ruff check backend/api/routes/ --select PERF203
   # Expected: 0 errors (down from 4)
   ```

2. **Test Coverage:**
   ```bash
   # Route test suite must pass with comprehensive helper coverage
   pytest tests/backend/test_routes* --cov=backend/api/routes --cov-report=term-missing
   # Expected: 100% pass rate, coverage ≥90%
   ```

3. **Integration Testing:**
   ```bash
   # Full API integration tests (behavior preservation)
   pytest tests/integration/test_api_endpoints.py -v
   # Expected: All existing tests pass unchanged
   ```

### Manual Checks

- [ ] Code review confirms each helper has single responsibility
- [ ] Code review confirms orchestrator endpoints are self-documenting
- [ ] Manual testing verifies health check responses unchanged
- [ ] Manual testing verifies upload error messages preserved
- [ ] WebSocket test client validates streaming behavior unchanged

---

## Related Requirements

**Cross-References:**
- `archive/2025-11-20-refactor-auth-complexity-p3/specs/operations/spec.md` - "Auth validation MUST use composable helpers"
  - Similar helper extraction pattern applied to auth dependency injection
  - Validates orchestrator approach

- `openspec/specs/operations/spec.md:28` - "Cache orchestration MUST separate per-layer logic"
  - Single-responsibility helper pattern alignment
  - Complexity reduction precedent

**Precedent Changes:**
- `archive/2025-11-20-refactor-auth-complexity-p3` - Auth subsystem refactoring (C901: 13,15 → 0,1)
- `archive/2025-11-13-refactor-integrated-cache-manager` - Cache complexity reduction

---

## Notes

- This spec delta is Phase 2 of 3-phase complexity reduction initiative (Auth → **Routes** → Services)
- Patterns established here (helper extraction, result objects) will extend to services in Phase 3
- All refactoring preserves behavior (no functional changes, only structural improvements)
- Performance improvements from PERF203 fixes are measured but not primary goals (code clarity is)
- Helper methods remain private to route modules (not extracted to service layer)
