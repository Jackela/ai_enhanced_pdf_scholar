# CI Parity Tooling Design

## 1. Current State & Pain Points
- `ruff check src backend --statistics` currently reports **622 violations**. Top categories:
  - `PERF203` try/except inside loops: 138 occurrences
  - `S608` string-formatted SQL: 51
  - `W293` blank line whitespace: 51
  - `C901` overly complex functions: 49
  - `PERF401`, `SIM102`, `SIM105`, etc.
- `PYTHONPATH=. mypy src backend` produces thousands of errors (3.5k+). The majority are `no-untyped-def`, `no-untyped-call`, and `arg-type` complaints in `src/services/rag/*` and `src/database/models.py`.
- Because legacy violations exist, `make lint` (Ruff + MyPy) fails locally and developers cannot replicate GA before pushing. GA currently tolerates failures by relying on limited rule sets per job, but the experience is inconsistent.

## 2. Proposed Strategy
### 2.1 Two-phase cleanup
1. **Baseline tracking**: keep Ruff/Mypy runs available via `make lint-full` so engineers can reference the exact debt and work on cleanup incrementally.
2. **Protect new code**: add staged/diff linting (`make lint-staged`) plus optional `pre-commit` hooks so touched files are checked even though the baseline is dirty.

### 2.2 Tooling alignment
- Provide `scripts/lint_staged.py` that figures out changed Python files vs. a base ref (default `origin/main`) and runs Ruff on them.
- Ship `.pre-commit-config.yaml` with Ruff format + check hooks so contributors can opt-in.
- Add `Makefile` targets:
  - `lint-full` (formerly `lint`) to run Ruff + MyPy across the repo.
  - `lint-staged` to run the staged script.
  - `ci-local` to execute the full backend lint/tests plus frontend Vitest to mimic GA.
  - `pre-commit-install` helper.
- Document the workflow in `docs/CI_PARITY.md` and reference it from README/SETUP.

### 2.3 Future cleanup plan
- Treat Ruff categories in batches (e.g., SIM/W29x first) and track progress in issues.
- As directories are cleaned, drop them from ignore lists and enforce `ruff check` CI gating gradually.

## 3. Implementation Plan
1. Add the staged lint script + `.pre-commit-config.yaml`.
2. Update Makefile targets and README/CI docs.
3. Encourage contributors to run `make ci-local` before pushing; GA will eventually call the same make target.
4. Keep design doc updated with latest inventory counts whenever we revisit the plan.
