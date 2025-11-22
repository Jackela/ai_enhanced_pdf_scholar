# Fortify Service Resilience Tests

## Problem
Critical service modules (EnhancedRAGService, DocumentLibraryService, cache managers, retry/circuit breaker helpers) handle retries, resource cleanup, and corruption repair but lack regression tests. The recent security review showed Bandit warnings tied to these paths, and coverage on `src/services` remains extremely low. Without tests, we risk regressions in recovery flows, cache maintenance, and document ingestion that would only surface in production incidents.

## Proposal
Introduce targeted pytest suites that instantiate the service classes with stub repositories/cache components. The tests will intentionally trigger retry/circuit-breaker boundaries, corruption repair decisions, cache inspection methods, and document library operations to ensure exceptions and metrics behave as designed. We'll validate both success (happy paths) and failure/recovery branches, giving the resilience layer measurable coverage.

## Goals
- Cover the retry/jitter/circuit-breaker logic in `src/services/error_recovery.py` plus the integration points used by EnhancedRAGService.
- Exercise cache maintenance helpers (IntegratedCacheManager, preview cache scripts) to verify metrics, logging, and cleanup.
- Assert DocumentLibraryService import flows handle duplicates, hash mismatches, and cleanup of temporary files.

## Non-Goals
- No refactors of service implementations beyond what is needed to make them testable.
- No changes to repository implementations or API routes.
