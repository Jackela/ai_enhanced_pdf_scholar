"""
Unit tests for document upload route helper functions.

Tests the 4 helper functions extracted during Day 2 refactoring:
- _validate_file_upload
- _save_uploaded_file
- _import_and_build_response
- _map_document_import_error

All external dependencies (file system, services) are mocked.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest
from fastapi import HTTPException, UploadFile

from backend.api.routes.documents import (
    _import_and_build_response,
    _map_document_import_error,
    _save_uploaded_file,
    _validate_file_upload,
)
from src.services.document_library_service import (
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)

# ============================================================================
# Tests for _validate_file_upload
# ============================================================================


class TestValidateFileUpload:
    """Test file upload validation helper."""

    def test_valid_pdf_file_passes(self):
        """Valid PDF file should pass validation without exception."""
        mock_file = Mock(spec=UploadFile)
        mock_file.content_type = "application/pdf"

        # Should not raise any exception
        _validate_file_upload(mock_file)

    def test_none_file_raises_400(self):
        """None file should raise HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(None)

        assert exc_info.value.status_code == 400
        assert "required" in exc_info.value.detail.lower()

    def test_non_pdf_file_raises_415(self):
        """Non-PDF file should raise HTTPException 415."""
        mock_file = Mock(spec=UploadFile)
        mock_file.content_type = "text/plain"

        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(mock_file)

        assert exc_info.value.status_code == 415
        assert "pdf" in exc_info.value.detail.lower()

    def test_image_file_raises_415(self):
        """Image file should raise HTTPException 415."""
        mock_file = Mock(spec=UploadFile)
        mock_file.content_type = "image/png"

        with pytest.raises(HTTPException) as exc_info:
            _validate_file_upload(mock_file)

        assert exc_info.value.status_code == 415


# ============================================================================
# Tests for _save_uploaded_file
# ============================================================================


class TestSaveUploadedFile:
    """Test file saving with size validation helper."""

    @pytest.mark.asyncio
    async def test_saves_small_file_successfully(self, tmp_path):
        """Small file should be saved successfully."""
        # Create mock file with 1KB content
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(side_effect=[b"x" * 1024, b""])  # 1KB then EOF

        with patch("backend.api.routes.documents.build_safe_temp_path") as mock_build:
            temp_file = tmp_path / "test.pdf"
            mock_build.return_value = temp_file

            path, size = await _save_uploaded_file(mock_file, tmp_path)

        assert path == temp_file
        assert size == 1024
        assert temp_file.exists()
        assert temp_file.read_bytes() == b"x" * 1024

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_limit(self, tmp_path):
        """File exceeding size limit should raise HTTPException 413."""
        # Create mock file with 51MB content (exceeds 50MB limit)
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "large.pdf"
        # 6 chunks of 10MB each = 60MB total
        mock_file.read = AsyncMock(
            side_effect=[b"x" * chunk_size for _ in range(6)] + [b""]
        )

        with patch("backend.api.routes.documents.build_safe_temp_path") as mock_build:
            temp_file = tmp_path / "large.pdf"
            mock_build.return_value = temp_file

            with pytest.raises(HTTPException) as exc_info:
                await _save_uploaded_file(mock_file, tmp_path)

        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_correct_file_size(self, tmp_path):
        """Should return actual file size in bytes."""
        expected_size = 5000  # 5KB
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "exact.pdf"
        mock_file.read = AsyncMock(side_effect=[b"y" * expected_size, b""])

        with patch("backend.api.routes.documents.build_safe_temp_path") as mock_build:
            temp_file = tmp_path / "exact.pdf"
            mock_build.return_value = temp_file

            path, size = await _save_uploaded_file(mock_file, tmp_path)

        assert size == expected_size

    @pytest.mark.asyncio
    async def test_respects_custom_size_limit(self, tmp_path):
        """Should respect custom max_size_mb parameter."""
        # 3MB file, 2MB limit
        chunk_size = 1024 * 1024  # 1MB chunks
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "medium.pdf"
        mock_file.read = AsyncMock(
            side_effect=[b"z" * chunk_size for _ in range(3)] + [b""]
        )

        with patch("backend.api.routes.documents.build_safe_temp_path") as mock_build:
            temp_file = tmp_path / "medium.pdf"
            mock_build.return_value = temp_file

            with pytest.raises(HTTPException) as exc_info:
                await _save_uploaded_file(mock_file, tmp_path, max_size_mb=2)

        assert exc_info.value.status_code == 413


# ============================================================================
# Tests for _import_and_build_response
# ============================================================================


