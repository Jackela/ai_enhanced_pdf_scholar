## Why
- Users currently must download an entire PDF to confirm they selected the right file; the API lacks light-weight preview/thumbnail endpoints.
- Frontend pagination tests reference the new envelope but there is no way to fetch quick previews, forcing the UI to render placeholders.
- We already persist canonical `file_type`; enabling previews requires consistent server-side sanitization and consistent API contracts before implementation begins.

## What Changes
- Add read-only preview endpoints under `/api/documents/{id}/preview` (paginated page images) and `/api/documents/{id}/thumbnail` (cached first-page image) that stream sanitized binary responses.
- Wire previews through a dedicated service that reuses the managed document path, enforces size/page limits, and caches rendered rasters on disk/Redis for repeated access.
- Extend Documents capability specs to cover preview guarantees (authn, range of supported file types, response headers) and note that unsupported types must return 415/400 with guidance.
- Update API docs and client envelope to describe preview URLs, including signed link generation toggle for future CDN support.
- Provide observability hooks (metrics, logs) and tests (unit + contract) to ensure previews respect ACLs and fail gracefully when a file is missing.

## Impact
- UX: library view can render real previews/thumbnails without downloading PDFs, reducing latency and bandwidth.
- Security: codifying size limits + auth ensures previews don't leak data and degrade service.
- Architecture: establishes a reusable PreviewService compatible with future CDN or cache tiers.
