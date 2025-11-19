"""
OpenTelemetry Distributed Tracing Service
Production-ready distributed tracing implementation.
"""

import logging
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, Union

from opentelemetry import baggage, context, trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat, B3SingleFormat
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semantic_conventions.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode
from opentelemetry.util.http import get_excluded_urls

logger = logging.getLogger(__name__)


# ============================================================================
# Tracing Configuration
# ============================================================================


class TracingConfig:
    """OpenTelemetry tracing configuration."""

    def __init__(self) -> None:
        """Initialize tracing configuration from environment."""
        # Service configuration
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "ai-pdf-scholar")
        self.service_version = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
        self.environment = os.getenv("ENVIRONMENT", "development")

        # Exporter configuration
        self.exporter_type = os.getenv(
            "OTEL_EXPORTER_TYPE", "jaeger"
        )  # jaeger, zipkin, console
        self.jaeger_endpoint = os.getenv(
            "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
        )
        self.zipkin_endpoint = os.getenv(
            "ZIPKIN_ENDPOINT", "http://localhost:9411/api/v2/spans"
        )

        # Sampling configuration
        self.sample_rate = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))  # 100% sampling

        # Propagation
        self.propagators = os.getenv("OTEL_PROPAGATORS", "b3multi,jaeger").split(",")

        # Instrumentation configuration
        self.auto_instrument_requests = (
            os.getenv("OTEL_INSTRUMENT_REQUESTS", "true").lower() == "true"
        )
        self.auto_instrument_database = (
            os.getenv("OTEL_INSTRUMENT_DATABASE", "true").lower() == "true"
        )
        self.auto_instrument_cache = (
            os.getenv("OTEL_INSTRUMENT_CACHE", "true").lower() == "true"
        )

        # Excluded URLs (health checks, metrics, etc.)
        self.excluded_urls = os.getenv(
            "OTEL_EXCLUDED_URLS", "/health,/metrics,/favicon.ico"
        ).split(",")


# ============================================================================
# Tracing Service
# ============================================================================


