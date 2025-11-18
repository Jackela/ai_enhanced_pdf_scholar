## Why
- `backend/api/routes/queries.py` still triggers Ruff rule B904: several query endpoints raise `HTTPException` inside bare `except` blocks without chaining the original error.
- Unlike documents and indexes, the query capability has no spec requirement ensuring exception context is preserved, so logs lose the stack trace when multi-document or cache operations fail.
- We need to document the requirement and update the routes/tests so the error-handling story is consistent across API surfaces.

## What Changes
- Add a documents spec delta covering query endpoints: every HTTP error must be raised via `raise ... from err` (or `... from None`).
- Update `backend/api/routes/queries.py` to chain the errors for single-document queries, multi-document queries, cache clearing, and cache stats.
- Add regression tests hitting representative endpoints to prove `__cause__` is populated, and re-run lint/tests.

## Impact
- Index/document/query routes all follow the same error-handling convention, giving on-call engineers full context when queries fail.
- Ruff B904 for `queries.py` is resolved, reducing lint noise so the CI gate becomes achievable.
- No changes to API payloads—only internal exception chaining and tests.
