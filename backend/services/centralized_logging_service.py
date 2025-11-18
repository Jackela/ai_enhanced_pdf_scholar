"""
Centralized Logging Service with ELK Stack Integration
Production-ready centralized logging and log aggregation system.
"""

import json
import logging
import logging.handlers
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from loguru import logger as loguru_logger
from pythonjsonlogger import jsonlogger

# ============================================================================
# Logging Configuration
# ============================================================================


class LogLevel(str, Enum):
    """Log severity levels."""

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogSource(str, Enum):
    """Log source types."""

    API = "api"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    DOCUMENT_PROCESSING = "document_processing"
    RAG_QUERY = "rag_query"
    CACHE = "cache"
    SECURITY = "security"
    AUDIT = "audit"
    SYSTEM = "system"
    EXTERNAL = "external"


class ElasticsearchConfig:
    """Elasticsearch configuration."""

    def __init__(self):
        """Initialize Elasticsearch configuration from environment."""
        # Connection settings
        self.hosts = os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(
            ","
        )
        self.username = os.getenv("ELASTICSEARCH_USERNAME", "")
        self.password = os.getenv("ELASTICSEARCH_PASSWORD", "")
        self.api_key = os.getenv("ELASTICSEARCH_API_KEY", "")

        # SSL settings
        self.use_ssl = os.getenv("ELASTICSEARCH_USE_SSL", "false").lower() == "true"
        self.ca_certs = os.getenv("ELASTICSEARCH_CA_CERTS", "")
        self.client_cert = os.getenv("ELASTICSEARCH_CLIENT_CERT", "")
        self.client_key = os.getenv("ELASTICSEARCH_CLIENT_KEY", "")
        self.verify_certs = (
            os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
        )

        # Index settings
        self.index_prefix = os.getenv("ELASTICSEARCH_INDEX_PREFIX", "ai-pdf-scholar")
        self.index_template = os.getenv(
            "ELASTICSEARCH_INDEX_TEMPLATE", f"{self.index_prefix}-%Y.%m.%d"
        )

        # Performance settings
        self.timeout = int(os.getenv("ELASTICSEARCH_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("ELASTICSEARCH_MAX_RETRIES", "3"))
        self.retry_on_timeout = True

        # Bulk indexing
        self.bulk_size = int(os.getenv("ELASTICSEARCH_BULK_SIZE", "500"))
        self.flush_interval = int(
            os.getenv("ELASTICSEARCH_FLUSH_INTERVAL", "5")
        )  # seconds


class LogstashConfig:
    """Logstash configuration."""

    def __init__(self):
        """Initialize Logstash configuration from environment."""
        self.host = os.getenv("LOGSTASH_HOST", "localhost")
        self.port = int(os.getenv("LOGSTASH_PORT", "5044"))
        self.use_tcp = os.getenv("LOGSTASH_USE_TCP", "true").lower() == "true"
        self.use_ssl = os.getenv("LOGSTASH_USE_SSL", "false").lower() == "true"
        self.cert_file = os.getenv("LOGSTASH_CERT_FILE", "")
        self.key_file = os.getenv("LOGSTASH_KEY_FILE", "")
        self.ca_file = os.getenv("LOGSTASH_CA_FILE", "")


# ============================================================================
# Custom Log Formatters
# ============================================================================


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Structured JSON formatter for logs."""

    def __init__(self, service_name: str = "ai-pdf-scholar"):
        """Initialize formatter."""
        self.service_name = service_name
        self.hostname = socket.gethostname()

        # Define log format
        format_string = (
            "%(asctime)s %(name)s %(levelname)s %(funcName)s "
            "%(lineno)d %(message)s %(pathname)s %(module)s"
        )

        super().__init__(
            format_string,
            rename_fields={
                "asctime": "timestamp",
                "name": "logger_name",
                "levelname": "level",
                "funcName": "function",
                "lineno": "line",
                "pathname": "file_path",
                "module": "module",
            },
        )

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add service information
        log_record["service"] = self.service_name
        log_record["hostname"] = self.hostname
        log_record["environment"] = os.getenv("ENVIRONMENT", "development")

        # Add correlation ID if available
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_record["correlation_id"] = correlation_id

        # Add trace information if available
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_record["trace_id"] = trace_id

        span_id = getattr(record, "span_id", None)
        if span_id:
            log_record["span_id"] = span_id

        # Add user context
        user_id = getattr(record, "user_id", None)
        if user_id:
            log_record["user_id"] = user_id

        # Add custom fields
        extra_fields = getattr(record, "extra_fields", {})
        if extra_fields:
            log_record.update(extra_fields)

        # Ensure timestamp is ISO format
        if "timestamp" in log_record:
            try:
                # Convert to datetime and back to ensure consistent format
                dt = datetime.fromisoformat(
                    log_record["timestamp"].replace("Z", "+00:00")
                )
                log_record["timestamp"] = dt.isoformat()
            except:
                log_record["timestamp"] = datetime.utcnow().isoformat()


# ============================================================================
# Elasticsearch Handler
# ============================================================================


class ElasticsearchHandler(logging.Handler):
    """Custom logging handler for Elasticsearch."""

    def __init__(self, config: ElasticsearchConfig):
        """Initialize Elasticsearch handler."""
        super().__init__()
        self.config = config
        self.client = None
        self.buffer = []
        self.buffer_lock = threading.Lock()

        # Initialize Elasticsearch client
        self._init_elasticsearch()

        # Start flush timer
        self._start_flush_timer()

    def _init_elasticsearch(self):
        """Initialize Elasticsearch client."""
        try:
            client_config = {
                "hosts": self.config.hosts,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
                "retry_on_timeout": self.config.retry_on_timeout,
            }

            # Authentication
            if self.config.api_key:
                client_config["api_key"] = self.config.api_key
            elif self.config.username and self.config.password:
                client_config["http_auth"] = (
                    self.config.username,
                    self.config.password,
                )

            # SSL configuration
            if self.config.use_ssl:
                client_config["use_ssl"] = True
                client_config["verify_certs"] = self.config.verify_certs

                if self.config.ca_certs:
                    client_config["ca_certs"] = self.config.ca_certs

                if self.config.client_cert and self.config.client_key:
                    client_config["client_cert"] = self.config.client_cert
                    client_config["client_key"] = self.config.client_key

            self.client = Elasticsearch(**client_config)

            # Test connection
            if self.client.ping():
                logging.getLogger(__name__).info("Connected to Elasticsearch")
            else:
                raise Exception("Failed to ping Elasticsearch")

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to connect to Elasticsearch: {e}"
            )
            self.client = None

    def emit(self, record):
        """Emit a log record to Elasticsearch."""
        if not self.client:
            return

        try:
            # Format the record
            log_entry = self.format(record)

            # Parse JSON if formatter is structured
            if isinstance(self.formatter, StructuredFormatter):
                log_data = json.loads(log_entry)
            else:
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "message": log_entry,
                    "logger_name": record.name,
                }

            # Add to buffer
            with self.buffer_lock:
                self.buffer.append(
                    {
                        "_index": datetime.now().strftime(self.config.index_template),
                        "_source": log_data,
                    }
                )

                # Flush if buffer is full
                if len(self.buffer) >= self.config.bulk_size:
                    self._flush_buffer()

        except Exception:
            self.handleError(record)

    def _flush_buffer(self):
        """Flush log buffer to Elasticsearch."""
        if not self.buffer or not self.client:
            return

        try:
            # Bulk index logs
            bulk(self.client, self.buffer)
            self.buffer.clear()

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to flush logs to Elasticsearch: {e}"
            )

    def _start_flush_timer(self):
        """Start periodic buffer flush."""

        def flush_periodically():
            while True:
                time.sleep(self.config.flush_interval)
                with self.buffer_lock:
                    if self.buffer:
                        self._flush_buffer()

        timer_thread = threading.Thread(target=flush_periodically, daemon=True)
        timer_thread.start()

    def close(self):
        """Close handler and flush remaining logs."""
        with self.buffer_lock:
            self._flush_buffer()
        super().close()


# ============================================================================
# Logstash Handler
# ============================================================================


class LogstashHandler(logging.handlers.SocketHandler):
    """Custom logging handler for Logstash."""

    def __init__(self, config: LogstashConfig):
        """Initialize Logstash handler."""
        self.config = config

        if config.use_tcp:
            super().__init__(config.host, config.port)
        else:
            # Use UDP socket handler for better performance
            super().__init__(config.host, config.port)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def emit(self, record):
        """Emit a log record to Logstash."""
        try:
            # Format the record as JSON
            log_entry = self.format(record)

            if isinstance(self.formatter, StructuredFormatter):
                # Already JSON formatted
                data = log_entry.encode("utf-8")
            else:
                # Convert to JSON
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "message": log_entry,
                    "logger_name": record.name,
                    "service": "ai-pdf-scholar",
                }
                data = json.dumps(log_data).encode("utf-8")

            if self.config.use_tcp:
                super().emit(record)
            else:
                # Send via UDP
                self.socket.sendto(data, (self.config.host, self.config.port))

        except Exception:
            self.handleError(record)


# ============================================================================
# Centralized Logging Service
# ============================================================================


class CentralizedLoggingService:
    """
    Comprehensive centralized logging service with ELK stack integration.
    """

    def __init__(
        self,
        service_name: str = "ai-pdf-scholar",
        log_level: LogLevel = LogLevel.INFO,
        enable_elasticsearch: bool = True,
        enable_logstash: bool = False,
        enable_file_logging: bool = True,
        log_directory: str = "./logs",
    ):
        """Initialize centralized logging service."""
        self.service_name = service_name
        self.log_level = getattr(logging, log_level.value.upper())
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_logstash = enable_logstash
        self.enable_file_logging = enable_file_logging
        self.log_directory = Path(log_directory)

        # Create log directory
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.elasticsearch_config = ElasticsearchConfig()
        self.logstash_config = LogstashConfig()

        # Handlers
        self.handlers = []

        # Setup logging
        self._setup_logging()

        logging.getLogger(__name__).info(
            f"Centralized logging service initialized for {service_name}"
        )

    def _setup_logging(self):
        """Setup comprehensive logging configuration."""
        # Create structured formatter
        formatter = StructuredFormatter(self.service_name)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        self.handlers.append(console_handler)

        # File handlers
        if self.enable_file_logging:
            self._setup_file_handlers(formatter)

        # Elasticsearch handler
        if self.enable_elasticsearch:
            try:
                es_handler = ElasticsearchHandler(self.elasticsearch_config)
                es_handler.setFormatter(formatter)
                es_handler.setLevel(logging.DEBUG)
                self.handlers.append(es_handler)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Failed to setup Elasticsearch handler: {e}"
                )

        # Logstash handler
        if self.enable_logstash:
            try:
                logstash_handler = LogstashHandler(self.logstash_config)
                logstash_handler.setFormatter(formatter)
                logstash_handler.setLevel(logging.DEBUG)
                self.handlers.append(logstash_handler)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Failed to setup Logstash handler: {e}"
                )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add our handlers
        for handler in self.handlers:
            root_logger.addHandler(handler)

        # Setup loguru for enhanced logging
        self._setup_loguru()

    def _setup_file_handlers(self, formatter):
        """Setup file-based logging handlers."""
        # Application log file (rotating)
        app_log_file = self.log_directory / "application.log"
        app_handler = logging.handlers.RotatingFileHandler(
            app_log_file, maxBytes=50 * 1024 * 1024, backupCount=10  # 50MB
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)
        self.handlers.append(app_handler)

        # Error log file
        error_log_file = self.log_directory / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        self.handlers.append(error_handler)

        # Audit log file (separate for compliance)
        audit_log_file = self.log_directory / "audit.log"
        audit_handler = logging.handlers.TimedRotatingFileHandler(
            audit_log_file,
            when="midnight",
            interval=1,
            backupCount=365,  # Keep for 1 year
        )
        audit_handler.setFormatter(formatter)
        audit_handler.setLevel(logging.INFO)
        # Only add audit events to this handler
        audit_handler.addFilter(lambda record: getattr(record, "audit_event", False))
        self.handlers.append(audit_handler)

        # Security log file
        security_log_file = self.log_directory / "security.log"
        security_handler = logging.handlers.RotatingFileHandler(
            security_log_file, maxBytes=20 * 1024 * 1024, backupCount=10  # 20MB
        )
        security_handler.setFormatter(formatter)
        security_handler.setLevel(logging.WARNING)
        # Only add security events to this handler
        security_handler.addFilter(
            lambda record: getattr(record, "security_event", False)
        )
        self.handlers.append(security_handler)

    def _setup_loguru(self):
        """Setup loguru for enhanced logging features."""
        # Remove default loguru handler
        loguru_logger.remove()

        # Add loguru handler that forwards to our logging system
        def loguru_sink(message):
            # Parse loguru message and forward to standard logging
            logger = logging.getLogger("loguru")
            level = message.record["level"].name.lower()

            if hasattr(logger, level):
                getattr(logger, level)(message.record["message"])

        loguru_logger.add(
            loguru_sink,
            format="{time} | {level} | {name}:{function}:{line} | {message}",
            level="DEBUG",
        )

    # ========================================================================
    # Enhanced Logging Methods
    # ========================================================================

    def get_logger(
        self,
        name: str,
        source: LogSource = LogSource.SYSTEM,
        correlation_id: str | None = None,
    ) -> logging.Logger:
        """Get a configured logger instance."""
        logger = logging.getLogger(name)

        # Add contextual information
        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.source = source.value
                if correlation_id:
                    record.correlation_id = correlation_id
                return True

        logger.addFilter(ContextFilter())
        return logger

    def log_structured(
        self,
        level: LogLevel,
        message: str,
        source: LogSource = LogSource.SYSTEM,
        user_id: int | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        extra_fields: dict[str, Any] | None = None,
        audit_event: bool = False,
        security_event: bool = False,
    ):
        """Log a structured message with context."""
        logger = logging.getLogger(source.value)

        # Create log record
        record = logger.makeRecord(
            name=logger.name,
            level=getattr(logging, level.value.upper()),
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add context
        record.source = source.value
        record.user_id = user_id
        record.trace_id = trace_id
        record.span_id = span_id
        record.correlation_id = correlation_id
        record.extra_fields = extra_fields or {}
        record.audit_event = audit_event
        record.security_event = security_event

        # Handle the record
        logger.handle(record)

    def log_api_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        user_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_size: int | None = None,
        response_size: int | None = None,
    ):
        """Log API request with standard fields."""
        extra_fields = {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration": duration,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_size": request_size,
            "response_size": response_size,
        }

        level = LogLevel.INFO if status_code < 400 else LogLevel.ERROR

        self.log_structured(
            level=level,
            message=f"{method} {endpoint} - {status_code} ({duration:.3f}s)",
            source=LogSource.API,
            user_id=user_id,
            extra_fields=extra_fields,
            audit_event=True,
        )

    def log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "medium",
        user_id: int | None = None,
        ip_address: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ):
        """Log security event."""
        extra_fields = {
            "event_type": event_type,
            "severity": severity,
            "ip_address": ip_address,
            **(additional_data or {}),
        }

        level_map = {
            "low": LogLevel.INFO,
            "medium": LogLevel.WARNING,
            "high": LogLevel.ERROR,
            "critical": LogLevel.CRITICAL,
        }

        self.log_structured(
            level=level_map.get(severity, LogLevel.WARNING),
            message=f"Security Event: {event_type} - {description}",
            source=LogSource.SECURITY,
            user_id=user_id,
            extra_fields=extra_fields,
            security_event=True,
            audit_event=True,
        )

    def log_database_query(
        self,
        operation: str,
        table: str,
        duration: float,
        rows_affected: int | None = None,
        user_id: int | None = None,
        query: str | None = None,
    ):
        """Log database query."""
        extra_fields = {
            "operation": operation,
            "table": table,
            "duration": duration,
            "rows_affected": rows_affected,
            "query": query[:200] if query else None,  # Truncate long queries
        }

        # Log slow queries as warnings
        level = LogLevel.WARNING if duration > 1.0 else LogLevel.DEBUG

        self.log_structured(
            level=level,
            message=f"DB {operation} on {table} ({duration:.3f}s)",
            source=LogSource.DATABASE,
            user_id=user_id,
            extra_fields=extra_fields,
        )

    def log_document_processing(
        self,
        document_id: int,
        operation: str,
        duration: float,
        success: bool,
        user_id: int | None = None,
        file_size: int | None = None,
        pages: int | None = None,
        error: str | None = None,
    ):
        """Log document processing operation."""
        extra_fields = {
            "document_id": document_id,
            "operation": operation,
            "duration": duration,
            "success": success,
            "file_size": file_size,
            "pages": pages,
            "error": error,
        }

        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "completed" if success else "failed"

        self.log_structured(
            level=level,
            message=f"Document processing {status}: {operation} for document {document_id} ({duration:.3f}s)",
            source=LogSource.DOCUMENT_PROCESSING,
            user_id=user_id,
            extra_fields=extra_fields,
            audit_event=True,
        )

    def log_rag_query(
        self,
        query_hash: str,
        document_id: int | None,
        duration: float,
        success: bool,
        retrieval_count: int | None = None,
        relevance_scores: list[float] | None = None,
        model_used: str | None = None,
        user_id: int | None = None,
    ):
        """Log RAG query operation."""
        extra_fields = {
            "query_hash": query_hash,
            "document_id": document_id,
            "duration": duration,
            "success": success,
            "retrieval_count": retrieval_count,
            "max_relevance": max(relevance_scores) if relevance_scores else None,
            "avg_relevance": (
                sum(relevance_scores) / len(relevance_scores)
                if relevance_scores
                else None
            ),
            "model_used": model_used,
        }

        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "completed" if success else "failed"

        self.log_structured(
            level=level,
            message=f"RAG query {status}: {query_hash} ({duration:.3f}s)",
            source=LogSource.RAG_QUERY,
            user_id=user_id,
            extra_fields=extra_fields,
            audit_event=True,
        )

    # ========================================================================
    # Log Analytics and Search
    # ========================================================================

    def search_logs(
        self,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        log_level: LogLevel | None = None,
        source: LogSource | None = None,
        user_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search logs in Elasticsearch."""
        if not self.enable_elasticsearch or not hasattr(self, "elasticsearch_handler"):
            return []

        try:
            # Build Elasticsearch query
            es_query = {
                "bool": {"must": [{"query_string": {"query": query}}], "filter": []}
            }

            # Add filters
            if start_time or end_time:
                time_range = {}
                if start_time:
                    time_range["gte"] = start_time.isoformat()
                if end_time:
                    time_range["lte"] = end_time.isoformat()
                es_query["bool"]["filter"].append({"range": {"timestamp": time_range}})

            if log_level:
                es_query["bool"]["filter"].append({"term": {"level": log_level.value}})

            if source:
                es_query["bool"]["filter"].append({"term": {"source": source.value}})

            if user_id:
                es_query["bool"]["filter"].append({"term": {"user_id": user_id}})

            # Search
            response = self.elasticsearch_handler.client.search(
                index=f"{self.elasticsearch_config.index_prefix}-*",
                body={
                    "query": es_query,
                    "sort": [{"timestamp": {"order": "desc"}}],
                    "size": limit,
                },
            )

            return [hit["_source"] for hit in response["hits"]["hits"]]

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to search logs: {e}")
            return []

    def get_log_statistics(
        self, start_time: datetime, end_time: datetime
    ) -> dict[str, Any]:
        """Get log statistics for a time period."""
        if not self.enable_elasticsearch or not hasattr(self, "elasticsearch_handler"):
            return {}

        try:
            # Build aggregation query
            query = {
                "query": {
                    "range": {
                        "timestamp": {
                            "gte": start_time.isoformat(),
                            "lte": end_time.isoformat(),
                        }
                    }
                },
                "aggs": {
                    "levels": {"terms": {"field": "level"}},
                    "sources": {"terms": {"field": "source"}},
                    "hourly_distribution": {
                        "date_histogram": {"field": "timestamp", "interval": "1h"}
                    },
                    "error_rate": {
                        "filter": {"terms": {"level": ["error", "critical"]}}
                    },
                },
                "size": 0,
            }

            response = self.elasticsearch_handler.client.search(
                index=f"{self.elasticsearch_config.index_prefix}-*", body=query
            )

            return {
                "total_logs": response["hits"]["total"]["value"],
                "levels": response["aggregations"]["levels"]["buckets"],
                "sources": response["aggregations"]["sources"]["buckets"],
                "hourly_distribution": response["aggregations"]["hourly_distribution"][
                    "buckets"
                ],
                "error_count": response["aggregations"]["error_rate"]["doc_count"],
            }

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get log statistics: {e}")
            return {}

    # ========================================================================
    # Log Management
    # ========================================================================

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files and indices."""
        # Clean up file logs
        if self.enable_file_logging:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            for log_file in self.log_directory.glob("*.log*"):
                try:
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        log_file.unlink()
                        logging.getLogger(__name__).info(
                            f"Deleted old log file: {log_file}"
                        )
                except Exception as e:
                    logging.getLogger(__name__).error(
                        f"Failed to delete log file {log_file}: {e}"
                    )

        # Clean up Elasticsearch indices
        if self.enable_elasticsearch and hasattr(self, "elasticsearch_handler"):
            try:
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)

                # Get all indices matching our pattern
                indices = self.elasticsearch_handler.client.indices.get(
                    index=f"{self.elasticsearch_config.index_prefix}-*"
                )

                for index_name in indices:
                    # Extract date from index name
                    try:
                        date_str = index_name.split("-")[
                            -3:
                        ]  # Assumes YYYY.MM.DD format
                        index_date = datetime.strptime(".".join(date_str), "%Y.%m.%d")

                        if index_date < cutoff_date:
                            self.elasticsearch_handler.client.indices.delete(
                                index=index_name
                            )
                            logging.getLogger(__name__).info(
                                f"Deleted old Elasticsearch index: {index_name}"
                            )
                    except (ValueError, IndexError):
                        # Skip indices that don't match expected format
                        continue

            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Failed to cleanup Elasticsearch indices: {e}"
                )

    def flush_logs(self):
        """Flush all log handlers."""
        for handler in self.handlers:
            handler.flush()
            if hasattr(handler, "_flush_buffer"):
                handler._flush_buffer()

    def close(self):
        """Close all log handlers."""
        self.flush_logs()

        for handler in self.handlers:
            handler.close()

        logging.getLogger(__name__).info("Centralized logging service closed")


# ============================================================================
# Log Context Manager
# ============================================================================


class LoggingContext:
    """Context manager for adding correlation ID to logs."""

    def __init__(self, correlation_id: str | None = None, **kwargs):
        """Initialize logging context."""
        self.correlation_id = correlation_id or str(uuid4())
        self.context_data = kwargs
        self.old_factory = None

    def __enter__(self):
        """Enter context and set up log record factory."""
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            record.correlation_id = self.correlation_id

            # Add context data
            for key, value in self.context_data.items():
                setattr(record, key, value)

            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore original factory."""
        logging.setLogRecordFactory(self.old_factory)


if __name__ == "__main__":
    # Example usage
    logging_service = CentralizedLoggingService()

    # Example structured logging
    with LoggingContext(user_id=123) as ctx:
        logging_service.log_structured(
            level=LogLevel.INFO,
            message="User logged in successfully",
            source=LogSource.AUTHENTICATION,
            user_id=123,
            extra_fields={"login_method": "oauth2"},
        )

    # Example API logging
    logging_service.log_api_request(
        method="POST",
        endpoint="/api/documents/upload",
        status_code=200,
        duration=1.2,
        user_id=123,
        request_size=1024000,
    )

    print("Centralized logging service demo completed")
