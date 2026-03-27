"""API router aggregator for the v2 surface."""

from fastapi import APIRouter

from backend.api.auth import routes as auth_routes
from backend.api.routes import (
    citations,
    documents,
    indexes,
    library,
    multi_document,
    queries,
    settings,
    system,
)

api_router = APIRouter()

# Auth routes (prefix already set in router: /auth)
api_router.include_router(auth_routes.router)

# Document management routes
api_router.include_router(documents.router, prefix="/documents")

# Query routes
api_router.include_router(queries.router, prefix="/queries")

# Index management routes
api_router.include_router(indexes.router, prefix="/indexes")

# Library management routes
api_router.include_router(library.router, prefix="/library")

# Citation management routes
api_router.include_router(citations.router, prefix="/citations")

# Multi-document collection routes
api_router.include_router(multi_document.router, prefix="/multi-document")

# System status and health routes
api_router.include_router(system.router, prefix="/system")

# Settings routes (prefix already set in router: /settings)
api_router.include_router(settings.router)

__all__ = ["api_router"]