class TracingService:
    """
    Comprehensive OpenTelemetry tracing service.
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        """Initialize tracing service."""
        self.config = config or TracingConfig()
        self.tracer_provider = None
        self.tracer = None

        # Initialize tracing
        self._setup_tracing()

        logger.info(f"Tracing service initialized for {self.config.service_name}")

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        # Create resource
        resource = Resource.create(
            {
                SERVICE_NAME: self.config.service_name,
                SERVICE_VERSION: self.config.service_version,
                "environment": self.config.environment,
                "host.name": os.getenv("HOSTNAME", "localhost"),
            }
        )

        # Create tracer provider
        self.tracer_provider = TracerProvider(
            resource=resource, sampler=self._create_sampler()
        )

        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

        # Get tracer
        self.tracer = trace.get_tracer(__name__, self.config.service_version)

        # Setup exporters
        self._setup_exporters()

        # Setup propagators
        self._setup_propagators()

        # Setup auto-instrumentation
        self._setup_auto_instrumentation()

    def _create_sampler(self) -> Any:
        """Create trace sampler."""
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        return TraceIdRatioBased(self.config.sample_rate)

    def _setup_exporters(self) -> None:
        """Setup trace exporters."""
        processors = []

        if self.config.exporter_type == "jaeger":
            jaeger_exporter = JaegerExporter(endpoint=self.config.jaeger_endpoint)
            processors.append(BatchSpanProcessor(jaeger_exporter))

        elif self.config.exporter_type == "zipkin":
            zipkin_exporter = ZipkinExporter(endpoint=self.config.zipkin_endpoint)
            processors.append(BatchSpanProcessor(zipkin_exporter))

        elif self.config.exporter_type == "console":
            console_exporter = ConsoleSpanExporter()
            processors.append(BatchSpanProcessor(console_exporter))

        # Add processors to tracer provider
        for processor in processors:
            self.tracer_provider.add_span_processor(processor)

    def _setup_propagators(self) -> None:
        """Setup trace propagators."""
        propagators = []

        for prop_name in self.config.propagators:
            if prop_name == "b3multi":
                propagators.append(B3MultiFormat())
            elif prop_name == "b3single":
                propagators.append(B3SingleFormat())
            elif prop_name == "jaeger":
                propagators.append(JaegerPropagator())

        if propagators:
            composite_propagator = CompositePropagator(propagators)
            set_global_textmap(composite_propagator)

    def _setup_auto_instrumentation(self) -> None:
        """Setup automatic instrumentation."""
        # HTTP requests instrumentation
        if self.config.auto_instrument_requests:
            RequestsInstrumentor().instrument()

        # Database instrumentation
        if self.config.auto_instrument_database:
            Psycopg2Instrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()

        # Redis instrumentation
        if self.config.auto_instrument_cache:
            RedisInstrumentor().instrument()

    # ========================================================================
    # Core Tracing Methods
    # ========================================================================

    def start_span(
        self,
        name: str,
        kind: trace.SpanKind | None = None,
        attributes: dict[str, Any] | None = None,
        parent: Union[trace.Span, trace.SpanContext] | None = None,
    ) -> trace.Span:
        """
        Start a new span.

        Args:
            name: Span name
            kind: Span kind
            attributes: Initial attributes
            parent: Parent span or context

        Returns:
            New span
        """
        span = self.tracer.start_span(
            name=name,
            kind=kind,
            attributes=attributes,
            context=trace.set_span_in_context(parent) if parent else None,
        )

        return span

    @contextmanager
    def trace(
        self,
        name: str,
        kind: trace.SpanKind | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """
        Context manager for tracing operations.

        Args:
            name: Span name
            kind: Span kind
            attributes: Initial attributes

        Example:
            with tracing.trace("document_processing"):
                process_document(doc)
        """
        span = self.start_span(name, kind, attributes)

        try:
            with trace.use_span(span, end_on_exit=True):
                yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise

    def trace_decorator(
        self,
        name: str | None = None,
        kind: trace.SpanKind | None = None,
        attributes: dict[str, Any] | None = None,
        record_exception: bool = True,
    ) -> Any:
        """
        Decorator for automatic tracing.

        Args:
            name: Span name (defaults to function name)
            kind: Span kind
            attributes: Initial attributes
            record_exception: Whether to record exceptions

        Example:
            @tracing.trace_decorator(name="process_document")
            def process_document(doc):
                ...
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            span_name = name or f"{func.__module__}.{func.__name__}"

            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                with self.trace(span_name, kind, attributes) as span:
                    # Add function attributes
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    if args:
                        span.set_attribute("function.args.count", len(args))

                    if kwargs:
                        span.set_attribute("function.kwargs.count", len(kwargs))
                        # Add non-sensitive kwargs
                        for k, v in kwargs.items():
                            if not self._is_sensitive_key(k):
                                span.set_attribute(f"function.kwargs.{k}", str(v)[:100])

                    try:
                        result = func(*args, **kwargs)
                        span.set_attribute(
                            "function.result.type", type(result).__name__
                        )
                        return result
                    except Exception as e:
                        if record_exception:
                            span.record_exception(e)
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise

            # Add async support
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                with self.trace(span_name, kind, attributes) as span:
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    span.set_attribute("function.async", True)

                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute(
                            "function.result.type", type(result).__name__
                        )
                        return result
                    except Exception as e:
                        if record_exception:
                            span.record_exception(e)
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise

            # Return appropriate wrapper based on function type
            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return wrapper

        return decorator

    # ========================================================================
    # Application-Specific Tracing
    # ========================================================================

    def trace_http_request(
        self,
        method: str,
        url: str,
        status_code: int | None = None,
        user_id: str | None = None,
        request_size: int | None = None,
        response_size: int | None = None,
    ) -> None:
        """Trace HTTP request with standard attributes."""
        span = trace.get_current_span()

        if span:
            span.set_attribute(SpanAttributes.HTTP_METHOD, method)
            span.set_attribute(SpanAttributes.HTTP_URL, url)

            if status_code:
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)

                if status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))

            if user_id:
                span.set_attribute("user.id", user_id)

            if request_size:
                span.set_attribute("http.request.size", request_size)

            if response_size:
                span.set_attribute("http.response.size", response_size)

    def trace_database_query(
        self,
        operation: str,
        table: str,
        query: str | None = None,
        rows_affected: int | None = None,
        duration: float | None = None,
    ) -> None:
        """Trace database query with standard attributes."""
        span = trace.get_current_span()

        if span:
            span.set_attribute(SpanAttributes.DB_OPERATION, operation)
            span.set_attribute(SpanAttributes.DB_SQL_TABLE, table)

            if query:
                # Only log first 200 characters of query
                span.set_attribute(SpanAttributes.DB_STATEMENT, query[:200])

            if rows_affected is not None:
                span.set_attribute("db.rows_affected", rows_affected)

            if duration is not None:
                span.set_attribute("db.duration", duration)

    def trace_document_processing(
        self,
        document_id: str,
        operation: str,
        file_type: str | None = None,
        file_size: int | None = None,
        page_count: int | None = None,
    ) -> None:
        """Trace document processing operations."""
        span = trace.get_current_span()

        if span:
            span.set_attribute("document.id", document_id)
            span.set_attribute("document.operation", operation)

            if file_type:
                span.set_attribute("document.type", file_type)

            if file_size:
                span.set_attribute("document.size", file_size)

            if page_count:
                span.set_attribute("document.pages", page_count)

    def trace_rag_query(
        self,
        query: str,
        document_id: str | None = None,
        retrieval_count: int | None = None,
        relevance_scores: list[float] | None = None,
        model_used: str | None = None,
    ) -> None:
        """Trace RAG (Retrieval-Augmented Generation) queries."""
        span = trace.get_current_span()

        if span:
            # Hash query for privacy
            import hashlib

            query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
            span.set_attribute("rag.query_hash", query_hash)
            span.set_attribute("rag.query_length", len(query))

            if document_id:
                span.set_attribute("rag.document_id", document_id)

            if retrieval_count:
                span.set_attribute("rag.retrieval_count", retrieval_count)

            if relevance_scores:
                span.set_attribute("rag.max_relevance", max(relevance_scores))
                span.set_attribute(
                    "rag.avg_relevance", sum(relevance_scores) / len(relevance_scores)
                )

            if model_used:
                span.set_attribute("rag.model", model_used)

    def trace_cache_operation(
        self,
        operation: str,
        key: str,
        hit: bool | None = None,
        size: int | None = None,
        ttl: int | None = None,
    ) -> None:
        """Trace cache operations."""
        span = trace.get_current_span()

        if span:
            # Hash key for privacy
            import hashlib

            key_hash = hashlib.sha256(key.encode()).hexdigest()[:8]
            span.set_attribute("cache.key_hash", key_hash)
            span.set_attribute("cache.operation", operation)

            if hit is not None:
                span.set_attribute("cache.hit", hit)

            if size is not None:
                span.set_attribute("cache.size", size)

            if ttl is not None:
                span.set_attribute("cache.ttl", ttl)

    # ========================================================================
    # Baggage Management
    # ========================================================================

    def set_baggage(self, key: str, value: str) -> None:
        """Set baggage that propagates across service boundaries."""
        ctx = baggage.set_baggage(key, value)
        context.attach(ctx)

    def get_baggage(self, key: str) -> str | None:
        """Get baggage value."""
        return baggage.get_baggage(key)

    def clear_baggage(self, key: str) -> None:
        """Clear specific baggage key."""
        ctx = baggage.clear_baggage(key)
        context.attach(ctx)

    # ========================================================================
    # Correlation and Context
    # ========================================================================

    def get_trace_id(self) -> str | None:
        """Get current trace ID."""
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return f"{span.get_span_context().trace_id:032x}"
        return None

    def get_span_id(self) -> str | None:
        """Get current span ID."""
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return f"{span.get_span_context().span_id:016x}"
        return None

    def inject_trace_context(self, headers: dict[str, str]) -> dict[str, str]:
        """Inject trace context into HTTP headers."""
        from opentelemetry.propagate import inject

        inject(headers)
        return headers

    def extract_trace_context(self, headers: dict[str, str]) -> Any:
        """Extract trace context from HTTP headers."""
        from opentelemetry.propagate import extract

        return extract(headers)

    # ========================================================================
    # Custom Events and Logs
    # ========================================================================

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the current span."""
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes or {})

    def log_error(
        self, error: Exception, attributes: dict[str, Any] | None = None
    ) -> None:
        """Log an error to the current span."""
        span = trace.get_current_span()
        if span:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))

            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

    def set_user_context(
        self, user_id: str, user_email: str | None = None, user_role: str | None = None
    ) -> None:
        """Set user context in current span."""
        span = trace.get_current_span()
        if span:
            span.set_attribute("user.id", user_id)
            if user_email:
                span.set_attribute("user.email", user_email)
            if user_role:
                span.set_attribute("user.role", user_role)

    # ========================================================================
    # Performance Monitoring
    # ========================================================================

    def measure_performance(self, operation: str) -> Any:
        """Context manager to measure operation performance."""

        @contextmanager
        def performance_context() -> None:
            start_time = time.time()

            with self.trace(f"perf.{operation}") as span:
                yield span

                duration = time.time() - start_time
                span.set_attribute("performance.duration", duration)

                # Add performance warnings
                if duration > 5.0:  # > 5 seconds
                    span.add_event(
                        "performance.slow_operation",
                        {"threshold": "5s", "actual_duration": duration},
                    )
                elif duration > 1.0:  # > 1 second
                    span.add_event(
                        "performance.moderate_duration", {"actual_duration": duration}
                    )

        return performance_context()

    # ========================================================================
    # FastAPI Integration
    # ========================================================================

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application."""
        # Set excluded URLs
        excluded_urls = get_excluded_urls("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS")

        # Add custom excluded URLs
        for url in self.config.excluded_urls:
            excluded_urls.add(url.strip())

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(
            app, excluded_urls=excluded_urls, tracer_provider=self.tracer_provider
        )

        logger.info("FastAPI instrumentation enabled")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive information."""
        sensitive_keys = [
            "password",
            "token",
            "secret",
            "key",
            "auth",
            "credential",
            "private",
            "confidential",
        ]
        return any(sensitive in key.lower() for sensitive in sensitive_keys)

    def close(self) -> None:
        """Close tracing service and flush remaining spans."""
        if self.tracer_provider:
            # Shutdown span processors
            for (
                processor
            ) in self.tracer_provider._active_span_processor._span_processors:
                processor.shutdown()

        logger.info("Tracing service closed")


# ============================================================================
# Global Tracing Instance
# ============================================================================

# Global tracing service instance
_tracing_service: TracingService | None = None


def get_tracer() -> TracingService:
    """Get global tracing service instance."""
    global _tracing_service

    if _tracing_service is None:
        _tracing_service = TracingService()

    return _tracing_service


def initialize_tracing(config: TracingConfig | None = None) -> TracingService:
    """Initialize global tracing service."""
    global _tracing_service
    _tracing_service = TracingService(config)
    return _tracing_service


if __name__ == "__main__":
    # Example usage
    tracing = TracingService()

    # Manual tracing
    with tracing.trace("example_operation") as span:
        span.set_attribute("example.key", "value")
        time.sleep(0.1)
        tracing.add_event("processing_complete")

    # Decorator tracing
    @tracing.trace_decorator(name="example_function")
    def example_function(x: int, y: int) -> int:
        return x + y

    result = example_function(1, 2)
    print(f"Result: {result}")
    print(f"Trace ID: {tracing.get_trace_id()}")

    tracing.close()
