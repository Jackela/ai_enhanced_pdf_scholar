"""
Citations API Routes
RESTful endpoints for citation management and analysis.

Implements:
- Citation extraction from documents
- Citation CRUD operations
- Citation search and filtering
- Citation network analysis
- Export functionality (BibTeX, JSON, CSV)

References:
- ADR-001: V2.0 Architecture Principles
- API_ENDPOINTS.md: Citation management endpoints
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import PlainTextResponse, Response

from backend.api.dependencies import (
    get_db,
    get_document_repository,
)
from backend.api.models.responses import (
    APIResponse,
    ErrorDetail,
    Meta,
    PaginatedResponse,
)
from src.database.connection import DatabaseConnection
from src.database.models import CitationModel
from src.exceptions import DatabaseError, ResourceNotFoundError, ValidationError
from src.interfaces.repository_interfaces import (
    ICitationRelationRepository,
    ICitationRepository,
    IDocumentRepository,
)
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.services.citation_service import CitationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["citations"])


# ============================================================================
# Dependency Injection
# ============================================================================

def get_citation_repository(
    db: DatabaseConnection = Depends(get_db),
) -> ICitationRepository:
    """Provide a CitationRepository instance."""
    return CitationRepository(db)


def get_citation_relation_repository(
    db: DatabaseConnection = Depends(get_db),
) -> ICitationRelationRepository:
    """Provide a CitationRelationRepository instance."""
    return CitationRelationRepository(db)


def get_citation_service(
    citation_repo: ICitationRepository = Depends(get_citation_repository),
    relation_repo: ICitationRelationRepository = Depends(get_citation_relation_repository),
) -> CitationService:
    """Provide a CitationService instance."""
    return CitationService(citation_repo, relation_repo)


# ============================================================================
# Request/Response Models
# ============================================================================

from pydantic import BaseModel, Field


class CitationData(BaseModel):
    """Citation data for API responses."""

    id: int | None = Field(None, description="Citation ID")
    document_id: int = Field(..., description="Source document ID")
    raw_text: str = Field(..., description="Raw citation text")
    authors: str | None = Field(None, description="Authors")
    title: str | None = Field(None, description="Title")
    publication_year: int | None = Field(None, description="Publication year")
    journal_or_venue: str | None = Field(None, description="Journal or venue")
    doi: str | None = Field(None, description="DOI")
    page_range: str | None = Field(None, description="Page range")
    citation_type: str | None = Field(None, description="Citation type (journal, conference, etc.)")
    confidence_score: float | None = Field(None, ge=0, le=1, description="Confidence score")
    created_at: str | None = Field(None, description="Creation timestamp")
    updated_at: str | None = Field(None, description="Update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "document_id": 5,
                "raw_text": "Smith, J. (2023). Machine Learning Fundamentals. Journal of AI, 15(3), 123-145.",
                "authors": "Smith, J.",
                "title": "Machine Learning Fundamentals",
                "publication_year": 2023,
                "journal_or_venue": "Journal of AI",
                "doi": "10.1000/jai.2023.001",
                "page_range": "123-145",
                "citation_type": "journal",
                "confidence_score": 0.95,
                "created_at": "2025-01-19T10:30:00Z",
                "updated_at": "2025-01-19T10:30:00Z",
            }
        }


class CitationListData(BaseModel):
    """Citation list with pagination info."""

    citations: list[CitationData]
    total: int
    page: int
    limit: int
    total_pages: int


class CitationExtractRequest(BaseModel):
    """Request model for citation extraction."""

    text_content: str | None = Field(None, description="Optional text content to parse")
    force_reparse: bool = Field(False, description="Force reparse even if citations exist")


class CitationExtractResponseData(BaseModel):
    """Response data for citation extraction."""

    citations: list[CitationData]
    total_extracted: int
    high_confidence_count: int
    average_confidence: float


class CitationUpdateRequest(BaseModel):
    """Request model for updating a citation."""

    authors: str | None = Field(None, description="Authors")
    title: str | None = Field(None, description="Title")
    publication_year: int | None = Field(None, description="Publication year")
    journal_or_venue: str | None = Field(None, description="Journal or venue")
    doi: str | None = Field(None, description="DOI")
    page_range: str | None = Field(None, description="Page range")
    citation_type: str | None = Field(None, description="Citation type")


class CitationNetworkNode(BaseModel):
    """Node in citation network."""

    id: str = Field(..., description="Node ID")
    type: str = Field(..., description="Node type (document/citation)")
    title: str = Field(..., description="Node title")
    citation_count: int | None = Field(None, description="Citation count")


class CitationNetworkEdge(BaseModel):
    """Edge in citation network."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relation type")
    confidence: float | None = Field(None, description="Confidence score")
    citation_text: str | None = Field(None, description="Citation text")


