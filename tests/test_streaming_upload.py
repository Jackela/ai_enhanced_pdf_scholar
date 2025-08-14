"""
Streaming Upload Tests
Comprehensive tests for memory-efficient streaming upload functionality.
"""

import asyncio
import hashlib
import tempfile
import time
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from backend.api.streaming_models import (
    StreamingUploadRequest,
    UploadStatus,
    UploadResumeRequest,
)
from backend.services.streaming_upload_service import StreamingUploadService
from backend.services.streaming_validation_service import StreamingValidationService
from backend.services.upload_resumption_service import UploadResumptionService
from backend.services.streaming_pdf_service import StreamingPDFProcessor


class MockWebSocketManager:
    """Mock WebSocket manager for testing."""

    def __init__(self):
        self.messages = []
        self.rooms = {}

    async def send_upload_progress(self, client_id: str, progress_data: dict):
        self.messages.append(("progress", client_id, progress_data))

    async def send_upload_status(self, client_id: str, session_id: str, status: str, message: str = None):
        self.messages.append(("status", client_id, session_id, status, message))

    async def send_upload_error(self, client_id: str, session_id: str, error: str, error_code: str = None):
        self.messages.append(("error", client_id, session_id, error, error_code))

    async def send_upload_completed(self, client_id: str, session_id: str, document_data: dict = None):
        self.messages.append(("completed", client_id, session_id, document_data))

    async def join_upload_room(self, client_id: str, session_id: str):
        room_name = f"upload_{session_id}"
        if room_name not in self.rooms:
            self.rooms[room_name] = []
        if client_id not in self.rooms[room_name]:
            self.rooms[room_name].append(client_id)

    async def leave_upload_room(self, client_id: str, session_id: str):
        room_name = f"upload_{session_id}"
        if room_name in self.rooms and client_id in self.rooms[room_name]:
            self.rooms[room_name].remove(client_id)


@pytest.fixture
async def temp_upload_dir():
    """Create temporary upload directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
async def streaming_service(temp_upload_dir):
    """Create streaming upload service."""
    service = StreamingUploadService(
        upload_dir=temp_upload_dir,
        max_concurrent_uploads=3,
        memory_limit_mb=100.0,
        session_timeout_minutes=30,
    )
    yield service
    await service.cleanup()


@pytest.fixture
async def validation_service():
    """Create validation service."""
    return StreamingValidationService()


@pytest.fixture
async def resumption_service(temp_upload_dir):
    """Create resumption service."""
    state_dir = temp_upload_dir / "resume_states"
    service = UploadResumptionService(
        state_dir=state_dir,
        max_resume_age_hours=24,
    )
    yield service
    await service.cleanup()


@pytest.fixture
async def pdf_processor():
    """Create PDF processor."""
    return StreamingPDFProcessor(
        max_pages_per_chunk=3,
        max_text_length_per_page=5000,
    )


@pytest.fixture
async def mock_websocket():
    """Create mock WebSocket manager."""
    return MockWebSocketManager()


@pytest.fixture
async def sample_pdf_data():
    """Create sample PDF data for testing."""
    # Simple PDF content - minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Hello, World!) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000189 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
284
%%EOF"""
    return pdf_content


