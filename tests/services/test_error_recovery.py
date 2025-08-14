"""
Comprehensive Tests for Error Recovery Components

This module tests all error recovery mechanisms including:
- Retry mechanisms with exponential backoff
- Circuit breaker pattern for external services
- Resource cleanup and transaction rollback
- Recovery orchestration and metrics
- Health checks and system recovery
"""

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Dict, Any

import pytest

from src.services.error_recovery import (
    RetryMechanism, RetryConfig, CircuitBreaker, CircuitBreakerConfig,
    ResourceCleanupManager, TransactionManager, HealthChecker,
    RecoveryOrchestrator, CircuitBreakerState, RetryExhaustedException,
    CircuitBreakerOpenError, with_retry, with_circuit_breaker
)


class TestRetryMechanism:
    """Test suite for retry mechanism functionality."""

    def test_successful_execution_no_retry(self):
        """Test successful execution without retries."""
        config = RetryConfig(max_attempts=3)
        retry = RetryMechanism(config)

        call_count = 0

        @retry
        def success_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_with_eventual_success(self):
        """Test retry mechanism with eventual success."""
        config = RetryConfig(max_attempts=3, initial_delay=0.1)
        retry = RetryMechanism(config)

        call_count = 0

        @retry
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 3
        assert retry.metrics.successful_recoveries == 1

    def test_retry_exhaustion(self):
        """Test retry exhaustion with persistent failures."""
        config = RetryConfig(max_attempts=2, initial_delay=0.1)
        retry = RetryMechanism(config)

        @retry
        def always_fail():
            raise ValueError("Persistent failure")

        with pytest.raises(RetryExhaustedException):
            always_fail()

        assert retry.metrics.failed_recoveries == 1
        assert retry.metrics.total_attempts == 2

    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=(ConnectionError,),
            non_retryable_exceptions=(ValueError,)
        )
        retry = RetryMechanism(config)

        call_count = 0

        @retry
        def non_retryable_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            non_retryable_fail()

        assert call_count == 1  # Should not retry

    def test_exponential_backoff(self):
        """Test exponential backoff timing."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable timing
        )
        retry = RetryMechanism(config)

        call_times = []

        @retry
        def timing_test():
            call_times.append(time.time())
            raise ConnectionError("Test failure")

        with pytest.raises(RetryExhaustedException):
            timing_test()

        # Check that delays approximately follow exponential backoff
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allowing some tolerance for timing
        assert 0.08 <= delay1 <= 0.12  # ~0.1 seconds
        assert 0.18 <= delay2 <= 0.22  # ~0.2 seconds


class TestCircuitBreaker:
    """Test suite for circuit breaker functionality."""

    def test_closed_state_normal_operation(self):
        """Test normal operation in closed state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        @breaker
        def normal_function():
            return "success"

        result = normal_function()
        assert result == "success"
        assert breaker.get_state() == CircuitBreakerState.CLOSED

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60)
        breaker = CircuitBreaker(config)

        @breaker
        def failing_function():
            raise ConnectionError("Service failure")

        # First failure
        with pytest.raises(ConnectionError):
            failing_function()
        assert breaker.get_state() == CircuitBreakerState.CLOSED

        # Second failure - should trip breaker
        with pytest.raises(ConnectionError):
            failing_function()
        assert breaker.get_state() == CircuitBreakerState.OPEN

        # Third attempt should be rejected without calling function
        with pytest.raises(CircuitBreakerOpenError):
            failing_function()

    def test_half_open_recovery(self):
        """Test half-open state and recovery."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Short timeout for testing
            success_threshold=1
        )
        breaker = CircuitBreaker(config)

        call_count = 0

        @breaker
        def recovery_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Initial failure")
            return "recovered"

        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                recovery_function()
        assert breaker.get_state() == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should succeed and close circuit
        result = recovery_function()
        assert result == "recovered"
        assert breaker.get_state() == CircuitBreakerState.CLOSED

    def test_half_open_failure_reopens(self):
        """Test that failure in half-open state reopens circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1
        )
        breaker = CircuitBreaker(config)

        @breaker
        def unstable_function():
            raise ConnectionError("Still failing")

        # Trip the breaker
        with pytest.raises(ConnectionError):
            unstable_function()
        assert breaker.get_state() == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Failure in half-open should reopen
        with pytest.raises(ConnectionError):
            unstable_function()
        assert breaker.get_state() == CircuitBreakerState.OPEN


