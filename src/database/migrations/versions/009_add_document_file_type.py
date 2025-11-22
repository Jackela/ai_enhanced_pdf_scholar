"""
Migration 009: Add file_type column to documents

Ensures every document row stores a canonical file type/extension that can be
referenced by APIs, services, and metrics.
"""

import json
import logging
from pathlib import Path

try:
    from ..base import BaseMigration
except ImportError:
    import sys
    from pathlib import Path as _Path

    sys.path.append(str(_Path(__file__).parent.parent))
    from base import BaseMigration

logger = logging.getLogger(__name__)


class AddDocumentFileTypeMigration(BaseMigration):
    """Add file_type column and backfill values for existing documents."""

    @property
    def version(self) -> int:
        return 9

    @property
    def description(self) -> str:
        return "Add documents.file_type column and backfill existing rows"

    @property
    def rollback_supported(self) -> bool:
        # Rolling back would require recreating the documents table; not supported
        return False

    def up(self) -> None:
        """Apply migration."""
        logger.info("Adding file_type column to documents table")

        if self._column_exists("documents", "file_type"):
            logger.info("file_type column already exists - skipping migration")
            return

        self.execute_sql("ALTER TABLE documents ADD COLUMN file_type TEXT")
        self._backfill_file_types()
        logger.info("file_type column added and backfilled successfully")

    def down(self) -> None:
        """Rollback migration (not supported)."""
        logger.warning(
            "Rollback is not supported for migration 009 (file_type column)."
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _column_exists(self, table: str, column: str) -> bool:
        """Check whether a column exists on a table."""
        try:
            rows = self.db.fetch_all(f"PRAGMA table_info({table})")
            return any(row["name"] == column for row in rows)
        except Exception as exc:
            logger.error(f"Failed to inspect columns for {table}: {exc}")
            raise

    def _backfill_file_types(self) -> None:
        """Populate file_type for existing documents using metadata or file path."""
        rows = self.db.fetch_all("SELECT id, file_path, metadata FROM documents")
        logger.info(f"Backfilling file_type for {len(rows)} documents")

        for row in rows:
            file_type = self._infer_file_type(row)
            if not file_type:
                continue

            self.execute_sql(
                "UPDATE documents SET file_type = ? WHERE id = ?",
                (file_type, self._row_value(row, "id")),
            )

    def _infer_file_type(self, row: dict) -> str | None:
        """Infer file type from metadata or file path."""
        # 1) metadata-based inference
        metadata = self._row_value(row, "metadata")
        if metadata:
            try:
                metadata_obj = json.loads(metadata)
            except Exception:
                metadata_obj = None
            if metadata_obj:
                candidate = (
                    metadata_obj.get("file_type")
                    or metadata_obj.get("file_extension")
                    or self._mime_to_extension(metadata_obj.get("mime_type"))
                )
                normalized = self._normalize_extension(candidate)
                if normalized:
                    return normalized

        # 2) file path extension
        file_path = self._row_value(row, "file_path")
        if file_path:
            normalized = self._normalize_extension(Path(file_path).suffix)
            if normalized:
                return normalized

        # 3) fall back to default PDF for unknown rows
        return ".pdf"

    def _row_value(self, row: dict, key: str):
        """Support both dict and sqlite3.Row access styles."""
        if isinstance(row, dict):
            return row.get(key)
        return row[key]

    def _mime_to_extension(self, mime_type: str | None) -> str | None:
        """Convert a MIME type to a canonical extension."""
        if not mime_type:
            return None
        mime_type = mime_type.lower()
        mapping = {
            "application/pdf": ".pdf",
        }
        return mapping.get(mime_type)

    def _normalize_extension(self, value: str | None) -> str | None:
        """Normalize extensions to lowercase dotted format."""
        if not value:
            return None

        value = value.strip().lower()
        if not value:
            return None

        # If looks like mime type, convert
        if "/" in value and not value.startswith("."):
            converted = self._mime_to_extension(value)
            if converted:
                return converted

        if not value.startswith("."):
            value = f".{value}"

        return value
