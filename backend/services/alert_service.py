"""
Multi-Channel Alert Service
Production-ready alerting with escalation logic and notification routing.
"""

import asyncio
import json
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

import aiohttp
import httpx
from jinja2 import Template

logger = logging.getLogger(__name__)


# ============================================================================
# Alert Types and Severities
# ============================================================================

class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertCategory(Enum):
    """Alert categories for routing."""
    SYSTEM = "system"
    APPLICATION = "application"
    SECURITY = "security"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Alert:
    """Alert data structure."""
    id: str
    name: str
    severity: AlertSeverity
    category: AlertCategory
    message: str
    description: str
    timestamp: datetime
    source: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    runbook_url: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None


@dataclass
class NotificationChannelConfig:
    """Configuration for notification channels."""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit: Optional[int] = None  # Max notifications per hour
    escalation_delay: Optional[int] = None  # Minutes before escalation


@dataclass
class AlertRule:
    """Alert routing and escalation rules."""
    name: str
    conditions: Dict[str, Any]
    channels: List[NotificationChannel]
    escalation_chain: List[NotificationChannel] = field(default_factory=list)
    escalation_delay: int = 30  # Minutes
    suppression_duration: int = 60  # Minutes
    enabled: bool = True


# ============================================================================
# Alert Service
# ============================================================================

