## Why
- Preview cache files accumulate indefinitely on disk; without a cleanup strategy, long-running deployments risk filling the disk or serving very stale images.
- Operators currently have no tooling to inspect cache size, purge entries, or rotate TTLs outside of deleting the entire directory.
- A scheduled maintenance routine (CLI command or background job) is needed to keep cache usage predictable.

## What Changes
- Track preview cache metadata (size, age) and expose a management command/API to purge entries older than TTL or exceeding disk quotas.
- Optionally integrate with existing maintenance scripts or cron to run cleanup periodically.
- Document operational guidance for monitoring cache size and responding to warnings.

## Impact
- Prevents unbounded disk growth from cached previews.
- Gives SRE/ops teams confidence that enabling previews won’t jeopardize disk space.
- Provides observability hooks to alert when cache usage crosses thresholds.