class TestImportAndBuildResponse:
    """Test document import and response building helper."""

    def test_imports_document_and_builds_response(self, tmp_path):
        """Should import document and build DocumentResponse."""
        temp_path = tmp_path / "test.pdf"
        temp_path.write_text("fake pdf")

        # Mock library service
        mock_service = Mock()
        mock_document = Mock()
        mock_document.id = 123
        mock_document.title = "Test Document"
        mock_document.file_hash = "abc123"
        mock_service.import_document.return_value = mock_document

        # Mock model_to_response_data with complete DocumentData
        with patch(
            "backend.api.routes.documents.model_to_response_data"
        ) as mock_to_data:
            mock_data = {
                "id": 123,
                "title": "Test Document",
                "file_hash": "abc123",
                "content_hash": "def456",
                "created_at": "2025-01-20T10:00:00",
                "is_file_available": True,
                "_links": {
                    "download": "/api/documents/123/download",
                    "preview": "/api/documents/123/preview",
                },
            }
            mock_to_data.return_value = mock_data

            response = _import_and_build_response(
                temp_path, "Test Title", True, False, mock_service
            )

        assert response.success is True
        assert response.data.id == 123  # Access via model attribute
        assert response.data.title == "Test Document"
        assert response.errors is None
        mock_service.import_document.assert_called_once_with(
            file_path=str(temp_path),
            title="Test Title",
            check_duplicates=True,
            overwrite_duplicates=False,
        )

    def test_passes_title_to_service(self, tmp_path):
        """Should pass title parameter to service."""
        temp_path = tmp_path / "test.pdf"

        mock_service = Mock()
        mock_service.import_document.return_value = Mock()

        with patch(
            "backend.api.routes.documents.model_to_response_data"
        ) as mock_to_data:
            # Provide complete mock data
            mock_to_data.return_value = {
                "id": 456,
                "title": "Custom Title",
                "file_hash": "hash",
                "content_hash": "hash2",
                "created_at": "2025-01-20T10:00:00",
                "is_file_available": True,
                "_links": {},
            }

            _import_and_build_response(
                temp_path, "Custom Title", False, True, mock_service
            )

        call_args = mock_service.import_document.call_args
        assert call_args.kwargs["title"] == "Custom Title"
        assert call_args.kwargs["check_duplicates"] is False
        assert call_args.kwargs["overwrite_duplicates"] is True


# ============================================================================
# Tests for _map_document_import_error
# ============================================================================


class TestMapDocumentImportError:
    """Test error mapping helper."""

    def test_http_exception_passed_through(self):
        """HTTPException should be returned unchanged."""
        exc = HTTPException(status_code=400, detail="test error")

        result = _map_document_import_error(exc)

        assert result is exc
        assert result.status_code == 400
        assert result.detail == "test error"

    def test_duplicate_error_maps_to_409(self):
        """DuplicateDocumentError should map to 409."""
        exc = DuplicateDocumentError(
            message="Duplicate found", user_message="Document already exists"
        )

        result = _map_document_import_error(exc)

        assert result.status_code == 409
        assert result.detail == "Document already exists"

    def test_validation_error_maps_to_400(self):
        """DocumentValidationError should map to 400."""
        exc = DocumentValidationError(
            message="Invalid PDF", user_message="File is corrupted"
        )

        result = _map_document_import_error(exc)

        assert result.status_code == 400
        assert result.detail == "File is corrupted"

    def test_import_error_maps_to_400(self):
        """DocumentImportError should map to 400."""
        exc = DocumentImportError(
            message="Import failed", user_message="Cannot process file"
        )

        result = _map_document_import_error(exc)

        assert result.status_code == 400
        assert result.detail == "Cannot process file"

    def test_duplicate_value_error_maps_to_409(self):
        """ValueError with 'duplicate' should map to 409."""
        exc = ValueError("Duplicate document detected")

        result = _map_document_import_error(exc)

        assert result.status_code == 409
        assert "duplicate" in result.detail.lower()

    def test_generic_value_error_maps_to_400(self):
        """Generic ValueError should map to 400."""
        exc = ValueError("Invalid input")

        result = _map_document_import_error(exc)

        assert result.status_code == 400
        assert result.detail == "Invalid input"

    def test_unknown_exception_maps_to_500(self):
        """Unknown exception should map to 500."""
        exc = RuntimeError("Unexpected error")

        with patch("backend.api.routes.documents.logger"):
            result = _map_document_import_error(exc)

        assert result.status_code == 500
        assert "failed" in result.detail.lower()
