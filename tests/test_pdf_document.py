import pytest
from unittest.mock import MagicMock, patch
import fitz  # PyMuPDF is imported to use its object types for mocking

from src.pdf_document import PDFDocument, PDFLoadError

@pytest.fixture
def mock_fitz_document():
    """A pytest fixture that provides a mock fitz.Document object."""
    mock_doc = MagicMock(spec=fitz.Document)
    mock_doc.page_count = 5

    # Mock pages
    mock_pages = []
    for i in range(5):
        mock_page = MagicMock(spec=fitz.Page)
        mock_page.number = i
        # Simulate get_text to return text based on the clip rectangle
        mock_page.get_text.return_value = f"Text from page {i}"
        mock_pages.append(mock_page)

    mock_doc.load_page.side_effect = lambda page_num: mock_pages[page_num]
    return mock_doc

@patch('fitz.open')
def test_pdf_document_load_success(mock_fitz_open, mock_fitz_document):
    """Tests successful loading of a PDF document."""
    mock_fitz_open.return_value = mock_fitz_document
    
    doc = PDFDocument("valid/path.pdf")
    
    assert doc.page_count == 5
    mock_fitz_open.assert_called_once_with("valid/path.pdf")
    doc.close()

@patch('fitz.open')
def test_pdf_document_load_failure(mock_fitz_open):
    """Tests that PDFLoadError is raised on failure to load a document."""
    mock_fitz_open.side_effect = Exception("Failed to open document")
    
    with pytest.raises(PDFLoadError, match="Failed to load PDF from 'invalid/path.pdf'"):
        PDFDocument("invalid/path.pdf")

@patch('fitz.open')
def test_get_page_success(mock_fitz_open, mock_fitz_document):
    """Tests successful retrieval of a page."""
    mock_fitz_open.return_value = mock_fitz_document
    doc = PDFDocument("valid/path.pdf")
    
    page = doc.get_page(2)
    assert page is not None
    assert page.number == 2
    mock_fitz_document.load_page.assert_called_with(2)
    doc.close()

@patch('fitz.open')
def test_get_page_out_of_bounds(mock_fitz_open, mock_fitz_document):
    """Tests that getting a page with an out-of-bounds index raises IndexError."""
    mock_fitz_open.return_value = mock_fitz_document
    doc = PDFDocument("valid/path.pdf")

    with pytest.raises(IndexError):
        doc.get_page(10)
    
    with pytest.raises(IndexError):
        doc.get_page(-1)
    
    doc.close()

@patch('fitz.open')
def test_get_text_in_rect(mock_fitz_open, mock_fitz_document):
    """Tests extracting text from a specified rectangle."""
    mock_fitz_open.return_value = mock_fitz_document
    doc = PDFDocument("valid/path.pdf")
    page = doc.get_page(3)
    
    test_rect = fitz.Rect(0, 0, 100, 100)
    text = doc.get_text_in_rect(page, test_rect)
    
    assert text == "Text from page 3"
    # Verify that get_text was called with the correct parameters
    page.get_text.assert_called_once_with("text", clip=test_rect)
    doc.close()

@patch('fitz.open')
def test_context_manager(mock_fitz_open, mock_fitz_document):
    """Tests that the document is closed when using a 'with' statement."""
    mock_fitz_open.return_value = mock_fitz_document
    
    with PDFDocument("valid/path.pdf") as doc:
        assert doc.page_count == 5
    
    # Check that the close method on the mock document was called
    mock_fitz_document.close.assert_called_once() 