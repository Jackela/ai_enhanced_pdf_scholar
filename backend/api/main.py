"""
FastAPI Main Application
Modern web API for AI Enhanced PDF Scholar with document library management,
RAG functionality, and real-time features.
"""

import asyncio
import importlib
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import uvicorn
from dotenv import load_dotenv

# Load .env file BEFORE any other imports that use env vars
# CRITICAL: Use override=True to override shell environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
print(f"[DEBUG] Loaded .env from: {env_path}")
print(f"[DEBUG] CORS_ORIGINS from env: {os.getenv('CORS_ORIGINS', 'NOT SET')}")
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from backend.api.cors_config import get_cors_config
from backend.api.middleware.error_handling import setup_comprehensive_error_handling
from backend.api.middleware.rate_limiting import RateLimitMiddleware
from backend.api.middleware.security_headers import (
    SecurityHeadersConfig,
    setup_security_headers,
)
from backend.api.rate_limit_config import get_env_override_config, get_rate_limit_config

# Models are used in individual route modules
# from backend.api.routes import settings  # TODO: Re-implement settings route
from backend.api.websocket_manager import WebSocketManager
from src.database import DatabaseMigrator
from src.database.connection import DatabaseConnection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize metrics collector
from backend.services.metrics_collector import get_metrics_collector

metrics_collector = get_metrics_collector()

# Initialize configuration objects that will be used in lifespan
cors_config = get_cors_config()
security_headers_config = SecurityHeadersConfig()
rate_limit_config = get_env_override_config(get_rate_limit_config())


async def _deferred_initialization(db_path: Path) -> None:
    """
    Handle non-essential initializations after server startup.
    This runs in the background to avoid blocking the server from accepting connections.
    """
    try:
        await asyncio.sleep(0.1)  # Small delay to ensure server is fully started

        logger.info("Starting deferred initialization tasks...")

        # Log CORS security configuration
        try:
            cors_config.log_security_info()
        except Exception as e:
            logger.warning(f"Failed to log CORS config: {e}")

        # Log security headers configuration
        try:
            logger.info("Security headers configuration:")
            logger.info(f"  - Environment: {security_headers_config.environment.value}")
            logger.info(
                f"  - CSP: {'Enabled' if security_headers_config.csp_enabled else 'Disabled'}"
            )
            logger.info(
                f"  - CSP Mode: {'Report-Only' if security_headers_config.csp_report_only else 'Enforcing'}"
            )
            logger.info(
                f"  - HSTS: {'Enabled' if security_headers_config.strict_transport_security_enabled else 'Disabled'}"
            )
            logger.info(
                f"  - Nonce-based CSP: {'Enabled' if security_headers_config.nonce_enabled else 'Disabled'}"
            )
        except Exception as e:
            logger.warning(f"Failed to log security headers config: {e}")

        # Log rate limiting configuration
        try:
            logger.info("Rate limiting configuration:")
            logger.info(
                f"  - Default limit: {rate_limit_config.default_limit.requests} requests/{rate_limit_config.default_limit.window}s"
            )
            logger.info(
                f"  - Global IP limit: {rate_limit_config.global_ip_limit.requests} requests/{rate_limit_config.global_ip_limit.window}s"
            )
            logger.info(
                f"  - Storage backend: {'Redis' if rate_limit_config.redis_url else 'In-Memory'}"
            )
            logger.info(f"  - Environment: {os.getenv('ENVIRONMENT', 'development')}")
        except Exception as e:
            logger.warning(f"Failed to log rate limit config: {e}")

        # Run database migrations if needed (non-blocking)
        try:
            # Also disable monitoring here to avoid background blocking
            db = DatabaseConnection(str(db_path), enable_monitoring=False)
            try:
                migrator = DatabaseMigrator(db)
                if migrator.needs_migration():
                    logger.info("Running database migrations in background...")
                    migrator.migrate()
                    logger.info("Database migrations completed")
            finally:
                db.close_all_connections()
        except Exception as e:
            logger.error(f"Background database migration failed: {e}")

        # Initialize cache system (lazy loading)
        try:
            importlib.import_module("backend.services.cache_service_integration")
            logger.info("Cache system ready for initialization on first request")
        except ModuleNotFoundError as e:
            if e.name == "sklearn":
                logger.warning(
                    "Cache system preparation skipped: scikit-learn is not installed. "
                    "Install optional ML cache dependencies "
                    '(`pip install -r requirements-scaling.txt` or `pip install ".[cache-ml]"`) '
                    "or set CACHE_ML_OPTIMIZATIONS_ENABLED=false."
                )
            else:
                logger.warning(f"Cache system preparation failed: {e}")
        except Exception as e:
            logger.warning(f"Cache system preparation failed: {e}")

        logger.info("Deferred initialization completed")

    except Exception as e:
        logger.error(f"Deferred initialization error (non-critical): {e}")
        # Don't raise - this shouldn't crash the server


