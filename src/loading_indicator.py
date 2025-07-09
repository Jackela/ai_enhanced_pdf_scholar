"""
LoadingIndicator widget for displaying AI query progress.
Shows a rotating spinner with a semi-transparent background.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
import math


class LoadingIndicator(QWidget):
    """
    A rotating loading indicator widget that follows the mouse cursor.
    Displays a spinner with "Querying AI..." text.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # As a child widget, it no longer needs top-level window flags.
        # It will be drawn on top of its parent (the main window).
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Animation properties
        self.angle = 0
        self._opacity = 0.9
        
        # Setup rotation timer
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self._rotate)
        self.rotation_timer.setInterval(50)  # 20 FPS for smooth rotation
        
        # Setup fade-in animation
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Widget styling
        self.setFixedSize(120, 60)
        self.spinner_radius = 15
        self.dot_count = 8
        self.dot_radius = 2
        
        self.hide()

    @pyqtProperty(float)
    def rotation(self):
        return self.angle

    @rotation.setter
    def rotation(self, value):
        self.angle = value
        self.update()

    def _rotate(self):
        """Update rotation angle for spinning animation."""
        self.angle = (self.angle + 8) % 360
        self.update()

    def show_at_position(self, global_pos):
        """
        Show the loading indicator at a position relative to its parent.
        
        @param global_pos: QPoint representing the global screen position
        """
        # Convert global position to parent's local coordinates
        if self.parent():
            local_pos = self.parent().mapFromGlobal(global_pos)
        else:
            local_pos = global_pos
            
        # Position the indicator near the cursor, but avoid edges
        x = local_pos.x() - self.width() // 2
        y = local_pos.y() - self.height() - 10  # 10px above cursor
        
        # Ensure it stays within parent's bounds
        if self.parent():
            parent_rect = self.parent().rect()
            x = max(0, min(x, parent_rect.width() - self.width()))
            y = max(0, min(y, parent_rect.height() - self.height()))
        
        self.move(x, y)
        
        # Show first, then animate
        self.show()
        self.raise_()  # Bring to front within the parent
        
        # Fade in animation
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(0.9)
        self.fade_animation.start()
        
        # Start rotation
        self.rotation_timer.start()

    def hide_with_fade(self):
        """Hide the indicator with a fade-out animation."""
        self.rotation_timer.stop()
        
        # Fade out animation
        self.fade_animation.setStartValue(0.9)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self.hide)
        self.fade_animation.start()

    def paintEvent(self, event):
        """Custom paint event to draw the spinning indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))  # Semi-transparent black
        
        # Center coordinates
        center_x = self.width() // 2
        center_y = self.height() // 2 - 8  # Offset up to make room for text
        
        # Draw spinning dots
        for i in range(self.dot_count):
            angle = (i * 360 / self.dot_count + self.angle) * math.pi / 180
            x = center_x + self.spinner_radius * math.cos(angle)
            y = center_y + self.spinner_radius * math.sin(angle)
            
            # Fade effect for dots (leading dots are brighter)
            alpha = int(255 * (1 - i / self.dot_count))
            color = QColor(255, 255, 255, alpha)
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color))
            painter.drawEllipse(int(x - self.dot_radius), int(y - self.dot_radius), 
                              self.dot_radius * 2, self.dot_radius * 2)
        
        # Draw text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Arial", 9))
        text_rect = self.rect()
        text_rect.setTop(center_y + self.spinner_radius + 8)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "Querying AI...")

    def focusOutEvent(self, event):
        """Override to prevent hiding when losing focus."""
        # This is likely no longer necessary as a child widget, but we'll keep it.
        pass
        
    def closeEvent(self, event):
        """Clean up when widget is closed."""
        self.rotation_timer.stop()
        super().closeEvent(event) 