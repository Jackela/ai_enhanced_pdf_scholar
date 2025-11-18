## Why
- Running `ruff check src backend` locally fails because the repo has hundreds of legacy violations, so developers can’t reproduce the CI pipeline before pushing.
- CI workflows expect Ruff/MyPy/Black to pass, but without a cleanup strategy or staged linting, pushes might fail only after hitting GitHub Actions.
- We need a comprehensive plan to align local developer workflow with remote CI.

## What Changes
- Categorize existing Ruff violations (complexity, security, style) and define a cleanup plan (per-directory or per-rule) so baseline lint debt is tracked and reduced.
- Introduce a staged lint approach (e.g., pre-commit, `make lint-staged`) that runs Ruff/MyPy on touched files to prevent new violations even before the full cleanup finishes.
- Update Makefile/README/SETUP docs to define the mandatory local commands mirroring GA.
- Adjust CI to use the same scripts, ensuring parity between local and remote environments.

## Impact
- Developers get clear guidance on running CI-equivalent checks locally, reducing failed pushes.
- Establishes a roadmap to eliminate legacy lint debt gradually.
- Improves overall code quality and confidence in the automated pipeline.
