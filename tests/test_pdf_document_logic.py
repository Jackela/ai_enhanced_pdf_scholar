"""
Unit tests for PDFDocument logic in src/pdf_document.py.
Tests PDF loading, page retrieval, rendering, text extraction and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
import fitz

from src.pdf_document import PDFDocument, PDFLoadError, PDFDocumentError


class DummyPage:
    """Mock fitz.Page for testing."""
    
    def __init__(self):
        self.get_pixmap = MagicMock()
        self.get_text = MagicMock(return_value="Sample text")
        
        # Mock pixmap
        mock_pixmap = MagicMock()
        mock_pixmap.samples = b"fake_image_data"
        mock_pixmap.width = 600
        mock_pixmap.height = 800
        mock_pixmap.stride = 1800  # 600 * 3 (RGB)
        self.get_pixmap.return_value = mock_pixmap


class DummyDocument:
    """Mock fitz.Document for testing."""
    
    def __init__(self, page_count=5):
        self._page_count = page_count
        self.close = MagicMock()
        self.load_page = MagicMock(return_value=DummyPage())
        
    @property
    def page_count(self):
        return self._page_count


@patch('src.pdf_document.fitz.open')
def test_pdf_document_successful_load(mock_fitz_open):
    """Test successful PDF document loading."""
    mock_doc = DummyDocument(page_count=10)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    assert pdf_doc.file_path == "test.pdf"
    assert pdf_doc.page_count == 10
    mock_fitz_open.assert_called_once_with("test.pdf")


@patch('src.pdf_document.fitz.open')
def test_pdf_document_load_failure(mock_fitz_open):
    """Test PDF loading failure raises PDFLoadError."""
    mock_fitz_open.side_effect = Exception("File not found")
    
    with pytest.raises(PDFLoadError) as exc_info:
        PDFDocument("nonexistent.pdf")
    
    assert "Failed to load PDF from 'nonexistent.pdf'" in str(exc_info.value)
    assert "File not found" in str(exc_info.value)


@patch('src.pdf_document.fitz.open')
def test_get_page_valid_index(mock_fitz_open):
    """Test getting page with valid index."""
    mock_doc = DummyDocument(page_count=5)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    page = pdf_doc.get_page(2)
    
    assert page is not None
    mock_doc.load_page.assert_called_once_with(2)
    assert pdf_doc._current_page == page


@patch('src.pdf_document.fitz.open')
def test_get_page_invalid_index_negative(mock_fitz_open):
    """Test getting page with negative index raises IndexError."""
    mock_doc = DummyDocument(page_count=5)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    with pytest.raises(IndexError) as exc_info:
        pdf_doc.get_page(-1)
    
    assert "Page number -1 is out of range (0-4)" in str(exc_info.value)


@patch('src.pdf_document.fitz.open')
def test_get_page_invalid_index_too_high(mock_fitz_open):
    """Test getting page with index too high raises IndexError."""
    mock_doc = DummyDocument(page_count=5)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    with pytest.raises(IndexError) as exc_info:
        pdf_doc.get_page(5)
    
    assert "Page number 5 is out of range (0-4)" in str(exc_info.value)


@patch('src.pdf_document.fitz.open')
def test_get_page_boundary_values(mock_fitz_open):
    """Test boundary page indices (0 and max)."""
    mock_doc = DummyDocument(page_count=3)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    # Test first page
    page0 = pdf_doc.get_page(0)
    assert page0 is not None
    
    # Test last page
    page2 = pdf_doc.get_page(2)
    assert page2 is not None
    
    # Verify load_page called with correct indices
    expected_calls = [call(0), call(2)]
    mock_doc.load_page.assert_has_calls(expected_calls)


@patch('src.pdf_document.fitz.open')
@patch('src.pdf_document.fitz.Matrix')
def test_render_page_default_dpi(mock_matrix, mock_fitz_open):
    """Test page rendering with default DPI."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    # Setup matrix mock
    mock_matrix_instance = MagicMock()
    mock_matrix.return_value = mock_matrix_instance
    
    pdf_doc = PDFDocument("test.pdf")
    page = pdf_doc.get_page(0)
    
    samples, width, height, stride = pdf_doc.render_page(page)
    
    # Verify matrix calculation (150 DPI default)
    expected_zoom = 150.0 / 72.0
    mock_matrix.assert_called_once_with(expected_zoom, expected_zoom)
    
    # Verify get_pixmap called with matrix
    page.get_pixmap.assert_called_once_with(matrix=mock_matrix_instance, alpha=False)
    
    # Verify returned values
    assert samples == b"fake_image_data"
    assert width == 600
    assert height == 800
    assert stride == 1800


