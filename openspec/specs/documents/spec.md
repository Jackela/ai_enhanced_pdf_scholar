# documents Specification

## Purpose
TBD - created by archiving change add-documents-file-type-column. Update Purpose after archive.
## Requirements
### Requirement: Documents MUST persist canonical file type metadata
All document records SHALL store a normalized `file_type` column (e.g., `.pdf`) that is populated on ingest and exposed via the API.

#### Scenario: Persist file type on ingest
- **GIVEN** a document import completes
- **WHEN** the record is stored in the `documents` table
- **THEN** the `file_type` column is set based on the uploaded file's extension or MIME type
- **AND** existing rows are backfilled during migration so no document has a NULL `file_type`

#### Scenario: Expose file type in API responses
- **GIVEN** a client calls any `/api/documents` endpoint
- **WHEN** the response envelope describes a document
- **THEN** the payload includes `file_type` so UI and analytics consumers can filter by type
- **AND** metrics collection assumes the column exists when aggregating document-type counts

### Requirement: Documents API MUST expose preview and thumbnail endpoints
Clients SHALL retrieve lightweight previews of managed documents through dedicated endpoints that enforce auth, limits, and caching.

#### Scenario: Stream specific page preview
- **GIVEN** a document exists and the caller is authorized
- **WHEN** they call `GET /api/documents/{id}/preview?page=2&width=600`
- **THEN** the API returns a `200 OK` response with `image/png` body representing page 2, constrained to the configured max width
- **AND** the response includes `Cache-Control: private` plus metadata headers (page, width, document id)
- **AND** requests for unsupported page numbers return `404` or `400` with a descriptive message

#### Scenario: Return cached thumbnail quickly
- **GIVEN** previews are enabled and the document is a supported type
- **WHEN** the client calls `GET /api/documents/{id}/thumbnail`
- **THEN** the API serves a cached first-page image (generating it on first request) within the configured TTL, respecting rate limits
- **AND** if previews are disabled globally, the endpoint responds with `503` or `404` and logs the reason
- **AND** access control errors surface as `401/403` without leaking file paths

### Requirement: Preview pipeline MUST define behaviour per file type
The system SHALL document supported/unsupported formats, conversion strategy, configuration knobs, and failure responses before implementation.

#### Scenario: DOCX/PPTX conversion documented
- **GIVEN** a DOCX or PPTX upload exists
- **WHEN** engineers read the capability spec
- **THEN** it clearly states the conversion flow (LibreOffice headless → intermediate PDF), env vars (`PREVIEW_CONVERTERS_ENABLED`, `PREVIEW_CONVERTER_TIMEOUT_SECONDS`, `PREVIEW_CONVERSION_DIR`), and HTTP behaviour (`415` when disabled, `503` when converter unavailable)

#### Scenario: Image preview documented
- **GIVEN** images (PNG/JPEG/BMP) are present in the library
- **WHEN** the spec is applied
- **THEN** it explains that Pillow resizes images directly, uses `page=1` cache keys, and surfaces limit errors (oversized image, corrupt data) with descriptive messages

#### Scenario: Unsupported formats surfaced consistently
- **GIVEN** a file with `file_type` outside the supported list
- **WHEN** `/preview` or `/thumbnail` is invoked
- **THEN** the spec mandates a `415 Unsupported Media Type` response that references the allowlist and directs operators to the conversion plan for extending support
