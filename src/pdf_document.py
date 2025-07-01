import fitz  # PyMuPDF
from typing import Optional, Tuple

class PDFDocumentError(Exception):
    """Base exception for PDF document errors."""
    pass

class PDFLoadError(PDFDocumentError):
    """Raised when a PDF file cannot be loaded or parsed."""
    pass

class PDFDocument:
    """
    {
        "name": "PDFDocument",
        "version": "1.0.0",
        "description": "Handles all low-level PDF processing using PyMuPDF (fitz). This class is UI-agnostic.",
        "dependencies": ["PyMuPDF"],
        "interface": {}
    }
    Encapsulates a PDF document's data and operations, abstracting away the
    specifics of the underlying PDF library. It does not depend on any UI framework.
    """
    def __init__(self, file_path: str):
        """
        @param {string} file_path - The path to the PDF file.
        @raises {PDFLoadError} - If the file cannot be opened or is not a valid PDF.
        """
        try:
            self._doc: fitz.Document = fitz.open(file_path)
        except Exception as e:
            raise PDFLoadError(f"Failed to load PDF from '{file_path}': {e}") from e

        self.file_path = file_path
        self._current_page: Optional[fitz.Page] = None

    @property
    def page_count(self) -> int:
        """Returns the total number of pages in the document."""
        return self._doc.page_count

    def get_page(self, page_number: int) -> fitz.Page:
        """
        Loads and returns a specific page from the document.
        @param {int} page_number - The zero-indexed page number to retrieve.
        @returns {fitz.Page} - The loaded page object.
        @raises {IndexError} - If the page_number is out of bounds.
        """
        if not 0 <= page_number < self.page_count:
            raise IndexError(f"Page number {page_number} is out of range (0-{self.page_count - 1}).")
        self._current_page = self._doc.load_page(page_number)
        return self._current_page

    def render_page(self, page: fitz.Page, dpi: int = 150) -> Tuple[bytes, int, int, int]:
        """
        Renders a given page to a raw pixel map (bytes).
        @param {fitz.Page} page - The page object to render.
        @param {int} dpi - The resolution in dots per inch.
        @returns {Tuple[bytes, int, int, int]} - A tuple containing the raw image samples (bytes),
                                                 width, height, and stride.
        """
        zoom_factor = dpi / 72.0
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.samples, pix.width, pix.height, pix.stride

    def get_text_in_rect(self, page: fitz.Page, rect: fitz.Rect) -> str:
        """
        Extracts text from a specified rectangular area on a page.
        @param {fitz.Page} page - The page object to extract text from.
        @param {fitz.Rect} rect - The rectangle defining the area to extract text from.
        @returns {string} - The extracted text.
        """
        return page.get_text("text", clip=rect)

    def close(self):
        """Closes the document."""
        self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 