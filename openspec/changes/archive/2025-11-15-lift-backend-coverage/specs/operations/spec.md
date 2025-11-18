# operations Specification Delta – lift-backend-coverage

## ADDED Requirements
### Requirement: Critical backend flows MUST reach the coverage gate
Document upload routes/services, cache initialization/warming, and ASGI document endpoints SHALL have automated tests that cover both success and documented error branches so coverage moves toward the 75% CI gate.

#### Scenario: Upload route error matrix
- **GIVEN** the upload endpoint handles duplicates, invalid PDFs, and missing files
- **WHEN** tests run
- **THEN** they assert 200/409/400/404 responses and cleanup of temporary files using stubs/fixtures

#### Scenario: Cache warming and hit/miss bookkeeping
- **GIVEN** IntegratedCacheManager runs background steps and records hit/miss/response-time metrics
- **WHEN** tests simulate cache operations and warming/performance/coherency steps
- **THEN** counters/metrics are updated and background helpers complete without external Redis/CDN

#### Scenario: ASGI contract for document routes
- **GIVEN** document routes (upload/download/preview) expose envelopes and headers
- **WHEN** ASGI-level tests exercise these endpoints
- **THEN** responses match the documented schema and error codes, protecting against wiring regressions
