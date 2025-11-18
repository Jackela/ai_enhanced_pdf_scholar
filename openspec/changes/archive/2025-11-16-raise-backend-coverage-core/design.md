# Design Notes – Raise Backend Coverage Core

## Scope & Focus
- Auth/JWT/RBAC: exercise token parsing, expiry, missing/invalid claims, and role enforcement. Use lightweight ASGI tests with dependency overrides; avoid real signing secrets by stubbing JWT decode.
- Middleware: cover error-handling envelopes, rate-limiting responses, and security headers where feasible without external Redis. Prefer unit-level tests of handlers plus minimal ASGI wiring for status/body shape.
- RAG/cache pipelines: target `rag_cache_service`, `vector_similarity`, and service factory wiring. Use in-memory SQLite/stubbed similarity calculators to avoid LLM/Redis.

## Approach
- Keep tests hermetic and fast: temp dirs, in-memory DBs, stubbed dependency injections, no network/LLM.
- Prioritize branches with high line counts in coverage report; defer negligible/self-evident code.
- Maintain `fail-under` as-is; purpose is to raise actual coverage toward the gate, not to relax it.
