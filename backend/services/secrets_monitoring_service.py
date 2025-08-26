"""
Secrets Monitoring and Alerting Service
Provides comprehensive monitoring, alerting, and audit logging
for production secrets management with real-time threat detection.
"""

import asyncio
import json
import logging
import smtplib
import time
from datetime import datetime, timedelta

try:
    from email.mime.multipart import MimeMultipart
    from email.mime.text import MimeText
except ImportError:
    # Python 3.13+ compatibility
    from email.mime.multipart import MIMEMultipart as MimeMultipart
    from email.mime.text import MIMEText as MimeText
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..core.secrets_vault import ProductionSecretsManager
from ..services.secrets_validation_service import SecretValidationService

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertChannel(str, Enum):
    """Alert notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    LOG = "log"


class MonitoringMetric(str, Enum):
    """Monitoring metrics for secrets."""
    SECRET_ACCESS_COUNT = "secret_access_count"
    SECRET_ACCESS_FREQUENCY = "secret_access_frequency"
    SECRET_AGE = "secret_age"
    ROTATION_OVERDUE = "rotation_overdue"
    VALIDATION_FAILURES = "validation_failures"
    ENCRYPTION_HEALTH = "encryption_health"
    BACKUP_STATUS = "backup_status"
    COMPLIANCE_STATUS = "compliance_status"
    ANOMALOUS_ACCESS = "anomalous_access"
    FAILED_DECRYPTIONS = "failed_decryptions"


@dataclass
class AlertRule:
    """Defines an alert rule for secrets monitoring."""
    name: str
    description: str
    metric: MonitoringMetric
    condition: str  # e.g., "value > threshold"
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 60
    channels: list[AlertChannel] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Represents a monitoring alert."""
    rule_name: str
    severity: AlertSeverity
    message: str
    details: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution_time: datetime | None = None
    alert_id: str = field(default_factory=lambda: f"alert_{int(time.time())}")


@dataclass
class MetricData:
    """Metric data point."""
    metric: MonitoringMetric
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AlertingConfig(BaseModel):
    """Configuration for alerting system."""
    # Email configuration
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = Field(default=True)
    from_email: str = Field(default="alerts@ai-pdf-scholar.com")

    # Slack configuration
    slack_webhook_url: str | None = None
    slack_channel: str = Field(default="#security-alerts")

    # PagerDuty configuration
    pagerduty_integration_key: str | None = None

    # Webhook configuration
    webhook_urls: list[str] = Field(default_factory=list)
    webhook_timeout: int = Field(default=30)

    # General settings
    alert_retention_days: int = Field(default=365)
    max_alerts_per_hour: int = Field(default=100)
    enable_alert_aggregation: bool = Field(default=True)
    batch_alert_window_minutes: int = Field(default=5)


