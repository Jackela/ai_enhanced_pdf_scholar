"""
Documents API v2 Routes
RESTful endpoints for document management.

Implements:
- Resource-oriented design
- Proper dependency injection
- HATEOAS links
- Standardized responses
- Comprehensive error handling

References:
- ADR-001: V2.0 Architecture Principles
- ADR-003: API Versioning Strategy
"""

import logging
import time
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from backend.api.dependencies import (
    get_document_library_service,
    get_document_preview_service,
    get_document_repository,
    get_documents_dir,
)
from backend.api.models.responses import (
    DocumentData,
    DocumentListResponse,
    DocumentResponse,
    Links,
    PaginationMeta,
)
from backend.api.utils.path_safety import build_safe_temp_path, is_within_allowed_roots
from backend.config.application_config import get_application_config
from backend.services.metrics_collector import get_metrics_collector
from src.database.models import DocumentModel
from src.exceptions import (
    DocumentImportError,
    DocumentValidationError,
    DuplicateDocumentError,
)
from src.interfaces.repository_interfaces import IDocumentRepository
from src.interfaces.service_interfaces import IDocumentLibraryService
from src.services.document_preview_service import (
    DocumentPreviewService,
    PreviewContent,
    PreviewDisabledError,
    PreviewError,
    PreviewNotFoundError,
    PreviewUnsupportedError,
)

logger = logging.getLogger(__name__)

# Note: No prefix here because it's set in main.py when including the router
router = APIRouter(tags=["documents"])
_preview_metrics = None


def _record_preview_metric(operation: str, result: str, duration: float | None) -> None:
    """Record preview metrics when the collector is available."""
    global _preview_metrics
    try:
        if _preview_metrics is None:
            _preview_metrics = get_metrics_collector().metrics
        if hasattr(_preview_metrics, "preview_requests_total"):
            _preview_metrics.preview_requests_total.labels(
                type=operation, result=result
            ).inc()
        if duration is not None and hasattr(
            _preview_metrics, "preview_generation_seconds"
        ):
            _preview_metrics.preview_generation_seconds.labels(type=operation).observe(
                duration
            )
    except Exception:
        logger.debug("Preview metrics collector unavailable", exc_info=True)


def _build_preview_headers(
    document_id: int, preview: "PreviewContent", ttl_seconds: int
) -> dict[str, str]:
    return {
        "Cache-Control": f"private, max-age={ttl_seconds}",
        "X-Document-Id": str(document_id),
        "X-Preview-Page": str(preview.page),
        "X-Preview-Cache": "hit" if preview.from_cache else "miss",
    }


def _handle_preview_exception(operation: str, exc: Exception) -> None:
    if isinstance(exc, PreviewDisabledError):
        _record_preview_metric(operation, "disabled", None)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PreviewUnsupportedError):
        _record_preview_metric(operation, "unsupported", None)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PreviewNotFoundError):
        _record_preview_metric(operation, "not_found", None)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PreviewError):
        _record_preview_metric(operation, "error", None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    _record_preview_metric(operation, "error", None)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate preview",
    ) from exc


# ============================================================================
# Helper Functions
# ============================================================================


