"""
WebSocket Manager
Manages WebSocket connections for real-time communication.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RAGTaskStatus(Enum):
    """Status of RAG processing tasks."""

    PENDING = "pending"
    PROCESSING = "processing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RAGProgressType(Enum):
    """Types of RAG progress updates."""

    STARTED = "started"
    PARSING = "parsing"
    INDEXING = "indexing"
    QUERYING = "querying"
    STREAMING_RESPONSE = "streaming_response"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class RAGTask:
    """Represents a RAG processing task."""

    task_id: str
    client_id: str
    document_id: int
    query: str
    status: RAGTaskStatus = RAGTaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    progress_percentage: float = 0.0
    current_stage: str | None = None
    result: str | None = None
    error: str | None = None
    processing_time_ms: float | None = None
    background_task: asyncio.Task | None = None
    cancellation_token: asyncio.Event | None = field(default_factory=asyncio.Event)


@dataclass
class RAGStreamConfig:
    """Configuration for RAG streaming behavior."""

    enable_progress_updates: bool = True
    progress_update_interval: float = 0.5  # seconds
    chunk_size: int = 512  # characters per chunk
    enable_real_time_streaming: bool = True
    max_concurrent_tasks: int = 5
    task_timeout_seconds: int = 300  # 5 minutes


class WebSocketManager:
    """Manages WebSocket connections for real-time features with RAG streaming support."""

    def __init__(self):
        # Store active connections
        self.active_connections: dict[str, WebSocket] = {}
        # Group connections by rooms/channels
        self.rooms: dict[str, list[str]] = {}

        # RAG streaming capabilities
        self.rag_tasks: dict[str, RAGTask] = {}
        self.client_tasks: dict[str, set[str]] = {}  # client_id -> set of task_ids
        self.rag_config = RAGStreamConfig()
        self._task_counter = 0
        self._cleanup_task: asyncio.Task | None = None
        self._is_started = False

        # Don't start background task immediately - wait until first connection

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # Start cleanup task if not already started
        self._start_cleanup_task()

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
        """Remove a WebSocket connection and cleanup associated RAG tasks."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Remove from all rooms
            for room_name, members in self.rooms.items():
                if client_id in members:
                    members.remove(client_id)

            # Cancel and cleanup RAG tasks for this client
            self._cleanup_client_rag_tasks(client_id)

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

    def get_room_members(self, room_name: str) -> list[str]:
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

    def _start_cleanup_task(self):
        """Start background task for cleaning up completed/failed RAG tasks."""
        try:
            # Only start if we have a running event loop and haven't started yet
            if not self._is_started and (
                not self._cleanup_task or self._cleanup_task.done()
            ):
                asyncio.get_running_loop()  # This will raise if no loop is running
                self._cleanup_task = asyncio.create_task(self._cleanup_background())
                self._is_started = True
        except RuntimeError:
            # No event loop running, task will be started later when needed
            pass

    async def _cleanup_background(self):
        """Background task to clean up old RAG tasks."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                current_time = datetime.now()

                # Find tasks to cleanup (completed/failed tasks older than 10 minutes)
                tasks_to_remove = []
                for task_id, task in self.rag_tasks.items():
                    if task.status in [
                        RAGTaskStatus.COMPLETED,
                        RAGTaskStatus.FAILED,
                        RAGTaskStatus.CANCELLED,
                    ]:
                        age_minutes = (
                            current_time - task.created_at
                        ).total_seconds() / 60
                        if age_minutes > 10:
                            tasks_to_remove.append(task_id)

                # Remove old tasks
                for task_id in tasks_to_remove:
                    self._remove_rag_task(task_id)

                if tasks_to_remove:
                    logger.debug(f"Cleaned up {len(tasks_to_remove)} old RAG tasks")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in RAG task cleanup: {e}")

    def _cleanup_client_rag_tasks(self, client_id: str):
        """Cancel and cleanup all RAG tasks for a specific client."""
        if client_id not in self.client_tasks:
            return

        task_ids = self.client_tasks[client_id].copy()
        for task_id in task_ids:
            if task_id in self.rag_tasks:
                task = self.rag_tasks[task_id]

                # Cancel background task if running
                if task.background_task and not task.background_task.done():
                    task.background_task.cancel()

                # Set cancellation token
                if task.cancellation_token:
                    task.cancellation_token.set()

                # Update status
                task.status = RAGTaskStatus.CANCELLED

                # Remove from tracking
                self._remove_rag_task(task_id)

        logger.debug(f"Cancelled {len(task_ids)} RAG tasks for client {client_id}")

    def _remove_rag_task(self, task_id: str):
        """Remove a RAG task from all tracking dictionaries."""
        if task_id in self.rag_tasks:
            task = self.rag_tasks[task_id]

            # Remove from client tracking
            if task.client_id in self.client_tasks:
                self.client_tasks[task.client_id].discard(task_id)
                if not self.client_tasks[task.client_id]:
                    del self.client_tasks[task.client_id]

            # Remove main task
            del self.rag_tasks[task_id]

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self._task_counter += 1
        timestamp = int(datetime.now().timestamp() * 1000)
        return f"rag_task_{timestamp}_{self._task_counter}"

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
        progress_percentage = (
            (bytes_uploaded / total_bytes) * 100 if total_bytes > 0 else 0
        )

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
        """Get WebSocket connection statistics including RAG streaming stats."""
        # Calculate RAG task statistics
        rag_stats = {
            "total_tasks": len(self.rag_tasks),
            "pending_tasks": len(
                [
                    t
                    for t in self.rag_tasks.values()
                    if t.status == RAGTaskStatus.PENDING
                ]
            ),
            "processing_tasks": len(
                [
                    t
                    for t in self.rag_tasks.values()
                    if t.status == RAGTaskStatus.PROCESSING
                ]
            ),
            "streaming_tasks": len(
                [
                    t
                    for t in self.rag_tasks.values()
                    if t.status == RAGTaskStatus.STREAMING
                ]
            ),
            "completed_tasks": len(
                [
                    t
                    for t in self.rag_tasks.values()
                    if t.status == RAGTaskStatus.COMPLETED
                ]
            ),
            "failed_tasks": len(
                [t for t in self.rag_tasks.values() if t.status == RAGTaskStatus.FAILED]
            ),
        }

        return {
            "active_connections": self.get_connection_count(),
            "total_rooms": self.get_room_count(),
            "rooms": {
                room_name: len(members) for room_name, members in self.rooms.items()
            },
            "rag_streaming": rag_stats,
            "rag_config": {
                "max_concurrent_tasks": self.rag_config.max_concurrent_tasks,
                "enable_real_time_streaming": self.rag_config.enable_real_time_streaming,
                "task_timeout_seconds": self.rag_config.task_timeout_seconds,
            },
        }

    # ============================================================================
    # RAG Streaming Methods
    # ============================================================================

    async def start_rag_stream(
        self,
        client_id: str,
        document_id: int,
        query: str,
        rag_processor: Callable[[str, int, str, asyncio.Event], Any],
        **kwargs,
    ) -> str:
        """Start a new RAG streaming task."""
        if client_id not in self.active_connections:
            raise ValueError(f"Client {client_id} not connected")

        client_task_count = len(self.client_tasks.get(client_id, set()))
        if client_task_count >= self.rag_config.max_concurrent_tasks:
            await self.send_rag_error(
                client_id,
                f"Maximum concurrent tasks ({self.rag_config.max_concurrent_tasks}) reached",
                document_id,
            )
            raise ValueError("Too many concurrent RAG tasks")

        task_id = self._generate_task_id()
        cancellation_token = asyncio.Event()

        task = RAGTask(
            task_id=task_id,
            client_id=client_id,
            document_id=document_id,
            query=query,
            status=RAGTaskStatus.PENDING,
            cancellation_token=cancellation_token,
        )

        self.rag_tasks[task_id] = task
        if client_id not in self.client_tasks:
            self.client_tasks[client_id] = set()
        self.client_tasks[client_id].add(task_id)

        background_task = asyncio.create_task(
            self._process_rag_task(task, rag_processor, **kwargs)
        )
        task.background_task = background_task

        await self.send_rag_task_started(client_id, task_id, document_id, query)
        logger.info(f"Started RAG streaming task {task_id} for client {client_id}")
        return task_id

    async def _process_rag_task(self, task: RAGTask, rag_processor: Callable, **kwargs):
        """Background task to process RAG query with streaming."""
        try:
            task.status = RAGTaskStatus.PROCESSING
            start_time = datetime.now()

            await self.send_rag_progress_update(
                task.client_id,
                task.task_id,
                RAGProgressType.STARTED,
                0.0,
                "Starting RAG processing",
            )

            result = await rag_processor(
                task.query,
                task.document_id,
                task.task_id,
                task.cancellation_token,
                **kwargs,
            )

            if task.cancellation_token.is_set():
                task.status = RAGTaskStatus.CANCELLED
                await self.send_rag_task_cancelled(task.client_id, task.task_id)
                return

            end_time = datetime.now()
            task.result = result
            task.processing_time_ms = (end_time - start_time).total_seconds() * 1000
            task.status = RAGTaskStatus.COMPLETED
            task.progress_percentage = 100.0

            await self.send_rag_task_completed(
                task.client_id,
                task.task_id,
                task.document_id,
                task.query,
                result,
                task.processing_time_ms,
            )

            logger.info(
                f"RAG task {task.task_id} completed in {task.processing_time_ms:.2f}ms"
            )

        except asyncio.CancelledError:
            task.status = RAGTaskStatus.CANCELLED
            await self.send_rag_task_cancelled(task.client_id, task.task_id)
            logger.info(f"RAG task {task.task_id} was cancelled")

        except Exception as e:
            task.status = RAGTaskStatus.FAILED
            task.error = str(e)
            await self.send_rag_task_failed(task.client_id, task.task_id, str(e))
            logger.error(f"RAG task {task.task_id} failed: {e}")

    async def cancel_rag_task(self, client_id: str, task_id: str) -> bool:
        """Cancel a running RAG task."""
        if task_id not in self.rag_tasks:
            return False
        task = self.rag_tasks[task_id]
        if task.client_id != client_id or task.status in [
            RAGTaskStatus.COMPLETED,
            RAGTaskStatus.FAILED,
            RAGTaskStatus.CANCELLED,
        ]:
            return False
        if task.cancellation_token:
            task.cancellation_token.set()
        if task.background_task and not task.background_task.done():
            task.background_task.cancel()
        task.status = RAGTaskStatus.CANCELLED
        await self.send_rag_task_cancelled(client_id, task_id)
        logger.info(f"RAG task {task_id} cancelled by client {client_id}")
        return True

    async def get_rag_task_status(
        self, client_id: str, task_id: str
    ) -> dict[str, Any] | None:
        """Get status of a RAG task."""
        if task_id not in self.rag_tasks:
            return None
        task = self.rag_tasks[task_id]
        if task.client_id != client_id:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "document_id": task.document_id,
            "query": task.query,
            "created_at": task.created_at.isoformat(),
            "progress_percentage": task.progress_percentage,
            "current_stage": task.current_stage,
            "result": task.result,
            "error": task.error,
            "processing_time_ms": task.processing_time_ms,
        }

    # Notification Methods
    async def send_rag_task_started(
        self, client_id: str, task_id: str, document_id: int, query: str
    ):
        """Send RAG task started notification."""
        await self.send_personal_json(
            {
                "type": "rag_task_started",
                "task_id": task_id,
                "document_id": document_id,
                "query": query,
                "timestamp": datetime.now().isoformat(),
            },
            client_id,
        )

    async def send_rag_progress_update(
        self,
        client_id: str,
        task_id: str,
        progress_type: RAGProgressType,
        percentage: float,
        message: str,
        stage_data: dict[str, Any] | None = None,
    ):
        """Send detailed RAG progress update."""
        data = {
            "type": "rag_progress_update",
            "task_id": task_id,
            "progress_type": progress_type.value,
            "percentage": percentage,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        if stage_data:
            data["stage_data"] = stage_data
        await self.send_personal_json(data, client_id)
        if task_id in self.rag_tasks:
            self.rag_tasks[task_id].progress_percentage = percentage
            self.rag_tasks[task_id].current_stage = progress_type.value

    async def send_rag_response_chunk(
        self,
        client_id: str,
        task_id: str,
        chunk: str,
        chunk_index: int,
        total_chunks: int | None = None,
    ):
        """Send streaming RAG response chunk."""
        await self.send_personal_json(
            {
                "type": "rag_response_chunk",
                "task_id": task_id,
                "chunk": chunk,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "timestamp": datetime.now().isoformat(),
            },
            client_id,
        )

    async def send_rag_task_completed(
        self,
        client_id: str,
        task_id: str,
        document_id: int,
        query: str,
        result: str,
        processing_time_ms: float,
    ):
        """Send RAG task completion notification."""
        await self.send_personal_json(
            {
                "type": "rag_task_completed",
                "task_id": task_id,
                "document_id": document_id,
                "query": query,
                "result": result,
                "processing_time_ms": processing_time_ms,
                "timestamp": datetime.now().isoformat(),
            },
            client_id,
        )

    async def send_rag_task_failed(self, client_id: str, task_id: str, error: str):
        """Send RAG task failure notification."""
        await self.send_personal_json(
            {
                "type": "rag_task_failed",
                "task_id": task_id,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            },
            client_id,
        )

    async def send_rag_task_cancelled(self, client_id: str, task_id: str):
        """Send RAG task cancellation notification."""
        await self.send_personal_json(
            {
                "type": "rag_task_cancelled",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
            client_id,
        )

    async def cleanup(self):
        """Clean up all resources and cancel background tasks."""
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all RAG tasks
        for task_id in list(self.rag_tasks.keys()):
            task = self.rag_tasks[task_id]
            if task.background_task and not task.background_task.done():
                task.background_task.cancel()
            if task.cancellation_token:
                task.cancellation_token.set()

        # Clear all data
        self.active_connections.clear()
        self.rooms.clear()
        self.client_tasks.clear()
        self.rag_tasks.clear()
        self._is_started = False

        logger.info("WebSocketManager cleanup completed")
