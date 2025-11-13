# Design: Document Preview Endpoints

## Goals
- Serve lightweight previews/thumbnails for PDFs without forcing a full download.
- Keep implementation incremental: reuse managed document paths, rely on PyMuPDF (already in requirements) for rasterization.
- Respect auth/filters already enforced by the documents router.

## Key Decisions
1. **Service Layer**: Introduce `DocumentPreviewService` under `src/services/` that:
   - Validates document ownership/access through `DocumentRepository`.
   - Generates images via PyMuPDF -> Pillow, producing PNG/JPEG bytes.
   - Caches rendered pages on disk (e.g., `.ai_pdf_scholar/previews/<doc>/<page>-<width>.png`) and optionally Redis when available.
2. **API Shape**:
   - `GET /api/documents/{id}/preview?page=1&width=600` → returns `image/png` stream of requested page; default width 600px capped by config.
   - `GET /api/documents/{id}/thumbnail` → returns cached first page at 256px width.
   - Both endpoints require existing auth dependencies, reuse rate limiting, and emit `Cache-Control: private, max-age=<ttl>`.
3. **Configuration**:
   - Extend `FileStorageConfig` or new `PreviewConfig` for enable/disable flag, max page per request, max resolution, cache TTL, disk location.
   - Env vars: `PREVIEWS_ENABLED`, `PREVIEW_MAX_WIDTH`, `PREVIEW_CACHE_DIR`, `PREVIEW_CACHE_TTL`.
4. **Observability & Limits**:
   - Metrics for preview hits/misses, generation time, failure reasons.
   - Enforce a hard maximum number of preview pages per request (e.g., 5) and return 400 if page exceeds document page count.
   - If file type is unsupported (non-PDF), return 415 with guidance.
5. **Security Considerations**:
   - Preview endpoints must honor existing ownership/role checks (reuse repository lookups + ACL logic).
   - Generated files stored under app-managed path with sanitized filenames derived from doc ID + page.
   - Avoid path traversal by not accepting raw file paths; rely on DB-managed path only.

## Open Questions / Assumptions
- Initial implementation targets PDFs only; fallback message encourages conversion for other types.
- Frontend will call these endpoints with current auth token; no signed URLs in the first iteration.
- CDN integration is out-of-scope but future-friendly via `Cache-Control` and consistent URL structure.
