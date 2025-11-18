## ADDED Requirements
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
