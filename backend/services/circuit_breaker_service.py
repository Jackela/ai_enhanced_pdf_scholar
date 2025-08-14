"""
Circuit Breaker Service
Production-ready circuit breaker pattern implementation for external services.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, Generic
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Circuit Breaker States and Models
# ============================================================================

class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Circuit is open, requests fail fast
    HALF_OPEN = "half_open" # Testing if service has recovered


class FailureType(str, Enum):
    """Types of failures that can trigger circuit breaker."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    SERVICE_ERROR = "service_error"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Number of failures to open circuit
    recovery_timeout: float = 60.0      # Seconds before trying half-open
    expected_recovery_time: float = 30.0 # Expected time for service recovery
    success_threshold: int = 3           # Successful calls to close circuit from half-open
    timeout: float = 30.0               # Request timeout in seconds

    # Advanced configuration
    sliding_window_size: int = 10       # Size of sliding window for failure rate
    minimum_throughput: int = 3         # Minimum calls before evaluating failure rate
    failure_rate_threshold: float = 50.0 # Failure rate percentage to open circuit
    slow_call_duration_threshold: float = 5.0  # Slow call threshold
    slow_call_rate_threshold: float = 30.0     # Slow call rate percentage

    # Exponential backoff
    enable_exponential_backoff: bool = True
    backoff_multiplier: float = 2.0
    max_backoff_time: float = 300.0     # Maximum backoff time (5 minutes)


@dataclass
class CallResult:
    """Result of a circuit breaker protected call."""
    success: bool
    duration: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    failure_type: Optional[FailureType] = None
    error: Optional[str] = None
    response_data: Optional[Any] = None


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    name: str
    state: CircuitBreakerState
    failure_count: int
    success_count: int
    total_calls: int
    failure_rate: float
    slow_call_rate: float
    last_state_change: datetime
    next_retry_time: Optional[datetime]
    recent_calls: List[CallResult] = field(default_factory=list)


# ============================================================================
# Exceptions
# ============================================================================

class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, retry_after: float):
        self.circuit_name = circuit_name
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker '{circuit_name}' is open. Retry after {retry_after:.1f}s")


# ============================================================================
# Circuit Breaker Implementation
# ============================================================================

