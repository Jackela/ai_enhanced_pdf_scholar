# Preview Multi-Format Plan

## Baseline
- Current preview pipeline only renders PDFs using PyMuPDF.
- `/api/documents/{id}/preview` returns `415 Unsupported Media Type` for other formats.
- Key env vars today: `PREVIEWS_ENABLED`, `PREVIEW_CACHE_DIR`, `PREVIEW_MAX_WIDTH`, `PREVIEW_MIN_WIDTH`, `PREVIEW_THUMBNAIL_WIDTH`, `PREVIEW_MAX_PAGE_NUMBER`, `PREVIEW_CACHE_TTL_SECONDS`.

## Target Formats & Strategy
| Format | Strategy | Optional Dependencies |
| --- | --- | --- |
| PDF | Keep PyMuPDF rendering | Already present |
| DOCX / PPTX | Convert to PDF via LibreOffice headless, then reuse PyMuPDF | `libreoffice`, `unoconv` |
| PNG / JPEG / BMP | Resize with Pillow directly | Pillow (existing) |

## Conversion Flow (DOCX/PPTX)
1. Detect `.docx/.pptx` from `DocumentModel.file_type`.
2. Run `soffice --headless --convert-to pdf` inside `PREVIEW_CONVERSION_DIR/<doc_id>` with sanitized filenames.
3. Enforce timeout (default 20s) and maximum artifact size (e.g., 200MB); log failures.
4. Pass generated PDF into existing renderer; cache PNG output as usual.

## Configuration Additions
- `PREVIEW_CONVERTERS_ENABLED=true|false`
- `PREVIEW_CONVERTER_TIMEOUT_SECONDS=20`
- `PREVIEW_CONVERSION_DIR=$HOME/.ai_pdf_scholar/preview_converted`
- `PREVIEW_SUPPORTED_FORMATS=.pdf,.docx,.pptx,.png,.jpg`

## Metrics & Logging
- `preview_conversion_requests_total{format,result}`
- `preview_conversion_duration_seconds{format}`
- Structured log entries for conversion start/finish/fail (doc id, duration, format).

## Operational Notes
- Conversion artifacts share TTL with PNG cache and respect disk quotas (see cache maintenance change).
- Health endpoint should expose converter availability (e.g., missing binaries → degraded).
- When conversions fail, API responds with `415` (unsupported) or `503` (converter unavailable) with actionable messages.
