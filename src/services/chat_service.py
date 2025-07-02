"""
Chat Service - Pure Business Logic

This module provides chat functionality as pure business logic,
completely decoupled from UI frameworks for maximum testability and reusability.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import asyncio

from src.core.state_manager import StateManager
from src.llm_service import LLMService, LLMServiceError
from src.rag_service import RAGService, RAGServiceError

logger = logging.getLogger(__name__)


class MessageSender(Enum):
    """Message sender types."""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class ChatMessage:
    """
    {
        "name": "ChatMessage",
        "version": "1.0.0", 
        "description": "Pure data model for chat messages without UI dependencies.",
        "dependencies": [],
        "interface": {
            "inputs": ["content: str", "sender: MessageSender", "timestamp: datetime"],
            "outputs": "Chat message data object"
        }
    }
    
    Pure data class representing a chat message without any UI coupling.
    """
    
    def __init__(self, content: str, sender: MessageSender, timestamp: datetime = None):
        """
        Initialize chat message.
        
        Args:
            content: Message text content
            sender: Who sent the message (user, ai, system)
            timestamp: When message was created (defaults to now)
        """
        self.content = content
        self.sender = sender
        self.timestamp = timestamp or datetime.now()
        self.id = f"{sender.value}_{self.timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            'id': self.id,
            'content': self.content,
            'sender': self.sender.value,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create message from dictionary."""
        return cls(
            content=data['content'],
            sender=MessageSender(data['sender']),
            timestamp=datetime.fromisoformat(data['timestamp'])
        )
    
    def __str__(self) -> str:
        return f"[{self.sender.value.upper()}] {self.content[:50]}..."


