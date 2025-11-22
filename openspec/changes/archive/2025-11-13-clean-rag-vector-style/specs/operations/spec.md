## ADDED Requirements

### Requirement: RAG evaluation helpers MUST keep docstrings lint-clean
Utilities under `src/services/rag/**` that document evaluation/diagnostics SHALL avoid trailing whitespace-only lines so that Ruff linting and generated docs remain readable for operators.

#### Scenario: Vector similarity helper docstring
- **GIVEN** `vector_similarity.py` describes metrics such as precision, MRR, and NDCG
- **WHEN** Ruff runs with rule `W293`
- **THEN** the module passes without errors because blank lines do not contain stray spaces.

#### Scenario: Regression coverage
- **GIVEN** a developer edits the RAG evaluation helpers
- **WHEN** they run the staged lint script or the targeted Ruff command referenced in README/docs
- **THEN** any new trailing whitespace is caught in the same commit.
