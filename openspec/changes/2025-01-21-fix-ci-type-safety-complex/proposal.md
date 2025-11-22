# Change: Fix CI Type Safety - Complex Issues

## Why
The codebase has ~929 complex type errors requiring specialized fixes. These include Prometheus metric indexing, ORM type handling, and migration conflicts.

Issues:
- **index (36)**: Prometheus metric indexing, object type inference
- **assignment (47)**: Column type assignments, datetime mismatches
- **Migration conflicts (8 files)**: BaseMigration duplicate definitions
- **Remaining (~300)**: Service-specific complex type issues

## What Changes
- Fix Prometheus metric type annotations
- Fix SQLAlchemy Column type assignments
- Resolve migration file import conflicts
- Address remaining service-specific type issues

## Impact
**Affected Specs:** type-safety (MODIFIED), database-types (ADDED)
**Affected Code:** ~81 files across all layers
**Breaking Changes:** None
**Risk:** Medium (complex type fixes)

## Success Criteria
- ✅ Zero mypy errors (1,646 → 0)
- ✅ All tests pass
- ✅ Strict type checking enabled

## Dependencies
Requires Phase 4B completion
