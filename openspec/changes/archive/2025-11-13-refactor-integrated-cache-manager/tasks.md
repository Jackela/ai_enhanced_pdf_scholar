## Tasks
1. Add an operations spec delta documenting that cache orchestration code must keep per-layer logic separated (facilitating instrumentation and lint compliance).
2. Refactor `backend/services/integrated_cache_manager.py`:
   - Extract helpers for L1/L2/L3 hits, miss bookkeeping, and background loops so `get/set/delete` drop below C901 and loops don’t combine `try`/`except` with `while` bodies.
3. Update unit tests (or add new targeted tests) for cache hits/misses and the background task runner (e.g., ensure helpers called as expected via mocks).
4. Run `python scripts/lint_staged.py --staged`, `python -m ruff check backend/services/integrated_cache_manager.py`, and `python -m pytest -q`.
5. `openspec validate refactor-integrated-cache-manager --strict` before requesting review.
