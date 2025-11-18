from __future__ import annotations

from pathlib import Path

import pytest

from src.services.content_hash_service import ContentHashError, ContentHashService

pytestmark = pytest.mark.services


def test_calculate_file_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "file.bin"
    file_path.write_bytes(b"abc123")
    file_hash = ContentHashService.calculate_file_hash(str(file_path))
    assert len(file_hash) == 16
    assert file_hash == ContentHashService.calculate_file_hash(str(file_path))


def test_calculate_file_hash_missing(tmp_path: Path) -> None:
    with pytest.raises(ContentHashError) as exc:
        ContentHashService.calculate_file_hash(str(tmp_path / "missing.pdf"))
    assert "File hashing failed" in str(exc.value)


def test_calculate_content_hash_string() -> None:
    content_hash = ContentHashService.calculate_content_hash("Hello World")
    assert len(content_hash) == 64


def test_calculate_content_hash_invalid_type() -> None:
    with pytest.raises(TypeError):
        ContentHashService.calculate_content_hash(None)  # type: ignore[arg-type]
