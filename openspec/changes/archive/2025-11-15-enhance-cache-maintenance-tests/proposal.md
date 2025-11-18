# Enhance Cache & Path Safety Tests

## Problem
Cache maintenance scripts (preview cache cleanup, integrated cache manager) and path-safety utilities underpin the platform’s security posture, yet they have almost no automated coverage. Without tests, regressions in cache eviction, TTL enforcement, or path validation could silently introduce security issues (e.g., serving files outside allowed roots) and continue to hold the coverage gate below target.

## Proposal
Create deterministic pytest suites for the preview cache maintenance script, integrated cache manager helpers, and `backend/api/utils/path_safety`. The tests will simulate cache directories, old/new files, and malicious filenames to make sure maintenance jobs delete the correct files, emit metrics/logs, and fail safely. Path sanitization/validation helpers will be exercised with adversarial inputs to guard against traversal exploits.

## Goals
- Cover preview cache cleanup command (scheduled + on-demand flows) with temporary directories so TTL/size logic is verified.
- Exercise integrated cache manager bookkeeping (hit/miss counters, health checks) with stub collectors.
- Assert `sanitize_upload_filename`, `build_safe_temp_path`, and `is_within_allowed_roots` handle malicious inputs and non-existent files.

## Non-Goals
- No redesign of cache layers—only regression tests and small fixture helpers.
- No changes to Redis/production cache infrastructure.
