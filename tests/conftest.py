import pytest
import logging
import sys
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QLabel
from PyQt6.QtCore import QSettings, Qt
import fitz
import gc
import os
import weakref
from contextlib import contextmanager

sys.path.append('E:/Code/ai_enhanced_pdf_scholar')

# Configure pytest-qt for headless testing
pytest_plugins = ['pytestqt']

# Suppress PyQt6 debug messages during testing
logging.getLogger('PyQt6').setLevel(logging.WARNING)

@pytest.fixture(scope="session")
def qapp():
    """
    Create a QApplication instance for the entire test session.
    This ensures PyQt6 widgets can be tested in a headless environment.
    """
    if QApplication.instance() is None:
        app = QApplication([])
        yield app
        app.quit()
    else:
        yield QApplication.instance()

@pytest.fixture
def mock_pdf_viewer():
    """Create a mock PDF viewer for testing."""
    viewer = Mock()
    viewer.get_current_page_number.return_value = 0
    viewer.get_widget_rect_from_pdf_coords.return_value = Mock()
    viewer.width.return_value = 800
    viewer.height.return_value = 600
    viewer.image = Mock()  # Simulate loaded PDF
    return viewer

@pytest.fixture
def mock_annotation_layout():
    """Create a mock QVBoxLayout for annotations panel."""
    layout = Mock(spec=QVBoxLayout)
    layout.addWidget = Mock()
    layout.removeWidget = Mock()
    return layout

@pytest.fixture
def mock_empty_message():
    """Create a mock empty message widget."""
    widget = Mock(spec=QLabel)
    widget.hide = Mock()
    widget.show = Mock()
    widget.isVisible = Mock(return_value=True)
    return widget

@pytest.fixture
def sample_pdf_rect():
    """Create a sample PDF rectangle for testing."""
    return fitz.Rect(100, 100, 200, 150)

@pytest.fixture
def sample_ai_response():
    """Create a sample AI response text for testing."""
    return "This is a sample AI response about the selected text content."

@pytest.fixture
def sample_selected_text():
    """Create a sample selected text for testing."""
    return "This is the text that was selected from the PDF document."

@pytest.fixture
def mock_settings():
    """Create a mock QSettings object for testing."""
    settings = Mock(spec=QSettings)
    settings.value = Mock(return_value="test_value")
    settings.setValue = Mock()
    settings.organizationName = Mock(return_value="TestOrg")
    settings.applicationName = Mock(return_value="TestApp")
    return settings

@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    service = Mock()
    service.is_configured.return_value = True
    service.refresh_config = Mock()
    return service

# Patch configuration for testing
@pytest.fixture(autouse=True)
def patch_config():
    """Automatically patch config values for all tests."""
    with patch('config.APP_NAME', 'TestAIEnhancedPDFScholar'):
        yield

# Pytest markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "gui: mark test as GUI test requiring display")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")

# Auto-use fixture to ensure clean state between tests
@pytest.fixture(autouse=True)
def clean_state():
    """Ensure clean state between tests."""
    yield
    # Any cleanup code would go here

@pytest.fixture
def mock_annotation():
    """Create a mock annotation for testing."""
    annotation = Mock()
    annotation.expanded = False
    annotation.page_number = 0
    annotation.pdf_coords = fitz.Rect(0, 0, 100, 100)
    annotation.text = "Test annotation text"
    annotation.width.return_value = 200
    annotation.height.return_value = 150
    annotation.deleteLater = Mock()
    annotation.hide = Mock()
    annotation.show = Mock()
    annotation.move = Mock()
    annotation.raise_ = Mock()
    annotation.setVisible = Mock()
    annotation.update = Mock()
    annotation.repaint = Mock()
    
    # Mock signals
    annotation.delete_requested = Mock()
    annotation.delete_requested.connect = Mock()
    annotation.expansion_changed = Mock()
    annotation.expansion_changed.connect = Mock()
    
    return annotation

# --- Comprehensive Resource Manager ---
class ComprehensiveResourceManager:
    """
    Manages the lifecycle of test resources, especially those from C++-backed
    libraries like PyQt and PyMuPDF, to ensure a stable cleanup order and
    prevent segmentation faults.
    
    The key is to clean up resources in a specific order:
    1. PyMuPDF documents ('pdf')
    2. Other resources ('other')
    3. PyQt widgets ('qt')
    """
    def __init__(self, qapp_instance=None):
        self.qapp = qapp_instance
        self.resources = {'pdf': [], 'qt': [], 'other': []}
        # CRITICAL: The cleanup order is essential to prevent crashes.
        self._cleanup_order = ['pdf', 'other', 'qt']

    def register(self, obj, category='other'):
        """
        Registers a resource to be managed and cleaned up at the end of a test.
        
        @param obj: The object to manage (e.g., a widget, a document).
        @param category: The category of the resource ('pdf', 'qt', 'other').
        @returns: The registered object.
        """
        # Use weak references for objects that have a __del__ method to avoid circular refs
        if hasattr(obj, '__del__'):
            self.resources[category].append(weakref.ref(obj))
        else:
            self.resources[category].append(obj)
        return obj

    def cleanup(self):
        """
        Cleans up all registered resources in the predefined order.
        """
        for category in self._cleanup_order:
            self._cleanup_category(category)
        
        # Force garbage collection multiple times to be thorough
        for _ in range(3):
            gc.collect()

    def _cleanup_category(self, category):
        """Helper to clean up all resources within a specific category."""
        refs = self.resources[category]
        
        # For Qt objects, use the safe deleteLater method
        if category == 'qt':
            for ref in refs:
                obj = ref() if isinstance(ref, weakref.ref) else ref
                if obj and hasattr(obj, 'deleteLater'):
                    obj.deleteLater()
            # CRITICAL: Process events to ensure deleteLater() is executed
            if self.qapp:
                self.qapp.processEvents()
        else: # For other objects like fitz documents
            for ref in refs:
                try:
                    obj = ref() if isinstance(ref, weakref.ref) else ref
                    if obj and hasattr(obj, 'close'):
                        obj.close()
                except Exception as e:
                    # During cleanup, we log errors but do not raise them,
                    # as the primary goal is to prevent the test runner from crashing.
                    print(f"Cleanup warning for '{category}' resource: {e}", file=sys.stderr)
        
        self.resources[category].clear()
        gc.collect()

@pytest.fixture(scope="function")
def resource_manager(qapp):
    """
    Pytest fixture that provides a configured ComprehensiveResourceManager.
    """
    manager = ComprehensiveResourceManager(qapp_instance=qapp)
    yield manager
    
    # Final safety net to ensure cleanup doesn't crash the test run
    try:
        manager.cleanup()
    except Exception as e:
        print(f"Final resource manager cleanup warning: {e}", file=sys.stderr)
