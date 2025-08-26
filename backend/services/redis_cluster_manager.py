"""
Advanced Redis Cluster Management Service
Production-ready Redis cluster orchestration with high availability and auto-scaling.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Union

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.cluster import RedisCluster
from redis.retry import Retry
from redis.sentinel import Sentinel

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Classes
# ============================================================================

class ClusterMode(str, Enum):
    """Redis cluster deployment modes."""
    STANDALONE = "standalone"
    SENTINEL = "sentinel"
    CLUSTER = "cluster"
    SHARDED = "sharded"


class NodeRole(str, Enum):
    """Redis node roles."""
    MASTER = "master"
    REPLICA = "replica"
    SENTINEL = "sentinel"


@dataclass
class RedisNodeConfig:
    """Configuration for a Redis node."""
    host: str
    port: int
    role: NodeRole
    password: str | None = None
    db: int = 0
    max_connections: int = 100
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    health_check_interval: float = 30.0

    @property
    def address(self) -> str:
        """Get node address."""
        return f"{self.host}:{self.port}"


@dataclass
class ClusterConfig:
    """Redis cluster configuration."""
    mode: ClusterMode = ClusterMode.CLUSTER
    nodes: list[RedisNodeConfig] = field(default_factory=list)
    service_name: str = "mymaster"  # For Sentinel
    sentinel_nodes: list[RedisNodeConfig] = field(default_factory=list)

    # Connection settings
    max_connections_per_node: int = 100
    connection_pool_kwargs: dict[str, Any] = field(default_factory=dict)

    # Cluster settings
    skip_full_coverage_check: bool = False
    max_connections: int = 1000
    readonly_mode: bool = False
    decode_responses: bool = False

    # Health check settings
    health_check_interval: float = 30.0
    failure_threshold: int = 3
    recovery_threshold: int = 2

    # Auto-scaling settings
    enable_auto_scaling: bool = True
    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    connection_threshold: float = 90.0
    scale_up_cooldown: int = 300  # 5 minutes
    scale_down_cooldown: int = 600  # 10 minutes

    # Backup and replication
    enable_automatic_backup: bool = True
    backup_interval: int = 3600  # 1 hour
    retention_days: int = 7
    replication_factor: int = 2


# ============================================================================
# Node Health Monitoring
# ============================================================================

@dataclass
class NodeHealth:
    """Redis node health information."""
    node_id: str
    address: str
    role: NodeRole
    is_healthy: bool = True
    last_check: datetime = field(default_factory=datetime.utcnow)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    connections_count: int = 0
    operations_per_second: int = 0
    last_error: str | None = None

    def update_success(self, response_time_ms: float):
        """Update health on successful check."""
        self.is_healthy = True
        self.last_check = datetime.utcnow()
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.response_time_ms = response_time_ms
        self.last_error = None

    def update_failure(self, error: str):
        """Update health on failed check."""
        self.last_check = datetime.utcnow()
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_error = error

        # Mark unhealthy after threshold failures
        if self.consecutive_failures >= 3:
            self.is_healthy = False


# ============================================================================
# Redis Cluster Manager
# ============================================================================

class RedisClusterManager:
    """
    Advanced Redis cluster management with high availability and monitoring.
    """

    def __init__(self, config: ClusterConfig):
        """Initialize cluster manager."""
        self.config = config
        self._clients: dict[str, Redis] = {}
        self._cluster_client: Union[RedisCluster, Redis] | None = None
        self._sentinel_client: Sentinel | None = None
        self._node_health: dict[str, NodeHealth] = {}
        self._is_monitoring = False
        self._monitoring_task: asyncio.Task | None = None

        # Performance metrics
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "cluster_slots_coverage": 0.0,
            "healthy_nodes": 0,
            "total_nodes": 0
        }

        logger.info(f"Initialized Redis cluster manager for {config.mode} deployment")

    # ========================================================================
    # Cluster Initialization
    # ========================================================================

    async def initialize(self) -> bool:
        """Initialize Redis cluster connections."""
        try:
            if self.config.mode == ClusterMode.CLUSTER:
                await self._initialize_cluster()
            elif self.config.mode == ClusterMode.SENTINEL:
                await self._initialize_sentinel()
            elif self.config.mode == ClusterMode.STANDALONE:
                await self._initialize_standalone()
            else:
                raise ValueError(f"Unsupported cluster mode: {self.config.mode}")

            # Start health monitoring
            await self._start_monitoring()

            logger.info(f"Redis cluster initialized successfully in {self.config.mode} mode")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Redis cluster: {e}")
            return False

    async def _initialize_cluster(self):
        """Initialize Redis Cluster mode."""
        startup_nodes = [
            {"host": node.host, "port": node.port}
            for node in self.config.nodes
        ]

        self._cluster_client = RedisCluster(
            startup_nodes=startup_nodes,
            decode_responses=self.config.decode_responses,
            skip_full_coverage_check=self.config.skip_full_coverage_check,
            max_connections=self.config.max_connections,
            readonly_mode=self.config.readonly_mode,
            retry=Retry(ExponentialBackoff(), retries=3),
            **self.config.connection_pool_kwargs
        )

        # Test cluster connection
        await asyncio.to_thread(self._cluster_client.ping)

        # Initialize individual node clients for monitoring
        await self._initialize_node_clients()

    async def _initialize_sentinel(self):
        """Initialize Redis Sentinel mode."""
        sentinel_addresses = [
            (node.host, node.port)
            for node in self.config.sentinel_nodes
        ]

        self._sentinel_client = Sentinel(
            sentinel_addresses,
            socket_timeout=5.0,
            **self.config.connection_pool_kwargs
        )

        # Get master and replica connections
        master = self._sentinel_client.master_for(
            self.config.service_name,
            socket_timeout=5.0
        )

        # Test connection
        await asyncio.to_thread(master.ping)
        self._cluster_client = master

        # Initialize node health tracking
        await self._initialize_sentinel_health()

    async def _initialize_standalone(self):
        """Initialize standalone Redis mode."""
        if not self.config.nodes:
            raise ValueError("No nodes configured for standalone mode")

        node = self.config.nodes[0]
        self._cluster_client = Redis(
            host=node.host,
            port=node.port,
            password=node.password,
            db=node.db,
            max_connections=node.max_connections,
            socket_timeout=node.socket_timeout,
            socket_connect_timeout=node.socket_connect_timeout,
            decode_responses=self.config.decode_responses,
            **self.config.connection_pool_kwargs
        )

        # Test connection
        await asyncio.to_thread(self._cluster_client.ping)

    async def _initialize_node_clients(self):
        """Initialize individual node clients for monitoring."""
        for node in self.config.nodes:
            try:
                client = Redis(
                    host=node.host,
                    port=node.port,
                    password=node.password,
                    db=node.db,
                    socket_timeout=node.socket_timeout,
                    decode_responses=False
                )

                # Test connection
                await asyncio.to_thread(client.ping)

                node_id = node.address
                self._clients[node_id] = client
                self._node_health[node_id] = NodeHealth(
                    node_id=node_id,
                    address=node.address,
                    role=node.role
                )

                logger.debug(f"Initialized client for node {node_id}")

            except Exception as e:
                logger.error(f"Failed to initialize client for {node.address}: {e}")

    async def _initialize_sentinel_health(self):
        """Initialize health tracking for Sentinel mode."""
        try:
            # Get master info
            masters = self._sentinel_client.sentinel_masters()
            for master_name, master_info in masters.items():
                master_id = f"{master_info['ip']}:{master_info['port']}"
                self._node_health[master_id] = NodeHealth(
                    node_id=master_id,
                    address=master_id,
                    role=NodeRole.MASTER
                )

            # Get replica info
            replicas = self._sentinel_client.sentinel_replicas(self.config.service_name)
            for replica_info in replicas:
                replica_id = f"{replica_info['ip']}:{replica_info['port']}"
                self._node_health[replica_id] = NodeHealth(
                    node_id=replica_id,
                    address=replica_id,
                    role=NodeRole.REPLICA
                )

        except Exception as e:
            logger.error(f"Failed to initialize Sentinel health tracking: {e}")

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    async def _start_monitoring(self):
        """Start cluster health monitoring."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_cluster_health())
        logger.info("Started Redis cluster health monitoring")

    async def _monitor_cluster_health(self):
        """Monitor cluster health continuously."""
        while self._is_monitoring:
            try:
                await self._check_cluster_health()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cluster health monitoring: {e}")
                await asyncio.sleep(5)  # Short delay on error

    async def _check_cluster_health(self):
        """Check health of all cluster nodes."""
        healthy_nodes = 0
        total_nodes = len(self._node_health)

        # Check each node
        for node_id, health in self._node_health.items():
            try:
                start_time = time.time()

                if node_id in self._clients:
                    client = self._clients[node_id]

                    # Ping check
                    await asyncio.to_thread(client.ping)

                    # Get node info
                    info = await asyncio.to_thread(client.info)

                    # Calculate response time
                    response_time = (time.time() - start_time) * 1000

                    # Update health
                    health.update_success(response_time)
                    health.memory_usage_mb = info.get('used_memory', 0) / 1024 / 1024
                    health.connections_count = info.get('connected_clients', 0)
                    health.operations_per_second = info.get('instantaneous_ops_per_sec', 0)

                    if health.is_healthy:
                        healthy_nodes += 1

            except Exception as e:
                health.update_failure(str(e))
                logger.warning(f"Health check failed for node {node_id}: {e}")

        # Update cluster metrics
        self._metrics.update({
            "healthy_nodes": healthy_nodes,
            "total_nodes": total_nodes,
            "cluster_health_percentage": (healthy_nodes / total_nodes * 100) if total_nodes > 0 else 0
        })

        # Check if auto-scaling is needed
        if self.config.enable_auto_scaling:
            await self._check_auto_scaling()

    async def _check_auto_scaling(self):
        """Check if auto-scaling actions are needed."""
        try:
            # Calculate average resource usage
            healthy_nodes = [h for h in self._node_health.values() if h.is_healthy]
            if not healthy_nodes:
                return

            avg_memory = sum(h.memory_usage_mb for h in healthy_nodes) / len(healthy_nodes)
            avg_connections = sum(h.connections_count for h in healthy_nodes) / len(healthy_nodes)

            # Check for scale-up conditions
            memory_usage_percent = (avg_memory / 1000) * 100  # Assuming 1GB nodes
            connection_usage_percent = (avg_connections / 1000) * 100  # Assuming 1000 max connections

            if (memory_usage_percent > self.config.memory_threshold or
                connection_usage_percent > self.config.connection_threshold):

                logger.info(f"Auto-scaling triggered: Memory {memory_usage_percent:.1f}%, "
                          f"Connections {connection_usage_percent:.1f}%")
                await self._trigger_scale_up()

        except Exception as e:
            logger.error(f"Error in auto-scaling check: {e}")

    async def _trigger_scale_up(self):
        """Trigger cluster scale-up (implementation depends on infrastructure)."""
        # This would integrate with infrastructure automation (Kubernetes, Terraform, etc.)
        logger.info("Scale-up event triggered - would integrate with infrastructure automation")

        # Metrics for monitoring
        self._metrics["scale_events"] = self._metrics.get("scale_events", 0) + 1

        # Example: Send event to external scaling system
        # await self._notify_infrastructure_scaler("scale_up", {"reason": "resource_threshold"})

    # ========================================================================
    # Client Operations
    # ========================================================================

    def get_client(self) -> Union[Redis, RedisCluster]:
        """Get the main cluster client."""
        if not self._cluster_client:
            raise RuntimeError("Cluster not initialized")
        return self._cluster_client

    def get_node_client(self, node_id: str) -> Redis | None:
        """Get client for a specific node."""
        return self._clients.get(node_id)

    async def execute_on_all_nodes(
        self,
        command: str,
        *args,
        **kwargs
    ) -> dict[str, Any]:
        """Execute a command on all healthy nodes."""
        results = {}

        for node_id, client in self._clients.items():
            health = self._node_health.get(node_id)
            if health and health.is_healthy:
                try:
                    result = await asyncio.to_thread(
                        getattr(client, command.lower()),
                        *args,
                        **kwargs
                    )
                    results[node_id] = result
                except Exception as e:
                    results[node_id] = {"error": str(e)}
                    logger.error(f"Command {command} failed on node {node_id}: {e}")

        return results

    async def get_cluster_info(self) -> dict[str, Any]:
        """Get comprehensive cluster information."""
        info = {
            "mode": self.config.mode,
            "nodes": {},
            "metrics": self._metrics.copy(),
            "health_summary": {
                "healthy_nodes": sum(1 for h in self._node_health.values() if h.is_healthy),
                "total_nodes": len(self._node_health),
                "unhealthy_nodes": [
                    {"node_id": node_id, "error": h.last_error}
                    for node_id, h in self._node_health.items()
                    if not h.is_healthy
                ]
            }
        }

        # Add detailed node information
        for node_id, health in self._node_health.items():
            info["nodes"][node_id] = {
                "address": health.address,
                "role": health.role,
                "is_healthy": health.is_healthy,
                "response_time_ms": health.response_time_ms,
                "memory_usage_mb": health.memory_usage_mb,
                "connections_count": health.connections_count,
                "operations_per_second": health.operations_per_second,
                "last_check": health.last_check.isoformat(),
                "consecutive_failures": health.consecutive_failures
            }

        return info

    # ========================================================================
    # Failover and Recovery
    # ========================================================================

    async def handle_node_failure(self, node_id: str):
        """Handle node failure."""
        health = self._node_health.get(node_id)
        if not health:
            return

        logger.warning(f"Handling failure for node {node_id}")

        # Mark node as unhealthy
        health.is_healthy = False

        # For Sentinel mode, trigger failover if master fails
        if (self.config.mode == ClusterMode.SENTINEL and
            health.role == NodeRole.MASTER and
            self._sentinel_client):

            try:
                await asyncio.to_thread(
                    self._sentinel_client.sentinel_failover,
                    self.config.service_name
                )
                logger.info(f"Initiated failover for master {node_id}")
            except Exception as e:
                logger.error(f"Failed to initiate failover: {e}")

        # Notify monitoring system
        await self._notify_failure(node_id, health.last_error)

    async def _notify_failure(self, node_id: str, error: str):
        """Notify external systems about node failure."""
        # This would integrate with alerting systems
        logger.error(f"Node failure notification: {node_id} - {error}")

        # Example: Send to metrics/alerting system
        self._metrics["node_failures"] = self._metrics.get("node_failures", 0) + 1

    async def recover_node(self, node_id: str) -> bool:
        """Attempt to recover a failed node."""
        try:
            if node_id not in self._clients:
                logger.error(f"No client found for node {node_id}")
                return False

            client = self._clients[node_id]

            # Test connection
            await asyncio.to_thread(client.ping)

            # Update health
            health = self._node_health.get(node_id)
            if health:
                health.update_success(0.0)
                logger.info(f"Successfully recovered node {node_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to recover node {node_id}: {e}")

        return False

    # ========================================================================
    # Backup and Maintenance
    # ========================================================================

    async def create_cluster_backup(self) -> dict[str, Any]:
        """Create backup of cluster data."""
        backup_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": {},
            "success": False
        }

        try:
            # Execute BGSAVE on all healthy master nodes
            results = await self.execute_on_all_nodes("bgsave")

            for node_id, result in results.items():
                health = self._node_health.get(node_id)
                if health and health.role == NodeRole.MASTER:
                    backup_info["nodes"][node_id] = {
                        "result": result,
                        "timestamp": datetime.utcnow().isoformat()
                    }

            backup_info["success"] = True
            logger.info("Cluster backup initiated successfully")

        except Exception as e:
            logger.error(f"Failed to create cluster backup: {e}")
            backup_info["error"] = str(e)

        return backup_info

    async def get_cluster_metrics(self) -> dict[str, Any]:
        """Get detailed cluster performance metrics."""
        metrics = self._metrics.copy()

        # Add real-time metrics
        if self._cluster_client:
            try:
                info = await asyncio.to_thread(self._cluster_client.info)
                metrics.update({
                    "redis_version": info.get("redis_version"),
                    "uptime_in_seconds": info.get("uptime_in_seconds"),
                    "used_memory": info.get("used_memory"),
                    "used_memory_human": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                })

                # Calculate hit rate
                hits = info.get("keyspace_hits", 0)
                misses = info.get("keyspace_misses", 0)
                total = hits + misses
                metrics["hit_rate_percent"] = (hits / total * 100) if total > 0 else 0

            except Exception as e:
                logger.error(f"Failed to get cluster metrics: {e}")

        return metrics

    # ========================================================================
    # Cleanup
    # ========================================================================

    async def shutdown(self):
        """Shutdown cluster manager and cleanup resources."""
        logger.info("Shutting down Redis cluster manager")

        # Stop monitoring
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for client in self._clients.values():
            try:
                if hasattr(client, 'close'):
                    await asyncio.to_thread(client.close)
                elif hasattr(client, 'connection_pool'):
                    await asyncio.to_thread(client.connection_pool.disconnect)
            except Exception as e:
                logger.error(f"Error closing client connection: {e}")

        if self._cluster_client:
            try:
                if hasattr(self._cluster_client, 'close'):
                    await asyncio.to_thread(self._cluster_client.close)
                elif hasattr(self._cluster_client, 'connection_pool'):
                    await asyncio.to_thread(self._cluster_client.connection_pool.disconnect)
            except Exception as e:
                logger.error(f"Error closing cluster client: {e}")

        logger.info("Redis cluster manager shutdown complete")


