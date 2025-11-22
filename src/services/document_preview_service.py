"""Document Preview Service
Generates lightweight previews/thumbnails for managed documents.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from src.database.models import DocumentModel
from src.interfaces.repository_interfaces import IDocumentRepository

# Lazy import PyMuPDF to avoid test-time import errors
# The fitz module is only imported when actually rendering PDFs
if TYPE_CHECKING:
    import fitz  # PyMuPDF - type checking only

logger = logging.getLogger(__name__)


class PreviewError(RuntimeError):
    """Base preview service error."""


class PreviewDisabledError(PreviewError):
    """Raised when previews are disabled by configuration."""


class PreviewUnsupportedError(PreviewError):
    """Raised when file type is unsupported for previews."""


class PreviewNotFoundError(PreviewError):
    """Raised when document or requested page cannot be found."""


@dataclass
class PreviewSettings:
    """Runtime settings for preview generation/caching."""

    enabled: bool
    cache_dir: Path
    max_width: int
    min_width: int
    thumbnail_width: int
    max_page_number: int
    cache_ttl_seconds: int


class PreviewContent(NamedTuple):
    content: bytes
    content_type: str
    width: int
    height: int
    page: int
    from_cache: bool


class DocumentPreviewService:
    """Render and cache document previews using PyMuPDF."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        settings: PreviewSettings,
    ) -> None:
        self._repo = document_repository
        self.settings = settings
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_page_preview(
        self, document_id: int, page: int, width: int | None = None
    ) -> PreviewContent:
        """Render or fetch cache for a specific document page."""
        self._ensure_enabled()
        normalized_page = self._normalize_page(page)
        normalized_width = self._normalize_width(width)
        document = self._get_document(document_id)

        cache_path = self._cache_path(document.id, normalized_page, normalized_width)
        cached = self._read_cache(cache_path)
        if cached is not None:
            cached_width, cached_height = self._read_dimensions(cache_path)
            return PreviewContent(
                cached, "image/png", cached_width, cached_height, normalized_page, True
            )

        start = time.perf_counter()
        content, width_px, height_px = self._render_page(
            document, normalized_page, normalized_width
        )
        render_duration = time.perf_counter() - start
        logger.debug(
            "Rendered preview for document %s page %s at width %s in %.2fms",
            document.id,
            normalized_page,
            width_px,
            render_duration * 1000,
        )
        self._write_cache(cache_path, content)
        self._write_dimensions(cache_path, width_px, height_px)
        return PreviewContent(
            content, "image/png", width_px, height_px, normalized_page, False
        )

    def get_thumbnail(self, document_id: int) -> PreviewContent:
        """Return cached first-page thumbnail."""
        return self.get_page_preview(
            document_id=document_id,
            page=1,
            width=self.settings.thumbnail_width,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled:
            raise PreviewDisabledError("Document previews are disabled")

    def _normalize_page(self, page: int) -> int:
        if page < 1:
            raise PreviewError("Page must be >= 1")
        if page > self.settings.max_page_number:
            raise PreviewError("Requested page exceeds configured limit")
        return page

    def _normalize_width(self, width: int | None) -> int:
        if width is None:
            width = self.settings.max_width
        width = max(self.settings.min_width, min(width, self.settings.max_width))
        return width

    def _get_document(self, document_id: int) -> DocumentModel:
        getter = getattr(self._repo, "get_by_id", None)
        if not getter:
            getter = getattr(self._repo, "find_by_id", None)
        if not getter:
            raise PreviewError("Document repository does not support ID lookups")
        document = getter(document_id)
        if not document:
            raise PreviewNotFoundError(f"Document {document_id} not found")
        if not document.file_path:
            raise PreviewNotFoundError("Document file path missing")
        if document.file_type and document.file_type.lower() not in {".pdf"}:
            raise PreviewUnsupportedError("Only PDF previews are supported")
        return document

    def _cache_path(self, document_id: int, page: int, width: int) -> Path:
        doc_dir = self.settings.cache_dir / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir / f"page-{page}-w{width}.png"

    def _read_cache(self, cache_path: Path) -> bytes | None:
        if not cache_path.exists():
            return None
        age = time.time() - cache_path.stat().st_mtime
        if age > self.settings.cache_ttl_seconds:
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to delete expired preview cache: %s", cache_path)
            return None
        try:
            return cache_path.read_bytes()
        except Exception as exc:
            logger.warning("Failed to read preview cache %s: %s", cache_path, exc)
            return None

    def _render_page(
        self, document: DocumentModel, page: int, width: int
    ) -> tuple[bytes, int, int]:
        # Lazy import fitz (PyMuPDF) only when actually rendering
        # This prevents import errors in test environments where PyMuPDF may not be available
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise PreviewError(
                "PyMuPDF (fitz) is not installed. Install it with: pip install PyMuPDF"
            ) from exc

        file_path = Path(document.file_path)
        if not file_path.exists():
            raise PreviewNotFoundError("Document file is not available on disk")

        try:
            with fitz.open(file_path) as pdf_doc:
                if page > pdf_doc.page_count:
                    raise PreviewNotFoundError("Requested page exceeds document length")
                pdf_page = pdf_doc.load_page(page - 1)
                original_width = pdf_page.rect.width or 1
                scale = width / original_width
                matrix = fitz.Matrix(scale, scale)
                pixmap = pdf_page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
                return pixmap.tobytes("png"), pixmap.width, pixmap.height
        except PreviewNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to render preview for %s page %s: %s", document.id, page, exc
            )
            raise PreviewError("Failed to render preview") from exc

    def _write_cache(self, cache_path: Path, data: bytes) -> None:
        try:
            temp_path = cache_path.with_suffix(".tmp")
            temp_path.write_bytes(data)
            temp_path.replace(cache_path)
        except Exception as exc:
            logger.debug("Failed to persist preview cache %s: %s", cache_path, exc)

    def _dimensions_path(self, cache_path: Path) -> Path:
        return cache_path.with_suffix(cache_path.suffix + ".meta")

    def _write_dimensions(self, cache_path: Path, width: int, height: int) -> None:
        try:
            self._dimensions_path(cache_path).write_text(f"{width},{height}")
        except Exception as exc:
            logger.debug("Failed to write preview metadata %s: %s", cache_path, exc)

    def _read_dimensions(self, cache_path: Path) -> tuple[int, int]:
        meta_path = self._dimensions_path(cache_path)
        if not meta_path.exists():
            return self.settings.max_width, self.settings.max_width
        try:
            width_str, height_str = meta_path.read_text().split(",")
            return int(width_str), int(height_str)
        except Exception:
            return self.settings.max_width, self.settings.max_width
