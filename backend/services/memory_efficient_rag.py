"""
Memory-Efficient RAG Processing
Optimized RAG processing with streaming, chunking, and memory management.
"""

import asyncio
import gc
import logging
import weakref
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from backend.api.websocket_manager import RAGProgressType, WebSocketManager
from backend.services.async_task_manager import (
    MemoryMonitor,
)

logger = logging.getLogger(__name__)


class MemoryOptimizedRAGProcessor:
    """Memory-efficient RAG processor with streaming capabilities."""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        memory_limit_mb: float = 512.0,
        chunk_size: int = 512,
        enable_streaming: bool = True,
        gc_threshold: float = 0.8,
    ) -> None:
        self.ws_manager = ws_manager
        self.memory_limit_mb = memory_limit_mb
        self.chunk_size = chunk_size
        self.enable_streaming = enable_streaming
        self.gc_threshold = gc_threshold

        self.memory_monitor = MemoryMonitor()
        self._active_processors: Any = weakref.WeakSet()

    async def process_with_memory_management(
        self,
        query: str,
        document_id: int,
        task_id: str,
        cancellation_token: asyncio.Event,
        client_id: str,
        controller: Any,
        **kwargs,
    ) -> str:
        """Process RAG query with comprehensive memory management."""

        processor = RAGMemoryContext(
            processor=self,
            task_id=task_id,
            client_id=client_id,
            memory_limit_mb=self.memory_limit_mb,
        )

        self._active_processors.add(processor)

        try:
            async with processor:
                return await self._execute_rag_query(
                    processor,
                    query,
                    document_id,
                    task_id,
                    cancellation_token,
                    client_id,
                    controller,
                    **kwargs,
                )
        finally:
            self._active_processors.discard(processor)

    async def _execute_rag_query(
        self,
        processor: "RAGMemoryContext",
        query: str,
        document_id: int,
        task_id: str,
        cancellation_token: asyncio.Event,
        client_id: str,
        controller: Any,
        **kwargs,
    ) -> str:
        """Execute RAG query with streaming and memory monitoring."""

        try:
            # Stage 1: Initial validation and memory check
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.STARTED,
                5.0,
                "Starting memory-optimized RAG processing",
            )

            await processor.check_memory_pressure()

            if cancellation_token.is_set():
                return ""

            # Stage 2: Document access validation
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.PARSING,
                15.0,
                "Validating document access",
            )

            # Use controller to validate document
            try:
                document = controller.get_document_by_id(document_id)
                if not document:
                    raise ValueError(f"Document {document_id} not found")
            except Exception as e:
                raise ValueError(f"Failed to access document {document_id}: {e}") from e

            await processor.check_memory_pressure()

            if cancellation_token.is_set():
                return ""

            # Stage 3: Index status verification
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.INDEXING,
                30.0,
                "Checking vector index status",
            )

            index_status = controller.get_index_status(document_id)
            if not index_status.get("can_query", False):
                raise ValueError(
                    f"Vector index for document {document_id} is not ready for querying"
                )

            await processor.check_memory_pressure()

            if cancellation_token.is_set():
                return ""

            # Stage 4: Query processing with memory monitoring
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.QUERYING,
                50.0,
                "Executing RAG query with memory optimization",
            )

            # Process query in chunks to manage memory
            response = await self._process_query_with_chunking(
                controller, document_id, query, processor, cancellation_token
            )

            if not response:
                raise ValueError("RAG query returned empty response")

            if cancellation_token.is_set():
                return ""

            # Stage 5: Response streaming (if enabled)
            if self.enable_streaming and len(response) > self.chunk_size:
                await self._progress_update(
                    client_id,
                    task_id,
                    RAGProgressType.STREAMING_RESPONSE,
                    80.0,
                    f"Streaming response ({len(response)} characters)",
                )

                await self._stream_response(
                    response, client_id, task_id, cancellation_token
                )

            await processor.check_memory_pressure()

            # Final stage
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.COMPLETED,
                100.0,
                f"RAG processing completed ({processor.peak_memory_mb:.1f}MB peak)",
            )

            return response

        except asyncio.CancelledError:
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.ERROR,
                0.0,
                "RAG processing was cancelled",
            )
            raise
        except Exception as e:
            await self._progress_update(
                client_id,
                task_id,
                RAGProgressType.ERROR,
                0.0,
                f"RAG processing failed: {str(e)}",
            )
            raise

    async def _process_query_with_chunking(
        self,
        controller: Any,
        document_id: int,
        query: str,
        processor: "RAGMemoryContext",
        cancellation_token: asyncio.Event,
    ) -> str:
        """Process query with memory-efficient chunking."""

        # Perform the actual RAG query
        # Note: This is where we'd implement advanced chunking if the controller supported it
        # For now, we use the existing controller method with memory monitoring

        # Monitor memory before query
        await processor.check_memory_pressure()

        # Execute query (this might be memory intensive)
        response = await asyncio.to_thread(
            controller.query_document, document_id, query
        )

        # Monitor memory after query
        await processor.check_memory_pressure()

        # Force garbage collection if memory usage is high
        if processor.current_memory_mb > self.memory_limit_mb * 0.8:
            gc.collect()
            await asyncio.sleep(0.1)  # Allow GC to complete

        return response

    async def _stream_response(
        self,
        response: str,
        client_id: str,
        task_id: str,
        cancellation_token: asyncio.Event,
    ) -> None:
        """Stream response in chunks to the client."""

        if not self.enable_streaming:
            return

        # Split response into chunks
        chunks = [
            response[i : i + self.chunk_size]
            for i in range(0, len(response), self.chunk_size)
        ]

        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            if cancellation_token.is_set():
                break

            await self.ws_manager.send_rag_response_chunk(
                client_id, task_id, chunk, i, total_chunks
            )

            # Small delay to prevent overwhelming the client
            if i < len(chunks) - 1:  # Don't delay after the last chunk
                await asyncio.sleep(0.02)

    async def _progress_update(
        self,
        client_id: str,
        task_id: str,
        progress_type: RAGProgressType,
        percentage: float,
        message: str,
        stage_data: dict[str, Any] | None = None,
    ) -> None:
        """Send progress update with memory stats."""

        # Add memory information to stage data
        memory_stats = self.memory_monitor.get_memory_stats()
        enhanced_stage_data = {
            "memory_used_mb": memory_stats.used_mb,
            "memory_percentage": memory_stats.percentage,
            **(stage_data or {}),
        }

        await self.ws_manager.send_rag_progress_update(
            client_id, task_id, progress_type, percentage, message, enhanced_stage_data
        )

    def get_active_processor_count(self) -> int:
        """Get number of active processors."""
        return len(self._active_processors)

    def get_memory_stats(self) -> dict[str, Any]:
        """Get comprehensive memory statistics."""
        system_stats = self.memory_monitor.get_memory_stats()

        active_processors = list(self._active_processors)

        return {
            "system_memory": {
                "used_mb": system_stats.used_mb,
                "available_mb": system_stats.available_mb,
                "percentage": system_stats.percentage,
                "is_critical": system_stats.is_critical,
            },
            "processor_stats": {
                "active_count": len(active_processors),
                "memory_limit_mb": self.memory_limit_mb,
                "total_peak_mb": sum(p.peak_memory_mb for p in active_processors),
            },
            "configuration": {
                "chunk_size": self.chunk_size,
                "streaming_enabled": self.enable_streaming,
                "gc_threshold": self.gc_threshold,
            },
        }