class CircuitBreaker(Generic[T]):
    """
    Production-ready circuit breaker implementation with advanced features.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitBreakerState, CircuitBreakerState], None]] = None
    ):
        """Initialize circuit breaker."""
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change

        # State management
        self._state = CircuitBreakerState.CLOSED
        self._last_state_change = datetime.utcnow()
        self._next_retry_time: Optional[datetime] = None
        self._lock = Lock()

        # Counters and metrics
        self._failure_count = 0
        self._success_count = 0
        self._consecutive_successes = 0
        self._recent_calls: List[CallResult] = []
        self._backoff_count = 0

        logger.info(f"Circuit breaker '{name}' initialized")

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        with self._lock:
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitBreakerState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitBreakerState.HALF_OPEN

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from the protected function
        """
        # Check if we can make the call
        if not self._can_execute():
            raise CircuitBreakerOpenError(
                self.name,
                self._get_retry_after_seconds()
            )

        # Execute the protected function
        start_time = time.time()
        result = None
        error = None

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # Record successful call
            call_result = CallResult(
                success=True,
                duration=duration,
                response_data=result
            )
            self._record_call(call_result)

            return result

        except Exception as e:
            duration = time.time() - start_time
            failure_type = self._classify_failure(e)

            # Record failed call
            call_result = CallResult(
                success=False,
                duration=duration,
                failure_type=failure_type,
                error=str(e)
            )
            self._record_call(call_result)

            raise

    async def async_call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from the protected function
        """
        # Check if we can make the call
        if not self._can_execute():
            raise CircuitBreakerOpenError(
                self.name,
                self._get_retry_after_seconds()
            )

        # Execute the protected function with timeout
        start_time = time.time()
        result = None
        error = None

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            duration = time.time() - start_time

            # Record successful call
            call_result = CallResult(
                success=True,
                duration=duration,
                response_data=result
            )
            self._record_call(call_result)

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time

            # Record timeout
            call_result = CallResult(
                success=False,
                duration=duration,
                failure_type=FailureType.TIMEOUT,
                error="Request timeout"
            )
            self._record_call(call_result)

            raise

        except Exception as e:
            duration = time.time() - start_time
            failure_type = self._classify_failure(e)

            # Record failed call
            call_result = CallResult(
                success=False,
                duration=duration,
                failure_type=failure_type,
                error=str(e)
            )
            self._record_call(call_result)

            raise

    def _can_execute(self) -> bool:
        """Check if we can execute a call based on current state."""
        with self._lock:
            now = datetime.utcnow()

            if self._state == CircuitBreakerState.CLOSED:
                return True

            elif self._state == CircuitBreakerState.OPEN:
                # Check if we should transition to half-open
                if self._next_retry_time and now >= self._next_retry_time:
                    self._transition_to_half_open()
                    return True
                return False

            elif self._state == CircuitBreakerState.HALF_OPEN:
                return True

            return False

    def _record_call(self, call_result: CallResult):
        """Record the result of a call and update state accordingly."""
        with self._lock:
            # Add to recent calls
            self._recent_calls.append(call_result)

            # Maintain sliding window
            if len(self._recent_calls) > self.config.sliding_window_size:
                self._recent_calls.pop(0)

            # Update counters
            if call_result.success:
                self._success_count += 1
                self._consecutive_successes += 1

                # If we're half-open and have enough consecutive successes, close circuit
                if (self._state == CircuitBreakerState.HALF_OPEN and
                    self._consecutive_successes >= self.config.success_threshold):
                    self._transition_to_closed()
            else:
                self._failure_count += 1
                self._consecutive_successes = 0

                # Check if we should open the circuit
                self._check_failure_threshold()

    def _check_failure_threshold(self):
        """Check if we should open the circuit based on failure rates."""
        if len(self._recent_calls) < self.config.minimum_throughput:
            return

        # Calculate failure rate
        failures = sum(1 for call in self._recent_calls if not call.success)
        failure_rate = (failures / len(self._recent_calls)) * 100

        # Calculate slow call rate
        slow_calls = sum(
            1 for call in self._recent_calls
            if call.duration > self.config.slow_call_duration_threshold
        )
        slow_call_rate = (slow_calls / len(self._recent_calls)) * 100

        # Open circuit if thresholds exceeded
        should_open = (
            failure_rate >= self.config.failure_rate_threshold or
            slow_call_rate >= self.config.slow_call_rate_threshold or
            self._failure_count >= self.config.failure_threshold
        )

        if should_open and self._state != CircuitBreakerState.OPEN:
            self._transition_to_open()

    def _transition_to_open(self):
        """Transition circuit breaker to open state."""
        old_state = self._state
        self._state = CircuitBreakerState.OPEN
        self._last_state_change = datetime.utcnow()

        # Calculate next retry time with exponential backoff
        if self.config.enable_exponential_backoff:
            backoff_time = min(
                self.config.recovery_timeout * (self.config.backoff_multiplier ** self._backoff_count),
                self.config.max_backoff_time
            )
            self._backoff_count += 1
        else:
            backoff_time = self.config.recovery_timeout

        self._next_retry_time = datetime.utcnow() + timedelta(seconds=backoff_time)

        logger.warning(f"Circuit breaker '{self.name}' opened. Retry after {backoff_time:.1f}s")

        if self.on_state_change:
            self.on_state_change(old_state, self._state)

    def _transition_to_half_open(self):
        """Transition circuit breaker to half-open state."""
        old_state = self._state
        self._state = CircuitBreakerState.HALF_OPEN
        self._last_state_change = datetime.utcnow()
        self._consecutive_successes = 0

        logger.info(f"Circuit breaker '{self.name}' transitioned to half-open")

        if self.on_state_change:
            self.on_state_change(old_state, self._state)

    def _transition_to_closed(self):
        """Transition circuit breaker to closed state."""
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._last_state_change = datetime.utcnow()
        self._failure_count = 0
        self._consecutive_successes = 0
        self._backoff_count = 0  # Reset backoff
        self._next_retry_time = None

        logger.info(f"Circuit breaker '{self.name}' closed")

        if self.on_state_change:
            self.on_state_change(old_state, self._state)

    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify the type of failure based on exception."""
        exception_name = type(exception).__name__.lower()

        if "timeout" in exception_name or isinstance(exception, asyncio.TimeoutError):
            return FailureType.TIMEOUT
        elif "connection" in exception_name:
            return FailureType.CONNECTION_ERROR
        elif "http" in exception_name:
            return FailureType.HTTP_ERROR
        elif "rate" in exception_name or "limit" in exception_name:
            return FailureType.RATE_LIMIT
        else:
            return FailureType.UNKNOWN

    def _get_retry_after_seconds(self) -> float:
        """Get seconds until next retry attempt."""
        if not self._next_retry_time:
            return 0.0

        now = datetime.utcnow()
        if now >= self._next_retry_time:
            return 0.0

        return (self._next_retry_time - now).total_seconds()

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        with self._lock:
            total_calls = len(self._recent_calls)
            failures = sum(1 for call in self._recent_calls if not call.success)
            slow_calls = sum(
                1 for call in self._recent_calls
                if call.duration > self.config.slow_call_duration_threshold
            )

            failure_rate = (failures / total_calls * 100) if total_calls > 0 else 0
            slow_call_rate = (slow_calls / total_calls * 100) if total_calls > 0 else 0

            return CircuitBreakerStats(
                name=self.name,
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_calls=self._failure_count + self._success_count,
                failure_rate=failure_rate,
                slow_call_rate=slow_call_rate,
                last_state_change=self._last_state_change,
                next_retry_time=self._next_retry_time,
                recent_calls=self._recent_calls.copy()
            )

    def reset(self):
        """Reset circuit breaker to initial state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitBreakerState.CLOSED
            self._last_state_change = datetime.utcnow()
            self._failure_count = 0
            self._success_count = 0
            self._consecutive_successes = 0
            self._recent_calls.clear()
            self._backoff_count = 0
            self._next_retry_time = None

            logger.info(f"Circuit breaker '{self.name}' reset")

            if self.on_state_change and old_state != self._state:
                self.on_state_change(old_state, self._state)


# ============================================================================
# Circuit Breaker Manager
# ============================================================================

class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers.
    """

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
        self._lock = Lock()

        logger.info("Circuit breaker manager initialized")

    def get_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Circuit breaker name
            config: Configuration (uses default if not provided)

        Returns:
            Circuit breaker instance
        """
        with self._lock:
            if name not in self._circuit_breakers:
                circuit_config = config or self._default_config
                self._circuit_breakers[name] = CircuitBreaker(
                    name=name,
                    config=circuit_config,
                    on_state_change=self._on_state_change
                )

            return self._circuit_breakers[name]

    def _on_state_change(self, old_state: CircuitBreakerState, new_state: CircuitBreakerState):
        """Handle circuit breaker state changes."""
        # This could be used for alerting, metrics, etc.
        pass

    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {
                name: cb.get_stats()
                for name, cb in self._circuit_breakers.items()
            }

    def reset_circuit_breaker(self, name: str):
        """Reset a specific circuit breaker."""
        with self._lock:
            if name in self._circuit_breakers:
                self._circuit_breakers[name].reset()

    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()

    def remove_circuit_breaker(self, name: str):
        """Remove a circuit breaker."""
        with self._lock:
            if name in self._circuit_breakers:
                del self._circuit_breakers[name]
                logger.info(f"Removed circuit breaker '{name}'")


# ============================================================================
# Decorators
# ============================================================================

# Global circuit breaker manager
_global_manager = CircuitBreakerManager()


def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator for circuit breaker protection.

    Args:
        name: Circuit breaker name
        config: Circuit breaker configuration

    Example:
        @circuit_breaker("external_api", CircuitBreakerConfig(failure_threshold=3))
        def call_external_api():
            # API call logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        cb = _global_manager.get_circuit_breaker(name, config)

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await cb.async_call(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return cb.call(func, *args, **kwargs)
            return sync_wrapper

    return decorator


# ============================================================================
# Specialized Circuit Breakers
# ============================================================================

class HTTPCircuitBreaker(CircuitBreaker):
    """Specialized circuit breaker for HTTP services."""

    def __init__(self, name: str, base_url: str, config: Optional[CircuitBreakerConfig] = None):
        """Initialize HTTP circuit breaker."""
        super().__init__(name, config)
        self.base_url = base_url

    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify HTTP-specific failures."""
        exception_name = type(exception).__name__.lower()

        # Check for specific HTTP status codes if available
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
            if status_code >= 500:
                return FailureType.SERVICE_ERROR
            elif status_code == 429:
                return FailureType.RATE_LIMIT
            elif status_code >= 400:
                return FailureType.HTTP_ERROR

        return super()._classify_failure(exception)


