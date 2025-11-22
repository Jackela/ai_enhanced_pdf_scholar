# CI Parity Workflow

This document explains how to reproduce GitHub Actions locally so changes fail on your machine before they fail in CI.

## 1. Install tools
```bash
make install-dev               # python deps (ruff, mypy, pytest, etc.)
(cd frontend && npm install)   # frontend deps for Vitest
pip install pre-commit         # optional but recommended
make pre-commit-install        # installs git hooks (.git/hooks/pre-commit)
```

## 2. Recommended loop
1. Write code.
2. Run fast checks on touched files:
   ```bash
   make lint-staged              # ruff on files changed vs. origin/main
   ```
   The script `scripts/lint_staged.py` accepts `--base <ref>` if you are working off a different branch.
3. Run the backend/unit suites:
   ```bash
   PYTHONPATH=. pytest -q
   ```
4. Run frontend unit tests:
   ```bash
   cd frontend && npm run test -- --run
   ```
5. Before pushing, run the full gate:
   ```bash
   make ci-local
   ```
   This target executes:
   - `make lint-ci` (Black + Ruff + MyPy on changed files, same as GitHub Actions)
   - `pytest -q`
   - `cd frontend && npm run test -- --run`

## 3. Handling existing lint debt
- `make lint-full` still exists to gauge the legacy Ruff/Mypy backlog, but GitHub Actions enforces the changed-file gate. Use `make lint-full || true` when you want to inspect or burn down that debt.
- `make lint-ci` mirrors CI exactly. It resolves Python files changed vs. `origin/main` (or `CI_LINT_BASE=<ref>`), runs `black --check`, `ruff check`, and `scripts/mypy_changed.py` on that set, then exits non-zero if anything fails.
- When cleaning a directory, run `ruff check <dir> --fix` and add tests to ensure behaviour stays stable.
- RAG evaluation helpers have their own lint target while we burn down the backlog:
  ```bash
  python -m ruff check src/services/rag/vector_similarity.py
  ```
  Run it whenever you touch the retrieval/evaluation utilities so trailing-whitespace regressions are caught immediately.

## 4. Pre-commit hooks (optional but encouraged)
`.pre-commit-config.yaml` includes:
- `ruff-format` (auto-format touched Python files)
- `ruff` (lint touched files with the same rules as CI)
- `mypy` (available as a manual hook via `pre-commit run mypy --all-files`; disabled by default because of legacy type errors)

Enable with:
```bash
pre-commit install
```
Hooks run only on staged files, so they are much faster than full-repo linting.

## 5. CI reference
GitHub Actions (`.github/workflows/main-ci.yml`) runs the following high-level steps:
1. Ruff lint (backend)
2. MyPy
3. Backend pytest w/ coverage
4. Frontend `npm run test -- --run`

`make ci-local` mirrors the same stack so the results should match across environments.
