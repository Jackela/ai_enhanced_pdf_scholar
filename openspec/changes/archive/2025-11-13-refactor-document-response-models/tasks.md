## Tasks
- [x] Update the documents spec to mandate reuse of shared error/response envelopes.
- [x] Remove duplicate `ErrorResponse` (and any related) classes, keeping a single canonical model.
- [x] Adjust imports/usages across the documents API to reference the canonical model.
- [x] Add/refresh tests covering the multi-document error payload shape.
- [x] Run `python scripts/lint_staged.py --staged`, `python -m pytest -q`, and capture results.
- [x] `openspec validate refactor-document-response-models --strict` before code review.