class TestResourceCleanupManager:
    """Test suite for resource cleanup functionality."""

    def test_cleanup_scope_success(self):
        """Test successful cleanup scope execution."""
        manager = ResourceCleanupManager()

        cleanup_called = False

        def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        with manager.cleanup_scope("test"):
            manager.add_cleanup_handler(cleanup_handler)
            # Normal execution
            pass

        assert cleanup_called

    def test_cleanup_scope_with_exception(self):
        """Test cleanup occurs even with exceptions."""
        manager = ResourceCleanupManager()

        cleanup_called = False

        def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        with pytest.raises(ValueError):
            with manager.cleanup_scope("test"):
                manager.add_cleanup_handler(cleanup_handler)
                raise ValueError("Test error")

        assert cleanup_called

    def test_path_cleanup(self):
        """Test automatic path cleanup."""
        manager = ResourceCleanupManager()

        # Create temporary files and directories
        temp_dir = Path(tempfile.mkdtemp())
        temp_file = temp_dir / "test_file.txt"
        temp_file.write_text("test content")

        with manager.cleanup_scope("path_test"):
            manager.add_cleanup_path(temp_dir)
            assert temp_dir.exists()
            assert temp_file.exists()

        # Should be cleaned up after scope
        assert not temp_dir.exists()

    def test_handler_exception_handling(self):
        """Test that cleanup handler exceptions don't prevent other cleanups."""
        manager = ResourceCleanupManager()

        successful_cleanup = False

        def failing_handler():
            raise RuntimeError("Cleanup failure")

        def successful_handler():
            nonlocal successful_cleanup
            successful_cleanup = True

        with manager.cleanup_scope("exception_test"):
            manager.add_cleanup_handler(failing_handler)
            manager.add_cleanup_handler(successful_handler)

        # Successful handler should still run despite failing one
        assert successful_cleanup
        assert manager.metrics.failed_recoveries == 1


class TestTransactionManager:
    """Test suite for transaction management."""

    def test_successful_transaction(self):
        """Test successful transaction execution."""
        # Mock database connection
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_db.transaction.return_value.__enter__ = MagicMock(return_value=mock_transaction)
        mock_db.transaction.return_value.__exit__ = MagicMock(return_value=None)

        manager = TransactionManager(mock_db)

        with manager.transaction_scope():
            pass  # Successful execution

        assert manager.metrics.successful_recoveries == 1
        assert manager.metrics.failed_recoveries == 0

    def test_transaction_rollback_on_exception(self):
        """Test transaction rollback on exception."""
        mock_db = MagicMock()
        mock_db.transaction.return_value.__enter__ = MagicMock()
        mock_db.transaction.return_value.__exit__ = MagicMock(return_value=None)

        manager = TransactionManager(mock_db)

        with pytest.raises(ValueError):
            with manager.transaction_scope():
                raise ValueError("Transaction error")

        assert manager.metrics.failed_recoveries == 1


class TestHealthChecker:
    """Test suite for health checking functionality."""

    def test_successful_health_checks(self):
        """Test successful health check execution."""
        checker = HealthChecker()

        def healthy_check():
            return True

        def another_healthy_check():
            return True

        checker.add_health_check("check1", healthy_check)
        checker.add_health_check("check2", another_healthy_check)

        results = checker.run_all_checks()
        assert results == {"check1": True, "check2": True}
        assert checker.is_healthy()

    def test_failed_health_checks(self):
        """Test health check failures."""
        checker = HealthChecker()

        def healthy_check():
            return True

        def failing_check():
            return False

        def exception_check():
            raise RuntimeError("Health check error")

        checker.add_health_check("healthy", healthy_check)
        checker.add_health_check("failing", failing_check)
        checker.add_health_check("exception", exception_check)

        results = checker.run_all_checks()
        assert results["healthy"] is True
        assert results["failing"] is False
        assert results["exception"] is False
        assert not checker.is_healthy()
        assert checker.metrics.failed_recoveries == 2  # failing and exception


class TestRecoveryOrchestrator:
    """Test suite for recovery orchestration."""

    def test_successful_operation_with_recovery(self):
        """Test successful operation with recovery orchestration."""
        orchestrator = RecoveryOrchestrator()

        def successful_operation():
            return "success"

        result = orchestrator.with_recovery(successful_operation)
        assert result == "success"
        assert orchestrator.metrics.successful_recoveries == 1

    def test_operation_with_cleanup_paths(self):
        """Test operation with automatic cleanup paths."""
        orchestrator = RecoveryOrchestrator()

        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp())
        temp_file = temp_dir / "test.txt"
        temp_file.write_text("test")

        def operation_with_cleanup():
            assert temp_dir.exists()
            return "success"

        result = orchestrator.with_recovery(
            operation_with_cleanup,
            cleanup_paths=[temp_dir]
        )

        assert result == "success"
        assert not temp_dir.exists()  # Should be cleaned up

    def test_recovery_on_failure(self):
        """Test recovery behavior on operation failure."""
        orchestrator = RecoveryOrchestrator()

        cleanup_called = False

        def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        def failing_operation():
            raise ValueError("Operation failed")

        with pytest.raises(ValueError):
            orchestrator.with_recovery(
                failing_operation,
                cleanup_handlers=[cleanup_handler]
            )

        assert cleanup_called
        assert orchestrator.metrics.failed_recoveries == 1

    def test_comprehensive_metrics(self):
        """Test comprehensive metrics collection."""
        orchestrator = RecoveryOrchestrator()

        # Perform some operations to generate metrics
        def successful_op():
            return "success"

        def failing_op():
            raise ValueError("Test failure")

        orchestrator.with_recovery(successful_op)

        try:
            orchestrator.with_recovery(failing_op)
        except ValueError:
            pass

        metrics = orchestrator.get_comprehensive_metrics()

        assert "orchestrator" in metrics
        assert "retry" in metrics
        assert "circuit_breaker" in metrics
        assert "cleanup" in metrics

        assert metrics["orchestrator"]["successful_recoveries"] == 1
        assert metrics["orchestrator"]["failed_recoveries"] == 1


