from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent

class InquiryPopup(QDialog):
    """
    A popup dialog that allows the user to ask a question about selected text.
    Its sole responsibility is to gather user input and emit a signal.
    """
    # Emits the final prompt and the original selected text
    annotation_requested = pyqtSignal(str, str) 

    def __init__(self, parent=None, selected_text="", context_text=""):
        """
        @param {QWidget} parent - The parent widget.
        @param {string} selected_text - The text selected by the user.
        @param {string} context_text - The surrounding context text from the PDF.
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # Enable input method support for international text input
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        
        self.selected_text = selected_text
        self.context_text = context_text
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.question_input = QLineEdit(self)
        self.question_input.setPlaceholderText("Ask a question or leave blank for explanation.")
        
        # Enable input method for text input widget
        self.question_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        # Set appropriate input method hints for international text
        self.question_input.setInputMethodHints(Qt.InputMethodHint.ImhNone)
        
        layout.addWidget(self.question_input)

        ask_button = QPushButton("Ask AI", self)
        ask_button.clicked.connect(self._create_prompt_and_emit)
        layout.addWidget(ask_button)
        
        self.question_input.setFocus()
        self.setFixedSize(300, 100)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events, including Enter key and Escape key."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._create_prompt_and_emit()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _create_prompt_and_emit(self):
        """
        Constructs the appropriate prompt based on user input (or a default)
        and emits the annotation_requested signal.
        """
        user_question = self.question_input.text().strip()
        
        if user_question:
            prompt = f"""Given the following context from a PDF document:

---CONTEXT---
{self.context_text}
---END CONTEXT---

The user highlighted this specific text:

---HIGHLIGHTED TEXT---
{self.selected_text}
---END HIGHLIGHTED TEXT---

Now, please answer the user's question: {user_question}"""
        else:
            prompt = f"""Given the following context from a PDF document:

---CONTEXT---
{self.context_text}
---END CONTEXT---

The user highlighted this specific text:

---HIGHLIGHTED TEXT---
{self.selected_text}
---END HIGHLIGHTED TEXT---

Please provide a detailed explanation of the highlighted text in the context provided. Explain its meaning, background, and significance.
"""
        
        self.annotation_requested.emit(prompt, self.selected_text)
        self.close()
