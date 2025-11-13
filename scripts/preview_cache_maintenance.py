"""Preview cache maintenance utility.

Usage examples:
    python scripts/preview_cache_maintenance.py stats
    python scripts/preview_cache_maintenance.py purge-expired --max-age 7200
    python scripts/preview_cache_maintenance.py purge-document --document-id 42
    python scripts/preview_cache_maintenance.py purge-max-size --max-gb 2
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from backend.config.application_config import get_application_config


@dataclass
class CacheStats:
    files: int
    total_bytes: int
    oldest_mtime: float | None
    newest_mtime: float | None

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def formatted_oldest(self) -> str:
        return time.ctime(self.oldest_mtime) if self.oldest_mtime else "n/a"

    @property
    def formatted_newest(self) -> str:
        return time.ctime(self.newest_mtime) if self.newest_mtime else "n/a"


def iter_cache_files(cache_dir: Path):
    for root, _, files in os.walk(cache_dir):
        for name in files:
            path = Path(root) / name
            if not path.is_file():
                continue
            yield path


def collect_stats(cache_dir: Path) -> CacheStats:
    total_bytes = 0
    oldest = None
    newest = None
    count = 0
    for path in iter_cache_files(cache_dir):
        stat = path.stat()
        total_bytes += stat.st_size
        count += 1
        oldest = min(oldest or stat.st_mtime, stat.st_mtime)
        newest = max(newest or stat.st_mtime, stat.st_mtime)
    return CacheStats(
        files=count, total_bytes=total_bytes, oldest_mtime=oldest, newest_mtime=newest
    )


def format_size(bytes_: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_ < 1024 or unit == "TB":
            return f"{bytes_:.2f} {unit}" if unit != "B" else f"{bytes_} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.2f} TB"


def purge_expired(cache_dir: Path, max_age: int) -> int:
    threshold = time.time() - max_age
    deleted = 0
    for path in iter_cache_files(cache_dir):
        if path.stat().st_mtime < threshold:
            path.unlink(missing_ok=True)
            deleted += 1
    # Remove empty directories
    for root, dirs, files in os.walk(cache_dir, topdown=False):
        if not dirs and not files:
            Path(root).rmdir()
    return deleted


def purge_document(cache_dir: Path, document_id: int) -> int:
    doc_dir = cache_dir / str(document_id)
    if not doc_dir.exists():
        return 0
    deleted = sum(1 for _ in doc_dir.glob("*"))
    shutil.rmtree(doc_dir)
    return deleted


def purge_max_size(cache_dir: Path, max_bytes: int) -> int:
    files = sorted(iter_cache_files(cache_dir), key=lambda p: p.stat().st_mtime)
    deleted = 0
    stats = collect_stats(cache_dir)
    while stats.total_bytes > max_bytes and files:
        path = files.pop(0)
        size = path.stat().st_size
        path.unlink(missing_ok=True)
        deleted += 1
        stats.total_bytes -= size
    for root, dirs, files in os.walk(cache_dir, topdown=False):
        if not dirs and not files:
            Path(root).rmdir()
    return deleted


def ensure_safe_cache_dir(cache_dir: Path, force: bool) -> None:
    home = Path.home().resolve()
    cache_dir = cache_dir.resolve()
    if force:
        return
    if not str(cache_dir).startswith(str(home)) and not str(cache_dir).startswith(
        "/tmp"
    ):
        raise RuntimeError(
            f"Cowardly refusing to operate on cache outside HOME or /tmp: {cache_dir}. "
            "Pass --force if you know what you are doing."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview cache maintenance tool")
    parser.add_argument(
        "--force", action="store_true", help="allow non-home cache directories"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("stats", help="display cache statistics")

    purge_expired_parser = subparsers.add_parser(
        "purge-expired", help="delete files older than TTL"
    )
    purge_expired_parser.add_argument(
        "--max-age", type=int, help="override max age (seconds)"
    )

    purge_doc_parser = subparsers.add_parser(
        "purge-document", help="delete cache entries for a document id"
    )
    purge_doc_parser.add_argument("--document-id", type=int, required=True)

    purge_size_parser = subparsers.add_parser(
        "purge-max-size", help="delete oldest entries until size <= max GB"
    )
    purge_size_parser.add_argument("--max-gb", type=float, required=True)

    args = parser.parse_args(argv)

    config = get_application_config()
    preview_cfg = getattr(config, "preview", None)
    if not preview_cfg:
        raise RuntimeError(
            "Preview configuration is not available. Has ApplicationConfig been initialized?"
        )

    cache_dir = Path(preview_cfg.cache_dir).expanduser()
    ensure_safe_cache_dir(cache_dir, force=args.force)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "stats":
        stats = collect_stats(cache_dir)
        print(f"Cache directory: {cache_dir}")
        print(f"Files: {stats.files}")
        print(f"Total size: {format_size(stats.total_bytes)}")
        print(f"Oldest entry: {stats.formatted_oldest}")
        print(f"Newest entry: {stats.formatted_newest}")
        return 0

    if args.command == "purge-expired":
        ttl = args.max_age or getattr(preview_cfg, "cache_ttl_seconds", 3600)
        deleted = purge_expired(cache_dir, ttl)
        print(f"Deleted {deleted} expired files (max age {ttl}s)")
        return 0

    if args.command == "purge-document":
        deleted = purge_document(cache_dir, args.document_id)
        print(f"Deleted {deleted} files for document {args.document_id}")
        return 0

    if args.command == "purge-max-size":
        max_bytes = int(args.max_gb * 1024**3)
        deleted = purge_max_size(cache_dir, max_bytes)
        print(f"Deleted {deleted} files to enforce {args.max_gb}GB limit")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
