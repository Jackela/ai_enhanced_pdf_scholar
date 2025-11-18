from typing import Any

"""
Upload Resumption Service
Service for handling interrupted upload resumption with persistent state tracking.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID

import aiofiles

from backend.api.streaming_models import (
    UploadResumeRequest,
    UploadSession,
    UploadStatus,
)

logger = logging.getLogger(__name__)


class UploadResumptionService:
    """
    Service for handling upload interruption and resumption.

    Features:
    - Persistent session state storage
    - Chunk tracking and validation
    - Automatic cleanup of stale sessions
    - Resume capability after network interruptions
    - Integrity validation on resume
    """

    def __init__(
        self,
        state_dir: Path,
        max_resume_age_hours: int = 24,
        cleanup_interval_minutes: int = 60,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True, parents=True)

        self.max_resume_age_hours = max_resume_age_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes

        # In-memory cache of resumable sessions
        self.resumable_sessions: dict[UUID, dict] = {}

        # Cleanup task
        self._cleanup_task: asyncio.Task | None = None
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_sessions())

    async def _cleanup_stale_sessions(self) -> None:
        """Periodically clean up stale resumable sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                await self._cleanup_expired_resume_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resumption cleanup task: {e}")

    async def save_session_state(self, session: UploadSession) -> None:
        """
        Save upload session state for potential resumption.

        Args:
            session: Upload session to save
        """
        try:
            state_file = self.state_dir / f"{session.session_id}.json"

            # Create resumption state
            state = {
                "session_id": str(session.session_id),
                "filename": session.filename,
                "content_type": session.content_type,
                "total_size": session.total_size,
                "chunk_size": session.chunk_size,
                "total_chunks": session.total_chunks,
                "uploaded_chunks": session.uploaded_chunks,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "temp_file_path": session.temp_file_path,
                "expected_hash": session.expected_hash,
                "actual_hash": session.actual_hash,
                "metadata": session.metadata,
                "error_message": session.error_message,
                "save_timestamp": time.time(),
            }

            # Save to file
            async with aiofiles.open(state_file, "w") as f:
                await f.write(json.dumps(state, indent=2))

            # Cache in memory
            self.resumable_sessions[session.session_id] = state

            logger.debug(f"Session state saved for resumption: {session.session_id}")

        except Exception as e:
            logger.error(f"Failed to save session state {session.session_id}: {e}")

    async def load_session_state(self, session_id: UUID) -> dict | None:
        """
        Load saved session state for resumption.

        Args:
            session_id: Session ID to load

        Returns:
            Optional[Dict]: Loaded session state or None if not found
        """
        try:
            # Check memory cache first
            if session_id in self.resumable_sessions:
                return self.resumable_sessions[session_id]

            # Load from file
            state_file = self.state_dir / f"{session_id}.json"
            if not state_file.exists():
                return None

            async with aiofiles.open(state_file) as f:
                content = await f.read()
                state = json.loads(content)

            # Validate state age
            save_time = state.get("save_timestamp", 0)
            age_hours = (time.time() - save_time) / 3600

            if age_hours > self.max_resume_age_hours:
                logger.info(f"Session state expired ({age_hours:.1f}h): {session_id}")
                await self._cleanup_session_state(session_id)
                return None

            # Cache in memory
            self.resumable_sessions[session_id] = state

            return state

        except Exception as e:
            logger.error(f"Failed to load session state {session_id}: {e}")
            return None

    async def is_session_resumable(self, session_id: UUID) -> bool:
        """
        Check if a session can be resumed.

        Args:
            session_id: Session ID to check

        Returns:
            bool: True if session can be resumed
        """
        state = await self.load_session_state(session_id)

        if not state:
            return False

        # Check if temp file still exists
        temp_file_path = state.get("temp_file_path")
        if not temp_file_path or not Path(temp_file_path).exists():
            logger.info(f"Temp file missing for session {session_id}")
            return False

        # Check if session was in progress
        status = state.get("status")
        if status not in ["uploading", "paused", "failed"]:
            return False

        # Check file integrity
        try:
            temp_file = Path(temp_file_path)
            expected_size = state.get("uploaded_chunks", 0) * state.get("chunk_size", 0)
            actual_size = temp_file.stat().st_size

            # Allow some variance for the last chunk
            if actual_size < expected_size - state.get("chunk_size", 0):
                logger.warning(
                    f"Temp file size mismatch for session {session_id}: {actual_size} < {expected_size}"
                )
                return False

        except Exception as e:
            logger.error(f"Error checking temp file for session {session_id}: {e}")
            return False

        return True

    async def resume_upload_session(
        self, resume_request: UploadResumeRequest
    ) -> UploadSession | None:
        """
        Resume an interrupted upload session.

        Args:
            resume_request: Resume request parameters

        Returns:
            Optional[UploadSession]: Resumed session or None if cannot resume
        """
        try:
            # Check if session is resumable
            if not await self.is_session_resumable(resume_request.session_id):
                logger.info(f"Session {resume_request.session_id} is not resumable")
                return None

            # Load session state
            state = await self.load_session_state(resume_request.session_id)
            if not state:
                return None

            # Validate chunk consistency if specified
            if resume_request.last_chunk_id is not None:
                expected_chunks = resume_request.last_chunk_id + 1
                if expected_chunks != state.get("uploaded_chunks", 0):
                    logger.warning(
                        f"Chunk count mismatch in resume request: "
                        f"expected {expected_chunks}, saved {state.get('uploaded_chunks', 0)}"
                    )
                    # Use the minimum to be safe
                    state["uploaded_chunks"] = min(
                        expected_chunks, state.get("uploaded_chunks", 0)
                    )

            # Validate and potentially truncate temp file
            await self._validate_and_fix_temp_file(state)

            # Recreate upload session
            session = UploadSession(
                session_id=UUID(state["session_id"]),
                filename=state["filename"],
                content_type=state["content_type"],
                total_size=state["total_size"],
                chunk_size=state["chunk_size"],
                total_chunks=state["total_chunks"],
                uploaded_chunks=state["uploaded_chunks"],
                client_id=resume_request.client_id,  # Use new client ID
                status=UploadStatus.UPLOADING,  # Reset to uploading
                created_at=datetime.fromisoformat(state["created_at"]),
                updated_at=datetime.utcnow(),
                temp_file_path=state["temp_file_path"],
                expected_hash=state.get("expected_hash"),
                actual_hash=state.get("actual_hash"),
                metadata=state.get("metadata", {}),
                error_message=None,  # Clear previous error
            )

            logger.info(
                f"Upload session resumed: {session.session_id} "
                f"({session.uploaded_chunks}/{session.total_chunks} chunks)"
            )

            return session

        except Exception as e:
            logger.error(
                f"Failed to resume upload session {resume_request.session_id}: {e}"
            )
            return None

    async def _validate_and_fix_temp_file(self, state: dict) -> None:
        """
        Validate temporary file and fix if needed.

        Args:
            state: Session state dictionary
        """
        try:
            temp_file_path = state["temp_file_path"]
            if not temp_file_path or not Path(temp_file_path).exists():
                raise ValueError("Temporary file not found")

            temp_file = Path(temp_file_path)
            current_size = temp_file.stat().st_size
            uploaded_chunks = state["uploaded_chunks"]
            chunk_size = state["chunk_size"]

            # Calculate expected size
            expected_size = uploaded_chunks * chunk_size

            # If file is larger than expected, truncate it
            if current_size > expected_size:
                logger.info(
                    f"Truncating temp file from {current_size} to {expected_size} bytes "
                    f"for session {state['session_id']}"
                )

                async with aiofiles.open(temp_file_path, "r+b") as f:
                    await f.truncate(expected_size)

            # If file is smaller, adjust chunk count
            elif current_size < expected_size:
                # Calculate actual chunks based on file size
                actual_chunks = current_size // chunk_size
                logger.info(
                    f"Adjusting chunk count from {uploaded_chunks} to {actual_chunks} "
                    f"for session {state['session_id']}"
                )
                state["uploaded_chunks"] = actual_chunks

        except Exception as e:
            logger.error(
                f"Failed to validate temp file for session {state['session_id']}: {e}"
            )
            raise

    async def get_resumable_sessions(self, client_id: str | None = None) -> list[dict]:
        """
        Get list of resumable sessions, optionally filtered by client.

        Args:
            client_id: Optional client ID filter

        Returns:
            List[Dict]: List of resumable session information
        """
        resumable = []

        try:
            # Scan state directory for session files
            for state_file in self.state_dir.glob("*.json"):
                try:
                    session_id = UUID(state_file.stem)

                    if await self.is_session_resumable(session_id):
                        state = await self.load_session_state(session_id)
                        if state:
                            # Create resume info
                            resume_info = {
                                "session_id": state["session_id"],
                                "filename": state["filename"],
                                "total_size": state["total_size"],
                                "uploaded_chunks": state["uploaded_chunks"],
                                "total_chunks": state["total_chunks"],
                                "progress_percentage": (
                                    state["uploaded_chunks"] / state["total_chunks"]
                                )
                                * 100,
                                "created_at": state["created_at"],
                                "updated_at": state["updated_at"],
                                "age_hours": (
                                    time.time() - state.get("save_timestamp", 0)
                                )
                                / 3600,
                            }
                            resumable.append(resume_info)

                except (ValueError, KeyError) as e:
                    logger.debug(f"Skipping invalid state file {state_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning resumable sessions: {e}")

        return resumable

    async def _cleanup_session_state(self, session_id: UUID) -> None:
        """
        Clean up state files and data for a specific session.

        Args:
            session_id: Session ID to clean up
        """
        try:
            # Remove from memory cache
            self.resumable_sessions.pop(session_id, None)

            # Remove state file
            state_file = self.state_dir / f"{session_id}.json"
            if state_file.exists():
                state_file.unlink()
                logger.debug(f"Removed state file: {state_file}")

            # Note: Temp file cleanup is handled by the main upload service

        except Exception as e:
            logger.error(f"Failed to cleanup session state {session_id}: {e}")

    async def _cleanup_expired_resume_data(self) -> None:
        """Clean up expired resumption data."""
        try:
            current_time = time.time()
            expired_sessions = []

            # Check all state files
            for state_file in self.state_dir.glob("*.json"):
                try:
                    async with aiofiles.open(state_file) as f:
                        content = await f.read()
                        state = json.loads(content)

                    save_time = state.get("save_timestamp", 0)
                    age_hours = (current_time - save_time) / 3600

                    if age_hours > self.max_resume_age_hours:
                        session_id = UUID(state_file.stem)
                        expired_sessions.append(session_id)

                        # Also clean up temp file if it exists
                        temp_file_path = state.get("temp_file_path")
                        if temp_file_path and Path(temp_file_path).exists():
                            try:
                                Path(temp_file_path).unlink()
                                logger.info(
                                    f"Cleaned up expired temp file: {temp_file_path}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to remove temp file {temp_file_path}: {e}"
                                )

                except Exception as e:
                    logger.debug(f"Error processing state file {state_file}: {e}")
                    # Consider the file corrupted, add to cleanup
                    try:
                        session_id = UUID(state_file.stem)
                        expired_sessions.append(session_id)
                    except ValueError:
                        # Invalid filename, remove directly
                        try:
                            state_file.unlink()
                            logger.info(f"Removed corrupted state file: {state_file}")
                        except Exception:
                            pass

            # Clean up expired sessions
            for session_id in expired_sessions:
                await self._cleanup_session_state(session_id)
                logger.info(f"Cleaned up expired resumable session: {session_id}")

        except Exception as e:
            logger.error(f"Error during resume data cleanup: {e}")

    async def delete_resumable_session(self, session_id: UUID) -> bool:
        """
        Manually delete a resumable session.

        Args:
            session_id: Session ID to delete

        Returns:
            bool: True if deleted successfully
        """
        try:
            await self._cleanup_session_state(session_id)
            logger.info(f"Manually deleted resumable session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete resumable session {session_id}: {e}")
            return False

    async def cleanup(self) -> None:
        """Clean up all resources and stop background tasks."""
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Clear memory cache
        self.resumable_sessions.clear()

        logger.info("Upload resumption service cleaned up")