class DatabaseCircuitBreaker(CircuitBreaker):
    """Specialized circuit breaker for database connections."""

    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify database-specific failures."""
        exception_name = type(exception).__name__.lower()

        if "operational" in exception_name or "database" in exception_name:
            return FailureType.SERVICE_ERROR
        elif "connection" in exception_name:
            return FailureType.CONNECTION_ERROR
        elif "timeout" in exception_name:
            return FailureType.TIMEOUT

        return super()._classify_failure(exception)


# ============================================================================
# Context Manager
# ============================================================================

class CircuitBreakerContext:
    """Context manager for circuit breaker operations."""

    def __init__(self, circuit_breaker: CircuitBreaker):
        """Initialize context manager."""
        self.circuit_breaker = circuit_breaker
        self.start_time = None

    def __enter__(self):
        """Enter context."""
        if not self.circuit_breaker._can_execute():
            raise CircuitBreakerOpenError(
                self.circuit_breaker.name,
                self.circuit_breaker._get_retry_after_seconds()
            )

        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and record result."""
        if self.start_time is None:
            return

        duration = time.time() - self.start_time

        if exc_type is None:
            # Success
            call_result = CallResult(success=True, duration=duration)
        else:
            # Failure
            failure_type = self.circuit_breaker._classify_failure(exc_val)
            call_result = CallResult(
                success=False,
                duration=duration,
                failure_type=failure_type,
                error=str(exc_val)
            )

        self.circuit_breaker._record_call(call_result)


