## ADDED Requirements

### Requirement: Query endpoints MUST preserve exception context
All `/api/queries` routes SHALL re-raise HTTP errors using `raise ... from <original>` (or `from None` when redacting) so operational logs retain the root cause.

#### Scenario: Single-document query failure
- **GIVEN** `/api/queries/{document_id}` encounters a backend error
- **WHEN** it raises `HTTPException(status_code=500, detail="Query execution failed")`
- **THEN** the exception is chained to the underlying error, satisfying Ruff B904.

#### Scenario: Multi-document and cache endpoints
- **GIVEN** multi-document queries or cache maintenance routes hit errors
- **WHEN** they respond with HTTP errors
- **THEN** the response is raised from the underlying exception so observability remains intact.
