## ADDED Requirements

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
