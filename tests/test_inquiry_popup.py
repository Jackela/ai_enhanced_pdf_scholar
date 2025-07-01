import pytest
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import QPushButton

from src.inquiry_popup import InquiryPopup

# Helper class to capture signals and their arguments
class SignalListener(QObject):
    def __init__(self, signal: pyqtSignal):
        super().__init__()
        self.signal = signal
        self.received = []
        self.signal.connect(self.on_signal)

    def on_signal(self, *args):
        self.received.append(args)

    @property
    def call_count(self):
        return len(self.received)

    @property
    def last_call_args(self):
        return self.received[-1] if self.received else None

def test_inquiry_popup_emits_signal_with_explanation(qtbot):
    """
    Tests that the popup emits the correct signal for a default explanation
    when the input is empty.
    """
    selected_text = "highlighted text"
    context_text = "Some context for the text."
    
    popup = InquiryPopup(selected_text=selected_text, context_text=context_text)
    qtbot.addWidget(popup)
    
    listener = SignalListener(popup.annotation_requested)
    
    # Find the "Ask AI" button and click it
    ask_button = popup.findChild(QPushButton)
    qtbot.mouseClick(ask_button, Qt.MouseButton.LeftButton)
    
    assert listener.call_count == 1
    prompt, original_text = listener.last_call_args
    
    # Check that the generated prompt is correct
    assert "Please provide a detailed explanation" in prompt
    assert selected_text in prompt
    assert context_text in prompt
    assert original_text == selected_text

def test_inquiry_popup_emits_signal_with_question(qtbot):
    """
    Tests that the popup emits the correct signal with a custom user question.
    """
    selected_text = "highlighted text"
    context_text = "Some context for the text."
    user_question = "What does this mean?"
    
    popup = InquiryPopup(selected_text=selected_text, context_text=context_text)
    qtbot.addWidget(popup)
    
    # Simulate user input into the QLineEdit
    popup.question_input.setText(user_question)
    
    listener = SignalListener(popup.annotation_requested)
    
    ask_button = popup.findChild(QPushButton)
    qtbot.mouseClick(ask_button, Qt.MouseButton.LeftButton)
    
    assert listener.call_count == 1
    prompt, original_text = listener.last_call_args

    # Check that the generated prompt contains the user's question
    assert user_question in prompt
    assert selected_text in prompt
    assert context_text in prompt
    assert original_text == selected_text

def test_popup_closes_on_button_click(qtbot):
    """
    Tests that the popup closes itself after the button is clicked.
    """
    popup = InquiryPopup(selected_text="text", context_text="context")
    qtbot.addWidget(popup)
    popup.show()
    assert popup.isVisible()

    ask_button = popup.findChild(QPushButton)
    qtbot.mouseClick(ask_button, Qt.MouseButton.LeftButton)
    
    # The popup should close after emitting the signal
    assert not popup.isVisible() 