class RAGMemoryContext:
    """Context manager for RAG processing with memory tracking."""

    def __init__(
        self,
        processor: MemoryOptimizedRAGProcessor,
        task_id: str,
        client_id: str,
        memory_limit_mb: float,
    ) -> None:
        self.processor = processor
        self.task_id = task_id
        self.client_id = client_id
        self.memory_limit_mb = memory_limit_mb

        self.start_memory_mb = 0.0
        self.peak_memory_mb = 0.0
        self.current_memory_mb = 0.0
        self.start_time = datetime.now()

    async def __aenter__(self) -> None:
        """Enter the memory context."""
        # Record initial memory usage
        memory_stats = self.processor.memory_monitor.get_memory_stats()
        self.start_memory_mb = memory_stats.used_mb
        self.current_memory_mb = self.start_memory_mb
        self.peak_memory_mb = self.start_memory_mb

        logger.debug(
            f"RAG context started for task {self.task_id} - Initial memory: {self.start_memory_mb:.1f}MB"
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the memory context with cleanup."""
        # Final memory measurement
        memory_stats = self.processor.memory_monitor.get_memory_stats()
        final_memory_mb = memory_stats.used_mb

        duration_seconds = (datetime.now() - self.start_time).total_seconds()

        logger.info(
            f"RAG context finished for task {self.task_id} - "
            f"Duration: {duration_seconds:.2f}s, "
            f"Peak memory: {self.peak_memory_mb:.1f}MB, "
            f"Final memory: {final_memory_mb:.1f}MB"
        )

        # Force garbage collection if needed
        if final_memory_mb > self.memory_limit_mb:
            gc.collect()
            await asyncio.sleep(0.1)

    async def check_memory_pressure(self) -> None:
        """Check for memory pressure and take action if needed."""
        memory_stats = self.processor.memory_monitor.get_memory_stats()
        self.current_memory_mb = memory_stats.used_mb

        # Update peak memory tracking
        if self.current_memory_mb > self.peak_memory_mb:
            self.peak_memory_mb = self.current_memory_mb

        # Check for memory pressure
        if memory_stats.is_critical:
            # Send warning to client
            await self.processor.ws_manager.send_memory_warning(
                self.client_id,
                {
                    "used_mb": memory_stats.used_mb,
                    "percentage": memory_stats.percentage,
                    "task_id": self.task_id,
                    "action": "critical_cleanup",
                },
            )

            # Force garbage collection
            gc.collect()
            await asyncio.sleep(0.1)

            # Re-check after cleanup
            post_gc_stats = self.processor.memory_monitor.get_memory_stats()
            if post_gc_stats.is_critical:
                raise MemoryError(
                    f"Critical memory pressure: {post_gc_stats.percentage:.1f}% used "
                    f"({post_gc_stats.used_mb:.1f}MB). Cannot continue processing."
                )

        # Check task-specific memory limit
        if self.memory_limit_mb and self.current_memory_mb > self.memory_limit_mb:
            logger.warning(
                f"Task {self.task_id} exceeded memory limit: "
                f"{self.current_memory_mb:.1f}MB > {self.memory_limit_mb:.1f}MB"
            )

            # Send warning to client
            await self.processor.ws_manager.send_memory_warning(
                self.client_id,
                {
                    "used_mb": self.current_memory_mb,
                    "limit_mb": self.memory_limit_mb,
                    "task_id": self.task_id,
                    "action": "task_limit_exceeded",
                },
            )


class StreamingRAGChunker:
    """Utility for chunking large responses for streaming."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    async def chunk_response(
        self, response: str, preserve_sentences: bool = True
    ) -> AsyncGenerator[str, None]:
        """Chunk response into streaming-friendly pieces."""

        if not response:
            return

        if len(response) <= self.chunk_size:
            yield response
            return

        position = 0
        while position < len(response):
            # Calculate chunk end position
            end_pos = position + self.chunk_size

            if preserve_sentences and end_pos < len(response):
                # Try to break at sentence boundary
                sentence_break = response.rfind(".", position, end_pos)
                if sentence_break > position:
                    end_pos = sentence_break + 1

            chunk = response[position:end_pos]
            yield chunk

            # Move position with overlap consideration
            if end_pos >= len(response):
                break

            position = max(end_pos - self.overlap, position + 1)

            # Allow for cancellation
            await asyncio.sleep(0)

    def calculate_chunks(self, text_length: int) -> int:
        """Calculate number of chunks for a given text length."""
        if text_length <= self.chunk_size:
            return 1

        effective_chunk_size = self.chunk_size - self.overlap
        return max(1, (text_length + effective_chunk_size - 1) // effective_chunk_size)
