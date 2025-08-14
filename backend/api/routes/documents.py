"""
Documents API Routes
RESTful API endpoints for document management operations.
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from backend.api.dependencies import (
    get_api_config,
    get_library_controller,
    get_upload_directory,
    validate_document_access,
)
from backend.api.websocket_manager import WebSocketManager
from backend.api.models import (
    BaseResponse,
    DocumentImportResponse,
    DocumentListResponse,
    DocumentQueryParams,
    DocumentResponse,
    DocumentUpdate,
    IntegrityCheckResponse,
    SecureFileUpload,
    SecurityValidationError,
    SecurityValidationErrorResponse,
    ValidationErrorResponse,
)
from backend.api.streaming_models import (
    ChunkUploadRequest,
    ChunkUploadResponse,
    StreamingUploadRequest,
    StreamingUploadResponse,
    UploadCancellationRequest,
    UploadMemoryStats,
    UploadProgress,
    UploadResumeRequest,
    UploadStatus,
)
from backend.api.error_handling import (
    ResourceNotFoundException,
    ValidationException,
    ConflictException,
    SystemException,
    ErrorTemplates,
    ErrorDetail
)
from backend.services.streaming_upload_service import StreamingUploadService
from backend.services.streaming_validation_service import StreamingValidationService
from backend.services.upload_resumption_service import UploadResumptionService
from backend.services.streaming_pdf_service import StreamingPDFProcessor
from src.controllers.library_controller import LibraryController
from src.database.models import DocumentModel
from src.services.document_library_service import DuplicateDocumentError

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize streaming services (these should be dependency injected in production)
_streaming_upload_service: Optional[StreamingUploadService] = None
_validation_service: Optional[StreamingValidationService] = None
_resumption_service: Optional[UploadResumptionService] = None
_pdf_processor: Optional[StreamingPDFProcessor] = None
_websocket_manager: Optional[WebSocketManager] = None


def get_streaming_upload_service(upload_dir: Path = Depends(get_upload_directory)) -> StreamingUploadService:
    """Get streaming upload service dependency."""
    global _streaming_upload_service
    if _streaming_upload_service is None:
        _streaming_upload_service = StreamingUploadService(
            upload_dir=upload_dir,
            max_concurrent_uploads=5,
            memory_limit_mb=500.0,
        )
    return _streaming_upload_service


def get_validation_service() -> StreamingValidationService:
    """Get streaming validation service dependency."""
    global _validation_service
    if _validation_service is None:
        _validation_service = StreamingValidationService()
    return _validation_service


def get_resumption_service(upload_dir: Path = Depends(get_upload_directory)) -> UploadResumptionService:
    """Get upload resumption service dependency."""
    global _resumption_service
    if _resumption_service is None:
        state_dir = upload_dir / "resume_states"
        _resumption_service = UploadResumptionService(state_dir=state_dir)
    return _resumption_service


def get_pdf_processor() -> StreamingPDFProcessor:
    """Get streaming PDF processor dependency."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = StreamingPDFProcessor()
    return _pdf_processor


