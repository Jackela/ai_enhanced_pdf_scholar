# Lift Backend Coverage for Critical Paths

## Why
CI coverage is ~24% (<75% gate). High-risk backend routes and services (document upload, cache layer wiring, Redis warming) remain under-tested, so regressions could slip through releases and keep the gate failing.

## What Changes
- Add contract and service-layer tests for `upload_document` (duplicate/invalid PDF/error branches) and ASGI-level document route flows.
- Add cache/warming/Redis wiring tests via stubbed cache layers to exercise hit/miss accounting and background steps.
- Optionally spin up minimal FastAPI TestClient-based tests to validate route wiring and envelopes.
