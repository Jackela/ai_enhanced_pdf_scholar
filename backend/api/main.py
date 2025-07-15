"""
FastAPI Main Application

Modern web API for AI Enhanced PDF Scholar with document library management,
RAG functionality, and real-time features.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.dependencies import get_db, get_enhanced_rag, get_library_controller
from backend.api.models import *
from backend.api.routes import settings
from backend.api.websocket_manager import WebSocketManager
from src.controllers.library_controller import LibraryController
from src.database.connection import DatabaseConnection
from src.database.migrations import DatabaseMigrator
from src.services.enhanced_rag_service import EnhancedRAGService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Enhanced PDF Scholar API",
    description="Modern API for intelligent PDF document management and analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager
websocket_manager = WebSocketManager()

# Include API routes
from backend.api.routes import documents, library, rag, system

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(library.router, prefix="/api/library", tags=["library"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(settings.router, prefix="/api")

# Serve static files for frontend
frontend_dist = project_root / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")

    @app.get("/", response_model=None)
    async def serve_frontend() -> FileResponse | HTMLResponse:
        """Serve the main frontend application."""
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse("<h1>Frontend not built yet</h1>")

else:

    @app.get("/", response_model=None)
    async def root() -> HTMLResponse:
        return HTMLResponse(
            """
        <html>
            <head><title>AI Enhanced PDF Scholar</title></head>
            <body>
                <h1>🚀 AI Enhanced PDF Scholar API</h1>
                <p>Backend is running! Frontend will be available once built.</p>
                <ul>
                    <li><a href="/api/docs">API Documentation</a></li>
                    <li><a href="/api/redoc">ReDoc Documentation</a></li>
                </ul>
            </body>
        </html>
        """
        )


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """WebSocket endpoint for real-time communication."""
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "pong"}), client_id
                )
            elif message.get("type") == "rag_query":
                # Handle RAG query in background
                asyncio.create_task(
                    handle_rag_query_websocket(
                        message.get("query", ""), message.get("document_id"), client_id
                    )
                )

    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"WebSocket client {client_id} disconnected")


async def handle_rag_query_websocket(
    query: str, document_id: int, client_id: str
) -> None:
    """Handle RAG query via WebSocket."""
    try:
        # Get services using dependency injection
        db = next(get_db())
        enhanced_rag = get_enhanced_rag(db)
        controller = get_library_controller(db, enhanced_rag)

        # Send progress update
        await websocket_manager.send_personal_message(
            json.dumps(
                {"type": "rag_progress", "message": "正在分析文档并生成回答..."}
            ),
            client_id,
        )

        # Perform query
        response = controller.query_document(document_id, query)

        # Send result
        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "rag_response",
                    "query": query,
                    "response": response,
                    "document_id": document_id,
                }
            ),
            client_id,
        )

    except Exception as e:
        logger.error(f"WebSocket RAG query failed: {e}")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "rag_error", "error": str(e)}), client_id
        )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    try:
        logger.info("Starting AI Enhanced PDF Scholar API...")

        # Initialize database
        db_dir = Path.home() / ".ai_pdf_scholar"
        db_dir.mkdir(exist_ok=True)
        db_path = db_dir / "documents.db"

        # Run migrations if needed
        db = DatabaseConnection(str(db_path))
        migrator = DatabaseMigrator(db)
        if migrator.needs_migration():
            logger.info("Running database migrations...")
            migrator.migrate()

        logger.info("API startup completed successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down AI Enhanced PDF Scholar API...")
    # Add cleanup logic here if needed


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
