# Preview Cache Maintenance Design

## Cache Layout
- Directory: `PREVIEW_CACHE_DIR` (default `~/.ai_pdf_scholar/previews`).
- Structure: `<cache_dir>/<document_id>/page-{page}-w{width}.png` plus `.meta` files storing width/height.
- TTL: `PREVIEW_CACHE_TTL_SECONDS` (default 3600) — currently enforced lazily when reading the cache.

## Goals
1. Provide a CLI utility to inspect cache size, purge expired entries, and clear a specific document.
2. Make it easy to automate (cron/systemd) by exposing `--dry-run`, `--max-age`, and `--max-size-gb` options.
3. Share logic with runtime (same cache TTL + file structure) so behaviour stays consistent.

## Strategy
- Implement `scripts/preview_cache_maintenance.py` that loads `ApplicationConfig` to discover cache dir + TTL.
- Supports subcommands:
  - `stats` → reports total size, file count, newest/oldest mtime.
  - `purge-expired` → deletes files older than TTL or user-supplied `--max-age`.
  - `purge-document --id <doc_id>` → deletes cache folder for a document.
  - `purge-max-size --max-gb N` → deletes oldest files until usage <= N GB.
- Logging: prints summary table; exit codes non-zero on error.

## Scheduling Guidance
- Operators can run `python scripts/preview_cache_maintenance.py purge-expired` via cron (recommended every hour).
- For container deployments, command can be invoked in a Kubernetes CronJob.

## Safety
- All deletions performed with explicit confirmation unless `--yes` is supplied (default yes for automation but can be toggled).
- Script refuses to run if cache dir is not inside user home or `/tmp` unless `--force` flag is passed.

## Observability
- After purge, script prints counts deleted/retained and resulting disk usage.
- Future work: expose metrics via management endpoint if needed.