def get_websocket_manager() -> WebSocketManager:
    """Get WebSocket manager dependency."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


@router.get("/", response_model=DocumentListResponse)
async def get_documents(
    params: DocumentQueryParams = Depends(),
    controller: LibraryController = Depends(get_library_controller),
) -> DocumentListResponse:
    """Get list of documents with optional filtering and pagination."""
    try:
        # Use secure validated parameters
        logger.info(f"Getting documents with secure params: sort_by={params.sort_by}, sort_order={params.sort_order}")

        # Get documents with secure parameters
        documents = controller.get_documents(
            search_query=params.search_query,
            limit=params.per_page * params.page,  # Simple pagination for now
            sort_by=params.sort_by,  # Enum inherits from str, so no .value needed
        )

        # Apply additional filters
        if not params.show_missing:
            documents = [doc for doc in documents if doc.is_file_available()]

        # Simple pagination
        start_idx = (params.page - 1) * params.per_page
        end_idx = start_idx + params.per_page
        paginated_docs = documents[start_idx:end_idx]

        # Convert to response models
        doc_responses = []
        for doc in paginated_docs:
            doc_dict = doc.to_api_dict()
            doc_dict["is_file_available"] = doc.is_file_available()
            doc_responses.append(DocumentResponse(**doc_dict))

        return DocumentListResponse(
            documents=doc_responses,
            total=len(documents),
            page=params.page,
            per_page=params.per_page
        )
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise SystemException(
            message="Failed to retrieve documents",
            error_type="database"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> DocumentResponse:
    """Get a specific document by ID."""
    try:
        document = validate_document_access(document_id, controller)
        doc_dict = document.to_api_dict()
        doc_dict["is_file_available"] = document.is_file_available()
        return DocumentResponse(**doc_dict)
    except HTTPException as e:
        if e.status_code == 404:
            raise ErrorTemplates.document_not_found(document_id)
        raise


@router.post("/upload", response_model=DocumentImportResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    check_duplicates: bool = True,
    auto_build_index: bool = False,
    controller: LibraryController = Depends(get_library_controller),
    upload_dir: Path = Depends(get_upload_directory),
    config: dict[str, Any] = Depends(get_api_config),
) -> DocumentImportResponse:
    """Upload and import a new PDF document with comprehensive security validation."""
    try:
        # Enhanced security validation for file upload
        try:
            secure_upload = SecureFileUpload(
                filename=file.filename or "unknown.pdf",
                content_type=file.content_type or "application/pdf",
                file_size=0  # Will be calculated during streaming
            )
        except SecurityValidationError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=SecurityValidationErrorResponse.from_security_error(e).dict()
            )

        # Validate file type (additional check)
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise ErrorTemplates.invalid_file_type(
                provided_type=file.content_type or "unknown",
                allowed_types=["application/pdf"]
            )
        # Validate file size
        max_size = config["max_file_size_mb"] * 1024 * 1024
        file_size = 0
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", dir=upload_dir
        ) as temp_file:
            temp_path = temp_file.name
            # Stream file content and check size
            while True:
                chunk = await file.read(8192)  # 8KB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > max_size:
                    # Clean up temp file
                    Path(temp_path).unlink(missing_ok=True)
                    raise ErrorTemplates.file_too_large(file_size, max_size)
                temp_file.write(chunk)
        try:
            # Import document (this will copy file to managed storage)
            success = controller.import_document(
                file_path=temp_path,
                title=title or Path(filename or "uploaded_document").stem,
                check_duplicates=check_duplicates,
                auto_build_index=auto_build_index,
            )
            if not success:
                raise SystemException(
                    message="Document import operation failed",
                    error_type="general"
                )
            # Clean up temp file after successful import
            Path(temp_path).unlink(missing_ok=True)
            # Get the imported document
            # Note: This is a simplified approach - in production, you'd want to
            # return the document ID from import_document method
            documents = controller.get_documents(limit=1, sort_by="created_at")
            if documents:
                document = documents[0]
                doc_dict = document.to_api_dict()
                doc_dict["is_file_available"] = document.is_file_available()
                return DocumentImportResponse(document=DocumentResponse(**doc_dict))
            raise SystemException(
                message="Document imported but could not retrieve details",
                error_type="database"
            )
        except DuplicateDocumentError as e:
            # Clean up temp file on duplicate error
            Path(temp_path).unlink(missing_ok=True)
            raise ErrorTemplates.duplicate_document(filename or "uploaded file")
        except Exception as e:
            # Clean up temp file on any error
            Path(temp_path).unlink(missing_ok=True)
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise SystemException(
            message="Document upload failed due to an unexpected error",
            error_type="general"
        )


@router.post("/streaming/initiate", response_model=StreamingUploadResponse)
async def initiate_streaming_upload(
    request: StreamingUploadRequest,
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
    config: dict[str, Any] = Depends(get_api_config),
) -> StreamingUploadResponse:
    """
    Initiate a streaming upload session for large PDF files.

    This endpoint starts a chunked upload process that allows:
    - Memory-efficient processing of large files
    - Real-time progress tracking via WebSocket
    - Upload resumption after interruptions
    - Concurrent upload management with backpressure
    """
    try:
        # Validate file size against limits
        max_size = config["max_file_size_mb"] * 1024 * 1024
        if request.file_size > max_size:
            raise ErrorTemplates.file_too_large(request.file_size, max_size)

        # Initiate upload session
        session = await streaming_service.initiate_upload(request, websocket_manager)

        # Join WebSocket room for progress updates
        await websocket_manager.join_upload_room(request.client_id, str(session.session_id))

        # Create response
        response = StreamingUploadResponse(
            session_id=session.session_id,
            upload_url=f"/api/documents/streaming/chunk/{session.session_id}",
            chunk_size=session.chunk_size,
            total_chunks=session.total_chunks,
            expires_at=session.created_at.replace(hour=23, minute=59, second=59),
            websocket_room=f"upload_{session.session_id}",
        )

        logger.info(
            f"Streaming upload initiated: {session.session_id} "
            f"({request.filename}, {request.file_size} bytes, {session.total_chunks} chunks)"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate streaming upload: {e}")
        raise SystemException(
            message="Failed to initiate streaming upload",
            error_type="general"
        )


@router.post("/streaming/chunk/{session_id}", response_model=ChunkUploadResponse)
async def upload_chunk(
    session_id: UUID,
    chunk_id: int = Form(...),
    chunk_offset: int = Form(...),
    is_final: bool = Form(default=False),
    checksum: Optional[str] = Form(None),
    file: UploadFile = File(...),
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
    validation_service: StreamingValidationService = Depends(get_validation_service),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
) -> ChunkUploadResponse:
    """
    Upload an individual chunk of a streaming upload.

    This endpoint handles:
    - Individual chunk validation and processing
    - Real-time progress updates
    - Memory-efficient chunk processing
    - Error recovery and retry support
    """
    try:
        # Read chunk data
        chunk_data = await file.read()

        # Validate chunk during upload
        is_first_chunk = chunk_id == 0
        chunk_valid, errors, warnings = await validation_service.validate_chunk_during_upload(
            chunk_data, chunk_id, is_first_chunk
        )

        if not chunk_valid:
            return ChunkUploadResponse(
                success=False,
                chunk_id=chunk_id,
                upload_complete=False,
                message=f"Chunk validation failed: {'; '.join(errors)}",
                retry_after=5,
            )

        # Send warnings if any
        if warnings and websocket_manager:
            for warning in warnings:
                await websocket_manager.send_upload_progress(
                    "",  # Will be determined from session
                    {"type": "warning", "message": warning}
                )

        # Process chunk
        success, message = await streaming_service.process_chunk(
            session_id=session_id,
            chunk_id=chunk_id,
            chunk_data=chunk_data,
            chunk_offset=chunk_offset,
            is_final=is_final,
            expected_checksum=checksum,
            websocket_manager=websocket_manager,
        )

        if not success:
            return ChunkUploadResponse(
                success=False,
                chunk_id=chunk_id,
                upload_complete=False,
                message=message,
                retry_after=5,
            )

        # Get session to check completion status
        session = await streaming_service.get_session(session_id)
        if not session:
            return ChunkUploadResponse(
                success=False,
                chunk_id=chunk_id,
                upload_complete=False,
                message="Upload session not found",
            )

        upload_complete = session.status == UploadStatus.COMPLETED
        next_chunk_id = None if upload_complete else chunk_id + 1

        return ChunkUploadResponse(
            success=True,
            chunk_id=chunk_id,
            next_chunk_id=next_chunk_id,
            upload_complete=upload_complete,
            message="Chunk uploaded successfully" if not upload_complete else "Upload completed successfully",
        )

    except Exception as e:
        logger.error(f"Failed to upload chunk {chunk_id} for session {session_id}: {e}")
        return ChunkUploadResponse(
            success=False,
            chunk_id=chunk_id,
            upload_complete=False,
            message=f"Chunk upload failed: {str(e)}",
            retry_after=10,
        )


@router.post("/streaming/complete/{session_id}", response_model=DocumentImportResponse)
async def complete_streaming_upload(
    session_id: UUID,
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
    pdf_processor: StreamingPDFProcessor = Depends(get_pdf_processor),
    resumption_service: UploadResumptionService = Depends(get_resumption_service),
    controller: LibraryController = Depends(get_library_controller),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
) -> DocumentImportResponse:
    """
    Complete a streaming upload and import the document into the library.

    This endpoint:
    - Validates the complete uploaded file
    - Processes PDF content with streaming approach
    - Imports document into the library system
    - Builds vector index if requested
    - Cleans up temporary files
    """
    try:
        # Get upload session
        session = await streaming_service.get_session(session_id)
        if not session:
            raise ErrorTemplates.resource_not_found("upload session", str(session_id))

        if session.status != UploadStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload not completed. Current status: {session.status.value}"
            )

        # Validate uploaded file
        if not session.temp_file_path or not Path(session.temp_file_path).exists():
            raise SystemException(
                message="Uploaded file not found",
                error_type="file_system"
            )

        # Send processing status
        await websocket_manager.send_upload_status(
            session.client_id,
            str(session_id),
            "processing",
            "Starting document import..."
        )

        try:
            # Import document using the controller
            # The temp file will be moved to permanent storage by the controller
            document_title = session.metadata.get("title") or Path(session.filename).stem
            check_duplicates = session.metadata.get("check_duplicates", True)
            auto_build_index = session.metadata.get("auto_build_index", False)

            success = controller.import_document(
                file_path=session.temp_file_path,
                title=document_title,
                check_duplicates=check_duplicates,
                auto_build_index=auto_build_index,
            )

            if not success:
                raise SystemException(
                    message="Document import operation failed",
                    error_type="general"
                )

            # Clean up session and temporary files
            await streaming_service.cancel_upload(session_id, "Import completed")
            await resumption_service.delete_resumable_session(session_id)

            # Get the imported document
            documents = controller.get_documents(limit=1, sort_by="created_at")
            if documents:
                document = documents[0]
                doc_dict = document.to_api_dict()
                doc_dict["is_file_available"] = document.is_file_available()

                # Send completion notification
                await websocket_manager.send_upload_completed(
                    session.client_id,
                    str(session_id),
                    doc_dict
                )

                # Leave upload room
                await websocket_manager.leave_upload_room(session.client_id, str(session_id))

                return DocumentImportResponse(document=DocumentResponse(**doc_dict))

            raise SystemException(
                message="Document imported but could not retrieve details",
                error_type="database"
            )

        except DuplicateDocumentError as e:
            # Clean up on duplicate error
            await streaming_service.cancel_upload(session_id, "Duplicate document")
            await resumption_service.delete_resumable_session(session_id)
            raise ErrorTemplates.duplicate_document(session.filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete streaming upload {session_id}: {e}")

        # Send error notification
        if websocket_manager and session:
            await websocket_manager.send_upload_error(
                session.client_id,
                str(session_id),
                f"Import failed: {str(e)}"
            )

        raise SystemException(
            message="Failed to complete document import",
            error_type="general"
        )


@router.post("/streaming/cancel/{session_id}", response_model=BaseResponse)
async def cancel_streaming_upload(
    session_id: UUID,
    request: UploadCancellationRequest,
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
    resumption_service: UploadResumptionService = Depends(get_resumption_service),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
) -> BaseResponse:
    """Cancel an active streaming upload."""
    try:
        # Get session for client ID
        session = await streaming_service.get_session(session_id)

        # Cancel upload
        success = await streaming_service.cancel_upload(session_id, request.reason or "User cancelled")

        if success:
            # Clean up resumption data
            await resumption_service.delete_resumable_session(session_id)

            # Notify client
            if session and websocket_manager:
                await websocket_manager.send_upload_status(
                    session.client_id,
                    str(session_id),
                    "cancelled",
                    request.reason or "Upload cancelled"
                )
                await websocket_manager.leave_upload_room(session.client_id, str(session_id))

            return BaseResponse(message=f"Upload {session_id} cancelled successfully")
        else:
            raise ErrorTemplates.resource_not_found("upload session", str(session_id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel streaming upload {session_id}: {e}")
        raise SystemException(
            message="Failed to cancel upload",
            error_type="general"
        )


@router.post("/streaming/resume", response_model=StreamingUploadResponse)
async def resume_streaming_upload(
    request: UploadResumeRequest,
    resumption_service: UploadResumptionService = Depends(get_resumption_service),
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
) -> StreamingUploadResponse:
    """Resume an interrupted streaming upload."""
    try:
        # Resume session
        session = await resumption_service.resume_upload_session(request)

        if not session:
            raise ErrorTemplates.resource_not_found("resumable upload session", str(request.session_id))

        # Re-register with streaming service
        streaming_service.active_sessions[session.session_id] = session
        streaming_service.session_locks[session.session_id] = asyncio.Lock()

        # Join WebSocket room
        await websocket_manager.join_upload_room(request.client_id, str(session.session_id))

        # Send resume notification
        await websocket_manager.send_upload_status(
            request.client_id,
            str(session.session_id),
            "resumed",
            f"Upload resumed from chunk {session.uploaded_chunks}"
        )

        response = StreamingUploadResponse(
            session_id=session.session_id,
            upload_url=f"/api/documents/streaming/chunk/{session.session_id}",
            chunk_size=session.chunk_size,
            total_chunks=session.total_chunks,
            expires_at=session.created_at.replace(hour=23, minute=59, second=59),
            websocket_room=f"upload_{session.session_id}",
        )

        logger.info(f"Streaming upload resumed: {session.session_id} from chunk {session.uploaded_chunks}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume streaming upload: {e}")
        raise SystemException(
            message="Failed to resume upload",
            error_type="general"
        )


@router.get("/streaming/resumable", response_model=List[dict])
async def get_resumable_uploads(
    client_id: Optional[str] = Query(None),
    resumption_service: UploadResumptionService = Depends(get_resumption_service),
) -> List[dict]:
    """Get list of resumable upload sessions."""
    try:
        resumable_sessions = await resumption_service.get_resumable_sessions(client_id)
        return resumable_sessions
    except Exception as e:
        logger.error(f"Failed to get resumable uploads: {e}")
        raise SystemException(
            message="Failed to retrieve resumable uploads",
            error_type="general"
        )


@router.get("/streaming/memory-stats", response_model=UploadMemoryStats)
async def get_upload_memory_stats(
    streaming_service: StreamingUploadService = Depends(get_streaming_upload_service),
) -> UploadMemoryStats:
    """Get current memory usage statistics for upload operations."""
    try:
        return await streaming_service.get_memory_stats()
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise SystemException(
            message="Failed to retrieve memory statistics",
            error_type="general"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    update_data: DocumentUpdate,
    controller: LibraryController = Depends(get_library_controller),
) -> DocumentResponse:
    """Update document metadata."""
    document = validate_document_access(document_id, controller)
    try:
        # Update document fields
        if update_data.title is not None:
            document.title = update_data.title
        if update_data.metadata is not None:
            if document.metadata is None:
                document.metadata = {}
            document.metadata.update(update_data.metadata)
        # Save changes (this would need to be implemented in the controller)
        # For now, we'll return the document as-is
        doc_dict = document.to_api_dict()
        doc_dict["is_file_available"] = document.is_file_available()
        return DocumentResponse(**doc_dict)
    except Exception as e:
        logger.error(f"Failed to update document {document_id}: {e}")
        raise SystemException(
            message="Document update failed",
            error_type="database"
        )


@router.delete("/{document_id}", response_model=BaseResponse)
async def delete_document(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> BaseResponse:
    """Delete a document."""
    validate_document_access(document_id, controller)
    try:
        success = controller.delete_document(document_id)
        if success:
            return BaseResponse(message=f"Document {document_id} deleted successfully")
        else:
            raise SystemException(
                message="Document deletion failed",
                error_type="database"
            )
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise SystemException(
            message="Document deletion failed due to an unexpected error",
            error_type="general"
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> FileResponse:
    """Download the original PDF file."""
    document = validate_document_access(document_id, controller)
    if not document.file_path or not Path(document.file_path).exists():
        raise ErrorTemplates.file_not_found(document.file_path or "document file")
    try:
        return FileResponse(
            path=document.file_path,
            filename=f"{document.title}.pdf",
            media_type="application/pdf",
        )
    except Exception as e:
        logger.error(f"Failed to serve document file: {e}")
        raise SystemException(
            message="Failed to serve document file",
            error_type="general"
        )


@router.get("/{document_id}/integrity", response_model=IntegrityCheckResponse)
async def check_document_integrity(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> IntegrityCheckResponse:
    """Check document and index integrity."""
    validate_document_access(document_id, controller)
    try:
        integrity = controller.verify_document_integrity(document_id)
        return IntegrityCheckResponse(
            document_id=document_id,
            exists=integrity.get("exists", False),
            file_exists=integrity.get("file_exists", False),
            file_accessible=integrity.get("file_accessible", False),
            hash_matches=integrity.get("hash_matches", False),
            vector_index_exists=integrity.get("vector_index_exists", False),
            vector_index_valid=integrity.get("vector_index_valid", False),
            is_healthy=integrity.get("is_healthy", False),
            errors=integrity.get("errors", []),
            warnings=integrity.get("warnings", []),
        )
    except Exception as e:
        logger.error(f"Failed to check integrity for document {document_id}: {e}")
        raise SystemException(
            message="Document integrity check failed",
            error_type="general"
        )
