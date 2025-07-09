import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import fitz
from PyQt6.QtCore import Qt, QPoint, QRectF, QCoreApplication, QPointF, QObject
from PyQt6.QtGui import QImage

from src.pdf_viewer import PDFViewer
from src.pdf_document import PDFLoadError

# Helper class to capture signals and their arguments
class SignalListener(QObject):
    def __init__(self, signal):
        super().__init__()
        self.received = []
        signal.connect(self.on_signal)

    def on_signal(self, *args):
        self.received.append(args)

    @property
    def call_count(self):
        return len(self.received)

    @property
    def last_call_args(self):
        return self.received[-1] if self.received else None

# We need a running QApplication for this test
pytestmark = pytest.mark.usefixtures("qapp")

@pytest.fixture
def mock_pdf_document_cls():
    """
    Fixture to patch the PDFDocument class.
    This provides a robust mock that can handle different calls to get_text.
    """
    with patch('src.pdf_viewer.PDFDocument', autospec=True) as mock_cls:
        # --- Create realistic mock data ---
        pix = fitz.Pixmap(fitz.csRGB, fitz.Rect(0, 0, 1, 1), 0)
        pix.set_pixel(0, 0, (255, 255, 255))
        
        mock_instance = MagicMock()
        mock_page = MagicMock()
        
        # Configure the mock page's properties
        type(mock_page).rect = PropertyMock(return_value=fitz.Rect(0, 0, 600, 800))

        # Define a side_effect function for get_text
        def get_text_side_effect(text_type):
            if text_type == "words":
                return [
                    (10, 10, 50, 20, "Hello", 0, 0, 0),
                    (55, 10, 90, 20, "World", 0, 0, 1),
                ]
            elif text_type == "text":
                return "Full page text for context."
            return "" # Default empty return
        
        mock_page.get_text.side_effect = get_text_side_effect
        
        mock_instance.get_page.return_value = mock_page
        mock_instance.render_page.return_value = (pix.samples, pix.width, pix.height, pix.stride)
        mock_instance.page_count = 5
        
        mock_cls.return_value = mock_instance
        yield mock_cls

def test_load_pdf_success(qtbot, mock_pdf_document_cls, resource_manager):
    """Tests that loading a PDF successfully emits the view_changed signal."""
    viewer = resource_manager.register(PDFViewer(), 'qt')
    
    listener = SignalListener(viewer.view_changed)
    
    viewer.load_pdf("some/path.pdf")
    
    assert viewer.document is not None
    # render_page is called during load, which emits the signal
    assert listener.call_count > 0
    mock_pdf_document_cls.assert_called_with("some/path.pdf")

def test_load_pdf_failure(qtbot, mock_pdf_document_cls, resource_manager):
    """Tests that a failing PDF load emits the error_occurred signal."""
    mock_pdf_document_cls.side_effect = PDFLoadError("Failed to load")
    
    viewer = resource_manager.register(PDFViewer(), 'qt')
    
    listener = SignalListener(viewer.error_occurred)
    
    viewer.load_pdf("bad/path.pdf")
    
    assert viewer.document is None
    assert listener.call_count == 1
    assert "Failed to load PDF: Failed to load" in listener.last_call_args[0]

def test_text_selection_emits_signal(qtbot, mock_pdf_document_cls, resource_manager):
    """Tests that a mouse drag in TEXT mode correctly triggers the text_query_requested signal."""
    viewer = resource_manager.register(PDFViewer(), 'qt')
    viewer.load_pdf("some/path.pdf")
    viewer.resize(600, 800)

    listener = SignalListener(viewer.text_query_requested)

    # Get image information for coordinate calculation
    x_offset, y_offset = viewer.get_image_offsets()

    # Word boxes are at PDF coordinates: [(10, 10, 50, 20, 'Hello'), (55, 10, 90, 20, 'World')]
    # Convert PDF coordinates to widget coordinates for proper selection
    word1_widget_x = 10 * viewer.current_render_scale_x + x_offset
    word1_widget_y = 10 * viewer.current_render_scale_y + y_offset
    word2_widget_x = 90 * viewer.current_render_scale_x + x_offset  # End of second word
    word_widget_y_end = 20 * viewer.current_render_scale_y + y_offset  # Bottom of words
    
    # Use coordinates that should cover both words
    start_pos = QPointF(word1_widget_x - 5, word1_widget_y - 5)
    end_pos = QPointF(word2_widget_x + 5, word_widget_y_end + 5)
    
    qtbot.mousePress(viewer, Qt.MouseButton.LeftButton, pos=start_pos.toPoint())
    qtbot.mouseMove(viewer, pos=end_pos.toPoint())
    qtbot.mouseRelease(viewer, Qt.MouseButton.LeftButton, pos=end_pos.toPoint())
    
    assert listener.call_count == 1
    
    selected_text, context_text, pdf_rect = listener.last_call_args
    # The selected text is now precisely what the mock returns for the selected words
    assert selected_text == "Hello World"
    assert context_text == "Full page text for context."
    assert isinstance(pdf_rect, fitz.Rect)

def test_screenshot_selection_emits_signal(qtbot, mock_pdf_document_cls, resource_manager):
    """Tests that a mouse drag in SCREENSHOT mode (with Ctrl) triggers the image_query_requested signal."""
    viewer = resource_manager.register(PDFViewer(), 'qt')
    viewer.load_pdf("some/path.pdf")
    viewer.resize(600, 800)
    # Ensure the pixmap is rendered and available for screenshotting
    viewer.render_page() 

    listener = SignalListener(viewer.image_query_requested)

    # Simulate a mouse drag WHILE holding Ctrl
    start_pos = QPointF(10, 10)
    end_pos = QPointF(100, 100)
    
    qtbot.mousePress(viewer, Qt.MouseButton.LeftButton, pos=start_pos.toPoint(), modifier=Qt.KeyboardModifier.ControlModifier)
    qtbot.mouseMove(viewer, pos=end_pos.toPoint())
    qtbot.mouseRelease(viewer, Qt.MouseButton.LeftButton, pos=end_pos.toPoint())

    assert listener.call_count == 1
    screenshot = listener.last_call_args[0]
    assert isinstance(screenshot, QImage)

def test_render_page_emits_signal(qtbot, mock_pdf_document_cls, resource_manager):
    """Tests that calling render_page() triggers a view_changed signal."""
    viewer = resource_manager.register(PDFViewer(), 'qt')
    viewer.load_pdf("some/path.pdf")
    
    # Use qtbot.waitSignal to wait for the signal to be emitted
    with qtbot.waitSignal(viewer.view_changed, timeout=1000) as blocker:
        # Directly call the method we want to test
        viewer.render_page()
    
    assert blocker.signal_triggered 