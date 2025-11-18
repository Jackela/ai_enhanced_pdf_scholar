# Design Notes – Lift Backend Coverage

## Focus Areas
- Document upload route/service: duplicate detection, invalid PDF, missing file, managed temp cleanup/happy path.
- Cache/warming/Redis wiring: exercise IntegratedCacheManager background steps and hit/miss accounting with stub caches/metrics—no real Redis.
- ASGI contract checks: minimal TestClient/httpx tests to validate envelopes/headers for upload/download/preview.

## Approach
- Reuse existing stubs (document repos, preview services, cache metrics) and extend them for upload/Redis init paths.
- Keep tests hermetic: tmp dirs for uploads/cache, monkeypatch config/env to avoid real dependencies.
- Prefer thin ASGI tests for route wiring; keep heavier integration optional.
