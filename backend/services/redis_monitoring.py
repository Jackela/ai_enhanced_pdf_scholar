"""
Comprehensive Redis Monitoring Service
Real-time monitoring, alerting, and performance tracking for Redis cluster.
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import redis
from redis import Redis, RedisError
from redis.cluster import RedisCluster

# Import our services
from .metrics_service import MetricsService
from .redis_cluster_manager import RedisClusterManager

logger = logging.getLogger(__name__)


# ============================================================================
# Monitoring Configuration
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class MetricType(str, Enum):
    """Types of Redis metrics."""
    MEMORY = "memory"
    PERFORMANCE = "performance"
    CONNECTIONS = "connections"
    REPLICATION = "replication"
    PERSISTENCE = "persistence"
    NETWORK = "network"
    CLUSTER = "cluster"


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric_path: str  # e.g., "used_memory_percent"
    operator: str  # gt, lt, eq, ne
    threshold: float
    severity: AlertSeverity
    message_template: str
    cooldown_minutes: int = 5
    enabled: bool = True

    # Internal state
    last_triggered: Optional[datetime] = None
    triggered_count: int = 0

    def check_threshold(self, value: float) -> bool:
        """Check if value triggers the alert."""
        if self.operator == "gt":
            return value > self.threshold
        elif self.operator == "lt":
            return value < self.threshold
        elif self.operator == "eq":
            return value == self.threshold
        elif self.operator == "ne":
            return value != self.threshold
        return False

    def is_in_cooldown(self) -> bool:
        """Check if alert is in cooldown period."""
        if not self.last_triggered:
            return False

        cooldown_end = self.last_triggered + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() < cooldown_end

    def trigger(self) -> str:
        """Trigger the alert and return formatted message."""
        self.last_triggered = datetime.utcnow()
        self.triggered_count += 1

        return self.message_template.format(
            name=self.name,
            threshold=self.threshold,
            severity=self.severity.value,
            timestamp=self.last_triggered.isoformat()
        )


@dataclass
class RedisMetricsSnapshot:
    """Snapshot of Redis metrics at a point in time."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    node_id: str = "default"

    # Memory metrics
    used_memory: int = 0
    used_memory_human: str = "0B"
    used_memory_rss: int = 0
    used_memory_peak: int = 0
    used_memory_lua: int = 0
    mem_fragmentation_ratio: float = 1.0
    maxmemory: int = 0
    used_memory_percent: float = 0.0

    # Performance metrics
    instantaneous_ops_per_sec: int = 0
    total_commands_processed: int = 0
    instantaneous_input_kbps: float = 0.0
    instantaneous_output_kbps: float = 0.0
    keyspace_hits: int = 0
    keyspace_misses: int = 0
    keyspace_hit_ratio: float = 0.0

    # Connection metrics
    connected_clients: int = 0
    client_recent_max_input_buffer: int = 0
    client_recent_max_output_buffer: int = 0
    blocked_clients: int = 0

    # Server metrics
    uptime_in_seconds: int = 0
    uptime_in_days: int = 0
    hz: int = 10
    lru_clock: int = 0

    # Replication metrics
    role: str = "master"
    connected_slaves: int = 0
    master_replid: str = ""
    master_repl_offset: int = 0
    repl_backlog_active: int = 0
    repl_backlog_size: int = 0

    # Persistence metrics
    rdb_changes_since_last_save: int = 0
    rdb_bgsave_in_progress: int = 0
    rdb_last_save_time: int = 0
    rdb_last_bgsave_status: str = "ok"
    aof_enabled: int = 0
    aof_rewrite_in_progress: int = 0
    aof_last_rewrite_time_sec: int = 0
    aof_current_size: int = 0

    # Cluster metrics (if applicable)
    cluster_enabled: int = 0
    cluster_state: str = "ok"
    cluster_slots_assigned: int = 0
    cluster_slots_ok: int = 0
    cluster_known_nodes: int = 0

    # Network metrics
    total_net_input_bytes: int = 0
    total_net_output_bytes: int = 0

    # Error metrics
    errorstats: Dict[str, int] = field(default_factory=dict)

    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw data."""
        # Memory percentage
        if self.maxmemory > 0:
            self.used_memory_percent = (self.used_memory / self.maxmemory) * 100

        # Hit ratio
        total_hits = self.keyspace_hits + self.keyspace_misses
        if total_hits > 0:
            self.keyspace_hit_ratio = (self.keyspace_hits / total_hits) * 100

        # Uptime in days
        self.uptime_in_days = self.uptime_in_seconds // 86400

    @classmethod
    def from_redis_info(cls, info_dict: Dict[str, Any], node_id: str = "default") -> 'RedisMetricsSnapshot':
        """Create metrics snapshot from Redis INFO output."""
        snapshot = cls(node_id=node_id)

        # Map Redis INFO fields to snapshot attributes
        field_mapping = {
            # Memory
            'used_memory': 'used_memory',
            'used_memory_human': 'used_memory_human',
            'used_memory_rss': 'used_memory_rss',
            'used_memory_peak': 'used_memory_peak',
            'used_memory_lua': 'used_memory_lua',
            'mem_fragmentation_ratio': 'mem_fragmentation_ratio',
            'maxmemory': 'maxmemory',

            # Performance
            'instantaneous_ops_per_sec': 'instantaneous_ops_per_sec',
            'total_commands_processed': 'total_commands_processed',
            'instantaneous_input_kbps': 'instantaneous_input_kbps',
            'instantaneous_output_kbps': 'instantaneous_output_kbps',
            'keyspace_hits': 'keyspace_hits',
            'keyspace_misses': 'keyspace_misses',

            # Connections
            'connected_clients': 'connected_clients',
            'client_recent_max_input_buffer': 'client_recent_max_input_buffer',
            'client_recent_max_output_buffer': 'client_recent_max_output_buffer',
            'blocked_clients': 'blocked_clients',

            # Server
            'uptime_in_seconds': 'uptime_in_seconds',
            'hz': 'hz',
            'lru_clock': 'lru_clock',

            # Replication
            'role': 'role',
            'connected_slaves': 'connected_slaves',
            'master_replid': 'master_replid',
            'master_repl_offset': 'master_repl_offset',
            'repl_backlog_active': 'repl_backlog_active',
            'repl_backlog_size': 'repl_backlog_size',

            # Persistence
            'rdb_changes_since_last_save': 'rdb_changes_since_last_save',
            'rdb_bgsave_in_progress': 'rdb_bgsave_in_progress',
            'rdb_last_save_time': 'rdb_last_save_time',
            'rdb_last_bgsave_status': 'rdb_last_bgsave_status',
            'aof_enabled': 'aof_enabled',
            'aof_rewrite_in_progress': 'aof_rewrite_in_progress',
            'aof_last_rewrite_time_sec': 'aof_last_rewrite_time_sec',
            'aof_current_size': 'aof_current_size',

            # Cluster
            'cluster_enabled': 'cluster_enabled',
            'cluster_state': 'cluster_state',
            'cluster_slots_assigned': 'cluster_slots_assigned',
            'cluster_slots_ok': 'cluster_slots_ok',
            'cluster_known_nodes': 'cluster_known_nodes',

            # Network
            'total_net_input_bytes': 'total_net_input_bytes',
            'total_net_output_bytes': 'total_net_output_bytes'
        }

        # Set attributes from info dict
        for info_key, attr_name in field_mapping.items():
            if info_key in info_dict:
                setattr(snapshot, attr_name, info_dict[info_key])

        # Handle errorstats section
        if 'errorstats_ERR' in info_dict:
            snapshot.errorstats = {
                k.replace('errorstats_', ''): v
                for k, v in info_dict.items()
                if k.startswith('errorstats_')
            }

        # Calculate derived metrics
        snapshot.calculate_derived_metrics()

        return snapshot


# ============================================================================
# Redis Monitoring Service
# ============================================================================

class RedisMonitoringService:
    """
    Comprehensive Redis monitoring service with real-time metrics,
    alerting, and performance tracking.
    """

    def __init__(
        self,
        cluster_manager: Optional[RedisClusterManager] = None,
        metrics_service: Optional[MetricsService] = None,
        alert_handlers: Optional[List[Callable[[str, AlertSeverity, str], None]]] = None
    ):
        """Initialize Redis monitoring service."""
        self.cluster_manager = cluster_manager
        self.metrics_service = metrics_service
        self.alert_handlers = alert_handlers or []

        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 30.0  # seconds

        # Metrics storage (ring buffers for efficiency)
        self.metrics_history: Dict[str, deque] = {}
        self.max_history_size = 1000  # Keep last 1000 data points

        # Alert rules
        self.alert_rules: List[AlertRule] = []
        self._load_default_alert_rules()

        # Performance baselines
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.baseline_window_hours = 24

        logger.info("Redis Monitoring Service initialized")

    def _load_default_alert_rules(self):
        """Load default alert rules."""
        default_rules = [
            # Memory alerts
            AlertRule(
                name="High Memory Usage",
                metric_path="used_memory_percent",
                operator="gt",
                threshold=85.0,
                severity=AlertSeverity.WARNING,
                message_template="Redis memory usage is {threshold}% (threshold: {threshold}%)",
                cooldown_minutes=5
            ),
            AlertRule(
                name="Critical Memory Usage",
                metric_path="used_memory_percent",
                operator="gt",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                message_template="CRITICAL: Redis memory usage is {threshold}% (threshold: {threshold}%)",
                cooldown_minutes=2
            ),
            AlertRule(
                name="High Memory Fragmentation",
                metric_path="mem_fragmentation_ratio",
                operator="gt",
                threshold=1.5,
                severity=AlertSeverity.WARNING,
                message_template="High memory fragmentation ratio: {threshold} (threshold: {threshold})",
                cooldown_minutes=10
            ),

            # Performance alerts
            AlertRule(
                name="Low Hit Ratio",
                metric_path="keyspace_hit_ratio",
                operator="lt",
                threshold=80.0,
                severity=AlertSeverity.WARNING,
                message_template="Low cache hit ratio: {threshold}% (threshold: {threshold}%)",
                cooldown_minutes=15
            ),
            AlertRule(
                name="High Operations Rate",
                metric_path="instantaneous_ops_per_sec",
                operator="gt",
                threshold=10000,
                severity=AlertSeverity.INFO,
                message_template="High operations rate: {threshold} ops/sec (threshold: {threshold})",
                cooldown_minutes=30
            ),

            # Connection alerts
            AlertRule(
                name="High Client Connections",
                metric_path="connected_clients",
                operator="gt",
                threshold=1000,
                severity=AlertSeverity.WARNING,
                message_template="High client connections: {threshold} (threshold: {threshold})",
                cooldown_minutes=5
            ),
            AlertRule(
                name="Blocked Clients",
                metric_path="blocked_clients",
                operator="gt",
                threshold=100,
                severity=AlertSeverity.WARNING,
                message_template="High blocked clients: {threshold} (threshold: {threshold})",
                cooldown_minutes=5
            ),

            # Persistence alerts
            AlertRule(
                name="RDB Save Failed",
                metric_path="rdb_last_bgsave_status",
                operator="ne",
                threshold="ok",
                severity=AlertSeverity.CRITICAL,
                message_template="RDB background save failed",
                cooldown_minutes=1
            ),
            AlertRule(
                name="High Unsaved Changes",
                metric_path="rdb_changes_since_last_save",
                operator="gt",
                threshold=50000,
                severity=AlertSeverity.WARNING,
                message_template="High unsaved changes: {threshold} (threshold: {threshold})",
                cooldown_minutes=30
            ),

            # Cluster alerts (if applicable)
            AlertRule(
                name="Cluster State Unhealthy",
                metric_path="cluster_state",
                operator="ne",
                threshold="ok",
                severity=AlertSeverity.CRITICAL,
                message_template="Cluster state is not OK",
                cooldown_minutes=1
            )
        ]

        self.alert_rules = default_rules

    # ========================================================================
    # Monitoring Control
    # ========================================================================

    async def start_monitoring(self, interval_seconds: float = 30.0):
        """Start continuous Redis monitoring."""
        if self.is_monitoring:
            logger.warning("Monitoring is already running")
            return

        self.monitoring_interval = interval_seconds
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info(f"Started Redis monitoring with {interval_seconds}s interval")

    async def stop_monitoring(self):
        """Stop continuous Redis monitoring."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped Redis monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Collect metrics from all nodes
                await self._collect_all_metrics()

                # Check alert rules
                await self._check_alerts()

                # Update performance baselines
                await self._update_baselines()

                # Export metrics to external systems
                await self._export_metrics()

                # Wait for next collection
                await asyncio.sleep(self.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Short delay on error

    # ========================================================================
    # Metrics Collection
    # ========================================================================

    async def _collect_all_metrics(self):
        """Collect metrics from all Redis nodes."""
        if self.cluster_manager:
            # Collect from cluster manager
            cluster_info = await self.cluster_manager.get_cluster_info()

            for node_id, node_info in cluster_info.get("nodes", {}).items():
                if node_info.get("is_healthy", False):
                    client = self.cluster_manager.get_node_client(node_id)
                    if client:
                        await self._collect_node_metrics(client, node_id)
        else:
            # Single node monitoring - would need client injection
            logger.warning("No cluster manager provided for monitoring")

    async def _collect_node_metrics(self, client: Union[Redis, RedisCluster], node_id: str):
        """Collect metrics from a specific Redis node."""
        try:
            # Get Redis INFO
            info = await asyncio.to_thread(client.info)

            # Create metrics snapshot
            snapshot = RedisMetricsSnapshot.from_redis_info(info, node_id)

            # Store in history
            if node_id not in self.metrics_history:
                self.metrics_history[node_id] = deque(maxlen=self.max_history_size)

            self.metrics_history[node_id].append(snapshot)

            # Export to external metrics service
            if self.metrics_service:
                await self._export_node_metrics(snapshot)

            logger.debug(f"Collected metrics from node {node_id}")

        except Exception as e:
            logger.error(f"Failed to collect metrics from node {node_id}: {e}")

    async def _export_node_metrics(self, snapshot: RedisMetricsSnapshot):
        """Export node metrics to external metrics service."""
        try:
            # Record memory metrics
            self.metrics_service.update_cache_size(
                "redis",
                snapshot.used_memory
            )

            # Record performance metrics
            self.metrics_service.record_cache_operation(
                operation="health_check",
                cache_type="redis",
                hit=snapshot.keyspace_hit_ratio > 80,
                duration=0.001  # Monitoring overhead
            )

            # Record connection metrics
            if hasattr(self.metrics_service.metrics, 'db_connections_active'):
                self.metrics_service.metrics.db_connections_active.labels(
                    db_type="redis"
                ).set(snapshot.connected_clients)

            # Record custom metrics
            if hasattr(self.metrics_service.metrics, 'cache_hits_total'):
                self.metrics_service.metrics.cache_hits_total.labels(
                    cache_type="redis",
                    key_pattern="all"
                )._value._value = snapshot.keyspace_hits

                self.metrics_service.metrics.cache_misses_total.labels(
                    cache_type="redis",
                    key_pattern="all"
                )._value._value = snapshot.keyspace_misses

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")

    # ========================================================================
    # Alert Management
    # ========================================================================

    async def _check_alerts(self):
        """Check all alert rules against current metrics."""
        for node_id, history in self.metrics_history.items():
            if not history:
                continue

            latest_snapshot = history[-1]

            for rule in self.alert_rules:
                if not rule.enabled or rule.is_in_cooldown():
                    continue

                # Get metric value
                try:
                    value = self._get_metric_value(latest_snapshot, rule.metric_path)
                    if value is None:
                        continue

                    # Check threshold
                    if rule.check_threshold(value):
                        message = rule.trigger()
                        await self._send_alert(rule.severity, f"Node {node_id}: {message}")

                except Exception as e:
                    logger.error(f"Error checking alert rule {rule.name}: {e}")

    def _get_metric_value(self, snapshot: RedisMetricsSnapshot, metric_path: str) -> Any:
        """Get metric value from snapshot using dot notation path."""
        try:
            return getattr(snapshot, metric_path)
        except AttributeError:
            return None

    async def _send_alert(self, severity: AlertSeverity, message: str):
        """Send alert to all registered handlers."""
        timestamp = datetime.utcnow().isoformat()

        # Log alert
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }
        logger.log(log_level[severity], f"ALERT [{severity.value.upper()}]: {message}")

        # Send to external handlers
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message, severity, timestamp)
                else:
                    handler(message, severity, timestamp)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def add_alert_rule(self, rule: AlertRule):
        """Add a new alert rule."""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")

    def remove_alert_rule(self, rule_name: str) -> bool:
        """Remove an alert rule by name."""
        initial_count = len(self.alert_rules)
        self.alert_rules = [r for r in self.alert_rules if r.name != rule_name]

        removed = len(self.alert_rules) < initial_count
        if removed:
            logger.info(f"Removed alert rule: {rule_name}")

        return removed

    def add_alert_handler(self, handler: Callable[[str, AlertSeverity, str], None]):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)

    # ========================================================================
    # Performance Baselines
    # ========================================================================

    async def _update_baselines(self):
        """Update performance baselines from historical data."""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.baseline_window_hours)

        for node_id, history in self.metrics_history.items():
            # Filter recent data
            recent_data = [
                snapshot for snapshot in history
                if snapshot.timestamp > cutoff_time
            ]

            if len(recent_data) < 10:  # Need enough data points
                continue

            # Calculate baselines
            baselines = {
                "avg_ops_per_sec": sum(s.instantaneous_ops_per_sec for s in recent_data) / len(recent_data),
                "avg_hit_ratio": sum(s.keyspace_hit_ratio for s in recent_data) / len(recent_data),
                "avg_memory_usage": sum(s.used_memory_percent for s in recent_data) / len(recent_data),
                "avg_connections": sum(s.connected_clients for s in recent_data) / len(recent_data),
                "avg_fragmentation": sum(s.mem_fragmentation_ratio for s in recent_data) / len(recent_data)
            }

            self.baselines[node_id] = baselines

    # ========================================================================
    # Data Export and API
    # ========================================================================

    async def _export_metrics(self):
        """Export metrics to external systems."""
        # This could export to time-series databases, monitoring systems, etc.
        pass

    def get_current_metrics(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current metrics for a node or all nodes."""
        if node_id:
            history = self.metrics_history.get(node_id)
            if not history:
                return {}

            latest = history[-1]
            return {
                "node_id": node_id,
                "timestamp": latest.timestamp.isoformat(),
                "metrics": asdict(latest)
            }
        else:
            # Return all nodes
            result = {}
            for nid, history in self.metrics_history.items():
                if history:
                    latest = history[-1]
                    result[nid] = {
                        "timestamp": latest.timestamp.isoformat(),
                        "metrics": asdict(latest)
                    }
            return result

    def get_metrics_history(
        self,
        node_id: str,
        hours: int = 1
    ) -> List[Dict[str, Any]]:
        """Get metrics history for a node."""
        history = self.metrics_history.get(node_id)
        if not history:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        return [
            {
                "timestamp": snapshot.timestamp.isoformat(),
                "metrics": asdict(snapshot)
            }
            for snapshot in history
            if snapshot.timestamp > cutoff_time
        ]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all nodes."""
        summary = {
            "total_nodes": len(self.metrics_history),
            "healthy_nodes": 0,
            "total_memory_mb": 0,
            "total_ops_per_sec": 0,
            "avg_hit_ratio": 0.0,
            "total_connections": 0,
            "alerts_active": len([r for r in self.alert_rules if r.last_triggered]),
            "last_update": None
        }

        if not self.metrics_history:
            return summary

        hit_ratios = []
        latest_time = None

        for history in self.metrics_history.values():
            if not history:
                continue

            latest = history[-1]

            # Update latest time
            if latest_time is None or latest.timestamp > latest_time:
                latest_time = latest.timestamp

            # Check if node is healthy (recent data)
            time_diff = datetime.utcnow() - latest.timestamp
            if time_diff.total_seconds() < 300:  # 5 minutes
                summary["healthy_nodes"] += 1

            # Aggregate metrics
            summary["total_memory_mb"] += latest.used_memory / (1024 * 1024)
            summary["total_ops_per_sec"] += latest.instantaneous_ops_per_sec
            summary["total_connections"] += latest.connected_clients

            if latest.keyspace_hit_ratio > 0:
                hit_ratios.append(latest.keyspace_hit_ratio)

        # Calculate averages
        if hit_ratios:
            summary["avg_hit_ratio"] = sum(hit_ratios) / len(hit_ratios)

        if latest_time:
            summary["last_update"] = latest_time.isoformat()

        return summary

    def get_alert_status(self) -> Dict[str, Any]:
        """Get current alert status."""
        return {
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules if r.enabled]),
            "active_alerts": len([r for r in self.alert_rules if r.last_triggered]),
            "rules": [
                {
                    "name": r.name,
                    "severity": r.severity.value,
                    "enabled": r.enabled,
                    "last_triggered": r.last_triggered.isoformat() if r.last_triggered else None,
                    "triggered_count": r.triggered_count
                }
                for r in self.alert_rules
            ]
        }


# ============================================================================
# Example Alert Handlers
# ============================================================================

def console_alert_handler(message: str, severity: AlertSeverity, timestamp: str):
    """Simple console alert handler."""
    print(f"[{timestamp}] {severity.value.upper()}: {message}")


async def webhook_alert_handler(
    webhook_url: str,
    message: str,
    severity: AlertSeverity,
    timestamp: str
):
    """Send alert to webhook endpoint."""
    import aiohttp

    payload = {
        "message": message,
        "severity": severity.value,
        "timestamp": timestamp,
        "service": "redis"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Webhook alert failed: {resp.status}")
    except Exception as e:
        logger.error(f"Webhook alert error: {e}")


if __name__ == "__main__":
    # Example usage
    async def main():
        # Create monitoring service
        monitoring = RedisMonitoringService()

        # Add console alert handler
        monitoring.add_alert_handler(console_alert_handler)

        # Start monitoring (would need actual Redis connection)
        # await monitoring.start_monitoring(interval_seconds=10)

        print("Redis monitoring service created")
        print(f"Alert rules loaded: {len(monitoring.alert_rules)}")

        # Show alert status
        status = monitoring.get_alert_status()
        print(f"Alert status: {status}")

    # Run example
    # asyncio.run(main())