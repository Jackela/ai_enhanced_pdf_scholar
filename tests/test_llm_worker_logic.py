"""
Unit tests for LLMWorker in src/llm_worker.py.
Covers emitting result_ready on successful query and error_occurred on exception.
"""

import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QCoreApplication

from src.llm_worker import LLMWorker


class DummyServiceSuccess:
    def query_llm(self, prompt):
        return f"echo: {prompt}"

class DummyServiceError:
    def query_llm(self, prompt):
        raise RuntimeError("failure occurred")

@pytest.fixture(autouse=True)
def qapp(request):
    # Ensure a QCoreApplication exists for signal emission
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


def test_run_emits_result_ready(qtbot):
    service = DummyServiceSuccess()
    worker = LLMWorker(service, prompt="hello world")
    # Capture the signal
    with qtbot.waitSignal(worker.result_ready, timeout=1000) as blocker:
        worker.run()
    # Verify the emitted argument
    assert blocker.args == ["echo: hello world"]


def test_run_emits_error_occurred(qtbot, caplog):
    service = DummyServiceError()
    worker = LLMWorker(service, prompt="test err")
    caplog.set_level('INFO')
    # Capture the error signal
    with qtbot.waitSignal(worker.error_occurred, timeout=1000) as blocker:
        worker.run()
    # The error message should include exception type and message
    emitted = blocker.args[0]
    assert emitted.startswith("RuntimeError: failure occurred") 