"""
Simple Alerting Service

Provides basic alerting capabilities for system performance monitoring
with configurable thresholds and notification channels.
"""

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """Alert data structure."""

    alert_id: str
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str
    source: str
    timestamp: datetime
    value: float | None = None
    threshold: float | None = None
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Alert rule configuration."""

    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: str  # >, >=, <, <=, ==, !=
    threshold_value: float
    severity: AlertSeverity
    cooldown_minutes: int = 5
    enabled: bool = True


class SimpleAlertingService:
    """
    Simple alerting service for performance monitoring with basic
    threshold-based rules and notification capabilities.
    """

    def __init__(self) -> None:
        self.rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self.alert_callbacks: list[Callable[[Alert], None]] = []
        self.rule_cooldowns: dict[str, float] = {}

        # Default alert rules
        self._initialize_default_rules()

        logger.info("SimpleAlertingService initialized")

    def _initialize_default_rules(self) -> None:
        """Initialize default alert rules for common metrics."""
        default_rules = [
            AlertRule(
                rule_id="cpu_high",
                name="High CPU Usage",
                description="CPU usage exceeds 80%",
                metric_name="cpu_percent",
                condition=">",
                threshold_value=80.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=5,
            ),
            AlertRule(
                rule_id="cpu_critical",
                name="Critical CPU Usage",
                description="CPU usage exceeds 90%",
                metric_name="cpu_percent",
                condition=">",
                threshold_value=90.0,
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=2,
            ),
            AlertRule(
                rule_id="memory_high",
                name="High Memory Usage",
                description="Memory usage exceeds 85%",
                metric_name="memory_percent",
                condition=">",
                threshold_value=85.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=5,
            ),
            AlertRule(
                rule_id="memory_critical",
                name="Critical Memory Usage",
                description="Memory usage exceeds 95%",
                metric_name="memory_percent",
                condition=">",
                threshold_value=95.0,
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=1,
            ),
            AlertRule(
                rule_id="disk_high",
                name="High Disk Usage",
                description="Disk usage exceeds 90%",
                metric_name="disk_usage_percent",
                condition=">",
                threshold_value=90.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=10,
            ),
            AlertRule(
                rule_id="api_slow",
                name="Slow API Responses",
                description="API response time exceeds 1000ms",
                metric_name="avg_response_time_ms",
                condition=">",
                threshold_value=1000.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=3,
            ),
            AlertRule(
                rule_id="api_errors",
                name="High API Error Rate",
                description="API error rate exceeds 5%",
                metric_name="error_rate_percent",
                condition=">",
                threshold_value=5.0,
                severity=AlertSeverity.ERROR,
                cooldown_minutes=5,
            ),
            AlertRule(
                rule_id="websocket_tasks_high",
                name="High WebSocket Task Queue",
                description="Pending RAG tasks exceed 10",
                metric_name="rag_tasks_pending",
                condition=">",
                threshold_value=10.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=3,
            ),
            AlertRule(
                rule_id="database_slow",
                name="Slow Database Queries",
                description="Average query time exceeds 500ms",
                metric_name="avg_query_time_ms",
                condition=">",
                threshold_value=500.0,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=5,
            ),
            AlertRule(
                rule_id="connection_leaks",
                name="Memory Connection Leaks",
                description="Connection leaks detected",
                metric_name="connection_leaks",
                condition=">",
                threshold_value=0.0,
                severity=AlertSeverity.ERROR,
                cooldown_minutes=10,
            ),
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    def add_rule(self, rule: AlertRule) -> bool:
        """Add a new alert rule."""
        try:
            self.rules[rule.rule_id] = rule
            logger.info(f"Added alert rule: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Error adding alert rule: {e}")
            return False

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        try:
            if rule_id in self.rules:
                rule = self.rules.pop(rule_id)
                logger.info(f"Removed alert rule: {rule.name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing alert rule: {e}")
            return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable an alert rule."""
        try:
            if rule_id in self.rules:
                self.rules[rule_id].enabled = True
                return True
            return False
        except Exception as e:
            logger.error(f"Error enabling alert rule: {e}")
            return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable an alert rule."""
        try:
            if rule_id in self.rules:
                self.rules[rule_id].enabled = False
                return True
            return False
        except Exception as e:
            logger.error(f"Error disabling alert rule: {e}")
            return False

    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add a callback function to be called when alerts are triggered."""
        self.alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Remove an alert callback."""
        with contextlib.suppress(ValueError):
            self.alert_callbacks.remove(callback)

    def evaluate_metrics(self, metrics_data: dict[str, Any]) -> None:
        """Evaluate metrics against alert rules and trigger alerts."""
        try:
            current_time = time.time()

            for rule in self.rules.values():
                if not rule.enabled:
                    continue

                # Check cooldown
                if rule.rule_id in self.rule_cooldowns:
                    last_triggered = self.rule_cooldowns[rule.rule_id]
                    cooldown_seconds = rule.cooldown_minutes * 60
                    if current_time - last_triggered < cooldown_seconds:
                        continue

                # Extract metric value from nested data
                metric_value = self._extract_metric_value(
                    metrics_data, rule.metric_name
                )
                if metric_value is None:
                    continue

                # Evaluate condition
                if self._evaluate_condition(
                    metric_value, rule.condition, rule.threshold_value
                ):
                    alert = self._create_alert(rule, metric_value)
                    self._trigger_alert(alert)
                    self.rule_cooldowns[rule.rule_id] = current_time

        except Exception as e:
            logger.error(f"Error evaluating metrics: {e}")

    def _extract_metric_value(
        self, metrics_data: dict[str, Any], metric_name: str
    ) -> float | None:
        """Extract metric value from nested metrics data structure."""
        try:
            # Direct lookup
            if metric_name in metrics_data:
                return float(metrics_data[metric_name])

            # Search in nested structures
            for category_name, category_data in metrics_data.items():
                if isinstance(category_data, dict) and metric_name in category_data:
                    return float(category_data[metric_name])

            return None

        except (ValueError, TypeError):
            return None

    def _evaluate_condition(
        self, value: float, condition: str, threshold: float
    ) -> bool:
        """Evaluate alert condition."""
        try:
            if condition == ">":
                return value > threshold
            elif condition == ">=":
                return value >= threshold
            elif condition == "<":
                return value < threshold
            elif condition == "<=":
                return value <= threshold
            elif condition == "==":
                return abs(value - threshold) < 0.001  # Float comparison
            elif condition == "!=":
                return abs(value - threshold) >= 0.001
            else:
                logger.warning(f"Unknown condition: {condition}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    def _create_alert(self, rule: AlertRule, metric_value: float) -> Alert:
        """Create an alert from a rule and metric value."""
        alert_id = f"{rule.rule_id}_{int(time.time())}"

        return Alert(
            alert_id=alert_id,
            alert_type=rule.metric_name,
            severity=rule.severity,
            title=rule.name,
            message=rule.description,
            source="performance_monitor",
            timestamp=datetime.now(),
            value=metric_value,
            threshold=rule.threshold_value,
            metadata={"rule_id": rule.rule_id, "condition": rule.condition},
        )

    def _trigger_alert(self, alert: Alert) -> None:
        """Trigger an alert and notify callbacks."""
        try:
            # Add to active alerts
            self.active_alerts[alert.alert_id] = alert

            # Add to history
            self.alert_history.append(alert)

            # Keep history manageable
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-500:]

            logger.warning(
                f"ALERT: {alert.title} - {alert.message} (value: {alert.value}, threshold: {alert.threshold})"
            )

            # Notify callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

        except Exception as e:
            logger.error(f"Error triggering alert: {e}")

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now()
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()

                # Move from active to resolved
                self.active_alerts.pop(alert_id)

                logger.info(f"Alert {alert_id} resolved")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False

    def get_active_alerts(self) -> list[Alert]:
        """Get list of active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, hours_back: int = 24) -> list[Alert]:
        """Get alert history for specified time period."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            return [
                alert for alert in self.alert_history if alert.timestamp >= cutoff_time
            ]
        except Exception as e:
            logger.error(f"Error getting alert history: {e}")
            return []

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert statistics."""
        try:
            recent_alerts = self.get_alert_history(24)

            severity_counts = {
                AlertSeverity.INFO.value: 0,
                AlertSeverity.WARNING.value: 0,
                AlertSeverity.ERROR.value: 0,
                AlertSeverity.CRITICAL.value: 0,
            }

            for alert in recent_alerts:
                severity_counts[alert.severity.value] += 1

            return {
                "active_alerts": len(self.active_alerts),
                "total_rules": len(self.rules),
                "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
                "alerts_last_24h": len(recent_alerts),
                "severity_breakdown": severity_counts,
                "most_recent_alert": (
                    recent_alerts[-1].timestamp.isoformat() if recent_alerts else None
                ),
            }

        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {"active_alerts": len(self.active_alerts), "error": str(e)}

    def clear_all_alerts(self) -> int:
        """Clear all active alerts and return count cleared."""
        try:
            count = len(self.active_alerts)

            # Mark all as resolved
            for alert in self.active_alerts.values():
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()

            self.active_alerts.clear()
            logger.info(f"Cleared {count} active alerts")
            return count

        except Exception as e:
            logger.error(f"Error clearing alerts: {e}")
            return 0