class AlertService:
    """
    Multi-channel alert service with escalation logic.
    """

    def __init__(self):
        """Initialize alert service."""
        self.channels: Dict[NotificationChannel, NotificationChannelConfig] = {}
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.suppressed_alerts: Set[str] = set()
        self.notification_history: List[Dict[str, Any]] = []
        self.rate_limits: Dict[str, List[datetime]] = {}

        # Templates
        self.email_template = Template("""
        <html>
        <head><title>{{ alert.severity.value.upper() }} Alert: {{ alert.name }}</title></head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="background: {% if alert.severity.value == 'critical' %}#dc3545{% elif alert.severity.value == 'warning' %}#fd7e14{% else %}#17a2b8{% endif %}; color: white; padding: 15px; margin-bottom: 20px;">
                <h2>🚨 {{ alert.severity.value.upper() }} ALERT</h2>
                <h3>{{ alert.name }}</h3>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid {% if alert.severity.value == 'critical' %}#dc3545{% elif alert.severity.value == 'warning' %}#fd7e14{% else %}#17a2b8{% endif %};">
                <p><strong>Message:</strong> {{ alert.message }}</p>
                <p><strong>Description:</strong> {{ alert.description }}</p>
                <p><strong>Source:</strong> {{ alert.source }}</p>
                <p><strong>Time:</strong> {{ alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
                <p><strong>Category:</strong> {{ alert.category.value }}</p>

                {% if alert.runbook_url %}
                <p><strong>Runbook:</strong> <a href="{{ alert.runbook_url }}">View troubleshooting guide</a></p>
                {% endif %}

                {% if alert.labels %}
                <h4>Labels:</h4>
                <ul>
                {% for key, value in alert.labels.items() %}
                    <li><strong>{{ key }}:</strong> {{ value }}</li>
                {% endfor %}
                </ul>
                {% endif %}
            </div>

            <div style="margin-top: 20px; padding: 10px; background: #e9ecef; border-radius: 5px;">
                <small>This alert was generated by AI Enhanced PDF Scholar monitoring system.</small>
            </div>
        </body>
        </html>
        """)

        self.slack_template = Template("""
        {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "{{ alert.severity.value.upper() }} Alert: {{ alert.name }}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*Message:*\\n{{ alert.message }}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Source:*\\n{{ alert.source }}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Category:*\\n{{ alert.category.value }}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Time:*\\n{{ alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') }}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Description:*\\n{{ alert.description }}"
                    }
                }
                {% if alert.runbook_url %}
                ,{
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Runbook"
                            },
                            "url": "{{ alert.runbook_url }}"
                        }
                    ]
                }
                {% endif %}
            ]
        }
        """)

        # Initialize default rules
        self._setup_default_rules()

        logger.info("Alert service initialized")

    def configure_channel(
        self,
        channel: NotificationChannel,
        config: Dict[str, Any],
        enabled: bool = True,
        rate_limit: Optional[int] = None
    ):
        """Configure a notification channel."""
        self.channels[channel] = NotificationChannelConfig(
            channel=channel,
            enabled=enabled,
            config=config,
            rate_limit=rate_limit
        )

        logger.info(f"Configured {channel.value} notification channel")

    def add_rule(self, rule: AlertRule):
        """Add an alert routing rule."""
        self.rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")

    def _setup_default_rules(self):
        """Setup default alert routing rules."""
        # Critical alerts - immediate multi-channel notification
        critical_rule = AlertRule(
            name="critical-alerts",
            conditions={"severity": AlertSeverity.CRITICAL},
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            escalation_chain=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
            escalation_delay=5,  # 5 minutes
            suppression_duration=30
        )

        # Security alerts - security team notification
        security_rule = AlertRule(
            name="security-alerts",
            conditions={"category": AlertCategory.SECURITY},
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            escalation_chain=[NotificationChannel.PAGERDUTY],
            escalation_delay=10,
            suppression_duration=60
        )

        # Warning alerts - standard notification
        warning_rule = AlertRule(
            name="warning-alerts",
            conditions={"severity": AlertSeverity.WARNING},
            channels=[NotificationChannel.EMAIL],
            escalation_delay=30,
            suppression_duration=120
        )

        self.rules.extend([critical_rule, security_rule, warning_rule])

    # ========================================================================
    # Alert Processing
    # ========================================================================

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert through configured channels."""
        try:
            # Check if alert is suppressed
            if self._is_suppressed(alert):
                logger.debug(f"Alert {alert.id} is suppressed")
                return True

            # Store active alert
            self.active_alerts[alert.id] = alert

            # Find matching rules
            matching_rules = self._find_matching_rules(alert)

            if not matching_rules:
                logger.warning(f"No matching rules for alert {alert.id}")
                return False

            # Send notifications
            success = True
            for rule in matching_rules:
                rule_success = await self._send_alert_via_rule(alert, rule)
                success = success and rule_success

            # Schedule escalation if needed
            for rule in matching_rules:
                if rule.escalation_chain:
                    asyncio.create_task(
                        self._schedule_escalation(alert, rule)
                    )

            # Add to suppression list
            self._suppress_alert(alert, matching_rules[0])

            return success

        except Exception as e:
            logger.error(f"Failed to send alert {alert.id}: {e}")
            return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark alert as resolved."""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()

                # Send resolution notification
                await self._send_resolution_notification(alert)

                # Remove from active alerts
                del self.active_alerts[alert_id]

                logger.info(f"Alert {alert_id} resolved")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False

    def _find_matching_rules(self, alert: Alert) -> List[AlertRule]:
        """Find rules matching the alert."""
        matching_rules = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            matches = True
            for condition_key, condition_value in rule.conditions.items():
                alert_value = getattr(alert, condition_key, None)

                if alert_value != condition_value:
                    matches = False
                    break

            if matches:
                matching_rules.append(rule)

        return matching_rules

    async def _send_alert_via_rule(self, alert: Alert, rule: AlertRule) -> bool:
        """Send alert via channels defined in rule."""
        success = True

        for channel in rule.channels:
            if channel in self.channels and self.channels[channel].enabled:
                channel_success = await self._send_via_channel(alert, channel)
                success = success and channel_success
            else:
                logger.warning(f"Channel {channel.value} not configured or disabled")

        return success

    async def _send_via_channel(self, alert: Alert, channel: NotificationChannel) -> bool:
        """Send alert via specific channel."""
        try:
            # Check rate limits
            if not self._check_rate_limit(channel):
                logger.warning(f"Rate limit exceeded for {channel.value}")
                return False

            # Send notification
            if channel == NotificationChannel.EMAIL:
                return await self._send_email(alert)
            elif channel == NotificationChannel.SLACK:
                return await self._send_slack(alert)
            elif channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook(alert)
            elif channel == NotificationChannel.TEAMS:
                return await self._send_teams(alert)
            else:
                logger.warning(f"Channel {channel.value} not implemented")
                return False

        except Exception as e:
            logger.error(f"Failed to send alert via {channel.value}: {e}")
            return False

    # ========================================================================
    # Channel Implementations
    # ========================================================================

    async def _send_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            config = self.channels[NotificationChannel.EMAIL].config

            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"
            msg['From'] = config.get('from_address', 'alerts@ai-pdf-scholar.com')
            msg['To'] = config.get('to_address', 'alerts@ai-pdf-scholar.com')

            # Generate HTML content
            html_content = self.email_template.render(alert=alert)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            smtp_server = config.get('smtp_server', 'localhost')
            smtp_port = config.get('smtp_port', 587)
            username = config.get('username')
            password = config.get('password')

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)

                server.send_message(msg)

            self._record_notification(alert, NotificationChannel.EMAIL, True)
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            self._record_notification(alert, NotificationChannel.EMAIL, False, str(e))
            return False

    async def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            config = self.channels[NotificationChannel.SLACK].config
            webhook_url = config.get('webhook_url')

            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False

            # Generate Slack payload
            payload = json.loads(self.slack_template.render(alert=alert))

            # Color based on severity
            color_map = {
                AlertSeverity.CRITICAL: "danger",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.INFO: "good"
            }

            # Add color attachment for older Slack versions
            payload["attachments"] = [{
                "color": color_map.get(alert.severity, "good"),
                "fallback": f"{alert.severity.value.upper()}: {alert.message}"
            }]

            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()

            self._record_notification(alert, NotificationChannel.SLACK, True)
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            self._record_notification(alert, NotificationChannel.SLACK, False, str(e))
            return False

    async def _send_webhook(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            config = self.channels[NotificationChannel.WEBHOOK].config
            webhook_url = config.get('url')

            if not webhook_url:
                logger.error("Webhook URL not configured")
                return False

            # Create webhook payload
            payload = {
                "alert_id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "category": alert.category.value,
                "message": alert.message,
                "description": alert.description,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source,
                "labels": alert.labels,
                "annotations": alert.annotations,
                "runbook_url": alert.runbook_url
            }

            headers = config.get('headers', {})
            auth = config.get('auth')

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    auth=auth if auth else None,
                    timeout=30
                )
                response.raise_for_status()

            self._record_notification(alert, NotificationChannel.WEBHOOK, True)
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            self._record_notification(alert, NotificationChannel.WEBHOOK, False, str(e))
            return False

    async def _send_teams(self, alert: Alert) -> bool:
        """Send alert to Microsoft Teams."""
        try:
            config = self.channels[NotificationChannel.TEAMS].config
            webhook_url = config.get('webhook_url')

            if not webhook_url:
                logger.error("Teams webhook URL not configured")
                return False

            # Create Teams payload
            color_map = {
                AlertSeverity.CRITICAL: "attention",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.INFO: "good"
            }

            payload = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": f"{alert.severity.value.upper()}: {alert.name}",
                "themeColor": {
                    AlertSeverity.CRITICAL: "FF0000",
                    AlertSeverity.WARNING: "FFA500",
                    AlertSeverity.INFO: "0078D4"
                }.get(alert.severity, "0078D4"),
                "sections": [{
                    "activityTitle": f"🚨 {alert.severity.value.upper()} Alert",
                    "activitySubtitle": alert.name,
                    "facts": [
                        {"name": "Message", "value": alert.message},
                        {"name": "Source", "value": alert.source},
                        {"name": "Category", "value": alert.category.value},
                        {"name": "Time", "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
                    ],
                    "text": alert.description
                }]
            }

            if alert.runbook_url:
                payload["potentialAction"] = [{
                    "@type": "OpenUri",
                    "name": "View Runbook",
                    "targets": [{"os": "default", "uri": alert.runbook_url}]
                }]

            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()

            self._record_notification(alert, NotificationChannel.TEAMS, True)
            return True

        except Exception as e:
            logger.error(f"Failed to send Teams alert: {e}")
            self._record_notification(alert, NotificationChannel.TEAMS, False, str(e))
            return False

    # ========================================================================
    # Escalation Logic
    # ========================================================================

    async def _schedule_escalation(self, alert: Alert, rule: AlertRule):
        """Schedule escalation for unresolved alert."""
        try:
            # Wait for escalation delay
            await asyncio.sleep(rule.escalation_delay * 60)

            # Check if alert is still active and not escalated
            if (alert.id in self.active_alerts and
                not self.active_alerts[alert.id].escalated and
                not self.active_alerts[alert.id].resolved):

                # Mark as escalated
                self.active_alerts[alert.id].escalated = True
                self.active_alerts[alert.id].escalated_at = datetime.utcnow()

                # Send escalation notifications
                for channel in rule.escalation_chain:
                    if channel in self.channels and self.channels[channel].enabled:
                        await self._send_escalation_notification(alert, channel)

                logger.info(f"Alert {alert.id} escalated")

        except Exception as e:
            logger.error(f"Failed to escalate alert {alert.id}: {e}")

    async def _send_escalation_notification(self, alert: Alert, channel: NotificationChannel):
        """Send escalation notification."""
        # Create escalated alert with modified message
        escalated_alert = Alert(
            id=f"{alert.id}_escalated",
            name=f"ESCALATED: {alert.name}",
            severity=alert.severity,
            category=alert.category,
            message=f"ESCALATED ALERT: {alert.message}",
            description=f"This alert has been escalated due to no resolution. Original: {alert.description}",
            timestamp=datetime.utcnow(),
            source=alert.source,
            labels=alert.labels,
            annotations=alert.annotations,
            runbook_url=alert.runbook_url
        )

        await self._send_via_channel(escalated_alert, channel)

    async def _send_resolution_notification(self, alert: Alert):
        """Send alert resolution notification."""
        try:
            resolution_alert = Alert(
                id=f"{alert.id}_resolved",
                name=f"RESOLVED: {alert.name}",
                severity=AlertSeverity.INFO,
                category=alert.category,
                message=f"Alert has been resolved: {alert.message}",
                description=f"Alert resolved at {alert.resolved_at}",
                timestamp=datetime.utcnow(),
                source=alert.source,
                labels=alert.labels,
                annotations=alert.annotations,
                runbook_url=alert.runbook_url,
                resolved=True
            )

            # Send to same channels as original alert
            matching_rules = self._find_matching_rules(alert)
            for rule in matching_rules:
                await self._send_alert_via_rule(resolution_alert, rule)

        except Exception as e:
            logger.error(f"Failed to send resolution notification: {e}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _is_suppressed(self, alert: Alert) -> bool:
        """Check if alert is suppressed."""
        return alert.id in self.suppressed_alerts

    def _suppress_alert(self, alert: Alert, rule: AlertRule):
        """Add alert to suppression list."""
        self.suppressed_alerts.add(alert.id)

        # Schedule removal from suppression
        async def remove_suppression():
            await asyncio.sleep(rule.suppression_duration * 60)
            if alert.id in self.suppressed_alerts:
                self.suppressed_alerts.remove(alert.id)

        asyncio.create_task(remove_suppression())

    def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """Check if channel rate limit allows notification."""
        config = self.channels.get(channel)
        if not config or not config.rate_limit:
            return True

        now = datetime.utcnow()
        channel_key = channel.value

        # Clean old entries
        if channel_key in self.rate_limits:
            cutoff = now - timedelta(hours=1)
            self.rate_limits[channel_key] = [
                ts for ts in self.rate_limits[channel_key] if ts > cutoff
            ]
        else:
            self.rate_limits[channel_key] = []

        # Check limit
        if len(self.rate_limits[channel_key]) >= config.rate_limit:
            return False

        # Add current timestamp
        self.rate_limits[channel_key].append(now)
        return True

    def _record_notification(
        self,
        alert: Alert,
        channel: NotificationChannel,
        success: bool,
        error: Optional[str] = None
    ):
        """Record notification attempt in history."""
        record = {
            "alert_id": alert.id,
            "channel": channel.value,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error
        }

        self.notification_history.append(record)

        # Keep only last 1000 records
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-1000:]

    # ========================================================================
    # Management Methods
    # ========================================================================

    def get_active_alerts(self) -> Dict[str, Alert]:
        """Get all active alerts."""
        return self.active_alerts.copy()

    def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get notification history."""
        return self.notification_history[-limit:]

    def get_channel_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for each channel."""
        stats = {}

        for channel, config in self.channels.items():
            channel_notifications = [
                record for record in self.notification_history
                if record["channel"] == channel.value
            ]

            successful = sum(1 for record in channel_notifications if record["success"])
            failed = len(channel_notifications) - successful

            stats[channel.value] = {
                "enabled": config.enabled,
                "total_notifications": len(channel_notifications),
                "successful": successful,
                "failed": failed,
                "success_rate": successful / len(channel_notifications) if channel_notifications else 0,
                "rate_limit": config.rate_limit
            }

        return stats


