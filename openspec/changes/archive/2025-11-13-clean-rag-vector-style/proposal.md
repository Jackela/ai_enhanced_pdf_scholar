## Why
- Ruff reports dozens of `W293` violations in `src/services/rag/vector_similarity.py` because docstrings contain trailing whitespace-only lines.
- These helpers power offline evaluation/diagnostics; sloppy formatting makes the generated docs harder to read and keeps lint from passing.
- We need an explicit requirement that RAG evaluation helpers meet our style guidelines plus code cleanup to restore lint hygiene.

## What Changes
- Extend the operations spec with a requirement that RAG evaluation utilities must ship lint-clean docstrings so runbooks and auto-generated docs stay readable.
- Remove trailing whitespace and tighten docstrings/comments in `vector_similarity.py` (and any sibling files that still fail W293) without changing runtime logic.
- Add a lightweight regression test (or docstring linter invocation) to ensure the helpers stay compliant.

## Impact
- Unblocks parts of the Ruff backlog and keeps evaluation docs polished for ops/ML teams.
- No behavioural changes—purely documentation/style adjustments within the RAG service layer.
