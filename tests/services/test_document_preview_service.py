from pathlib import Path

import pytest

from src.database.models import DocumentModel
from src.services.document_preview_service import (
    DocumentPreviewService,
    PreviewSettings,
    PreviewUnsupportedError,
)


class _RepoStub:
    def __init__(self, document: DocumentModel):
        self._document = document

    def get_by_id(self, document_id: int):
        if self._document.id == document_id:
            return self._document
        return None


def _settings(tmp_path: Path) -> PreviewSettings:
    return PreviewSettings(
        enabled=True,
        cache_dir=tmp_path / "previews",
        max_width=800,
        min_width=200,
        thumbnail_width=256,
        max_page_number=50,
        cache_ttl_seconds=60,
    )


def test_preview_service_renders_and_caches(monkeypatch, tmp_path: Path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.3 test")

    document = DocumentModel(
        id=1,
        title="Test",
        file_path=str(pdf_path),
        file_hash="hash",
        file_size=100,
        file_type=".pdf",
        _from_database=True,
    )

    service = DocumentPreviewService(_RepoStub(document), _settings(tmp_path))

    render_calls = {"count": 0}

    def _fake_render(self, doc, page, width):  # pylint: disable=unused-argument
        render_calls["count"] += 1
        return b"preview-bytes", width, 128

    monkeypatch.setattr(DocumentPreviewService, "_render_page", _fake_render)

    preview = service.get_page_preview(1, page=1, width=400)
    assert preview.content == b"preview-bytes"
    assert preview.from_cache is False

    cached_preview = service.get_page_preview(1, page=1, width=400)
    assert cached_preview.from_cache is True
    assert render_calls["count"] == 1


def test_preview_service_rejects_unsupported_types(tmp_path: Path):
    dummy_file = tmp_path / "doc.txt"
    dummy_file.write_text("hello")

    document = DocumentModel(
        id=1,
        title="Test",
        file_path=str(dummy_file),
        file_hash="hash",
        file_size=10,
        file_type=".txt",
        _from_database=True,
    )

    service = DocumentPreviewService(_RepoStub(document), _settings(tmp_path))

    with pytest.raises(PreviewUnsupportedError):
        service.get_page_preview(1, page=1, width=400)
