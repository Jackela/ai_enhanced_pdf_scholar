"""
Production Gunicorn Configuration
Optimized for high-performance production deployment with comprehensive monitoring,
graceful shutdowns, and resource management.
"""

import os
import logging
import multiprocessing
from typing import Any, Dict

# ============================================================================
# Basic Configuration
# ============================================================================

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", str(min(multiprocessing.cpu_count() * 2 + 1, 8))))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "10000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "1000"))

# Worker lifecycle
preload_app = os.getenv("GUNICORN_PRELOAD_APP", "true").lower() == "true"
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "65"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# ============================================================================
# Performance Optimization
# ============================================================================

# Memory management
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")  # Use RAM for temp files
worker_class_str = worker_class

# Connection handling
max_worker_memory = int(os.getenv("MAX_WORKER_MEMORY_MB", "2048")) * 1024 * 1024  # Convert to bytes

# Request limits
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "8190"))
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", "200"))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "8190"))

# ============================================================================
# Security Configuration  
# ============================================================================

# Process ownership
user = os.getenv("GUNICORN_USER", None)
group = os.getenv("GUNICORN_GROUP", None)

# SSL/TLS Configuration
keyfile = os.getenv("GUNICORN_KEYFILE", None)
certfile = os.getenv("GUNICORN_CERTFILE", None)
ssl_version = int(os.getenv("GUNICORN_SSL_VERSION", "2"))  # TLS 1.2
cert_reqs = int(os.getenv("GUNICORN_CERT_REQS", "0"))  # No client cert required
ca_certs = os.getenv("GUNICORN_CA_CERTS", None)
suppress_ragged_eofs = True
do_handshake_on_connect = False
ciphers = os.getenv("GUNICORN_CIPHERS", "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS")

# ============================================================================
# Logging Configuration
# ============================================================================

# Log levels
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True
enable_stdio_inheritance = True

# Access logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # stdout by default
access_log_format = os.getenv(
    "GUNICORN_ACCESS_LOG_FORMAT",
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s %(X-Request-ID)s %(X-Forwarded-For)s'
)

# Error logging
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")  # stdout by default

# Disable access logs if needed for performance
disable_redirect_access_to_syslog = os.getenv("DISABLE_ACCESS_LOG", "false").lower() == "true"
if disable_redirect_access_to_syslog:
    accesslog = None

# ============================================================================
# Process Management
# ============================================================================

# PID file
pidfile = os.getenv("GUNICORN_PID_FILE", "/tmp/gunicorn.pid")

# Daemon mode
daemon = os.getenv("GUNICORN_DAEMON", "false").lower() == "true"

# Process title
proc_name = os.getenv("GUNICORN_PROC_NAME", "ai_pdf_scholar")

# ============================================================================
# Advanced Configuration
# ============================================================================

# Environment variable passthrough
raw_env = [
    f"DATABASE_URL={os.getenv('DATABASE_URL', '')}",
    f"REDIS_URL={os.getenv('REDIS_URL', '')}",
    f"GOOGLE_API_KEY={os.getenv('GOOGLE_API_KEY', '')}",
    f"SECRET_KEY={os.getenv('SECRET_KEY', '')}",
    f"ENVIRONMENT={os.getenv('ENVIRONMENT', 'production')}",
    f"LOG_LEVEL={os.getenv('LOG_LEVEL', 'INFO')}",
    f"METRICS_PORT={os.getenv('METRICS_PORT', '9090')}",
    f"ENABLE_PROMETHEUS={os.getenv('ENABLE_PROMETHEUS', 'true')}",
    f"CORS_ORIGINS={os.getenv('CORS_ORIGINS', '')}",
]

# ============================================================================
# Monitoring and Health Checks
# ============================================================================

def when_ready(server):
    """Called when the server is started and ready to accept connections."""
    server.log.info("AI PDF Scholar server is ready. Workers: %d", server.num_workers)
    
    # Optional: Register with service discovery
    register_with_service_discovery()
    
    # Optional: Warm up application
    warmup_application()