def model_to_response_data(
    document: DocumentModel, base_url: str = "/api"
) -> DocumentData:
    """
    Convert DocumentModel to DocumentData response.

    Args:
        document: Database document model
        base_url: Base URL for generating links

    Returns:
        DocumentData with HATEOAS links
    """
    # Check if file exists
    file_exists = Path(document.file_path).exists() if document.file_path else False

    # Generate HATEOAS links
    links = Links(
        self=f"{base_url}/documents/{document.id}",
        related={
            "download": f"{base_url}/documents/{document.id}/download",
            "queries": f"{base_url}/documents/{document.id}/queries",
            "indexes": f"{base_url}/documents/{document.id}/indexes",
            "citations": f"{base_url}/documents/{document.id}/citations",
            "preview": f"{base_url}/documents/{document.id}/preview",
            "thumbnail": f"{base_url}/documents/{document.id}/thumbnail",
        },
    )

    preview_url = None
    thumbnail_url = None
    try:
        preview_config = get_application_config().preview
        if preview_config and preview_config.enabled:
            preview_url = f"{base_url}/documents/{document.id}/preview"
            thumbnail_url = f"{base_url}/documents/{document.id}/thumbnail"
    except Exception:
        logger.debug("Preview configuration unavailable", exc_info=True)

    return DocumentData(
        id=document.id,
        title=document.title,
        file_path=document.file_path,
        file_hash=document.file_hash,
        file_size=document.file_size,
        file_type=document.file_type,
        page_count=document.page_count,
        content_hash=document.content_hash,
        created_at=document.created_at,
        updated_at=document.updated_at,
        is_file_available=file_exists,
        preview_url=preview_url,
        thumbnail_url=thumbnail_url,
        _links=links,
    )


