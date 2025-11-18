## Tasks
- [x] Add spec delta under `documents` requiring exception chaining for `/api/documents` endpoints.
- [x] Update `backend/api/routes/documents.py` to use `raise ... from e` (or `... from None` when redacting) across list/get/upload flows.
- [x] Extend the documents API contract tests (or targeted unit tests) to assert that errors retain cause metadata.
- [x] Run `python scripts/lint_staged.py --staged`, `python -m pytest -q`, and document results.
- [x] `openspec validate improve-document-error-handling --strict` before requesting review.
