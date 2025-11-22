from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts import preview_cache_maintenance as pcm


class StubPreviewConfig:
    def __init__(self, cache_dir: Path, ttl: int = 60):
        self.cache_dir = str(cache_dir)
        self.cache_ttl_seconds = ttl


class StubAppConfig:
    def __init__(self, cache_dir: Path):
        self.preview = StubPreviewConfig(cache_dir)


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "preview-cache"
    cache_dir.mkdir()
    return cache_dir


def _write_file(path: Path, size: int = 1, age_seconds: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if age_seconds:
        past = time.time() - age_seconds
        os.utime(path, (past, past))


def test_collect_stats_reports_counts(cache_dir: Path):
    _write_file(cache_dir / "1" / "page.png", size=2048)
    stats = pcm.collect_stats(cache_dir)
    assert stats.files == 1
    assert stats.total_bytes == 2048
    assert stats.formatted_oldest != "n/a"
    assert stats.formatted_newest != "n/a"


def test_purge_expired_removes_old_files(cache_dir: Path):
    _write_file(cache_dir / "1" / "old.png", age_seconds=100)
    _write_file(cache_dir / "1" / "new.png", age_seconds=1)
    deleted = pcm.purge_expired(cache_dir, max_age=10)
    assert deleted == 1
    assert (cache_dir / "1" / "new.png").exists()


def test_purge_document_removes_doc_folder(cache_dir: Path):
    _write_file(cache_dir / "42" / "preview.png")
    deleted = pcm.purge_document(cache_dir, document_id=42)
    assert deleted == 1
    assert not (cache_dir / "42").exists()


def test_purge_max_size_deletes_oldest(cache_dir: Path):
    _write_file(cache_dir / "1" / "a.png", size=100, age_seconds=100)
    _write_file(cache_dir / "2" / "b.png", size=100, age_seconds=10)
    deleted = pcm.purge_max_size(cache_dir, max_bytes=150)
    assert deleted == 1
    remaining = list(pcm.iter_cache_files(cache_dir))
    assert len(remaining) == 1
    assert "b.png" in str(remaining[0])


def test_ensure_safe_cache_dir_blocks_outside():
    outside = Path("/etc")
    with pytest.raises(RuntimeError):
        pcm.ensure_safe_cache_dir(outside, force=False)


def test_main_stats_and_purge_commands(monkeypatch, cache_dir: Path):
    stub_config = StubAppConfig(cache_dir)
    monkeypatch.setattr(
        "scripts.preview_cache_maintenance.get_application_config",
        lambda: stub_config,
    )
    assert pcm.main(["--force", "stats"]) == 0
    _write_file(cache_dir / "123" / "p.png", age_seconds=100)
    assert pcm.main(["--force", "purge-expired", "--max-age", "0"]) == 0
