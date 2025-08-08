"""
Error Recovery and Resilience Utilities

This module provides comprehensive error recovery mechanisms including:
- Retry mechanisms with exponential backoff
- Circuit breaker pattern for external services
- Resource cleanup and transaction rollback utilities
- Error monitoring and recovery metrics
- Health checks and system recovery verification
"""

import asyncio
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
import threading
import weakref

logger = logging.getLogger(__name__)


class RecoveryError(Exception):
    """Base exception for recovery operations."""
    pass


class RetryExhaustedException(RecoveryError):
    """Raised when retry attempts are exhausted."""
    pass


class CircuitBreakerOpenError(RecoveryError):
    """Raised when circuit breaker is in open state."""
    pass


class CleanupError(RecoveryError):
    """Raised when cleanup operations fail."""
    pass


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests  
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)
    non_retryable_exceptions: tuple = (KeyboardInterrupt, SystemExit)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: Type[Exception] = Exception
    success_threshold: int = 2  # Successes needed to close in half-open


@dataclass 
class RecoveryMetrics:
    """Metrics for tracking recovery operations."""
    total_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    circuit_breaker_trips: int = 0
    cleanup_operations: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    error_types: Dict[str, int] = field(default_factory=dict)


class RetryMechanism:
    """Retry mechanism with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.metrics = RecoveryMetrics()
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator for retry functionality."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self._execute_with_retry(func, *args, **kwargs)
        return wrapper
        
    def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        delay = self.config.initial_delay
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.metrics.total_attempts += 1
                result = func(*args, **kwargs)
                
                if attempt > 1:  # Recovery after failure
                    self.metrics.successful_recoveries += 1
                    self.metrics.last_success_time = datetime.now()
                    logger.info(f"Function {func.__name__} succeeded after {attempt} attempts")
                    
                return result
                
            except self.config.non_retryable_exceptions:
                # Don't retry these exceptions
                raise
                
            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
                
                if not isinstance(e, self.config.retryable_exceptions):
                    logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                    raise
                    
                if attempt == self.config.max_attempts:
                    self.metrics.failed_recoveries += 1
                    self.metrics.last_failure_time = datetime.now()
                    break
                    
                logger.warning(
                    f"Attempt {attempt}/{self.config.max_attempts} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                # Apply jitter if enabled
                actual_delay = delay
                if self.config.jitter:
                    import random
                    actual_delay = delay * (0.5 + random.random() * 0.5)
                    
                time.sleep(actual_delay)
                
                # Calculate next delay with exponential backoff
                delay = min(delay * self.config.exponential_base, self.config.max_delay)
                
        # All retries exhausted
        raise RetryExhaustedException(
            f"Failed to execute {func.__name__} after {self.config.max_attempts} attempts. "
            f"Last error: {last_exception}"
        ) from last_exception


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.metrics = RecoveryMetrics()
        self._lock = threading.Lock()
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator for circuit breaker functionality."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self._execute_with_circuit_breaker(func, *args, **kwargs)
        return wrapper
        
    def _execute_with_circuit_breaker(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker for {func.__name__} transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN for {func.__name__}. "
                        f"Last failure: {self.last_failure_time}"
                    )
                    
        try:
            self.metrics.total_attempts += 1
            result = func(*args, **kwargs)
            
            with self._lock:
                self._record_success()
                
            return result
            
        except self.config.expected_exception as e:
            with self._lock:
                self._record_failure()
                
            error_type = type(e).__name__
            self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
            raise
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
            
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
        
    def _record_success(self) -> None:
        """Record a successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.metrics.successful_recoveries += 1
                self.metrics.last_success_time = datetime.now()
                logger.info("Circuit breaker transitioned to CLOSED")
        else:
            self.failure_count = 0  # Reset failure count on success
            
    def _record_failure(self) -> None:
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.metrics.last_failure_time = self.last_failure_time
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.metrics.circuit_breaker_trips += 1
            logger.warning("Circuit breaker tripped back to OPEN from HALF_OPEN")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.metrics.circuit_breaker_trips += 1
            logger.warning(f"Circuit breaker tripped to OPEN after {self.failure_count} failures")
            
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.state
        
    def force_open(self) -> None:
        """Force circuit breaker to open state."""
        with self._lock:
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = datetime.now()
            
    def force_close(self) -> None:
        """Force circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0


class ResourceCleanupManager:
    """Manages cleanup of resources with automatic tracking."""
    
    def __init__(self):
        self.cleanup_handlers: List[Callable] = []
        self.cleanup_paths: List[Path] = []
        self.metrics = RecoveryMetrics()
        self._lock = threading.Lock()
        
    @contextmanager
    def cleanup_scope(self, description: str = ""):
        """Context manager for automatic cleanup."""
        logger.debug(f"Entering cleanup scope: {description}")
        try:
            yield self
        except Exception as e:
            logger.error(f"Error in cleanup scope '{description}': {e}")
            raise
        finally:
            self.cleanup_all()
            
    def add_cleanup_handler(self, handler: Callable, *args, **kwargs) -> None:
        """Add a cleanup handler function."""
        with self._lock:
            self.cleanup_handlers.append(lambda: handler(*args, **kwargs))
            
    def add_cleanup_path(self, path: Union[str, Path]) -> None:
        """Add a path for cleanup."""
        with self._lock:
            self.cleanup_paths.append(Path(path))
            
    def cleanup_all(self) -> None:
        """Execute all cleanup handlers."""
        with self._lock:
            # Clean up paths first
            for path in self.cleanup_paths:
                try:
                    self._cleanup_path(path)
                    self.metrics.cleanup_operations += 1
                except Exception as e:
                    logger.error(f"Failed to cleanup path {path}: {e}")
                    self.metrics.failed_recoveries += 1
                    
            # Execute cleanup handlers
            for handler in self.cleanup_handlers:
                try:
                    handler()
                    self.metrics.cleanup_operations += 1
                except Exception as e:
                    logger.error(f"Cleanup handler failed: {e}")
                    self.metrics.failed_recoveries += 1
                    
            # Clear all handlers
            self.cleanup_handlers.clear()
            self.cleanup_paths.clear()
            
    def _cleanup_path(self, path: Path) -> None:
        """Clean up a specific path."""
        if not path.exists():
            return
            
        if path.is_file():
            path.unlink()
            logger.debug(f"Cleaned up file: {path}")
        elif path.is_dir():
            import shutil
            shutil.rmtree(path, ignore_errors=True)
            logger.debug(f"Cleaned up directory: {path}")


class TransactionManager:
    """Manages database transactions with automatic rollback."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.metrics = RecoveryMetrics()
        
    @contextmanager
    def transaction_scope(self, savepoint_name: Optional[str] = None):
        """Context manager for transactional operations with rollback."""
        try:
            with self.db.transaction(savepoint_name):
                self.metrics.total_attempts += 1
                yield
                self.metrics.successful_recoveries += 1
                self.metrics.last_success_time = datetime.now()
        except Exception as e:
            self.metrics.failed_recoveries += 1
            self.metrics.last_failure_time = datetime.now()
            error_type = type(e).__name__
            self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
            logger.error(f"Transaction failed and rolled back: {e}")
            raise


