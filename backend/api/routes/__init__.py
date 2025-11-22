"""API router aggregator for the v2 surface."""

from fastapi import APIRouter

from backend.api.routes import documents, indexes, queries

api_router = APIRouter()

api_router.include_router(documents.router, prefix="/documents")
api_router.include_router(queries.router, prefix="/queries")
api_router.include_router(indexes.router, prefix="/indexes")

__all__ = ["api_router"]
