## Tasks
- [x] Add a documents spec delta requiring query routes to chain exceptions just like documents/indexes.
- [x] Update `backend/api/routes/queries.py` so every HTTP error uses `raise ... from e` (or `from None`).
- [x] Add focused unit tests covering query, multi-query, cache clear, and cache stats errors to ensure `__cause__` is set.
- [x] Run `python scripts/lint_staged.py --staged`, `python -m ruff check backend/api/routes/queries.py`, and `python -m pytest -q`.
- [x] `openspec validate fix-queries-error-chaining --strict` before requesting review.
