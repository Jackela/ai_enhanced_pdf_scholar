# Implementation Tasks

## 1. Setup
- [ ] 1.1 Run `mypy src backend --ignore-missing-imports > mypy-report.txt`
- [ ] 1.2 Group errors by category and file

## 2. Fix no-untyped-def (136 errors)
- [ ] 2.1 Services layer (40 files) - Add function type hints
- [ ] 2.2 Database layer (20 files) - Add method type hints
- [ ] 2.3 API layer (15 files) - Add endpoint type hints
- [ ] 2.4 Use IDE auto-fix where possible

## 3. Fix type-arg (21 errors)
- [ ] 3.1 Add tuple type parameters: `tuple[int, str]`
- [ ] 3.2 Add dict type parameters: `dict[str, Any]`
- [ ] 3.3 Add list type parameters: `list[str]`

## 4. Fix unreachable (40 errors)
- [ ] 4.1 Remove dead code after returns
- [ ] 4.2 Remove dead code after raises

## 5. Validation
- [ ] 5.1 Run mypy to verify 0 basic errors
- [ ] 5.2 Run full test suite

## Estimated Effort: 20 hours
## Dependencies: Phase 1 complete
