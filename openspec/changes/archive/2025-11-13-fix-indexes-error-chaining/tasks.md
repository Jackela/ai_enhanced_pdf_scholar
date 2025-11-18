## Tasks
- [x] Add a documents spec delta requiring index routes to chain exceptions just like the document routes.
- [x] Update `backend/api/routes/indexes.py` to use `raise ... from e` (or `from None` when redacting) for all B904 locations.
- [x] Add targeted unit tests to prove the cause is preserved for representative endpoints (e.g., verification/cleanup/storage stats).
- [x] Run `python scripts/lint_staged.py --staged`, `python -m ruff check backend/api/routes/indexes.py`, and `python -m pytest -q`.
- [x] `openspec validate fix-indexes-error-chaining --strict` before requesting review.