class TestStreamingUploadService:
    """Test cases for StreamingUploadService."""

    async def test_initiate_upload(self, streaming_service, mock_websocket):
        """Test upload session initiation."""
        request = StreamingUploadRequest(
            filename="test.pdf",
            file_size=1024000,  # 1MB
            client_id="test_client",
            chunk_size=8388608,  # 8MB
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)

        assert session is not None
        assert session.filename == "test.pdf"
        assert session.total_size == 1024000
        assert session.status == UploadStatus.INITIALIZING
        assert session.total_chunks > 0
        assert session.session_id in streaming_service.active_sessions

    async def test_chunk_processing(self, streaming_service, mock_websocket, sample_pdf_data):
        """Test individual chunk processing."""
        request = StreamingUploadRequest(
            filename="test.pdf",
            file_size=len(sample_pdf_data),
            client_id="test_client",
            chunk_size=1024,  # 1KB chunks
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)

        # Process chunks
        chunk_size = 1024
        chunks_uploaded = 0

        for i in range(0, len(sample_pdf_data), chunk_size):
            chunk_data = sample_pdf_data[i:i + chunk_size]
            is_final = i + chunk_size >= len(sample_pdf_data)

            success, message = await streaming_service.process_chunk(
                session_id=session.session_id,
                chunk_id=chunks_uploaded,
                chunk_data=chunk_data,
                chunk_offset=i,
                is_final=is_final,
                websocket_manager=mock_websocket,
            )

            assert success, f"Chunk {chunks_uploaded} failed: {message}"
            chunks_uploaded += 1

        # Verify final state
        updated_session = await streaming_service.get_session(session.session_id)
        assert updated_session.status in [UploadStatus.COMPLETED, UploadStatus.VALIDATING]
        assert updated_session.uploaded_chunks == chunks_uploaded

    async def test_concurrent_upload_limits(self, streaming_service, mock_websocket):
        """Test concurrent upload limits."""
        # Create multiple upload requests
        requests = []
        for i in range(5):  # More than max_concurrent_uploads (3)
            request = StreamingUploadRequest(
                filename=f"test_{i}.pdf",
                file_size=1024000,
                client_id=f"test_client_{i}",
            )
            requests.append(request)

        sessions = []
        for i, request in enumerate(requests[:3]):  # Should succeed
            session = await streaming_service.initiate_upload(request, mock_websocket)
            sessions.append(session)

        # The 4th request should fail due to concurrent limits
        with pytest.raises(RuntimeError, match="Maximum concurrent uploads"):
            await streaming_service.initiate_upload(requests[3], mock_websocket)

    async def test_memory_monitoring(self, streaming_service):
        """Test memory usage monitoring."""
        stats = await streaming_service.get_memory_stats()

        assert isinstance(stats.memory_usage_mb, float)
        assert stats.memory_usage_mb >= 0
        assert stats.active_sessions >= 0
        assert stats.concurrent_uploads >= 0
        assert isinstance(stats.disk_space_available_mb, float)

    async def test_upload_cancellation(self, streaming_service, mock_websocket):
        """Test upload session cancellation."""
        request = StreamingUploadRequest(
            filename="test.pdf",
            file_size=1024000,
            client_id="test_client",
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)
        session_id = session.session_id

        # Cancel upload
        success = await streaming_service.cancel_upload(session_id, "User cancelled")

        assert success
        assert session_id not in streaming_service.active_sessions

        # Verify temp file is cleaned up
        if session.temp_file_path:
            assert not Path(session.temp_file_path).exists()


class TestStreamingValidationService:
    """Test cases for StreamingValidationService."""

    async def test_pdf_signature_validation(self, validation_service, sample_pdf_data, temp_upload_dir):
        """Test PDF signature detection and validation."""
        # Write sample PDF to temp file
        temp_file = temp_upload_dir / "test.pdf"
        temp_file.write_bytes(sample_pdf_data)

        result = await validation_service.validate_streaming_upload(str(temp_file))

        assert result.is_pdf
        assert result.is_valid
        assert result.detected_mime_type == "application/pdf"
        assert result.pdf_version is not None
        assert len(result.validation_errors) == 0

    async def test_invalid_file_validation(self, validation_service, temp_upload_dir):
        """Test validation of non-PDF files."""
        # Create invalid file
        temp_file = temp_upload_dir / "invalid.txt"
        temp_file.write_text("This is not a PDF file")

        result = await validation_service.validate_streaming_upload(str(temp_file))

        assert not result.is_pdf
        assert not result.is_valid
        assert len(result.validation_errors) > 0

    async def test_chunk_validation(self, validation_service, sample_pdf_data):
        """Test individual chunk validation during upload."""
        # Test first chunk (should have PDF signature)
        chunk = sample_pdf_data[:1024]
        is_valid, errors, warnings = await validation_service.validate_chunk_during_upload(
            chunk, 0, is_first_chunk=True
        )

        assert is_valid
        assert len(errors) == 0

        # Test non-first chunk
        chunk = sample_pdf_data[1024:2048]
        is_valid, errors, warnings = await validation_service.validate_chunk_during_upload(
            chunk, 1, is_first_chunk=False
        )

        assert is_valid

    async def test_security_scanning(self, validation_service, temp_upload_dir):
        """Test security threat detection."""
        # Create PDF with potential security issues
        malicious_content = b"""%PDF-1.4
/JavaScript (app.alert('XSS'))
/EmbeddedFiles
<<
/Type /Catalog
>>
"""
        temp_file = temp_upload_dir / "malicious.pdf"
        temp_file.write_bytes(malicious_content)

        result = await validation_service.validate_streaming_upload(str(temp_file))

        # Should detect but not block (warnings only)
        assert len(result.warnings) > 0
        # Check if security warnings are present
        security_warning_found = any("javascript" in warning.lower() or "embedded" in warning.lower() for warning in result.warnings)
        assert security_warning_found


