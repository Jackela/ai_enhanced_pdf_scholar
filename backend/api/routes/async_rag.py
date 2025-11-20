"""
Async RAG API Routes
Async WebSocket-enabled RAG endpoints for real-time streaming processing.
"""

import asyncio
import logging
import time
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel

from backend.api.dependencies import (
    get_library_controller,
    get_websocket_manager,
    require_rag_service,
    validate_document_access,
)
from backend.api.error_handling import (
    ErrorTemplates,
    ResourceNotFoundException,
    SystemException,
)
from backend.api.models import (
    RAGQueryRequest,
    RAGQueryResponse,
)
from backend.api.websocket_manager import RAGProgressType, WebSocketManager
from src.controllers.library_controller import LibraryController
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)
router = APIRouter()


class AsyncRAGQueryRequest(BaseModel):
    """Request model for async RAG queries."""

    document_id: int
    query: str
    client_id: str
    use_streaming: bool = True
    chunk_size: int = 512
    enable_progress_updates: bool = True


class RAGTaskResponse(BaseModel):
    """Response model for RAG task operations."""

    task_id: str
    status: str
    message: str


class RAGStreamingProcessor:
    """Processor for async RAG operations with WebSocket streaming support."""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        controller: LibraryController,
        rag_service: EnhancedRAGService,
    ) -> None:
        self.ws_manager = ws_manager
        self.controller = controller
        self.rag_service = rag_service

    async def process_rag_query(  # noqa: C901 - RAG workflow orchestration with state machine logic
        self,
        query: str,
        document_id: int,
        task_id: str,
        cancellation_token: asyncio.Event,
        client_id: str,
        chunk_size: int = 512,
        enable_progress_updates: bool = True,
        **kwargs,
    ) -> str:
        """Process RAG query with streaming updates."""
        try:
            # Stage 1: Validation and Setup
            if enable_progress_updates:
                await self.ws_manager.send_rag_progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.PARSING,
                    10.0,
                    "Validating document and preparing query",
                )

            # Check cancellation
            if cancellation_token.is_set():
                return ""

            # Validate document access
            validate_document_access(document_id, self.controller)

            # Stage 2: Index Status Check
            if enable_progress_updates:
                await self.ws_manager.send_rag_progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.INDEXING,
                    30.0,
                    "Checking vector index status",
                )

            # Check cancellation
            if cancellation_token.is_set():
                return ""

            index_status = self.controller.get_index_status(document_id)
            if not index_status.get("can_query", False):
                raise ErrorTemplates.index_not_ready(document_id)

            # Stage 3: Query Processing
            if enable_progress_updates:
                await self.ws_manager.send_rag_progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.QUERYING,
                    50.0,
                    "Processing RAG query",
                )

            # Check cancellation
            if cancellation_token.is_set():
                return ""

            # Execute RAG query (simulate async processing)
            await asyncio.sleep(0.1)  # Allow for cancellation checks
            response = self.controller.query_document(document_id, query)

            if response is None:
                raise SystemException(
                    message="RAG query processing failed", error_type="external_service"
                )

            # Stage 4: Response Streaming (if enabled)
            if enable_progress_updates and len(response) > chunk_size:
                await self.ws_manager.send_rag_progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.STREAMING_RESPONSE,
                    80.0,
                    "Streaming response to client",
                )

                # Stream response in chunks
                chunks = [
                    response[i : i + chunk_size]
                    for i in range(0, len(response), chunk_size)
                ]
                total_chunks = len(chunks)

                for i, chunk in enumerate(chunks):
                    if cancellation_token.is_set():
                        return ""

                    await self.ws_manager.send_rag_response_chunk(
                        client_id, task_id, chunk, i, total_chunks
                    )

                    # Small delay between chunks to prevent overwhelming
                    await asyncio.sleep(0.05)

            # Final stage
            if enable_progress_updates:
                await self.ws_manager.send_rag_progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.COMPLETED,
                    100.0,
                    "Query processing completed",
                )

            return response

        except asyncio.CancelledError:
            logger.info(f"RAG query cancelled for task {task_id}")
            raise
        except Exception as e:
            logger.error(f"RAG query processing failed for task {task_id}: {e}")
            if enable_progress_updates:
                await self.ws_manager.send_rag_progress_update(
                    client_id, task_id, RAGProgressType.ERROR, 0.0, f"Error: {str(e)}"
                )
            raise