class CitationNetworkData(BaseModel):
    """Citation network data."""

    nodes: list[CitationNetworkNode]
    edges: list[CitationNetworkEdge]


class CitationNetworkMetrics(BaseModel):
    """Metrics for citation network."""

    total_nodes: int
    total_edges: int
    max_depth_reached: int
    average_confidence: float


class CitationNetworkResponseData(BaseModel):
    """Response data for citation network."""

    network: CitationNetworkData
    metrics: CitationNetworkMetrics


class CitationSearchParams(BaseModel):
    """Search parameters for citations."""

    author: str | None = Field(None, description="Author name (fuzzy match)")
    title: str | None = Field(None, description="Title keywords")
    year_from: int | None = Field(None, description="Start year")
    year_to: int | None = Field(None, description="End year")
    citation_type: str | None = Field(None, description="Citation type")
    doi: str | None = Field(None, description="DOI exact match")
    min_confidence: float = Field(0.0, ge=0, le=1, description="Minimum confidence score")
    limit: int = Field(50, ge=1, le=200, description="Result limit")


class CitationStatisticsData(BaseModel):
    """Citation statistics data."""

    total_citations: int
    complete_citations: int
    average_confidence_score: float
    by_type: dict[str, int]
    by_year: dict[str, int]
    high_confidence_count: int
    documents_with_citations: int


class ExportResponseData(BaseModel):
    """Export response data."""

    format: str
    total_exported: int
    content: str


# ============================================================================
# Typed Response Aliases
# ============================================================================

CitationResponse = APIResponse[CitationData]
CitationListResponse = PaginatedResponse[CitationData]
CitationExtractResponse = APIResponse[CitationExtractResponseData]
CitationNetworkResponse = APIResponse[CitationNetworkResponseData]
CitationStatisticsResponse = APIResponse[CitationStatisticsData]
CitationExportResponse = APIResponse[ExportResponseData]


# ============================================================================
# Helper Functions
# ============================================================================

def model_to_citation_data(citation: CitationModel) -> CitationData:
    """Convert CitationModel to CitationData response."""
    return CitationData(
        id=citation.id,
        document_id=citation.document_id,
        raw_text=citation.raw_text,
        authors=citation.authors,
        title=citation.title,
        publication_year=citation.publication_year,
        journal_or_venue=citation.journal_or_venue,
        doi=citation.doi,
        page_range=citation.page_range,
        citation_type=citation.citation_type,
        confidence_score=citation.confidence_score,
        created_at=citation.created_at.isoformat() if citation.created_at else None,
        updated_at=citation.updated_at.isoformat() if citation.updated_at else None,
    )


def validate_document_exists(
    document_id: int,
    doc_repo: IDocumentRepository,
) -> None:
    """Validate that a document exists."""
    document = doc_repo.get_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )


def format_bibtex(citation: CitationModel) -> str:
    """Format citation as BibTeX entry."""
    cite_key = f"cite{citation.id}"
    lines = [f"@article{{{cite_key},"]
    
    if citation.title:
        lines.append(f"  title={{{citation.title}}},")
    if citation.authors:
        lines.append(f"  author={{{citation.authors}}},")
    if citation.journal_or_venue:
        lines.append(f"  journal={{{citation.journal_or_venue}}},")
    if citation.publication_year:
        lines.append(f"  year={{{citation.publication_year}}},")
    if citation.doi:
        lines.append(f"  doi={{{citation.doi}}},")
    if citation.page_range:
        lines.append(f"  pages={{{citation.page_range}}},")
    
    lines.append("}")
    return "\n".join(lines)


