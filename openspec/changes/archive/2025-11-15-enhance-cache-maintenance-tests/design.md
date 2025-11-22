# Design Notes – Enhance Cache & Path Safety Tests

## Strategy
- Use `tmp_path` fixtures to create cache directories with files whose mtimes we can control (via `os.utime`). This allows deterministic verification of TTL/size cleanup logic.
- For integrated cache manager tests, instantiate the manager with stub cache layers + metrics collectors that record method calls; assertions will compare hit/miss counts and cleanup actions.
- The preview cache maintenance CLI can be executed via subprocess or directly by importing its `main()` entry point with injected arguments pointing to temp directories.
- Path-safety helper tests will focus on adversarial filenames and root lists, ensuring traversal attempts raise/return `False`.

## Tooling
- Pytest + tmp_path/time mocking; avoid external dependencies (Redis, real caches).
- Logging assertions (using `caplog`) confirm maintenance scripts emit actionable info.
