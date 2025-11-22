# Tests Overview

## Document Route Coverage Plan

The FastAPI document routes were previously missing regression tests. We now cover the following scenarios:

| Route/Utility | Covered Scenarios | Notes |
| --- | --- | --- |
| `list_documents` | pagination metadata, search vs. non-search, 400 for invalid params, 500 for repository failures | ensures envelope integrity |
| `get_document` | success envelope, 404 when missing, 500 on repository errors | uses `_StubDocRepo` |
| `get_document_preview` / `get_document_thumbnail` | success headers (`Cache-Control`, IDs), disabled previews (503), unsupported (415), not found (404), generic + unexpected preview errors | `_StubPreviewService` variants |
| `download_document` | happy path response, missing document/file path, missing file on disk, path traversal rejection | `_SingleDocRepo` |
| `upload_document` | success + temp cleanup, duplicate (409), validation/import failures (400), non-PDF rejection (415), missing file (400) | combines route-level unit tests + ASGI contracts |
| ASGI document routes | upload/download/preview responses, headers, and envelopes via `TestClient` | verifies wire-level behavior without real backends |
| Auth/JWT + middleware | JWT access/refresh/expired handling, error envelope standardization, rate-limit headers + 429 responses | see `tests/auth/test_jwt_handler.py` and `tests/backend/test_middleware_contracts.py` |
| Auth route guards | protected-route success (200), missing token (401), non-admin blocked (403) with stubbed auth service | `tests/backend/test_auth_route_guards.py` |
| Password security | bcrypt hash/verify round trip with deterministic salt | `tests/backend/test_password_security.py` |
| `path_safety` helpers | filename sanitization, temporary path building, allowed root enforcement | ensures traversal mitigations |
| Preview cache maintenance | stats, purge-expired, purge-document, purge-max-size, safe-directory enforcement | see `tests/scripts/test_preview_cache_maintenance.py` |
| Integrated cache manager | cache hit/miss bookkeeping, coherency/performance/warming step intervals | `tests/services/test_integrated_cache_manager.py` |
| Vector similarity / RAG cache | similarity calculators, threshold tuning, rerank, semantic cache hits, stats | `tests/services/test_vector_similarity_algorithms.py`, `tests/services/test_rag_cache_service_similarity.py` |
| RAG coordinator stubs | vector similarity winner & cache hit/miss flow with stubbed storage | `tests/services/test_rag_coordinator_stubs.py` |
| Rate limiting | middleware response headers/body helper and monitor metrics/alerts | `tests/backend/test_rate_limiting_headers.py`, `tests/backend/test_rate_limit_monitor.py` |

### Remaining Gaps (to prioritize next)
- Global backend coverage is ~23% (`pytest --cov` fails the repo-wide `fail-under=75` gate). Auth services/routes (login/logout/reset/verify), RBAC and password_security internals, rate_limiting/security_validation internals, and RAG coordinators/index builders/vector managers remain largely uncovered.
- Preview upload toggles (env-based enable/disable) are only covered indirectly.
- Redis/warming integration remains untested end-to-end; current coverage relies on stubbed background step helpers.

## Stub Fixtures

- `_StubDocRepo` (`tests/backend/test_documents_api_contract.py`): in-memory list implementation used to simulate repository success, 404, and error cases.
- `_FailingDocRepo`: extends `_StubDocRepo` to raise exceptions for 400/500 coverage.
- `_StubPreviewService` and variants (`_DisabledPreviewService`, `_UnsupportedPreviewService`, `_NotFoundPreviewService`, `_GenericPreviewErrorService`): used to provoke each preview exception branch without touching the real preview service.
- `_SingleDocRepo` (`tests/backend/test_documents_download_route.py`): lightweight repo for download tests.

Re-use these stubs when adding future document-route tests to keep coverage high without duplicating boilerplate.
