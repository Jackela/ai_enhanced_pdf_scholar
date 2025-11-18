## Why
- Ruff still flags B904 in `backend/api/routes/indexes.py` because several endpoints raise `HTTPException` inside bare `except` clauses without chaining the root cause.
- These routes power vector index management; when verification/cleanup/storage-stat failures occur we currently lose stack context, making on-call debugging harder.
- The documents routes now meet the requirement, so the indexes capability needs the same spec coverage and code cleanup to stay consistent.

## What Changes
- Add a documents/index spec delta clarifying that vector index endpoints must preserve exception causes (`raise ... from e` or `... from None`).
- Update `backend/api/routes/indexes.py` to chain every HTTP error in the affected flows.
- Add targeted unit tests hitting representative endpoints to prove the cause is retained, and confirm Ruff no longer flags this module.

## Impact
- Faster debugging for index synchronization issues thanks to richer logs.
- Further reduction of the Ruff backlog, getting us closer to running full lint in CI.
- No API contract changes beyond better internal instrumentation.
