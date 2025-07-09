import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QObject, pyqtSignal

from src.llm_worker import LLMWorker
from src.llm_service import LLMService, LLMAPIError

@pytest.fixture
def mock_llm_service():
    """Fixture to create a mock LLMService."""
    return MagicMock(spec=LLMService)

def test_llm_worker_happy_path_with_mock_output(qtbot, mock_llm_service):
    """
    Tests the LLMWorker in a simulated threaded environment using qtbot,
    simulating a successful LLM response with mocked output.
    """
    expected_response = "This is a mocked happy path response from the LLM."
    mock_llm_service.query_llm.return_value = expected_response
    
    worker = LLMWorker(llm_service=mock_llm_service, prompt="Simulated happy path prompt")
    
    # Use qtbot.wait_for_signals to wait for the signals to be emitted
    with qtbot.wait_signals([worker.result_ready], timeout=5000) as blocker:
        worker.start() # Start the thread
    
    assert blocker.signal_triggered
    
    # Assert the arguments received by the signal
    assert blocker.args[0] == expected_response
    
    # Assert that query_llm was called exactly once with the correct prompt
    mock_llm_service.query_llm.assert_called_once_with("Simulated happy path prompt")
