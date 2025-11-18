from __future__ import annotations

import time

import pytest

from src.services.error_recovery import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    RetryConfig,
    RetryMechanism,
)


def test_retry_mechanism_succeeds_after_failure():
    attempts = {"count": 0}

    @RetryMechanism(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ValueError("fail once")
        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 2


def test_retry_mechanism_records_failed_attempts():
    mechanism = RetryMechanism(
        RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
    )

    @mechanism
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(Exception):
        always_fail()
    assert mechanism.metrics.failed_recoveries == 1


def test_circuit_breaker_trips_and_recovers():
    breaker = CircuitBreaker(
        CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.01)
    )

    call_count = {"count": 0}

    @breaker
    def flaky():
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise ValueError("boom")
        return "ok"

    with pytest.raises(ValueError):
        flaky()

    with pytest.raises(CircuitBreakerOpenError):
        flaky()

    time.sleep(0.02)
    assert flaky() == "ok"
