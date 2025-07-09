"""
Unit tests for AnnotationManager logic.
Tests add_annotation (first hide empty widget, skip duplicates), remove_annotation, clear_all_annotations,
handle_highlight_request, handle_viewer_changed, and get_annotation_count.
"""

import pytest
from unittest.mock import MagicMock, patch
import fitz

from src.annotation_manager import AnnotationManager


class DummyLayout:
    """A dummy layout to collect added widgets"""
    def __init__(self):
        self.widgets = []
    def addWidget(self, widget):
        self.widgets.append(widget)
    def removeWidget(self, widget):
        self.widgets.remove(widget)
    def count(self):
        return len(self.widgets)


class DummyWidget:
    """A dummy widget to track visibility for empty_message_widget"""
    def __init__(self):
        self._visible = True
    def hide(self):
        self._visible = False
    def show(self):
        self._visible = True


class SignalStub:
    """Stub for Qt signals; allows connect and emit."""
    def __init__(self):
        self._slots = []
    def connect(self, slot):
        self._slots.append(slot)
    def emit(self, *args, **kwargs):
        for slot in self._slots:
            slot(*args, **kwargs)


class DummyAnnotation:
    """A stub for PanelAnnotation with required interface."""
    def __init__(self, *, text, page_number, pdf_coords, selected_text):
        self.text = text
        self.page_number = page_number
        self.pdf_coords = pdf_coords
        self.selected_text = selected_text
        self.delete_requested = SignalStub()
        self.highlight_requested = SignalStub()
        self._deleted = False
    def deleteLater(self):
        self._deleted = True


@pytest.fixture
def manager_fixture():
    viewer = MagicMock()
    layout = DummyLayout()
    empty_widget = DummyWidget()
    manager = AnnotationManager(viewer, layout, empty_widget)
    return manager, layout, empty_widget


def test_add_annotation_hides_empty_and_stores(manager_fixture):
    manager, layout, empty_widget = manager_fixture
    coords = fitz.Rect(0, 0, 10, 10)
    with patch('src.annotation_manager.PanelAnnotation', DummyAnnotation):
        manager.add_annotation(page_number=1, pdf_coords=coords, text="hello", selected_text="sel")

    # Empty widget hidden and annotation stored
    assert not empty_widget._visible
    assert manager.get_annotation_count() == 1
    assert layout.count() == 1


def test_add_duplicate_annotation_skipped(manager_fixture):
    manager, layout, empty_widget = manager_fixture
    coords = fitz.Rect(0, 0, 10, 10)
    with patch('src.annotation_manager.PanelAnnotation', DummyAnnotation):
        # Add first
        manager.add_annotation(1, coords, "dup", "")
        # Attempt duplicate
        manager.add_annotation(1, coords, "dup", "")

    # Only one annotation should exist
    assert manager.get_annotation_count() == 1
    assert layout.count() == 1


def test_remove_annotation_shows_empty(manager_fixture):
    manager, layout, empty_widget = manager_fixture
    coords = fitz.Rect(0, 0, 10, 10)
    with patch('src.annotation_manager.PanelAnnotation', DummyAnnotation):
        manager.add_annotation(1, coords, "text1", "")
        ann = manager.annotations[0]
        manager.remove_annotation(ann)

    # Annotation removed and empty widget shown
    assert manager.get_annotation_count() == 0
    assert layout.count() == 0
    assert empty_widget._visible
    # Underlying widget marked deleted
    assert ann._deleted


def test_clear_all_annotations(manager_fixture):
    manager, layout, empty_widget = manager_fixture
    coords = fitz.Rect(0, 0, 10, 10)
    with patch('src.annotation_manager.PanelAnnotation', DummyAnnotation):
        # Add multiple annotations
        manager.add_annotation(0, coords, "a", "")
        manager.add_annotation(1, coords, "b", "")
        manager.clear_all_annotations()

    assert manager.get_annotation_count() == 0
    assert layout.count() == 0
    assert empty_widget._visible


def test_handle_highlight_request_logs(caplog, manager_fixture):
    manager, _, _ = manager_fixture
    # Create dummy annotation with page_number
    dummy = DummyAnnotation(text="x", page_number=5, pdf_coords=fitz.Rect(0,0,1,1), selected_text="")
    caplog.set_level('INFO')
    manager._handle_highlight_request(dummy)
    assert f"Highlight requested for annotation on page {dummy.page_number}" in caplog.text


def test_handle_viewer_changed_logs(caplog, manager_fixture):
    manager, _, _ = manager_fixture
    caplog.set_level('INFO')
    manager.handle_viewer_changed()
    assert "Viewer changed - panel annotations remain visible" in caplog.text


def test_get_annotation_count(manager_fixture):
    manager, _, _ = manager_fixture
    assert manager.get_annotation_count() == 0
    # Directly append dummy
    manager.annotations.append(DummyAnnotation(text="x", page_number=0, pdf_coords=fitz.Rect(0,0,1,1), selected_text=""))
    assert manager.get_annotation_count() == 1 