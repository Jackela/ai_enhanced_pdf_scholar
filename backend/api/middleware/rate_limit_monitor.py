from typing import Any

"""
Rate Limiting Monitoring and Metrics Module
Provides monitoring, metrics collection, and alerting for rate limiting
"""

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEvent:
    """Rate limiting event for monitoring."""

    timestamp: float
    client_ip: str
    endpoint: str
    status_code: int
    response_time: float
    user_agent: str | None = None
    limit_type: str | None = None  # "endpoint", "global", "bypass"
    limit_value: int | None = None
    remaining: int | None = None


@dataclass
class RateLimitMetrics:
    """Rate limiting metrics summary."""

    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    error_requests: int = 0
    unique_ips: int = 0
    avg_response_time: float = 0.0
    top_endpoints: list[tuple[str, int]] = None
    top_ips: list[tuple[str, int]] = None
    rate_limit_effectiveness: float = 0.0

    def __post_init__(self) -> None:
        if self.top_endpoints is None:
            self.top_endpoints = []
        if self.top_ips is None:
            self.top_ips = []


class RateLimitMonitor:
    """Monitoring system for rate limiting middleware."""

    def __init__(
        self,
        max_events: int = 10000,
        metrics_window_minutes: int = 60,
        alert_threshold: float = 0.8,
        log_file: str | None = None,
    ) -> None:
        """
        Initialize rate limit monitor.

        Args:
            max_events: Maximum number of events to keep in memory
            metrics_window_minutes: Time window for metrics calculation
            alert_threshold: Threshold for rate limiting alerts (0.0-1.0)
            log_file: Optional file to log events to
        """
        self.max_events = max_events
        self.metrics_window = timedelta(minutes=metrics_window_minutes)
        self.alert_threshold = alert_threshold
        self.log_file = log_file

        # Event storage
        self._events: deque[Any] = deque[Any](maxlen=max_events)

        # Real-time counters
        self._counters: Any = defaultdict(int)
        self._ip_counters: Any = defaultdict(int)
        self._endpoint_counters: Any = defaultdict(int)
        self._response_times = deque[Any](maxlen=1000)

        # Alerting state
        self._last_alert_time: dict[str, Any] = {}
        self._alert_cooldown = timedelta(minutes=5)

        logger.info(f"Rate limit monitor initialized with {max_events} event capacity")

    def record_event(self, event: RateLimitEvent) -> None:
        """Record a rate limiting event."""
        self._events.append(event)

        # Update real-time counters
        self._counters["total_requests"] += 1
        self._ip_counters[event.client_ip] += 1
        self._endpoint_counters[event.endpoint] += 1
        self._response_times.append(event.response_time)

        if event.status_code == 200:
            self._counters["successful_requests"] += 1
        elif event.status_code == 429:
            self._counters["rate_limited_requests"] += 1
            self._check_alert_conditions(event)
        else:
            self._counters["error_requests"] += 1

        # Log to file if configured
        if self.log_file:
            self._log_event_to_file(event)

    def _log_event_to_file(self, event: RateLimitEvent) -> None:
        """Log event to file."""
        try:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as e:
            logger.error(f"Failed to log event to file: {e}")

    def _check_alert_conditions(self, event: RateLimitEvent) -> None:
        """Check if alert conditions are met."""
        current_time = datetime.fromtimestamp(event.timestamp)

        # Per-IP alert
        ip_key = f"ip:{event.client_ip}"
        if self._should_alert(ip_key, current_time):
            recent_events = self._get_recent_events_for_ip(event.client_ip, minutes=5)
            rate_limited_count = sum(1 for e in recent_events if e.status_code == 429)
            total_count = len(recent_events)

            if (
                total_count > 0
                and rate_limited_count / total_count > self.alert_threshold
            ):
                self._trigger_alert(
                    "high_rate_limiting",
                    {
                        "type": "ip",
                        "client_ip": event.client_ip,
                        "rate_limited": rate_limited_count,
                        "total_requests": total_count,
                        "rate": rate_limited_count / total_count,
                    },
                )
                self._last_alert_time[ip_key] = current_time

        # Per-endpoint alert
        endpoint_key = f"endpoint:{event.endpoint}"
        if self._should_alert(endpoint_key, current_time):
            recent_events = self._get_recent_events_for_endpoint(
                event.endpoint, minutes=5
            )
            rate_limited_count = sum(1 for e in recent_events if e.status_code == 429)
            total_count = len(recent_events)

            if (
                total_count > 0
                and rate_limited_count / total_count > self.alert_threshold
            ):
                self._trigger_alert(
                    "high_rate_limiting",
                    {
                        "type": "endpoint",
                        "endpoint": event.endpoint,
                        "rate_limited": rate_limited_count,
                        "total_requests": total_count,
                        "rate": rate_limited_count / total_count,
                    },
                )
                self._last_alert_time[endpoint_key] = current_time

    def _should_alert(self, alert_key: str, current_time: datetime) -> bool:
        """Check if enough time has passed since last alert."""
        last_alert = self._last_alert_time.get(alert_key)
        if last_alert is None:
            return True
        return current_time - last_alert > self._alert_cooldown

    def _trigger_alert(self, alert_type: str, context: dict[str, Any]) -> None:
        """Trigger a rate limiting alert."""
        logger.warning(f"Rate limiting alert [{alert_type}]: {context}")

        # Here you could integrate with external alerting systems:
        # - Send to monitoring service (Prometheus, DataDog, etc.)
        # - Send email/SMS notifications
        # - Post to Slack/Teams
        # - Write to dedicated alert log

        # For now, just log with high priority
        if alert_type == "high_rate_limiting":
            if context["type"] == "ip":
                logger.warning(
                    f"High rate limiting for IP {context['client_ip']}: "
                    f"{context['rate_limited']}/{context['total_requests']} requests "
                    f"({context['rate']:.1%}) rate limited in last 5 minutes"
                )
            elif context["type"] == "endpoint":
                logger.warning(
                    f"High rate limiting for endpoint {context['endpoint']}: "
                    f"{context['rate_limited']}/{context['total_requests']} requests "
                    f"({context['rate']:.1%}) rate limited in last 5 minutes"
                )

    def get_metrics(self, window_minutes: int | None = None) -> RateLimitMetrics:
        """Get rate limiting metrics for specified time window."""
        if window_minutes is None:
            window_minutes = self.metrics_window.total_seconds() / 60

        cutoff_time = time.time() - (window_minutes * 60)
        recent_events = [e for e in self._events if e.timestamp >= cutoff_time]

        if not recent_events:
            return RateLimitMetrics()

        # Calculate metrics
        total_requests = len(recent_events)
        successful_requests = sum(1 for e in recent_events if e.status_code == 200)
        rate_limited_requests = sum(1 for e in recent_events if e.status_code == 429)
        error_requests = sum(
            1 for e in recent_events if e.status_code not in [200, 429]
        )

        unique_ips = len(set[str](e.client_ip for e in recent_events))

        response_times = [e.response_time for e in recent_events]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        # Top endpoints
        endpoint_counts: Any = defaultdict(int)
        for event in recent_events:
            endpoint_counts[event.endpoint] += 1
        top_endpoints = sorted(
            endpoint_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Top IPs
        ip_counts: Any = defaultdict(int)
        for event in recent_events:
            ip_counts[event.client_ip] += 1
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Rate limiting effectiveness
        effectiveness = 0.0
        if total_requests > 0:
            # Assume requests beyond reasonable limits should be rate limited
            reasonable_limit = window_minutes * 60  # 1 req/sec average
            excess_requests = max(0, total_requests - reasonable_limit)
            if excess_requests > 0:
                effectiveness = rate_limited_requests / excess_requests

        return RateLimitMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            rate_limited_requests=rate_limited_requests,
            error_requests=error_requests,
            unique_ips=unique_ips,
            avg_response_time=avg_response_time,
            top_endpoints=top_endpoints,
            top_ips=top_ips,
            rate_limit_effectiveness=min(1.0, effectiveness),
        )

    def get_ip_metrics(
        self, client_ip: str, window_minutes: int = 60
    ) -> dict[str, Any]:
        """Get metrics for a specific IP address."""
        events = self._get_recent_events_for_ip(client_ip, window_minutes)

        if not events:
            return {"error": "No events found for IP"}

        total_requests = len(events)
        rate_limited_requests = sum(1 for e in events if e.status_code == 429)

        # Endpoints accessed
        endpoints = set[str](e.endpoint for e in events)

        # Request pattern
        timestamps = [e.timestamp for e in events]
        if len(timestamps) > 1:
            time_span = max(timestamps) - min(timestamps)
            request_rate = (
                total_requests / max(time_span, 1) * 60
            )  # requests per minute
        else:
            request_rate = 0

        return {
            "client_ip": client_ip,
            "total_requests": total_requests,
            "rate_limited_requests": rate_limited_requests,
            "rate_limited_percentage": rate_limited_requests / total_requests * 100,
            "endpoints_accessed": list[Any](endpoints),
            "request_rate_per_minute": request_rate,
            "first_seen": min(timestamps) if timestamps else None,
            "last_seen": max(timestamps) if timestamps else None,
        }

    def get_endpoint_metrics(
        self, endpoint: str, window_minutes: int = 60
    ) -> dict[str, Any]:
        """Get metrics for a specific endpoint."""
        events = self._get_recent_events_for_endpoint(endpoint, window_minutes)

        if not events:
            return {"error": "No events found for endpoint"}

        total_requests = len(events)
        rate_limited_requests = sum(1 for e in events if e.status_code == 429)
        unique_ips = len(set[str](e.client_ip for e in events))

        # Response time stats
        response_times = [e.response_time for e in events]
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)

        # Top IPs for this endpoint
        ip_counts: Any = defaultdict(int)
        for event in events:
            ip_counts[event.client_ip] += 1
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "endpoint": endpoint,
            "total_requests": total_requests,
            "rate_limited_requests": rate_limited_requests,
            "rate_limited_percentage": rate_limited_requests / total_requests * 100,
            "unique_ips": unique_ips,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "top_ips": top_ips,
        }

    def _get_recent_events_for_ip(
        self, client_ip: str, minutes: int
    ) -> list[RateLimitEvent]:
        """Get recent events for a specific IP."""
        cutoff_time = time.time() - (minutes * 60)
        return [
            e
            for e in self._events
            if e.client_ip == client_ip and e.timestamp >= cutoff_time
        ]

    def _get_recent_events_for_endpoint(
        self, endpoint: str, minutes: int
    ) -> list[RateLimitEvent]:
        """Get recent events for a specific endpoint."""
        cutoff_time = time.time() - (minutes * 60)
        return [
            e
            for e in self._events
            if e.endpoint == endpoint and e.timestamp >= cutoff_time
        ]

    def get_suspicious_ips(
        self, window_minutes: int = 60, min_requests: int = 50
    ) -> list[dict[str, Any]]:
        """Get list[Any] of suspicious IP addresses based on request patterns."""
        cutoff_time = time.time() - (window_minutes * 60)
        recent_events = [e for e in self._events if e.timestamp >= cutoff_time]

        # Group by IP
        ip_events: Any = defaultdict(list[Any])
        for event in recent_events:
            ip_events[event.client_ip].append(event)

        suspicious_ips = []

        for client_ip, events in ip_events.items():
            if len(events) < min_requests:
                continue

            # Calculate suspicion metrics
            total_requests = len(events)
            rate_limited_requests = sum(1 for e in events if e.status_code == 429)
            rate_limited_percentage = rate_limited_requests / total_requests * 100

            # Request rate
            timestamps = [e.timestamp for e in events]
            time_span = max(timestamps) - min(timestamps)
            request_rate = total_requests / max(time_span, 1) * 60  # per minute

            # Unique endpoints
            endpoints = set[str](e.endpoint for e in events)

            # User agents
            user_agents = set[str](e.user_agent for e in events if e.user_agent)

            # Suspicion score (higher = more suspicious)
            score = 0
            if rate_limited_percentage > 50:
                score += 3
            if request_rate > 100:  # More than 100 requests per minute
                score += 2
            if len(user_agents) == 1:  # Single user agent
                score += 1
            if len(endpoints) > 10:  # Scanning many endpoints
                score += 2

            if score >= 3:  # Threshold for suspicious behavior
                suspicious_ips.append(
                    {
                        "client_ip": client_ip,
                        "total_requests": total_requests,
                        "rate_limited_requests": rate_limited_requests,
                        "rate_limited_percentage": rate_limited_percentage,
                        "request_rate_per_minute": request_rate,
                        "unique_endpoints": len(endpoints),
                        "unique_user_agents": len(user_agents),
                        "suspicion_score": score,
                        "first_seen": min(timestamps),
                        "last_seen": max(timestamps),
                    }
                )

        return sorted(suspicious_ips, key=lambda x: x["suspicion_score"], reverse=True)

    def export_events(self, filename: str, window_minutes: int | None = None) -> None:
        """Export events to JSON file."""
        if window_minutes:
            cutoff_time = time.time() - (window_minutes * 60)
            events = [e for e in self._events if e.timestamp >= cutoff_time]
        else:
            events = list[Any](self._events)

        with open(filename, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(asdict(event)) + "\n")

        logger.info(f"Exported {len(events)} events to {filename}")

    def clear_old_events(self, hours_to_keep: int = 24) -> None:
        """Clear events older than specified hours."""
        cutoff_time = time.time() - (hours_to_keep * 3600)

        # Convert deque[Any] to list[Any], filter, then back to deque[Any]
        filtered_events = [e for e in self._events if e.timestamp >= cutoff_time]
        self._events.clear()
        self._events.extend(filtered_events)

        logger.info(
            f"Cleared old events, kept {len(filtered_events)} events from last {hours_to_keep} hours"
        )


# Global monitor instance
_monitor_instance: RateLimitMonitor | None = None


def get_monitor(log_file: str | None = None) -> RateLimitMonitor:
    """Get or create global monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = RateLimitMonitor(log_file=log_file)
    return _monitor_instance


def record_rate_limit_event(
    client_ip: str,
    endpoint: str,
    status_code: int,
    response_time: float,
    user_agent: str | None = None,
    limit_type: str | None = None,
    limit_value: int | None = None,
    remaining: int | None = None,
) -> None:
    """Convenience function to record a rate limiting event."""
    monitor = get_monitor()
    event = RateLimitEvent(
        timestamp=time.time(),
        client_ip=client_ip,
        endpoint=endpoint,
        status_code=status_code,
        response_time=response_time,
        user_agent=user_agent,
        limit_type=limit_type,
        limit_value=limit_value,
        remaining=remaining,
    )
    monitor.record_event(event)
