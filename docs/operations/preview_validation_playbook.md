# Document Preview Validation Playbook

This playbook verifies that preview/thumbnail endpoints work correctly in any environment (dev/staging/prod). Run it after deployments, when toggling environment variables, or while triaging preview incidents.

## 1. Prerequisites
- API server reachable (default `http://localhost:8000`).
- Auth token or session cookie for a user who can access the target document.
- At least one document with `file_type=.pdf` present (get the ID via `/api/documents`).

## 2. Relevant Environment Variables
| Variable | Default | Description |
| --- | --- | --- |
| `PREVIEWS_ENABLED` | `true` | Master flag for preview endpoints. Set `false` to disable quickly. |
| `PREVIEW_CACHE_DIR` | `~/.ai_pdf_scholar/previews` | Location of cached PNG rasters. |
| `PREVIEW_MAX_WIDTH` | `1024` | Maximum width for rendered previews. Requests above this value are clamped. |
| `PREVIEW_MIN_WIDTH` | `200` | Minimum width accepted. |
| `PREVIEW_THUMBNAIL_WIDTH` | `256` | Width used for `/thumbnail`. |
| `PREVIEW_MAX_PAGE_NUMBER` | `500` | Hard limit for requested page numbers. |
| `PREVIEW_CACHE_TTL_SECONDS` | `3600` | Time before cached files expire. |

Set env vars and restart the API server when toggling values. Example:
```bash
export PREVIEWS_ENABLED=true
export PREVIEW_CACHE_DIR="$HOME/.ai_pdf_scholar/previews"
export PREVIEW_MAX_WIDTH=800
```

## 3. Smoke Test Steps
1. **Baseline health**
   ```bash
   curl -s http://localhost:8000/api/system/health | jq '.components.preview'
   ```
   Confirm the component is `healthy` when enabled.

2. **Thumbnail request**
   ```bash
   curl -i \
     -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/documents/123/thumbnail -o thumb.png
   ```
   Verify:
   - `200 OK`
   - Headers include `X-Document-Id`, `X-Preview-Page: 1`, `X-Preview-Cache: miss|hit`.
   - Body saves to `thumb.png` (PNG format).

3. **Preview request (custom page/width)**
   ```bash
   curl -i \
     -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/api/documents/123/preview?page=2&width=600" \
     -o page2.png
   ```
   - Expect `200 OK` and headers like above.
   - Repeat; the second call should show `X-Preview-Cache: hit`.

4. **Disabled mode**
   - Set `PREVIEWS_ENABLED=false`, restart API.
   - Requests should return `503 Service Unavailable` with message `Document previews are disabled`.

## 4. Metrics & Logs
- Prometheus metrics (scrape `/metrics` or use console):
  - `preview_requests_total{type="preview",result="success"}` should increment for previews.
  - `preview_generation_seconds{type="preview"}` records render duration.
- Logs:
  - INFO entries from `backend.api.routes.documents` show preview requests.
  - WARN/ERROR entries flag rendering issues or unsupported file types.

## 5. Cache Inspection & Troubleshooting
- List cached files:
  ```bash
  ls -lh "$PREVIEW_CACHE_DIR/123"
  ```
- Remove a specific document’s cache:
  ```bash
  rm -f "$PREVIEW_CACHE_DIR/123"/*
  ```
- Common issues:
  | Symptom | Likely Cause | Action |
  | --- | --- | --- | --- |
  | `415 Unsupported Media Type` | Non-PDF file | Convert to PDF or implement extended format support. |
  | `404 Not Found` | Page > document length | Check `page_count` from `/api/documents/{id}`. |
  | `503` with previews enabled | Cache dir permissions or env typo | Verify `PREVIEW_CACHE_DIR` exists and is writable. |

## 6. Reporting
Document results (pass/fail, document ID used, env vars) in your deployment notes or incident ticket.
