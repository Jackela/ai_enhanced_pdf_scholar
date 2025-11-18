from __future__ import annotations

from pathlib import Path

from backend.api.utils.path_safety import (
    build_safe_temp_path,
    is_within_allowed_roots,
    sanitize_upload_filename,
)


def test_is_within_allowed_roots_accepts_nested(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    nested = root / "sub" / "file.pdf"
    nested.parent.mkdir()
    nested.write_text("data")
    assert is_within_allowed_roots(nested, [root]) is True


def test_is_within_allowed_roots_rejects_outside(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "file.pdf"
    outside.parent.mkdir()
    outside.write_text("data")
    assert is_within_allowed_roots(outside, [root]) is False


def test_build_safe_temp_path_places_file_in_tmp(tmp_path: Path) -> None:
    docs_dir = tmp_path / "storage"
    docs_dir.mkdir()
    temp_path = build_safe_temp_path(docs_dir, "../../weird.pdf")
    assert temp_path.parent.name == "_tmp_uploads"
    assert temp_path.suffix == ".pdf"
    assert temp_path.parent.parent == docs_dir.parent


def test_sanitize_upload_filename_strips_paths() -> None:
    name = sanitize_upload_filename("../../evil\nname.exe")
    assert name.endswith(".pdf")
    assert ".." not in name
