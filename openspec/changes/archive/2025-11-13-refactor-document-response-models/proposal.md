## Why
- Ruff reports F811 because `backend/api/models/multi_document_models.py` defines two separate `ErrorResponse` classes, causing confusion in downstream type hints and tests.
- Duplicate response models make it unclear which shape the `/api/documents` multi-document endpoints should return.
- We need a spec clarification plus code cleanup so responses remain consistent and lint passes.

## What Changes
- Add a documents spec requirement that shared response envelopes (like `ErrorResponse`) must be defined once and reused across multi-document APIs.
- Consolidate the duplicate model definitions, update imports/usages, and ensure serialization matches the existing API contract.
- Expand unit tests (or Pydantic schema snapshots) to cover the canonical error payload and avoid future regressions.

## Impact
- Eliminates Ruff F811 noise and clarifies the API schema for clients.
- Keeps response payloads consistent across document operations, reducing the risk of subtle bugs.
- Purely server-side/twIR change; no DB migration.
