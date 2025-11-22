## Why
- Ruff still flags multiple C901/PERF203 violations in `backend/services/integrated_cache_manager.py` (get/set/delete and the background monitoring loops), making `make lint-staged` fail.
- These methods have grown monolithic as features accumulated (multi-layer cache, coherency monitor, cache warming), so we need to split them into smaller helpers without regressing behaviour.
- Refactoring is large enough to justify a formal OpenSpec change so reviewers understand how the cache manager is evolving.

## What Changes
- Introduce helper methods for cache hits, miss bookkeeping, and layer-specific operations so `get/set/delete` drop below the C901 threshold.
- Extract reusable async utilities for the background monitoring loops (coherency/performance/warming) to avoid `try`/`except` inside `while` loops and make PERF203 pass.
- Add targeted unit tests (or structured integration tests) to ensure the new helpers still honour L1/L2/L3 semantics, and run lint/tests.

## Impact
- Enables `make lint-staged` to succeed by removing the remaining blockers from the cache manager.
- Improves readability of the cache orchestrator, making future changes (e.g., real ML cache enablement) easier to reason about.
- Behaviour stays the same; we’re only moving logic into smaller functions with clearer names.
