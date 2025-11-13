## Tasks
1. [x] Audit the React components that render the document list/detail view to identify integration points.
2. [x] Extend the API client/types to include `preview_url`/`thumbnail_url`.
3. [x] Implement thumbnail rendering + preview modal (lazy fetch, loading/error states, cache-busting strategy if needed).
4. [x] Add Vitest/RTL coverage plus tests verifying fallback behaviour when previews are disabled.
5. [x] Update frontend docs (README preview section references) to describe usage/env toggles.
6. [x] Run `openspec validate integrate-preview-into-frontend --strict` before requesting approval.