class TestDecoratorFunctions:
    """Test suite for decorator convenience functions."""

    def test_with_retry_decorator(self):
        """Test with_retry decorator functionality."""
        call_count = 0

        @with_retry(max_attempts=3, initial_delay=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 2

    def test_with_circuit_breaker_decorator(self):
        """Test with_circuit_breaker decorator functionality."""

        @with_circuit_breaker(failure_threshold=2, recovery_timeout=60)
        def protected_function(should_fail=True):
            if should_fail:
                raise ConnectionError("Service failure")
            return "success"

        # Trigger failures to open circuit
        with pytest.raises(ConnectionError):
            protected_function(True)
        with pytest.raises(ConnectionError):
            protected_function(True)

        # Should now be open and reject calls
        with pytest.raises(CircuitBreakerOpenError):
            protected_function(True)


class TestIntegrationScenarios:
    """Integration tests for complex recovery scenarios."""

    def test_combined_retry_and_circuit_breaker(self):
        """Test combined retry and circuit breaker protection."""
        orchestrator = RecoveryOrchestrator()

        call_count = 0

        def unstable_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                raise ConnectionError("Service unstable")
            return "recovered"

        # Configure for quick testing
        retry_config = RetryConfig(max_attempts=2, initial_delay=0.1)
        circuit_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.2)

        # First attempt should exhaust retries and trip circuit breaker
        with pytest.raises((RetryExhaustedException, ConnectionError)):
            orchestrator.with_recovery(
                unstable_service,
                retry_config=retry_config,
                circuit_breaker_config=circuit_config
            )

        # Immediate next attempt should be rejected by circuit breaker
        with pytest.raises(CircuitBreakerOpenError):
            orchestrator.with_recovery(
                unstable_service,
                retry_config=retry_config,
                circuit_breaker_config=circuit_config
            )

    def test_resource_cleanup_with_failure_recovery(self):
        """Test comprehensive resource cleanup with failure recovery."""
        orchestrator = RecoveryOrchestrator()

        # Create resources to be cleaned up
        temp_dirs = []
        for i in range(3):
            temp_dir = Path(tempfile.mkdtemp())
            (temp_dir / f"file_{i}.txt").write_text(f"content {i}")
            temp_dirs.append(temp_dir)

        cleanup_handlers_called = []

        def cleanup_handler(handler_id):
            cleanup_handlers_called.append(handler_id)

        def operation_that_fails():
            # Verify all resources exist during operation
            for temp_dir in temp_dirs:
                assert temp_dir.exists()
            raise RuntimeError("Operation failed")

        with pytest.raises(RuntimeError):
            orchestrator.with_recovery(
                operation_that_fails,
                cleanup_paths=temp_dirs,
                cleanup_handlers=[
                    lambda: cleanup_handler("handler1"),
                    lambda: cleanup_handler("handler2")
                ]
            )

        # Verify all resources were cleaned up
        for temp_dir in temp_dirs:
            assert not temp_dir.exists()

        # Verify cleanup handlers were called
        assert "handler1" in cleanup_handlers_called
        assert "handler2" in cleanup_handlers_called

    def test_metrics_accuracy_across_components(self):
        """Test that metrics are accurately tracked across all components."""
        orchestrator = RecoveryOrchestrator()

        # Perform various operations
        operations_performed = 0

        def successful_operation():
            nonlocal operations_performed
            operations_performed += 1
            return f"success_{operations_performed}"

        def failing_operation():
            raise ValueError("Test failure")

        # Execute successful operations
        for _ in range(3):
            orchestrator.with_recovery(successful_operation)

        # Execute failing operations
        for _ in range(2):
            try:
                orchestrator.with_recovery(failing_operation)
            except ValueError:
                pass

        # Check comprehensive metrics
        metrics = orchestrator.get_comprehensive_metrics()

        # Verify orchestrator metrics
        assert metrics["orchestrator"]["successful_recoveries"] == 3
        assert metrics["orchestrator"]["failed_recoveries"] == 2

        # Verify retry metrics (each operation counted)
        assert metrics["retry"]["total_attempts"] >= 5

        # Verify cleanup metrics
        assert metrics["cleanup"]["operations"] >= 5  # Each operation triggers cleanup

        print(f"Final metrics: {json.dumps(metrics, indent=2, default=str)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])