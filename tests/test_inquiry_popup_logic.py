"""
Unit tests for InquiryPopup in src/inquiry_popup.py.
Covers signal emission on custom question, default explanation, and keyPressEvent handling for Enter and Escape.
"""

import pytest
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLineEdit

from src.inquiry_popup import InquiryPopup

@pytest.fixture
def popup(qtbot):
    # Create popup with sample selected and context text
    selected = "SELECTED TEXT"
    context = "CONTEXT TEXT"
    dlg = InquiryPopup(parent=None, selected_text=selected, context_text=context)
    qtbot.addWidget(dlg)
    return dlg


def test_emit_custom_question(popup, qtbot):
    # Set a custom question and emit prompt synchronously
    popup.question_input.setText("What is this?")
    captured = []
    popup.annotation_requested.connect(lambda prompt, sel: captured.append((prompt, sel)))
    popup._create_prompt_and_emit()
    assert len(captured) == 1
    prompt, sel = captured[0]

    assert sel == "SELECTED TEXT"
    # Prompt should contain user question and context sections
    assert "Now, please answer the user's question: What is this?" in prompt
    assert "---CONTEXT---\nCONTEXT TEXT\n---END CONTEXT---" in prompt
    assert "---HIGHLIGHTED TEXT---\nSELECTED TEXT\n---END HIGHLIGHTED TEXT---" in prompt


def test_emit_default_explanation(popup):
    # Leave question blank for default explanation
    popup.question_input.setText("")
    captured = []
    popup.annotation_requested.connect(lambda prompt, sel: captured.append((prompt, sel)))
    popup._create_prompt_and_emit()
    assert len(captured) == 1
    prompt, sel = captured[0]

    assert sel == "SELECTED TEXT"
    # Should ask for detailed explanation
    assert "Please provide a detailed explanation of the highlighted text" in prompt


def test_keypress_enter_triggers(popup):
    # Simulate pressing Enter key
    popup.question_input.setText("KeyTest")
    captured = []
    popup.annotation_requested.connect(lambda prompt, sel: captured.append((prompt, sel)))
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    popup.keyPressEvent(event)
    assert len(captured) == 1
    prompt, sel = captured[0]
    assert "KeyTest" in prompt


def test_keypress_escape_closes(popup, qtbot):
    # Prevent widget deletion on close so teardown can close safely
    popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    # Show popup
    popup.show()
    assert popup.isVisible() is True
    # Simulate Escape key
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    popup.keyPressEvent(event)
    # After Escape, dialog should close
    assert popup.isVisible() is False 