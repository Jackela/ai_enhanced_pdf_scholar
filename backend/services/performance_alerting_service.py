"""
Performance Alerting and Notification Service

Provides intelligent alerting for performance degradation, cache issues,
and system health problems with configurable thresholds and notification channels.
"""

import asyncio
import json
import logging
import smtplib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp

from backend.services.apm_service import APMService
from backend.services.cache_telemetry_service import CacheTelemetryService

logger = logging.getLogger(__name__)


# ============================================================================
# Alert Configuration and Models
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    LOG_ONLY = "log_only"


@dataclass
class AlertRule:
    """Configurable alert rule."""
    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: str  # e.g., ">", "<", ">=", "<=", "=="
    threshold_value: float
    severity: AlertSeverity
    evaluation_window_minutes: int = 5
    min_data_points: int = 3
    cooldown_minutes: int = 15
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    custom_message_template: str | None = None


@dataclass
class NotificationConfig:
    """Notification configuration."""
    channel: NotificationChannel
    config: dict[str, Any]
    enabled: bool = True
    severity_filter: list[AlertSeverity] = field(
        default_factory=lambda: list(AlertSeverity)
    )


@dataclass
class AlertEvent:
    """Individual alert event."""
    event_id: str
    rule_id: str
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    state: AlertState
    metric_name: str
    metric_value: float
    threshold_value: float
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


@dataclass
class AlertInstance:
    """Active alert instance."""
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    state: AlertState
    first_triggered: datetime
    last_triggered: datetime
    trigger_count: int
    current_value: float
    threshold_value: float
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    events: list[AlertEvent] = field(default_factory=list)


# ============================================================================
# Performance Alerting Service
# ============================================================================

