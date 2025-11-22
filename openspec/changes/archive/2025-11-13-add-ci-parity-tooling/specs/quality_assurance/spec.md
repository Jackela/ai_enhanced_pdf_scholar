## ADDED Requirements

### Requirement: CI parity plan MUST be documented
Developers MUST have a documented workflow that mirrors GitHub Actions (linting, type checking, tests) so issues are caught locally first.

#### Scenario: Developer runs CI-equivalent checks
- **GIVEN** a contributor prepares a change
- **WHEN** they follow the documented CI parity workflow
- **THEN** they run the same lint/type/test steps (or staged equivalents) locally, preventing CI surprises
- **AND** the plan includes guidance on existing lint debt and how new work remains clean
