# Design Notes – Expand Backend Document API Tests

## Approach
- Use async pytest tests that call the route functions directly (consistent with existing `tests/backend` patterns) so we can inject stub repositories/services.
- Provide small stub classes for document repositories and preview services. Each stub will explicitly raise the target exception (e.g., duplicate upload, missing document, path traversal) to validate the FastAPI error responses.
- For download/preview coverage, rely on `tmp_path` fixtures to create temporary files and allowed roots; this keeps tests deterministic and avoids hitting real storage.
- Ensure every test asserts both the HTTP status code and relevant response metadata (pagination counts, headers, etc.) to protect API envelope contracts.
- Keep the tests fast (no external IO) so they can run on every CI invocation.

## Trade-offs / Risks
- Route-level tests are still function-level (not spinning up ASGI clients), but they give us deterministic coverage without expensive setup.
- We will need to maintain stub implementations if repository/service interfaces change; documenting them mitigates churn.
