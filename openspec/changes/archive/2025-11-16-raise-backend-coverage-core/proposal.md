# Raise Backend Coverage for Auth, Middleware, and RAG Pipelines

## Why
- Repo-wide coverage is ~20%, far below the 75% CI gate; the last push focused on document upload/cache paths only.
- The biggest uncovered areas (auth/JWT/RBAC, middleware, RAG pipelines and caches) remain untested, so regressions there keep the gate failing and block releases.
- We need structured tests that hit these branches without real external services to lift coverage quickly and sustainably.

## What Changes
- Add targeted unit/ASGI tests for auth flows (JWT decode/expiry, RBAC denies, missing/invalid tokens) and middleware envelopes/rate limiting.
- Add fast, isolated tests for RAG and cache pipelines (rag_cache_service, vector_similarity, service factories) using in-memory stubs to avoid network/LLM calls.
- Document the coverage plan and rerun coverage so the critical backend areas move toward/beyond the 75% fail-under threshold.