class ChatService:
    """
    {
        "name": "ChatService", 
        "version": "1.0.0",
        "description": "Pure business logic for chat functionality, completely UI-independent.",
        "dependencies": ["StateManager", "LLMService", "RAGService"],
        "interface": {
            "inputs": ["message: str", "context: dict"],
            "outputs": "ChatMessage with AI response"
        }
    }
    
    Pure business logic service for chat functionality.
    Handles message processing, AI integration, and conversation management
    without any UI framework dependencies.
    """
    
    def __init__(self, 
                 llm_service: LLMService,
                 state_manager: StateManager,
                 rag_service: Optional[RAGService] = None):
        """
        Initialize chat service with required dependencies.
        
        Args:
            llm_service: LLM service for AI responses
            state_manager: Global state management
            rag_service: Optional RAG service for document-aware responses
        """
        self._llm = llm_service
        self._state = state_manager
        self._rag = rag_service
        
        # Initialize conversation state if not exists
        if not self._state.get_state('chat.messages'):
            self._state.set_state('chat.messages', [])
        
        logger.info("ChatService initialized with LLM and state management")
    
    async def send_message(self, message_content: str, use_rag: bool = None) -> ChatMessage:
        """
        Process user message and generate AI response.
        
        Args:
            message_content: User's message text
            use_rag: Override RAG mode setting (None = use state setting)
            
        Returns:
            ChatMessage containing AI response
            
        Raises:
            ValueError: If message content is empty
            LLMServiceError: If AI service fails
            RAGServiceError: If RAG service fails
        """
        if not message_content or not message_content.strip():
            raise ValueError("Message content cannot be empty")
        
        # Create user message
        user_message = ChatMessage(
            content=message_content.strip(),
            sender=MessageSender.USER
        )
        
        # Add user message to conversation
        self._add_message_to_state(user_message)
        
        # Update state - AI is responding
        self._state.set_state('chat.is_ai_responding', True)
        self._state.set_state('chat.last_user_message', message_content)
        
        try:
            # Determine if we should use RAG
            should_use_rag = use_rag if use_rag is not None else self._state.get_state('app.rag_mode', False)
            
            # Generate AI response
            if should_use_rag and self._rag and self._rag.is_ready():
                ai_response_text = await self._query_rag(message_content)
            else:
                ai_response_text = await self._query_llm(message_content)
            
            # Create AI message
            ai_message = ChatMessage(
                content=ai_response_text,
                sender=MessageSender.AI
            )
            
            # Add AI message to conversation
            self._add_message_to_state(ai_message)
            
            logger.info(f"Chat exchange completed: user={len(message_content)} chars, ai={len(ai_response_text)} chars")
            return ai_message
            
        except Exception as e:
            logger.error(f"Failed to process chat message: {e}")
            
            # Create error message
            error_message = ChatMessage(
                content=f"Sorry, I encountered an error: {str(e)}",
                sender=MessageSender.SYSTEM
            )
            self._add_message_to_state(error_message)
            
            raise
            
        finally:
            # Always reset AI responding state
            self._state.set_state('chat.is_ai_responding', False)
    
    async def _query_llm(self, message: str) -> str:
        """Query LLM service for AI response."""
        try:
            logger.debug("Querying LLM service")
            return await asyncio.to_thread(self._llm.query_llm, message)
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise LLMServiceError(f"Failed to get AI response: {e}") from e
    
    async def _query_rag(self, message: str) -> str:
        """Query RAG service for document-aware response."""
        try:
            logger.debug("Querying RAG service")
            return await asyncio.to_thread(self._rag.query, message)
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise RAGServiceError(f"Failed to get document-aware response: {e}") from e
    
    def _add_message_to_state(self, message: ChatMessage) -> None:
        """Add message to global state and update counters."""
        # Get current messages
        messages = self._state.get_state('chat.messages') or []
        
        # Add new message
        messages.append(message)
        
        # Update state
        self._state.set_state('chat.messages', messages)
        self._state.update_state('chat.message_count', lambda x: x + 1)
        
        logger.debug(f"Added {message.sender.value} message to conversation (total: {len(messages)})")
    
    def get_conversation_history(self) -> List[ChatMessage]:
        """Get current conversation history."""
        messages_data = self._state.get_state('chat.messages') or []
        
        # Convert to ChatMessage objects if needed
        messages = []
        for msg_data in messages_data:
            if isinstance(msg_data, ChatMessage):
                messages.append(msg_data)
            elif isinstance(msg_data, dict):
                messages.append(ChatMessage.from_dict(msg_data))
        
        return messages
    
    def get_conversation_context(self, max_messages: int = 10) -> str:
        """
        Get recent conversation as context string for AI.
        
        Args:
            max_messages: Maximum number of recent messages to include
            
        Returns:
            Formatted conversation context
        """
        messages = self.get_conversation_history()
        recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
        
        context_lines = []
        for msg in recent_messages:
            prefix = "User" if msg.sender == MessageSender.USER else "Assistant"
            context_lines.append(f"{prefix}: {msg.content}")
        
        return "\n".join(context_lines)
    
    def clear_conversation(self) -> None:
        """Clear all messages from current conversation."""
        message_count = len(self._state.get_state('chat.messages') or [])
        
        self._state.set_state('chat.messages', [])
        self._state.set_state('chat.message_count', 0)
        self._state.set_state('chat.last_user_message', '')
        self._state.set_state('chat.conversation_id', None)
        
        logger.info(f"Cleared conversation with {message_count} messages")
    
    def export_conversation(self, format: str = 'json') -> str:
        """
        Export conversation in specified format.
        
        Args:
            format: Export format ('json', 'text', 'markdown')
            
        Returns:
            Formatted conversation string
        """
        messages = self.get_conversation_history()
        
        if format == 'json':
            import json
            return json.dumps([msg.to_dict() for msg in messages], indent=2)
        
        elif format == 'text':
            lines = []
            for msg in messages:
                timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{timestamp}] {msg.sender.value.upper()}: {msg.content}")
            return "\n".join(lines)
        
        elif format == 'markdown':
            lines = ["# Conversation Export", ""]
            for msg in messages:
                timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if msg.sender == MessageSender.USER:
                    lines.append(f"**User** ({timestamp}):")
                    lines.append(f"> {msg.content}")
                elif msg.sender == MessageSender.AI:
                    lines.append(f"**AI Assistant** ({timestamp}):")
                    lines.append(f"{msg.content}")
                lines.append("")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_message_statistics(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        messages = self.get_conversation_history()
        
        user_messages = [m for m in messages if m.sender == MessageSender.USER]
        ai_messages = [m for m in messages if m.sender == MessageSender.AI]
        
        total_chars = sum(len(m.content) for m in messages)
        user_chars = sum(len(m.content) for m in user_messages)
        ai_chars = sum(len(m.content) for m in ai_messages)
        
        return {
            'total_messages': len(messages),
            'user_messages': len(user_messages),
            'ai_messages': len(ai_messages),
            'total_characters': total_chars,
            'user_characters': user_chars,
            'ai_characters': ai_chars,
            'average_user_message_length': user_chars / len(user_messages) if user_messages else 0,
            'average_ai_message_length': ai_chars / len(ai_messages) if ai_messages else 0,
            'conversation_started': messages[0].timestamp.isoformat() if messages else None,
            'last_activity': messages[-1].timestamp.isoformat() if messages else None
        }
    
    def is_ai_responding(self) -> bool:
        """Check if AI is currently processing a response."""
        return self._state.get_state('chat.is_ai_responding', False)
    
    def set_rag_service(self, rag_service: RAGService) -> None:
        """Set or update RAG service."""
        self._rag = rag_service
        logger.info("RAG service updated in ChatService")
    
    def get_rag_status(self) -> Dict[str, Any]:
        """Get RAG service status information."""
        if not self._rag:
            return {'available': False, 'ready': False}
        
        return {
            'available': True,
            'ready': self._rag.is_ready(),
            'current_pdf': self._rag.get_current_pdf_path(),
            'cache_info': self._rag.get_cache_info() if hasattr(self._rag, 'get_cache_info') else {}
        } 