# ============================================================================
# List Documents
# ============================================================================


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="Get paginated list of documents with optional search and filtering",
    responses={
        200: {"description": "Documents retrieved successfully"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Internal server error"},
    },
)
async def list_documents(
    # Query parameters
    query: str | None = Query(
        None,
        min_length=1,
        max_length=500,
        description="Search query text",
    ),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    # Dependencies
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> DocumentListResponse:
    """
    List all documents with pagination and optional search.

    This endpoint demonstrates:
    - Proper dependency injection (doc_repo injected)
    - Database-level pagination (LIMIT/OFFSET)
    - Batch file existence check (no N+1 queries)
    - HATEOAS links on each document
    - Standardized response envelope
    """
    try:
        # Calculate offset for pagination
        offset = (page - 1) * per_page

        # Get documents from repository
        if query:
            # Search mode with proper pagination + total count
            documents, total = doc_repo.search(
                query=query,
                limit=per_page,
                offset=offset,
            )
        else:
            # List all mode
            documents = doc_repo.get_all(
                limit=per_page,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            total = doc_repo.count()

        # Convert to response format with HATEOAS links
        # Note: File availability is checked inside model_to_response_data
        document_data = [model_to_response_data(doc) for doc in documents]

        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1

        meta = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

        return DocumentListResponse(
            success=True,
            data=document_data,
            meta=meta,
            errors=None,
        )

    except ValueError as e:
        logger.warning(f"Invalid parameters for list_documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents",
        ) from e


# ============================================================================
# Get Document by ID
# ============================================================================


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document",
    description="Get document details by ID",
    responses={
        200: {"description": "Document retrieved successfully"},
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_document(
    document_id: int,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> DocumentResponse:
    """
    Get a specific document by ID.

    Args:
        document_id: Document ID
        doc_repo: Document repository (injected)

    Returns:
        DocumentResponse with document data and HATEOAS links

    Raises:
        HTTPException: 404 if document not found
    """
    try:
        # Get document from repository
        document = doc_repo.get_by_id(document_id)

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # Convert to response format
        document_data = model_to_response_data(document)

        return DocumentResponse(
            success=True,
            data=document_data,
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document",
        ) from e


@router.get(
    "/{document_id}/preview",
    summary="Get document page preview",
    responses={
        200: {
            "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}
        },
        400: {"description": "Invalid parameters"},
        404: {"description": "Document/page not found"},
        415: {"description": "Unsupported media type"},
        503: {"description": "Previews disabled"},
    },
)
async def get_document_preview(
    document_id: int,
    page: int = Query(1, ge=1, le=1000, description="One-based page number"),
    width: int | None = Query(
        None,
        ge=64,
        le=2000,
        description="Target width in pixels (auto-clamped to configured limits)",
    ),
    preview_service: DocumentPreviewService = Depends(get_document_preview_service),
) -> Response:
    """Return a rendered PNG preview for the requested page."""
    start = time.perf_counter()
    try:
        preview = preview_service.get_page_preview(document_id, page, width)
        duration = time.perf_counter() - start
        _record_preview_metric("preview", "success", duration)
        headers = _build_preview_headers(
            document_id, preview, preview_service.settings.cache_ttl_seconds
        )
        return Response(
            content=preview.content, media_type=preview.content_type, headers=headers
        )
    except Exception as exc:  # noqa: BLE001
        _handle_preview_exception("preview", exc)


@router.get(
    "/{document_id}/thumbnail",
    summary="Get document thumbnail",
    responses={
        200: {
            "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}
        },
        404: {"description": "Document not found"},
        415: {"description": "Unsupported media type"},
        503: {"description": "Previews disabled"},
    },
)
async def get_document_thumbnail(
    document_id: int,
    preview_service: DocumentPreviewService = Depends(get_document_preview_service),
) -> Response:
    """Return the cached thumbnail (first page) for a document."""
    start = time.perf_counter()
    try:
        preview = preview_service.get_thumbnail(document_id)
        duration = time.perf_counter() - start
        _record_preview_metric("thumbnail", "success", duration)
        headers = _build_preview_headers(
            document_id, preview, preview_service.settings.cache_ttl_seconds
        )
        return Response(
            content=preview.content, media_type=preview.content_type, headers=headers
        )
    except Exception as exc:  # noqa: BLE001
        _handle_preview_exception("thumbnail", exc)


# ============================================================================
# Upload Document
# ============================================================================


def _validate_file_upload(file: UploadFile | None) -> None:
    """
    Validate uploaded file type and presence.

    Args:
        file: Uploaded file to validate

    Raises:
        HTTPException(400): File is None
        HTTPException(415): File is not PDF
    """
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is required",
        )
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )


async def _save_uploaded_file(
    file: UploadFile,
    documents_dir: Path,
    max_size_mb: int = 50,
) -> tuple[Path, int]:
    """
    Save uploaded file to temporary location with size validation.

    Args:
        file: Uploaded file
        documents_dir: Base documents directory
        max_size_mb: Maximum file size in MB

    Returns:
        (temp_path, file_size_bytes)

    Raises:
        HTTPException(413): File exceeds size limit
    """
    MAX_SIZE = max_size_mb * 1024 * 1024
    file_size = 0
    temp_path = build_safe_temp_path(documents_dir, file.filename)

    with open(temp_path, "wb") as f:
        while chunk := await file.read(8192):  # 8KB chunks
            file_size += len(chunk)
            if file_size > MAX_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large (max {max_size_mb}MB)",
                )
            f.write(chunk)

    return temp_path, file_size


def _import_and_build_response(
    temp_path: Path,
    title: str | None,
    check_duplicates: bool,
    overwrite_duplicates: bool,
    library_service: IDocumentLibraryService,
) -> DocumentResponse:
    """
    Import document via service and build response.

    Args:
        temp_path: Temporary file path
        title: Optional document title
        check_duplicates: Whether to check for duplicates
        overwrite_duplicates: Whether to overwrite duplicates
        library_service: Document library service

    Returns:
        DocumentResponse with imported document data
    """
    document = library_service.import_document(
        file_path=str(temp_path),
        title=title,
        check_duplicates=check_duplicates,
        overwrite_duplicates=overwrite_duplicates,
    )

    document_data = model_to_response_data(document)

    return DocumentResponse(
        success=True,
        data=document_data,
        errors=None,
    )


def _map_document_import_error(exc: Exception) -> HTTPException:
    """
    Map domain exceptions to HTTP exceptions.

    Args:
        exc: Exception from document import

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, DuplicateDocumentError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.user_message,
        )
    if isinstance(exc, DocumentValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.user_message,
        )
    if isinstance(exc, DocumentImportError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.user_message,
        )
    if isinstance(exc, ValueError):
        if "duplicate" in str(exc).lower():
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )
        else:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    # Generic error
    logger.error(f"Failed to upload document: {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to upload document",
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Upload a new PDF document to the library",
    responses={
        201: {"description": "Document uploaded successfully"},
        400: {"description": "Invalid file or parameters"},
        409: {"description": "Duplicate document exists"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported media type (must be PDF)"},
        500: {"description": "Internal server error"},
    },
)
async def upload_document(
    # File upload (multipart/form-data)
    file: UploadFile = File(..., description="PDF file to upload"),
    # Optional metadata
    title: str | None = Query(
        None, description="Document title (defaults to filename)"
    ),
    check_duplicates: bool = Query(True, description="Check for duplicates"),
    overwrite_duplicates: bool = Query(
        False, description="Overwrite if duplicate found"
    ),
    # Dependencies
    library_service: IDocumentLibraryService = Depends(get_document_library_service),
    documents_dir: Path = Depends(get_documents_dir),
) -> DocumentResponse:
    """Upload a new document to the library with validation and duplicate handling."""
    try:
        # Validate file type and presence
        _validate_file_upload(file)

        # Save file with size validation
        temp_path, _ = await _save_uploaded_file(file, documents_dir)

        try:
            # Import document and build response
            return _import_and_build_response(
                temp_path,
                title,
                check_duplicates,
                overwrite_duplicates,
                library_service,
            )
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    except Exception as e:
        raise _map_document_import_error(e) from e


# ============================================================================
# Download Document
# ============================================================================


@router.get(
    "/{document_id}/download",
    response_class=FileResponse,
    summary="Download document",
    description="Download the PDF file for a document",
    responses={
        200: {"description": "File download"},
        404: {"description": "Document or file not found"},
        500: {"description": "Internal server error"},
    },
)
async def download_document(
    document_id: int,
    doc_repo: IDocumentRepository = Depends(get_document_repository),
    documents_dir: Path = Depends(get_documents_dir),
) -> FileResponse:
    """
    Download document file.

    This endpoint demonstrates:
    - Path traversal prevention (validate_file_path)
    - Secure file serving
    - Proper content-type headers

    Args:
        document_id: Document ID
        doc_repo: Document repository (injected)
        documents_dir: Documents storage directory (injected)

    Returns:
        FileResponse with PDF file

    Raises:
        HTTPException: 404 if document or file not found
    """
    try:
        # Get document from repository
        document = doc_repo.get_by_id(document_id)

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        if not document.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file path is missing",
            )

        # Validate file path (prevent path traversal)
        file_path = Path(document.file_path).expanduser().resolve()

        # Allow per-document storage root overrides tracked in metadata
        allowed_roots = [documents_dir.resolve()]
        storage_root = (document.metadata or {}).get("storage_root")
        if storage_root:
            allowed_roots.insert(0, Path(storage_root))

        if not is_within_allowed_roots(file_path, allowed_roots):
            logger.error(
                f"Path traversal attempt blocked: {file_path} not in allowed roots {allowed_roots}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid file path",
            )

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found on disk",
            )

        # Return file
        return FileResponse(
            path=file_path,
            filename=f"{document.title}.pdf",
            media_type="application/pdf",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document",
        ) from e


# ============================================================================
# Delete Document
# ============================================================================


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and optionally its vector index",
    responses={
        204: {"description": "Document deleted successfully"},
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_document(
    document_id: int,
    remove_index: bool = Query(True, description="Also remove vector index"),
    library_service: IDocumentLibraryService = Depends(get_document_library_service),
) -> None:
    """
    Delete a document from the library.

    Args:
        document_id: Document ID
        remove_index: Whether to also remove vector index
        library_service: Document library service (injected)

    Raises:
        HTTPException: 404 if document not found
    """
    try:
        # Delete document using service
        success = library_service.delete_document(
            document_id=document_id,
            remove_vector_index=remove_index,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # 204 No Content - no response body

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        ) from e
