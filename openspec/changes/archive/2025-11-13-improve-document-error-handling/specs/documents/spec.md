## ADDED Requirements

### Requirement: Documents API errors MUST preserve exception context
All `/api/documents` handlers SHALL re-raise HTTP errors with `raise ... from <original>` (or an equivalent structured trace) so logs capture the root cause while still returning the correct status code.

#### Scenario: Upload failure surfaces original cause
- **GIVEN** the document upload route catches a validation or storage error
- **WHEN** it raises `HTTPException(status_code=400/409/500, ...)`
- **THEN** the exception is chained to the original error (`raise HTTPException(...) from err`)
- **AND** log entries include the source stack for debugging without leaking sensitive payloads.

#### Scenario: List/get errors chain causes
- **GIVEN** `/api/documents` list or detail endpoints encounter invalid pagination parameters or missing records
- **WHEN** they respond with HTTP errors
- **THEN** the response is raised from the underlying exception unless explicitly redacted (using `from None`)
- **AND** automated linting (Ruff B904) passes for those modules.