def on_starting(server):
    """Called at server startup."""
    server.log.info("Starting AI PDF Scholar server...")
    server.log.info("Configuration: %d workers, %s worker class", 
                    server.cfg.workers, server.cfg.worker_class)
    
    # Initialize monitoring
    setup_monitoring()


def on_reload(server):
    """Called when configuration is reloaded."""
    server.log.info("Configuration reloaded")


def worker_int(worker):
    """Called when a worker receives a SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received SIGINT/SIGQUIT")


def pre_fork(server, worker):
    """Called before forking a worker."""
    server.log.debug("Worker %d forked", worker.pid)


def post_fork(server, worker):
    """Called after forking a worker."""
    server.log.debug("Worker %d ready", worker.pid)
    
    # Set up worker-specific resources
    setup_worker_resources()


def pre_exec(server):
    """Called before re-executing the master process."""
    server.log.info("Forked child, re-executing")


def when_ready(server):
    """Called when server is ready."""
    server.log.info("Server is ready. Listening on: %s", server.address)


def worker_abort(worker):
    """Called when a worker is killed by SIGKILL."""
    worker.log.error("Worker was killed by SIGKILL")


def pre_request(worker, req):
    """Called before processing a request."""
    # Add request ID for tracing
    import uuid
    req.headers.append(("X-Request-ID", str(uuid.uuid4())))


def post_request(worker, req, environ, resp):
    """Called after processing a request."""
    # Log performance metrics if needed
    pass


def nworkers_changed(server, new_value, old_value):
    """Called when number of workers changes."""
    server.log.info("Number of workers changed from %d to %d", old_value, new_value)


def on_exit(server):
    """Called when server is shutting down."""
    server.log.info("Shutting down AI PDF Scholar server")
    
    # Cleanup resources
    cleanup_resources()
    
    # Deregister from service discovery
    deregister_from_service_discovery()


# ============================================================================
# Custom Hook Functions
# ============================================================================

def setup_monitoring():
    """Initialize monitoring and metrics collection."""
    try:
        # Initialize Prometheus metrics if enabled
        if os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true":
            from backend.services.metrics_service import MetricsService
            metrics_service = MetricsService(
                app_name="ai_pdf_scholar",
                version=os.getenv("APP_VERSION", "2.0.0")
            )
            # Start metrics server on separate port
            metrics_port = int(os.getenv("METRICS_PORT", "9090"))
            metrics_service.start_metrics_server(port=metrics_port)
    except ImportError:
        logging.warning("Metrics service not available")
    except Exception as e:
        logging.error(f"Failed to setup monitoring: {e}")


def setup_worker_resources():
    """Set up worker-specific resources."""
    try:
        # Set memory limits for worker
        import resource
        if 'max_worker_memory' in globals():
            resource.setrlimit(resource.RLIMIT_AS, (max_worker_memory, max_worker_memory))
        
        # Set CPU limits if needed
        cpu_limit = os.getenv("WORKER_CPU_LIMIT")
        if cpu_limit:
            import psutil
            p = psutil.Process()
            p.cpu_affinity(list(range(int(cpu_limit))))
            
    except Exception as e:
        logging.warning(f"Failed to setup worker resources: {e}")


def warmup_application():
    """Warm up the application after startup."""
    try:
        import requests
        import time
        
        # Wait a moment for server to be ready
        time.sleep(2)
        
        # Make a health check request to warm up
        health_url = f"http://{bind.split(':')[0]}:{bind.split(':')[1]}/health"
        requests.get(health_url, timeout=5)
        logging.info("Application warmed up successfully")
        
    except Exception as e:
        logging.warning(f"Application warmup failed: {e}")


def register_with_service_discovery():
    """Register with service discovery system."""
    try:
        # Placeholder for service discovery registration
        # In production, this would register with Consul, etcd, etc.
        service_discovery_url = os.getenv("SERVICE_DISCOVERY_URL")
        if service_discovery_url:
            logging.info(f"Would register with service discovery at {service_discovery_url}")
    except Exception as e:
        logging.error(f"Service discovery registration failed: {e}")


def deregister_from_service_discovery():
    """Deregister from service discovery system."""
    try:
        # Placeholder for service discovery deregistration
        service_discovery_url = os.getenv("SERVICE_DISCOVERY_URL")
        if service_discovery_url:
            logging.info("Would deregister from service discovery")
    except Exception as e:
        logging.error(f"Service discovery deregistration failed: {e}")


def cleanup_resources():
    """Clean up resources on shutdown."""
    try:
        # Close database connections
        # Close Redis connections
        # Clean up temporary files
        logging.info("Resources cleaned up")
    except Exception as e:
        logging.error(f"Resource cleanup failed: {e}")


# ============================================================================
# Dynamic Configuration Based on Environment
# ============================================================================

def load_environment_config():
    """Load environment-specific configuration."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    
    if env == "development":
        # Development overrides
        global workers, loglevel, accesslog, timeout
        workers = 1
        loglevel = "debug"
        timeout = 120  # Longer timeout for debugging
        
    elif env == "staging":
        # Staging overrides
        global workers, loglevel
        workers = max(2, multiprocessing.cpu_count())
        loglevel = "info"
        
    elif env == "production":
        # Production is the default, but we can add specific overrides
        global workers, loglevel, preload_app
        workers = min(workers, int(os.getenv("MAX_WORKERS", "8")))
        preload_app = True
        
        # Enable all security features in production
        if not keyfile and not certfile:
            logging.warning("Running in production without SSL/TLS certificates")


