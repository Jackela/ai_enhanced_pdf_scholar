# Design Notes – Fortify Service Resilience Tests

## Approach
- Compose service instances with lightweight stubs (in-memory repositories, fake cache/stat collectors) so retry/circuit-breaker code can execute deterministically.
- Use pytest parametrization to cover multiple recovery decisions (force rebuild vs. partial repair, cache hits vs. misses) without duplicating boilerplate.
- Validate metrics by exposing stub collectors that record label/value pairs; assertions confirm the services emit the expected telemetry.
- Avoid hitting real filesystem or network resources—temporary directories and monkeypatched stubs keep runs fast and hermetic.

## Considerations
- Some services depend on optional libraries (llama-index, Redis). Tests will run in `test_mode` or guard imports to avoid heavy dependencies.
- We may need helper factories (e.g., `make_enhanced_rag_service`) within the tests directory to centralize stub wiring; documenting these fixtures helps future contributors.
