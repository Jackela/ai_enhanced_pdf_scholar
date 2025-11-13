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