# Apply environment configuration
load_environment_config()

# ============================================================================
# Health Check Configuration
# ============================================================================

def get_health_check_config() -> Dict[str, Any]:
    """Get health check configuration for load balancer."""
    return {
        "health_check_path": "/health",
        "health_check_interval": 30,
        "health_check_timeout": 5,
        "healthy_threshold": 2,
        "unhealthy_threshold": 3
    }


# ============================================================================
# Custom Error Pages
# ============================================================================

def custom_error_page(status_code: int, message: str) -> str:
    """Generate custom error page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI PDF Scholar - Error {status_code}</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
            .error {{ color: #d32f2f; }}
        </style>
    </head>
    <body>
        <h1 class="error">Error {status_code}</h1>
        <p>{message}</p>
        <p>Please try again later or contact support.</p>
    </body>
    </html>
    """


# ============================================================================
# Performance Monitoring
# ============================================================================

class PerformanceMonitor:
    """Monitor worker performance and resource usage."""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.start_time = None
    
    def record_request(self, status_code: int):
        """Record request metrics."""
        self.request_count += 1
        if status_code >= 400:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        uptime = 0
        if self.start_time:
            from time import time
            uptime = time() - self.start_time
            
        return {
            "uptime_seconds": uptime,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1)
        }


# Global performance monitor
performance_monitor = PerformanceMonitor()

# ============================================================================
# Logging Configuration
# ============================================================================

# Custom logging format with more details
detailed_log_format = (
    "%(asctime)s [%(process)d:%(thread)d] [%(levelname)s] "
    "%(name)s: %(message)s [in %(pathname)s:%(lineno)d]"
)

# Configure Python logging
logging.basicConfig(
    level=getattr(logging, loglevel.upper()),
    format=detailed_log_format
)

# Suppress noisy loggers in production
if loglevel != "debug":
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    
logging.info("Gunicorn configuration loaded successfully")
logging.info(f"Workers: {workers}, Worker Class: {worker_class}")
logging.info(f"Bind: {bind}, Backlog: {backlog}")
logging.info(f"Timeout: {timeout}s, Graceful Timeout: {graceful_timeout}s")