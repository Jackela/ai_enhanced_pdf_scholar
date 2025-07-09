import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QObject, pyqtSignal

from src.llm_worker import LLMWorker
from src.llm_service import LLMService, LLMAPIError

# No longer need qapp fixture for this direct-call approach
# pytestmark = pytest.mark.usefixtures("qapp")

class SignalListener(QObject):
    """Helper class to capture signals and their arguments."""
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

@pytest.fixture
def mock_llm_service():
    """Fixture to create a mock LLMService."""
    return MagicMock(spec=LLMService)

def test_llm_worker_success_direct_call(mock_llm_service):
    """
    Tests the worker's logic by calling run() directly.
    Verifies that result_ready is emitted on a successful query.
    """
    mock_llm_service.query_llm.return_value = "AI response"
    
    # We pass None for parent to avoid Qt parenting issues in tests
    worker = LLMWorker(llm_service=mock_llm_service, prompt="A test prompt", parent=None)
    
    result_listener = SignalListener(worker.result_ready)
    error_listener = SignalListener(worker.error_occurred)
    
    # Directly invoke the run method instead of starting a new thread
    worker.run()
    
    assert result_listener.call_count == 1
    assert result_listener.last_call_args[0] == "AI response"
    assert error_listener.call_count == 0
    mock_llm_service.query_llm.assert_called_once_with("A test prompt")

def test_llm_worker_failure_direct_call(mock_llm_service):
    """
    Tests the worker's logic by calling run() directly.
    Verifies that error_occurred is emitted when the service raises an exception.
    """
    error_message = "API key invalid"
    mock_llm_service.query_llm.side_effect = LLMAPIError(error_message)
    
    worker = LLMWorker(llm_service=mock_llm_service, prompt="Another prompt", parent=None)
    
    result_listener = SignalListener(worker.result_ready)
    error_listener = SignalListener(worker.error_occurred)
    
    # Directly invoke the run method
    worker.run()

    assert result_listener.call_count == 0
    assert error_listener.call_count == 1
    # Check for the new formatted error message
    expected_error_str = f"LLMAPIError: {error_message}"
    assert error_listener.last_call_args[0] == expected_error_str
    mock_llm_service.query_llm.assert_called_once_with("Another prompt") 