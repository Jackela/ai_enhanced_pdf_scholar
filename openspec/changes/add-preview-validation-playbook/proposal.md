## Why
- Preview endpoints just landed, but there’s no repeatable runbook for verifying them per environment (dev/staging/prod) with the new env vars.
- Ops/support teams need a documented procedure to smoke-test toggles (`PREVIEWS_ENABLED`, cache dirs, metrics) after deploys or when debugging user reports.
- Without an explicit validation checklist, we risk regressions (e.g., missing headers, disabled previews) going unnoticed until end users complain.

## What Changes
- Author a preview validation playbook that covers enabling/disabling previews, clearing caches, exercising both endpoints, and observing metrics/logs.
- Include CLI snippets (curl/httpie) plus expected headers/responses, and instructions for verifying Prometheus metrics + log entries.
- Link the playbook from `TESTING.md` / `README.md` so engineers know how to run it before/after releases.

## Impact
- Reduces deployment risk by giving engineers a concrete checklist.
- Speeds up incident response when previews misbehave.
- Documents the operational expectations for the new env vars/metrics so future changes can extend them confidently.
