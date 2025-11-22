# operations Specification

## Purpose
TBD - created by archiving change add-preview-validation-playbook. Update Purpose after archive.
## Requirements
### Requirement: Provide a document preview validation playbook
Operators MUST have a documented procedure for verifying preview endpoints, toggles, and metrics after deployments.

#### Scenario: Run preview smoke test
- **GIVEN** a deployment introduces preview changes
- **WHEN** an engineer follows the playbook
- **THEN** they enable/disable previews via env vars, hit `/preview` and `/thumbnail` with curl examples, confirm headers/HTTP codes, and inspect metrics/logs per instructions
- **AND** the playbook lists troubleshooting steps (cache inspection, clearing stale files) so incidents can be resolved quickly

### Requirement: Preview cache MUST support maintenance workflows
Operators SHALL be able to inspect and purge preview cache entries via documented tooling.

#### Scenario: Scheduled cleanup
- **GIVEN** the cache directory grows beyond acceptable thresholds
- **WHEN** the maintenance command runs (manually or via cron)
- **THEN** it removes files older than TTL or beyond size quotas, logs the action, and exposes metrics so the operation can be monitored

#### Scenario: On-demand troubleshooting
- **GIVEN** previews behave oddly (stale or corrupted images)
- **WHEN** an engineer follows the maintenance guidance
- **THEN** they can list cache entries, purge a specific document’s previews, and verify metrics reflecting the cleanup

### Requirement: Cache orchestration MUST separate per-layer logic
Integrated cache manager implementations SHALL keep layer-specific caching logic (L1, L2, L3) and monitoring loops in dedicated helper functions so lint rules can enforce complexity limits and instrumentation remains composable.

#### Scenario: Cache hit/miss bookkeeping
- **GIVEN** the cache manager handles a GET request
- **WHEN** it records hits/misses
- **THEN** the statistics/metrics updates are handled by dedicated helpers rather than inline branches, keeping the top-level method small enough for automated linting.

#### Scenario: Background loops
- **GIVEN** the coherency, performance, and warming loops run indefinitely
- **WHEN** they handle cancellation/error conditions
- **THEN** the control flow lives in helper wrappers so the loop body doesn’t require nested `try`/`except`, satisfying PERF203.

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

### Requirement: Core auth and middleware flows MUST be covered
Auth token parsing, RBAC enforcement, and error/rate-limit middleware SHALL have automated tests that exercise both success and rejection paths so CI coverage moves toward the 75% gate.

#### Scenario: Auth token acceptance and rejection
- **GIVEN** JWT parsing and RBAC checks guard protected endpoints
- **WHEN** tests send valid tokens, expired/invalid tokens, and missing-role tokens via unit or ASGI clients
- **THEN** 200/401/403 responses are asserted with the documented envelope/headers, ensuring regressions are caught

#### Scenario: Middleware envelopes and rate limiting
- **GIVEN** error-handling and rate-limit middleware standardize responses
- **WHEN** tests trigger handled exceptions and rate-limit blocks
- **THEN** the response body/headers match the API contract and rate-limit headers are present, preventing silent changes

### Requirement: RAG/cache services MUST have hermetic coverage
RAG cache/store layers and similarity pipelines SHALL be tested with in-memory stubs so cache hit/miss, expiration, and vector-scoring branches are exercised without external services.

#### Scenario: RAG cache lifecycle
- **GIVEN** the RAG cache stores, expires, and invalidates entries
- **WHEN** tests run with an in-memory DB
- **THEN** hit/miss counts, TTL expiration, and invalidation paths return expected values and metrics/statistics update accordingly

#### Scenario: Vector similarity and retrieval wiring
- **GIVEN** vector similarity helpers and service factories orchestrate retrieval
- **WHEN** tests feed synthetic vectors and stubbed repositories
- **THEN** similarity scores, ordering, and error handling are asserted without hitting live LLM/vector stores

### Requirement: Auth guards MUST be covered
Auth JWT parsing, RBAC checks, and protected routes SHALL have automated tests that exercise valid, expired/invalid tokens, and missing-role cases to ensure 200/401/403 responses match the contract.

#### Scenario: Protected route accepts valid token
- **GIVEN** a protected endpoint requires a valid access token
- **WHEN** tests send a valid token via ASGI client
- **THEN** the response succeeds (2xx) and the handler executes with the expected user claims

#### Scenario: Protected route rejects bad or unauthorized tokens
- **GIVEN** the same protected endpoint
- **WHEN** tests send expired/invalid tokens or tokens missing required roles
- **THEN** 401/403 responses are returned with the standardized envelope so regressions are caught

### Requirement: Middleware and monitoring MUST expose stable envelopes/headers
Rate-limit/security middleware and monitoring hooks SHALL be covered by tests to ensure headers and structured error bodies remain stable.

#### Scenario: Rate limiting publishes headers and 429 body
- **GIVEN** rate limiting is configured
- **WHEN** tests exceed the limit via ASGI client
- **THEN** the response is 429 with Retry-After and X-RateLimit-* headers plus the documented body shape

#### Scenario: Error handling preserves envelope
- **GIVEN** error-handling middleware wraps requests
- **WHEN** a handled exception is raised
- **THEN** the JSON envelope contains correlation_id, code, and status fields as documented

### Requirement: RAG orchestration MUST be test-covered with stubs
RAG coordinator/index builder/vector manager flows SHALL be exercised with stub embeddings/repos so success/error branches gain coverage without external services.

#### Scenario: Coordinator/index builder happy path
- **GIVEN** stub repositories and embedding outputs
- **WHEN** the coordinator/index builder runs
- **THEN** it produces a successful result and updates state/metrics as expected

#### Scenario: Vector manager handles errors
- **GIVEN** the vector manager is provided bad inputs or simulated store failures
- **WHEN** operations run
- **THEN** errors are surfaced consistently and no external calls are made