# ============================================================================
# Cluster Factory
# ============================================================================

class RedisClusterFactory:
    """Factory for creating Redis cluster managers."""

    @staticmethod
    def create_from_config(config_dict: dict[str, Any]) -> RedisClusterManager:
        """Create cluster manager from configuration dictionary."""
        # Parse nodes
        nodes = []
        for node_config in config_dict.get("nodes", []):
            nodes.append(RedisNodeConfig(
                host=node_config["host"],
                port=node_config["port"],
                role=NodeRole(node_config.get("role", "master")),
                password=node_config.get("password"),
                db=node_config.get("db", 0),
                max_connections=node_config.get("max_connections", 100)
            ))

        # Parse sentinel nodes if present
        sentinel_nodes = []
        for sentinel_config in config_dict.get("sentinel_nodes", []):
            sentinel_nodes.append(RedisNodeConfig(
                host=sentinel_config["host"],
                port=sentinel_config["port"],
                role=NodeRole.SENTINEL,
                password=sentinel_config.get("password")
            ))

        # Create cluster config
        cluster_config = ClusterConfig(
            mode=ClusterMode(config_dict.get("mode", "cluster")),
            nodes=nodes,
            sentinel_nodes=sentinel_nodes,
            service_name=config_dict.get("service_name", "mymaster"),
            max_connections=config_dict.get("max_connections", 1000),
            enable_auto_scaling=config_dict.get("enable_auto_scaling", True),
            health_check_interval=config_dict.get("health_check_interval", 30.0)
        )

        return RedisClusterManager(cluster_config)

    @staticmethod
    def create_standalone(host: str = "localhost", port: int = 6379, **kwargs) -> RedisClusterManager:
        """Create standalone Redis cluster manager."""
        node = RedisNodeConfig(host=host, port=port, role=NodeRole.MASTER, **kwargs)
        config = ClusterConfig(mode=ClusterMode.STANDALONE, nodes=[node])
        return RedisClusterManager(config)

    @staticmethod
    def create_sentinel(
        sentinel_hosts: list[tuple[str, int]],
        service_name: str = "mymaster",
        **kwargs
    ) -> RedisClusterManager:
        """Create Sentinel-based cluster manager."""
        sentinel_nodes = [
            RedisNodeConfig(host=host, port=port, role=NodeRole.SENTINEL)
            for host, port in sentinel_hosts
        ]

        config = ClusterConfig(
            mode=ClusterMode.SENTINEL,
            sentinel_nodes=sentinel_nodes,
            service_name=service_name,
            **kwargs
        )

        return RedisClusterManager(config)


if __name__ == "__main__":
    # Example usage
    async def main():
        # Create a simple standalone cluster for testing
        manager = RedisClusterFactory.create_standalone()

        if await manager.initialize():
            print("Cluster initialized successfully")

            # Get cluster info
            info = await manager.get_cluster_info()
            print(f"Cluster info: {info}")

            # Wait a bit for health checks
            await asyncio.sleep(5)

            # Get metrics
            metrics = await manager.get_cluster_metrics()
            print(f"Cluster metrics: {metrics}")

        await manager.shutdown()

    # Run example
    # asyncio.run(main())