@router.post("/query/async", response_model=RAGTaskResponse)
async def async_query_document(
    request: AsyncRAGQueryRequest,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> Any:
    """Start an async RAG query with WebSocket streaming support."""
    try:
        # Validate WebSocket connection
        if request.client_id not in ws_manager.active_connections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Client {request.client_id} not connected to WebSocket",
            )

        # Create RAG processor
        processor = RAGStreamingProcessor(ws_manager, controller, rag_service)

        # Start async RAG processing
        task_id = await ws_manager.start_rag_stream(
            client_id=request.client_id,
            document_id=request.document_id,
            query=request.query,
            rag_processor=processor.process_rag_query,
            chunk_size=request.chunk_size,
            enable_progress_updates=request.enable_progress_updates,
        )

        return RAGTaskResponse(
            task_id=task_id, status="started", message="RAG query processing started"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start async RAG query: {e}")
        raise SystemException(
            message="Failed to start async RAG query", error_type="general"
        ) from e


@router.get("/query/async/{task_id}", response_model=dict[str, Any])
async def get_async_query_status(
    task_id: str,
    client_id: str,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> Any:
    """Get the status of an async RAG query."""
    try:
        status_info = await ws_manager.get_rag_task_status(client_id, task_id)

        if status_info is None:
            raise ResourceNotFoundException(
                resource_type="rag_task",
                message=f"RAG task {task_id} not found or not accessible",
            )

        return status_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get RAG task status: {e}")
        raise SystemException(
            message="Failed to retrieve RAG task status", error_type="general"
        ) from e


@router.delete("/query/async/{task_id}", response_model=RAGTaskResponse)
async def cancel_async_query(
    task_id: str,
    client_id: str,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> Any:
    """Cancel a running async RAG query."""
    try:
        success = await ws_manager.cancel_rag_task(client_id, task_id)

        if not success:
            raise ResourceNotFoundException(
                resource_type="rag_task",
                message=f"RAG task {task_id} not found, not accessible, or already completed",
            )

        return RAGTaskResponse(
            task_id=task_id,
            status="cancelled",
            message="RAG query cancelled successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel RAG task: {e}")
        raise SystemException(
            message="Failed to cancel RAG task", error_type="general"
        ) from e


def _validate_websocket_message(data: dict) -> str:
    """
    Validate WebSocket message structure and extract type.

    Args:
        data: Received JSON message

    Returns:
        message_type string

    Raises:
        ValueError: Missing or invalid message type
    """
    message_type = data.get("type")
    if not message_type or not isinstance(message_type, str):
        raise ValueError("Invalid or missing 'type' field in message")
    return message_type


async def _handle_websocket_message(
    data: dict,
    client_id: str,
    websocket: WebSocket,
    ws_manager: WebSocketManager,
) -> None:
    """
    Route and handle WebSocket message based on type.

    Args:
        data: Received JSON message
        client_id: Client identifier
        websocket: WebSocket connection
        ws_manager: WebSocket manager
    """
    message_type = data.get("type")

    if message_type == "ping":
        await websocket.send_json({"type": "pong", "timestamp": time.time()})

    elif message_type == "task_status":
        task_id = data.get("task_id")
        if task_id:
            status_info = await ws_manager.get_rag_task_status(client_id, task_id)
            await websocket.send_json(
                {
                    "type": "task_status_response",
                    "task_id": task_id,
                    "status": status_info,
                }
            )

    elif message_type == "cancel_task":
        task_id = data.get("task_id")
        if task_id:
            success = await ws_manager.cancel_rag_task(client_id, task_id)
            await websocket.send_json(
                {
                    "type": "task_cancelled",
                    "task_id": task_id,
                    "success": success,
                }
            )

    else:
        await websocket.send_json(
            {
                "type": "error",
                "message": f"Unknown message type: {message_type}",
            }
        )


@router.websocket("/stream")
async def websocket_rag_endpoint(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> None:
    """WebSocket endpoint for RAG streaming operations."""
    client_id = f"rag_client_{int(time.time() * 1000)}"

    try:
        await ws_manager.connect(websocket, client_id)

        while True:
            data = await websocket.receive_json()
            await _handle_websocket_message(data, client_id, websocket, ws_manager)

    except WebSocketDisconnect:
        logger.info(f"RAG WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"RAG WebSocket error for client {client_id}: {e}")
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.close(code=1011)
    finally:
        ws_manager.disconnect(client_id)


@router.get("/stream/stats", response_model=dict[str, Any])
async def get_streaming_stats(
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> Any:
    """Get RAG streaming statistics."""
    try:
        stats = ws_manager.get_stats()
        return {"websocket_stats": stats, "timestamp": time.time()}

    except Exception as e:
        logger.error(f"Failed to get streaming stats: {e}")
        raise SystemException(
            message="Failed to retrieve streaming statistics", error_type="general"
        ) from e


@router.post("/query/hybrid", response_model=RAGQueryResponse)
async def hybrid_query_document(
    query_request: RAGQueryRequest,
    client_id: str | None = None,
    controller: LibraryController = Depends(get_library_controller),
    rag_service: EnhancedRAGService = Depends(require_rag_service),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> Any:
    """Hybrid RAG query that falls back to sync if WebSocket not available."""
    try:
        # If client_id provided and connected, use async streaming
        if client_id and client_id in ws_manager.active_connections:
            processor = RAGStreamingProcessor(ws_manager, controller, rag_service)

            task_id = await ws_manager.start_rag_stream(
                client_id=client_id,
                document_id=query_request.document_id,
                query=query_request.query,
                rag_processor=processor.process_rag_query,
                enable_progress_updates=False,  # Return response immediately
            )

            # Wait for completion (with timeout)
            timeout_seconds = 30
            start_time = time.time()

            while time.time() - start_time < timeout_seconds:
                task_status = await ws_manager.get_rag_task_status(client_id, task_id)
                if task_status and task_status["status"] == "completed":
                    return RAGQueryResponse(
                        query=query_request.query,
                        response=task_status["result"],
                        document_id=query_request.document_id,
                        from_cache=False,
                        processing_time_ms=task_status.get("processing_time_ms", 0),
                    )
                elif task_status and task_status["status"] == "failed":
                    raise SystemException(
                        message=f"Async RAG query failed: {task_status.get('error', 'Unknown error')}",
                        error_type="external_service",
                    )

                await asyncio.sleep(0.1)

            # Timeout - cancel task and fall back to sync
            await ws_manager.cancel_rag_task(client_id, task_id)
            logger.warning(
                f"Async RAG query timeout, falling back to sync for document {query_request.document_id}"
            )

        # Fall back to synchronous processing
        validate_document_access(query_request.document_id, controller)

        index_status = controller.get_index_status(query_request.document_id)
        if not index_status.get("can_query", False):
            raise ErrorTemplates.index_not_ready(query_request.document_id)

        start_time = time.time()
        response = controller.query_document(
            query_request.document_id, query_request.query
        )
        processing_time = (time.time() - start_time) * 1000

        if response is None:
            raise SystemException(
                message="RAG query processing failed", error_type="external_service"
            )

        return RAGQueryResponse(
            query=query_request.query,
            response=response,
            document_id=query_request.document_id,
            from_cache=False,
            processing_time_ms=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hybrid RAG query failed: {e}")
        raise SystemException(
            message="RAG query processing failed", error_type="external_service"
        ) from e
