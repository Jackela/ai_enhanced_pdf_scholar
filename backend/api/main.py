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
from datetime import datetime
from pathlib import Path

import uvicorn
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

# Models are used in individual route modules
from backend.api.routes import settings
from backend.api.websocket_manager import WebSocketManager
from src.database import DatabaseMigrator
from src.database.connection import DatabaseConnection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize metrics collector
from backend.services.metrics_collector import get_metrics_collector

metrics_collector = get_metrics_collector()
# Create FastAPI app
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
security_headers_config = SecurityHeadersConfig()
setup_security_headers(app, security_headers_config)

# Configure rate limiting middleware
rate_limit_config = get_env_override_config(get_rate_limit_config())
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Configure secure CORS based on environment
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

# Add metrics collection middleware
from backend.services.metrics_service import FastAPIMetricsMiddleware

app.add_middleware(FastAPIMetricsMiddleware, app, metrics_collector.metrics_service)

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

@app.get("/health")
async def health_check():
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

        # Log CORS security configuration
        cors_config.log_security_info()

        # Log security headers configuration
        logger.info("Security headers initialized:")
        logger.info(f"  - Environment: {security_headers_config.environment.value}")
        logger.info(f"  - CSP: {'Enabled' if security_headers_config.csp_enabled else 'Disabled'}")
        logger.info(f"  - CSP Mode: {'Report-Only' if security_headers_config.csp_report_only else 'Enforcing'}")
        logger.info(f"  - HSTS: {'Enabled' if security_headers_config.strict_transport_security_enabled else 'Disabled'}")
        logger.info(f"  - Nonce-based CSP: {'Enabled' if security_headers_config.nonce_enabled else 'Disabled'}")

        # Log rate limiting configuration
        logger.info("Rate limiting initialized:")
        logger.info(f"  - Default limit: {rate_limit_config.default_limit.requests} requests/{rate_limit_config.default_limit.window}s")
        logger.info(f"  - Global IP limit: {rate_limit_config.global_ip_limit.requests} requests/{rate_limit_config.global_ip_limit.window}s")
        logger.info(f"  - Storage backend: {'Redis' if rate_limit_config.redis_url else 'In-Memory'}")
        logger.info(f"  - Environment: {os.getenv('ENVIRONMENT', 'development')}")

        # Initialize database
        db_dir = Path.home() / ".ai_pdf_scholar"
        db_dir.mkdir(exist_ok=True)
        db_path = db_dir / "documents.db"
        # Run migrations if needed
        # Use context manager to ensure connection is properly closed
        with DatabaseConnection(str(db_path)) as db:
            migrator = DatabaseMigrator(db)
            if migrator.needs_migration():
                logger.info("Running database migrations...")
                migrator.migrate()
        # Connection automatically closed after migration
        # Initialize cache system
        try:
            from backend.services.cache_service_integration import (
                initialize_application_cache,
            )
            cache_initialized = await initialize_application_cache(metrics=metrics_collector.metrics_service)
            if cache_initialized:
                logger.info("Multi-layer cache system initialized")
            else:
                logger.info("Cache system disabled or initialization failed")
        except Exception as cache_error:
            logger.warning(f"Cache system initialization failed: {cache_error}")

        logger.info("API startup completed successfully")
        logger.info("Unified error handling system active")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down AI Enhanced PDF Scholar API...")

    # Shutdown cache system
    try:
        from backend.services.cache_service_integration import (
            shutdown_application_cache,
        )
        await shutdown_application_cache()
        logger.info("Cache system shutdown completed")
    except Exception as cache_error:
        logger.warning(f"Cache system shutdown error: {cache_error}")

    # Add other cleanup logic here if needed
    logger.info("API shutdown completed")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
