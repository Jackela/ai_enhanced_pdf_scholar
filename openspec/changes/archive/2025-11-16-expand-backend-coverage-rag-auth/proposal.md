# Expand Backend Coverage for Auth/RAG/Middleware Gaps

## Why
- Coverage is still ~22% vs the 75% gate; large, high-risk modules (auth routes/RBAC/services, rate-limit monitoring, RAG coordinators/index builders) remain untested.
- Existing coverage focuses on documents/cache; auth and RAG regressions could still slip through and keep CI red.
- We need fast, hermetic tests that raise coverage in these hotspots without external services.

## What Changes
- Add JWT/RBAC/auth route tests (unit + minimal ASGI) to cover valid/expired/invalid tokens, missing roles, and route-level guards.
- Cover middleware/monitoring (rate_limit_monitor, security headers) to assert structured envelopes/headers and metrics hooks.
- Add RAG pipeline coverage (coordinator/index builders/vector manager) with stubbed repos/embeddings to exercise success/error paths and bump coverage.
- Update test docs and rerun lint/tests/coverage to demonstrate lift toward the 75% gate.
