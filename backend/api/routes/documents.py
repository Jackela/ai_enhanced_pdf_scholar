"""
Documents API Routes
RESTful API endpoints for document management operations.
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.dependencies import (
    get_api_config,
    get_library_controller,
    get_upload_directory,
    validate_document_access,
)
from backend.api.models import (
    BaseResponse,
    DocumentImportResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    IntegrityCheckResponse,
)
from src.controllers.library_controller import LibraryController
from src.database.models import DocumentModel
from src.services.document_library_service import DuplicateDocumentError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=DocumentListResponse)
async def get_documents(
    search_query: Optional[str] = Query(None, description="Search documents by title"),
    sort_by: str = Query(
        "created_at", regex="^(created_at|updated_at|last_accessed|title|file_size)$"
    ),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    show_missing: bool = Query(
        False, description="Include documents with missing files"
    ),
    controller: LibraryController = Depends(get_library_controller),
) -> DocumentListResponse:
    """Get list of documents with optional filtering and pagination."""
    try:
        # Get documents
        documents = controller.get_documents(
            search_query=search_query,
            limit=per_page * page,  # Simple pagination for now
            sort_by=sort_by,
        )
        # Apply additional filters
        if not show_missing:
            documents = [doc for doc in documents if doc.is_file_available()]
        # Simple pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_docs = documents[start_idx:end_idx]
        # Convert to response models
        doc_responses = []
        for doc in paginated_docs:
            doc_dict = doc.to_api_dict()
            doc_dict["is_file_available"] = doc.is_file_available()
            doc_responses.append(DocumentResponse(**doc_dict))
        return DocumentListResponse(
            documents=doc_responses, total=len(documents), page=page, per_page=per_page
        )
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve documents: {str(e)}",
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> DocumentResponse:
    """Get a specific document by ID."""
    document = validate_document_access(document_id, controller)
    doc_dict = document.to_api_dict()
    doc_dict["is_file_available"] = document.is_file_available()
    return DocumentResponse(**doc_dict)


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
    """Upload and import a new PDF document."""
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed",
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
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size: {config['max_file_size_mb']}MB",
                    )
                temp_file.write(chunk)
        try:
            # Import document (this will copy file to managed storage)
            success = controller.import_document(
                file_path=temp_path,
                title=title or Path(file.filename).stem,
                check_duplicates=check_duplicates,
                auto_build_index=auto_build_index,
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document import failed",
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document imported but could not retrieve details",
            )
        except DuplicateDocumentError as e:
            # Clean up temp file on duplicate error
            Path(temp_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document: {str(e)}",
            )
        except Exception as e:
            # Clean up temp file on any error
            Path(temp_path).unlink(missing_ok=True)
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update failed: {str(e)}",
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Delete operation failed",
            )
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}",
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: int, controller: LibraryController = Depends(get_library_controller)
) -> FileResponse:
    """Download the original PDF file."""
    document = validate_document_access(document_id, controller)
    if not document.file_path or not Path(document.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found"
        )
    try:
        return FileResponse(
            path=document.file_path,
            filename=f"{document.title}.pdf",
            media_type="application/pdf",
        )
    except Exception as e:
        logger.error(f"Failed to serve document file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve file",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Integrity check failed: {str(e)}",
        )
