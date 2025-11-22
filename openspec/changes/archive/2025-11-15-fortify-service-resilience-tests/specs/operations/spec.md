# operations Specification Delta – fortify-service-resilience-tests

## ADDED Requirements
### Requirement: Resilience services MUST have regression tests
Recovery, caching, and document import services SHALL include automated tests that exercise retry/circuit-breaker logic, corruption repair, and cache maintenance workflows.

#### Scenario: Recovery orchestration coverage
- **GIVEN** EnhancedRAGService invokes retry/circuit-breaker helpers for index repair
- **WHEN** the test suite runs
- **THEN** it triggers success/failure branches (partial vs. full rebuild) and asserts metrics/logs are emitted as documented

#### Scenario: Document import duplicate handling
- **GIVEN** DocumentLibraryService ingests files and deduplicates by hash
- **WHEN** tests simulate duplicates and invalid PDFs
- **THEN** HTTP/errors and cleanup of temporary files are asserted, preventing regressions in ingestion resilience

#### Scenario: Cache maintenance instrumentation
- **GIVEN** cache/preview maintenance scripts expose metrics and cleanup routines
- **WHEN** tests invoke scheduled/on-demand cleanup paths
- **THEN** they confirm the correct files are purged and metrics/return codes reflect the action so operational runbooks remain accurate