class TestUploadResumptionService:
    """Test cases for UploadResumptionService."""

    async def test_session_state_persistence(self, resumption_service, temp_upload_dir):
        """Test saving and loading session state."""
        # Create a mock session
        from backend.api.streaming_models import UploadSession

        session = UploadSession(
            filename="test.pdf",
            total_size=1024000,
            chunk_size=8192,
            total_chunks=125,
            uploaded_chunks=50,
            client_id="test_client",
            temp_file_path=str(temp_upload_dir / "test.tmp"),
        )

        # Create temp file
        temp_file = Path(session.temp_file_path)
        temp_file.write_bytes(b"x" * (50 * 8192))  # 50 chunks worth of data

        # Save session state
        await resumption_service.save_session_state(session)

        # Load session state
        loaded_state = await resumption_service.load_session_state(session.session_id)

        assert loaded_state is not None
        assert loaded_state['filename'] == "test.pdf"
        assert loaded_state['uploaded_chunks'] == 50
        assert loaded_state['total_chunks'] == 125

    async def test_session_resumption(self, resumption_service, temp_upload_dir):
        """Test upload session resumption."""
        from backend.api.streaming_models import UploadSession

        # Create and save session
        original_session = UploadSession(
            filename="resume_test.pdf",
            total_size=1024000,
            chunk_size=8192,
            total_chunks=125,
            uploaded_chunks=75,
            client_id="original_client",
            temp_file_path=str(temp_upload_dir / "resume_test.tmp"),
        )

        # Create temp file with partial data
        temp_file = Path(original_session.temp_file_path)
        temp_file.write_bytes(b"x" * (75 * 8192))

        await resumption_service.save_session_state(original_session)

        # Create resume request
        resume_request = UploadResumeRequest(
            session_id=original_session.session_id,
            client_id="new_client",
            last_chunk_id=74,  # 75 chunks uploaded (0-indexed)
        )

        # Resume session
        resumed_session = await resumption_service.resume_upload_session(resume_request)

        assert resumed_session is not None
        assert resumed_session.session_id == original_session.session_id
        assert resumed_session.client_id == "new_client"  # Updated client ID
        assert resumed_session.uploaded_chunks == 75
        assert resumed_session.status == UploadStatus.UPLOADING

    async def test_resumable_session_listing(self, resumption_service, temp_upload_dir):
        """Test listing resumable sessions."""
        from backend.api.streaming_models import UploadSession

        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = UploadSession(
                filename=f"test_{i}.pdf",
                total_size=1024000,
                chunk_size=8192,
                total_chunks=125,
                uploaded_chunks=50 + i * 10,
                client_id=f"client_{i}",
                temp_file_path=str(temp_upload_dir / f"test_{i}.tmp"),
            )

            # Create temp files
            temp_file = Path(session.temp_file_path)
            temp_file.write_bytes(b"x" * ((50 + i * 10) * 8192))

            sessions.append(session)
            await resumption_service.save_session_state(session)

        # Get resumable sessions
        resumable = await resumption_service.get_resumable_sessions()

        assert len(resumable) == 3
        assert all(session['progress_percentage'] > 0 for session in resumable)


