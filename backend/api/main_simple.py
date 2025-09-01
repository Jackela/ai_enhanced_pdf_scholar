"""
FastAPI Main Application (Simplified for Hypercorn)
Version without lifespan context manager for better Windows/Hypercorn compatibility.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.cors_config import get_cors_config
from backend.api.dependencies import get_db, get_enhanced_rag, get_library_controller
from backend.api.middleware.error_handling import setup_comprehensive_error_handling
from backend.api.middleware.rate_limiting import RateLimitMiddleware
from backend.api.middleware.security_headers import (
    SecurityHeadersConfig,
    setup_security_headers,
)
from backend.api.rate_limit_config import get_env_override_config, get_rate_limit_config
from backend.api.websocket_manager import WebSocketManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize metrics collector
from backend.services.metrics_collector import get_metrics_collector

metrics_collector = get_metrics_collector()

# Initialize configuration objects
cors_config = get_cors_config()
security_headers_config = SecurityHeadersConfig()
rate_limit_config = get_env_override_config(get_rate_limit_config())

# Create FastAPI app WITHOUT lifespan
app = FastAPI(
    title="AI Enhanced PDF Scholar API",
    description="Modern API for intelligent PDF document management and analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure comprehensive error handling
setup_comprehensive_error_handling(app, include_debug_info=False)

# Configure security headers middleware (must be before other middleware)
setup_security_headers(app, security_headers_config)

# Configure rate limiting middleware
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Configure secure CORS based on environment
app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

# Add metrics collection middleware
from backend.services.metrics_service import FastAPIMetricsMiddleware

# Note: add_middleware passes the app automatically as the first argument
# We only need to pass additional arguments as keyword arguments
app.add_middleware(FastAPIMetricsMiddleware, metrics_service=metrics_collector.metrics_service)

# WebSocket manager
websocket_manager = WebSocketManager()

# Include API routes
from backend.api.auth import routes as auth_routes
from backend.api.routes import (
    cache_admin,
    documents,
    library,
    multi_document,
    rag,
    rate_limit_admin,
    settings,
    system,
)

app.include_router(auth_routes.router, prefix="/api", tags=["authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(library.router, prefix="/api/library", tags=["library"])
app.include_router(multi_document.router, prefix="/api/multi-document", tags=["multi-document"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(settings.router, prefix="/api")
app.include_router(rate_limit_admin.router, prefix="/api/admin", tags=["rate-limiting"])
app.include_router(cache_admin.router, prefix="/api/admin", tags=["cache-admin"])

# ============================================================================
# Basic Health Check Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint for basic connectivity test."""
    return {
        "message": "AI Enhanced PDF Scholar API is running",
        "version": "2.0.0",
        "docs": "/api/docs"
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity test."""
    return {"pong": True}

@app.get("/health")
async def basic_health_check():
    """Basic health check endpoint - no dependencies."""
    return {
        "status": "healthy",
        "service": "AI Enhanced PDF Scholar API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check endpoint."""
    try:
        health_status = await metrics_collector.check_comprehensive_health()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ============================================================================
# Monitoring Endpoints
# ============================================================================

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    try:
        metrics_data, content_type = metrics_collector.get_metrics_response()
        return Response(content=metrics_data, media_type=content_type)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics") from e

@app.get("/metrics/dashboard")
async def get_dashboard_metrics():
    """Get formatted metrics for custom dashboard."""
    try:
        dashboard_data = metrics_collector.get_dashboard_metrics()
        return dashboard_data
    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard metrics") from e

# Serve static files for frontend
frontend_dist = project_root / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")

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
                import asyncio
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

# Log startup info
logger.info("AI Enhanced PDF Scholar API (Simplified) initialized")
logger.info("Using simplified startup without lifespan for Hypercorn compatibility")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_simple:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
