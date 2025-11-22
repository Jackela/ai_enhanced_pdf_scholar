# Change: Fix CI Type Safety - Basics

## Why
The codebase has 217 basic type safety violations that can be systematically fixed with minimal risk. These represent low-hanging fruit for improving type coverage and enabling stricter type checking.

Issues:
- **no-untyped-def (136)**: Functions missing type annotations
- **type-arg (21)**: Generic types missing parameters (tuple, dict, list)
- **unreachable (40)**: Dead code after returns/raises

## What Changes
- Add type hints to 136 functions using mypy suggestions
- Add generic type parameters: `tuple` → `tuple[int, str]`
- Remove 40 instances of unreachable dead code

## Impact
**Affected Specs:** type-safety (ADDED)
**Affected Code:** ~60 files across services, database, API layers
**Breaking Changes:** None
**Risk:** Low (type hints don't affect runtime)

## Success Criteria
- ✅ Zero no-untyped-def, type-arg, unreachable errors
- ✅ All tests pass

## Dependencies
Requires Phase 1 completion
