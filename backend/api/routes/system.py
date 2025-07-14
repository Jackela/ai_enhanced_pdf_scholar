"""
System API Routes

RESTful API endpoints for system status, configuration, and health checks.
"""

import logging
import time
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.models import *
from backend.api.dependencies import get_db, get_enhanced_rag, get_api_config
from src.database.connection import DatabaseConnection
from src.services.enhanced_rag_service import EnhancedRAGService
from config import Config

logger = logging.getLogger(__name__)

router = APIRouter()

# Store startup time for uptime calculation
startup_time = time.time()


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: DatabaseConnection = Depends(get_db),
    rag_service: EnhancedRAGService = Depends(get_enhanced_rag)
):
    """Get system health status."""
    try:
        # Check database connection
        database_connected = True
        try:
            # Simple database query to test connection
            db.fetch_one("SELECT 1 as test")
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            database_connected = False
        
        # Check RAG service availability
        rag_service_available = rag_service is not None
        
        # Check API key configuration
        api_key_configured = Config.get_gemini_api_key() is not None
        
        # Calculate uptime
        uptime_seconds = time.time() - startup_time
        
        # Determine overall health status
        if database_connected and rag_service_available:
            status_value = "healthy"
        elif database_connected:
            status_value = "degraded"
        else:
            status_value = "unhealthy"
        
        # Check storage health
        storage_health = "unknown"
        try:
            storage_dir = Path.home() / ".ai_pdf_scholar"
            if storage_dir.exists():
                # Basic storage check
                total_space = sum(f.stat().st_size for f in storage_dir.rglob('*') if f.is_file())
                if total_space < 10 * 1024 * 1024 * 1024:  # Less than 10GB
                    storage_health = "healthy"
                else:
                    storage_health = "warning"
            else:
                storage_health = "not_initialized"
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
            storage_health = "error"
        
        return SystemHealthResponse(
            status=status_value,
            database_connected=database_connected,
            rag_service_available=rag_service_available,
            api_key_configured=api_key_configured,
            storage_health=storage_health,
            uptime_seconds=uptime_seconds
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/config", response_model=ConfigurationResponse)
async def get_configuration(
    config: dict = Depends(get_api_config)
):
    """Get system configuration."""
    try:
        # Feature availability
        features = {
            "document_upload": True,
            "rag_queries": Config.get_gemini_api_key() is not None,
            "vector_indexing": Config.get_gemini_api_key() is not None,
            "cache_system": True,
            "websocket_support": True,
            "duplicate_detection": True,
            "library_management": True
        }
        
        # System limits
        limits = {
            "max_file_size_mb": config["max_file_size_mb"],
            "max_query_length": config["max_query_length"],
            "allowed_file_types": config["allowed_file_types"],
            "max_documents": 10000,  # Configurable limit
            "max_concurrent_queries": 10
        }
        
        return ConfigurationResponse(
            features=features,
            limits=limits,
            version=config["version"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration retrieval failed: {str(e)}"
        )


@router.get("/info", response_model=BaseResponse)
async def get_system_info():
    """Get system information."""
    try:
        info = {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "working_directory": str(Path.cwd()),
            "data_directory": str(Path.home() / ".ai_pdf_scholar"),
            "uptime_seconds": time.time() - startup_time
        }
        
        return BaseResponse(
            message="System information retrieved",
            data=info
        )
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System info retrieval failed: {str(e)}"
        )


@router.get("/version")
async def get_version():
    """Get API version."""
    return {"version": "2.0.0", "name": "AI Enhanced PDF Scholar API"}


@router.post("/initialize", response_model=BaseResponse)
async def initialize_system(
    db: DatabaseConnection = Depends(get_db)
):
    """Initialize system (run migrations, create directories, etc.)."""
    try:
        from src.database.migrations import DatabaseMigrator
        
        # Run database migrations
        migrator = DatabaseMigrator(db)
        if migrator.needs_migration():
            success = migrator.migrate()
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database migration failed"
                )
        
        # Create necessary directories
        base_dir = Path.home() / ".ai_pdf_scholar"
        directories = [
            base_dir / "uploads",
            base_dir / "vector_indexes",
            base_dir / "vector_indexes" / "active",
            base_dir / "vector_indexes" / "backup",
            base_dir / "vector_indexes" / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        return BaseResponse(
            message="System initialized successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(e)}"
        )


@router.get("/storage", response_model=BaseResponse)
async def get_storage_info():
    """Get storage usage information."""
    try:
        base_dir = Path.home() / ".ai_pdf_scholar"
        
        if not base_dir.exists():
            return BaseResponse(
                message="Storage not initialized",
                data={"initialized": False}
            )
        
        # Calculate storage usage
        total_size = 0
        file_count = 0
        
        for file_path in base_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        # Directory breakdown
        directories = {}
        for subdir in ["uploads", "vector_indexes", "backups"]:
            subdir_path = base_dir / subdir
            if subdir_path.exists():
                subdir_size = sum(
                    f.stat().st_size for f in subdir_path.rglob('*') if f.is_file()
                )
                directories[subdir] = {
                    "size_bytes": subdir_size,
                    "size_mb": round(subdir_size / (1024 * 1024), 2)
                }
        
        storage_info = {
            "initialized": True,
            "base_directory": str(base_dir),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_files": file_count,
            "directories": directories
        }
        
        return BaseResponse(
            message="Storage information retrieved",
            data=storage_info
        )
        
    except Exception as e:
        logger.error(f"Failed to get storage info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage info retrieval failed: {str(e)}"
        )


@router.post("/maintenance", response_model=BaseResponse)
async def run_maintenance():
    """Run system maintenance tasks."""
    try:
        maintenance_tasks = []
        
        # Clean up temporary files
        temp_dir = Path.home() / ".ai_pdf_scholar" / "uploads"
        if temp_dir.exists():
            import time
            cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago
            
            cleaned_files = 0
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
                    cleaned_files += 1
            
            if cleaned_files > 0:
                maintenance_tasks.append(f"Cleaned {cleaned_files} temporary files")
        
        # TODO: Add more maintenance tasks
        # - Log rotation
        # - Cache optimization
        # - Database optimization
        
        if maintenance_tasks:
            message = f"Maintenance completed: {', '.join(maintenance_tasks)}"
        else:
            message = "No maintenance tasks needed"
        
        return BaseResponse(message=message)
        
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Maintenance failed: {str(e)}"
        )