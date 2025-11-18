# Expand Backend Document API Tests

## Problem
The FastAPI document routes (list, upload, download, preview) have thin or missing regression tests. As a result, the CI coverage gate (75 %) cannot be met—the current backend coverage sits near 24 % and the `download_document`/`list_documents` error branches are essentially untested. Missing assertions around pagination metadata, duplicate-upload handling, and response headers increase the risk of shipping regressions in these user-facing endpoints.

## Proposal
Add a focused suite of asynchronous pytest contract tests that exercise the document routes end-to-end with stub repositories/services. The new coverage will validate success and failure scenarios for listing, retrieving, uploading (including duplicate/malformed inputs), and downloading PDFs. Each test will assert both payload structure (envelopes, pagination, HATEOAS links) and the HTTP status codes raised on error.

## Goals
- Raise coverage of `backend/api/routes/documents.py` to capture both success paths and HTTP 400/403/404/500 branches.
- Provide reusable stub repositories/services so future document route tests can be added quickly.
- Ensure preview/download endpoints implement the documented headers and path-safety behavior.

## Non-Goals
- No changes to business logic or FastAPI routing.
- No frontend test additions.
- No database schema or API contract changes beyond coverage assertions.