def format_csv(citations: list[CitationModel]) -> str:
    """Format citations as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "id", "document_id", "authors", "title", "publication_year",
        "journal_or_venue", "doi", "page_range", "citation_type", "confidence_score"
    ])
    
    # Data rows
    for c in citations:
        writer.writerow([
            c.id, c.document_id, c.authors, c.title, c.publication_year,
            c.journal_or_venue, c.doi, c.page_range, c.citation_type, c.confidence_score
        ])
    
    return output.getvalue()


def format_json_export(citations: list[CitationModel]) -> str:
    """Format citations as JSON string."""
    import json
    data = [c.to_api_dict() for c in citations]
    return json.dumps(data, indent=2, default=str)


# ============================================================================
# Citation Extraction
# ============================================================================

@router.post(
    "/extract/{document_id}",
    response_model=CitationExtractResponse,
    summary="Extract citations from document",
    description="Extract academic citations from a specified document",
    responses={
        200: {"description": "Citations extracted successfully"},
        404: {"description": "Document not found"},
        400: {"description": "Invalid request parameters"},
        500: {"description": "Internal server error"},
    },
)
async def extract_citations(
    document_id: int,
    request: CitationExtractRequest,
    citation_service: CitationService = Depends(get_citation_service),
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> CitationExtractResponse:
    """
    Extract citations from a document.

    Args:
        document_id: Document ID to extract citations from
        request: Extraction request with optional text content
        citation_service: Citation service (injected)
        doc_repo: Document repository (injected)

    Returns:
        CitationExtractResponse with extracted citations

    Raises:
        HTTPException: 404 if document not found, 400 on validation error
    """
    try:
        # Validate document exists
        document = doc_repo.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # Extract citations using service
        citations = citation_service.extract_citations_from_document(document)

        # Convert to response format
        citation_data = [model_to_citation_data(c) for c in citations]

        # Calculate statistics
        total_extracted = len(citations)
        high_confidence_count = sum(
            1 for c in citations
            if c.confidence_score and c.confidence_score >= 0.8
        )
        avg_confidence = (
            sum(c.confidence_score or 0 for c in citations) / total_extracted
            if total_extracted > 0
            else 0.0
        )

        return CitationExtractResponse(
            success=True,
            data=CitationExtractResponseData(
                citations=citation_data,
                total_extracted=total_extracted,
                high_confidence_count=high_confidence_count,
                average_confidence=round(avg_confidence, 2),
            ),
            meta=Meta(),
            errors=None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error extracting citations: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to extract citations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract citations",
        ) from e


# ============================================================================
# Get Citations for Document
# ============================================================================

@router.get(
    "/document/{document_id}",
    response_model=CitationListResponse,
    summary="Get document citations",
    description="Get all citations for a specific document with pagination",
    responses={
        200: {"description": "Citations retrieved successfully"},
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_document_citations(
    document_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    min_confidence: float = Query(0.0, ge=0, le=1, description="Minimum confidence filter"),
    citation_service: CitationService = Depends(get_citation_service),
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> CitationListResponse:
    """
    Get all citations for a specific document.

    Args:
        document_id: Document ID
        page: Page number for pagination
        limit: Items per page
        min_confidence: Minimum confidence score filter
        citation_service: Citation service (injected)
        doc_repo: Document repository (injected)

    Returns:
        CitationListResponse with paginated citations

    Raises:
        HTTPException: 404 if document not found
    """
    try:
        # Validate document exists
        validate_document_exists(document_id, doc_repo)

        # Get citations from service
        citations = citation_service.get_citations_for_document(document_id)

        # Filter by confidence if specified
        if min_confidence > 0:
            citations = [
                c for c in citations
                if c.confidence_score and c.confidence_score >= min_confidence
            ]

        # Pagination
        total = len(citations)
        total_pages = (total + limit - 1) // limit
        offset = (page - 1) * limit
        paginated_citations = citations[offset:offset + limit]

        # Convert to response format
        citation_data = [model_to_citation_data(c) for c in paginated_citations]

        from backend.api.models.responses import PaginationMeta
        return CitationListResponse(
            success=True,
            data=citation_data,
            meta=PaginationMeta(
                page=page,
                per_page=limit,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get citations for document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citations",
        ) from e


# ============================================================================
# Get Single Citation
# ============================================================================

@router.get(
    "/{citation_id}",
    response_model=CitationResponse,
    summary="Get citation by ID",
    description="Get detailed information about a specific citation",
    responses={
        200: {"description": "Citation retrieved successfully"},
        404: {"description": "Citation not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_citation(
    citation_id: int,
    citation_repo: ICitationRepository = Depends(get_citation_repository),
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> CitationResponse:
    """
    Get a specific citation by ID.

    Args:
        citation_id: Citation ID
        citation_repo: Citation repository (injected)
        doc_repo: Document repository (injected)

    Returns:
        CitationResponse with citation data

    Raises:
        HTTPException: 404 if citation not found
    """
    try:
        citation = citation_repo.get_by_id(citation_id)
        if citation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citation {citation_id} not found",
            )

        return CitationResponse(
            success=True,
            data=model_to_citation_data(citation),
            meta=Meta(),
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get citation {citation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citation",
        ) from e


# ============================================================================
# Update Citation
# ============================================================================

@router.put(
    "/{citation_id}",
    response_model=CitationResponse,
    summary="Update citation",
    description="Update citation information (manual correction)",
    responses={
        200: {"description": "Citation updated successfully"},
        404: {"description": "Citation not found"},
        400: {"description": "Invalid update data"},
        500: {"description": "Internal server error"},
    },
)
async def update_citation(
    citation_id: int,
    request: CitationUpdateRequest,
    citation_service: CitationService = Depends(get_citation_service),
    citation_repo: ICitationRepository = Depends(get_citation_repository),
) -> CitationResponse:
    """
    Update an existing citation.

    Args:
        citation_id: Citation ID to update
        request: Update request with new citation data
        citation_service: Citation service (injected)
        citation_repo: Citation repository (injected)

    Returns:
        CitationResponse with updated citation data

    Raises:
        HTTPException: 404 if citation not found, 400 on validation error
    """
    try:
        # Get existing citation
        existing = citation_repo.get_by_id(citation_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citation {citation_id} not found",
            )

        # Update fields if provided
        if request.authors is not None:
            existing.authors = request.authors
        if request.title is not None:
            existing.title = request.title
        if request.publication_year is not None:
            existing.publication_year = request.publication_year
        if request.journal_or_venue is not None:
            existing.journal_or_venue = request.journal_or_venue
        if request.doi is not None:
            existing.doi = request.doi
        if request.page_range is not None:
            existing.page_range = request.page_range
        if request.citation_type is not None:
            existing.citation_type = request.citation_type

        # Update timestamp
        existing.updated_at = datetime.now()

        # Save via service
        updated = citation_service.update_citation(existing)

        return CitationResponse(
            success=True,
            data=model_to_citation_data(updated),
            meta=Meta(),
            errors=None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating citation {citation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to update citation {citation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update citation",
        ) from e


# ============================================================================
# Delete Citation
# ============================================================================

@router.delete(
    "/{citation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete citation",
    description="Delete a specific citation",
    responses={
        204: {"description": "Citation deleted successfully"},
        404: {"description": "Citation not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_citation(
    citation_id: int,
    citation_service: CitationService = Depends(get_citation_service),
) -> None:
    """
    Delete a citation.

    Args:
        citation_id: Citation ID to delete
        citation_service: Citation service (injected)

    Raises:
        HTTPException: 404 if citation not found
    """
    try:
        success = citation_service.delete_citation(citation_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citation {citation_id} not found",
            )
        # 204 No Content - no response body

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete citation {citation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete citation",
        ) from e


# ============================================================================
# Search Citations
# ============================================================================

@router.get(
    "/search",
    response_model=CitationListResponse,
    summary="Search citations",
    description="Search citations by various criteria",
    responses={
        200: {"description": "Search completed successfully"},
        400: {"description": "Invalid search parameters"},
        500: {"description": "Internal server error"},
    },
)
async def search_citations(
    author: str | None = Query(None, description="Author name (fuzzy match)"),
    title: str | None = Query(None, description="Title keywords"),
    year_from: int | None = Query(None, description="Start year"),
    year_to: int | None = Query(None, description="End year"),
    citation_type: str | None = Query(None, description="Citation type filter"),
    doi: str | None = Query(None, description="DOI exact match"),
    min_confidence: float = Query(0.0, ge=0, le=1, description="Minimum confidence"),
    limit: int = Query(50, ge=1, le=200, description="Result limit"),
    page: int = Query(1, ge=1, description="Page number"),
    citation_repo: ICitationRepository = Depends(get_citation_repository),
) -> CitationListResponse:
    """
    Search citations by various criteria.

    Args:
        author: Author name for fuzzy matching
        title: Title keywords
        year_from: Start year for year range
        year_to: End year for year range
        citation_type: Citation type filter
        doi: DOI for exact matching
        min_confidence: Minimum confidence score
        limit: Maximum results to return
        page: Page number for pagination
        citation_repo: Citation repository (injected)

    Returns:
        CitationListResponse with matching citations

    Raises:
        HTTPException: 400 on invalid search parameters
    """
    try:
        citations: list[CitationModel] = []

        # Search by specific criteria
        if doi:
            citation = citation_repo.find_by_doi(doi)
            if citation:
                citations = [citation]
        elif author:
            citations = citation_repo.search_by_author(author, limit)
        elif title:
            citations = citation_repo.search_by_title(title, limit)
        elif year_from is not None and year_to is not None:
            citations = citation_repo.find_by_year_range(year_from, year_to)
        elif citation_type:
            citations = citation_repo.get_by_type(citation_type)
        else:
            # No specific filter - this would need a get_all method
            # For now, return empty or use statistics to get all
            citations = []

        # Filter by confidence
        if min_confidence > 0:
            citations = [
                c for c in citations
                if c.confidence_score and c.confidence_score >= min_confidence
            ]

        # Pagination
        total = len(citations)
        total_pages = (total + limit - 1) // limit
        offset = (page - 1) * limit
        paginated_citations = citations[offset:offset + limit]

        citation_data = [model_to_citation_data(c) for c in paginated_citations]

        from backend.api.models.responses import PaginationMeta
        return CitationListResponse(
            success=True,
            data=citation_data,
            meta=PaginationMeta(
                page=page,
                per_page=limit,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
            errors=None,
        )

    except ValueError as e:
        logger.warning(f"Invalid search parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to search citations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search citations",
        ) from e


# ============================================================================
# Get Citation Network
# ============================================================================

@router.get(
    "/network/{document_id}",
    response_model=CitationNetworkResponse,
    summary="Get citation network",
    description="Build citation network centered on a document",
    responses={
        200: {"description": "Network built successfully"},
        404: {"description": "Document not found"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Internal server error"},
    },
)
async def get_citation_network(
    document_id: int,
    depth: int = Query(1, ge=1, le=3, description="Network depth (1-3)"),
    min_confidence: float = Query(0.5, ge=0, le=1, description="Minimum relation confidence"),
    citation_service: CitationService = Depends(get_citation_service),
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> CitationNetworkResponse:
    """
    Build citation network for a document.

    Args:
        document_id: Center document ID
        depth: Network depth to traverse (1-3)
        min_confidence: Minimum confidence for relations
        citation_service: Citation service (injected)
        doc_repo: Document repository (injected)

    Returns:
        CitationNetworkResponse with network data

    Raises:
        HTTPException: 404 if document not found, 400 on validation error
    """
    try:
        # Validate document exists
        validate_document_exists(document_id, doc_repo)

        # Build network via service
        network_data = citation_service.build_citation_network(document_id, depth)

        # Convert nodes
        nodes = [
            CitationNetworkNode(
                id=node.get("id", ""),
                type=node.get("type", "document"),
                title=node.get("title", "Unknown"),
                citation_count=node.get("citation_count"),
            )
            for node in network_data.get("nodes", [])
        ]

        # Convert edges
        edges = [
            CitationNetworkEdge(
                source=edge.get("source", ""),
                target=edge.get("target", ""),
                type=edge.get("type", "cites"),
                confidence=edge.get("confidence"),
                citation_text=edge.get("citation_text"),
            )
            for edge in network_data.get("edges", [])
        ]

        # Build metrics
        edge_metrics = network_data.get("edge_metrics", {})
        metrics = CitationNetworkMetrics(
            total_nodes=len(nodes),
            total_edges=len(edges),
            max_depth_reached=network_data.get("depth", depth),
            average_confidence=edge_metrics.get("avg_confidence", 0.0),
        )

        return CitationNetworkResponse(
            success=True,
            data=CitationNetworkResponseData(
                network=CitationNetworkData(nodes=nodes, edges=edges),
                metrics=metrics,
            ),
            meta=Meta(),
            errors=None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error building network: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to build citation network: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build citation network",
        ) from e


# ============================================================================
# Export Citations
# ============================================================================

@router.post(
    "/export/{format}",
    response_model=CitationExportResponse,
    summary="Export citations",
    description="Export citations in various formats (BibTeX, JSON, CSV)",
    responses={
        200: {"description": "Export completed successfully"},
        400: {"description": "Invalid format or parameters"},
        500: {"description": "Internal server error"},
    },
)
async def export_citations(
    format: str,
    document_id: int | None = Query(None, description="Filter by document ID"),
    author: str | None = Query(None, description="Filter by author"),
    year_from: int | None = Query(None, description="Start year"),
    year_to: int | None = Query(None, description="End year"),
    citation_repo: ICitationRepository = Depends(get_citation_repository),
    doc_repo: IDocumentRepository = Depends(get_document_repository),
) -> CitationExportResponse:
    """
    Export citations in specified format.

    Args:
        format: Export format (bibtex, json, csv)
        document_id: Optional document ID filter
        author: Optional author filter
        year_from: Optional start year filter
        year_to: Optional end year filter
        citation_repo: Citation repository (injected)
        doc_repo: Document repository (injected)

    Returns:
        CitationExportResponse with exported content

    Raises:
        HTTPException: 400 for invalid format
    """
    try:
        # Validate format
        format_lower = format.lower()
        if format_lower not in ("bibtex", "json", "csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {format}. Use bibtex, json, or csv.",
            )

        # Get citations to export
        citations: list[CitationModel] = []

        if document_id:
            # Validate document exists
            validate_document_exists(document_id, doc_repo)
            citations = citation_repo.find_by_document_id(document_id)
        elif author:
            citations = citation_repo.search_by_author(author, limit=1000)
        elif year_from is not None and year_to is not None:
            citations = citation_repo.find_by_year_range(year_from, year_to)
        else:
            # Get all citations - would need a get_all method
            # For now, get by document IDs
            all_docs = doc_repo.get_all(limit=1000, offset=0)
            for doc in all_docs:
                citations.extend(citation_repo.find_by_document_id(doc.id))

        # Format export content
        if format_lower == "bibtex":
            content = "\n\n".join(format_bibtex(c) for c in citations)
        elif format_lower == "csv":
            content = format_csv(citations)
        else:  # json
            content = format_json_export(citations)

        return CitationExportResponse(
            success=True,
            data=ExportResponseData(
                format=format_lower,
                total_exported=len(citations),
                content=content,
            ),
            meta=Meta(),
            errors=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export citations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export citations",
        ) from e


# ============================================================================
# Get Citation Statistics
# ============================================================================

@router.get(
    "/statistics",
    response_model=CitationStatisticsResponse,
    summary="Get citation statistics",
    description="Get comprehensive citation statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        500: {"description": "Internal server error"},
    },
)
async def get_citation_statistics(
    document_id: int | None = Query(None, description="Optional document ID filter"),
    citation_service: CitationService = Depends(get_citation_service),
    citation_repo: ICitationRepository = Depends(get_citation_repository),
) -> CitationStatisticsResponse:
    """
    Get citation statistics.

    Args:
        document_id: Optional document ID to get stats for
        citation_service: Citation service (injected)
        citation_repo: Citation repository (injected)

    Returns:
        CitationStatisticsResponse with statistics data
    """
    try:
        if document_id:
            # Get stats for specific document
            citations = citation_service.get_citations_for_document(document_id)
            total = len(citations)
            complete = sum(1 for c in citations if c.is_complete())
            high_conf = sum(1 for c in citations if c.confidence_score and c.confidence_score >= 0.8)
            avg_conf = (
                sum(c.confidence_score or 0 for c in citations) / total
                if total > 0
                else 0.0
            )

            # Type breakdown
            by_type: dict[str, int] = {}
            for c in citations:
                ctype = c.citation_type or "unknown"
                by_type[ctype] = by_type.get(ctype, 0) + 1

            # Year breakdown
            by_year: dict[str, int] = {}
            for c in citations:
                if c.publication_year:
                    year_str = str(c.publication_year)
                    by_year[year_str] = by_year.get(year_str, 0) + 1

            stats = CitationStatisticsData(
                total_citations=total,
                complete_citations=complete,
                average_confidence_score=round(avg_conf, 2),
                by_type=by_type,
                by_year=by_year,
                high_confidence_count=high_conf,
                documents_with_citations=1 if total > 0 else 0,
            )
        else:
            # Get global statistics
            repo_stats = citation_repo.get_statistics()
            stats = CitationStatisticsData(
                total_citations=repo_stats.get("total_citations", 0),
                complete_citations=repo_stats.get("complete_citations", 0),
                average_confidence_score=repo_stats.get("avg_confidence_score", 0.0),
                by_type=repo_stats.get("citation_types", {}),
                by_year={str(k): v for k, v in repo_stats.get("years_breakdown", {}).items()},
                high_confidence_count=0,  # Would need to calculate
                documents_with_citations=repo_stats.get("documents_with_citations", 0),
            )

        return CitationStatisticsResponse(
            success=True,
            data=stats,
            meta=Meta(),
            errors=None,
        )

    except Exception as e:
        logger.error(f"Failed to get citation statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve citation statistics",
        ) from e
