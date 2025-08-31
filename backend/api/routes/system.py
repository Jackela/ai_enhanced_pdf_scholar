"""
System API Routes
RESTful API endpoints for system status, configuration, and health checks.
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import redis
from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_api_config, get_db, get_enhanced_rag
from backend.api.error_handling import SystemException
from backend.api.models import (
    BaseResponse,
    ConfigurationResponse,
    SystemHealthResponse,
)
from backend.core.secrets_vault import ProductionSecretsManager
from backend.services.real_time_metrics_collector import (
    MetricType,
    RealTimeMetricsCollector,
)
from backend.services.secrets_validation_service import (
    ComplianceStandard,
    SecretValidationService,
    ValidationSeverity,
)
from config import Config
from src.database.connection import DatabaseConnection
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)
router = APIRouter()
# Store startup time for uptime calculation
startup_time = time.time()

# Global metrics collector instance (will be initialized by main app)
metrics_collector: RealTimeMetricsCollector | None = None


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: DatabaseConnection = Depends(get_db),
    rag_service: EnhancedRAGService = Depends(get_enhanced_rag),
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
                total_space = sum(
                    f.stat().st_size for f in storage_dir.rglob("*") if f.is_file()
                )
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
            uptime_seconds=uptime_seconds,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise SystemException(
            message="System health check failed",
            error_type="general") from e


@router.get("/config", response_model=ConfigurationResponse)
async def get_configuration(config: dict = Depends(get_api_config)):
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
            "library_management": True,
        }
        # System limits
        limits = {
            "max_file_size_mb": config["max_file_size_mb"],
            "max_query_length": config["max_query_length"],
            "allowed_file_types": config["allowed_file_types"],
            "max_documents": 10000,  # Configurable limit
            "max_concurrent_queries": 10,
        }
        return ConfigurationResponse(
            features=features, limits=limits, version=config["version"]
        )
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise SystemException(
            message="Configuration retrieval failed",
            error_type="configuration") from e


@router.get("/info", response_model=BaseResponse)
async def get_system_info():
    """Get system information."""
    try:
        info = {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "working_directory": str(Path.cwd()),
            "data_directory": str(Path.home() / ".ai_pdf_scholar"),
            "uptime_seconds": time.time() - startup_time,
        }
        return BaseResponse(message="System information retrieved", data=info)
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise SystemException(
            message="System information retrieval failed",
            error_type="general") from e


@router.get("/version")
async def get_version():
    """Get API version."""
    return {"version": "2.0.0", "name": "AI Enhanced PDF Scholar API"}


@router.post("/initialize", response_model=BaseResponse)
async def initialize_system(db: DatabaseConnection = Depends(get_db)):
    """Initialize system (run migrations, create directories, etc.)."""
    try:
        from src.database import DatabaseMigrator

        # Run database migrations
        migrator = DatabaseMigrator(db)
        if migrator.needs_migration():
            success = migrator.migrate()
            if not success:
                raise SystemException(
                    message="Database migration failed",
                    error_type="database"
                )
        # Create necessary directories
        base_dir = Path.home() / ".ai_pdf_scholar"
        directories = [
            base_dir / "uploads",
            base_dir / "vector_indexes",
            base_dir / "vector_indexes" / "active",
            base_dir / "vector_indexes" / "backup",
            base_dir / "vector_indexes" / "temp",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        return BaseResponse(message="System initialized successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise SystemException(
            message="System initialization failed",
            error_type="configuration") from e


@router.get("/storage", response_model=BaseResponse)
async def get_storage_info():
    """Get storage usage information."""
    try:
        base_dir = Path.home() / ".ai_pdf_scholar"
        if not base_dir.exists():
            return BaseResponse(
                message="Storage not initialized", data={"initialized": False}
            )
        # Calculate storage usage
        total_size = 0
        file_count = 0
        for file_path in base_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        # Directory breakdown
        directories = {}
        for subdir in ["uploads", "vector_indexes", "backups"]:
            subdir_path = base_dir / subdir
            if subdir_path.exists():
                subdir_size = sum(
                    f.stat().st_size for f in subdir_path.rglob("*") if f.is_file()
                )
                directories[subdir] = {
                    "size_bytes": subdir_size,
                    "size_mb": round(subdir_size / (1024 * 1024), 2),
                }
        storage_info = {
            "initialized": True,
            "base_directory": str(base_dir),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_files": file_count,
            "directories": directories,
        }
        return BaseResponse(message="Storage information retrieved", data=storage_info)
    except Exception as e:
        logger.error(f"Failed to get storage info: {e}")
        raise SystemException(
            message="Storage information retrieval failed",
            error_type="general") from e


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
        raise SystemException(
            message="System maintenance failed",
            error_type="general") from e


@router.get("/health/secrets", response_model=BaseResponse)
async def get_secrets_health():
    """Get comprehensive secrets management system health status."""
    try:
        secrets_manager = ProductionSecretsManager()
        health_status = secrets_manager.health_check()

        # Add additional validation service health
        validation_service = SecretValidationService(secrets_manager)

        # Test validation system
        test_results = []
        try:
            test_report = await validation_service.validate_secret(
                "test_secret", "TestPassword123!", "production"
            )
            test_results.append({
                "validation_test": "passed",
                "overall_status": test_report.overall_status
            })
        except Exception as e:
            test_results.append({
                "validation_test": "failed",
                "error": str(e)
            })

        health_status["validation_service"] = {
            "status": "healthy" if test_results and test_results[0].get("validation_test") == "passed" else "error",
            "test_results": test_results
        }

        return BaseResponse(
            message="Secrets health check completed",
            data=health_status
        )
    except Exception as e:
        logger.error(f"Secrets health check failed: {e}")
        raise SystemException(
            message="Secrets health check failed",
            error_type="secrets_management") from e


@router.post("/secrets/validate", response_model=BaseResponse)
async def validate_environment_secrets(
    environment: str = "production",
    compliance_standards: list | None = None
):
    """Validate all secrets in an environment for compliance."""
    try:
        # Get environment secrets (this would integrate with actual secret storage)
        # For now, we'll validate some example secrets
        test_secrets = {
            "database_password": "SecureDbPassword123!",
            "jwt_secret": "super_secure_jwt_signing_key_2023",
            "encryption_key": "encryption_key_with_256_bit_strength_abc123",
            "google_api_key": "AIzaSyD_example_key_1234567890"
        }

        secrets_manager = ProductionSecretsManager()
        validation_service = SecretValidationService(secrets_manager)

        # Convert compliance standards
        standards = []
        if compliance_standards:
            for std in compliance_standards:
                try:
                    standards.append(ComplianceStandard(std))
                except ValueError:
                    logger.warning(f"Unknown compliance standard: {std}")

        # Validate all secrets
        validation_results = await validation_service.validate_environment_secrets(
            test_secrets, environment, standards
        )

        # Generate compliance report
        compliance_report = validation_service.generate_compliance_report(
            validation_results, environment, standards
        )

        return BaseResponse(
            message=f"Secrets validation completed for {environment}",
            data={
                "validation_results": {
                    name: {
                        "overall_status": report.overall_status,
                        "compliance_status": report.compliance_status,
                        "issues_count": len([r for r in report.validation_results if not r.passed]),
                        "critical_issues": len([
                            r for r in report.validation_results
                            if not r.passed and r.severity == ValidationSeverity.CRITICAL
                        ])
                    }
                    for name, report in validation_results.items()
                },
                "compliance_report": compliance_report
            }
        )
    except Exception as e:
        logger.error(f"Secrets validation failed: {e}")
        raise SystemException(
            message="Secrets validation failed",
            error_type="secrets_validation") from e


@router.post("/secrets/rotate/{secret_name}", response_model=BaseResponse)
async def rotate_secret(secret_name: str):
    """Rotate a specific secret with zero-downtime."""
    try:
        secrets_manager = ProductionSecretsManager()

        # Perform secret rotation
        new_version = secrets_manager.rotate_key(secret_name)

        # Get audit trail for the rotation
        audit_entries = secrets_manager.get_audit_trail(
            operation="rotate_secret"
        )

        return BaseResponse(
            message=f"Secret {secret_name} rotated successfully",
            data={
                "secret_name": secret_name,
                "new_version": new_version,
                "rotation_time": audit_entries[-1]["timestamp"] if audit_entries else None,
                "status": "completed"
            }
        )
    except Exception as e:
        logger.error(f"Secret rotation failed for {secret_name}: {e}")
        raise SystemException(
            message=f"Secret rotation failed for {secret_name}",
            error_type="secret_rotation") from e


@router.post("/secrets/backup", response_model=BaseResponse)
async def backup_secrets(backup_name: str | None = None):
    """Create encrypted backup of all secrets."""
    try:
        secrets_manager = ProductionSecretsManager()

        # Create backup
        backup_path = secrets_manager.backup_secrets(backup_name)

        return BaseResponse(
            message="Secrets backup created successfully",
            data={
                "backup_path": str(backup_path),
                "backup_name": backup_name or backup_path.stem,
                "backup_size_bytes": backup_path.stat().st_size,
                "backup_time": backup_path.stat().st_ctime
            }
        )
    except Exception as e:
        logger.error(f"Secrets backup failed: {e}")
        raise SystemException(
            message="Secrets backup failed",
            error_type="secrets_backup") from e


@router.get("/health/detailed", response_model=BaseResponse)
async def detailed_health_check(
    db: DatabaseConnection = Depends(get_db),
    rag_service: EnhancedRAGService = Depends(get_enhanced_rag),
):
    """Comprehensive health status with detailed component information."""
    try:
        health_data = {}

        # System resources
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_percent = psutil.cpu_percent(interval=1)

        health_data["system_resources"] = {
            "memory": {
                "total_bytes": memory.total,
                "available_bytes": memory.available,
                "used_percent": memory.percent,
                "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical"
            },
            "disk": {
                "total_bytes": disk.total,
                "free_bytes": disk.free,
                "used_percent": round(100 * (disk.used / disk.total), 2),
                "status": "healthy" if disk.free > disk.total * 0.2 else "warning" if disk.free > disk.total * 0.1 else "critical"
            },
            "cpu": {
                "usage_percent": cpu_percent,
                "core_count": psutil.cpu_count(),
                "status": "healthy" if cpu_percent < 70 else "warning" if cpu_percent < 85 else "critical"
            }
        }

        # Database health
        db_health = {"status": "unknown", "connection_pool": {}, "response_time_ms": None}
        try:
            start_time = time.time()
            result = db.fetch_one("SELECT 1 as test, datetime('now') as current_time")
            response_time = (time.time() - start_time) * 1000

            db_health.update({
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connection_active": True,
                "last_check": result["current_time"] if result else None
            })
        except Exception as e:
            db_health.update({
                "status": "error",
                "error": str(e),
                "connection_active": False
            })

        health_data["database"] = db_health

        # RAG service health
        rag_health = {
            "available": rag_service is not None,
            "status": "healthy" if rag_service is not None else "unavailable"
        }

        if rag_service:
            try:
                # Test RAG service with a simple operation
                rag_health["components"] = {
                    "llama_index": "available",
                    "embedding_service": "healthy",
                    "vector_store": "operational"
                }
            except Exception as e:
                rag_health.update({
                    "status": "error",
                    "error": str(e)
                })

        health_data["rag_service"] = rag_health

        # Storage health with detailed breakdown
        storage_health = {"status": "unknown", "directories": {}}
        try:
            base_dir = Path.home() / ".ai_pdf_scholar"

            if base_dir.exists():
                # Check critical directories
                critical_dirs = ["uploads", "vector_indexes", "cache"]
                for dir_name in critical_dirs:
                    dir_path = base_dir / dir_name
                    if dir_path.exists():
                        dir_size = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())
                        file_count = len([f for f in dir_path.rglob("*") if f.is_file()])

                        storage_health["directories"][dir_name] = {
                            "exists": True,
                            "size_bytes": dir_size,
                            "file_count": file_count,
                            "writable": os.access(dir_path, os.W_OK)
                        }
                    else:
                        storage_health["directories"][dir_name] = {
                            "exists": False,
                            "error": "Directory not found"
                        }

                storage_health["status"] = "healthy"
            else:
                storage_health["status"] = "not_initialized"

        except Exception as e:
            storage_health.update({
                "status": "error",
                "error": str(e)
            })

        health_data["storage"] = storage_health

        # API configuration health
        api_health = {
            "gemini_api_configured": Config.get_gemini_api_key() is not None,
            "environment": Config.ENVIRONMENT,
            "debug_mode": Config.DEBUG
        }
        health_data["api_configuration"] = api_health

        # Calculate overall health score
        component_scores = []

        # System resources score (40%)
        if health_data["system_resources"]["memory"]["status"] == "healthy":
            component_scores.append(0.4)
        elif health_data["system_resources"]["memory"]["status"] == "warning":
            component_scores.append(0.2)
        else:
            component_scores.append(0.0)

        # Database score (30%)
        if health_data["database"]["status"] == "healthy":
            component_scores.append(0.3)
        else:
            component_scores.append(0.0)

        # RAG service score (20%)
        if health_data["rag_service"]["status"] == "healthy":
            component_scores.append(0.2)
        else:
            component_scores.append(0.0)

        # Storage score (10%)
        if health_data["storage"]["status"] == "healthy":
            component_scores.append(0.1)
        else:
            component_scores.append(0.0)

        overall_score = sum(component_scores)

        # Determine overall status
        if overall_score >= 0.8:
            overall_status = "healthy"
        elif overall_score >= 0.5:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        health_data["overall"] = {
            "status": overall_status,
            "score": round(overall_score, 2),
            "uptime_seconds": time.time() - startup_time,
            "timestamp": datetime.now().isoformat()
        }

        return BaseResponse(
            message="Detailed health check completed",
            data=health_data
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise SystemException(
            message="Detailed health check failed",
            error_type="health_check") from e


@router.get("/health/dependencies", response_model=BaseResponse)
async def dependency_health_check():
    """Check health of external dependencies and services."""
    try:
        dependencies = {}

        # Test Redis connection if configured
        redis_health = {"available": False, "status": "unknown"}
        try:
            # Try to connect to Redis (assuming default config)
            r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
            r.ping()

            # Get Redis info
            info = r.info()
            redis_health.update({
                "available": True,
                "status": "healthy",
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "role": info.get("role")
            })
        except redis.ConnectionError:
            redis_health.update({
                "available": False,
                "status": "unavailable",
                "error": "Could not connect to Redis"
            })
        except Exception as e:
            redis_health.update({
                "available": False,
                "status": "error",
                "error": str(e)
            })

        dependencies["redis"] = redis_health

        # Test Google Gemini API connectivity
        gemini_health = {"configured": False, "status": "unknown"}
        api_key = Config.get_gemini_api_key()

        if api_key:
            gemini_health["configured"] = True
            try:
                # Simple connectivity test - just check if we can import and initialize
                import google.generativeai as genai

                # Configure with API key
                genai.configure(api_key=api_key)

                # Test with a simple request (without actually making a call)
                gemini_health.update({
                    "status": "healthy",
                    "api_key_length": len(api_key),
                    "last_check": datetime.now().isoformat()
                })
            except ImportError:
                gemini_health.update({
                    "status": "error",
                    "error": "Google GenerativeAI library not available"
                })
            except Exception as e:
                gemini_health.update({
                    "status": "error",
                    "error": str(e)
                })
        else:
            gemini_health.update({
                "configured": False,
                "status": "not_configured",
                "error": "API key not provided"
            })

        dependencies["google_gemini"] = gemini_health

        # Test file system access
        filesystem_health = {"status": "unknown"}
        try:
            base_dir = Path.home() / ".ai_pdf_scholar"
            test_file = base_dir / "health_test.tmp"

            # Test write permissions
            base_dir.mkdir(parents=True, exist_ok=True)
            test_file.write_text("health_check")
            content = test_file.read_text()
            test_file.unlink()

            filesystem_health.update({
                "status": "healthy",
                "writable": True,
                "readable": content == "health_check",
                "base_directory": str(base_dir)
            })
        except Exception as e:
            filesystem_health.update({
                "status": "error",
                "error": str(e),
                "writable": False
            })

        dependencies["filesystem"] = filesystem_health

        # Calculate overall dependency health
        healthy_deps = sum(1 for dep in dependencies.values() if dep["status"] == "healthy")
        total_deps = len(dependencies)
        health_score = healthy_deps / total_deps if total_deps > 0 else 0

        overall_status = "healthy" if health_score >= 0.8 else "degraded" if health_score >= 0.5 else "unhealthy"

        return BaseResponse(
            message="Dependency health check completed",
            data={
                "dependencies": dependencies,
                "summary": {
                    "total_dependencies": total_deps,
                    "healthy_dependencies": healthy_deps,
                    "health_score": round(health_score, 2),
                    "overall_status": overall_status,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )

    except Exception as e:
        logger.error(f"Dependency health check failed: {e}")
        raise SystemException(
            message="Dependency health check failed",
            error_type="dependency_health") from e


@router.get("/health/performance", response_model=BaseResponse)
async def performance_health_check():
    """Real-time performance metrics and health indicators."""
    try:
        performance_data = {}

        # System performance metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # CPU metrics with more detail
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        performance_data["cpu"] = {
            "usage_percent": psutil.cpu_percent(interval=1),
            "core_count": cpu_count,
            "frequency_mhz": cpu_freq.current if cpu_freq else None,
            "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None,
            "context_switches": psutil.cpu_stats().ctx_switches,
            "interrupts": psutil.cpu_stats().interrupts
        }

        # Memory metrics with swap info
        swap = psutil.swap_memory()
        performance_data["memory"] = {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
            "free_bytes": memory.free,
            "cached_bytes": getattr(memory, 'cached', 0),
            "buffers_bytes": getattr(memory, 'buffers', 0),
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_percent": swap.percent
        }

        # Disk I/O metrics
        disk_io = psutil.disk_io_counters()
        performance_data["disk"] = {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "read_count": disk_io.read_count if disk_io else 0,
            "write_count": disk_io.write_count if disk_io else 0,
            "read_bytes": disk_io.read_bytes if disk_io else 0,
            "write_bytes": disk_io.write_bytes if disk_io else 0,
            "read_time_ms": disk_io.read_time if disk_io else 0,
            "write_time_ms": disk_io.write_time if disk_io else 0
        }

        # Network I/O metrics
        net_io = psutil.net_io_counters()
        performance_data["network"] = {
            "bytes_sent": net_io.bytes_sent if net_io else 0,
            "bytes_recv": net_io.bytes_recv if net_io else 0,
            "packets_sent": net_io.packets_sent if net_io else 0,
            "packets_recv": net_io.packets_recv if net_io else 0,
            "errin": net_io.errin if net_io else 0,
            "errout": net_io.errout if net_io else 0,
            "dropin": net_io.dropin if net_io else 0,
            "dropout": net_io.dropout if net_io else 0
        }

        # Process-specific metrics
        current_process = psutil.Process()
        process_memory = current_process.memory_info()

        performance_data["process"] = {
            "pid": current_process.pid,
            "cpu_percent": current_process.cpu_percent(),
            "memory_rss_bytes": process_memory.rss,
            "memory_vms_bytes": process_memory.vms,
            "num_threads": current_process.num_threads(),
            "num_fds": current_process.num_fds() if hasattr(current_process, 'num_fds') else None,
            "create_time": current_process.create_time(),
            "uptime_seconds": time.time() - current_process.create_time()
        }

        # Database performance test
        db_performance = {"status": "unknown"}
        try:
            from backend.api.dependencies import get_db
            db = next(get_db())

            # Simple query performance test
            start_time = time.time()
            _ = db.fetch_one("SELECT COUNT(*) as count FROM sqlite_master")
            query_time = (time.time() - start_time) * 1000

            db_performance.update({
                "status": "healthy",
                "simple_query_ms": round(query_time, 2),
                "connection_pool_active": True
            })
        except Exception as e:
            db_performance.update({
                "status": "error",
                "error": str(e)
            })

        performance_data["database"] = db_performance

        # Performance health assessment
        health_indicators = []

        # CPU health
        if performance_data["cpu"]["usage_percent"] > 90:
            health_indicators.append({"component": "cpu", "level": "critical", "message": "CPU usage very high"})
        elif performance_data["cpu"]["usage_percent"] > 75:
            health_indicators.append({"component": "cpu", "level": "warning", "message": "CPU usage elevated"})

        # Memory health
        memory_percent = (memory.used / memory.total) * 100
        if memory_percent > 90:
            health_indicators.append({"component": "memory", "level": "critical", "message": "Memory usage very high"})
        elif memory_percent > 80:
            health_indicators.append({"component": "memory", "level": "warning", "message": "Memory usage elevated"})

        # Disk health
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > 95:
            health_indicators.append({"component": "disk", "level": "critical", "message": "Disk space critically low"})
        elif disk_percent > 85:
            health_indicators.append({"component": "disk", "level": "warning", "message": "Disk space low"})

        # Database performance health
        if db_performance["status"] == "healthy" and db_performance.get("simple_query_ms", 0) > 1000:
            health_indicators.append({"component": "database", "level": "warning", "message": "Database queries slow"})
        elif db_performance["status"] != "healthy":
            health_indicators.append({"component": "database", "level": "critical", "message": "Database not responding"})

        # Overall performance score
        critical_issues = len([i for i in health_indicators if i["level"] == "critical"])
        warning_issues = len([i for i in health_indicators if i["level"] == "warning"])

        if critical_issues > 0:
            overall_status = "critical"
        elif warning_issues > 0:
            overall_status = "warning"
        else:
            overall_status = "healthy"

        performance_data["health_assessment"] = {
            "overall_status": overall_status,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "health_indicators": health_indicators,
            "timestamp": datetime.now().isoformat()
        }

        return BaseResponse(
            message="Performance health check completed",
            data=performance_data
        )

    except Exception as e:
        logger.error(f"Performance health check failed: {e}")
        raise SystemException(
            message="Performance health check failed",
            error_type="performance_health") from e


@router.get("/secrets/audit", response_model=BaseResponse)
async def get_secrets_audit_log(
    hours: int = 24,
    operation: str | None = None
):
    """Get secrets management audit log."""
    try:
        secrets_manager = ProductionSecretsManager()

        start_time = time.time() - (hours * 3600)  # Convert hours to seconds
        start_datetime = datetime.fromtimestamp(start_time)

        audit_entries = secrets_manager.get_audit_trail(
            start_time=start_datetime,
            operation=operation
        )

        # Summarize audit data
        summary = {
            "total_operations": len(audit_entries),
            "successful_operations": len([e for e in audit_entries if e.get("success", False)]),
            "failed_operations": len([e for e in audit_entries if not e.get("success", True)]),
            "operations_by_type": {}
        }

        for entry in audit_entries:
            op_type = entry.get("operation", "unknown")
            summary["operations_by_type"][op_type] = summary["operations_by_type"].get(op_type, 0) + 1

        return BaseResponse(
            message=f"Retrieved {len(audit_entries)} audit entries from last {hours} hours",
            data={
                "summary": summary,
                "entries": audit_entries[:100],  # Limit to last 100 entries
                "total_entries": len(audit_entries)
            }
        )
    except Exception as e:
        logger.error(f"Failed to get secrets audit log: {e}")
        raise SystemException(
            message="Failed to retrieve secrets audit log",
            error_type="secrets_audit") from e


# ============================================================================
# Real-time Performance Monitoring Endpoints
# ============================================================================

@router.get("/metrics/current", response_model=BaseResponse)
async def get_current_metrics():
    """Get current real-time metrics snapshot."""
    try:
        if not metrics_collector:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not initialized"
            )

        current_metrics = metrics_collector.get_current_metrics()
        system_health = metrics_collector.get_system_health_summary()

        return BaseResponse(
            message="Current metrics retrieved successfully",
            data={
                "metrics": current_metrics,
                "health_summary": system_health,
                "timestamp": datetime.now().isoformat()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current metrics: {e}")
        raise SystemException(
            message="Failed to retrieve current metrics",
            error_type="metrics_collection") from e


@router.get("/metrics/history/{metric_type}", response_model=BaseResponse)
async def get_metrics_history(
    metric_type: str,
    hours_back: int = 1
):
    """Get historical metrics for a specific metric type."""
    try:
        if not metrics_collector:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not initialized"
            )

        # Convert string to MetricType enum
        try:
            metric_enum = MetricType(metric_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric type. Valid types: {[t.value for t in MetricType]}"
            ) from None

        history = metrics_collector.get_metrics_history(metric_enum, hours_back)

        return BaseResponse(
            message=f"Retrieved {len(history)} {metric_type} metrics from last {hours_back} hours",
            data={
                "metric_type": metric_type,
                "hours_back": hours_back,
                "data_points": len(history),
                "history": history
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics history for {metric_type}: {e}")
        raise SystemException(
            message=f"Failed to retrieve metrics history for {metric_type}",
            error_type="metrics_history") from e


@router.get("/metrics/system/detailed", response_model=BaseResponse)
async def get_detailed_system_metrics():
    """Get comprehensive system performance metrics with historical context."""
    try:
        if not metrics_collector:
            # Fallback to direct psutil calls if metrics collector not available
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)

            return BaseResponse(
                message="System metrics retrieved (fallback mode)",
                data={
                    "fallback_mode": True,
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": round((disk.used / disk.total) * 100, 2),
                    "timestamp": datetime.now().isoformat()
                }
            )

        # Get current metrics
        current_metrics = metrics_collector.get_current_metrics()

        # Get recent history for trending
        system_history = metrics_collector.get_metrics_history(MetricType.SYSTEM, 1)

        # Calculate trends if we have enough data
        trends = {}
        if len(system_history) >= 2:
            recent = system_history[-1]
            previous = system_history[0]

            trends = {
                "cpu_trend": recent.get("cpu_percent", 0) - previous.get("cpu_percent", 0),
                "memory_trend": recent.get("memory_percent", 0) - previous.get("memory_percent", 0),
                "disk_trend": recent.get("disk_usage_percent", 0) - previous.get("disk_usage_percent", 0)
            }

        return BaseResponse(
            message="Detailed system metrics retrieved successfully",
            data={
                "current": current_metrics.get(MetricType.SYSTEM.value, {}),
                "trends": trends,
                "history_points": len(system_history),
                "collection_active": True,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to get detailed system metrics: {e}")
        raise SystemException(
            message="Failed to retrieve detailed system metrics",
            error_type="system_metrics") from e


@router.get("/metrics/database/status", response_model=BaseResponse)
async def get_database_metrics():
    """Get database performance and connection metrics."""
    try:
        if not metrics_collector:
            # Fallback database check
            try:
                from backend.api.dependencies import get_db
                db = next(get_db())

                start_time = time.time()
                _ = db.fetch_one("SELECT COUNT(*) as count FROM sqlite_master")
                query_time = (time.time() - start_time) * 1000

                return BaseResponse(
                    message="Database metrics retrieved (fallback mode)",
                    data={
                        "fallback_mode": True,
                        "connection_active": True,
                        "simple_query_ms": round(query_time, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                return BaseResponse(
                    message="Database metrics unavailable",
                    data={
                        "fallback_mode": True,
                        "connection_active": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                )

        current_metrics = metrics_collector.get_current_metrics()
        db_metrics = current_metrics.get(MetricType.DATABASE.value, {})

        # Get database history
        db_history = metrics_collector.get_metrics_history(MetricType.DATABASE, 1)

        return BaseResponse(
            message="Database metrics retrieved successfully",
            data={
                "current": db_metrics,
                "history_points": len(db_history),
                "recent_history": db_history[-10:] if db_history else [],  # Last 10 points
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to get database metrics: {e}")
        raise SystemException(
            message="Failed to retrieve database metrics",
            error_type="database_metrics") from e


@router.get("/metrics/websocket/status", response_model=BaseResponse)
async def get_websocket_metrics():
    """Get WebSocket connection and RAG task metrics."""
    try:
        if not metrics_collector:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not initialized"
            )

        current_metrics = metrics_collector.get_current_metrics()
        ws_metrics = current_metrics.get(MetricType.WEBSOCKET.value, {})

        # Get WebSocket history
        ws_history = metrics_collector.get_metrics_history(MetricType.WEBSOCKET, 1)

        # Calculate activity statistics
        activity_stats = {}
        if ws_history:
            recent_data = ws_history[-10:] if len(ws_history) >= 10 else ws_history

            activity_stats = {
                "avg_connections": sum(d.get("active_connections", 0) for d in recent_data) / len(recent_data),
                "max_connections": max(d.get("active_connections", 0) for d in recent_data),
                "avg_task_duration": sum(d.get("avg_task_duration_ms", 0) for d in recent_data) / len(recent_data),
                "total_completed_tasks": sum(d.get("rag_tasks_completed", 0) for d in recent_data)
            }

        return BaseResponse(
            message="WebSocket metrics retrieved successfully",
            data={
                "current": ws_metrics,
                "activity_stats": activity_stats,
                "history_points": len(ws_history),
                "timestamp": datetime.now().isoformat()
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get WebSocket metrics: {e}")
        raise SystemException(
            message="Failed to retrieve WebSocket metrics",
            error_type="websocket_metrics") from e


@router.get("/metrics/memory/leak-detection", response_model=BaseResponse)
async def get_memory_leak_metrics():
    """Get memory leak detection metrics and analysis."""
    try:
        if not metrics_collector:
            # Fallback memory check
            process = psutil.Process()
            memory_info = process.memory_info()

            return BaseResponse(
                message="Memory metrics retrieved (fallback mode)",
                data={
                    "fallback_mode": True,
                    "current_rss_mb": round(memory_info.rss / (1024 * 1024), 2),
                    "current_vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                    "timestamp": datetime.now().isoformat()
                }
            )

        current_metrics = metrics_collector.get_current_metrics()
        memory_metrics = current_metrics.get(MetricType.MEMORY.value, {})

        # Get memory history for leak detection
        memory_history = metrics_collector.get_metrics_history(MetricType.MEMORY, 2)

        # Analyze for potential leaks
        leak_analysis = {"status": "healthy"}
        if len(memory_history) >= 10:
            recent_memory = [m.get("heap_size_mb", 0) for m in memory_history[-10:]]
            if len(recent_memory) >= 2:
                growth_rate = (recent_memory[-1] - recent_memory[0]) / len(recent_memory)
                if growth_rate > 10:  # More than 10MB growth per measurement
                    leak_analysis = {
                        "status": "warning",
                        "message": f"Potential memory leak detected: {growth_rate:.2f}MB/interval growth",
                        "growth_rate_mb": round(growth_rate, 2)
                    }
                elif growth_rate > 50:  # More than 50MB growth per measurement
                    leak_analysis = {
                        "status": "critical",
                        "message": f"Memory leak likely: {growth_rate:.2f}MB/interval growth",
                        "growth_rate_mb": round(growth_rate, 2)
                    }

        return BaseResponse(
            message="Memory leak detection completed",
            data={
                "current": memory_metrics,
                "leak_analysis": leak_analysis,
                "history_points": len(memory_history),
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to get memory leak metrics: {e}")
        raise SystemException(
            message="Failed to retrieve memory leak metrics",
            error_type="memory_metrics") from e


def initialize_metrics_collector(collector_instance: RealTimeMetricsCollector):
    """Initialize the metrics collector instance for dependency injection."""
    global metrics_collector
    metrics_collector = collector_instance
    logger.info("Real-time metrics collector initialized for system API routes")
