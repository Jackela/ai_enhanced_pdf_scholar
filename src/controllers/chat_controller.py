"""
Chat Controller - UI-Service Decoupling for Chat Functionality

This controller acts as the intermediary between chat UI components and ChatService,
ensuring complete separation of concerns and enabling reactive UI updates.
"""

import logging
from typing import Optional, Callable, Any
import asyncio

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

from src.core.state_manager import StateManager
from src.core.config_manager import ConfigManager
from src.services.chat_service import ChatService, ChatMessage, MessageSender
from src.llm_service import LLMServiceError
from src.rag_service import RAGServiceError

logger = logging.getLogger(__name__)


class ChatController(QObject):
    """
    {
        "name": "ChatController",
        "version": "1.0.0", 
        "description": "Controller for chat UI-Service coordination with reactive state management.",
        "dependencies": ["ChatService", "StateManager", "ConfigManager"],
        "interface": {
            "inputs": ["ui_events", "user_messages", "rag_mode_changes"],
            "outputs": "Coordinated UI updates and service calls"
        }
    }
    
    Controller that decouples chat UI components from ChatService.
    Handles event coordination, async message processing, and reactive state updates.
    """
    
    # UI Update Signals
    message_received = pyqtSignal(str, str, str)  # content, sender, timestamp
    ai_response_started = pyqtSignal()
    ai_response_completed = pyqtSignal(str)  # ai_response_content
    ai_response_error = pyqtSignal(str)  # error_message
    conversation_cleared = pyqtSignal()
    rag_mode_changed = pyqtSignal(bool)  # rag_enabled
    input_enabled_changed = pyqtSignal(bool)  # enabled
    
    def __init__(self, 
                 chat_service: ChatService,
                 state_manager: StateManager,
                 config_manager: ConfigManager):
        """
        Initialize chat controller with service dependencies.
        
        Args:
            chat_service: Business logic service for chat
            state_manager: Global state management
            config_manager: Configuration management
        """
        super().__init__()
        
        self._chat_service = chat_service
        self._state = state_manager
        self._config = config_manager
        
        # State tracking
        self._processing_message = False
        self._current_task: Optional[asyncio.Task] = None
        
        # Setup state observers
        self._setup_state_observers()
        
        # Setup async task management
        self._setup_async_handling()
        
        logger.info("ChatController initialized with reactive state management")
    
    def _setup_state_observers(self) -> None:
        """Setup observers for state changes that affect UI."""
        # RAG mode changes
        self._state.subscribe('app.rag_mode', self._on_rag_mode_changed)
        
        # AI responding state changes
        self._state.subscribe('chat.is_ai_responding', self._on_ai_responding_changed)
        
        # Message list changes
        self._state.subscribe('chat.messages', self._on_messages_changed)
    
    def _setup_async_handling(self) -> None:
        """Setup async task management for Qt integration."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_async_tasks)
        self._timer.start(100)  # Check every 100ms
    
    def _process_async_tasks(self) -> None:
        """Process pending async tasks in Qt event loop."""
        if self._current_task and self._current_task.done():
            try:
                result = self._current_task.result()
                # Task completed successfully, result handled in task callback
            except Exception as e:
                logger.error(f"Async task failed: {e}")
                self.ai_response_error.emit(str(e))
            finally:
                self._current_task = None
                self._processing_message = False
    
    # Public API for UI Components
    
    def handle_user_message(self, message: str) -> None:
        """
        Handle user message from UI component.
        
        Args:
            message: User's message text
        """
        if self._processing_message:
            logger.warning("Already processing a message, ignoring new request")
            return
        
        if not message or not message.strip():
            logger.warning("Empty message ignored")
            return
        
        logger.info(f"Processing user message: {len(message)} characters")
        
        # Update processing state
        self._processing_message = True
        self._state.set_state('chat.is_ai_responding', True)
        
        # Start async processing
        self._current_task = asyncio.create_task(self._process_message_async(message))
    
    def handle_rag_mode_toggle(self, enabled: bool) -> None:
        """
        Handle RAG mode toggle from UI.
        
        Args:
            enabled: Whether RAG mode is enabled
        """
        logger.info(f"RAG mode toggled: {enabled}")
        self._state.set_state('app.rag_mode', enabled)
    
    def handle_clear_conversation(self) -> None:
        """Handle clear conversation request from UI."""
        logger.info("Clearing conversation")
        self._chat_service.clear_conversation()
        self.conversation_cleared.emit()
    
    def handle_export_conversation(self, format: str = 'json') -> str:
        """
        Handle conversation export request.
        
        Args:
            format: Export format ('json', 'markdown', 'txt')
            
        Returns:
            Exported conversation data
        """
        logger.info(f"Exporting conversation in {format} format")
        return self._chat_service.export_conversation(format)
    
    # Async Processing
    
    async def _process_message_async(self, message: str) -> None:
        """
        Process user message asynchronously.
        
        Args:
            message: User message to process
        """
        try:
            # Get current RAG mode
            use_rag = self._state.get_state('app.rag_mode', False)
            
            # Send message to service
            ai_message = await self._chat_service.send_message(message, use_rag)
            
            # Emit success signal on main thread
            QApplication.instance().postEvent(
                self,
                lambda: self.ai_response_completed.emit(ai_message.content)
            )
            
        except (LLMServiceError, RAGServiceError) as e:
            logger.error(f"Service error processing message: {e}")
            QApplication.instance().postEvent(
                self,
                lambda: self.ai_response_error.emit(str(e))
            )
            
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            QApplication.instance().postEvent(
                self,
                lambda: self.ai_response_error.emit(f"Unexpected error: {e}")
            )
    
    # State Change Handlers
    
    def _on_rag_mode_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle RAG mode state change."""
        enabled = new_value
        logger.debug(f"RAG mode changed to: {enabled}")
        self.rag_mode_changed.emit(enabled)
    
    def _on_ai_responding_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle AI responding state change."""
        responding = new_value
        logger.debug(f"AI responding state changed to: {responding}")
        
        if responding:
            self.ai_response_started.emit()
        
        # Update input enabled state
        input_enabled = not responding
        self.input_enabled_changed.emit(input_enabled)
    
    def _on_messages_changed(self, path: str, new_value: Any, old_value: Any, change_type) -> None:
        """Handle messages list change."""
        messages = new_value
        if not messages:
            return
        
        # Get the latest message
        latest_msg_data = messages[-1]
        if latest_msg_data:
            # Convert from dict if needed
            if isinstance(latest_msg_data, dict):
                msg = ChatMessage.from_dict(latest_msg_data)
            else:
                msg = latest_msg_data
            
            # Emit message signal for UI update
            self.message_received.emit(
                msg.content,
                msg.sender.value,
                msg.timestamp.isoformat()
            )
    
    # Utility Methods
    
    def get_conversation_stats(self) -> dict:
        """Get conversation statistics for UI display."""
        return self._chat_service.get_message_statistics()
    
    def is_processing(self) -> bool:
        """Check if currently processing a message."""
        return self._processing_message
    
    def get_rag_status(self) -> dict:
        """Get RAG service status for UI display."""
        return self._chat_service.get_rag_status()
    
    def cleanup(self) -> None:
        """Cleanup controller resources."""
        if self._timer:
            self._timer.stop()
        
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        
        logger.info("ChatController cleaned up") 