# Define lifespan context manager for proper ASGI lifespan handling
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events.

    REFACTORED: Minimized startup time by deferring non-essential initializations.
    Only critical database setup happens during startup. All logging and cache
    initialization are deferred to background tasks after server starts.
    """
    # Startup - MINIMAL for fastest possible startup
    try:
        logger.info("Starting API server (fast startup mode)...")

        # CRITICAL: Database must be initialized for routes to work
        db_dir = Path.home() / ".ai_pdf_scholar"
        db_dir.mkdir(exist_ok=True)
        db_path = db_dir / "documents.db"

        # Quick database connection test with monitoring DISABLED for fast startup
        # The heavy monitoring features (leak detection, memory monitoring) were blocking startup
        db = DatabaseConnection(str(db_path), enable_monitoring=False)
        db.close_all_connections()

        logger.info("API ready to accept connections")

        # Schedule non-essential initializations for after startup
        asyncio.create_task(_deferred_initialization(db_path))

    except Exception as e:
        logger.error(f"Critical startup failed: {e}")
        raise

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down AI Enhanced PDF Scholar API...")

    # Shutdown cache system
    try:
        logger.info("Cache system shutdown completed")
    except Exception as cache_error:
        logger.warning(f"Cache system shutdown error: {cache_error}")

    logger.info("API shutdown completed")


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Enhanced PDF Scholar API",
    description="Modern API for intelligent PDF document management and analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
# Configure comprehensive error handling
setup_comprehensive_error_handling(app, include_debug_info=False)

# Configure security headers middleware (must be before other middleware)
# Note: security_headers_config is already initialized above for lifespan
setup_security_headers(app, security_headers_config)

# Configure rate limiting middleware
# Note: rate_limit_config is already initialized above for lifespan
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Configure secure CORS based on environment
# Note: cors_config is already initialized above for lifespan
app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

# Add metrics collection middleware
from backend.services.metrics_service import FastAPIMetricsMiddleware

# Note: add_middleware passes the app automatically as the first argument
# We only need to pass additional arguments as keyword arguments
app.add_middleware(
    FastAPIMetricsMiddleware, metrics_service=metrics_collector.metrics_service
)

# WebSocket manager
websocket_manager: WebSocketManager = WebSocketManager()
# Include API routes (only available v2 routes)
from backend.api.routes import api_router

# TODO: Re-implement missing routes (auth, library, multi_document, system, rate_limit_admin, cache_admin)
# Single source of truth for public APIs lives under /api
app.include_router(api_router, prefix="/api")

# ============================================================================
# Monitoring Endpoints
# ============================================================================


@app.get("/metrics")
async def get_metrics() -> Response:
    """Prometheus metrics endpoint."""
    try:
        metrics_data, content_type = metrics_collector.get_metrics_response()
        return Response(content=metrics_data, media_type=content_type)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics") from e


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint for basic connectivity test."""
    return {
        "message": "AI Enhanced PDF Scholar API is running",
        "version": "2.0.0",
        "docs": "/api/docs",
    }


@app.get("/ping")
async def ping() -> dict[str, bool]:
    """Simple ping endpoint for connectivity test."""
    return {"pong": True}


@app.get("/health")
@app.get(
    "/api/system/health"
)  # Alias for frontend compatibility (Vite proxy expects /api prefix)
async def basic_health_check() -> dict[str, Any]:
    """Basic health check endpoint - no dependencies."""
    return {
        "status": "healthy",
        "service": "AI Enhanced PDF Scholar API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Comprehensive health check endpoint."""
    try:
        health_status = await metrics_collector.check_comprehensive_health()
        return cast(dict[str, Any], health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/metrics/dashboard")
async def get_dashboard_metrics() -> dict[str, Any]:
    """Get formatted metrics for custom dashboard."""
    try:
        dashboard_data = metrics_collector.get_dashboard_metrics()
        return cast(dict[str, Any], dashboard_data)
    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get dashboard metrics"
        ) from e


# Serve static files for frontend
frontend_dist = project_root / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")


# WebSocket endpoint for real-time communication
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


app.add_api_websocket_route("/ws/{client_id}", websocket_endpoint)


async def handle_rag_query_websocket(
    query: str, document_id: int, client_id: str
) -> None:
    """Handle RAG query via WebSocket."""
    try:
        # TODO: Reimplement with v2 architecture - WebSocket RAG queries currently disabled
        # For now, redirect users to REST API
        logger.info(
            f"WebSocket RAG query received but disabled - document_id: {document_id}"
        )
        # Inform client to use REST API instead
        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "rag_info",
                    "message": f"WebSocket RAG queries are temporarily disabled. Please use REST API: POST /api/documents/{document_id}/query",
                }
            ),
            client_id,
        )
    except Exception as e:
        logger.error(f"WebSocket RAG query failed: {e}")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "rag_error", "error": str(e)}), client_id
        )


# Note: Startup and shutdown events are now handled in the lifespan context manager above


if __name__ == "__main__":
    # Fix 1: Correct module path for ASGI
    # Fix 2: Exclude .trunk directory to prevent watchfiles filesystem loop error
    server_host = os.getenv("API_SERVER_HOST", "127.0.0.1")
    server_port = int(os.getenv("API_SERVER_PORT", "8000"))
    uvicorn.run(
        "backend.api.main:app",
        host=server_host,
        port=server_port,
        reload=True,
        reload_excludes=[".trunk/**", "node_modules/**", ".git/**"],
        log_level="info",
    )
