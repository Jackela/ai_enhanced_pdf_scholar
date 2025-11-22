# documents Specification Delta – expand-backend-doc-tests

## ADDED Requirements
### Requirement: Document API endpoints MUST have regression coverage
Document list, retrieval, preview, upload, and download endpoints SHALL provide automated tests that cover success responses as well as all documented HTTP error cases.

#### Scenario: List documents pagination contract
- **GIVEN** `list_documents` is invoked in both search and non-search modes
- **WHEN** the test suite executes
- **THEN** it asserts pagination metadata (page, per_page, total, total_pages, has_next/has_prev) and verifies 400/500 errors propagate when repository calls fail

#### Scenario: Preview and download path safety
- **GIVEN** preview/thumbnail and download endpoints process user-provided document paths
- **WHEN** tests run
- **THEN** they confirm headers (cache-control, IDs) on success and ensure 403/404 responses are raised for missing files or disallowed paths

#### Scenario: Upload/duplicate handling
- **GIVEN** the upload route enforces deduplication and validation
- **WHEN** the test suite stubs duplicate/malformed submissions
- **THEN** HTTP 409/400 responses are asserted so regressions cannot silently ship
