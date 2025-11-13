## Why
- The backend now exposes `preview_url`/`thumbnail_url`, but the React library view still renders placeholders; users don't see real thumbnails or page previews.
- Pagination/unit tests only verify the envelope, so regressions in the client-side hook/components would go unnoticed.
- Adding previews to the UI provides the tangible UX improvement the backend change was meant to unlock.

## What Changes
- Update the React data layer (query hooks/state) to consume the new fields, fetch thumbnails lazily, and display fallback skeletons when disabled.
- Add a modal/lightbox for page previews that hits `/preview?page=...` with the currently selected page.
- Cover the feature with Vitest/RTL tests (ensuring the component renders the `<img>` with the right `src`, handles loading/error states) and Storybook or docs snippets.
- Surface feature flags/env vars so the frontend can hide preview controls when `PREVIEWS_ENABLED=false`.

## Impact
- Immediate UX win (real thumbnails) with minimal backend load thanks to cached endpoints.
- Better test coverage around the new API shape.
- Clear toggle story for environments lacking preview support.
