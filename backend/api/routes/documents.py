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
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.dependencies import (
    get_document_library_service,
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
from src.database.models import DocumentModel
from src.interfaces.repository_interfaces import IDocumentRepository
from src.interfaces.service_interfaces import IDocumentLibraryService

logger = logging.getLogger(__name__)

# Note: No prefix here because it's set in main.py when including the router
router = APIRouter(tags=["documents"])


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
        },
    )

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
    query: str
    | None = Query(
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
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents",
        )


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
        )


# ============================================================================
# Upload Document
# ============================================================================


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
    title: str
    | None = Query(None, description="Document title (defaults to filename)"),
    check_duplicates: bool = Query(True, description="Check for duplicates"),
    overwrite_duplicates: bool = Query(
        False, description="Overwrite if duplicate found"
    ),
    # Dependencies
    library_service: IDocumentLibraryService = Depends(get_document_library_service),
    documents_dir: Path = Depends(get_documents_dir),
) -> DocumentResponse:
    """
    Upload a new document to the library.

    This endpoint demonstrates:
    - File upload handling with FastAPI
    - Business logic delegation to service layer
    - Duplicate detection
    - Proper error handling with specific status codes

    Args:
        file: Uploaded PDF file
        title: Optional document title
        check_duplicates: Whether to check for duplicates
        overwrite_duplicates: Whether to overwrite duplicates
        library_service: Document library service (injected)
        documents_dir: Documents storage directory (injected)

    Returns:
        DocumentResponse with uploaded document data

    Raises:
        HTTPException: Various status codes for different errors
    """
    try:
        # Validate file type
        if not file.content_type == "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF files are supported",
            )

        # Validate file size (50MB limit)
        MAX_SIZE = 50 * 1024 * 1024  # 50MB
        file_size = 0

        # Save file to sanitized temporary location
        temp_path = build_safe_temp_path(documents_dir, file.filename)
        try:
            with open(temp_path, "wb") as f:
                while chunk := await file.read(8192):  # 8KB chunks
                    file_size += len(chunk)
                    if file_size > MAX_SIZE:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File too large (max {MAX_SIZE // 1024 // 1024}MB)",
                        )
                    f.write(chunk)

            # Import document using service
            document = library_service.import_document(
                file_path=str(temp_path),
                title=title,
                check_duplicates=check_duplicates,
                overwrite_duplicates=overwrite_duplicates,
            )

            # Convert to response format
            document_data = model_to_response_data(document)

            return DocumentResponse(
                success=True,
                data=document_data,
                errors=None,
            )

        finally:
            # Clean up temp file if it still exists
            if temp_path.exists():
                temp_path.unlink()

    except HTTPException:
        raise
    except ValueError as e:
        # Duplicate document or validation error
        if "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except Exception as e:
        logger.error(f"Failed to upload document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


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
        )


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
        )
