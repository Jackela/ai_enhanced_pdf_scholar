"""Utilities for sanitizing document paths and upload filenames."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_upload_filename(filename: str | None) -> str:
    """Return a filesystem-safe filename limited to PDF uploads."""
    if not filename:
        return "upload.pdf"
    # Drop any path components and normalize whitespace
    candidate = Path(filename).name.strip()
    if not candidate:
        candidate = "upload.pdf"
    # Replace unsafe characters
    candidate = SAFE_FILENAME.sub("_", candidate)
    # Enforce .pdf extension
    if not candidate.lower().endswith(".pdf"):
        candidate = f"{candidate}.pdf"
    # Prevent extremely long filenames
    return candidate[:120]


def build_safe_temp_path(documents_dir: Path, original_filename: str | None) -> Path:
    """Create a secure temporary path under the managed documents directory."""
    sanitized = sanitize_upload_filename(original_filename)
    temp_dir = documents_dir.parent / "_tmp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    return temp_dir / f"{token}_{sanitized}"


def is_within_allowed_roots(path: Path, allowed_roots: list[Path]) -> bool:
    """Ensure the resolved path is contained within one of the allowed roots."""
    try:
        resolved = path.resolve()
        for root in allowed_roots:
            if resolved.is_relative_to(root.resolve()):
                return True
        return False
    except FileNotFoundError:
        # If the path does not exist yet, validate parent directory
        parent = path.parent.resolve()
        return any(parent.is_relative_to(root.resolve()) for root in allowed_roots)
