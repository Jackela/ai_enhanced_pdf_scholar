"""
Unit tests for WebSocket RAG route helper functions.

Tests the 2 helper functions extracted during Day 2 refactoring:
- _validate_websocket_message
- _handle_websocket_message

All external dependencies (WebSocket, managers) are mocked.
"""

import time
from unittest.mock import AsyncMock, Mock

import pytest

from backend.api.routes.async_rag import (
    _handle_websocket_message,
    _validate_websocket_message,
)

# ============================================================================
# Tests for _validate_websocket_message
# ============================================================================


class TestValidateWebsocketMessage:
    """Test WebSocket message validation helper."""

    def test_valid_message_returns_type(self):
        """Valid message should return type string."""
        data = {"type": "ping"}

        result = _validate_websocket_message(data)

        assert result == "ping"

    def test_valid_task_status_message(self):
        """Valid task_status message should return type."""
        data = {"type": "task_status", "task_id": "123"}

        result = _validate_websocket_message(data)

        assert result == "task_status"

    def test_missing_type_raises_value_error(self):
        """Missing type field should raise ValueError."""
        data = {}

        with pytest.raises(ValueError) as exc_info:
            _validate_websocket_message(data)

        assert "invalid" in str(exc_info.value).lower()

    def test_none_type_raises_value_error(self):
        """None type should raise ValueError."""
        data = {"type": None}

        with pytest.raises(ValueError) as exc_info:
            _validate_websocket_message(data)

        assert "invalid" in str(exc_info.value).lower()

    def test_empty_string_type_raises_value_error(self):
        """Empty string type should raise ValueError."""
        data = {"type": ""}

        with pytest.raises(ValueError) as exc_info:
            _validate_websocket_message(data)

        assert "invalid" in str(exc_info.value).lower()


# ============================================================================
# Tests for _handle_websocket_message
# ============================================================================


class TestHandleWebsocketMessage:
    """Test WebSocket message routing and handling helper."""

    @pytest.mark.asyncio
    async def test_ping_message_sends_pong(self):
        """Ping message should send pong response."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()

        data = {"type": "ping"}

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify pong response sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "pong"
        assert "timestamp" in call_args
        assert isinstance(call_args["timestamp"], float)

    @pytest.mark.asyncio
    async def test_task_status_with_id_queries_manager(self):
        """Task status message should query ws_manager."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()
        mock_ws_manager.get_rag_task_status = AsyncMock(
            return_value={"status": "running", "progress": 50}
        )

        data = {"type": "task_status", "task_id": "task_456"}

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify manager called with correct args
        mock_ws_manager.get_rag_task_status.assert_called_once_with(
            "client_123", "task_456"
        )

        # Verify response sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "task_status_response"
        assert call_args["task_id"] == "task_456"
        assert call_args["status"] == {"status": "running", "progress": 50}

    @pytest.mark.asyncio
    async def test_task_status_without_id_ignores(self):
        """Task status without task_id should be ignored."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()
        mock_ws_manager.get_rag_task_status = AsyncMock()

        data = {"type": "task_status"}  # Missing task_id

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify manager not called
        mock_ws_manager.get_rag_task_status.assert_not_called()
        # Verify no response sent
        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_task_calls_manager(self):
        """Cancel task message should call ws_manager."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()
        mock_ws_manager.cancel_rag_task = AsyncMock(return_value=True)

        data = {"type": "cancel_task", "task_id": "task_789"}

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify manager called
        mock_ws_manager.cancel_rag_task.assert_called_once_with(
            "client_123", "task_789"
        )

        # Verify response sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "task_cancelled"
        assert call_args["task_id"] == "task_789"
        assert call_args["success"] is True

    @pytest.mark.asyncio
    async def test_cancel_task_without_id_ignores(self):
        """Cancel task without task_id should be ignored."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()
        mock_ws_manager.cancel_rag_task = AsyncMock()

        data = {"type": "cancel_task"}  # Missing task_id

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify manager not called
        mock_ws_manager.cancel_rag_task.assert_not_called()
        # Verify no response sent
        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_type_sends_error(self):
        """Unknown message type should send error response."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()

        data = {"type": "invalid_type"}

        await _handle_websocket_message(
            data, "client_123", mock_websocket, mock_ws_manager
        )

        # Verify error response sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert "unknown" in call_args["message"].lower()
        assert "invalid_type" in call_args["message"]

    @pytest.mark.asyncio
    async def test_handles_multiple_message_types_sequentially(self):
        """Should handle different message types correctly in sequence."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_ws_manager = Mock()
        mock_ws_manager.get_rag_task_status = AsyncMock(return_value={"status": "done"})

        # First ping
        await _handle_websocket_message(
            {"type": "ping"}, "client_123", mock_websocket, mock_ws_manager
        )
        assert mock_websocket.send_json.call_count == 1
        assert mock_websocket.send_json.call_args[0][0]["type"] == "pong"

        # Then task status
        await _handle_websocket_message(
            {"type": "task_status", "task_id": "abc"},
            "client_123",
            mock_websocket,
            mock_ws_manager,
        )
        assert mock_websocket.send_json.call_count == 2
        assert (
            mock_websocket.send_json.call_args[0][0]["type"] == "task_status_response"
        )
