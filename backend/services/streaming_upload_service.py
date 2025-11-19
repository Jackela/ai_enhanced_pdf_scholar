"""
Streaming Upload Service
Memory-efficient file upload service with chunked processing and progress tracking.
"""

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union, Any
from uuid import UUID

import aiofiles
import psutil

from backend.api.streaming_models import (
    StreamingUploadRequest,
    StreamingValidationResult,
    UploadMemoryStats,
    UploadProgress,
    UploadSession,
    UploadStatus,
)

logger = logging.getLogger(__name__)


class StreamingUploadService:
    """
    Memory-efficient streaming upload service with chunked processing.

    Features:
    - Chunked file upload with configurable chunk sizes
    - Real-time progress tracking via WebSocket
    - Memory usage monitoring and limiting
    - Upload resumption after interruptions
    - Concurrent upload management with backpressure
    - Streaming validation of file content
    """

    def __init__(
        self,
        upload_dir: Path,
        max_concurrent_uploads: int = 5,
        memory_limit_mb: float = 500.0,
        session_timeout_minutes: int = 60,
        cleanup_interval_seconds: int = 300,
    ) -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True, parents=True)

        # Configuration
        self.max_concurrent_uploads = max_concurrent_uploads
        self.memory_limit_mb = memory_limit_mb
        self.session_timeout_minutes = session_timeout_minutes
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # Active sessions tracking
        self.active_sessions: dict[UUID, UploadSession] = {}
        self.session_locks: dict[UUID, asyncio.Lock] = {}
        self.active_uploads: set[UUID] = set[str]()

        # Memory monitoring
        self.process = psutil.Process()
        self.peak_memory_mb: float = 0.0

        # Chunk processing statistics
        self.chunk_stats: dict[UUID, dict[str, Union[int, float]]] = {}

        # Background cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

    async def _cleanup_expired_sessions(self) -> None:
        """Periodically clean up expired upload sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def _cleanup_expired(self) -> None:
        """Clean up expired sessions and temporary files."""
        current_time = datetime.utcnow()
        expired_sessions = []

        for session_id, session in self.active_sessions.items():
            session_age = current_time - session.created_at
            if session_age > timedelta(minutes=self.session_timeout_minutes):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            logger.info(f"Cleaning up expired session: {session_id}")
            await self._cleanup_session(session_id, "Session expired")

    async def _cleanup_session(self, session_id: UUID, reason: str = "Cleanup") -> None:
        """Clean up a specific upload session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]

            # Remove temporary file
            if session.temp_file_path:
                try:
                    temp_path = Path(session.temp_file_path)
                    if temp_path.exists():
                        temp_path.unlink()
                        logger.info(f"Removed temp file: {session.temp_file_path}")
                except Exception as e:
                    logger.error(
                        f"Failed to remove temp file {session.temp_file_path}: {e}"
                    )

            # Clean up tracking data
            self.active_sessions.pop(session_id, None)
            self.session_locks.pop(session_id, None)
            self.active_uploads.discard(session_id)
            self.chunk_stats.pop(session_id, None)

            logger.info(f"Session {session_id} cleaned up: {reason}")

    async def initiate_upload(
        self,
        request: StreamingUploadRequest,
        websocket_manager=None,
    ) -> UploadSession:
        """
        Initiate a new streaming upload session.

        Args:
            request: Upload request parameters
            websocket_manager: WebSocket manager for progress updates

        Returns:
            UploadSession: Created upload session

        Raises:
            ValueError: If request parameters are invalid
            RuntimeError: If system resources are insufficient
        """
        # Check concurrent upload limits
        if len(self.active_uploads) >= self.max_concurrent_uploads:
            raise RuntimeError(
                f"Maximum concurrent uploads ({self.max_concurrent_uploads}) exceeded. "
                "Please wait for an existing upload to complete."
            )

        # Check memory availability
        current_memory = await self._get_memory_usage_mb()
        if current_memory > self.memory_limit_mb * 0.8:
            raise RuntimeError(
                f"Memory usage ({current_memory:.1f}MB) approaching limit ({self.memory_limit_mb}MB). "
                "Please wait for uploads to complete."
            )

        # Calculate optimal chunk size and total chunks
        optimal_chunk_size = self._calculate_optimal_chunk_size(
            request.file_size, request.chunk_size
        )
        total_chunks = (
            request.file_size + optimal_chunk_size - 1
        ) // optimal_chunk_size

        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".tmp", prefix=f"upload_{request.client_id}_", dir=self.upload_dir
        )
        os.close(temp_fd)  # Close the file descriptor, we'll use aiofiles

        # Create upload session
        session = UploadSession(
            filename=request.filename,
            content_type=request.content_type,
            total_size=request.file_size,
            chunk_size=optimal_chunk_size,
            total_chunks=total_chunks,
            client_id=request.client_id,
            temp_file_path=temp_path,
            expected_hash=request.expected_hash,
            metadata={
                "title": request.title,
                "check_duplicates": request.check_duplicates,
                "auto_build_index": request.auto_build_index,
            },
        )

        # Register session
        self.active_sessions[session.session_id] = session
        self.session_locks[session.session_id] = asyncio.Lock()
        self.chunk_stats[session.session_id] = {
            "start_time": time.time(),
            "uploaded_bytes": 0,
            "upload_speed_bps": 0.0,
        }

        # Send initial progress update
        if websocket_manager:
            await self._send_progress_update(session, websocket_manager)

        logger.info(
            f"Upload session initiated: {session.session_id} "
            f"({request.filename}, {request.file_size} bytes, {total_chunks} chunks)"
        )

        return session

    def _calculate_optimal_chunk_size(
        self, file_size: int, requested_chunk_size: int
    ) -> int:
        """
        Calculate optimal chunk size based on file size and system resources.

        Args:
            file_size: Total file size in bytes
            requested_chunk_size: Client-requested chunk size

        Returns:
            int: Optimal chunk size in bytes
        """
        # Base constraints
        min_chunk_size = 1024 * 1024  # 1MB minimum
        max_chunk_size = 16 * 1024 * 1024  # 16MB maximum

        # Adjust based on file size
        if file_size < 10 * 1024 * 1024:  # < 10MB
            optimal_size = min(requested_chunk_size, 2 * 1024 * 1024)  # Max 2MB
        elif file_size < 100 * 1024 * 1024:  # < 100MB
            optimal_size = min(requested_chunk_size, 8 * 1024 * 1024)  # Max 8MB
        else:  # >= 100MB
            optimal_size = requested_chunk_size  # Use requested size

        # Apply constraints
        optimal_size = max(min_chunk_size, min(optimal_size, max_chunk_size))

        # Ensure we don't have too many chunks (max 1000)
        max_chunks = 1000
        if file_size // optimal_size > max_chunks:
            optimal_size = (file_size + max_chunks - 1) // max_chunks
            optimal_size = min(optimal_size, max_chunk_size)

        return optimal_size

    async def process_chunk(
        self,
        session_id: UUID,
        chunk_id: int,
        chunk_data: bytes,
        chunk_offset: int,
        is_final: bool = False,
        expected_checksum: str | None = None,
        websocket_manager=None,
    ) -> tuple[bool, str]:
        """
        Process an uploaded chunk with validation and progress tracking.

        Args:
            session_id: Upload session ID
            chunk_id: Sequential chunk identifier
            chunk_data: Chunk binary data
            chunk_offset: Chunk offset in original file
            is_final: Whether this is the last chunk
            expected_checksum: Expected chunk checksum
            websocket_manager: WebSocket manager for progress updates

        Returns:
            Tuple[bool, str]: (success, message)

        Raises:
            ValueError: If chunk data is invalid
            RuntimeError: If session not found or system error
        """
        # Validate session
        if session_id not in self.active_sessions:
            raise RuntimeError(f"Upload session {session_id} not found or expired")

        session = self.active_sessions[session_id]

        # Acquire session lock
        async with self.session_locks[session_id]:
            try:
                # Validate chunk
                if len(chunk_data) == 0:
                    return False, "Empty chunk data"

                if chunk_id != session.uploaded_chunks:
                    return (
                        False,
                        f"Expected chunk {session.uploaded_chunks}, got {chunk_id}",
                    )

                # Validate chunk size (except for final chunk)
                if not is_final and len(chunk_data) != session.chunk_size:
                    return (
                        False,
                        f"Invalid chunk size: expected {session.chunk_size}, got {len(chunk_data)}",
                    )

                # Validate checksum if provided
                if expected_checksum:
                    actual_checksum = hashlib.sha256(chunk_data).hexdigest()
                    if actual_checksum != expected_checksum:
                        return (
                            False,
                            f"Chunk checksum mismatch: expected {expected_checksum}, got {actual_checksum}",
                        )

                # Check memory usage before processing
                current_memory = await self._get_memory_usage_mb()
                if current_memory > self.memory_limit_mb:
                    session.status = UploadStatus.PAUSED
                    return (
                        False,
                        f"Memory limit exceeded: {current_memory:.1f}MB > {self.memory_limit_mb}MB",
                    )

                # Write chunk to temporary file
                async with aiofiles.open(session.temp_file_path, "ab") as f:
                    await f.write(chunk_data)

                # Update session progress
                session.uploaded_chunks += 1
                session.updated_at = datetime.utcnow()

                # Update statistics
                stats = self.chunk_stats[session_id]
                stats["uploaded_bytes"] += len(chunk_data)

                # Calculate upload speed
                elapsed_time = time.time() - stats["start_time"]
                if elapsed_time > 0:
                    stats["upload_speed_bps"] = stats["uploaded_bytes"] / elapsed_time

                # Update status
                if is_final or session.uploaded_chunks == session.total_chunks:
                    session.status = UploadStatus.VALIDATING
                    await self._finalize_upload(session, websocket_manager)
                else:
                    session.status = UploadStatus.UPLOADING

                # Send progress update
                if websocket_manager:
                    await self._send_progress_update(session, websocket_manager)

                logger.debug(
                    f"Chunk {chunk_id} processed for session {session_id} "
                    f"({len(chunk_data)} bytes, {session.uploaded_chunks}/{session.total_chunks})"
                )

                return True, "Chunk processed successfully"

            except Exception as e:
                session.status = UploadStatus.FAILED
                session.error_message = f"Chunk processing failed: {str(e)}"
                logger.error(
                    f"Failed to process chunk {chunk_id} for session {session_id}: {e}"
                )

                # Send error update
                if websocket_manager:
                    await self._send_progress_update(session, websocket_manager)

                return False, str(e)

    async def _finalize_upload(
        self, session: UploadSession, websocket_manager=None
    ) -> None:
        """
        Finalize upload by validating file integrity and preparing for processing.

        Args:
            session: Upload session to finalize
            websocket_manager: WebSocket manager for updates
        """
        try:
            # Calculate file hash for integrity check
            if session.temp_file_path:
                session.actual_hash = await self._calculate_file_hash(
                    session.temp_file_path
                )

                # Verify hash if expected hash was provided
                if (
                    session.expected_hash
                    and session.actual_hash != session.expected_hash
                ):
                    session.status = UploadStatus.FAILED
                    session.error_message = "File integrity check failed: hash mismatch"
                    return

                # Validate file format
                validation_result = await self._validate_uploaded_file(
                    session.temp_file_path
                )
                if not validation_result.is_valid:
                    session.status = UploadStatus.FAILED
                    session.error_message = f"File validation failed: {', '.join(validation_result.validation_errors)}"
                    return

                # Update metadata with validation results
                session.metadata.update(
                    {
                        "pdf_version": validation_result.pdf_version,
                        "page_count": validation_result.page_count,
                        "is_encrypted": validation_result.is_encrypted,
                        "detected_mime_type": validation_result.detected_mime_type,
                    }
                )

            session.status = UploadStatus.COMPLETED
            session.updated_at = datetime.utcnow()

            # Remove from active uploads
            self.active_uploads.discard(session.session_id)

            logger.info(f"Upload finalized successfully: {session.session_id}")

        except Exception as e:
            session.status = UploadStatus.FAILED
            session.error_message = f"Upload finalization failed: {str(e)}"
            logger.error(f"Failed to finalize upload {session.session_id}: {e}")

        # Send final progress update
        if websocket_manager:
            await self._send_progress_update(session, websocket_manager)

    async def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of uploaded file in streaming fashion.

        Args:
            file_path: Path to the file

        Returns:
            str: SHA-256 hash as hex string
        """
        hash_obj = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    async def _validate_uploaded_file(
        self, file_path: str
    ) -> StreamingValidationResult:
        """
        Validate uploaded file format and content.

        Args:
            file_path: Path to the uploaded file

        Returns:
            StreamingValidationResult: Validation results
        """
        result = StreamingValidationResult()

        try:
            # Read file signature (first 1024 bytes)
            async with aiofiles.open(file_path, "rb") as f:
                signature_bytes = await f.read(1024)

            # Check PDF signature
            if signature_bytes.startswith(b"%PDF-"):
                result.is_pdf = True
                result.detected_mime_type = "application/pdf"
                result.file_signature = signature_bytes[:8].decode(
                    "ascii", errors="ignore"
                )

                # Extract PDF version
                version_match = signature_bytes[:20].decode("ascii", errors="ignore")
                if "-" in version_match:
                    version_part = version_match.split("-")[1][:3]
                    if version_part.replace(".", "").isdigit():
                        result.pdf_version = version_part

                # Basic PDF validation
                result.is_valid = True

                # TODO: Add more detailed PDF validation
                # - Check for encryption
                # - Count pages
                # - Validate internal structure

            else:
                result.is_valid = False
                result.validation_errors.append("File is not a valid PDF")
                result.detected_mime_type = "unknown"

        except Exception as e:
            result.is_valid = False
            result.validation_errors.append(f"File validation error: {str(e)}")

        return result

    async def _send_progress_update(
        self, session: UploadSession, websocket_manager
    ) -> None:
        """
        Send progress update via WebSocket.

        Args:
            session: Upload session
            websocket_manager: WebSocket manager instance
        """
        try:
            stats = self.chunk_stats.get(session.session_id, {})
            uploaded_bytes = stats.get("uploaded_bytes", 0)
            upload_speed = stats.get("upload_speed_bps", 0.0)

            progress = UploadProgress(
                session_id=session.session_id,
                status=session.status,
                uploaded_bytes=uploaded_bytes,
                total_bytes=session.total_size,
                uploaded_chunks=session.uploaded_chunks,
                total_chunks=session.total_chunks,
                progress_percentage=(
                    (uploaded_bytes / session.total_size) * 100
                    if session.total_size > 0
                    else 0
                ),
                upload_speed_bps=upload_speed,
                estimated_time_remaining=self._calculate_eta(session, upload_speed),
                current_chunk=session.uploaded_chunks,
                message=self._get_status_message(session),
                error_details=session.error_message,
            )

            # Send to client via WebSocket
            await websocket_manager.send_upload_progress(
                session.client_id, progress.dict[str, Any]()
            )

        except Exception as e:
            logger.error(
                f"Failed to send progress update for session {session.session_id}: {e}"
            )

    def _calculate_eta(self, session: UploadSession, upload_speed: float) -> int | None:
        """Calculate estimated time remaining."""
        if upload_speed <= 0:
            return None

        stats = self.chunk_stats.get(session.session_id, {})
        uploaded_bytes = stats.get("uploaded_bytes", 0)
        remaining_bytes = session.total_size - uploaded_bytes

        if remaining_bytes <= 0:
            return 0

        return int(remaining_bytes / upload_speed)

    def _get_status_message(self, session: UploadSession) -> str:
        """Get human-readable status message."""
        status_messages = {
            UploadStatus.INITIALIZING: "Initializing upload...",
            UploadStatus.UPLOADING: f"Uploading... {session.uploaded_chunks}/{session.total_chunks} chunks",
            UploadStatus.VALIDATING: "Validating file integrity...",
            UploadStatus.PROCESSING: "Processing document...",
            UploadStatus.COMPLETED: "Upload completed successfully",
            UploadStatus.FAILED: f"Upload failed: {session.error_message or 'Unknown error'}",
            UploadStatus.CANCELLED: "Upload cancelled",
            UploadStatus.PAUSED: "Upload paused due to resource constraints",
        }
        return status_messages.get(session.status, "Unknown status")

    async def cancel_upload(
        self, session_id: UUID, reason: str = "User cancelled"
    ) -> bool:
        """
        Cancel an active upload session.

        Args:
            session_id: Session to cancel
            reason: Cancellation reason

        Returns:
            bool: True if cancelled successfully
        """
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        session.status = UploadStatus.CANCELLED
        session.error_message = reason
        session.updated_at = datetime.utcnow()

        # Clean up session
        await self._cleanup_session(session_id, reason)

        logger.info(f"Upload session {session_id} cancelled: {reason}")
        return True

    async def get_session(self, session_id: UUID) -> UploadSession | None:
        """Get upload session by ID."""
        return self.active_sessions.get(session_id)

    async def get_memory_stats(self) -> UploadMemoryStats:
        """Get current memory usage statistics."""
        current_memory = await self._get_memory_usage_mb()
        self.peak_memory_mb = max(self.peak_memory_mb, current_memory)

        # Calculate temp files statistics
        temp_files_count = 0
        temp_files_size = 0

        for session in self.active_sessions.values():
            if session.temp_file_path and Path(session.temp_file_path).exists():
                temp_files_count += 1
                temp_files_size += Path(session.temp_file_path).stat().st_size

        # Get disk space
        disk_usage = psutil.disk_usage(str(self.upload_dir))
        available_mb = disk_usage.free / (1024 * 1024)

        return UploadMemoryStats(
            active_sessions=len(self.active_sessions),
            memory_usage_mb=current_memory,
            peak_memory_mb=self.peak_memory_mb,
            temp_files_count=temp_files_count,
            temp_files_size_mb=temp_files_size / (1024 * 1024),
            concurrent_uploads=len(self.active_uploads),
            memory_limit_mb=self.memory_limit_mb,
            disk_space_available_mb=available_mb,
        )

    async def _get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB."""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0

    async def cleanup(self) -> None:
        """Clean up all resources and stop background tasks."""
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Clean up all active sessions
        session_ids = list[Any](self.active_sessions.keys())
        for session_id in session_ids:
            await self._cleanup_session(session_id, "Service shutdown")

        logger.info("Streaming upload service cleaned up")


# WebSocket extension methods
async def send_upload_progress(
    websocket_manager, client_id: str, progress_data: dict[str, Any]
) -> None:
    """Send upload progress update via WebSocket."""
    await websocket_manager.send_personal_json(
        {
            "type": "upload_progress",
            "data": progress_data,
        },
        client_id,
    )


# Monkey patch WebSocket manager to add upload progress method
def extend_websocket_manager() -> None:
    """Extend WebSocket manager with upload-specific methods."""
    from backend.api.websocket_manager import WebSocketManager

    if not hasattr(WebSocketManager, "send_upload_progress"):
        WebSocketManager.send_upload_progress = send_upload_progress
