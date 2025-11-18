"""
Streaming Upload Models
Pydantic models for streaming file upload operations and progress tracking.
"""

import hashlib
import re
from datetime import datetime
from enum import Enum
from typing import Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class UploadStatus(str, Enum):
    """Upload status enumeration."""

    INITIALIZING = "initializing"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ChunkStatus(str, Enum):
    """Individual chunk processing status."""

    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    FAILED = "failed"


class StreamingChunk(BaseModel):
    """Individual file chunk for streaming upload."""

    chunk_id: int = Field(..., description="Sequential chunk identifier")
    data: bytes = Field(..., description="Chunk data content")
    size: int = Field(..., description="Chunk size in bytes")
    offset: int = Field(..., description="Chunk offset in the original file")
    is_final: bool = Field(default=False, description="Whether this is the last chunk")
    checksum: str | None = Field(None, description="Chunk SHA-256 checksum")

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, v: str | None, info) -> str | None:
        """Validate or generate chunk checksum."""
        if v is None and hasattr(info, "data"):
            # Generate checksum if not provided
            data = info.data.get("data")
            if data:
                return hashlib.sha256(data).hexdigest()
        return v

    class Config:
        arbitrary_types_allowed = True


class UploadSession(BaseModel):
    """Streaming upload session tracking."""

    session_id: UUID = Field(
        default_factory=uuid4, description="Unique session identifier"
    )
    filename: str = Field(
        ..., min_length=1, max_length=255, description="Original filename"
    )
    content_type: str = Field(default="application/pdf", description="File MIME type")
    total_size: int = Field(..., gt=0, description="Total file size in bytes")
    chunk_size: int = Field(
        default=8388608,
        gt=0,
        le=16777216,
        description="Chunk size (8MB default, 16MB max)",
    )
    total_chunks: int = Field(..., gt=0, description="Total number of chunks")
    uploaded_chunks: int = Field(
        default=0, ge=0, description="Number of uploaded chunks"
    )
    client_id: str = Field(..., description="WebSocket client ID for progress updates")
    status: UploadStatus = Field(
        default=UploadStatus.INITIALIZING, description="Current upload status"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Session creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update time"
    )
    error_message: str | None = Field(
        None, description="Error message if upload failed"
    )
    temp_file_path: str | None = Field(None, description="Temporary file path")
    expected_hash: str | None = Field(None, description="Expected file SHA-256 hash")
    actual_hash: str | None = Field(None, description="Calculated file SHA-256 hash")
    metadata: dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("total_chunks")
    @classmethod
    def validate_total_chunks(cls, v: int, info) -> int:
        """Validate total chunks calculation."""
        if hasattr(info, "data"):
            total_size = info.data.get("total_size")
            chunk_size = info.data.get("chunk_size")
            if total_size and chunk_size:
                expected = (total_size + chunk_size - 1) // chunk_size
                if v != expected:
                    raise ValueError(
                        f"Invalid total_chunks: expected {expected}, got {v}"
                    )
        return v


class UploadProgress(BaseModel):
    """Upload progress information."""

    session_id: UUID = Field(..., description="Upload session ID")
    status: UploadStatus = Field(..., description="Current upload status")
    uploaded_bytes: int = Field(..., ge=0, description="Bytes uploaded so far")
    total_bytes: int = Field(..., gt=0, description="Total file size")
    uploaded_chunks: int = Field(..., ge=0, description="Chunks uploaded")
    total_chunks: int = Field(..., gt=0, description="Total chunks")
    progress_percentage: float = Field(
        ..., ge=0, le=100, description="Upload progress percentage"
    )
    upload_speed_bps: float | None = Field(
        None, ge=0, description="Upload speed in bytes per second"
    )
    estimated_time_remaining: int | None = Field(
        None, ge=0, description="Estimated time remaining in seconds"
    )
    current_chunk: int | None = Field(None, description="Currently processing chunk")
    message: str | None = Field(None, description="Status message")
    error_details: str | None = Field(None, description="Error details if failed")