class PerformanceAlertingService:
    """
    Comprehensive performance alerting service with intelligent notifications.
    """

    def __init__(
        self,
        apm_service: APMService,
        cache_telemetry: CacheTelemetryService,
        config_path: Path | None = None
    ):
        self.apm = apm_service
        self.cache_telemetry = cache_telemetry
        self.config_path = config_path or Path("alert_config.json")

        # Alert management
        self.alert_rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, AlertInstance] = {}
        self.alert_history: list[AlertEvent] = []
        self.silenced_rules: dict[str, datetime] = {}  # rule_id -> until_time

        # Notification configuration
        self.notification_configs: list[NotificationConfig] = []

        # Evaluation state
        self.metric_history: dict[str, list[Tuple[datetime, float]]] = {}
        self.last_evaluation: datetime | None = None
        self.evaluation_lock = asyncio.Lock()

        # Background tasks
        self._running = False
        self._evaluation_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # Load configuration
        self._load_configuration()

        # Setup default rules if none exist
        if not self.alert_rules:
            self._setup_default_alert_rules()

        logger.info(f"Performance alerting service initialized with {len(self.alert_rules)} rules")

    # ========================================================================
    # Configuration Management
    # ========================================================================

    def _load_configuration(self):
        """Load alert configuration from file."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    config = json.load(f)

                # Load alert rules
                for rule_data in config.get("alert_rules", []):
                    rule = AlertRule(**rule_data)
                    self.alert_rules[rule.rule_id] = rule

                # Load notification configs
                for notif_data in config.get("notifications", []):
                    notif = NotificationConfig(
                        channel=NotificationChannel(notif_data["channel"]),
                        config=notif_data["config"],
                        enabled=notif_data.get("enabled", True),
                        severity_filter=[
                            AlertSeverity(s) for s in notif_data.get("severity_filter", [])
                        ] or list(AlertSeverity)
                    )
                    self.notification_configs.append(notif)

                logger.info(f"Loaded alert configuration from {self.config_path}")
            else:
                logger.info("No alert configuration file found, using defaults")

        except Exception as e:
            logger.error(f"Error loading alert configuration: {e}")

    def save_configuration(self):
        """Save current alert configuration to file."""
        try:
            config = {
                "alert_rules": [asdict(rule) for rule in self.alert_rules.values()],
                "notifications": [
                    {
                        "channel": notif.channel.value,
                        "config": notif.config,
                        "enabled": notif.enabled,
                        "severity_filter": [s.value for s in notif.severity_filter]
                    }
                    for notif in self.notification_configs
                ]
            }

            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2, default=str)

            logger.info(f"Saved alert configuration to {self.config_path}")

        except Exception as e:
            logger.error(f"Error saving alert configuration: {e}")

    def _setup_default_alert_rules(self):
        """Setup default alert rules."""
        default_rules = [
            AlertRule(
                rule_id="high_p95_latency",
                name="High P95 Response Time",
                description="P95 response time exceeds threshold",
                metric_name="p95_response_time_ms",
                condition=">=",
                threshold_value=2000.0,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_data_points=3
            ),
            AlertRule(
                rule_id="high_error_rate",
                name="High Error Rate",
                description="Error rate exceeds threshold",
                metric_name="error_rate_percent",
                condition=">=",
                threshold_value=5.0,
                severity=AlertSeverity.CRITICAL,
                evaluation_window_minutes=3,
                min_data_points=2
            ),
            AlertRule(
                rule_id="low_cache_hit_rate",
                name="Low Cache Hit Rate",
                description="Overall cache hit rate is too low",
                metric_name="cache_hit_rate_percent",
                condition="<=",
                threshold_value=50.0,
                severity=AlertSeverity.MEDIUM,
                evaluation_window_minutes=10,
                min_data_points=5
            ),
            AlertRule(
                rule_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage exceeds threshold",
                metric_name="cpu_percent",
                condition=">=",
                threshold_value=85.0,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_data_points=3
            ),
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage exceeds threshold",
                metric_name="memory_percent",
                condition=">=",
                threshold_value=90.0,
                severity=AlertSeverity.CRITICAL,
                evaluation_window_minutes=3,
                min_data_points=2
            ),
            AlertRule(
                rule_id="low_throughput",
                name="Low Throughput",
                description="Request throughput is too low",
                metric_name="requests_per_second",
                condition="<=",
                threshold_value=1.0,
                severity=AlertSeverity.MEDIUM,
                evaluation_window_minutes=15,
                min_data_points=8
            )
        ]

        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule

        # Setup default notification (log only)
        self.notification_configs.append(
            NotificationConfig(
                channel=NotificationChannel.LOG_ONLY,
                config={}
            )
        )

        logger.info("Setup default alert rules")

    # ========================================================================
    # Alert Rule Management
    # ========================================================================

    def add_alert_rule(self, rule: AlertRule) -> bool:
        """Add a new alert rule."""
        try:
            self.alert_rules[rule.rule_id] = rule
            self.save_configuration()
            logger.info(f"Added alert rule: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Error adding alert rule: {e}")
            return False

    def update_alert_rule(self, rule_id: str, updates: dict[str, Any]) -> bool:
        """Update an existing alert rule."""
        try:
            if rule_id not in self.alert_rules:
                return False

            rule = self.alert_rules[rule_id]
            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

            self.save_configuration()
            logger.info(f"Updated alert rule: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return False

    def delete_alert_rule(self, rule_id: str) -> bool:
        """Delete an alert rule."""
        try:
            if rule_id in self.alert_rules:
                del self.alert_rules[rule_id]

                # Resolve any active alerts for this rule
                if rule_id in self.active_alerts:
                    self.resolve_alert(rule_id, "Rule deleted")

                self.save_configuration()
                logger.info(f"Deleted alert rule: {rule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting alert rule: {e}")
            return False

    def silence_rule(self, rule_id: str, duration_minutes: int) -> bool:
        """Silence an alert rule for a specified duration."""
        try:
            until_time = datetime.utcnow() + timedelta(minutes=duration_minutes)
            self.silenced_rules[rule_id] = until_time
            logger.info(f"Silenced rule {rule_id} until {until_time}")
            return True
        except Exception as e:
            logger.error(f"Error silencing rule: {e}")
            return False

    def unsilence_rule(self, rule_id: str) -> bool:
        """Remove silence from an alert rule."""
        try:
            if rule_id in self.silenced_rules:
                del self.silenced_rules[rule_id]
                logger.info(f"Unsilenced rule: {rule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unsilencing rule: {e}")
            return False

    # ========================================================================
    # Alert Lifecycle Management
    # ========================================================================

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.state = AlertState.ACKNOWLEDGED

                # Create acknowledgment event
                event = AlertEvent(
                    event_id=f"{alert_id}_ack_{datetime.utcnow().timestamp()}",
                    rule_id=alert.rule_id,
                    alert_id=alert_id,
                    timestamp=datetime.utcnow(),
                    severity=alert.severity,
                    state=AlertState.ACKNOWLEDGED,
                    metric_name="",
                    metric_value=0,
                    threshold_value=0,
                    message=f"Alert acknowledged by {acknowledged_by}",
                    acknowledged_by=acknowledged_by,
                    acknowledged_at=datetime.utcnow()
                )

                alert.events.append(event)
                self.alert_history.append(event)

                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False

    def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Manually resolve an active alert."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.state = AlertState.RESOLVED

                # Create resolution event
                event = AlertEvent(
                    event_id=f"{alert_id}_resolved_{datetime.utcnow().timestamp()}",
                    rule_id=alert.rule_id,
                    alert_id=alert_id,
                    timestamp=datetime.utcnow(),
                    severity=alert.severity,
                    state=AlertState.RESOLVED,
                    metric_name="",
                    metric_value=0,
                    threshold_value=0,
                    message=f"Alert resolved: {resolution_note}",
                    resolved_at=datetime.utcnow()
                )

                alert.events.append(event)
                self.alert_history.append(event)

                # Remove from active alerts
                del self.active_alerts[alert_id]

                logger.info(f"Alert {alert_id} resolved: {resolution_note}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False

    # ========================================================================
    # Metric Collection and Evaluation
    # ========================================================================

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if not self._running:
            self._running = True
            self._evaluation_task = asyncio.create_task(self._evaluation_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Performance alerting monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        self._running = False

        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Performance alerting monitoring stopped")

    async def _evaluation_loop(self):
        """Main evaluation loop for checking alert conditions."""
        while self._running:
            try:
                async with self.evaluation_lock:
                    await self._collect_current_metrics()
                    await self._evaluate_alert_rules()
                    self.last_evaluation = datetime.utcnow()

                # Wait 30 seconds between evaluations
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert evaluation loop: {e}")
                await asyncio.sleep(30)

    async def _cleanup_loop(self):
        """Cleanup loop for maintaining alert history and silenced rules."""
        while self._running:
            try:
                await self._cleanup_old_data()
                await self._cleanup_silenced_rules()

                # Cleanup every 10 minutes
                await asyncio.sleep(600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(600)

    async def _collect_current_metrics(self):
        """Collect current performance metrics."""
        try:
            # Get latest performance snapshot
            if self.apm.performance_snapshots:
                snapshot = self.apm.performance_snapshots[-1]
                timestamp = snapshot.timestamp

                # Collect key metrics
                metrics = {
                    "p95_response_time_ms": snapshot.p95_response_time_ms,
                    "avg_response_time_ms": snapshot.avg_response_time_ms,
                    "error_rate_percent": snapshot.error_rate_percent,
                    "requests_per_second": snapshot.requests_per_second,
                    "cpu_percent": snapshot.cpu_percent,
                    "memory_percent": snapshot.memory_percent,
                    "cache_hit_rate_percent": snapshot.cache_hit_rate_percent
                }

                # Store metrics in history
                for metric_name, value in metrics.items():
                    if metric_name not in self.metric_history:
                        self.metric_history[metric_name] = []

                    self.metric_history[metric_name].append((timestamp, value))

                    # Keep only last 2 hours of data for evaluation
                    cutoff_time = datetime.utcnow() - timedelta(hours=2)
                    self.metric_history[metric_name] = [
                        (ts, val) for ts, val in self.metric_history[metric_name]
                        if ts >= cutoff_time
                    ]

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def _evaluate_alert_rules(self):
        """Evaluate all alert rules against current metrics."""
        current_time = datetime.utcnow()

        for rule_id, rule in self.alert_rules.items():
            try:
                if not rule.enabled:
                    continue

                # Check if rule is silenced
                if rule_id in self.silenced_rules:
                    if current_time < self.silenced_rules[rule_id]:
                        continue  # Still silenced
                    else:
                        # Silence expired
                        del self.silenced_rules[rule_id]

                # Get metric data for evaluation window
                if rule.metric_name not in self.metric_history:
                    continue

                window_start = current_time - timedelta(minutes=rule.evaluation_window_minutes)
                metric_data = [
                    (ts, val) for ts, val in self.metric_history[rule.metric_name]
                    if ts >= window_start
                ]

                if len(metric_data) < rule.min_data_points:
                    continue  # Not enough data points

                # Calculate evaluation value (using most recent value)
                current_value = metric_data[-1][1]

                # Check condition
                condition_met = self._evaluate_condition(
                    current_value, rule.condition, rule.threshold_value
                )

                # Handle alert state
                if condition_met:
                    await self._handle_alert_trigger(rule, current_value)
                else:
                    await self._handle_alert_recovery(rule_id)

            except Exception as e:
                logger.error(f"Error evaluating rule {rule_id}: {e}")

    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
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
        else:
            logger.error(f"Unknown condition: {condition}")
            return False

    async def _handle_alert_trigger(self, rule: AlertRule, current_value: float):
        """Handle alert trigger event."""
        alert_id = rule.rule_id
        current_time = datetime.utcnow()

        if alert_id in self.active_alerts:
            # Update existing alert
            alert = self.active_alerts[alert_id]
            alert.last_triggered = current_time
            alert.trigger_count += 1
            alert.current_value = current_value

            # Check cooldown
            time_since_last_notification = current_time - alert.last_triggered
            if time_since_last_notification.total_seconds() < rule.cooldown_minutes * 60:
                return  # Still in cooldown
        else:
            # Create new alert
            message = self._generate_alert_message(rule, current_value)

            alert = AlertInstance(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                state=AlertState.ACTIVE,
                first_triggered=current_time,
                last_triggered=current_time,
                trigger_count=1,
                current_value=current_value,
                threshold_value=rule.threshold_value,
                message=message,
                context={"rule_tags": rule.tags}
            )

            self.active_alerts[alert_id] = alert

        # Create alert event
        event = AlertEvent(
            event_id=f"{alert_id}_{current_time.timestamp()}",
            rule_id=rule.rule_id,
            alert_id=alert_id,
            timestamp=current_time,
            severity=rule.severity,
            state=AlertState.ACTIVE,
            metric_name=rule.metric_name,
            metric_value=current_value,
            threshold_value=rule.threshold_value,
            message=alert.message
        )

        alert.events.append(event)
        self.alert_history.append(event)

        # Send notifications
        await self._send_notifications(alert, event)

    async def _handle_alert_recovery(self, rule_id: str):
        """Handle alert recovery (condition no longer met)."""
        if rule_id in self.active_alerts:
            alert = self.active_alerts[rule_id]

            # Auto-resolve alert
            resolution_event = AlertEvent(
                event_id=f"{rule_id}_recovered_{datetime.utcnow().timestamp()}",
                rule_id=rule_id,
                alert_id=rule_id,
                timestamp=datetime.utcnow(),
                severity=alert.severity,
                state=AlertState.RESOLVED,
                metric_name="",
                metric_value=0,
                threshold_value=0,
                message="Alert condition no longer met - auto-resolved",
                resolved_at=datetime.utcnow()
            )

            alert.events.append(resolution_event)
            self.alert_history.append(resolution_event)

            # Send recovery notification
            await self._send_notifications(alert, resolution_event)

            # Remove from active alerts
            del self.active_alerts[rule_id]

            logger.info(f"Alert {rule_id} auto-resolved")

    def _generate_alert_message(self, rule: AlertRule, current_value: float) -> str:
        """Generate alert message."""
        if rule.custom_message_template:
            try:
                return rule.custom_message_template.format(
                    rule_name=rule.name,
                    metric_name=rule.metric_name,
                    current_value=current_value,
                    threshold_value=rule.threshold_value,
                    condition=rule.condition
                )
            except Exception:
                pass  # Fall back to default

        return (
            f"Alert: {rule.name} - "
            f"{rule.metric_name} is {current_value:.2f} "
            f"({rule.condition} {rule.threshold_value})"
        )

    # ========================================================================
    # Notification System
    # ========================================================================

    async def _send_notifications(self, alert: AlertInstance, event: AlertEvent):
        """Send notifications for alert event."""
        for notification_config in self.notification_configs:
            if not notification_config.enabled:
                continue

            # Check severity filter
            if (notification_config.severity_filter and
                alert.severity not in notification_config.severity_filter):
                continue

            try:
                await self._send_single_notification(notification_config, alert, event)
            except Exception as e:
                logger.error(f"Error sending notification via {notification_config.channel}: {e}")

    async def _send_single_notification(
        self,
        notification_config: NotificationConfig,
        alert: AlertInstance,
        event: AlertEvent
    ):
        """Send a single notification."""
        if notification_config.channel == NotificationChannel.LOG_ONLY:
            logger.warning(f"ALERT: {alert.message}")

        elif notification_config.channel == NotificationChannel.EMAIL:
            await self._send_email_notification(notification_config.config, alert, event)

        elif notification_config.channel == NotificationChannel.WEBHOOK:
            await self._send_webhook_notification(notification_config.config, alert, event)

        elif notification_config.channel == NotificationChannel.SLACK:
            await self._send_slack_notification(notification_config.config, alert, event)

        elif notification_config.channel == NotificationChannel.DISCORD:
            await self._send_discord_notification(notification_config.config, alert, event)

    async def _send_email_notification(
        self,
        config: dict[str, Any],
        alert: AlertInstance,
        event: AlertEvent
    ):
        """Send email notification."""
        try:
            smtp_server = config["smtp_server"]
            smtp_port = config["smtp_port"]
            username = config["username"]
            password = config["password"]
            from_addr = config["from_address"]
            to_addrs = config["to_addresses"]

            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = ", ".join(to_addrs)
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.rule_name}"

            # Create email body
            body = f"""
