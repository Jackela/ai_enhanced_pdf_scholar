# Design Notes: Expanded Document Preview Support

## Current State / Limitations
- Only PDF files can be previewed; all other `file_type` values return 415.
- PyMuPDF handles rendering, so we already incur a ~150MB dependency but avoid heavier LibreOffice/Imagemagick installs.
- No conversion artifacts are cached; the PNG rasters are derived directly from the uploaded PDF.

## Target Formats
| Format | Conversion strategy | Notes |
| --- | --- | --- |
| PDF | Status quo | Keep existing PyMuPDF pipeline. |
| DOCX / PPTX | LibreOffice (headless) -> intermediate PDF -> PyMuPDF | Requires optional dependency set + sandboxed temp dir. |
| Images (PNG/JPEG/BMP) | Pillow resize directly | Bypass PyMuPDF; treat as single-page preview. |
| Future: HTML/Markdown | Pandoc -> PDF | Optionally handled in later phases. |

## Conversion Pipeline
1. **Office files**
   - Use `soffice --headless --convert-to pdf --outdir <tmp>`.
   - Place intermediate PDF under `PREVIEW_CONVERSION_DIR/<doc_id>/<hash>.pdf` with TTL, reuse for subsequent renders.
   - Clean up on TTL expiry or when cache exceeds quota.
2. **Images**
   - Use Pillow (`Image.open` + `.thumbnail`) to generate direct PNG outputs.
   - Reuse existing raster cache naming scheme with `page=1` to keep API consistent.

## Resource Controls
- Hard timeout (configurable, default 20 seconds) for any external conversion process.
- Memory constraints enforced via cgroup/ulimit when running LibreOffice.
- Maximum intermediate file size (e.g., 200MB) to prevent runaway conversions.
- Converted artifacts stored separately from PNG cache to simplify cleanup.

## Security Considerations
- Run conversions inside a dedicated temp directory with sanitized filenames.
- Denylist macros/external links via LibreOffice flags (`--nologo --norestore --invisible`).
- Ensure we never stream unconverted user content; only generated PNGs are returned.

## Configuration / Flags
- `PREVIEW_CONVERTERS_ENABLED=true|false`
- `PREVIEW_CONVERTER_TIMEOUT_SECONDS`
- `PREVIEW_CONVERSION_DIR`
- Format allowlist (e.g., `PREVIEW_SUPPORTED_FORMATS=".pdf,.docx,.pptx,.png,.jpg"`).
- Feature can be partially enabled (e.g., images without Office conversions) via JSON config.

## Observability
- Metrics: `preview_conversion_requests_total{format,result}`, `preview_conversion_duration_seconds{format}`.
- Logs: structured entries when conversions start/finish/fail.
- Health check entry to surface converter availability (e.g., LibreOffice binary missing).

## Rollout Plan
1. Phase 1: Image previews (minimal dependencies) behind flag.
2. Phase 2: Office conversions in staging environment to gather perf data.
3. Phase 3: Enable in production with dashboards/alerts for cache growth + conversion failures.

## Cleanup Strategy
- Conversion artifacts share TTL with PNG cache (default 1h) but also respond to disk-quota based eviction.
- Provide CLI/management command to purge conversions (shared with general preview cache maintenance work).
