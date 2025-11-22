## Tasks
- [x] Add an operations spec delta documenting the lint/docstring requirement for RAG evaluation helpers.
- [x] Remove trailing whitespace and fix docstrings in `src/services/rag/vector_similarity.py` (and any related helper touched by W293).
- [x] Add a simple test or lint check (e.g., `python -m ruff check src/services/rag/vector_similarity.py`) to CI or docs so regressions are caught.
- [x] Run `python scripts/lint_staged.py --staged` and `python -m pytest -q`.
- [x] `openspec validate clean-rag-vector-style --strict` before requesting review.
