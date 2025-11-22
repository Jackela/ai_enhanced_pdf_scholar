# Design Notes – Expand Backend Coverage (Auth/RAG/Middleware)

## Scope
- Auth: JWT parsing/verification, RBAC guards, auth route behaviors (401/403).
- Middleware: rate_limit_monitor hooks, security headers, error envelope consistency under handled exceptions.
- RAG: coordinator/index builder/vector manager minimal flows using stub embeddings/repos—no external LLM/vector store.

## Approach
- Use dependency overrides and symmetric JWT stubs to avoid key generation and keep tests fast.
- Prefer ASGI `TestClient` for route/guard assertions; unit tests for pure helpers.
- Stub metrics/monitoring and repositories to avoid Redis/network; use temp dirs and in-memory data structures.
- Keep fail-under unchanged; goal is to raise actual coverage, not relax thresholds.
