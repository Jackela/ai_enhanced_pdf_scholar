from __future__ import annotations

import time

from backend.api.middleware.rate_limit_monitor import (
    RateLimitEvent,
    RateLimitMonitor,
)


def test_rate_limit_monitor_records_and_alerts():
    monitor = RateLimitMonitor(
        max_events=10, metrics_window_minutes=1, alert_threshold=0.5, log_file=None
    )

    now = time.time()
    # Record a mix of events, including rate-limited ones to trigger alert logic
    for _ in range(3):
        monitor.record_event(
            RateLimitEvent(
                timestamp=now,
                client_ip="1.2.3.4",
                endpoint="/api/test",
                status_code=429,
                response_time=0.1,
            )
        )
    monitor.record_event(
        RateLimitEvent(
            timestamp=now,
            client_ip="1.2.3.4",
            endpoint="/api/test",
            status_code=200,
            response_time=0.05,
        )
    )

    metrics = monitor.get_metrics(window_minutes=5)
    assert metrics.total_requests == 4
    assert metrics.rate_limited_requests == 3
    assert metrics.rate_limit_effectiveness >= 0

    recent_ip_events = monitor._get_recent_events_for_ip("1.2.3.4", minutes=5)
    assert len(recent_ip_events) == 4
