"""
WebSocket Manager
Manages WebSocket connections for real-time communication.
"""

import json
import logging
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time features."""

    def __init__(self):
        # Store active connections
        self.active_connections: Dict[str, WebSocket] = {}
        # Group connections by rooms/channels
        self.rooms: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(
            f"WebSocket client {client_id} connected. Total: {len(self.active_connections)}"
        )
        # Send welcome message
        await self.send_personal_message(
            json.dumps(
                {
                    "type": "connected",
                    "client_id": client_id,
                    "message": "Connected to AI PDF Scholar",
                }
            ),
            client_id,
        )

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Remove from all rooms
            for room_name, members in self.rooms.items():
                if client_id in members:
                    members.remove(client_id)
            logger.info(
                f"WebSocket client {client_id} disconnected. Total: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                # Clean up broken connection
                self.disconnect(client_id)

    async def send_personal_json(self, data: dict, client_id: str):
        """Send JSON data to a specific client."""
        await self.send_personal_message(json.dumps(data), client_id)

    async def broadcast(self, message: str):
        """Send a message to all connected clients."""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected.append(client_id)
        # Clean up broken connections
        for client_id in disconnected:
            self.disconnect(client_id)

    async def broadcast_json(self, data: dict):
        """Broadcast JSON data to all connected clients."""
        await self.broadcast(json.dumps(data))

    async def join_room(self, client_id: str, room_name: str):
        """Add a client to a room."""
        if room_name not in self.rooms:
            self.rooms[room_name] = []
        if client_id not in self.rooms[room_name]:
            self.rooms[room_name].append(client_id)
        logger.info(f"Client {client_id} joined room {room_name}")

    async def leave_room(self, client_id: str, room_name: str):
        """Remove a client from a room."""
        if room_name in self.rooms and client_id in self.rooms[room_name]:
            self.rooms[room_name].remove(client_id)
            logger.info(f"Client {client_id} left room {room_name}")

    async def send_to_room(self, message: str, room_name: str):
        """Send a message to all clients in a room."""
        if room_name not in self.rooms:
            return
        disconnected = []
        for client_id in self.rooms[room_name]:
            if client_id in self.active_connections:
                try:
                    websocket = self.active_connections[client_id]
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(
                        f"Failed to send to room {room_name}, client {client_id}: {e}"
                    )
                    disconnected.append(client_id)
        # Clean up broken connections
        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_json_to_room(self, data: dict, room_name: str):
        """Send JSON data to all clients in a room."""
        await self.send_to_room(json.dumps(data), room_name)

    def get_room_members(self, room_name: str) -> List[str]:
        """Get list of clients in a room."""
        return self.rooms.get(room_name, [])

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)

    def get_room_count(self) -> int:
        """Get total number of rooms."""
        return len(self.rooms)

    async def send_rag_progress(self, client_id: str, document_id: int, message: str):
        """Send RAG query progress update."""
        await self.send_personal_json(
            {"type": "rag_progress", "document_id": document_id, "message": message},
            client_id,
        )

    async def send_rag_response(
        self, client_id: str, query: str, response: str, document_id: int
    ):
        """Send RAG query response."""
        await self.send_personal_json(
            {
                "type": "rag_response",
                "query": query,
                "response": response,
                "document_id": document_id,
            },
            client_id,
        )

    async def send_rag_error(self, client_id: str, error: str, document_id: int = None):
        """Send RAG query error."""
        await self.send_personal_json(
            {"type": "rag_error", "error": error, "document_id": document_id}, client_id
        )

    async def send_index_progress(
        self, client_id: str, document_id: int, status: str, progress: int = None
    ):
        """Send index build progress."""
        data = {"type": "index_progress", "document_id": document_id, "status": status}
        if progress is not None:
            data["progress"] = progress
        await self.send_personal_json(data, client_id)

    async def send_document_update(
        self, document_id: int, action: str, data: dict = None
    ):
        """Broadcast document update to all clients."""
        message = {
            "type": "document_update",
            "document_id": document_id,
            "action": action,  # "created", "updated", "deleted"
        }
        if data:
            message["data"] = data
        await self.broadcast_json(message)

    async def send_upload_progress(self, client_id: str, progress_data: dict):
        """Send streaming upload progress update to client."""
        await self.send_personal_json(
            {
                "type": "upload_progress",
                "data": progress_data,
            },
            client_id,
        )

    async def send_upload_status(
        self, client_id: str, session_id: str, status: str, message: str = None
    ):
        """Send upload status update to client."""
        data = {
            "type": "upload_status",
            "session_id": session_id,
            "status": status,
        }
        if message:
            data["message"] = message
        await self.send_personal_json(data, client_id)

    async def send_upload_error(
        self, client_id: str, session_id: str, error: str, error_code: str = None
    ):
        """Send upload error to client."""
        data = {
            "type": "upload_error",
            "session_id": session_id,
            "error": error,
        }
        if error_code:
            data["error_code"] = error_code
        await self.send_personal_json(data, client_id)

    async def send_upload_completed(
        self, client_id: str, session_id: str, document_data: dict = None
    ):
        """Send upload completion notification."""
        data = {
            "type": "upload_completed",
            "session_id": session_id,
        }
        if document_data:
            data["document"] = document_data
        await self.send_personal_json(data, client_id)

    async def join_upload_room(self, client_id: str, session_id: str):
        """Add client to an upload-specific room for progress tracking."""
        room_name = f"upload_{session_id}"
        await self.join_room(client_id, room_name)

    async def leave_upload_room(self, client_id: str, session_id: str):
        """Remove client from upload-specific room."""
        room_name = f"upload_{session_id}"
        await self.leave_room(client_id, room_name)

    async def broadcast_to_upload_room(
        self, session_id: str, message_type: str, data: dict
    ):
        """Broadcast message to all clients watching an upload."""
        room_name = f"upload_{session_id}"
        message_data = {
            "type": message_type,
            "session_id": session_id,
            "data": data,
        }
        await self.send_json_to_room(message_data, room_name)

    async def send_memory_warning(self, client_id: str, memory_stats: dict):
        """Send memory usage warning to client."""
        await self.send_personal_json(
            {
                "type": "memory_warning",
                "data": memory_stats,
            },
            client_id,
        )

    async def send_chunk_progress(
        self,
        client_id: str,
        session_id: str,
        chunk_id: int,
        chunks_uploaded: int,
        total_chunks: int,
        bytes_uploaded: int,
        total_bytes: int,
        upload_speed: float = None,
    ):
        """Send detailed chunk upload progress."""
        progress_percentage = (bytes_uploaded / total_bytes) * 100 if total_bytes > 0 else 0
        
        data = {
            "type": "chunk_progress",
            "session_id": session_id,
            "chunk_id": chunk_id,
            "chunks_uploaded": chunks_uploaded,
            "total_chunks": total_chunks,
            "bytes_uploaded": bytes_uploaded,
            "total_bytes": total_bytes,
            "progress_percentage": round(progress_percentage, 2),
        }
        
        if upload_speed:
            data["upload_speed_bps"] = upload_speed
            if upload_speed > 0:
                remaining_bytes = total_bytes - bytes_uploaded
                eta_seconds = remaining_bytes / upload_speed
                data["eta_seconds"] = int(eta_seconds)
        
        await self.send_personal_json(data, client_id)

    def get_stats(self) -> dict:
        """Get WebSocket connection statistics."""
        return {
            "active_connections": self.get_connection_count(),
            "total_rooms": self.get_room_count(),
            "rooms": {
                room_name: len(members) for room_name, members in self.rooms.items()
            },
        }
