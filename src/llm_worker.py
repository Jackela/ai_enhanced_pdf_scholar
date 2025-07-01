from PyQt6.QtCore import QThread, pyqtSignal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm_service import LLMService, LLMServiceError

class LLMWorker(QThread):
    """
    {
        "name": "LLMWorker",
        "version": "1.1.0",
        "description": "A QThread subclass to perform LLM queries asynchronously.",
        "dependencies": ["LLMService"]
    }
    Executes a query on an LLMService in a separate thread to prevent the UI
    from freezing. It handles exceptions from the service and emits the
    result or an error message via signals.
    """
    result_ready = pyqtSignal(str)  # Emits the AI response text
    error_occurred = pyqtSignal(str) # Emits an error message string

    def __init__(self, llm_service: 'LLMService', prompt: str, parent=None):
        """
        @param {LLMService} llm_service - An instance of a class that implements the LLMService interface.
        @param {string} prompt - The prompt to send to the LLM.
        @param {QObject} parent - The parent QObject.
        """
        super().__init__(parent)
        self.llm_service = llm_service
        self.prompt = prompt

    def run(self):
        """
        Executes the LLM query in the worker thread and emits the appropriate signal.
        """
        try:
            # The LLMService is expected to raise LLMServiceError on failure
            response = self.llm_service.query_llm(self.prompt)
            self.result_ready.emit(response)
        except Exception as e:
            # This will catch LLMServiceError as well as any other unexpected errors
            # Format the error to include the exception type for better handling upstream.
            error_message = f"{type(e).__name__}: {e}"
            self.error_occurred.emit(error_message)