# ============================================================================
# Utility Functions
# ============================================================================

def create_alert(
    name: str,
    severity: AlertSeverity,
    category: AlertCategory,
    message: str,
    description: str,
    source: str = "ai-pdf-scholar",
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
    runbook_url: Optional[str] = None
) -> Alert:
    """Create a new alert."""
    return Alert(
        id=f"{name}_{int(time.time())}",
        name=name,
        severity=severity,
        category=category,
        message=message,
        description=description,
        timestamp=datetime.utcnow(),
        source=source,
        labels=labels or {},
        annotations=annotations or {},
        runbook_url=runbook_url
    )


# ============================================================================
# Singleton Instance
# ============================================================================

_alert_service_instance: Optional[AlertService] = None

def get_alert_service() -> AlertService:
    """Get or create the global alert service instance."""
    global _alert_service_instance

    if _alert_service_instance is None:
        _alert_service_instance = AlertService()

    return _alert_service_instance


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        alert_service = AlertService()

        # Configure email channel
        alert_service.configure_channel(
            NotificationChannel.EMAIL,
            {
                "from_address": "alerts@ai-pdf-scholar.com",
                "to_address": "admin@ai-pdf-scholar.com",
                "smtp_server": "localhost",
                "smtp_port": 587
            }
        )

        # Create test alert
        test_alert = create_alert(
            name="TestAlert",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.SYSTEM,
            message="This is a test alert",
            description="Testing the alert system functionality",
            labels={"instance": "localhost", "service": "test"}
        )

        # Send alert
        success = await alert_service.send_alert(test_alert)
        print(f"Alert sent: {success}")

        # Get stats
        stats = alert_service.get_channel_stats()
        print(f"Channel stats: {stats}")

    asyncio.run(main())