@patch('src.pdf_document.fitz.open')
@patch('src.pdf_document.fitz.Matrix')
def test_render_page_custom_dpi(mock_matrix, mock_fitz_open):
    """Test page rendering with custom DPI."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    page = pdf_doc.get_page(0)
    
    pdf_doc.render_page(page, dpi=300)
    
    # Verify matrix calculation (300 DPI)
    expected_zoom = 300.0 / 72.0
    mock_matrix.assert_called_once_with(expected_zoom, expected_zoom)


@patch('src.pdf_document.fitz.open')
def test_get_text_in_rect(mock_fitz_open):
    """Test text extraction from rectangular area."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    page = pdf_doc.get_page(0)
    
    # Create mock rectangle
    mock_rect = MagicMock()
    page.get_text.return_value = "Extracted text"
    
    result = pdf_doc.get_text_in_rect(page, mock_rect)
    
    page.get_text.assert_called_once_with("text", clip=mock_rect)
    assert result == "Extracted text"


@patch('src.pdf_document.fitz.open')
def test_close_method(mock_fitz_open):
    """Test document close method."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    pdf_doc.close()
    
    mock_doc.close.assert_called_once()


@patch('src.pdf_document.fitz.open')
def test_context_manager(mock_fitz_open):
    """Test PDFDocument as context manager."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    with PDFDocument("test.pdf") as pdf_doc:
        assert pdf_doc is not None
        assert pdf_doc.page_count == 5
    
    # Should call close when exiting context
    mock_doc.close.assert_called_once()


@patch('src.pdf_document.fitz.open')
def test_context_manager_with_exception(mock_fitz_open):
    """Test context manager handles exceptions properly."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    try:
        with PDFDocument("test.pdf") as pdf_doc:
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # Should still call close even with exception
    mock_doc.close.assert_called_once()


@patch('src.pdf_document.fitz.open')
def test_page_count_property(mock_fitz_open):
    """Test page_count property returns correct value."""
    mock_doc = DummyDocument(page_count=15)
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    assert pdf_doc.page_count == 15


@patch('src.pdf_document.fitz.open')
def test_current_page_tracking(mock_fitz_open):
    """Test _current_page is updated correctly."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    
    # Initially no current page
    assert pdf_doc._current_page is None
    
    # Get page should update current page
    page = pdf_doc.get_page(1)
    assert pdf_doc._current_page == page
    
    # Get different page should update current page
    page2 = pdf_doc.get_page(2)
    assert pdf_doc._current_page == page2


def test_pdf_document_error_hierarchy():
    """Test exception hierarchy is correct."""
    assert issubclass(PDFDocumentError, Exception)
    assert issubclass(PDFLoadError, PDFDocumentError)
    
    # Test exception can be raised and caught
    with pytest.raises(PDFDocumentError):
        raise PDFLoadError("Test error")


@patch('src.pdf_document.fitz.open')
def test_render_page_pixmap_properties(mock_fitz_open):
    """Test render_page correctly extracts pixmap properties."""
    mock_doc = DummyDocument()
    mock_fitz_open.return_value = mock_doc
    
    pdf_doc = PDFDocument("test.pdf")
    page = pdf_doc.get_page(0)
    
    # Customize pixmap properties
    mock_pixmap = page.get_pixmap.return_value
    mock_pixmap.samples = b"custom_data"
    mock_pixmap.width = 1200
    mock_pixmap.height = 1600
    mock_pixmap.stride = 3600
    
    samples, width, height, stride = pdf_doc.render_page(page)
    
    assert samples == b"custom_data"
    assert width == 1200
    assert height == 1600
    assert stride == 3600 