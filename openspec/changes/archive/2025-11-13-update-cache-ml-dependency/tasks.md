## Tasks
- [x] Analyze current dependency sets (`pyproject.toml`, requirements-*.txt, Dockerfile) to record where scikit-learn is referenced
- [x] Decide on target strategy (core dependency vs optional profile) with pros/cons documented
- [x] Update dependency manifests, Dockerfile, and setup docs to match the decision
- [x] Enhance startup diagnostics/config validation to ensure cache settings align with installed deps
- [x] Refresh documentation (DEPENDENCY_NOTES.md, PROJECT_DOCS.md, README) describing how to enable ML caching
- [x] Run `openspec validate update-cache-ml-dependency --strict`
