# Preview Cache Maintenance Guide

Use `scripts/preview_cache_maintenance.py` to inspect and purge cached preview/thumbnail files.

## Commands

### Stats
```bash
python scripts/preview_cache_maintenance.py stats
```
Shows cache directory, file count, total size, and oldest/newest entries (based on `PREVIEW_CACHE_DIR`).

### Purge expired
```bash
python scripts/preview_cache_maintenance.py purge-expired
# override TTL
python scripts/preview_cache_maintenance.py purge-expired --max-age 7200
```
Removes files older than the configured TTL (`PREVIEW_CACHE_TTL_SECONDS` by default).

### Purge by document
```bash
python scripts/preview_cache_maintenance.py purge-document --document-id 42
```
Deletes all cached previews for the specified document ID.

### Enforce max size
```bash
python scripts/preview_cache_maintenance.py purge-max-size --max-gb 2
```
Deletes oldest entries until total usage is below the provided size.

## Automation
- Run `purge-expired` hourly via cron or a Kubernetes CronJob to keep cache fresh.
- Use `purge-max-size` weekly if disk quotas are tight.

## Safety
- The script refuses to operate on directories outside `$HOME` or `/tmp` unless `--force` is passed.
- All deletions log the number of files removed. Integrate with your monitoring pipeline if desired.