class HealthChecker:
    """Health checking and system recovery verification."""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.metrics = RecoveryMetrics()
        
    def add_health_check(self, name: str, check_func: Callable) -> None:
        """Add a health check function."""
        self.checks[name] = check_func
        
    def run_all_checks(self) -> Dict[str, bool]:
        """Run all health checks and return results."""
        results = {}
        for name, check_func in self.checks.items():
            try:
                self.metrics.total_attempts += 1
                result = check_func()
                results[name] = result
                if result:
                    self.metrics.successful_recoveries += 1
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = False
                self.metrics.failed_recoveries += 1
                error_type = type(e).__name__
                self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
                
        return results
        
    def is_healthy(self) -> bool:
        """Check if all health checks pass."""
        results = self.run_all_checks()
        return all(results.values())


class RecoveryOrchestrator:
    """Orchestrates complex recovery operations."""
    
    def __init__(self):
        self.retry = RetryMechanism(RetryConfig())
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self.cleanup_manager = ResourceCleanupManager()
        self.health_checker = HealthChecker()
        self.metrics = RecoveryMetrics()
        
    def with_recovery(
        self,
        operation: Callable,
        cleanup_paths: Optional[List[Union[str, Path]]] = None,
        cleanup_handlers: Optional[List[Callable]] = None,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ) -> Any:
        """Execute operation with full recovery support."""
        
        # Setup custom configurations if provided
        if retry_config:
            retry_mechanism = RetryMechanism(retry_config)
        else:
            retry_mechanism = self.retry
            
        if circuit_breaker_config:
            circuit_breaker = CircuitBreaker(circuit_breaker_config)
        else:
            circuit_breaker = self.circuit_breaker
            
        # Setup cleanup
        if cleanup_paths:
            for path in cleanup_paths:
                self.cleanup_manager.add_cleanup_path(path)
                
        if cleanup_handlers:
            for handler in cleanup_handlers:
                self.cleanup_manager.add_cleanup_handler(handler)
                
        try:
            # Combine retry and circuit breaker
            protected_operation = circuit_breaker(retry_mechanism(operation))
            result = protected_operation()
            
            self.metrics.successful_recoveries += 1
            self.metrics.last_success_time = datetime.now()
            return result
            
        except Exception as e:
            self.metrics.failed_recoveries += 1
            self.metrics.last_failure_time = datetime.now()
            error_type = type(e).__name__
            self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
            
            logger.error(f"Recovery operation failed: {e}")
            raise
        finally:
            # Always attempt cleanup
            self.cleanup_manager.cleanup_all()
            
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive recovery metrics."""
        return {
            "orchestrator": {
                "successful_recoveries": self.metrics.successful_recoveries,
                "failed_recoveries": self.metrics.failed_recoveries,
                "error_types": self.metrics.error_types,
                "last_success": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                "last_failure": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            },
            "retry": {
                "total_attempts": self.retry.metrics.total_attempts,
                "successful_recoveries": self.retry.metrics.successful_recoveries,
                "failed_recoveries": self.retry.metrics.failed_recoveries,
                "error_types": self.retry.metrics.error_types,
            },
            "circuit_breaker": {
                "state": self.circuit_breaker.get_state().value,
                "failure_count": self.circuit_breaker.failure_count,
                "trips": self.circuit_breaker.metrics.circuit_breaker_trips,
                "last_failure": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None,
            },
            "cleanup": {
                "operations": self.cleanup_manager.metrics.cleanup_operations,
                "failures": self.cleanup_manager.metrics.failed_recoveries,
            }
        }


# Convenience functions for common patterns
def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
):
    """Decorator for retry with common settings."""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        exponential_base=exponential_base,
        retryable_exceptions=retryable_exceptions
    )
    return RetryMechanism(config)


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """Decorator for circuit breaker with common settings."""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    return CircuitBreaker(config)