Performance Alert: {alert.rule_name}

Severity: {alert.severity.upper()}
Status: {alert.state.upper()}
Metric: {event.metric_name}
Current Value: {event.metric_value:.2f}
Threshold: {event.threshold_value:.2f}
Triggered: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message: {alert.message}

Alert Details:
- Rule ID: {alert.rule_id}
- Alert ID: {alert.alert_id}
- First Triggered: {alert.first_triggered.strftime('%Y-%m-%d %H:%M:%S UTC')}
- Trigger Count: {alert.trigger_count}

View Dashboard: http://your-domain/dashboard/performance
            """

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg, from_addr, to_addrs)
            server.quit()

            logger.info(f"Email notification sent for alert {alert.alert_id}")

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    async def _send_webhook_notification(
        self,
        config: dict[str, Any],
        alert: AlertInstance,
        event: AlertEvent
    ):
        """Send webhook notification."""
        try:
            url = config["url"]
            headers = config.get("headers", {})

            payload = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "state": alert.state.value,
                "message": alert.message,
                "metric_name": event.metric_name,
                "metric_value": event.metric_value,
                "threshold_value": event.threshold_value,
                "timestamp": event.timestamp.isoformat(),
                "trigger_count": alert.trigger_count
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"Webhook notification sent for alert {alert.alert_id}")
                    else:
                        logger.error(f"Webhook returned status {response.status}")

        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")

    async def _send_slack_notification(
        self,
        config: dict[str, Any],
        alert: AlertInstance,
        event: AlertEvent
    ):
        """Send Slack notification."""
        try:
            webhook_url = config["webhook_url"]
            channel = config.get("channel", "#alerts")

            color_map = {
                AlertSeverity.LOW: "#36a64f",      # Green
                AlertSeverity.MEDIUM: "#ffcc00",   # Yellow
                AlertSeverity.HIGH: "#ff9900",     # Orange
                AlertSeverity.CRITICAL: "#ff0000"  # Red
            }

            payload = {
                "channel": channel,
                "username": "Performance Monitor",
                "icon_emoji": ":warning:",
                "attachments": [{
                    "color": color_map.get(alert.severity, "#808080"),
                    "title": f"[{alert.severity.upper()}] {alert.rule_name}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Metric", "value": event.metric_name, "short": True},
                        {"title": "Value", "value": f"{event.metric_value:.2f}", "short": True},
                        {"title": "Threshold", "value": f"{event.threshold_value:.2f}", "short": True},
                        {"title": "State", "value": alert.state.upper(), "short": True}
                    ],
                    "footer": "Performance Monitor",
                    "ts": int(event.timestamp.timestamp())
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for alert {alert.alert_id}")
                    else:
                        logger.error(f"Slack webhook returned status {response.status}")

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")

    async def _send_discord_notification(
        self,
        config: dict[str, Any],
        alert: AlertInstance,
        event: AlertEvent
    ):
        """Send Discord notification."""
        try:
            webhook_url = config["webhook_url"]

            color_map = {
                AlertSeverity.LOW: 0x36a64f,      # Green
                AlertSeverity.MEDIUM: 0xffcc00,   # Yellow
                AlertSeverity.HIGH: 0xff9900,     # Orange
                AlertSeverity.CRITICAL: 0xff0000  # Red
            }

            payload = {
                "username": "Performance Monitor",
                "avatar_url": config.get("avatar_url"),
                "embeds": [{
                    "title": f"[{alert.severity.upper()}] {alert.rule_name}",
                    "description": alert.message,
                    "color": color_map.get(alert.severity, 0x808080),
                    "fields": [
                        {"name": "Metric", "value": event.metric_name, "inline": True},
                        {"name": "Value", "value": f"{event.metric_value:.2f}", "inline": True},
                        {"name": "Threshold", "value": f"{event.threshold_value:.2f}", "inline": True},
                        {"name": "State", "value": alert.state.upper(), "inline": True}
                    ],
                    "footer": {"text": "Performance Monitor"},
                    "timestamp": event.timestamp.isoformat()
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=10) as response:
                    if response.status in [200, 204]:
                        logger.info(f"Discord notification sent for alert {alert.alert_id}")
                    else:
                        logger.error(f"Discord webhook returned status {response.status}")

        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")

    # ========================================================================
    # Cleanup and Maintenance
    # ========================================================================

    async def _cleanup_old_data(self):
        """Clean up old alert history and metric data."""
        try:
            # Clean up alert history (keep 7 days)
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            original_count = len(self.alert_history)

            self.alert_history = [
                event for event in self.alert_history
                if event.timestamp >= cutoff_time
            ]

            cleaned_count = original_count - len(self.alert_history)
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old alert events")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")

    async def _cleanup_silenced_rules(self):
        """Clean up expired silenced rules."""
        try:
            current_time = datetime.utcnow()
            expired_rules = [
                rule_id for rule_id, until_time in self.silenced_rules.items()
                if current_time >= until_time
            ]

            for rule_id in expired_rules:
                del self.silenced_rules[rule_id]
                logger.info(f"Silence expired for rule: {rule_id}")

        except Exception as e:
            logger.error(f"Error cleaning up silenced rules: {e}")

    # ========================================================================
    # API Methods
    # ========================================================================

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all active alerts."""
        return [asdict(alert) for alert in self.active_alerts.values()]

    def get_alert_history(
        self,
        hours_back: int = 24,
        severity_filter: list[AlertSeverity] | None = None
    ) -> list[dict[str, Any]]:
        """Get alert history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        filtered_events = [
            event for event in self.alert_history
            if event.timestamp >= cutoff_time
        ]

        if severity_filter:
            filtered_events = [
                event for event in filtered_events
                if event.severity in severity_filter
            ]

        return [asdict(event) for event in filtered_events]

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert statistics."""
        now = datetime.utcnow()

        # Count alerts by severity in last 24 hours
        last_24h = now - timedelta(hours=24)
        recent_events = [
            event for event in self.alert_history
            if event.timestamp >= last_24h
        ]

        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = sum(
                1 for event in recent_events if event.severity == severity
            )

        # Top alerting rules
        rule_counts = {}
        for event in recent_events:
            rule_counts[event.rule_id] = rule_counts.get(event.rule_id, 0) + 1

        top_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "timestamp": now.isoformat(),
            "active_alerts_count": len(self.active_alerts),
            "total_rules": len(self.alert_rules),
            "silenced_rules": len(self.silenced_rules),
            "last_24h_events": len(recent_events),
            "severity_distribution": severity_counts,
            "top_alerting_rules": [
                {"rule_id": rule_id, "count": count}
                for rule_id, count in top_rules
            ],
            "system_health": {
                "monitoring_active": self._running,
                "last_evaluation": self.last_evaluation.isoformat() if self.last_evaluation else None
            }
        }
