## ADDED Requirements

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
