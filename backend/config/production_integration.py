"""
Production Environment Integration
Complete integration and orchestration of all production components including
Agent A1 (secrets), Agent A2 (monitoring), and Agent A3 (configuration).
"""

import asyncio
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .production import ProductionConfig
from .secrets_integration import ProductionSecretsIntegration
from .redis_cluster import RedisClusterManager
from ..database.production_config import ProductionDatabaseManager
from ..services.production_monitoring import ProductionMonitoringService
from ..services.metrics_service import MetricsService
from ..services.alert_service import AlertingService
from ..api.security.production_headers import ProductionSecurityHeaders
from ..api.security.ip_whitelist import ProductionIPWhitelist
from ..api.security.request_signing import ProductionRequestSigning

logger = logging.getLogger(__name__)


@dataclass
class ProductionServices:
    """Container for all production services."""
    production_config: ProductionConfig
    secrets_integration: ProductionSecretsIntegration
    database_manager: ProductionDatabaseManager
    redis_manager: RedisClusterManager
    metrics_service: MetricsService
    alerting_service: AlertingService
    monitoring_service: ProductionMonitoringService
    security_headers: ProductionSecurityHeaders
    ip_whitelist: ProductionIPWhitelist
    request_signing: ProductionRequestSigning


class ProductionEnvironmentManager:
    """
    Master production environment manager that orchestrates all
    production services and ensures proper initialization, monitoring,
    and graceful shutdown.
    """
    
    def __init__(self):
        """Initialize production environment manager."""
        self.services: Optional[ProductionServices] = None
        self.initialization_complete = False
        self.shutdown_initiated = False
        
        # Startup monitoring
        self.startup_start_time = time.time()
        self.initialization_steps: List[Dict[str, Any]] = []
        
        # Graceful shutdown handling
        self._shutdown_handlers: List[asyncio.Task] = []
        
        logger.info("Production environment manager initialized")
    
    async def initialize_production_environment(self) -> ProductionServices:
        """
        Initialize complete production environment with all services.
        
        Returns:
            ProductionServices instance with all initialized services
        """
        logger.info("=== Starting Production Environment Initialization ===")
        startup_time = time.time()
        
        try:
            # Step 1: Initialize production configuration
            await self._initialization_step(
                "production_config",
                "Loading production configuration",
                self._initialize_production_config
            )
            
            # Step 2: Initialize secrets management (Agent A1 integration)
            await self._initialization_step(
                "secrets_integration", 
                "Initializing secrets management (Agent A1)",
                self._initialize_secrets_integration
            )
            
            # Step 3: Initialize database with production configuration
            await self._initialization_step(
                "database_manager",
                "Initializing production database",
                self._initialize_database_manager
            )
            
            # Step 4: Initialize Redis cluster
            await self._initialization_step(
                "redis_manager",
                "Initializing Redis cluster", 
                self._initialize_redis_manager
            )
            
            # Step 5: Initialize metrics and alerting (Agent A2 integration)
            await self._initialization_step(
                "metrics_and_alerting",
                "Initializing metrics and alerting (Agent A2)",
                self._initialize_metrics_and_alerting
            )
            
            # Step 6: Initialize security components
            await self._initialization_step(
                "security_components",
                "Initializing security components",
                self._initialize_security_components
            )
            
            # Step 7: Initialize monitoring service
            await self._initialization_step(
                "monitoring_service",
                "Initializing production monitoring",
                self._initialize_monitoring_service
            )
            
            # Step 8: Start all monitoring and background tasks
            await self._initialization_step(
                "background_tasks",
                "Starting background monitoring tasks",
                self._start_background_tasks
            )
            
            # Step 9: Perform health checks
            await self._initialization_step(
                "health_checks",
                "Running initial health checks",
                self._run_initial_health_checks
            )
            
            # Step 10: Register shutdown handlers
            await self._initialization_step(
                "shutdown_handlers",
                "Registering shutdown handlers",
                self._register_shutdown_handlers
            )
            
            # Initialization complete
            total_time = time.time() - startup_time
            self.initialization_complete = True
            
            logger.info(f"=== Production Environment Initialized Successfully ===")
            logger.info(f"Total initialization time: {total_time:.2f} seconds")
            logger.info(f"Initialization steps completed: {len(self.initialization_steps)}")
            
            # Record initialization metrics
            if self.services.metrics_service:
                self.services.metrics_service.record_user_activity("system", "production_startup")
                self.services.metrics_service.update_health_status("healthy")
            
            return self.services
            
        except Exception as e:
            logger.error(f"Production environment initialization failed: {e}")
            
            # Cleanup on failure
            if self.services:
                await self._cleanup_services()
            
            raise
    
    async def _initialization_step(
        self,
        step_name: str,
        description: str,
        step_function
    ):
        """Execute an initialization step with monitoring."""
        step_start = time.time()
        logger.info(f"Step: {description}")
        
        try:
            result = await step_function()
            step_duration = time.time() - step_start
            
            step_record = {
                "step_name": step_name,
                "description": description,
                "duration_seconds": step_duration,
                "success": True,
                "timestamp": time.time()
            }
            
            self.initialization_steps.append(step_record)
            logger.info(f"✓ Completed: {description} ({step_duration:.2f}s)")
            
            return result
            
        except Exception as e:
            step_duration = time.time() - step_start
            
            step_record = {
                "step_name": step_name,
                "description": description,
                "duration_seconds": step_duration,
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
            
            self.initialization_steps.append(step_record)
            logger.error(f"✗ Failed: {description} ({step_duration:.2f}s): {e}")
            
            raise
    
    async def _initialize_production_config(self):
        """Initialize production configuration."""
        from ..config.production import ProductionConfig
        
        production_config = ProductionConfig()
        
        if not self.services:
            self.services = ProductionServices(
                production_config=production_config,
                secrets_integration=None,
                database_manager=None,
                redis_manager=None,
                metrics_service=None,
                alerting_service=None,
                monitoring_service=None,
                security_headers=None,
                ip_whitelist=None,
                request_signing=None
            )
        else:
            self.services.production_config = production_config
    
    async def _initialize_secrets_integration(self):
        """Initialize secrets management integration with Agent A1."""
        from ..config.secrets_integration import create_production_secrets_integration
        
        secrets_integration = create_production_secrets_integration(
            self.services.production_config
        )
        
        await secrets_integration.initialize()
        self.services.secrets_integration = secrets_integration
    
    async def _initialize_database_manager(self):
        """Initialize production database manager."""
        from ..database.production_config import create_production_database_manager
        
        database_manager = create_production_database_manager(
            self.services.production_config
        )
        
        await database_manager.initialize()
        self.services.database_manager = database_manager
    
    async def _initialize_redis_manager(self):
        """Initialize Redis cluster manager."""
        from ..config.redis_cluster import create_redis_cluster_manager
        
        redis_config = self.services.production_config.get_redis_config()
        
        redis_manager = create_redis_cluster_manager(
            nodes=redis_config["cluster_nodes"],
            backend_type="cluster" if redis_config["cluster_enabled"] else "standalone",
            max_connections=redis_config["connection_pool_kwargs"]["max_connections"]
        )
        
        await redis_manager.initialize()
        self.services.redis_manager = redis_manager
    
    async def _initialize_metrics_and_alerting(self):
        """Initialize metrics and alerting services (Agent A2 integration)."""
        from ..services.metrics_service import MetricsService
        from ..services.alert_service import AlertingService
        
        # Initialize metrics service
        metrics_service = MetricsService(
            app_name="ai_pdf_scholar",
            version="2.1.0",
            enable_push_gateway=True
        )
        
        # Initialize alerting service
        alerting_service = AlertingService()
        
        # Start metrics server
        monitoring_config = self.services.production_config.get_monitoring_config()
        if monitoring_config["prometheus"]["enabled"]:
            metrics_service.start_metrics_server(
                port=monitoring_config["prometheus"]["port"]
            )
        
        self.services.metrics_service = metrics_service
        self.services.alerting_service = alerting_service
    
    async def _initialize_security_components(self):
        """Initialize security components."""
        from ..api.security.production_headers import create_production_security_headers
        from ..api.security.ip_whitelist import create_production_ip_whitelist
        from ..api.security.request_signing import create_production_request_signing
        
        # Initialize security headers
        security_headers = create_production_security_headers(
            self.services.production_config,
            self.services.metrics_service
        )
        
        # Initialize IP whitelist
        ip_whitelist = create_production_ip_whitelist(
            self.services.production_config,
            self.services.metrics_service
        )
        
        # Initialize request signing
        request_signing = create_production_request_signing(
            self.services.secrets_integration.secrets_manager,
            self.services.production_config,
            self.services.metrics_service
        )
        
        self.services.security_headers = security_headers
        self.services.ip_whitelist = ip_whitelist
        self.services.request_signing = request_signing
    
    async def _initialize_monitoring_service(self):
        """Initialize comprehensive monitoring service."""
        from ..services.production_monitoring import create_production_monitoring_service
        
        monitoring_service = create_production_monitoring_service(
            production_config=self.services.production_config,
            metrics_service=self.services.metrics_service,
            alerting_service=self.services.alerting_service,
            secrets_integration=self.services.secrets_integration,
            database_manager=self.services.database_manager,
            redis_manager=self.services.redis_manager
        )
        
        self.services.monitoring_service = monitoring_service
    
    async def _start_background_tasks(self):
        """Start all background monitoring and maintenance tasks."""
        # Start monitoring service
        await self.services.monitoring_service.start_monitoring()
        
        logger.info("All background tasks started successfully")
    
    async def _run_initial_health_checks(self):
        """Run initial health checks to verify system status."""
        health_status = self.services.monitoring_service.get_overall_health()
        
        if health_status["status"] == "unhealthy":
            critical_issues = health_status.get("critical_issues", [])
            raise RuntimeError(f"Critical health check failures: {critical_issues}")
        
        if health_status["status"] == "degraded":
            logger.warning(f"System started in degraded state: {health_status.get('non_critical_issues', [])}")
        
        logger.info(f"Initial health check passed: {health_status['status']}")
    
    async def _register_shutdown_handlers(self):
        """Register graceful shutdown handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.shutdown_production_environment())
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Shutdown handlers registered")
    
    async def shutdown_production_environment(self):
        """Gracefully shutdown all production services."""
        if self.shutdown_initiated:
            logger.info("Shutdown already in progress")
            return
        
        self.shutdown_initiated = True
        shutdown_start = time.time()
        
        logger.info("=== Starting Production Environment Shutdown ===")
        
        try:
            # Stop monitoring service
            if self.services and self.services.monitoring_service:
                logger.info("Stopping monitoring service...")
                await self.services.monitoring_service.stop_monitoring()
            
            # Cleanup services in reverse initialization order
            await self._cleanup_services()
            
            shutdown_time = time.time() - shutdown_start
            logger.info(f"=== Production Environment Shutdown Completed ({shutdown_time:.2f}s) ===")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            raise
    
    async def _cleanup_services(self):
        """Cleanup all services in proper order."""
        if not self.services:
            return
        
        cleanup_tasks = []
        
        # Close database connections
        if self.services.database_manager:
            logger.info("Closing database connections...")
            cleanup_tasks.append(self.services.database_manager.close())
        
        # Close Redis connections
        if self.services.redis_manager:
            logger.info("Closing Redis connections...")
            cleanup_tasks.append(self.services.redis_manager.close())
        
        # Stop metrics services
        if self.services.metrics_service:
            logger.info("Stopping metrics collection...")
            # Metrics service cleanup would go here
        
        # Execute cleanup tasks
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("Service cleanup completed")
    
    @asynccontextmanager
    async def production_environment_context(self):
        """Context manager for production environment lifecycle."""
        services = None
        try:
            services = await self.initialize_production_environment()
            yield services
        finally:
            if services:
                await self.shutdown_production_environment()
    
    def get_initialization_report(self) -> Dict[str, Any]:
        """Get detailed initialization report."""
        total_time = time.time() - self.startup_start_time if hasattr(self, 'startup_start_time') else 0
        
        return {
            "initialization_complete": self.initialization_complete,
            "total_initialization_time": total_time,
            "steps": self.initialization_steps,
            "failed_steps": [step for step in self.initialization_steps if not step["success"]],
            "services_initialized": {
                "production_config": self.services.production_config is not None if self.services else False,
                "secrets_integration": self.services.secrets_integration is not None if self.services else False,
                "database_manager": self.services.database_manager is not None if self.services else False,
                "redis_manager": self.services.redis_manager is not None if self.services else False,
                "metrics_service": self.services.metrics_service is not None if self.services else False,
                "monitoring_service": self.services.monitoring_service is not None if self.services else False
            }
        }


# Global production environment manager instance
_production_manager: Optional[ProductionEnvironmentManager] = None


def get_production_manager() -> ProductionEnvironmentManager:
    """Get global production environment manager."""
    global _production_manager
    if _production_manager is None:
        _production_manager = ProductionEnvironmentManager()
    return _production_manager


async def initialize_production_environment() -> ProductionServices:
    """Initialize complete production environment."""
    manager = get_production_manager()
    return await manager.initialize_production_environment()


async def shutdown_production_environment():
    """Shutdown production environment."""
    manager = get_production_manager()
    await manager.shutdown_production_environment()


@asynccontextmanager
async def production_environment():
    """Context manager for complete production environment."""
    manager = get_production_manager()
    async with manager.production_environment_context() as services:
        yield services


# FastAPI integration
def setup_production_app(app):
    """Set up FastAPI application with all production services."""
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize production environment on application startup."""
        try:
            services = await initialize_production_environment()
            app.state.production_services = services
            logger.info("FastAPI production environment initialized")
        except Exception as e:
            logger.error(f"Failed to initialize production environment: {e}")
            raise
    
    @app.on_event("shutdown") 
    async def shutdown_event():
        """Cleanup production environment on application shutdown."""
        try:
            await shutdown_production_environment()
            logger.info("FastAPI production environment shutdown completed")
        except Exception as e:
            logger.error(f"Error during production environment shutdown: {e}")
    
    # Add health check endpoints
    @app.get("/health/production")
    async def production_health():
        """Get production environment health status."""
        if hasattr(app.state, 'production_services'):
            services = app.state.production_services
            if services and services.monitoring_service:
                return services.monitoring_service.get_overall_health()
        
        return {"status": "unknown", "message": "Production services not initialized"}
    
    @app.get("/admin/production/initialization")
    async def initialization_report():
        """Get production environment initialization report."""
        manager = get_production_manager()
        return manager.get_initialization_report()
    
    logger.info("FastAPI production setup completed")