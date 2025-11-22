# Implementation Tasks

## 1. Fix union-attr errors (~500)
- [ ] 1.1 Identify all Optional type access without checks
- [ ] 1.2 Add `if value is not None:` guards
- [ ] 1.3 Fix metrics_service.py (8 violations)
- [ ] 1.4 Fix rate_limit_monitor.py (multiple violations)
- [ ] 1.5 Process remaining 28 files systematically

## 2. Fix attr-defined errors (56)
- [ ] 2.1 Fix attribute typos
- [ ] 2.2 Add missing attributes to classes
- [ ] 2.3 Improve type inference annotations

## 3. Validation
- [ ] 3.1 Run mypy to verify 0 union/attr errors
- [ ] 3.2 Run full test suite

## Estimated Effort: 15 hours
## Dependencies: Phase 4A complete
