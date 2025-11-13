## Why
- Smart Cache ML optimizations now fail open when `scikit-learn` is missing, but we still lack a definitive decision on whether ML caching is an optional add-on or part of the default experience.
- Without clear guidance, environments diverge: some installs include `scikit-learn`, others do not, leading to inconsistent performance characteristics and support burden.
- Dependency management documentation currently spans multiple files and does not specify which requirements (base vs scaling) should be used for cache-related features.

## What Changes
- Evaluate the operational impact, package size, and resource requirements of including `scikit-learn` (and companions such as `pandas`, `numpy`) in the default dependency set.
- Choose between two strategies:
  1. Promote ML deps to core/production requirements and update installers/containers accordingly, **or**
  2. Keep them optional but document a supported "ML cache" profile with feature flags/tests ensuring parity.
- Update requirements files, Docker image, and documentation to reflect the chosen strategy, including guidance for enabling/disabling ML caching.
- Add automated health checks or startup diagnostics verifying that the dependency posture matches configuration (e.g., warn if ML cache enabled but deps missing).

## Impact
- Provides a single, predictable story for cache ML features, reducing surprises during deployments.
- Simplifies support instructions ("install profile X to enable ML cache" vs ad-hoc troubleshooting).
- Ensures documentation and tooling (scripts, tests) match the decided dependency tier.