class TestStreamingPDFProcessor:
    """Test cases for StreamingPDFProcessor."""

    async def test_pdf_info_extraction(self, pdf_processor, sample_pdf_data, temp_upload_dir):
        """Test PDF information extraction without loading full file."""
        # Write sample PDF
        temp_file = temp_upload_dir / "info_test.pdf"
        temp_file.write_bytes(sample_pdf_data)

        info = await pdf_processor.get_pdf_info_streaming(str(temp_file))

        assert 'file_size' in info
        assert info['file_size'] == len(sample_pdf_data)
        assert 'page_count' in info
        assert 'processing_estimate' in info

    async def test_processing_readiness_validation(self, pdf_processor, sample_pdf_data, temp_upload_dir):
        """Test PDF processing readiness validation."""
        # Write sample PDF
        temp_file = temp_upload_dir / "readiness_test.pdf"
        temp_file.write_bytes(sample_pdf_data)

        is_ready, errors, warnings = await pdf_processor.validate_pdf_processing_readiness(
            str(temp_file), available_memory_mb=100.0
        )

        assert is_ready
        assert len(errors) == 0
        # May have warnings about file size or page count, that's ok


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple services."""

    async def test_complete_streaming_upload_workflow(
        self,
        streaming_service,
        validation_service,
        resumption_service,
        mock_websocket,
        sample_pdf_data,
    ):
        """Test complete streaming upload workflow from start to finish."""
        # 1. Initiate upload
        request = StreamingUploadRequest(
            filename="integration_test.pdf",
            file_size=len(sample_pdf_data),
            client_id="integration_client",
            chunk_size=512,  # Small chunks for testing
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)
        assert session.status == UploadStatus.INITIALIZING

        # 2. Save state for resumption
        await resumption_service.save_session_state(session)

        # 3. Upload chunks
        chunk_size = 512
        for i in range(0, len(sample_pdf_data), chunk_size):
            chunk_data = sample_pdf_data[i:i + chunk_size]
            chunk_id = i // chunk_size
            is_final = i + chunk_size >= len(sample_pdf_data)

            # Validate chunk
            is_valid, errors, warnings = await validation_service.validate_chunk_during_upload(
                chunk_data, chunk_id, is_first_chunk=(chunk_id == 0)
            )
            assert is_valid, f"Chunk {chunk_id} validation failed: {errors}"

            # Process chunk
            success, message = await streaming_service.process_chunk(
                session_id=session.session_id,
                chunk_id=chunk_id,
                chunk_data=chunk_data,
                chunk_offset=i,
                is_final=is_final,
                websocket_manager=mock_websocket,
            )
            assert success, f"Chunk {chunk_id} processing failed: {message}"

        # 4. Verify completion
        final_session = await streaming_service.get_session(session.session_id)
        assert final_session.status == UploadStatus.COMPLETED

        # 5. Validate final file
        if final_session.temp_file_path:
            validation_result = await validation_service.validate_streaming_upload(
                final_session.temp_file_path
            )
            assert validation_result.is_valid
            assert validation_result.is_pdf

        # 6. Clean up
        await streaming_service.cancel_upload(session.session_id, "Test completed")

    async def test_upload_interruption_and_resume(
        self,
        streaming_service,
        resumption_service,
        mock_websocket,
        sample_pdf_data,
    ):
        """Test upload interruption and successful resumption."""
        # 1. Start upload
        request = StreamingUploadRequest(
            filename="resume_test.pdf",
            file_size=len(sample_pdf_data),
            client_id="resume_client",
            chunk_size=256,
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)
        await resumption_service.save_session_state(session)

        # 2. Upload partial chunks (simulate interruption)
        chunk_size = 256
        chunks_to_upload = 3  # Only upload first 3 chunks

        for i in range(chunks_to_upload):
            chunk_start = i * chunk_size
            chunk_data = sample_pdf_data[chunk_start:chunk_start + chunk_size]

            success, message = await streaming_service.process_chunk(
                session_id=session.session_id,
                chunk_id=i,
                chunk_data=chunk_data,
                chunk_offset=chunk_start,
                is_final=False,
                websocket_manager=mock_websocket,
            )
            assert success

            # Save state after each chunk
            updated_session = await streaming_service.get_session(session.session_id)
            await resumption_service.save_session_state(updated_session)

        # 3. Simulate interruption (clear active sessions)
        streaming_service.active_sessions.clear()
        streaming_service.session_locks.clear()

        # 4. Resume upload
        resume_request = UploadResumeRequest(
            session_id=session.session_id,
            client_id="resume_client_new",
            last_chunk_id=chunks_to_upload - 1,
        )

        resumed_session = await resumption_service.resume_upload_session(resume_request)
        assert resumed_session is not None
        assert resumed_session.uploaded_chunks == chunks_to_upload

        # Re-register with streaming service
        streaming_service.active_sessions[resumed_session.session_id] = resumed_session
        streaming_service.session_locks[resumed_session.session_id] = asyncio.Lock()

        # 5. Complete upload
        total_chunks = (len(sample_pdf_data) + chunk_size - 1) // chunk_size

        for i in range(chunks_to_upload, total_chunks):
            chunk_start = i * chunk_size
            chunk_end = min(chunk_start + chunk_size, len(sample_pdf_data))
            chunk_data = sample_pdf_data[chunk_start:chunk_end]
            is_final = (i == total_chunks - 1)

            success, message = await streaming_service.process_chunk(
                session_id=resumed_session.session_id,
                chunk_id=i,
                chunk_data=chunk_data,
                chunk_offset=chunk_start,
                is_final=is_final,
                websocket_manager=mock_websocket,
            )
            assert success

        # 6. Verify completion
        final_session = await streaming_service.get_session(resumed_session.session_id)
        assert final_session.status == UploadStatus.COMPLETED


@pytest.mark.asyncio
async def test_performance_benchmarks(temp_upload_dir):
    """Performance benchmark tests for streaming upload."""
    # Create large test data (10MB)
    large_data = b"x" * (10 * 1024 * 1024)

    streaming_service = StreamingUploadService(
        upload_dir=temp_upload_dir,
        max_concurrent_uploads=2,
        memory_limit_mb=200.0,
    )

    mock_websocket = MockWebSocketManager()

    try:
        # Benchmark upload initiation
        start_time = time.time()

        request = StreamingUploadRequest(
            filename="benchmark.pdf",
            file_size=len(large_data),
            client_id="benchmark_client",
            chunk_size=1024*1024,  # 1MB chunks
        )

        session = await streaming_service.initiate_upload(request, mock_websocket)
        initiation_time = time.time() - start_time

        # Benchmark chunk processing
        chunk_size = 1024 * 1024  # 1MB
        processing_times = []

        for i in range(0, min(len(large_data), chunk_size * 5), chunk_size):  # Process first 5 chunks
            chunk_data = large_data[i:i + chunk_size]
            chunk_id = i // chunk_size

            chunk_start_time = time.time()
            success, message = await streaming_service.process_chunk(
                session_id=session.session_id,
                chunk_id=chunk_id,
                chunk_data=chunk_data,
                chunk_offset=i,
                is_final=False,
                websocket_manager=mock_websocket,
            )
            chunk_time = time.time() - chunk_start_time
            processing_times.append(chunk_time)

            assert success, f"Chunk {chunk_id} failed: {message}"

        # Performance assertions
        assert initiation_time < 1.0, f"Upload initiation too slow: {initiation_time:.2f}s"
        avg_chunk_time = sum(processing_times) / len(processing_times)
        assert avg_chunk_time < 0.5, f"Average chunk processing too slow: {avg_chunk_time:.2f}s"

        # Memory usage check
        stats = await streaming_service.get_memory_stats()
        assert stats.memory_usage_mb < 200.0, f"Memory usage too high: {stats.memory_usage_mb}MB"

        print(f"Performance Results:")
        print(f"  Upload initiation: {initiation_time:.3f}s")
        print(f"  Average chunk processing: {avg_chunk_time:.3f}s")
        print(f"  Memory usage: {stats.memory_usage_mb:.1f}MB")
        print(f"  Chunks processed: {len(processing_times)}")

    finally:
        await streaming_service.cleanup()


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v", "--tb=short"])