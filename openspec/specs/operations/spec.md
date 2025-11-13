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
