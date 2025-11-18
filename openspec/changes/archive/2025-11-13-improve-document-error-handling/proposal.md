## Why
- Ruff rule B904 is firing in `backend/api/routes/documents.py` because we raise `HTTPException` inside `except` blocks without chaining the original error.
- Without structured chaining we lose stack context, and logs become less actionable when debugging ingest failures or pagination errors.
- The Documents spec currently covers preview/metadata but is silent about error causality, so we need a spec delta plus code changes to enforce the pattern.

## What Changes
- Add a documents capability requirement that `/api/documents` endpoints must preserve exception context (either re-raise or attach `from e`).
- Update the document routes to use `raise ... from e` (or `raise ... from None` when hiding sensitive errors) and expand tests to assert that tracebacks include the cause.
- Document the new behaviour in unit tests and ensure Ruff B904 no longer fires for this module.

## Impact
- Clearer logs and observability for document ingestion/listing bugs.
- Reduced lint noise so developers can chip away at the broader Ruff backlog incrementally.
- No API contract changes beyond improved error messaging; status codes remain the same.
