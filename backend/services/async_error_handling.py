"""
Async Error Handling and Recovery
Comprehensive error handling, recovery strategies, and resilience patterns for async RAG operations.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors for specific handling strategies."""
    NETWORK = "network"
    MEMORY = "memory"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"
    USER_INPUT = "user_input"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CIRCUIT_BREAKER = "circuit_breaker"
    BACKOFF = "backoff"
    ESCALATION = "escalation"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    error: Exception
    category: ErrorCategory
    severity: ErrorSeverity
    task_id: str | None = None
    client_id: str | None = None
    operation: str | None = None
    attempt_count: int = 1
    first_occurrence: datetime = field(default_factory=datetime.now)
    last_occurrence: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_occurrence(self):
        """Update last occurrence timestamp."""
        self.last_occurrence = datetime.now()
        self.attempt_count += 1


@dataclass
class RecoveryConfig:
    """Configuration for recovery strategies."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    timeout_seconds: float | None = None
    fallback_handler: Callable | None = None
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 300.0


class AsyncCircuitBreaker:
    """Circuit breaker pattern for preventing cascade failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
        expected_exception: type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    async def __aenter__(self):
        """Enter circuit breaker context."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open. Last failure: {self.last_failure_time}"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit circuit breaker context."""
        if exc_type is None:
            # Success
            self._on_success()
        elif issubclass(exc_type, self.expected_exception):
            # Expected failure
            self._on_failure()

        return False  # Don't suppress exceptions

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is in open state."""
    pass


class AsyncErrorHandler:
    """Comprehensive async error handling with recovery strategies."""

    def __init__(self):
        self.error_history: dict[str, list[ErrorContext]] = {}
        self.circuit_breakers: dict[str, AsyncCircuitBreaker] = {}
        self.recovery_configs: dict[ErrorCategory, RecoveryConfig] = {
            ErrorCategory.NETWORK: RecoveryConfig(max_retries=3, base_delay=1.0),
            ErrorCategory.MEMORY: RecoveryConfig(max_retries=1, base_delay=2.0),
            ErrorCategory.TIMEOUT: RecoveryConfig(max_retries=2, base_delay=0.5),
            ErrorCategory.VALIDATION: RecoveryConfig(max_retries=0),  # Don't retry validation errors
            ErrorCategory.EXTERNAL_SERVICE: RecoveryConfig(max_retries=3, base_delay=2.0, max_delay=30.0),
            ErrorCategory.SYSTEM: RecoveryConfig(max_retries=1, base_delay=1.0),
            ErrorCategory.USER_INPUT: RecoveryConfig(max_retries=0),  # Don't retry user input errors
            ErrorCategory.RESOURCE_EXHAUSTION: RecoveryConfig(max_retries=2, base_delay=5.0, max_delay=120.0),
        }

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message."""
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Network-related errors
        if any(keyword in error_str for keyword in ['connection', 'network', 'timeout', 'unreachable']):
            return ErrorCategory.NETWORK

        # Memory-related errors
        if 'memory' in error_str or error_type in ['MemoryError', 'OutOfMemoryError']:
            return ErrorCategory.MEMORY

        # Timeout errors
        if 'timeout' in error_str or error_type in ['TimeoutError', 'asyncio.TimeoutError']:
            return ErrorCategory.TIMEOUT

        # Validation errors
        if any(keyword in error_str for keyword in ['validation', 'invalid', 'not found', 'permission']):
            return ErrorCategory.VALIDATION

        # External service errors
        if any(keyword in error_str for keyword in ['api', 'service', 'gemini', 'llama']):
            return ErrorCategory.EXTERNAL_SERVICE

        # Resource exhaustion
        if any(keyword in error_str for keyword in ['exhausted', 'limit', 'quota', 'capacity']):
            return ErrorCategory.RESOURCE_EXHAUSTION

        # System errors
        if error_type in ['SystemError', 'OSError', 'IOError']:
            return ErrorCategory.SYSTEM

        # Default to system error
        return ErrorCategory.SYSTEM

    def determine_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity based on category and error details."""
        error_str = str(error).lower()

        # Critical errors
        if category == ErrorCategory.MEMORY or 'critical' in error_str:
            return ErrorSeverity.CRITICAL

        # High severity errors
        if category in [ErrorCategory.SYSTEM, ErrorCategory.RESOURCE_EXHAUSTION]:
            return ErrorSeverity.HIGH

        # Medium severity errors
        if category in [ErrorCategory.EXTERNAL_SERVICE, ErrorCategory.NETWORK]:
            return ErrorSeverity.MEDIUM

        # Low severity errors
        return ErrorSeverity.LOW

    async def handle_error(
        self,
        error: Exception,
        operation: str,
        task_id: str | None = None,
        client_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> ErrorContext:
        """Handle an error with appropriate categorization and logging."""

        category = self.categorize_error(error)
        severity = self.determine_severity(error, category)

        error_context = ErrorContext(
            error=error,
            category=category,
            severity=severity,
            task_id=task_id,
            client_id=client_id,
            operation=operation,
            metadata=metadata or {}
        )

        # Store error in history
        operation_key = f"{operation}:{category.value}"
        if operation_key not in self.error_history:
            self.error_history[operation_key] = []
        self.error_history[operation_key].append(error_context)

        # Log error with appropriate level
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }[severity]

        logger.log(
            log_level,
            f"Error in {operation} (Task: {task_id}, Category: {category.value}, Severity: {severity.value}): {error}"
        )

        return error_context

    @asynccontextmanager
    async def with_retry(
        self,
        operation: str,
        config: RecoveryConfig | None = None,
        task_id: str | None = None,
        client_id: str | None = None
    ):
        """Context manager for retry logic with exponential backoff."""

        attempt = 0
        last_error = None

        while attempt <= (config.max_retries if config else 3):
            try:
                yield attempt
                return  # Success

            except Exception as error:
                last_error = error
                attempt += 1

                # Handle error
                error_context = await self.handle_error(
                    error, operation, task_id, client_id,
                    metadata={"attempt": attempt}
                )

                # Check if we should retry
                if not config:
                    config = self.recovery_configs.get(
                        error_context.category,
                        RecoveryConfig()
                    )

                if attempt > config.max_retries:
                    logger.error(f"Max retries ({config.max_retries}) exceeded for {operation}")
                    break

                # Don't retry certain error categories
                if error_context.category in [ErrorCategory.VALIDATION, ErrorCategory.USER_INPUT]:
                    logger.info(f"Not retrying {error_context.category.value} error for {operation}")
                    break

                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.backoff_multiplier ** (attempt - 1)),
                    config.max_delay
                )

                # Add jitter if enabled
                if config.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)

                logger.info(f"Retrying {operation} in {delay:.2f}s (attempt {attempt}/{config.max_retries})")
                await asyncio.sleep(delay)

        # All retries failed
        if last_error:
            raise last_error

    async def with_circuit_breaker(
        self,
        operation: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0
    ) -> AsyncCircuitBreaker:
        """Get or create circuit breaker for an operation."""

        if operation not in self.circuit_breakers:
            self.circuit_breakers[operation] = AsyncCircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )

        return self.circuit_breakers[operation]

    async def with_timeout(
        self,
        operation: Callable,
        timeout_seconds: float,
        operation_name: str = "async_operation"
    ) -> Any:
        """Execute operation with timeout handling."""

        try:
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            await self.handle_error(
                e, operation_name,
                metadata={"timeout_seconds": timeout_seconds}
            )
            raise

    def get_error_statistics(self) -> dict[str, Any]:
        """Get comprehensive error statistics."""

        total_errors = sum(len(errors) for errors in self.error_history.values())

        # Category breakdown
        category_stats = {}
        severity_stats = {}

        for operation_key, errors in self.error_history.items():
            for error_context in errors:
                category = error_context.category.value
                severity = error_context.severity.value

                category_stats[category] = category_stats.get(category, 0) + 1
                severity_stats[severity] = severity_stats.get(severity, 0) + 1

        # Circuit breaker status
        circuit_breaker_stats = {
            operation: {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "last_failure": cb.last_failure_time
            }
            for operation, cb in self.circuit_breakers.items()
        }

        # Recent errors (last hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_errors = []

        for operation_key, errors in self.error_history.items():
            for error_context in errors:
                if error_context.last_occurrence >= cutoff_time:
                    recent_errors.append({
                        "operation": operation_key,
                        "category": error_context.category.value,
                        "severity": error_context.severity.value,
                        "attempt_count": error_context.attempt_count,
                        "last_occurrence": error_context.last_occurrence.isoformat(),
                        "error_message": str(error_context.error)[:200]  # Truncate long messages
                    })

        return {
            "total_errors": total_errors,
            "category_breakdown": category_stats,
            "severity_breakdown": severity_stats,
            "circuit_breaker_status": circuit_breaker_stats,
            "recent_errors": recent_errors[:20],  # Last 20 recent errors
            "error_operations": list(self.error_history.keys())
        }

    async def clear_error_history(self, older_than_hours: int = 24):
        """Clear old error history to prevent memory buildup."""

        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        cleared_count = 0

        for operation_key in list(self.error_history.keys()):
            errors = self.error_history[operation_key]
            self.error_history[operation_key] = [
                error for error in errors
                if error.last_occurrence >= cutoff_time
            ]

            cleared_count += len(errors) - len(self.error_history[operation_key])

            # Remove empty lists
            if not self.error_history[operation_key]:
                del self.error_history[operation_key]

        logger.info(f"Cleared {cleared_count} old error records")
        return cleared_count


# Decorator for automatic error handling
def with_async_error_handling(
    operation_name: str = None,
    max_retries: int = 3,
    circuit_breaker: bool = False,
    timeout_seconds: float | None = None
):
    """Decorator for automatic async error handling."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal operation_name
            if operation_name is None:
                operation_name = f"{func.__module__}.{func.__name__}"

            handler = AsyncErrorHandler()

            # Apply circuit breaker if requested
            if circuit_breaker:
                circuit_breaker_context = await handler.with_circuit_breaker(operation_name)
                async with circuit_breaker_context:
                    # Apply timeout if specified
                    if timeout_seconds:
                        return await handler.with_timeout(
                            lambda: func(*args, **kwargs),
                            timeout_seconds,
                            operation_name
                        )
                    else:
                        return await func(*args, **kwargs)
            else:
                # Apply retry logic
                config = RecoveryConfig(max_retries=max_retries)
                async with handler.with_retry(operation_name, config):
                    # Apply timeout if specified
                    if timeout_seconds:
                        return await handler.with_timeout(
                            lambda: func(*args, **kwargs),
                            timeout_seconds,
                            operation_name
                        )
                    else:
                        return await func(*args, **kwargs)

        return wrapper
    return decorator


# Global error handler instance
_error_handler: AsyncErrorHandler | None = None


def get_error_handler() -> AsyncErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = AsyncErrorHandler()
    return _error_handler
