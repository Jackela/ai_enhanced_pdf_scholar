from typing import Optional, Tuple, List
from enum import Enum, auto
from PyQt6.QtWidgets import QWidget, QMessageBox, QSizePolicy, QApplication
from PyQt6.QtCore import Qt, QRectF, QPoint, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QImage, QColor, QPen, QBrush
import fitz  # PyMuPDF

from src.pdf_document import PDFDocument, PDFLoadError
from src.responsive_utils import responsive_calc

CONTEXT_EXPANSION_FACTOR = 2

class SelectionMode(Enum):
    """Defines the current user selection mode."""
    TEXT = auto()
    SCREENSHOT = auto()

class PDFViewer(QWidget):
    """
    A widget that displays PDF pages and handles user interaction for both
    text selection and screenshot selection.
    """
    # Emits (selected_text, context_text, fitz.Rect of selection)
    text_query_requested = pyqtSignal(str, str, fitz.Rect)
    # Emits (screenshot_qimage)
    image_query_requested = pyqtSignal(QImage)
    
    open_pdf_requested = pyqtSignal()
    view_changed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document: Optional[PDFDocument] = None
        self.page_number = 0
        self.image: Optional[QImage] = None
        
        # --- Selection related attributes ---
        self.selection_mode: Optional[SelectionMode] = None
        self.selection_start_pos: Optional[QPointF] = None
        self.selection_end_pos: Optional[QPointF] = None
        self.word_boxes: List[Tuple[float, float, float, float, str]] = []
        self.selected_words: List[Tuple[float, float, float, float, str]] = []

        self.current_render_scale_x = 1.0
        self.current_render_scale_y = 1.0
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Default selection mode
        self.current_selection_mode = SelectionMode.TEXT

    def set_selection_mode(self, mode: SelectionMode):
        """Allows the parent window to set the current selection mode."""
        self.current_selection_mode = mode

    def load_pdf(self, file_path: str):
        try:
            if self.document:
                self.document.close()
            self.document = PDFDocument(file_path)
            self.page_number = 0
            self.render_page()
        except PDFLoadError as e:
            self.document = None
            self.image = None
            self.update()
            self.error_occurred.emit(f"Failed to load PDF: {e}")

    def render_page(self):
        self.word_boxes.clear()
        if self.document:
            page = self.document.get_page(self.page_number)
            if not page:
                self.image = None
                self.update()
                return

            # Cache word boxes for text selection
            # PyMuPDF words format: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
            raw_words = page.get_text("words")
            self.word_boxes = [(w[0], w[1], w[2], w[3], w[4]) for w in raw_words]

            # Render page image
            samples, width, height, stride = self.document.render_page(page, dpi=150)
            img_format = QImage.Format.Format_RGB888
            qimage = QImage(samples, width, height, stride, img_format).copy()
            
            if self.width() > 0 and self.height() > 0:
                aspect_ratio = qimage.width() / qimage.height()
                if self.width() / self.height() > aspect_ratio:
                    new_height = self.height()
                    new_width = int(new_height * aspect_ratio)
                else:
                    new_width = self.width()
                    new_height = int(new_width / aspect_ratio)
                
                self.image = qimage.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                page_rect = page.rect
                if page_rect.width > 0 and page_rect.height > 0:
                    self.current_render_scale_x = self.image.width() / page_rect.width
                    self.current_render_scale_y = self.image.height() / page_rect.height
            else:
                self.image = qimage
                dpi_scale = 150 / 72.0
                self.current_render_scale_x = dpi_scale
                self.current_render_scale_y = dpi_scale
            
            self.update()
            self.view_changed.emit()

    def resizeEvent(self, event):
        self.render_page()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        """Handles mouse wheel scrolling to change pages."""
        if not self.document:
            return
        
        angle = event.angleDelta().y()
        num_pages = self.document.page_count
        
        if angle > 0 and self.page_number > 0:
            self.page_number -= 1
            self.render_page()
        elif angle < 0 and self.page_number < num_pages - 1:
            self.page_number += 1
            self.render_page()
            
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.image:
            # Draw hint text if no PDF is loaded
            painter.setPen(QColor("#a0a0a0"))
            font = self.font()
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Double-click to open a PDF file")
            return
            
        x_offset, y_offset = self.get_image_offsets()
        painter.drawImage(int(x_offset), int(y_offset), self.image)
        
        # Draw selection highlights with modern, configurable appearance
        if self.selection_start_pos and self.selection_end_pos:
            selection_config = responsive_calc.get_pdf_selection_config()
            
            if self.selection_mode == SelectionMode.SCREENSHOT:
                # Screenshot selection - distinctive style
                screenshot_config = selection_config["screenshot_selection"]
                
                if screenshot_config["border_color"]:
                    border_color = QColor(*screenshot_config["border_color"])
                    painter.setPen(QPen(border_color, screenshot_config["border_width"]))
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                
                fill_color = QColor(*screenshot_config["fill_color"])
                painter.setBrush(QBrush(fill_color))
                
                selection_rect = QRectF(QPointF(self.selection_start_pos), QPointF(self.selection_end_pos)).normalized()
                if screenshot_config["corner_radius"] > 0:
                    painter.drawRoundedRect(selection_rect, screenshot_config["corner_radius"], screenshot_config["corner_radius"])
                else:
                    painter.drawRect(selection_rect)
                    
            elif self.selection_mode == SelectionMode.TEXT:
                # Text selection - soft, elegant style for readability
                text_config = selection_config["text_selection"]
                
                if text_config["border_color"]:
                    border_color = QColor(*text_config["border_color"])
                    painter.setPen(QPen(border_color, text_config["border_width"]))
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                
                fill_color = QColor(*text_config["fill_color"])
                painter.setBrush(QBrush(fill_color))
                
                # Draw continuous text selection highlights
                self._draw_continuous_text_selection(painter, text_config["corner_radius"])

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        # Determine selection mode: prioritize keyboard modifier, then fallback to current mode
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            self.selection_mode = SelectionMode.SCREENSHOT
        else:
            self.selection_mode = self.current_selection_mode
        
        self.selection_start_pos = event.position()
        self.selection_end_pos = event.position()
        self.selected_words.clear()
        self.update()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton and self.selection_start_pos):
            return

        self.selection_end_pos = event.position()
        if self.selection_mode == SelectionMode.TEXT:
            self._update_selected_words()
        
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.selection_start_pos:
            return

        selection_rect_f = QRectF(QPointF(self.selection_start_pos), QPointF(self.selection_end_pos)).normalized()

        if selection_rect_f.width() > 3 and selection_rect_f.height() > 3:
            if self.selection_mode == SelectionMode.SCREENSHOT:
                self._handle_screenshot_selection(selection_rect_f)
                self._reset_selection()  # Screenshot selection can reset immediately
            elif self.selection_mode == SelectionMode.TEXT:
                self._handle_text_selection()
                # DON'T reset selection here - let it persist until after AI query
        else:
            self._reset_selection()  # Reset if selection is too small

    def _update_selected_words(self):
        """
        Update selected words based on selection rectangle.
        Implements continuous text selection from start point to end point,
        similar to normal PDF readers.
        """
        self.selected_words.clear()
        if not self.word_boxes:
            return
            
        # Convert selection points to PDF coordinates
        start_pdf = self._widget_point_to_pdf_point(self.selection_start_pos)
        end_pdf = self._widget_point_to_pdf_point(self.selection_end_pos)
        
        # Ensure start is before end in reading order
        if start_pdf.y > end_pdf.y or (start_pdf.y == end_pdf.y and start_pdf.x > end_pdf.x):
            start_pdf, end_pdf = end_pdf, start_pdf
        
        # Find words that fall between start and end points in reading order
        selected_words = []
        for word_box in self.word_boxes:
            word_rect = fitz.Rect(word_box[:4])
            word_center = fitz.Point((word_rect.x0 + word_rect.x1) / 2, (word_rect.y0 + word_rect.y1) / 2)
            
            # Check if word is within the selection area using reading order
            if self._is_word_in_selection(word_center, word_rect, start_pdf, end_pdf):
                selected_words.append(word_box)
        
        # Sort selected words by reading order (top to bottom, left to right)
        selected_words.sort(key=lambda w: (w[1], w[0]))  # Sort by y (top), then x (left)
        self.selected_words = selected_words

    def _is_word_in_selection(self, word_center, word_rect, start_point, end_point):
        """
        Determine if a word should be included in the selection based on reading order.
        """
        # For single line selection (same y-coordinate range)
        if abs(start_point.y - end_point.y) < 10:  # Threshold for same line
            return (word_rect.y0 <= max(start_point.y, end_point.y) and 
                    word_rect.y1 >= min(start_point.y, end_point.y) and
                    word_center.x >= min(start_point.x, end_point.x) and 
                    word_center.x <= max(start_point.x, end_point.x))
        
        # For multi-line selection
        # First line: from start_point to end of line
        if word_center.y >= start_point.y - 5 and word_center.y <= start_point.y + 20:
            return word_center.x >= start_point.x
        
        # Last line: from beginning of line to end_point
        if word_center.y >= end_point.y - 5 and word_center.y <= end_point.y + 20:
            return word_center.x <= end_point.x
        
        # Middle lines: entire lines between start and end
        return (word_center.y > start_point.y + 20 and word_center.y < end_point.y - 5)

    def _widget_point_to_pdf_point(self, widget_point):
        """Convert a widget point to PDF coordinates."""
        x_offset, y_offset = self.get_image_offsets()
        return fitz.Point(
            (widget_point.x() - x_offset) / self.current_render_scale_x,
            (widget_point.y() - y_offset) / self.current_render_scale_y
        )

    def _handle_screenshot_selection(self, selection_rect: QRectF):
        if not self.image: return
        x_offset, y_offset = self.get_image_offsets()
        screenshot_rect = selection_rect.translated(-x_offset, -y_offset).toRect()
        screenshot = self.image.copy(screenshot_rect)
        self.image_query_requested.emit(screenshot)

    def _handle_text_selection(self):
        if not self.selected_words:
            return

        selected_text = " ".join(word[4] for word in self.selected_words)
        
        # Calculate the union of all selected word boxes to get a precise bounding rect
        union_rect = fitz.Rect()
        if self.selected_words:
            for word in self.selected_words:
                union_rect += fitz.Rect(word[:4])
            
        # For context, get all text on the page for simplicity
        page = self.document.get_page(self.page_number)
        context_text = page.get_text("text")

        if selected_text.strip():
            self.text_query_requested.emit(selected_text, context_text, union_rect)
            
    def _reset_selection(self):
        self.selection_start_pos = None
        self.selection_end_pos = None
        self.selection_mode = None
        self.selected_words.clear()
        self.update()

    def _draw_continuous_text_selection(self, painter, corner_radius=3):
        """
        Draw continuous text selection highlights that look like modern web browser text selection.
        Uses configurable rounded rectangles for a more elegant appearance.
        
        Args:
            painter: QPainter instance for drawing
            corner_radius: Radius for rounded corners
        """
        if not self.selected_words:
            return
        
        # Group words by lines for better continuous appearance
        lines = {}
        for word in self.selected_words:
            word_rect = fitz.Rect(word[:4])
            line_y = round(word_rect.y0 / 5) * 5  # Group by approximate line position
            if line_y not in lines:
                lines[line_y] = []
            lines[line_y].append(word_rect)
        
        # Draw selection for each line with configurable rounded corners
        for line_y in sorted(lines.keys()):
            line_words = lines[line_y]
            if not line_words:
                continue
                
            # Find the bounding rectangle for this line
            min_x = min(rect.x0 for rect in line_words)
            max_x = max(rect.x1 for rect in line_words)
            min_y = min(rect.y0 for rect in line_words)
            max_y = max(rect.y1 for rect in line_words)
            
            # Convert to widget coordinates and draw
            line_rect_pdf = fitz.Rect(min_x, min_y, max_x, max_y)
            line_rect_widget = self._pdf_to_widget_rect(line_rect_pdf)
            
            # Add gentle padding for softer appearance
            line_rect_widget.adjust(-1, -1, 1, 1)
            
            # Draw with configurable corner radius
            if corner_radius > 0:
                painter.drawRoundedRect(line_rect_widget, corner_radius, corner_radius)
            else:
                painter.drawRect(line_rect_widget)

    def _pdf_to_widget_rect(self, pdf_rect: fitz.Rect) -> QRectF:
        x_offset, y_offset = self.get_image_offsets()
        return QRectF(
            pdf_rect.x0 * self.current_render_scale_x + x_offset,
            pdf_rect.y0 * self.current_render_scale_y + y_offset,
            pdf_rect.width * self.current_render_scale_x,
            pdf_rect.height * self.current_render_scale_y
        )

    def _widget_to_pdf_rect(self, widget_rect: QRectF) -> fitz.Rect:
        x_offset, y_offset = self.get_image_offsets()
        return fitz.Rect(
            (widget_rect.left() - x_offset) / self.current_render_scale_x,
            (widget_rect.top() - y_offset) / self.current_render_scale_y,
            (widget_rect.right() - x_offset) / self.current_render_scale_x,
            (widget_rect.bottom() - y_offset) / self.current_render_scale_y,
        )

    # --- Helper methods for AnnotationManager ---
    # These methods are deprecated or need updates after the refactoring of selection
    def get_current_page_number(self) -> Optional[int]:
        return self.page_number if self.document else None

    def get_current_render_scale(self) -> Tuple[float, float]:
        return self.current_render_scale_x, self.current_render_scale_y

    def get_image_offsets(self) -> Tuple[float, float]:
        if not self.image:
            return 0, 0
        x_offset = (self.width() - self.image.width()) / 2
        y_offset = (self.height() - self.image.height()) / 2
        return x_offset, y_offset

    def get_widget_rect_from_pdf_coords(self, pdf_coords: fitz.Rect) -> QRectF:
        """Converts PDF coordinates to a QRectF in the widget's coordinate system."""
        if not self.document:
            return QRectF()
        return self._pdf_to_widget_rect(pdf_coords)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open a file if no document is loaded."""
        if not self.document and event.button() == Qt.MouseButton.LeftButton:
            self.open_pdf_requested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def clear_selection(self):
        """Public method to clear selection state after AI query is complete."""
        self._reset_selection()
