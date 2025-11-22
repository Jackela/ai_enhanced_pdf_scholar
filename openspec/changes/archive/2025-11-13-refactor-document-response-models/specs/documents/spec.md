## ADDED Requirements

### Requirement: Documents API MUST reuse canonical error response models
Documents endpoints SHALL define shared response envelopes (e.g., `ErrorResponse`) once and import them wherever needed to avoid divergent schemas.

#### Scenario: Multi-document errors reuse canonical model
- **GIVEN** a failure occurs in `/api/documents/multi`
- **WHEN** the endpoint returns an error payload
- **THEN** it uses the same `ErrorResponse` structure defined for other document endpoints (status, code, detail, optional metadata)
- **AND** no duplicate Pydantic classes exist with the same name.

#### Scenario: Schema validation
- **GIVEN** automated tests introspect the Pydantic schema
- **WHEN** they serialize the error response model
- **THEN** only one schema entry named `ErrorResponse` is present, ensuring clients see a consistent contract.
