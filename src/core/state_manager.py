"""
Global State Manager
This module provides centralized application state management using observers.
It implements SSOT for all application state with change notifications.
Key Features:
- Centralized state storage with nested path support
- Observer pattern for state change notifications
- Type-safe state access with validation
- State persistence support for critical data
"""

import logging
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StateChangeType(Enum):
    """Types of state changes for granular observation."""

    SET = "set"
    UPDATE = "update"
    DELETE = "delete"
    RESET = "reset"


class StateManager:
    """
    {
        "name": "StateManager",
        "version": "1.0.0",
        "description": "Global application state management with observer pattern.",
        "dependencies": [],
        "interface": {
            "inputs": ["path: str", "value: Any", "notify: bool"],
            "outputs": "Centralized state with change notifications"
        }
    }
    Singleton state manager that provides unified access to all application state
    with observer pattern for reactive UI updates and data flow.
    """

    # Constants
    MAX_HISTORY_SIZE = 100  # Maximum number of state changes to keep in history

    _instance: Optional["StateManager"] = None

    def __new__(cls) -> "StateManager":
        """Ensure singleton pattern for global state access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize state manager with default application state."""
        if hasattr(self, "_initialized"):
            return
        # Application state tree
        self._state: dict[str, Any] = {
            "app": {
                "current_pdf": None,
                "rag_mode": False,
                "ui_state": "ready",  # ready, loading, error
                "current_breakpoint": "medium",
                "last_error": None,
                "debug_mode": False,
            },
            "chat": {
                "messages": [],
                "is_ai_responding": False,
                "last_user_message": "",
                "conversation_id": None,
                "message_count": 0,
            },
            "annotations": {
                "items": [],
                "selected_annotation": None,
                "total_count": 0,
                "last_added": None,
            },
            "pdf": {
                "current_path": None,
                "current_page": 0,
                "total_pages": 0,
                "zoom_level": 1.0,
                "selection": None,
            },
            "rag": {
                "index_ready": False,
                "indexing_progress": 0,
                "last_query": None,
                "cache_info": {},
            },
        }
        # Observer registry: path -> list of callbacks
        self._observers: dict[str, list[Callable]] = {}
        # State change history for debugging
        self._change_history: list[dict[str, Any]] = []
        self._initialized = True
        logger.info("StateManager initialized with default application state")

    def get_state(self, path: str | None = None, default: Any = None) -> Any:
        """
        Get state value using dot-separated path notation.
        Args:
            path: Dot-separated state path (e.g., 'chat.messages').
                  If None, returns entire state tree.
            default: Default value to return if path doesn't exist
        Returns:
            State value at the specified path, or default if path doesn't exist
        Examples:
            get_state('chat.messages') -> List of chat messages
            get_state('app.rag_mode', False) -> Boolean RAG mode flag with default
            get_state() -> Entire state dictionary
        """
        if path is None:
            return self._state
        try:
            return self._get_nested_value(self._state, path)
        except Exception as e:
            logger.warning(f"Failed to get state at path '{path}': {e}")
            return default

    def set_state(self, path: str, value: Any, notify: bool = True) -> bool:
        """
        Set state value at the specified path with optional change notification.
        Args:
            path: Dot-separated state path to set
            value: Value to set at the path
            notify: Whether to notify observers of the change
        Returns:
            True if state was successfully set, False otherwise
        Examples:
            set_state('app.rag_mode', True) -> Enable RAG mode
            set_state('chat.is_ai_responding', False) -> Stop AI response indicator
        """
        try:
            old_value = self._get_nested_value(self._state, path)
            # Set the new value
            self._set_nested_value(self._state, path, value)
            # Record the change
            change_record = {
                "timestamp": datetime.now(),
                "path": path,
                "old_value": old_value,
                "new_value": value,
                "change_type": StateChangeType.SET,
            }
            self._change_history.append(change_record)
            # Keep history limited to last MAX_HISTORY_SIZE changes
            if len(self._change_history) > self.MAX_HISTORY_SIZE:
                self._change_history.pop(0)
            logger.debug(f"State set: {path} = {value}")
            # Notify observers if requested
            if notify:
                self._notify_observers(path, value, old_value, StateChangeType.SET)
            return True
        except Exception as e:
            logger.error(f"Failed to set state at path '{path}': {e}")
            return False

    def update_state(
        self, path: str, update_func: Callable[[Any], Any], notify: bool = True
    ) -> bool:
        """
        Update state value using a function that receives the current value.
        Args:
            path: Dot-separated state path to update
            update_func: Function that takes current value and returns new value
            notify: Whether to notify observers of the change
        Returns:
            True if state was successfully updated, False otherwise
        Examples:
            update_state('chat.message_count', lambda x: x + 1) -> Increment count
            update_state('chat.messages', lambda msgs: msgs + [new_msg]) -> Add msg
        """
        try:
            current_value = self._get_nested_value(self._state, path)
            new_value = update_func(current_value)
            # Use set_state to handle the actual update
            return self.set_state(path, new_value, notify)
        except Exception as e:
            logger.error(f"Failed to update state at path '{path}': {e}")
            return False

    def delete_state(self, path: str, notify: bool = True) -> bool:
        """
        Delete state value at the specified path.
        Args:
            path: Dot-separated state path to delete
            notify: Whether to notify observers of the deletion
        Returns:
            True if state was successfully deleted, False otherwise
        """
        try:
            old_value = self._get_nested_value(self._state, path)
            # Delete the value
            self._delete_nested_value(self._state, path)
            # Record the change
            change_record = {
                "timestamp": datetime.now(),
                "path": path,
                "old_value": old_value,
                "new_value": None,
                "change_type": StateChangeType.DELETE,
            }
            self._change_history.append(change_record)
            logger.debug(f"State deleted: {path}")
            # Notify observers if requested
            if notify:
                self._notify_observers(path, None, old_value, StateChangeType.DELETE)
            return True
        except Exception as e:
            logger.error(f"Failed to delete state at path '{path}': {e}")
            return False

    def subscribe(
        self, path: str, callback: Callable[[str, Any, Any, StateChangeType], None]
    ) -> None:
        """
        Subscribe to state changes at a specific path.
        Args:
            path: State path to observe (supports wildcards)
            callback: Function called when state changes (path, new_val, old_val, type)
        """
        if path not in self._observers:
            self._observers[path] = []
        self._observers[path].append(callback)
        logger.debug(f"Added observer for path '{path}': {callback.__name__}")

    def unsubscribe(self, path: str, callback: Callable) -> None:
        """
        Unsubscribe from state changes at a specific path.
        Args:
            path: State path being observed
            callback: Function to remove from observers
        """
        if path in self._observers and callback in self._observers[path]:
            self._observers[path].remove(callback)
            logger.debug(f"Removed observer for path '{path}': {callback.__name__}")

    def _get_nested_value(self, state_dict: dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split(".")
        current = state_dict
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _set_nested_value(
        self, state_dict: dict[str, Any], path: str, value: Any
    ) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = path.split(".")
        current = state_dict
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        # Set the final value
        current[keys[-1]] = value

    def _delete_nested_value(self, state_dict: dict[str, Any], path: str) -> None:
        """Delete value from nested dictionary using dot notation."""
        keys = path.split(".")
        current = state_dict
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                return  # Path doesn't exist
            current = current[key]
        # Delete the final key if it exists
        if keys[-1] in current:
            del current[keys[-1]]

    def _safe_notify_observer(
        self,
        observer: callable,
        path: str,
        new_value: Any,
        old_value: Any,
        change_type: StateChangeType,
    ) -> None:
        """Safely notify a single observer, handling exceptions."""
        try:
            observer(path, new_value, old_value, change_type)
        except Exception as e:
            logger.error(f"Error notifying observer {observer.__name__}: {e}")

    def _notify_observers(
        self, path: str, new_value: Any, old_value: Any, change_type: StateChangeType
    ) -> None:
        """
        Notify all relevant observers of state changes.
        Args:
            path: Path that changed
            new_value: New value at the path
            old_value: Previous value at the path
            change_type: Type of change that occurred
        """
        # Notify exact path observers
        if path in self._observers:
            for observer in self._observers[path]:
                self._safe_notify_observer(
                    observer, path, new_value, old_value, change_type
                )

        # Notify wildcard observers (e.g., 'chat.*' matches 'chat.messages')
        import re

        for observer_path, observers in self._observers.items():
            if "*" in observer_path:
                pattern = observer_path.replace("*", ".*")
                if re.match(pattern, path):
                    for observer in observers:
                        self._safe_notify_observer(
                            observer, path, new_value, old_value, change_type
                        )

    def reset_state(self, section: str | None = None) -> None:
        """
        Reset state to defaults.
        Args:
            section: Optional section to reset (e.g., 'chat'). If None, resets all.
        """
        if section:
            if section in self._state:
                old_state = self._state[section].copy()
                self._state[section] = self._get_default_state()[section]
                self._notify_observers(
                    section, self._state[section], old_state, StateChangeType.RESET
                )
                logger.info(f"Reset state section: {section}")
        else:
            old_state = self._state.copy()
            self._state = self._get_default_state()
            self._notify_observers(
                "__all__", self._state, old_state, StateChangeType.RESET
            )
            logger.info("Reset all application state")

    def _get_default_state(self) -> dict[str, Any]:
        """Get default application state structure."""
        return {
            "app": {
                "current_pdf": None,
                "rag_mode": False,
                "ui_state": "ready",
                "current_breakpoint": "medium",
                "last_error": None,
                "debug_mode": False,
            },
            "chat": {
                "messages": [],
                "is_ai_responding": False,
                "last_user_message": "",
                "conversation_id": None,
                "message_count": 0,
            },
            "annotations": {
                "items": [],
                "selected_annotation": None,
                "total_count": 0,
                "last_added": None,
            },
            "pdf": {
                "current_path": None,
                "current_page": 0,
                "total_pages": 0,
                "zoom_level": 1.0,
                "selection": None,
            },
            "rag": {
                "index_ready": False,
                "indexing_progress": 0,
                "last_query": None,
                "cache_info": {},
            },
        }

    def get_change_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent state change history for debugging."""
        return self._change_history[-limit:] if limit > 0 else self._change_history

    def get_state_summary(self) -> dict[str, Any]:
        """Get summary of current state for debugging."""
        return {
            "total_observers": sum(len(obs) for obs in self._observers.values()),
            "change_history_size": len(self._change_history),
            "state_sections": list(self._state.keys()),
            "last_changes": self.get_change_history(5),
        }
