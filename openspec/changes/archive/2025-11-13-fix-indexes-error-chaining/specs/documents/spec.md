## ADDED Requirements

### Requirement: Index management endpoints MUST chain errors
Vector index API routes SHALL re-raise HTTP errors with `raise ... from <original>` (or `... from None` when redacting) so operational logs retain the root cause.

#### Scenario: Verification failure preserves cause
- **GIVEN** the `/api/indexes/{id}/verify` endpoint catches an unexpected error
- **WHEN** it raises `HTTPException(status_code=500, detail="Index verification failed")`
- **THEN** the original exception is chained via `from err` so the traceback keeps the actual failure.

#### Scenario: Cleanup/storage stats errors chain root cause
- **GIVEN** cleanup or storage stats routes encounter backend errors
- **WHEN** they respond with HTTP errors
- **THEN** the response is raised from the underlying exception (or explicitly from `None` when hiding sensitive data)
- **AND** Ruff rule B904 passes for `backend/api/routes/indexes.py`.
