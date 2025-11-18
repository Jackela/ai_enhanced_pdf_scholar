## ADDED Requirements
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
