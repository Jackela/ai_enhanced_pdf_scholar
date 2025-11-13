## Tasks
1. **Context review**
   - [x] Audit `backend/api/routes/documents.py`, document storage paths, and existing security middleware to understand auth + streaming patterns.
2. **Preview service contract**
   - [x] Design interfaces for `DocumentPreviewService` (inputs: document ID, page, size) and caching policy; capture decisions in `design.md`.
3. **Backend implementation**
   - [x] Add preview generation (PyMuPDF/Pillow) with size and page limits, cached rasters, and graceful fallbacks for unsupported types.
   - [x] Expose new routes `/api/documents/{id}/preview` (accepts `page`, `resolution`) and `/api/documents/{id}/thumbnail` (cached first page) with proper headers.
   - [x] Wire metrics/logging plus configuration flags (enable/disable previews, max pages per request).
4. **Validation & tests**
   - [x] Add unit tests for the preview service, contract tests for the routes (200 path, 404, 415, auth) and update existing API docs/examples.
5. **Documentation & specs**
   - [x] Update `API_ENDPOINTS.md`, `PROJECT_DOCS.md`, and relevant frontend notes to describe preview usage.
   - [x] Finalize spec deltas and rerun `openspec validate add-document-preview-endpoints --strict`.