if __name__ == "__main__":
    # Example usage
    import requests
    import asyncio
    import aiohttp

    # Example 1: Using decorator
    @circuit_breaker("external_api", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30))
    def call_external_api():
        response = requests.get("https://httpbin.org/delay/1", timeout=5)
        response.raise_for_status()
        return response.json()

    # Example 2: Using context manager
    cb = CircuitBreaker("test_service")

    def test_function():
        with CircuitBreakerContext(cb):
            # Your code here
            time.sleep(0.1)
            return "success"

    # Example 3: Async usage
    @circuit_breaker("async_api", CircuitBreakerConfig(timeout=10))
    async def call_async_api():
        async with aiohttp.ClientSession() as session:
            async with session.get("https://httpbin.org/delay/1") as response:
                return await response.json()

    # Test the circuit breaker
    async def main():
        try:
            # Test sync circuit breaker
            print("Testing sync circuit breaker:")
            for i in range(5):
                try:
                    result = call_external_api()
                    print(f"Call {i+1}: Success")
                except Exception as e:
                    print(f"Call {i+1}: Failed - {e}")

            # Test async circuit breaker
            print("\nTesting async circuit breaker:")
            for i in range(5):
                try:
                    result = await call_async_api()
                    print(f"Async call {i+1}: Success")
                except Exception as e:
                    print(f"Async call {i+1}: Failed - {e}")

            # Get stats
            stats = _global_manager.get_all_stats()
            for name, stat in stats.items():
                print(f"\nCircuit breaker '{name}' stats:")
                print(f"  State: {stat.state}")
                print(f"  Total calls: {stat.total_calls}")
                print(f"  Failure rate: {stat.failure_rate:.1f}%")
                print(f"  Success count: {stat.success_count}")
                print(f"  Failure count: {stat.failure_count}")

        except Exception as e:
            print(f"Error: {e}")

    # Run the example
    asyncio.run(main())