class StreamingUploadRequest(BaseModel):
    """Request model for initiating streaming upload."""

    filename: str = Field(
        ..., min_length=1, max_length=255, description="Original filename"
    )
    content_type: str = Field(default="application/pdf", description="File MIME type")
    file_size: int = Field(
        ..., gt=0, le=1073741824, description="File size in bytes (max 1GB)"
    )
    chunk_size: int = Field(
        default=8388608, gt=0, le=16777216, description="Preferred chunk size"
    )
    client_id: str = Field(..., min_length=1, description="WebSocket client ID")
    title: str | None = Field(None, max_length=500, description="Document title")
    check_duplicates: bool = Field(
        default=True, description="Check for duplicate documents"
    )
    auto_build_index: bool = Field(
        default=False, description="Auto-build vector index after upload"
    )
    expected_hash: str | None = Field(
        None, min_length=64, max_length=64, description="Expected SHA-256 hash"
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename format."""
        if not v.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported")
        # Remove dangerous characters
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ()"
        )
        if not all(c in safe_chars for c in v):
            raise ValueError("Filename contains invalid characters")
        return v

    @field_validator("expected_hash")
    @classmethod
    def validate_expected_hash(cls, v: str | None) -> str | None:
        """Validate SHA-256 hash format."""
        if v is not None:
            if not re.match(r"^[a-fA-F0-9]{64}$", v):
                raise ValueError("Invalid SHA-256 hash format")
        return v


class StreamingUploadResponse(BaseModel):
    """Response model for streaming upload initiation."""

    session_id: UUID = Field(..., description="Upload session ID")
    upload_url: str = Field(..., description="URL for chunk uploads")
    chunk_size: int = Field(..., description="Server-assigned chunk size")
    total_chunks: int = Field(..., description="Total number of chunks expected")
    expires_at: datetime = Field(..., description="Session expiration time")
    websocket_room: str = Field(..., description="WebSocket room for progress updates")


class ChunkUploadRequest(BaseModel):
    """Request model for individual chunk upload."""

    session_id: UUID = Field(..., description="Upload session ID")
    chunk_id: int = Field(..., ge=0, description="Sequential chunk number")
    chunk_size: int = Field(..., gt=0, description="Chunk size in bytes")
    chunk_offset: int = Field(..., ge=0, description="Chunk offset in original file")
    is_final: bool = Field(default=False, description="Whether this is the last chunk")
    checksum: str | None = Field(None, description="Chunk SHA-256 checksum")


class ChunkUploadResponse(BaseModel):
    """Response model for chunk upload."""

    success: bool = Field(..., description="Whether chunk upload succeeded")
    chunk_id: int = Field(..., description="Processed chunk ID")
    next_chunk_id: int | None = Field(None, description="Next expected chunk ID")
    upload_complete: bool = Field(
        default=False, description="Whether entire upload is complete"
    )
    message: str = Field(..., description="Response message")
    retry_after: int | None = Field(
        None, description="Seconds to wait before retry if failed"
    )


class UploadMemoryStats(BaseModel):
    """Memory usage statistics for upload operations."""

    active_sessions: int = Field(..., description="Number of active upload sessions")
    memory_usage_mb: float = Field(..., description="Current memory usage in MB")
    peak_memory_mb: float = Field(..., description="Peak memory usage in MB")
    temp_files_count: int = Field(..., description="Number of temporary files")
    temp_files_size_mb: float = Field(
        ..., description="Total size of temporary files in MB"
    )
    concurrent_uploads: int = Field(..., description="Number of concurrent uploads")
    memory_limit_mb: float | None = Field(None, description="Memory limit in MB")
    disk_space_available_mb: float = Field(
        ..., description="Available disk space in MB"
    )


class UploadCancellationRequest(BaseModel):
    """Request model for cancelling an upload."""

    session_id: UUID = Field(..., description="Upload session ID to cancel")
    reason: str | None = Field(None, max_length=200, description="Cancellation reason")


class UploadResumeRequest(BaseModel):
    """Request model for resuming an interrupted upload."""

    session_id: UUID = Field(..., description="Upload session ID to resume")
    client_id: str = Field(..., description="New WebSocket client ID")
    last_chunk_id: int | None = Field(
        None, description="Last successfully uploaded chunk"
    )


class StreamingValidationResult(BaseModel):
    """Result of streaming file validation."""

    is_valid: bool = Field(..., description="Whether file passed validation")
    detected_mime_type: str | None = Field(None, description="Detected MIME type")
    file_signature: str | None = Field(None, description="File signature/magic bytes")
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation error messages"
    )
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    is_pdf: bool = Field(default=False, description="Whether file is a valid PDF")
    pdf_version: str | None = Field(None, description="PDF version if detected")
    page_count: int | None = Field(None, description="Number of PDF pages")
    is_encrypted: bool = Field(default=False, description="Whether PDF is encrypted")