class SecretsMonitoringService:
    """
    Advanced monitoring service for secrets management
    with real-time alerting and audit trail analysis.
    """

    def __init__(
        self,
        secrets_manager: ProductionSecretsManager,
        validation_service: SecretValidationService,
        config: AlertingConfig | None = None
    ):
        """Initialize the monitoring service."""
        self.secrets_manager = secrets_manager
        self.validation_service = validation_service
        self.config = config or AlertingConfig()

        # Monitoring state
        self.alert_rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.metric_history: list[MetricData] = []
        self.alert_history: list[Alert] = []

        # Alert rate limiting
        self.alert_counts: dict[str, list[datetime]] = {}
        self.last_alert_times: dict[str, datetime] = {}

        # Background tasks
        self.monitoring_task: asyncio.Task | None = None
        self.cleanup_task: asyncio.Task | None = None

        # Initialize alert rules
        self._initialize_alert_rules()

        logger.info("Secrets monitoring service initialized")

    def _initialize_alert_rules(self):
        """Initialize default alert rules."""
        default_rules = [
            AlertRule(
                name="secret_rotation_overdue",
                description="Secret rotation is overdue",
                metric=MonitoringMetric.ROTATION_OVERDUE,
                condition="value > 0",
                threshold=0,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                tags={"category": "compliance", "automation": "rotation"}
            ),
            AlertRule(
                name="high_secret_access_frequency",
                description="Unusually high secret access frequency detected",
                metric=MonitoringMetric.SECRET_ACCESS_FREQUENCY,
                condition="value > threshold",
                threshold=100,  # accesses per hour
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.SLACK, AlertChannel.WEBHOOK],
                tags={"category": "security", "type": "anomaly"}
            ),
            AlertRule(
                name="validation_failures_spike",
                description="High number of secret validation failures",
                metric=MonitoringMetric.VALIDATION_FAILURES,
                condition="value > threshold",
                threshold=5,  # failures in 15 minutes
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.PAGERDUTY],
                tags={"category": "security", "type": "validation"}
            ),
            AlertRule(
                name="encryption_health_degraded",
                description="Secrets encryption system health is degraded",
                metric=MonitoringMetric.ENCRYPTION_HEALTH,
                condition="value < threshold",
                threshold=0.95,  # 95% health threshold
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.PAGERDUTY, AlertChannel.SMS],
                tags={"category": "infrastructure", "type": "health"}
            ),
            AlertRule(
                name="backup_failure",
                description="Secrets backup operation failed",
                metric=MonitoringMetric.BACKUP_STATUS,
                condition="value == 0",
                threshold=0,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
                tags={"category": "backup", "type": "failure"}
            ),
            AlertRule(
                name="compliance_violation",
                description="Secrets compliance violation detected",
                metric=MonitoringMetric.COMPLIANCE_STATUS,
                condition="value < threshold",
                threshold=0.9,  # 90% compliance threshold
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.PAGERDUTY],
                tags={"category": "compliance", "type": "violation"}
            ),
            AlertRule(
                name="anomalous_access_pattern",
                description="Anomalous secret access pattern detected",
                metric=MonitoringMetric.ANOMALOUS_ACCESS,
                condition="value > threshold",
                threshold=0.8,  # 80% anomaly score
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                tags={"category": "security", "type": "anomaly"}
            ),
            AlertRule(
                name="decryption_failures",
                description="Multiple secret decryption failures",
                metric=MonitoringMetric.FAILED_DECRYPTIONS,
                condition="value > threshold",
                threshold=3,  # failures in 5 minutes
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.PAGERDUTY, AlertChannel.EMAIL],
                tags={"category": "security", "type": "encryption"}
            )
        ]

        for rule in default_rules:
            self.alert_rules[rule.name] = rule

        logger.info(f"Initialized {len(default_rules)} alert rules")

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Started secrets monitoring background tasks")

    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped secrets monitoring background tasks")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while True:
            try:
                await self._collect_metrics()
                await self._evaluate_alert_rules()
                await self._process_alerts()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _cleanup_loop(self):
        """Cleanup loop for old metrics and alerts."""
        while True:
            try:
                await self._cleanup_old_data()
                await asyncio.sleep(3600)  # Cleanup every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)

    async def _collect_metrics(self):
        """Collect monitoring metrics."""
        try:
            # Get secrets health status
            health_status = self.secrets_manager.health_check()

            # Encryption health metric
            encryption_health = 1.0 if health_status.get("overall_status") == "healthy" else 0.0
            self._record_metric(MonitoringMetric.ENCRYPTION_HEALTH, encryption_health)

            # Get audit trail for recent activities
            recent_audit = self.secrets_manager.get_audit_trail(
                start_time=datetime.utcnow() - timedelta(minutes=15)
            )

            # Access frequency metrics
            access_operations = [e for e in recent_audit if e.get("operation") == "decrypt"]
            access_frequency = len(access_operations)
            self._record_metric(MonitoringMetric.SECRET_ACCESS_FREQUENCY, access_frequency)

            # Validation failures
            failed_operations = [e for e in recent_audit if not e.get("success", True)]
            validation_failures = len(failed_operations)
            self._record_metric(MonitoringMetric.VALIDATION_FAILURES, validation_failures)

            # Decryption failures
            decryption_failures = len([
                e for e in recent_audit
                if e.get("operation") == "decrypt" and not e.get("success", True)
            ])
            self._record_metric(MonitoringMetric.FAILED_DECRYPTIONS, decryption_failures)

            # Check for overdue rotations
            await self._check_rotation_status()

            # Check compliance status
            await self._check_compliance_status()

            # Analyze access patterns for anomalies
            await self._analyze_access_patterns(recent_audit)

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def _check_rotation_status(self):
        """Check if any secrets need rotation."""
        try:
            # Get secrets that need rotation
            secrets_needing_rotation = self.secrets_manager.check_rotation_needed()
            overdue_count = len(secrets_needing_rotation)

            self._record_metric(MonitoringMetric.ROTATION_OVERDUE, overdue_count)

            # Record individual secret ages
            for secret_name, metadata in secrets_needing_rotation:
                if metadata.last_rotated:
                    age_days = (datetime.utcnow() - metadata.last_rotated).days
                else:
                    age_days = (datetime.utcnow() - metadata.created_at).days

                self._record_metric(
                    MonitoringMetric.SECRET_AGE,
                    age_days,
                    labels={"secret_name": secret_name}
                )

        except Exception as e:
            logger.error(f"Error checking rotation status: {e}")

    async def _check_compliance_status(self):
        """Check secrets compliance status."""
        try:
            # This would typically validate current secrets in production
            # For now, we'll simulate a compliance check
            test_secrets = {
                "database_password": "SecureDbPassword123!",
                "jwt_secret": "super_secure_jwt_signing_key_2023",
                "encryption_key": "encryption_key_with_256_bit_strength_abc123"
            }

            validation_results = await self.validation_service.validate_environment_secrets(
                test_secrets, "production"
            )

            # Calculate overall compliance score
            total_secrets = len(validation_results)
            compliant_secrets = len([
                r for r in validation_results.values()
                if r.overall_status == "pass"
            ])

            compliance_score = compliant_secrets / total_secrets if total_secrets > 0 else 0.0
            self._record_metric(MonitoringMetric.COMPLIANCE_STATUS, compliance_score)

        except Exception as e:
            logger.error(f"Error checking compliance status: {e}")
            self._record_metric(MonitoringMetric.COMPLIANCE_STATUS, 0.0)

    async def _analyze_access_patterns(self, audit_entries: list[dict[str, Any]]):
        """Analyze access patterns for anomalies."""
        try:
            # Simple anomaly detection based on access patterns
            access_times = []
            access_ips = []
            access_secrets = []

            for entry in audit_entries:
                if entry.get("operation") == "decrypt":
                    timestamp_str = entry.get("timestamp", "")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            access_times.append(timestamp.hour)
                        except:
                            continue

                    # In real implementation, extract IP from request context
                    # access_ips.append(entry.get("source_ip", "unknown"))
                    access_secrets.append(entry.get("key", "unknown"))

            # Check for unusual access times (e.g., middle of the night)
            unusual_hours = len([h for h in access_times if h < 6 or h > 22])
            unusual_ratio = unusual_hours / len(access_times) if access_times else 0

            # Check for repeated access to same secret
            if access_secrets:
                from collections import Counter
                secret_counts = Counter(access_secrets)
                max_access_count = max(secret_counts.values()) if secret_counts else 0
                high_frequency_ratio = (max_access_count / len(access_secrets)) if access_secrets else 0
            else:
                high_frequency_ratio = 0

            # Simple anomaly score (0-1, higher is more anomalous)
            anomaly_score = min(1.0, (unusual_ratio * 0.5) + (high_frequency_ratio * 0.5))

            self._record_metric(MonitoringMetric.ANOMALOUS_ACCESS, anomaly_score)

        except Exception as e:
            logger.error(f"Error analyzing access patterns: {e}")
            self._record_metric(MonitoringMetric.ANOMALOUS_ACCESS, 0.0)

    def _record_metric(
        self,
        metric: MonitoringMetric,
        value: float,
        labels: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None
    ):
        """Record a metric data point."""
        metric_data = MetricData(
            metric=metric,
            value=value,
            labels=labels or {},
            metadata=metadata or {}
        )
        self.metric_history.append(metric_data)

        # Keep only recent metrics (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.metric_history = [
            m for m in self.metric_history
            if m.timestamp >= cutoff_time
        ]

    async def _evaluate_alert_rules(self):
        """Evaluate alert rules against current metrics."""
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            try:
                # Check cooldown period
                last_alert_time = self.last_alert_times.get(rule_name)
                if last_alert_time:
                    cooldown_period = timedelta(minutes=rule.cooldown_minutes)
                    if datetime.utcnow() - last_alert_time < cooldown_period:
                        continue

                # Get recent metrics for this rule
                recent_metrics = [
                    m for m in self.metric_history
                    if (m.metric == rule.metric and
                        m.timestamp >= datetime.utcnow() - timedelta(minutes=15))
                ]

                if not recent_metrics:
                    continue

                # Get the latest metric value
                latest_metric = max(recent_metrics, key=lambda x: x.timestamp)

                # Evaluate condition
                should_alert = self._evaluate_condition(
                    latest_metric.value, rule.condition, rule.threshold
                )

                if should_alert:
                    await self._create_alert(rule, latest_metric)

            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule_name}: {e}")

    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
        try:
            # Replace placeholders in condition
            condition = condition.replace("value", str(value))
            condition = condition.replace("threshold", str(threshold))

            # Evaluate the condition
            return eval(condition)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    async def _create_alert(self, rule: AlertRule, metric: MetricData):
        """Create a new alert."""
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            message=f"{rule.description}: {metric.metric.value} = {metric.value}",
            details={
                "metric": metric.metric.value,
                "value": metric.value,
                "threshold": rule.threshold,
                "condition": rule.condition,
                "labels": metric.labels,
                "metadata": metric.metadata,
                "rule_tags": rule.tags
            }
        )

        # Check for rate limiting
        if not self._check_rate_limit(rule.name):
            logger.warning(f"Alert rate limit exceeded for rule: {rule.name}")
            return

        # Store alert
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        self.last_alert_times[rule.name] = datetime.utcnow()

        logger.warning(f"Created alert: {alert.alert_id} - {alert.message}")

        # Send notifications
        await self._send_alert_notifications(alert, rule.channels)

    def _check_rate_limit(self, rule_name: str) -> bool:
        """Check if alert is within rate limits."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Get alert count for this rule in the last hour
        if rule_name not in self.alert_counts:
            self.alert_counts[rule_name] = []

        # Clean old entries
        self.alert_counts[rule_name] = [
            t for t in self.alert_counts[rule_name] if t >= hour_ago
        ]

        # Check limit
        if len(self.alert_counts[rule_name]) >= self.config.max_alerts_per_hour:
            return False

        # Record this alert
        self.alert_counts[rule_name].append(now)
        return True

    async def _send_alert_notifications(self, alert: Alert, channels: list[AlertChannel]):
        """Send alert notifications to configured channels."""
        notification_tasks = []

        for channel in channels:
            if channel == AlertChannel.EMAIL:
                task = self._send_email_alert(alert)
            elif channel == AlertChannel.SLACK:
                task = self._send_slack_alert(alert)
            elif channel == AlertChannel.WEBHOOK:
                task = self._send_webhook_alert(alert)
            elif channel == AlertChannel.PAGERDUTY:
                task = self._send_pagerduty_alert(alert)
            elif channel == AlertChannel.LOG:
                task = self._log_alert(alert)
            else:
                continue

            notification_tasks.append(task)

        # Send notifications concurrently
        if notification_tasks:
            results = await asyncio.gather(*notification_tasks, return_exceptions=True)

            # Log any notification failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    channel = channels[i]
                    logger.error(f"Failed to send alert via {channel}: {result}")

    async def _send_email_alert(self, alert: Alert):
        """Send alert via email."""
        try:
            if not self.config.smtp_username or not self.config.smtp_password:
                return

            msg = MimeMultipart()
            msg['From'] = self.config.from_email
            msg['To'] = "admin@ai-pdf-scholar.com"  # Should be configurable
            msg['Subject'] = f"[{alert.severity.upper()}] Secrets Alert: {alert.rule_name}"

            body = f"""
            Alert Details:

            Rule: {alert.rule_name}
            Severity: {alert.severity.upper()}
            Message: {alert.message}
            Time: {alert.timestamp}
            Alert ID: {alert.alert_id}

            Details:
            {json.dumps(alert.details, indent=2)}

            This is an automated alert from the AI PDF Scholar secrets monitoring system.
            """

            msg.attach(MimeText(body, 'plain'))

            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            if self.config.smtp_use_tls:
                server.starttls()
            server.login(self.config.smtp_username, self.config.smtp_password)

            text = msg.as_string()
            server.sendmail(self.config.from_email, "admin@ai-pdf-scholar.com", text)
            server.quit()

            logger.info(f"Sent email alert: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    async def _send_slack_alert(self, alert: Alert):
        """Send alert via Slack webhook."""
        try:
            if not self.config.slack_webhook_url:
                return

            severity_colors = {
                AlertSeverity.CRITICAL: "#FF0000",
                AlertSeverity.HIGH: "#FF8800",
                AlertSeverity.MEDIUM: "#FFAA00",
                AlertSeverity.LOW: "#00AA00",
                AlertSeverity.INFO: "#0088AA"
            }

            payload = {
                "channel": self.config.slack_channel,
                "username": "Secrets Monitor",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": severity_colors.get(alert.severity, "#888888"),
                        "title": f"Secrets Alert: {alert.rule_name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.upper(),
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            }
                        ],
                        "footer": "AI PDF Scholar Secrets Monitor",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.slack_webhook_url,
                    json=payload,
                    timeout=self.config.webhook_timeout
                )
                response.raise_for_status()

            logger.info(f"Sent Slack alert: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    async def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook."""
        try:
            if not self.config.webhook_urls:
                return

            payload = {
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "details": alert.details,
                "source": "ai-pdf-scholar-secrets-monitor"
            }

            async with httpx.AsyncClient() as client:
                for webhook_url in self.config.webhook_urls:
                    try:
                        response = await client.post(
                            webhook_url,
                            json=payload,
                            timeout=self.config.webhook_timeout
                        )
                        response.raise_for_status()
                        logger.info(f"Sent webhook alert to {webhook_url}: {alert.alert_id}")
                    except Exception as e:
                        logger.error(f"Failed to send webhook alert to {webhook_url}: {e}")

        except Exception as e:
            logger.error(f"Failed to send webhook alerts: {e}")

    async def _send_pagerduty_alert(self, alert: Alert):
        """Send alert via PagerDuty."""
        try:
            if not self.config.pagerduty_integration_key:
                return

            payload = {
                "routing_key": self.config.pagerduty_integration_key,
                "event_action": "trigger",
                "dedup_key": f"secrets-alert-{alert.rule_name}",
                "payload": {
                    "summary": alert.message,
                    "severity": alert.severity,
                    "source": "ai-pdf-scholar-secrets-monitor",
                    "component": "secrets-management",
                    "group": "security",
                    "class": "secrets",
                    "custom_details": alert.details
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    timeout=self.config.webhook_timeout
                )
                response.raise_for_status()

            logger.info(f"Sent PagerDuty alert: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")

    async def _log_alert(self, alert: Alert):
        """Log alert to system logs."""
        logger.warning(
            f"SECRETS_ALERT: {alert.severity.upper()} - {alert.message} "
            f"[ID: {alert.alert_id}] [Rule: {alert.rule_name}]"
        )

    async def _process_alerts(self):
        """Process and manage active alerts."""
        # Auto-resolve alerts that are no longer triggering
        for alert_id, alert in list(self.active_alerts.items()):
            if alert.resolved:
                continue

            # Check if alert condition is still met
            rule = self.alert_rules.get(alert.rule_name)
            if not rule:
                continue

            # Get recent metrics
            recent_metrics = [
                m for m in self.metric_history
                if (m.metric.value == alert.details.get("metric") and
                    m.timestamp >= datetime.utcnow() - timedelta(minutes=5))
            ]

            if recent_metrics:
                latest_metric = max(recent_metrics, key=lambda x: x.timestamp)
                should_alert = self._evaluate_condition(
                    latest_metric.value, rule.condition, rule.threshold
                )

                if not should_alert:
                    # Auto-resolve alert
                    alert.resolved = True
                    alert.resolution_time = datetime.utcnow()
                    del self.active_alerts[alert_id]

                    logger.info(f"Auto-resolved alert: {alert_id}")

    async def _cleanup_old_data(self):
        """Clean up old metrics and alerts."""
        # Clean up old metrics (keep last 7 days)
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        old_count = len(self.metric_history)
        self.metric_history = [
            m for m in self.metric_history if m.timestamp >= cutoff_time
        ]
        new_count = len(self.metric_history)

        if old_count != new_count:
            logger.info(f"Cleaned up {old_count - new_count} old metrics")

        # Clean up old alerts
        alert_cutoff = datetime.utcnow() - timedelta(days=self.config.alert_retention_days)
        old_alert_count = len(self.alert_history)
        self.alert_history = [
            a for a in self.alert_history if a.timestamp >= alert_cutoff
        ]
        new_alert_count = len(self.alert_history)

        if old_alert_count != new_alert_count:
            logger.info(f"Cleaned up {old_alert_count - new_alert_count} old alerts")

    # Public API methods

    def add_alert_rule(self, rule: AlertRule):
        """Add a custom alert rule."""
        self.alert_rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def remove_alert_rule(self, rule_name: str):
        """Remove an alert rule."""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            logger.info(f"Removed alert rule: {rule_name}")

    def get_active_alerts(self) -> list[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        severity: AlertSeverity | None = None
    ) -> list[Alert]:
        """Get alert history with optional filtering."""
        alerts = self.alert_history

        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]

        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def get_metrics(
        self,
        metric: MonitoringMetric | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> list[MetricData]:
        """Get metric history with optional filtering."""
        metrics = self.metric_history

        if metric:
            metrics = [m for m in metrics if m.metric == metric]

        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]

        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]

        return metrics

    def get_monitoring_status(self) -> dict[str, Any]:
        """Get overall monitoring status."""
        return {
            "monitoring_active": self.monitoring_task and not self.monitoring_task.done(),
            "cleanup_active": self.cleanup_task and not self.cleanup_task.done(),
            "alert_rules_count": len(self.alert_rules),
            "active_alerts_count": len(self.active_alerts),
            "total_alerts_count": len(self.alert_history),
            "metrics_count": len(self.metric_history),
            "last_collection_time": max(
                [m.timestamp for m in self.metric_history], default=None
            ),
            "uptime": (datetime.utcnow() - datetime.utcnow()).total_seconds() if self.monitoring_task else 0
        }
