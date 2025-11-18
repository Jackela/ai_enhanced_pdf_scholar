#!/usr/bin/env python3
"""
Intelligent Database Load Balancer for AI Enhanced PDF Scholar
Advanced load balancing across multiple database instances with health monitoring,
adaptive routing, and performance optimization.
"""

import hashlib
import logging
import random
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.database.read_write_splitter import QueryType, ReadWriteSplitter
    from backend.services.connection_pool_manager import AdvancedConnectionPoolManager
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_RESPONSE_TIME = "least_response_time"
    CONSISTENT_HASHING = "consistent_hashing"
    ADAPTIVE = "adaptive"


class ServerState(Enum):
    """Database server states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


@dataclass
class ServerMetrics:
    """Metrics for a database server."""

    server_id: str
    connection_count: int = 0
    active_queries: int = 0
    avg_response_time_ms: float = 0.0
    last_response_time_ms: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_io_rate: float = 0.0
    network_io_rate: float = 0.0
    last_health_check: float = field(default_factory=time.time)
    health_check_failures: int = 0
    state: ServerState = ServerState.HEALTHY

    def update_response_time(self, response_time_ms: float) -> None:
        """Update response time metrics."""
        self.last_response_time_ms = response_time_ms
        self.total_requests += 1

        # Update rolling average
        alpha = 0.1  # Smoothing factor
        self.avg_response_time_ms = (
            alpha * response_time_ms + (1 - alpha) * self.avg_response_time_ms
        )

    def get_health_score(self) -> float:
        """Calculate server health score (0-100)."""
        if self.state == ServerState.FAILED or self.state == ServerState.MAINTENANCE:
            return 0.0
        elif self.state == ServerState.DEGRADED:
            base_score = 50.0
        else:  # HEALTHY
            base_score = 100.0

        # Adjust based on performance metrics
        response_penalty = min(
            50, self.avg_response_time_ms / 10
        )  # Penalty for slow responses
        failure_penalty = min(
            30, self.health_check_failures * 10
        )  # Penalty for failures

        score = base_score - response_penalty - failure_penalty
        return max(0.0, min(100.0, score))


@dataclass
class DatabaseServer:
    """Represents a database server in the load balancer."""

    server_id: str
    connection_string: str
    weight: int = 100
    max_connections: int = 50
    role: str = "replica"  # primary, replica, analytics
    region: str = "default"
    availability_zone: str = "default"
    metrics: ServerMetrics = field(default_factory=lambda: None)
    connection_pool: AdvancedConnectionPoolManager | None = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ServerMetrics(self.server_id)


@dataclass
class LoadBalancingRequest:
    """Represents a load balancing request."""

    request_id: str
    query_type: QueryType
    client_id: str | None = None
    session_id: str | None = None
    preferred_region: str | None = None
    preferred_server: str | None = None
    consistency_level: str = "eventual"  # strong, eventual, weak
    priority: int = 5  # 1-10, higher = more important
    timeout_ms: int = 30000


@dataclass
class RoutingDecision:
    """Result of load balancing decision."""

    selected_server: DatabaseServer
    routing_reason: str
    backup_servers: list[DatabaseServer]
    estimated_response_time_ms: float
    routing_metadata: dict[str, Any] = field(default_factory=dict)


class DatabaseLoadBalancer:
    """
    Intelligent Database Load Balancer

    Features:
    - Multiple load balancing strategies
    - Health monitoring and failover
    - Session affinity and consistency guarantees
    - Performance-based adaptive routing
    - Geographic and zone-aware routing
    - Circuit breaker pattern
    - Weighted routing with automatic weight adjustment
    """

    def __init__(
        self,
        servers: list[DatabaseServer],
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ADAPTIVE,
        health_check_interval_s: int = 30,
        enable_circuit_breaker: bool = True,
        enable_session_affinity: bool = True,
    ):
        """
        Initialize the Database Load Balancer.

        Args:
            servers: List of database servers to balance across
            strategy: Load balancing strategy to use
            health_check_interval_s: Health check interval in seconds
            enable_circuit_breaker: Whether to enable circuit breaker pattern
            enable_session_affinity: Whether to enable session affinity
        """
        self.servers = {server.server_id: server for server in servers}
        self.strategy = strategy
        self.health_check_interval_s = health_check_interval_s
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_session_affinity = enable_session_affinity

        # Routing state
        self._round_robin_index = 0
        self._consistent_hash_ring: dict[int, str] = {}
        self._session_affinity: dict[str, str] = {}  # session_id -> server_id
        self._client_affinity: dict[str, str] = {}  # client_id -> server_id

        # Circuit breaker state
        self._circuit_breaker_state: dict[str, dict[str, Any]] = {}

        # Performance tracking
        self._response_times: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._error_rates: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Thread safety
        self._routing_lock = threading.RLock()
        self._metrics_lock = threading.Lock()

        # Background monitoring
        self._health_monitor_thread: threading.Thread | None = None
        self._metrics_collector_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Initialize components
        self._initialize_servers()
        self._initialize_consistent_hashing()
        self._initialize_circuit_breakers()
        self._start_background_tasks()

    def _initialize_servers(self) -> None:
        """Initialize database server connections and pools."""
        for server in self.servers.values():
            try:
                # Initialize connection pool for each server
                from backend.services.connection_pool_manager import PoolConfiguration

                config = PoolConfiguration(
                    max_connections=server.max_connections,
                    min_connections=min(5, server.max_connections // 4),
                    initial_connections=min(3, server.max_connections // 8),
                )

                server.connection_pool = AdvancedConnectionPoolManager(
                    server.connection_string, config
                )

                logger.info(
                    f"Initialized server {server.server_id} with connection pool"
                )

            except Exception as e:
                logger.error(f"Failed to initialize server {server.server_id}: {e}")
                server.metrics.state = ServerState.FAILED

    def _initialize_consistent_hashing(self) -> None:
        """Initialize consistent hashing ring."""
        if self.strategy != LoadBalancingStrategy.CONSISTENT_HASHING:
            return

        # Create virtual nodes for each server
        virtual_nodes_per_server = 100

        for server in self.servers.values():
            if server.metrics.state != ServerState.FAILED:
                for i in range(virtual_nodes_per_server * server.weight // 100):
                    virtual_node_key = f"{server.server_id}:{i}"
                    hash_value = int(
                        hashlib.sha256(virtual_node_key.encode()).hexdigest(), 16
                    )
                    self._consistent_hash_ring[hash_value] = server.server_id

        logger.info(
            f"Initialized consistent hashing with {len(self._consistent_hash_ring)} virtual nodes"
        )

    def _initialize_circuit_breakers(self) -> None:
        """Initialize circuit breakers for each server."""
        if not self.enable_circuit_breaker:
            return

        for server_id in self.servers:
            self._circuit_breaker_state[server_id] = {
                "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
                "failure_count": 0,
                "last_failure_time": 0,
                "success_count": 0,
                "next_attempt_time": 0,
                "failure_threshold": 5,
                "success_threshold": 3,
                "timeout_ms": 60000,  # 1 minute
            }

    def _start_background_tasks(self) -> None:
        """Start background monitoring and optimization tasks."""
        # Health monitoring thread
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_worker,
            daemon=True,
            name="DBLoadBalancerHealthMonitor",
        )
        self._health_monitor_thread.start()

        # Metrics collection thread
        self._metrics_collector_thread = threading.Thread(
            target=self._metrics_collector_worker,
            daemon=True,
            name="DBLoadBalancerMetricsCollector",
        )
        self._metrics_collector_thread.start()

        logger.info("Load balancer background tasks started")

    def _health_monitor_worker(self) -> None:
        """Background worker for health monitoring."""
        while not self._shutdown_event.wait(self.health_check_interval_s):
            try:
                self._perform_health_checks()
                self._update_circuit_breakers()
                self._adjust_server_weights()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _metrics_collector_worker(self) -> None:
        """Background worker for metrics collection."""
        while not self._shutdown_event.wait(10):  # Every 10 seconds
            try:
                self._collect_server_metrics()
                self._cleanup_old_metrics()
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")

    def _perform_health_checks(self) -> None:
        """Perform health checks on all servers."""
        for server in self.servers.values():
            try:
                if server.connection_pool is None:
                    server.metrics.state = ServerState.FAILED
                    continue

                # Perform health check query
                start_time = time.time()
                managed_conn = server.connection_pool.acquire_connection(
                    timeout_ms=5000
                )

                try:
                    cursor = managed_conn.connection.execute("SELECT 1 as health_check")
                    result = cursor.fetchone()
                    health_check_time = (time.time() - start_time) * 1000

                    # Update metrics
                    server.metrics.last_health_check = time.time()
                    server.metrics.health_check_failures = 0

                    # Update server state based on response time
                    if health_check_time > 1000:  # > 1 second
                        server.metrics.state = ServerState.DEGRADED
                    else:
                        server.metrics.state = ServerState.HEALTHY

                    logger.debug(
                        f"Health check for {server.server_id}: {health_check_time:.2f}ms"
                    )

                finally:
                    server.connection_pool.release_connection(
                        managed_conn, health_check_time, True
                    )

            except Exception as e:
                server.metrics.health_check_failures += 1
                server.metrics.last_health_check = time.time()

                if server.metrics.health_check_failures >= 3:
                    server.metrics.state = ServerState.FAILED
                    logger.warning(f"Server {server.server_id} marked as failed: {e}")
                else:
                    server.metrics.state = ServerState.DEGRADED
                    logger.debug(f"Health check failed for {server.server_id}: {e}")

    def _update_circuit_breakers(self) -> None:
        """Update circuit breaker states based on recent performance."""
        if not self.enable_circuit_breaker:
            return

        current_time = time.time() * 1000  # Convert to milliseconds

        for server_id, cb_state in self._circuit_breaker_state.items():
            server = self.servers[server_id]

            if cb_state["state"] == "OPEN":
                # Check if timeout has passed to try half-open
                if current_time >= cb_state["next_attempt_time"]:
                    cb_state["state"] = "HALF_OPEN"
                    cb_state["success_count"] = 0
                    logger.info(f"Circuit breaker for {server_id} moved to HALF_OPEN")

            elif cb_state["state"] == "HALF_OPEN":
                # Check if we have enough successes to close
                if cb_state["success_count"] >= cb_state["success_threshold"]:
                    cb_state["state"] = "CLOSED"
                    cb_state["failure_count"] = 0
                    logger.info(f"Circuit breaker for {server_id} moved to CLOSED")

            elif cb_state["state"] == "CLOSED":
                # Check if we should open due to failures
                if (
                    server.metrics.state == ServerState.FAILED
                    and cb_state["failure_count"] >= cb_state["failure_threshold"]
                ):
                    cb_state["state"] = "OPEN"
                    cb_state["next_attempt_time"] = (
                        current_time + cb_state["timeout_ms"]
                    )
                    logger.warning(f"Circuit breaker for {server_id} moved to OPEN")

    def _collect_server_metrics(self) -> None:
        """Collect and update server metrics."""
        with self._metrics_lock:
            for server in self.servers.values():
                try:
                    if server.connection_pool:
                        pool_stats = server.connection_pool.get_statistics()

                        # Update connection metrics
                        server.metrics.connection_count = pool_stats.active_connections
                        server.metrics.total_requests = pool_stats.total_requests
                        server.metrics.successful_requests = (
                            pool_stats.successful_requests
                        )
                        server.metrics.failed_requests = pool_stats.failed_requests

                        # Update response time from pool statistics
                        if pool_stats.avg_response_time_ms > 0:
                            server.metrics.avg_response_time_ms = (
                                pool_stats.avg_response_time_ms
                            )

                except Exception as e:
                    logger.debug(
                        f"Failed to collect metrics for {server.server_id}: {e}"
                    )

    def _adjust_server_weights(self) -> None:
        """Dynamically adjust server weights based on performance."""
        if self.strategy != LoadBalancingStrategy.ADAPTIVE:
            return

        # Calculate new weights based on performance metrics
        for server in self.servers.values():
            if (
                server.metrics.state == ServerState.FAILED
                or server.metrics.state == ServerState.MAINTENANCE
            ):
                server.weight = 0
                continue

            # Base weight calculation on health score
            health_score = server.metrics.get_health_score()

            # Adjust for response time (lower is better)
            response_time_factor = max(
                0.1, 100 / max(1, server.metrics.avg_response_time_ms)
            )

            # Adjust for connection utilization
            if server.connection_pool:
                pool_stats = server.connection_pool.get_statistics()
                utilization = pool_stats.active_connections / max(
                    1, pool_stats.total_connections
                )
                utilization_factor = max(0.1, 1.0 - min(0.9, utilization))
            else:
                utilization_factor = 0.1

            # Calculate new weight
            new_weight = int(health_score * response_time_factor * utilization_factor)
            server.weight = max(
                1, min(200, new_weight)
            )  # Keep within reasonable bounds

            logger.debug(f"Adjusted weight for {server.server_id}: {server.weight}")

    def _cleanup_old_metrics(self) -> None:
        """Clean up old performance metrics."""
        with self._metrics_lock:
            # Keep only recent metrics (last 1000 samples)
            for server_id in list(self._response_times.keys()):
                if len(self._response_times[server_id]) > 1000:
                    # Keep only the most recent 500
                    recent_times = list(self._response_times[server_id])[-500:]
                    self._response_times[server_id] = deque(recent_times, maxlen=100)

                if len(self._error_rates[server_id]) > 1000:
                    recent_errors = list(self._error_rates[server_id])[-500:]
                    self._error_rates[server_id] = deque(recent_errors, maxlen=100)

    def select_server(self, request: LoadBalancingRequest) -> RoutingDecision:
        """
        Select the best server for a request based on the current strategy.

        Args:
            request: Load balancing request

        Returns:
            RoutingDecision with selected server and metadata
        """
        with self._routing_lock:
            # Filter available servers
            available_servers = self._get_available_servers(request)

            if not available_servers:
                raise RuntimeError("No available database servers")

            # Apply load balancing strategy
            if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                selected_server = self._select_round_robin(available_servers)
                reason = "round_robin"
            elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                selected_server = self._select_least_connections(available_servers)
                reason = "least_connections"
            elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                selected_server = self._select_weighted_round_robin(available_servers)
                reason = "weighted_round_robin"
            elif self.strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
                selected_server = self._select_least_response_time(available_servers)
                reason = "least_response_time"
            elif self.strategy == LoadBalancingStrategy.CONSISTENT_HASHING:
                selected_server = self._select_consistent_hashing(
                    available_servers, request
                )
                reason = "consistent_hashing"
            else:  # ADAPTIVE
                selected_server = self._select_adaptive(available_servers, request)
                reason = "adaptive"

            # Check session/client affinity
            if self.enable_session_affinity:
                affinity_server = self._check_affinity(request, available_servers)
                if affinity_server and affinity_server != selected_server:
                    selected_server = affinity_server
                    reason = f"{reason}_with_affinity"

            # Prepare backup servers
            backup_servers = [s for s in available_servers if s != selected_server]
            backup_servers.sort(
                key=lambda s: s.metrics.get_health_score(), reverse=True
            )
            backup_servers = backup_servers[:3]  # Top 3 backups

            # Estimate response time
            estimated_response_time = selected_server.metrics.avg_response_time_ms

            # Update affinity tracking
            if self.enable_session_affinity:
                if request.session_id:
                    self._session_affinity[request.session_id] = (
                        selected_server.server_id
                    )
                if request.client_id:
                    self._client_affinity[request.client_id] = selected_server.server_id

            return RoutingDecision(
                selected_server=selected_server,
                routing_reason=reason,
                backup_servers=backup_servers,
                estimated_response_time_ms=estimated_response_time,
                routing_metadata={
                    "request_id": request.request_id,
                    "strategy": self.strategy.value,
                    "available_servers": len(available_servers),
                    "server_health_score": selected_server.metrics.get_health_score(),
                },
            )

    def _get_available_servers(
        self, request: LoadBalancingRequest
    ) -> list[DatabaseServer]:
        """Get list of available servers for a request."""
        available_servers = []

        for server in self.servers.values():
            # Check basic availability
            if server.metrics.state == ServerState.FAILED:
                continue

            # Check circuit breaker
            if self.enable_circuit_breaker:
                cb_state = self._circuit_breaker_state[server.server_id]
                if cb_state["state"] == "OPEN":
                    continue

            # Check role compatibility
            if request.query_type == QueryType.WRITE and server.role not in [
                "primary",
                "master",
            ]:
                continue

            # Check region preference
            if (
                request.preferred_region
                and server.region != request.preferred_region
                and server.region != "default"
            ):
                continue

            available_servers.append(server)

        return available_servers

    def _select_round_robin(self, servers: list[DatabaseServer]) -> DatabaseServer:
        """Select server using round-robin algorithm."""
        self._round_robin_index = (self._round_robin_index + 1) % len(servers)
        return servers[self._round_robin_index]

    def _select_least_connections(
        self, servers: list[DatabaseServer]
    ) -> DatabaseServer:
        """Select server with least connections."""
        return min(servers, key=lambda s: s.metrics.connection_count)

    def _select_weighted_round_robin(
        self, servers: list[DatabaseServer]
    ) -> DatabaseServer:
        """Select server using weighted round-robin."""
        # Calculate total weight
        total_weight = sum(s.weight for s in servers)

        if total_weight == 0:
            return self._select_round_robin(servers)

        # Generate weighted random selection
        random_weight = random.randint(1, total_weight)

        cumulative_weight = 0
        for server in servers:
            cumulative_weight += server.weight
            if random_weight <= cumulative_weight:
                return server

        # Fallback
        return servers[-1]

    def _select_least_response_time(
        self, servers: list[DatabaseServer]
    ) -> DatabaseServer:
        """Select server with best response time."""
        return min(
            servers, key=lambda s: s.metrics.avg_response_time_ms or float("inf")
        )

    def _select_consistent_hashing(
        self, servers: list[DatabaseServer], request: LoadBalancingRequest
    ) -> DatabaseServer:
        """Select server using consistent hashing."""
        # Use session_id or client_id for consistency
        hash_key = request.session_id or request.client_id or request.request_id
        hash_value = int(hashlib.sha256(hash_key.encode()).hexdigest(), 16)

        # Find the nearest server in the hash ring
        available_server_ids = {s.server_id for s in servers}

        # Find the first server in the ring that's available
        sorted_ring = sorted(self._consistent_hash_ring.keys())

        for ring_hash in sorted_ring:
            if ring_hash >= hash_value:
                server_id = self._consistent_hash_ring[ring_hash]
                if server_id in available_server_ids:
                    return next(s for s in servers if s.server_id == server_id)

        # Wrap around to beginning of ring
        for ring_hash in sorted_ring:
            server_id = self._consistent_hash_ring[ring_hash]
            if server_id in available_server_ids:
                return next(s for s in servers if s.server_id == server_id)

        # Fallback
        return servers[0]

    def _select_adaptive(
        self, servers: list[DatabaseServer], request: LoadBalancingRequest
    ) -> DatabaseServer:
        """Select server using adaptive algorithm combining multiple factors."""

        def calculate_score(server: DatabaseServer) -> float:
            """Calculate adaptive score for server (higher is better)."""
            health_score = server.metrics.get_health_score()

            # Response time score (lower time = higher score)
            response_time_score = max(0, 100 - server.metrics.avg_response_time_ms / 10)

            # Connection utilization score
            if server.connection_pool:
                pool_stats = server.connection_pool.get_statistics()
                utilization = pool_stats.active_connections / max(
                    1, pool_stats.total_connections
                )
                utilization_score = max(0, 100 - utilization * 100)
            else:
                utilization_score = 0

            # Weight factor
            weight_score = server.weight

            # Priority bonus for certain request types
            priority_bonus = 0
            if request.priority >= 8 and server.role == "primary":
                priority_bonus = 20
            elif request.query_type == QueryType.READ and server.role == "replica":
                priority_bonus = 10

            # Combine scores with weights
            total_score = (
                health_score * 0.3
                + response_time_score * 0.25
                + utilization_score * 0.2
                + weight_score * 0.15
                + priority_bonus * 0.1
            )

            return total_score

        # Select server with highest adaptive score
        return max(servers, key=calculate_score)

    def _check_affinity(
        self, request: LoadBalancingRequest, available_servers: list[DatabaseServer]
    ) -> DatabaseServer | None:
        """Check for session or client affinity."""
        # Check session affinity
        if request.session_id and request.session_id in self._session_affinity:
            server_id = self._session_affinity[request.session_id]
            for server in available_servers:
                if server.server_id == server_id:
                    return server

        # Check client affinity
        if request.client_id and request.client_id in self._client_affinity:
            server_id = self._client_affinity[request.client_id]
            for server in available_servers:
                if server.server_id == server_id:
                    return server

        return None

    def record_request_result(
        self, server_id: str, response_time_ms: float, success: bool
    ) -> None:
        """
        Record the result of a request for performance tracking.

        Args:
            server_id: ID of the server that handled the request
            response_time_ms: Response time in milliseconds
            success: Whether the request was successful
        """
        if server_id not in self.servers:
            return

        server = self.servers[server_id]

        # Update server metrics
        server.metrics.update_response_time(response_time_ms)

        if success:
            server.metrics.successful_requests += 1
        else:
            server.metrics.failed_requests += 1

        # Update circuit breaker state
        if self.enable_circuit_breaker:
            cb_state = self._circuit_breaker_state[server_id]

            if success:
                cb_state["failure_count"] = 0
                if cb_state["state"] == "HALF_OPEN":
                    cb_state["success_count"] += 1
            else:
                cb_state["failure_count"] += 1
                cb_state["last_failure_time"] = time.time() * 1000

        # Store performance data
        with self._metrics_lock:
            self._response_times[server_id].append(response_time_ms)
            self._error_rates[server_id].append(0 if success else 1)

    def get_load_balancer_statistics(self) -> dict[str, Any]:
        """Get comprehensive load balancer statistics."""
        stats = {
            "strategy": self.strategy.value,
            "total_servers": len(self.servers),
            "healthy_servers": 0,
            "degraded_servers": 0,
            "failed_servers": 0,
            "servers": {},
            "routing_stats": {
                "session_affinity_entries": len(self._session_affinity),
                "client_affinity_entries": len(self._client_affinity),
            },
            "circuit_breaker_stats": {},
        }

        # Collect server statistics
        for server_id, server in self.servers.items():
            server_stats = {
                "state": server.metrics.state.value,
                "weight": server.weight,
                "role": server.role,
                "region": server.region,
                "health_score": server.metrics.get_health_score(),
                "connection_count": server.metrics.connection_count,
                "avg_response_time_ms": server.metrics.avg_response_time_ms,
                "total_requests": server.metrics.total_requests,
                "successful_requests": server.metrics.successful_requests,
                "failed_requests": server.metrics.failed_requests,
                "health_check_failures": server.metrics.health_check_failures,
                "last_health_check": server.metrics.last_health_check,
            }

            stats["servers"][server_id] = server_stats

            # Count server states
            if server.metrics.state == ServerState.HEALTHY:
                stats["healthy_servers"] += 1
            elif server.metrics.state == ServerState.DEGRADED:
                stats["degraded_servers"] += 1
            elif server.metrics.state == ServerState.FAILED:
                stats["failed_servers"] += 1

        # Collect circuit breaker statistics
        if self.enable_circuit_breaker:
            for server_id, cb_state in self._circuit_breaker_state.items():
                stats["circuit_breaker_stats"][server_id] = {
                    "state": cb_state["state"],
                    "failure_count": cb_state["failure_count"],
                    "success_count": cb_state["success_count"],
                    "last_failure_time": cb_state["last_failure_time"],
                }

        return stats

    def add_server(self, server: DatabaseServer) -> bool:
        """
        Add a new server to the load balancer.

        Args:
            server: DatabaseServer to add

        Returns:
            True if added successfully
        """
        try:
            with self._routing_lock:
                if server.server_id in self.servers:
                    logger.warning(f"Server {server.server_id} already exists")
                    return False

                # Initialize server
                self._initialize_single_server(server)
                self.servers[server.server_id] = server

                # Update consistent hashing if needed
                if self.strategy == LoadBalancingStrategy.CONSISTENT_HASHING:
                    self._add_server_to_hash_ring(server)

                # Initialize circuit breaker
                if self.enable_circuit_breaker:
                    self._circuit_breaker_state[server.server_id] = {
                        "state": "CLOSED",
                        "failure_count": 0,
                        "last_failure_time": 0,
                        "success_count": 0,
                        "next_attempt_time": 0,
                        "failure_threshold": 5,
                        "success_threshold": 3,
                        "timeout_ms": 60000,
                    }

                logger.info(f"Added server {server.server_id} to load balancer")
                return True

        except Exception as e:
            logger.error(f"Failed to add server {server.server_id}: {e}")
            return False

    def remove_server(self, server_id: str) -> bool:
        """
        Remove a server from the load balancer.

        Args:
            server_id: ID of server to remove

        Returns:
            True if removed successfully
        """
        try:
            with self._routing_lock:
                if server_id not in self.servers:
                    logger.warning(f"Server {server_id} not found")
                    return False

                server = self.servers[server_id]

                # Close connection pool
                if server.connection_pool:
                    server.connection_pool.shutdown()

                # Remove from servers
                del self.servers[server_id]

                # Remove from consistent hashing if needed
                if self.strategy == LoadBalancingStrategy.CONSISTENT_HASHING:
                    self._remove_server_from_hash_ring(server_id)

                # Clean up circuit breaker
                if self.enable_circuit_breaker:
                    self._circuit_breaker_state.pop(server_id, None)

                # Clean up affinity
                sessions_to_remove = [
                    sid
                    for sid, sid_server_id in self._session_affinity.items()
                    if sid_server_id == server_id
                ]
                for sid in sessions_to_remove:
                    del self._session_affinity[sid]

                clients_to_remove = [
                    cid
                    for cid, cid_server_id in self._client_affinity.items()
                    if cid_server_id == server_id
                ]
                for cid in clients_to_remove:
                    del self._client_affinity[cid]

                # Clean up metrics
                with self._metrics_lock:
                    self._response_times.pop(server_id, None)
                    self._error_rates.pop(server_id, None)

                logger.info(f"Removed server {server_id} from load balancer")
                return True

        except Exception as e:
            logger.error(f"Failed to remove server {server_id}: {e}")
            return False

    def _initialize_single_server(self, server: DatabaseServer) -> None:
        """Initialize a single server's connection pool."""
        try:
            from backend.services.connection_pool_manager import PoolConfiguration

            config = PoolConfiguration(
                max_connections=server.max_connections,
                min_connections=min(5, server.max_connections // 4),
                initial_connections=min(3, server.max_connections // 8),
            )

            server.connection_pool = AdvancedConnectionPoolManager(
                server.connection_string, config
            )

        except Exception as e:
            logger.error(f"Failed to initialize server {server.server_id}: {e}")
            server.metrics.state = ServerState.FAILED

    def _add_server_to_hash_ring(self, server: DatabaseServer) -> None:
        """Add server to consistent hashing ring."""
        virtual_nodes_per_server = 100

        for i in range(virtual_nodes_per_server * server.weight // 100):
            virtual_node_key = f"{server.server_id}:{i}"
            hash_value = int(hashlib.sha256(virtual_node_key.encode()).hexdigest(), 16)
            self._consistent_hash_ring[hash_value] = server.server_id

    def _remove_server_from_hash_ring(self, server_id: str) -> None:
        """Remove server from consistent hashing ring."""
        keys_to_remove = [
            k for k, v in self._consistent_hash_ring.items() if v == server_id
        ]

        for key in keys_to_remove:
            del self._consistent_hash_ring[key]

    def shutdown(self) -> None:
        """Shutdown the load balancer and cleanup resources."""
        self._shutdown_event.set()

        # Wait for background threads
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5)

        if self._metrics_collector_thread:
            self._metrics_collector_thread.join(timeout=5)

        # Shutdown all server connection pools
        for server in self.servers.values():
            if server.connection_pool:
                server.connection_pool.shutdown()

        logger.info("Database load balancer shutdown complete")


def main():
    """CLI interface for testing the Database Load Balancer."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Load Balancer")
    parser.add_argument("--config", help="Configuration file with server definitions")
    parser.add_argument(
        "--stats", action="store_true", help="Show load balancer statistics"
    )
    parser.add_argument("--test", action="store_true", help="Run load balancing test")
    parser.add_argument(
        "--strategy",
        choices=["round_robin", "least_connections", "adaptive"],
        default="adaptive",
        help="Load balancing strategy",
    )

    args = parser.parse_args()

    try:
        # Create sample servers for testing
        servers = [
            DatabaseServer(
                server_id="db1",
                connection_string="sqlite:///test_db1.db",
                weight=100,
                max_connections=20,
                role="primary",
            ),
            DatabaseServer(
                server_id="db2",
                connection_string="sqlite:///test_db2.db",
                weight=80,
                max_connections=15,
                role="replica",
            ),
            DatabaseServer(
                server_id="db3",
                connection_string="sqlite:///test_db3.db",
                weight=60,
                max_connections=10,
                role="replica",
            ),
        ]

        # Initialize load balancer
        strategy = LoadBalancingStrategy(args.strategy)
        load_balancer = DatabaseLoadBalancer(
            servers=servers,
            strategy=strategy,
            enable_circuit_breaker=True,
            enable_session_affinity=True,
        )

        if args.test:
            print("Testing load balancer routing...")

            # Create test requests
            for i in range(20):
                request = LoadBalancingRequest(
                    request_id=f"req_{i}",
                    query_type=QueryType.READ if i % 3 != 0 else QueryType.WRITE,
                    client_id=f"client_{i % 3}",
                    session_id=f"session_{i % 5}",
                    priority=random.randint(1, 10),
                )

                try:
                    decision = load_balancer.select_server(request)
                    print(
                        f"Request {i}: {decision.selected_server.server_id} "
                        f"({decision.routing_reason}) - "
                        f"Est: {decision.estimated_response_time_ms:.2f}ms"
                    )

                    # Simulate request completion
                    response_time = random.uniform(10, 200)
                    success = random.random() > 0.1  # 90% success rate

                    load_balancer.record_request_result(
                        decision.selected_server.server_id, response_time, success
                    )

                except Exception as e:
                    print(f"Request {i} failed: {e}")

            print("Load balancing test completed")

        if args.stats:
            stats = load_balancer.get_load_balancer_statistics()
            print("Load Balancer Statistics:")
            print(f"Strategy: {stats['strategy']}")
            print(f"Total Servers: {stats['total_servers']}")
            print(
                f"Healthy: {stats['healthy_servers']}, "
                f"Degraded: {stats['degraded_servers']}, "
                f"Failed: {stats['failed_servers']}"
            )

            print("\nServer Details:")
            for server_id, server_stats in stats["servers"].items():
                print(f"  {server_id} ({server_stats['role']}):")
                print(f"    State: {server_stats['state']}")
                print(f"    Health Score: {server_stats['health_score']:.1f}")
                print(f"    Requests: {server_stats['total_requests']}")
                print(f"    Avg Response: {server_stats['avg_response_time_ms']:.2f}ms")
                print(f"    Weight: {server_stats['weight']}")

        load_balancer.shutdown()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
