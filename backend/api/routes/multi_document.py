"""
Multi-Document RAG API Routes
FastAPI routes for document collections and cross-document queries.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_multi_document_rag_service
from backend.api.models.multi_document_models import (
    AddDocumentRequest,
    CollectionIndexResponse,
    CollectionListResponse,
    CollectionResponse,
    CollectionStatisticsResponse,
    CreateCollectionRequest,
    CrossDocumentQueryRequest,
    MultiDocumentQueryResponse,
    QueryHistoryResponse,
    UpdateCollectionRequest,
)
from src.services.multi_document_rag_service import MultiDocumentRAGService

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_collection_to_response(collection) -> CollectionResponse:
    """Convert collection model to API response."""
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        document_ids=collection.document_ids,
        document_count=collection.document_count,
        created_at=collection.created_at.isoformat() if collection.created_at else None,
        updated_at=collection.updated_at.isoformat() if collection.updated_at else None,
    )


def convert_query_to_response(query_model) -> MultiDocumentQueryResponse:
    """Convert query model to API response."""
    from backend.api.models.multi_document_models import (
        CrossReferenceResponse,
        DocumentSourceResponse,
    )

    sources = [
        DocumentSourceResponse(
            document_id=s.document_id,
            relevance_score=s.relevance_score,
            excerpt=s.excerpt,
            page_number=s.page_number,
            chunk_id=s.chunk_id
        )
        for s in query_model.sources
    ]

    cross_refs = [
        CrossReferenceResponse(
            source_doc_id=cr.source_doc_id,
            target_doc_id=cr.target_doc_id,
            relation_type=cr.relation_type,
            confidence=cr.confidence,
            description=cr.description
        )
        for cr in query_model.cross_references
    ]

    return MultiDocumentQueryResponse(
        id=query_model.id,
        query=query_model.query_text,
        answer=query_model.response_text or "",
        confidence=query_model.confidence_score or 0.0,
        sources=sources,
        cross_references=cross_refs,
        processing_time_ms=query_model.processing_time_ms or 0,
        tokens_used=query_model.tokens_used,
        status=query_model.status,
        created_at=query_model.created_at.isoformat() if query_model.created_at else ""
    )


# Collection Management Endpoints

@router.post("/collections", response_model=CollectionResponse)
async def create_collection(
    request: CreateCollectionRequest,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Create a new document collection."""
    try:
        collection = service.create_collection(
            name=request.name,
            description=request.description,
            document_ids=request.document_ids
        )
        return convert_collection_to_response(collection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """List all document collections with pagination."""
    try:
        offset = (page - 1) * limit
        collections = service.get_all_collections()

        # Simple pagination (should be done in repository layer)
        total_count = len(collections)
        paginated_collections = collections[offset:offset + limit]

        collection_responses = [
            convert_collection_to_response(c) for c in paginated_collections
        ]

        return CollectionListResponse(
            collections=collection_responses,
            total_count=total_count,
            page=page,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: int,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Get a specific collection by ID."""
    try:
        collection = service.get_collection(collection_id)
        return convert_collection_to_response(collection)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    request: UpdateCollectionRequest,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Update a collection's metadata."""
    try:
        collection = service.get_collection(collection_id)

        if request.name is not None:
            collection.name = request.name
        if request.description is not None:
            collection.description = request.description

        # Note: This would need a proper update method in the service
        # For now, just return the collection
        return convert_collection_to_response(collection)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: int,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Delete a collection and its associated index."""
    try:
        success = service.delete_collection(collection_id)
        if not success:
            raise HTTPException(status_code=404, detail="Collection not found")
        return {"message": "Collection deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/collections/{collection_id}/documents", response_model=CollectionResponse)
async def add_document_to_collection(
    collection_id: int,
    request: AddDocumentRequest,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Add a document to a collection."""
    try:
        collection = service.add_document_to_collection(
            collection_id, request.document_id
        )
        return convert_collection_to_response(collection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add document to collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/collections/{collection_id}/documents/{document_id}")
async def remove_document_from_collection(
    collection_id: int,
    document_id: int,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Remove a document from a collection."""
    try:
        collection = service.remove_document_from_collection(collection_id, document_id)
        return convert_collection_to_response(collection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove document from collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Collection Index Endpoints

@router.post("/collections/{collection_id}/index", response_model=CollectionIndexResponse)
async def create_collection_index(
    collection_id: int,
    background_tasks: BackgroundTasks,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Create or rebuild the vector index for a collection."""
    try:
        # Create index in background for large collections
        def create_index():
            service.create_collection_index(collection_id)

        background_tasks.add_task(create_index)

        return JSONResponse(
            content={"message": "Index creation started", "collection_id": collection_id},
            status_code=202
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create index for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/collections/{collection_id}/statistics", response_model=CollectionStatisticsResponse)
async def get_collection_statistics(
    collection_id: int,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Get statistics for a collection."""
    try:
        stats = service.get_collection_statistics(collection_id)
        return CollectionStatisticsResponse(**stats)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get collection statistics {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Cross-Document Query Endpoints

@router.post("/collections/{collection_id}/query", response_model=MultiDocumentQueryResponse)
async def query_collection(
    collection_id: int,
    request: CrossDocumentQueryRequest,
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Perform a cross-document query on a collection."""
    try:
        response = await service.query_collection(
            collection_id=collection_id,
            query=request.query,
            user_id=request.user_id,
            max_results=request.max_results
        )

        # Convert service response to API response
        from backend.api.models.multi_document_models import (
            CrossReferenceResponse,
            DocumentSourceResponse,
        )

        sources = [
            DocumentSourceResponse(
                document_id=s.document_id,
                relevance_score=s.relevance_score,
                excerpt=s.excerpt,
                page_number=s.page_number,
                chunk_id=s.chunk_id
            )
            for s in response.sources
        ]

        cross_refs = [
            CrossReferenceResponse(
                source_doc_id=cr.source_doc_id,
                target_doc_id=cr.target_doc_id,
                relation_type=cr.relation_type,
                confidence=cr.confidence,
                description=cr.description
            )
            for cr in response.cross_references
        ]

        return MultiDocumentQueryResponse(
            id=0,  # Would be set from query model if returned
            query=request.query,
            answer=response.answer,
            confidence=response.confidence,
            sources=sources,
            cross_references=cross_refs,
            processing_time_ms=response.processing_time_ms,
            tokens_used=response.tokens_used,
            status="completed",
            created_at=""  # Would be set from query model
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to query collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/collections/{collection_id}/queries", response_model=QueryHistoryResponse)
async def get_query_history(
    collection_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: str | None = Query(None),
    service: MultiDocumentRAGService = Depends(get_multi_document_rag_service)
):
    """Get query history for a collection."""
    try:
        # This would need to be implemented in the service
        # For now, return empty list
        return QueryHistoryResponse(
            queries=[],
            total_count=0,
            page=page,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Failed to get query history for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
